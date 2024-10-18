import io
import json
import sys
from pathlib import Path

from openai import OpenAI

from lib.Config import Config
from lib.ActionManager import ActionManager
from lib.Actions import register_actions
from lib.ControllerManager import ControllerManager
from lib.Event import Event
from lib.PromptGenerator import PromptGenerator
from lib.STT import STT
from lib.TTS import TTS
from lib.StatusParser import StatusParser

# from MousePt import MousePoint

# Add the parent directory to sys.path
parent_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(parent_dir))

from lib.Voice import *
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

def reply(client, events: List[Event], new_events: List[Event], prompt_generator: PromptGenerator, status_parser: StatusParser,
          event_manager: EventManager, tts: TTS):
    global is_thinking
    is_thinking = True
    prompt = prompt_generator.generate_prompt(events=events, status=status_parser.current_status)

    use_tools = useTools and any([event.kind == 'user' for event in new_events])

    completion = client.chat.completions.create(
        model=llm_model_name,
        messages=prompt,
        tools=action_manager.getToolsList() if use_tools else None
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
    is_thinking = False

    response_actions = completion.choices[0].message.tool_calls
    if response_actions:
        action_results = []
        for action in response_actions:
            action_result = action_manager.runAction(action)
            action_results.append(action_result)

        event_manager.add_tool_call([tool_call.dict() for tool_call in response_actions], action_results)


useTools = False


def getCurrentState():
    keysToFilterOut = ["time"]
    rawState = jn.ship_state()

    return {key: value for key, value in rawState.items() if key not in keysToFilterOut}


previous_status = None


def checkForJournalUpdates(client, eventManager, commander_name, boot):
    global previous_status
    if boot:
        previous_status['extra_events'].clear()
        return

    current_status = getCurrentState()

    if current_status['extra_events'] and len(current_status['extra_events']) > 0:
        while current_status['extra_events']:
            item = current_status['extra_events'][0]  # Get the first item
            if 'event_content' in item:
                if item['event_content'].get('ScanType') == "AutoScan":
                    current_status['extra_events'].pop(0)
                    continue

                elif 'Message_Localised' in item['event_content'] and item['event_content']['Message'].startswith(
                        "$COMMS_entered"):
                    current_status['extra_events'].pop(0)
                    continue

            eventManager.add_game_event(item['event_content'])
            current_status['extra_events'].pop(0)

    # Update previous status
    previous_status = current_status


jn = None
tts = None
prompt_generator: PromptGenerator = None
status_parser: StatusParser = None
event_manager: EventManager = None

controller_manager = ControllerManager()


def main():
    global llmClient, sttClient, ttsClient, tts, aiModel, backstory, useTools, jn, previous_status, event_manager, prompt_generator, llm_model_name

    # Load or prompt for configuration
    config = load_config()
    llm_model_name = config["llm_model_name"]

    jn = EDJournal(config["game_events"])
    previous_status = getCurrentState()

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
    # alternative character
    if config["character"] != '':
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

    if config["tts_model_name"] != 'edge-tts':
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
    tts = TTS(openai_client=ttsClient, model=config["tts_model_name"], voice=config["tts_voice"], speed=config["tts_speed"])
    stt = STT(openai_client=sttClient, input_device_name=config["input_device_name"], model=config["stt_model_name"])

    if config['ptt_var'] and config['ptt_key']:
        log('info', f"Setting push-to-talk hotkey {config['ptt_key']}.")
        controller_manager.register_hotkey(config["ptt_key"], lambda _: stt.listen_once_start(),
                                           lambda _: stt.listen_once_end())
    else:
        stt.listen_continuous()
    log('info', "Voice interface ready.")


    enabled_game_events = []
    for category in config["game_events"].values():
        for event, state in category.items():
            if state:
                enabled_game_events.append(event)

    status_parser = StatusParser()
    prompt_generator = PromptGenerator(config["commander_name"], config["character"], journal=jn)
    event_manager = EventManager(
        on_reply_request=lambda events, new_events: reply(llmClient, events, new_events, prompt_generator, status_parser, event_manager,
                                                          tts),
        game_events=enabled_game_events,
        continue_conversation=config["continue_conversation_var"]
    )

    if useTools:
        register_actions(action_manager, event_manager, llmClient, llm_model_name, visionClient, config["vision_model_name"], status_parser)
        log('info', "Actions ready.")

    # Cue the user that we're ready to go.
    log('info', "System Ready.")

    counter = 0
    while True:
        try:
            counter += 1

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
                event_manager.add_conversation_event('user', text)

            if not is_thinking and not tts.get_is_playing() and event_manager.is_replying:
                event_manager.add_assistant_complete_event()

            # check EDJournal files for updates
            if counter % 5 == 0:
                checkForJournalUpdates(llmClient, event_manager, config["commander_name"], counter <= 5)

            event_manager.reply()

            # Infinite loops are bad for processors, must sleep.
            sleep(0.25)
        except KeyboardInterrupt:
            break
        except Exception as e:
            log("error", str(e), e)
            break

    # save_conversation(conversation)
    event_manager.save_history()

    # Teardown TTS
    tts.quit()


if __name__ == "__main__":
    main()
