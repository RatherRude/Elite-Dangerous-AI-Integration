import json
from sys import platform
import threading
from time import sleep
from typing import Optional

import openai
import requests
from .Logger import log
from .EDKeys import EDKeys
from .EventManager import EventManager
from .ActionManager import ActionManager

keys = EDKeys()
vision_client: openai.OpenAI = None
llm_client: openai.OpenAI = None
llm_model_name: str = None
vision_model_name: str = None
event_manager: EventManager = None

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


handle = None
def get_game_window_handle():
    global handle
    if platform != "win32":
        return None
    import win32gui

    if not handle:
        handle = win32gui.FindWindow(0, "Elite - Dangerous (CLIENT)")
    return handle


def setGameWindowActive():
    if platform != "win32":
        return None
    handle = get_game_window_handle()
    import win32gui

    if handle:
        try:
            win32gui.SetForegroundWindow(handle)  # give focus to ED
            log("debug", "Set game window as active")
        except:
            log("error", "Failed to set game window as active")
    else:
        log("debug", "Unable to find Elite game window")


def screenshot():
    if platform != "win32":
        return None
    handle = get_game_window_handle()
    import win32gui
    import pyautogui
    from PIL import Image
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
        log("error", 'Window not found!')
        return None


def format_image(image, query=""):
    from io import BytesIO
    import base64
    
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


# fetch station info from EDSM and summarizes it
def get_station_info(obj):
    url = "https://www.edsm.net/api-system-v1/stations"
    params = {
        "systemName": obj.get('systemName'),
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx and 5xx)

        completion = llm_client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://github.com/RatherRude/Elite-Dangerous-AI-Integration",
                "X-Title": "Elite Dangerous AI Integration",
            },
            model=llm_model_name,
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

            completion = llm_client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": "https://github.com/RatherRude/Elite-Dangerous-AI-Integration",
                    "X-Title": "Elite Dangerous AI Integration",
                },
                model=llm_model_name,
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

        completion = llm_client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://github.com/RatherRude/Elite-Dangerous-AI-Integration",
                "X-Title": "Elite Dangerous AI Integration",
            },
            model=llm_model_name,
            messages=[{
                "role": "user",
                "content": f"Analyze the following data: {response.text}\nInquiry: {obj.get('query')}"
            }],
        )

        return completion.choices[0].message.content

    except:
        return "Currently no information on factions inside this system available"
    
# Region: Trade Planner Start
def check_trade_planner_job(job_id):
    url = "https://spansh.co.uk/api/results/" + job_id
    retries = 60

    for i in range(retries):
        try:
            response = requests.get(url)
            response.raise_for_status()  # Raises an HTTPError for bad responses (4xx and 5xx)

            data = response.json()

            if data['status'] == 'queued':
                # wait 5 seconds and then continue fetching
                sleep(5)
            if data['status'] == 'ok':
                # Filtering the list
                filtered_data = [
                    {
                        **item,
                        "destination": {k: item["destination"][k] for k in
                                        ["system", "station", "distance_to_arrival"]},
                        "source": {k: item["source"][k] for k in ["system", "station", "distance_to_arrival"]}
                    }
                    for item in data['result']
                ]
                # add conversational piece - here is your trade route!
                event_manager.add_external_event({'event': 'SpanshTradePlanner', 'result': filtered_data})

                # persist route as optional piece
                return
        except Exception as e:
            log('error', f"Error: {e}")
            # add conversational piece - error request
            event_manager.add_external_event({'event': 'SpanshTradePlannerFailed',
                                                'reason': 'The Spansh API has encountered an error! Please try at a later point in time!',
                                                'error': f'{e}'})
            return

    event_manager.add_external_event({'event': 'SpanshTradePlannerFailed',
                                        'reason': 'The Spansh API took longer than 5 minutes to find a trade route. That should not happen, try again at a later point in time!'})

def trade_planner_create_thread(obj):
    dict = {'max_system_distance': 10000000,
            'allow_prohibited': False,
            'allow_planetary': False,
            'allow_player_owned': False,
            'unique': False,
            'permit': False}

    dict.update(obj)

    log('Debug, Request data', dict)
    # send request with obj, will return a queue id
    url = "https://spansh.co.uk/api/trade/route"

    try:
        response = requests.post(url, data=dict)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx and 5xx)

        data = response.json()

        job_id = data['job']

        # start checking job status
        check_trade_planner_job(job_id)


    except Exception as e:
        log('error', f"Error: {e}")
        event_manager.add_external_event({'event': 'SpanshTradePlannerFailed',
                                            'reason': 'The request to the Spansh API wasn\'t successful! Please try at a later point in time!',
                                            'error': f'{e}'})

def trade_planner(obj):
    # start thread with first request
    threading.Thread(target=trade_planner_create_thread, args=(obj,), daemon=True).start()

    return 'The information has been requested from the Spansh API. An answer will be provided once available. Please be patient.'
# Region: Trade Planner End


def get_visuals(obj):
    image = screenshot()
    if not image: return "Unable to take screenshot."
    if not vision_client: return "Vision not enabled."

    completion = vision_client.chat.completions.create(
        extra_headers={
            "HTTP-Referer": "https://github.com/RatherRude/Elite-Dangerous-AI-Integration",
            "X-Title": "Elite Dangerous AI Integration",
        },
        model=llm_model_name if vision_model_name == '' else vision_model_name,
        messages=format_image(image, obj.get("query")),
    )

    return completion.choices[0].message.content


def register_actions(actionManager: ActionManager, eventManager: EventManager, llmClient: openai.OpenAI, llmModelName: str, visionClient: Optional[openai.OpenAI], visionModelName: Optional[str]):
    global event_manager, vision_client, llm_client, llm_model_name, vision_model_name
    event_manager = eventManager
    llm_client = llmClient
    llm_model_name = llmModelName
    vision_client = visionClient
    vision_model_name = visionModelName

    setGameWindowActive()
    # Register actions
    actionManager.registerAction('fire', "start firing primary weapons", {
        "type": "object",
        "properties": {}
    }, fire_primary_weapon)

    actionManager.registerAction('holdFire', "stop firing primary weapons", {
        "type": "object",
        "properties": {}
    }, hold_fire_primary_weapon)

    actionManager.registerAction('fireSecondary', "start secondary primary weapons", {
        "type": "object",
        "properties": {}
    }, fire_secondary_weapon)

    actionManager.registerAction('holdFireSecondary', "stop secondary primary weapons", {
        "type": "object",
        "properties": {}
    }, hold_fire_secondary_weapon)

    actionManager.registerAction('hyperSuperCombination',
                            "initiate FSD Jump, required to jump to the next system or to enter supercruise", {
                                "type": "object",
                                "properties": {}
                            }, hyper_super_combination)

    actionManager.registerAction('setSpeedZero', "Set speed to 0%", {
        "type": "object",
        "properties": {}
    }, set_speed_zero)

    actionManager.registerAction('setSpeed50', "Set speed to 50%", {
        "type": "object",
        "properties": {}
    }, set_speed_50)

    actionManager.registerAction('setSpeed100', "Set speed to 100%", {
        "type": "object",
        "properties": {}
    }, set_speed_100)

    actionManager.registerAction('deployHeatSink', "Deploy heat sink", {
        "type": "object",
        "properties": {}
    }, deploy_heat_sink)

    actionManager.registerAction('deployHardpointToggle', "Deploy or retract hardpoints", {
        "type": "object",
        "properties": {}
    }, deploy_hardpoint_toggle)

    actionManager.registerAction('increaseEnginesPower', "Increase engine power, can be done multiple times", {
        "type": "object",
        "properties": {
            "pips": {
                "type": "integer",
                "description": "Amount of pips to increase engine power, default: 1, maximum: 4",
            },
        },
        "required": ["pips"]
    }, increase_engines_power)

    actionManager.registerAction('increaseWeaponsPower', "Increase weapon power, can be done multiple times", {
        "type": "object",
        "properties": {
            "pips": {
                "type": "integer",
                "description": "Amount of pips to increase weapon power, default: 1, maximum: 4",
            },
        },
        "required": ["pips"]
    }, increase_weapons_power)

    actionManager.registerAction('increaseSystemsPower', "Increase systems power, can be done multiple times", {
        "type": "object",
        "properties": {
            "pips": {
                "type": "integer",
                "description": "Amount of pips to increase systems power, default: 1, maximum: 4",
            },
        },
        "required": ["pips"]
    }, increase_systems_power)

    actionManager.registerAction('galaxyMapOpen', "Open or close galaxy map", {
        "type": "object",
        "properties": {}
    }, galaxy_map_open)

    actionManager.registerAction('systemMapOpen', "Open or close system map", {
        "type": "object",
        "properties": {}
    }, system_map_open)

    actionManager.registerAction('cycleNextTarget', "Cycle to next target", {
        "type": "object",
        "properties": {}
    }, cycle_next_target)

    actionManager.registerAction('cycleFireGroupNext', "Cycle to next fire group", {
        "type": "object",
        "properties": {}
    }, cycle_fire_group_next)

    actionManager.registerAction('shipSpotLightToggle', "Toggle ship spotlight", {
        "type": "object",
        "properties": {}
    }, ship_spot_light_toggle)

    actionManager.registerAction('ejectAllCargo', "Eject all cargo", {
        "type": "object",
        "properties": {}
    }, eject_all_cargo)

    actionManager.registerAction('landingGearToggle', "Toggle landing gear", {
        "type": "object",
        "properties": {}
    }, landing_gear_toggle)

    actionManager.registerAction('useShieldCell', "Use shield cell", {
        "type": "object",
        "properties": {}
    }, use_shield_cell)

    actionManager.registerAction('fireChaffLauncher', "Fire chaff launcher", {
        "type": "object",
        "properties": {}
    }, fire_chaff_launcher)

    actionManager.registerAction('nightVisionToggle', "Toggle night vision", {
        "type": "object",
        "properties": {}
    }, night_vision_toggle)

    actionManager.registerAction('recallDismissShip', "Recall or dismiss ship, available on foot and inside SRV", {
        "type": "object",
        "properties": {}
    }, recall_dismiss_ship)

    actionManager.registerAction('getFactions', "Retrieve information about factions for a system", {
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

    actionManager.registerAction('getStations', "Retrieve information about stations in this system", {
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

    actionManager.registerAction('getGalnetNews', "Retrieve current interstellar news from Galnet", {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Inquiry you are trying to answer. Example: 'What happened to the thargoids recently?'"
            },
        },
        "required": ["query"]
    }, get_galnet_news)


    actionManager.registerAction('trade_plotter', "Retrieve a trade route from the trade plotter. Ask for unknown values and make sure they are known.", {
        "type": "object",
        "properties": {
            "system": {
                "type": "string",
                "description": "Name of the current system. Example: 'Sol'"
            },
            "station": {
                "type": "string",
                "description": "Name of the current station. Example: 'Wakata Station'"
            },
            "max_hops": {
                "type": "integer",
                "description": "Maximum number of hops (jumps) allowed for the route."
            },
            "max_hop_distance": {
                "type": "number",
                "description": "Maximum distance in light-years for a single hop."
            },
            "starting_capital": {
                "type": "number",
                "description": "Available starting capital in credits."
            },
            "max_cargo": {
                "type": "integer",
                "description": "Maximum cargo capacity in tons."
            },
            "requires_large_pad": {
                "type": "boolean",
                "description": "Whether the station must have a large landing pad."
            },
        },
        "required": [
            "system",
            "station",
            "max_hops",
            "max_hop_distance",
            "starting_capital",
            "max_cargo",
            "requires_large_pad",
        ]
    }, trade_planner)

    if vision_client:
        actionManager.registerAction('getVisuals', "Describes what's currently visible to the Commander.", {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Describe what you are curious about in the description. Example: 'Count the number of pirates'"
                }
            },
            "required": ["query"]
        }, get_visuals)
