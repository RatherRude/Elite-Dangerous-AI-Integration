import io
import json
import sys
from pathlib import Path

from openai import OpenAI

from lib.ActionManager import ActionManager
from lib.STT import STT
from lib.TTS import TTS
from lib.ControllerManager import ControllerManager
from lib.Event import Event
from lib.PromptGenerator import PromptGenerator
from lib.Actions import register_actions

# from MousePt import MousePoint

# Add the parent directory to sys.path
parent_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(parent_dir))

from lib.Voice import *
from lib.EDKeys import *
from lib.EDJournal import *

from lib.EventManager import EventManager

llmClient = None
sttClient = None
ttsClient = None
llm_model_name = None

action_manager = ActionManager()

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def load_or_prompt_config():
    config_file = Path("config.json")
    if config_file.exists():
        with open(config_file, 'r') as f:
            config = json.load(f)
            api_key = config.get('api_key', '')
            llm_api_key = config.get('llm_api_key', '')
            llm_endpoint = config.get('llm_endpoint', '')
            commander_name = config.get('commander_name', '')
            character = config.get('character', '')
            llm_model_name = config.get('llm_model_name', '')
            vision_model_name = config.get('vision_model_name', '')
            vision_endpoint = config.get('vision_endpoint', '')
            vision_api_key = config.get('vision_api_key', '')
            stt_model_name = config.get('stt_model_name', '')
            stt_api_key = config.get('stt_api_key', '')
            stt_endpoint = config.get('stt_endpoint', '')
            tts_model_name = config.get('tts_model_name', '')
            tts_api_key = config.get('tts_api_key', '')
            tts_endpoint = config.get('tts_endpoint', '')
            alternative_stt_var = config.get('alternative_stt_var', '')
            alternative_tts_var = config.get('alternative_tts_var', '')
            tools_var = config.get('tools_var', '')
            vision_var = config.get('vision_var', '')
            ptt_var = config.get('ptt_var', '')
            continue_conversation_var = config.get('continue_conversation_var', '')
            tts_voice = config.get('tts_voice', '')
            tts_speed = config.get('tts_speed', '')
            ptt_key = config.get('ptt_key', '')
            game_events = config.get('game_events', '[]')
    return api_key, llm_api_key, llm_endpoint, vision_model_name, vision_endpoint, vision_api_key, stt_model_name, stt_api_key, stt_endpoint, tts_model_name, tts_api_key, tts_endpoint, commander_name, character, llm_model_name, alternative_stt_var, alternative_tts_var, tools_var, vision_var, ptt_var, continue_conversation_var, tts_voice, tts_speed, ptt_key, game_events

is_thinking = False

def reply(client, events: List[Event], new_events: List[Event], prompt_generator: PromptGenerator,
          event_manager: EventManager, tts: TTS):
    global is_thinking
    is_thinking = True
    prompt = prompt_generator.generate_prompt(events)

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


def checkForJournalUpdates(client, eventManager, commanderName, boot):
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
event_manager: EventManager = None

controller_manager = ControllerManager()


def main():
    global llmClient, sttClient, ttsClient, tts, aiModel, backstory, useTools, jn, previous_status, event_manager, prompt_generator, llm_model_name

    # Load or prompt for configuration
    apiKey, llm_api_key, llm_endpoint, vision_model_name, vision_endpoint, vision_api_key, stt_model_name, stt_api_key, stt_endpoint, tts_model_name, tts_api_key, tts_endpoint, commanderName, character, llm_model_name, alternative_stt_var, alternative_tts_var, tools_var, vision_var, ptt_var, continue_conversation_var, tts_voice, tts_speed, ptt_key, game_events = load_or_prompt_config()

    jn = EDJournal(game_events)
    previous_status = getCurrentState()

    # gets API Key from config.json
    llmClient = OpenAI(
        base_url="https://api.openai.com/v1" if llm_endpoint == '' else llm_endpoint,
        api_key=apiKey if llm_api_key == '' else llm_api_key,
    )

    # tool usage
    if tools_var:
        useTools = True
    # alternative models
    if llm_model_name != '':
        aiModel = llm_model_name
    # alternative character
    if character != '':
        backstory = character
    # vision
    if vision_var:
        visionClient = OpenAI(
            base_url="https://api.openai.com/v1" if vision_endpoint == '' else vision_endpoint,
            api_key=apiKey if vision_api_key == '' else vision_api_key,
        )


    sttClient = OpenAI(
        base_url="https://api.openai.com/v1" if stt_endpoint == '' else stt_endpoint,
        api_key=apiKey if stt_api_key == '' else stt_api_key,
    )
    ttsClient = OpenAI(
        base_url="https://api.openai.com/v1" if tts_endpoint == '' else tts_endpoint,
        api_key=apiKey if tts_api_key == '' else tts_api_key,
    )

    log('Debug', f"Initializing CMDR {commanderName}'s personal AI...\n")
    log('Debug', "API Key: Loaded")
    log('Debug', f"Using Push-to-Talk: {ptt_var}")
    log('Debug', f"Using Function Calling: {useTools}")
    log('Debug', f"Current model: {llm_model_name}")
    log('Debug', f"Current TTS voice: {tts_voice}")
    log('Debug', f"Current TTS Speed: {tts_speed}")
    log('Debug', "Current backstory: " + backstory.replace("{commander_name}", commanderName))

    # TTS Setup
    log('Debug', "Basic configuration complete.")
    log('Debug', "Loading voice output...")
    if alternative_tts_var:
        # log('Debug', 'Local TTS')
        tts = Voice(rate_multiplier=float(tts_speed), voice=tts_voice)
        tts.set_on()
    else:
        # log('Debug', 'remote TTS')
        tts = TTS(openai_client=ttsClient, model=tts_model_name, voice=tts_voice, speed=tts_speed)

    log('Debug', "Loading voice input...")
    if alternative_stt_var:
        # log('Debug', 'local STT')
        stt = STT(openai_client=None, model="distil-medium.en")
    else:
        # log('Debug', 'remote STT')
        stt = STT(openai_client=sttClient, model=stt_model_name)

    if ptt_var and ptt_key:
        log('Debug', f"Setting push-to-talk hotkey {ptt_key}...")
        controller_manager.register_hotkey(ptt_key, lambda _: stt.listen_once_start(),
                                           lambda _: stt.listen_once_end())
    else:
        stt.listen_continuous()
    log('Debug', "Voice interface ready.")


    enabled_game_events = []
    for category in game_events.values():
        for event, state in category.items():
            if state:
                enabled_game_events.append(event)

    prompt_generator = PromptGenerator(commanderName, character, journal=jn)
    event_manager = EventManager(
        on_reply_request=lambda events, new_events: reply(llmClient, events, new_events, prompt_generator, event_manager,
                                                          tts),
        game_events=enabled_game_events,
        continue_conversation=continue_conversation_var
    )

    log('Debug', "Loading actions...")
    register_actions(action_manager, event_manager, llmClient, llm_model_name, visionClient, vision_model_name)
    log('Debug', "Actions ready.")

    # Cue the user that we're ready to go.
    log('Debug', "\nSystem Ready.")

    counter = 0
    while True:
        try:
            counter += 1

            # check STT result queue
            if not stt.resultQueue.empty():
                text = stt.resultQueue.get().text
                tts.abort()
                event_manager.add_conversation_event('user', text)

            if not is_thinking and not tts.get_is_playing() and event_manager.is_replying:
                event_manager.add_assistant_complete_event()

            if counter % 5 == 0:
                checkForJournalUpdates(llmClient, event_manager, commanderName, counter <= 5)

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
