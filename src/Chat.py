import io
import json
import math
import sys
from pathlib import Path
import traceback
from typing import Any

from openai import OpenAI

from lib.Config import Config, get_ed_appdata_path, get_ed_journals_path
from lib.ActionManager import ActionManager
from lib.Actions import register_actions
from lib.ControllerManager import ControllerManager
from lib.EDCoPilot import EDCoPilot
from lib.EDKeys import EDKeys
from lib.Event import Event
from lib.Projections import registerProjections
from lib.PromptGenerator import PromptGenerator
from lib.STT import STT
from lib.TTS import TTS
from lib.StatusParser import StatusParser

# from MousePt import MousePoint

# Add the parent directory to sys.path
parent_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(parent_dir))

from lib.EDJournal import *
from lib.EventManager import EventManager

llm_model_name = None
llmClient = None
sttClient = None
ttsClient = None
visionClient = None

action_manager = ActionManager()

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def load_config() -> Config:
    config_file = Path("config.json")
    if config_file.exists():
        with open(config_file, 'r') as f:
            return json.load(f)
    raise FileNotFoundError("config.json not found")

is_thinking = False

def reply(client, events: list[Event], new_events: list[Event], projected_states: dict[str, dict], prompt_generator: PromptGenerator,
          event_manager: EventManager, tts: TTS, copilot: EDCoPilot, config: Config):
    global is_thinking
    is_thinking = True
    prompt = prompt_generator.generate_prompt(events=events, projected_states=projected_states, pending_events=new_events)

    use_tools = useTools and any([event.kind == 'user' for event in new_events])
    reasons = [event.content.get('event', event.kind) if event.kind=='game' else event.kind for event in new_events if event.kind in ['user', 'game', 'tool', 'status']]

    current_status = projected_states.get("CurrentStatus")
    flags = current_status["flags"]
    flags2 = current_status["flags2"]

    active_mode = None
    if flags:
        if flags["InMainShip"]:
            active_mode = "mainship"
        elif flags["InFighter"]:
            active_mode = "fighter"
        elif flags["InSRV"]:
            active_mode = "buggy"
    if flags2:
        if flags2["OnFoot"]:
            active_mode = "humanoid"

    uses_actions = config["game_actions_var"]
    uses_web_actions = config["web_search_actions_var"]
    tool_list = action_manager.getToolsList(active_mode, uses_actions, uses_web_actions)
    completion = client.chat.completions.create(
        model=llm_model_name,
        messages=prompt,
        tools= tool_list if use_tools and tool_list else None
    )

    if hasattr(completion, 'error'):
        log("error", "completion with error:", completion)
        is_thinking = False
        return
    log("Debug", f'Prompt: {completion.usage.prompt_tokens}, Completion: {completion.usage.completion_tokens}')

    response_text = completion.choices[0].message.content
    if response_text:
        tts.say(response_text)
        event_manager.add_conversation_event('assistant', completion.choices[0].message.content)
        copilot.output_covas(response_text, reasons)
    is_thinking = False

    response_actions = completion.choices[0].message.tool_calls
    if response_actions:
        action_results = []
        for action in response_actions:
            action_result = action_manager.runAction(action)
            action_results.append(action_result)

        event_manager.add_tool_call([tool_call.model_dump() for tool_call in response_actions], action_results)


useTools = False


jn: EDJournal | None = None
tts: TTS | None = None
prompt_generator: PromptGenerator | None = None
status_parser: StatusParser | None = None
event_manager: EventManager | None = None

controller_manager = ControllerManager()


def bio_scan(content: dict[str, Any], scans:list[dict[str, Any]], scan_in_progress:bool, scan_radius:int):
    colony_size = {
        "Codex_Ent_Aleoida_Genus_Name": 150,
        "Codex_Ent_Amphora_Plant_Genus_Name": 100,
        "Codex_Ent_Anemone_Genus_Name": 100,
        "Codex_Ent_Bacterium_Genus_Name": 500,
        "Codex_Ent_Bark_Mound_Genus_Name": 100,
        "Codex_Ent_Brain_Tree_Genus_Name": 100,
        "Codex_Ent_Cactoida_Genus_Name": 300,
        "Codex_Ent_Clypeus_Genus_Name": 150,
        "Codex_Ent_Concha_Genus_Name": 150,
        "Codex_Ent_Crystalline_Shard_Genus_Name": 100,
        "Codex_Ent_Electricae_Genus_Name": 1000,
        "Codex_Ent_Fonticulua_Genus_Name": 500,
        "Codex_Ent_Frutexa_Genus_Name": 150,
        "Codex_Ent_Fumerola_Genus_Name": 100,
        "Codex_Ent_Fungoida_Genus_Name": 300,
        "Codex_Ent_Osseus_Genus_Name": 800,
        "Codex_Ent_Recepta_Genus_Name": 150,
        "Codex_Ent_Sinuous_Tuber_Genus_Name": 100,
        "Codex_Ent_Stratum_Genus_Name": 500,
        "Codex_Ent_Tubus_Genus_Name": 800,
        "Codex_Ent_Tussocks_Genus_Name": 200
    }
    status = status_parser.current_status

    if content["ScanType"] == "Log":
        content["event"] = "ScanOrganicFirst"
        scans.clear()
        scans.append({'lat': status['Latitude'], 'long': status['Longitude']})
        scan_radius = colony_size[content['Genus'][1:-1]]
        scan_in_progress = False
    elif content["ScanType"] == "Sample":
        if not scan_in_progress:
            content["event"] = "ScanOrganicSecond"
            scans.append({'lat': status['Latitude'], 'long': status['Longitude']})
            scan_in_progress = True
        else:
            content["event"] = "ScanOrganicThird"
            scan_in_progress = False
    elif content["ScanType"] == "Analyse":
        content["event"] = "ScanOrganicFinished"

    return content, scans, scan_in_progress, scan_radius


def haversine_distance(new_value, old_value, radius):
    # Convert latitude and longitude from degrees to radians
    lat1, lon1 = math.radians(new_value['lat']), math.radians(new_value['long'])
    lat2, lon2 = math.radians(old_value['lat']), math.radians(old_value['long'])

    # Calculate differences
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    # Haversine formula
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # Distance in meters
    distance = radius * c
    return distance

def main():
    global llmClient, sttClient, ttsClient, tts, aiModel, useTools, jn, event_manager, prompt_generator, llm_model_name, status_parser

    # Load configuration
    config = load_config()
    if config["api_key"] == '':
        config["api_key"] = '-'
    llm_model_name = config["llm_model_name"]

    jn = EDJournal(config["game_events"], get_ed_journals_path(config))
    copilot = EDCoPilot(config["edcopilot"], is_edcopilot_dominant=config["edcopilot_dominant"])

    # gets API Key from config.json
    llmClient = OpenAI(
        base_url="https://api.openai.com/v1" if config["llm_endpoint"] == '' else config["llm_endpoint"],
        api_key=config["api_key"] if config["llm_api_key"] == '' else config["llm_api_key"],
    )

    # tool usage
    if config["tools_var"]:
        useTools = True
    # alternative models
    if llm_model_name != '':
        aiModel = llm_model_name
    # character prompt
    backstory = config["character"]
    # vision
    if config["vision_var"]:
        visionClient = OpenAI(
            base_url="https://api.openai.com/v1" if config["vision_endpoint"] == '' else config["vision_endpoint"],
            api_key=config["api_key"] if config["vision_api_key"] == '' else config["vision_api_key"],
        )
    else:
        visionClient = None


    sttClient = OpenAI(
        base_url=config["stt_endpoint"],
        api_key=config["api_key"] if config["stt_api_key"] == '' else config["stt_api_key"],
    )

    if config["tts_provider"] in ['openai', 'custom']:
        ttsClient = OpenAI(
            base_url=config["tts_endpoint"],
            api_key=config["api_key"] if config["tts_api_key"] == '' else config["tts_api_key"],
        )

    log('info', f"Initializing CMDR {config['commander_name']}'s personal AI...\n")
    log('info', "API Key: Loaded")
    log('info', f"Using Push-to-Talk: {config['ptt_var']}")
    log('info', f"Using Function Calling: {useTools}")
    log('info', f"Current model: {llm_model_name}")
    log('info', f"Current TTS voice: {config['tts_voice']}")
    log('info', f"Current TTS Speed: {config['tts_speed']}")
    log('info', "Current backstory: " + backstory.replace("{commander_name}", config['commander_name']))

    # TTS Setup
    log('info', "Basic configuration complete.")
    log('info', "Loading voice output...")
    if config["edcopilot_dominant"]:
        log('info', "EDCoPilot is dominant, voice output will be handled by EDCoPilot.")
    tts_provider = 'none' if config["edcopilot_dominant"] else config["tts_provider"]
    tts = TTS(openai_client=ttsClient, provider=tts_provider, model=config["tts_model_name"], voice=config["tts_voice"], speed=config["tts_speed"])
    stt = STT(openai_client=sttClient, input_device_name=config["input_device_name"], model=config["stt_model_name"])

    if config['ptt_var'] and config['ptt_key']:
        log('info', f"Setting push-to-talk hotkey {config['ptt_key']}.")
        controller_manager.register_hotkey(config["ptt_key"], lambda _: stt.listen_once_start(),
                                           lambda _: stt.listen_once_end())
    else:
        stt.listen_continuous()
    log('info', "Voice interface ready.")


    enabled_game_events: list[str] = []
    if config["event_reaction_enabled_var"]:
        for category in config["game_events"].values():
            for event, state in category.items():
                if state:
                    enabled_game_events.append(event)

    ed_keys = EDKeys(get_ed_appdata_path(config))
    status_parser = StatusParser(get_ed_journals_path(config))
    prompt_generator = PromptGenerator(config["commander_name"], config["character"], important_game_events=enabled_game_events)
    event_manager = EventManager(
        on_reply_request=lambda events, new_events, states: reply(llmClient, events, new_events, states, prompt_generator, event_manager,
                                                          tts, copilot, config),
        game_events=enabled_game_events,
        continue_conversation=config["continue_conversation_var"],
        react_to_text_local=config["react_to_text_local_var"],
        react_to_text_starsystem=config["react_to_text_starsystem_var"],
        react_to_text_npc=config["react_to_text_npc_var"],
        react_to_text_squadron=config["react_to_text_squadron_var"],
        react_to_material=config["react_to_material"]
    )
    registerProjections(event_manager)

    if useTools:
        register_actions(action_manager, event_manager, llmClient, llm_model_name, visionClient, config["vision_model_name"], status_parser, ed_keys)
        log('info', "Actions ready.")
        
    log('info', 'Initializing states...')
    while jn.historic_events:
        event_manager.add_historic_game_event(jn.historic_events.pop(0))
        
    event_manager.add_status_event(status_parser.current_status)
    event_manager.process()

    # Cue the user that we're ready to go.
    log('info', "System Ready.")

    within_scan_radius = True
    scan_radius = 0
    scan_in_progress = False
    scans = []
    counter = 0
    while True:
        try:
            counter += 1
            status = None
            # check status file for updates
            while not status_parser.status_queue.empty():
                status = status_parser.status_queue.get()
                event_manager.add_status_event(status)

            # check STT recording
            if stt.recording:
                if tts.get_is_playing():
                    log('debug', 'interrupting TTS')
                    tts.abort()
                if not event_manager.is_listening:
                    event_manager.is_listening = True
            else:
                if event_manager.is_listening:
                    event_manager.is_listening = False

            # check STT result queue
            if not stt.resultQueue.empty():
                text = stt.resultQueue.get().text
                tts.abort()
                copilot.output_commander(text)
                event_manager.add_conversation_event('user', text)

            if not is_thinking and not tts.get_is_playing() and event_manager.is_replying:
                event_manager.add_assistant_complete_event()

            # check EDJournal files for updates
            while not jn.events.empty():
                event = jn.events.get()
                # log('info', 'main loop event', event)

                if event["event"] == "ScanOrganic":
                    event, scans, scan_in_progress, scan_radius = bio_scan(event, scans, scan_in_progress, scan_radius)
                if event["event"] in ['SupercruiseEntry','FSDJump','Died','Shutdown','JoinACrew']:
                    scans.clear()

                event_manager.add_game_event(event)

            if len(scans) > 0 and status:
                in_scan_radius = False
                if (status_parser.current_status.get('Latitude', False) and
                    status_parser.current_status.get('Longitude', False) and
                    status_parser.current_status.get('PlanetRadius', False)):
                    distance_obj = {'lat': status_parser.current_status['Latitude'], 'long': status_parser.current_status['Longitude']}
                    for scan in scans:
                        distance = haversine_distance(scan, distance_obj, status_parser.current_status['PlanetRadius'])
                        log('info', 'distance', distance)
                        if distance < scan_radius:
                            in_scan_radius = True
                    if in_scan_radius:
                        if not within_scan_radius:
                            event_manager.add_game_event({'event':'ScanOrganicTooClose','id':'0'})
                            within_scan_radius = in_scan_radius
                    else:
                        if within_scan_radius:
                            event_manager.add_game_event({'event': 'ScanOrganicFarEnough','id':'0'})
                            within_scan_radius = in_scan_radius
                else:
                    scans.clear()

            event_manager.process()

            # Infinite loops are bad for processors, must sleep.
            sleep(0.25)
        except KeyboardInterrupt:
            break
        except Exception as e:
            log("error", e, traceback.format_exc())
            break

    # Teardown TTS
    tts.quit()


if __name__ == "__main__":
    main()
