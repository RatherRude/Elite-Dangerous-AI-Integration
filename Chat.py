import base64
import io
import json
import sys
from io import BytesIO
from pathlib import Path

import keyboard
import pyautogui
import requests
import win32gui
from PIL import Image
from openai import OpenAI

import AIActions
import STT
import TTS
from ControllerManager import ControllerManager
from Event import Event
from Logger import log
from PromptGenerator import PromptGenerator

# from MousePt import MousePoint

# Add the parent directory to sys.path
parent_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(parent_dir))

from Voice import *
from EDKeys import *
from EDJournal import *

import EventManager

client = None
sttClient = None
ttsClient = None

aiActions = AIActions.AIActions()

# fallback settings
aiModel = "gpt-4o"
backstory = """I am Commander {commander_name}. I am a broke bounty hunter who can barely pay the fuel. \
You will be addressed as 'Computer', you are the onboard AI of my starship. \
You possess extensive knowledge and can provide detailed and accurate information on a wide range of topics, \
including galactic navigation, ship status, the current system, and more. \
Do not inform about my ship status and my location unless it's relevant or requested by me. Answer within 3 sentences. Acknowledge given orders. \
Guide and support me with witty and intelligent commentary. Provide clear mission briefings, sarcastic comments, and humorous observations. \
Advance the narrative involving bounty hunting."""

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


# Define functions for each action
def fire_primary_weapon(args):
    setGameWindowActive()
    keys.send('PrimaryFire', state=1)
    return f"successfully opened fire with primary weapons."


def hold_fire_primary_weapon(args):
    setGameWindowActive()
    keys.send('PrimaryFire', state=0)
    return f"successfully stopped firing with primary weapons."


def fire_secondary_weapon(args):
    setGameWindowActive()
    keys.send('SecondaryFire', state=1)
    return f"successfully opened fire with secondary weapons."


def hold_fire_secondary_weapon(args):
    setGameWindowActive()
    keys.send('SecondaryFire', state=0)
    return f"successfully stopped firing with secondary weapons."


def hyper_super_combination(args):
    setGameWindowActive()
    keys.send('HyperSuperCombination')
    return f"Frame Shift Drive is charging for a jump"


def set_speed_zero(args):
    setGameWindowActive()
    keys.send('SetSpeedZero')
    return f"Speed set to 0%"


def set_speed_50(args):
    setGameWindowActive()
    keys.send('SetSpeed50')
    return f"Speed set to 50%"


def set_speed_100(args):
    setGameWindowActive()
    keys.send('SetSpeed100')
    return f"Speed set to 100%"


def deploy_heat_sink(args):
    setGameWindowActive()
    keys.send('DeployHeatSink')
    return f"Heat sink deployed"


def deploy_hardpoint_toggle(args):
    setGameWindowActive()
    keys.send('DeployHardpointToggle')
    return f"Hardpoints deployed/retracted"


def increase_engines_power(args):
    setGameWindowActive()
    keys.send('IncreaseEnginesPower', None, args['pips'])
    return f"Engine power increased"


def increase_weapons_power(args):
    setGameWindowActive()
    keys.send('IncreaseWeaponsPower', None, args['pips'])
    return f"Weapon power increased"


def increase_systems_power(args):
    setGameWindowActive()
    keys.send('IncreaseSystemsPower', None, args['pips'])
    return f"Systems power increased"


def galaxy_map_open(args):
    setGameWindowActive()
    keys.send('GalaxyMapOpen')
    return f"Galaxy map opened/closed"


def system_map_open(args):
    setGameWindowActive()
    keys.send('SystemMapOpen')
    return f"System map opened/closed"


def cycle_next_target(args):
    setGameWindowActive()
    keys.send('CycleNextTarget')
    return f"Next target cycled"


def cycle_fire_group_next(args):
    setGameWindowActive()
    keys.send('CycleFireGroupNext')
    return f"Fire group cycled"


def ship_spot_light_toggle(args):
    setGameWindowActive()
    keys.send('ShipSpotLightToggle')
    return f"Ship spotlight toggled"


def eject_all_cargo(args):
    setGameWindowActive()
    keys.send('EjectAllCargo')
    return f"All cargo ejected"


def landing_gear_toggle(args):
    setGameWindowActive()
    keys.send('LandingGearToggle')
    return f"Landing gear toggled"


def use_shield_cell(args):
    setGameWindowActive()
    keys.send('UseShieldCell')
    return f"Shield cell used"


def fire_chaff_launcher(args):
    setGameWindowActive()
    keys.send('FireChaffLauncher')
    return f"Chaff launcher fired"


def night_vision_toggle(args):
    setGameWindowActive()
    keys.send('NightVisionToggle')
    return f"Night vision toggled"


def recall_dismiss_ship(args):
    setGameWindowActive()
    keys.send('RecallDismissShip')
    return f"Ship has either been recalled or dismissed"


# Register actions
aiActions.registerAction('fire', "start firing primary weapons", {
    "type": "object",
    "properties": {}
}, fire_primary_weapon)

aiActions.registerAction('holdFire', "stop firing primary weapons", {
    "type": "object",
    "properties": {}
}, hold_fire_primary_weapon)

aiActions.registerAction('fireSecondary', "start secondary primary weapons", {
    "type": "object",
    "properties": {}
}, fire_secondary_weapon)

aiActions.registerAction('holdFireSecondary', "stop secondary primary weapons", {
    "type": "object",
    "properties": {}
}, hold_fire_secondary_weapon)

aiActions.registerAction('hyperSuperCombination',
                         "initiate FSD Jump, required to jump to the next system or to enter supercruise", {
                             "type": "object",
                             "properties": {}
                         }, hyper_super_combination)

aiActions.registerAction('setSpeedZero', "Set speed to 0%", {
    "type": "object",
    "properties": {}
}, set_speed_zero)

aiActions.registerAction('setSpeed50', "Set speed to 50%", {
    "type": "object",
    "properties": {}
}, set_speed_50)

aiActions.registerAction('setSpeed100', "Set speed to 100%", {
    "type": "object",
    "properties": {}
}, set_speed_100)

aiActions.registerAction('deployHeatSink', "Deploy heat sink", {
    "type": "object",
    "properties": {}
}, deploy_heat_sink)

aiActions.registerAction('deployHardpointToggle', "Deploy or retract hardpoints", {
    "type": "object",
    "properties": {}
}, deploy_hardpoint_toggle)

aiActions.registerAction('increaseEnginesPower', "Increase engine power, can be done multiple times", {
    "type": "object",
    "properties": {
        "pips": {
            "type": "integer",
            "description": "Amount of pips to increase engine power, default: 1, maximum: 4",
        },
    },
    "required": ["pips"]
}, increase_engines_power)

aiActions.registerAction('increaseWeaponsPower', "Increase weapon power, can be done multiple times", {
    "type": "object",
    "properties": {
        "pips": {
            "type": "integer",
            "description": "Amount of pips to increase weapon power, default: 1, maximum: 4",
        },
    },
    "required": ["pips"]
}, increase_weapons_power)

aiActions.registerAction('increaseSystemsPower', "Increase systems power, can be done multiple times", {
    "type": "object",
    "properties": {
        "pips": {
            "type": "integer",
            "description": "Amount of pips to increase systems power, default: 1, maximum: 4",
        },
    },
    "required": ["pips"]
}, increase_systems_power)

aiActions.registerAction('galaxyMapOpen', "Open or close galaxy map", {
    "type": "object",
    "properties": {}
}, galaxy_map_open)

aiActions.registerAction('systemMapOpen', "Open or close system map", {
    "type": "object",
    "properties": {}
}, system_map_open)

aiActions.registerAction('cycleNextTarget', "Cycle to next target", {
    "type": "object",
    "properties": {}
}, cycle_next_target)

aiActions.registerAction('cycleFireGroupNext', "Cycle to next fire group", {
    "type": "object",
    "properties": {}
}, cycle_fire_group_next)

aiActions.registerAction('shipSpotLightToggle', "Toggle ship spotlight", {
    "type": "object",
    "properties": {}
}, ship_spot_light_toggle)

aiActions.registerAction('ejectAllCargo', "Eject all cargo", {
    "type": "object",
    "properties": {}
}, eject_all_cargo)

aiActions.registerAction('landingGearToggle', "Toggle landing gear", {
    "type": "object",
    "properties": {}
}, landing_gear_toggle)

aiActions.registerAction('useShieldCell', "Use shield cell", {
    "type": "object",
    "properties": {}
}, use_shield_cell)

aiActions.registerAction('fireChaffLauncher', "Fire chaff launcher", {
    "type": "object",
    "properties": {}
}, fire_chaff_launcher)

aiActions.registerAction('nightVisionToggle', "Toggle night vision", {
    "type": "object",
    "properties": {}
}, night_vision_toggle)

aiActions.registerAction('recallDismissShip', "Recall or dismiss ship, available on foot and inside SRV", {
    "type": "object",
    "properties": {}
}, recall_dismiss_ship)


def prompt_for_config():
    # This function should implement the logic to prompt the user for configuration
    # Since the prompt logic is not provided, this is a placeholder function
    commander_name = input("Enter Commander Name: ")
    character = input("Enter AI Character: ")
    api_key = input("Enter API Key: ")
    ai_model = input("Enter AI Model Name: ")
    llm_api_key = input("Enter LLM API Key: ")
    llm_endpoint = input("Enter LLM Endpoint: ")
    vision_model_name = input("Enter Vision Model Name: ")
    vision_endpoint = input("Enter Vision Model Endpoint: ")
    vision_api_key = input("Enter Vision Model API Key: ")
    stt_model_name = input("Enter STT Model Name: ")
    stt_api_key = input("Enter STT API Key: ")
    stt_endpoint = input("Enter STT Endpoint: ")
    tts_model_name = input("Enter TTS Model Name: ")
    tts_api_key = input("Enter TTS API Key: ")
    tts_endpoint = input("Enter TTS Endpoint: ")
    alternative_stt_var = input("Local STT? ")
    alternative_tts_var = input("Local TTS? ")
    tools_var = input("AI Tools? ")
    vision_var = input("Vision Capabilities? ")
    ptt_var = input("Use Push-to-talk? ")
    continue_conversation_var = input("Continue Conversation? ")
    tts_voice = input("Enter TTS Voice: ")
    tts_speed = input("Enter TTS Speed: ")
    key_binding = input("Push-to-talk button: ")
    game_events = input("Please enter game events in the format of Dict[str, Dict[str, bool]] ☺")

    return api_key, llm_api_key, llm_endpoint, vision_model_name, vision_endpoint, vision_api_key, stt_model_name, stt_api_key, stt_endpoint, tts_model_name, tts_api_key, tts_endpoint, commander_name, character, ai_model, alternative_stt_var, alternative_tts_var, tools_var, vision_var, ptt_var, continue_conversation_var, tts_voice, tts_speed, key_binding, game_events


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
            model_name = config.get('llm_model_name', '')
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
            key_binding = config.get('key_binding', '')
            game_events = config.get('game_events', '[]')
    else:
        api_key, llm_api_key, llm_endpoint, vision_model_name, vision_endpoint, vision_api_key, stt_model_name, stt_api_key, stt_endpoint, tts_model_name, tts_api_key, tts_endpoint, commander_name, character, ai_model, alternative_stt_var, alternative_tts_var, tools_var, vision_var, ptt_var, continue_conversation_var, tts_voice, tts_speed, key_binding, game_events = prompt_for_config()
        with open(config_file, 'w') as f:
            json.dump({
                'api_key': api_key,
                'llm_api_key': llm_api_key,
                'llm_endpoint': llm_endpoint,
                'commander_name': commander_name,
                'character': character,
                'model_name': ai_model,
                'vision_model_name': vision_model_name,
                'vision_endpoint': vision_endpoint,
                'vision_api_key': vision_api_key,
                'stt_model_name': stt_model_name,
                'stt_api_key': stt_api_key,
                'stt_endpoint': stt_endpoint,
                'tts_model_name': tts_model_name,
                'tts_api_key': tts_api_key,
                'tts_endpoint': tts_endpoint,
                'alternative_stt_var': alternative_stt_var,
                'alternative_tts_var': alternative_tts_var,
                'tools_var': tools_var,
                'vision_var': vision_var,
                'ptt_var': ptt_var,
                'continue_conversation_var': continue_conversation_var,
                'tts_voice': tts_voice,
                'tts_speed': tts_speed,
                'key_binding': key_binding,
                'game_events': game_events,
            }, f)

    return api_key, llm_api_key, llm_endpoint, vision_model_name, vision_endpoint, vision_api_key, stt_model_name, stt_api_key, stt_endpoint, tts_model_name, tts_api_key, tts_endpoint, commander_name, character, model_name, alternative_stt_var, alternative_tts_var, tools_var, vision_var, ptt_var, continue_conversation_var, tts_voice, tts_speed, key_binding, game_events

handle = win32gui.FindWindow(0, "Elite - Dangerous (CLIENT)")

def setGameWindowActive():
    global handle

    if handle:
        try:
            win32gui.SetForegroundWindow(handle)  # give focus to ED
        except:
            log("error", "Failed to set game window as active")


def screenshot():
    global handle
    if handle:
        setGameWindowActive()
        x, y, x1, y1 = win32gui.GetClientRect(handle)
        x, y = win32gui.ClientToScreen(handle, (x, y))
        x1, y1 = win32gui.ClientToScreen(handle, (x1, y1))
        width = x1 - x
        height = y1 - y
        im = pyautogui.screenshot(region=(x, y, width, height))

        # Convert the screenshot to a PIL image
        im = im.convert("RGB")

        # Resize to height 720 while maintaining aspect ratio
        aspect_ratio = width / height
        new_height = 720
        new_width = int(new_height * aspect_ratio)
        im = im.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Crop the center to a 16:9 aspect ratio
        target_aspect_ratio = 16 / 9
        target_width = int(new_height * target_aspect_ratio)
        left = (new_width - target_width) / 2
        top = 0
        right = left + target_width
        bottom = new_height
        im = im.crop((left, top, right, bottom))

        return im
    else:
        log("error",'Window not found!')
        return None


def format_image(image, query=""):
    buffered = BytesIO()
    image.save(buffered, format="JPEG")
    image_data = buffered.getvalue()
    base64_image = base64.b64encode(image_data).decode('utf-8')

    return [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "This is a screenshot of the game Elite:Dangerous Odyssey. " +
                            "Briefly describe everything visible(e.g. celestial bodies, ships, humans and other surroundings). " +
                            "Try to summarize all visible text while only keeping the relevant details. Do not describe any other game HUD or the ship cockpit." +
                            "Try to answer the following query: " + query
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                }
            ]
        }
    ]


# fetch system info from EDSM
def get_system_info(system_name):
    url = "https://www.edsm.net/api-v1/system"
    params = {
        "systemName": system_name,
        "showInformation": 1,
        "showPrimaryStar": 1,
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx and 5xx)

        return response.text

    except:
        return "Currently no information on system available"


# fetch station info from EDSM and summarizes it
def get_station_info(obj):
    url = "https://www.edsm.net/api-system-v1/stations"
    params = {
        "systemName": obj.get('systemName'),
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx and 5xx)

        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://github.com/RatherRude/Elite-Dangerous-AI-Integration",
                "X-Title": "Elite Dangerous AI Integration",
            },
            model=aiModel,
            messages=[{
                "role": "user",
                "content": f"Analyze the following data: {response.text}\nInquiry: {obj.get('query')}"
            }],
        )

        return completion.choices[0].message.content

    except:
        return "Currently no information on system available"


# returns summary of galnet news
def get_galnet_news(obj):
    url = "https://cms.zaonce.net/en-GB/jsonapi/node/galnet_article?&sort=-published_at&page[offset]=0&page[limit]=10"

    try:
        response = requests.get(url)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx and 5xx)
        results = json.loads(response.content.decode())["data"]
        articles = []

        if results:
            for result in results:
                article = {
                    "date": result["attributes"]["field_galnet_date"],
                    "title": result["attributes"]["title"],
                    "content": result["attributes"]["body"]["value"],
                }
                articles.append(article)

            completion = client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": "https://github.com/RatherRude/Elite-Dangerous-AI-Integration",
                    "X-Title": "Elite Dangerous AI Integration",
                },
                model=aiModel,
                messages=[{
                    "role": "user",
                    "content": f"Analyze the following list of news articles, either answer the given inquiry or create a short summary that includes all named entities: {articles}\nInquiry: {obj.get('query')}"
                }],
            )

            return completion.choices[0].message.content

        return "News feed currently unavailable"

    except:
        return "News feed currently unavailable"


# fetch faction info from EDSM and summarizes it
def get_faction_info(obj):
    url = "https://www.edsm.net/api-system-v1/factions"
    params = {
        "systemName": obj.get('systemName'),
        "showHistory": 0,
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx and 5xx)

        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://github.com/RatherRude/Elite-Dangerous-AI-Integration",
                "X-Title": "Elite Dangerous AI Integration",
            },
            model=aiModel,
            messages=[{
                "role": "user",
                "content": f"Analyze the following data: {response.text}\nInquiry: {obj.get('query')}"
            }],
        )

        return completion.choices[0].message.content

    except:
        return "Currently no information on factions inside this system available"


aiActions.registerAction('getFactions', "Retrieve information about factions for a system", {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Answer inquiry if given, otherise give general overview. Example: 'What factions are at war?'"
        },
        "systemName": {
            "type": "string",
            "description": "Name of relevant system. Example: 'Sol'"
        },
    },
    "required": ["query", "systemName"]
}, get_faction_info)

aiActions.registerAction('getStations', "Retrieve information about stations in this system", {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Answer inquiry if given, otherise give general overview. Example: 'What stations require immediate repair?'"
        },
        "systemName": {
            "type": "string",
            "description": "Name of relevant system. Example: 'Sol'"
        },
    },
    "required": ["query", "systemName"]
}, get_station_info)

aiActions.registerAction('getGalnetNews', "Retrieve current interstellar news from Galnet", {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Inquiry you are trying to answer. Example: 'What happened to the thargoids recently?'"
        },
    },
    "required": ["query"]
}, get_galnet_news)

is_thinking = False

def reply(client, events: List[Event], new_events: List[Event], prompt_generator: PromptGenerator, event_manager: EventManager, tts: TTS.TTS):
    global is_thinking
    is_thinking = True
    prompt = prompt_generator.generate_prompt(events)

    use_tools = useTools and any([event.kind == 'user' for event in new_events])

    completion = client.chat.completions.create(
        model=aiModel,
        messages=prompt,
        tools=aiActions.getToolsList() if use_tools else None
    )

    if hasattr(completion, 'error'):
        log("error", "completion with error:", completion)
        is_thinking = False
        return

    response_text = completion.choices[0].message.content
    if response_text:
        tts.say(response_text)
        event_manager.add_conversation_event('assistant', completion.choices[0].message.content)
    is_thinking = False

    response_actions = completion.choices[0].message.tool_calls
    if response_actions:
        action_results = []
        for action in response_actions:
            action_result = aiActions.runAction(action)
            action_results.append(action_result)

        event_manager.add_tool_call([tool_call.dict() for tool_call in response_actions], action_results)


useTools = False

def getCurrentState():
    keysToFilterOut = ["time"]
    rawState = jn.ship_state()

    return {key: value for key, value in rawState.items() if key not in keysToFilterOut}


previous_status = None

def checkForJournalUpdates(client, eventManager, commanderName, boot):
    #printFlush('checkForJournalUpdates is checking')
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
keys = EDKeys()
tts = None
prompt_generator: PromptGenerator = None
event_manager: EventManager = None

controller_manager = ControllerManager()

def main():
    global client, sttClient, ttsClient, v, tts, keys, aiModel, backstory, useTools, jn, previous_status, conversation, event_manager, prompt_generator
    setGameWindowActive()

    # Load or prompt for configuration
    apiKey, llm_api_key, llm_endpoint, vision_model_name, vision_endpoint, vision_api_key, stt_model_name, stt_api_key, stt_endpoint, tts_model_name, tts_api_key, tts_endpoint, commanderName, character, model_name, alternative_stt_var, alternative_tts_var, tools_var, vision_var, ptt_var, continue_conversation_var, tts_voice, tts_speed, key_binding, game_events = load_or_prompt_config()

    jn = EDJournal(game_events)
    previous_status = getCurrentState()

    # log('Debug', 'loading keys')

    # gets API Key from config.json
    client = OpenAI(
        base_url="https://api.openai.com/v1" if llm_endpoint == '' else llm_endpoint,
        api_key=apiKey if llm_api_key == '' else llm_api_key,
    )

    # tool usage
    if tools_var:
        useTools = True
    # alternative models
    if model_name != '':
        aiModel = model_name
    # alternative character
    if character != '':
        backstory = character
    # vision
    if vision_var:
        visionClient = OpenAI(
            base_url="https://api.openai.com/v1" if vision_endpoint == '' else vision_endpoint,
            api_key=apiKey if vision_api_key == '' else vision_api_key,
        )

        def get_visuals(obj):
            image = screenshot()
            if not image: return "Unable to take screenshot."

            completion = visionClient.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": "https://github.com/RatherRude/Elite-Dangerous-AI-Integration",
                    "X-Title": "Elite Dangerous AI Integration",
                },
                model=aiModel if vision_model_name == '' else vision_model_name,
                messages=format_image(image, obj.get("query")),
            )

            return completion.choices[0].message.content

        aiActions.registerAction('getVisuals', "Describes what's currently visible to the Commander.", {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Describe what you are curious about in the description. Example: 'Count the number of pirates'"
                }
            },
            "required": ["query"]
        }, get_visuals)

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
    log('Debug', f"Current model: {aiModel}")
    log('Debug', f"Current TTS voice: {tts_voice}")
    log('Debug', f"Current TTS Speed: {tts_speed}")
    log('Debug', "Current backstory: " + backstory.replace("{commander_name}", commanderName))
    log('Debug', "Basic configuration complete.\nLoading voice interface...")

    # TTS Setup
    if alternative_tts_var:
        # log('Debug', 'Local TTS')
        tts = Voice(rate_multiplier=float(tts_speed))
        tts.set_on()
    else:
        # log('Debug', 'remote TTS')
        tts = TTS.TTS(openai_client=ttsClient, model=tts_model_name, voice=tts_voice, speed=tts_speed)

    if alternative_stt_var:
        # log('Debug', 'local STT')
        stt = STT.STT(openai_client=None, model="distil-medium.en")
    else:
        # log('Debug', 'remote STT')
        stt = STT.STT(openai_client=sttClient, model=stt_model_name)

    if ptt_var and key_binding:
        push_to_talk_key = key_binding  # Change this to your desired key
        controller_manager.register_hotkey(push_to_talk_key, lambda _: stt.listen_once_start(), lambda _: stt.listen_once_end())
    else:
        stt.listen_continuous()

    enabled_game_events = []
    for category in game_events.values():
        for event, state in category.items():
            if state:
                enabled_game_events.append(event)

    # Cue the user that we're ready to go.
    log('Debug', "Voice interface ready.\n")

    prompt_generator = PromptGenerator(commanderName, character, journal=jn)
    event_manager = EventManager.EventManager(
        on_reply_request=lambda events, new_events: reply(client, events, new_events, prompt_generator, event_manager, tts),
        game_events=enabled_game_events,
        continue_conversation=continue_conversation_var
    )

    counter = 0

    while True:
        try:
            # check STT result queue
            if not stt.resultQueue.empty():
                text = stt.resultQueue.get().text
                tts.abort()
                event_manager.add_conversation_event('user', text)
            else:
                counter += 1

                if not is_thinking and not tts.get_is_playing() and event_manager.is_replying:
                    event_manager.add_assistant_complete_event()

                if counter % 5 == 0:
                    checkForJournalUpdates(client, event_manager, commanderName, counter <= 5)

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
