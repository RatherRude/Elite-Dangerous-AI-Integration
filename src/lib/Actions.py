import json
from sys import platform
import threading
from time import sleep
import traceback
from typing import Optional

import openai
import requests

from .ScreenReader import ScreenReader
from .StatusParser import StatusParser
from .Logger import log
from .EDKeys import EDKeys
from .EventManager import EventManager
from .ActionManager import ActionManager

keys: EDKeys = None
vision_client: openai.OpenAI | None = None
llm_client: openai.OpenAI = None
llm_model_name: str = None
vision_model_name: str | None = None
event_manager: EventManager = None
status_parser: StatusParser = None


# Define functions for each action
# General Ship Actions
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


def fire_chaff_launcher(args):
    setGameWindowActive()
    keys.send('FireChaffLauncher')
    return f"Chaff launcher fired"


def night_vision_toggle(args):
    setGameWindowActive()
    keys.send('NightVisionToggle')
    return f"Night vision toggled"


def select_highest_threat(args):
    setGameWindowActive()
    keys.send('SelectHighestThreat')
    return f"Highest threat (if one exists) is now target locked"


def charge_ecm(args):
    setGameWindowActive()
    keys.send('ChargeECM')
    return "ECM is attempting to charge"


def galaxy_map_open(args):
    from pyautogui import typewrite

    setGameWindowActive()

    # Galaxy map already open, so we close it
    if status_parser.current_status["GuiFocus"] == 'GalaxyMap':
        keys.send('GalaxyMapOpen')
        sleep(1)

    # Freshly open the galaxy map
    keys.send('GalaxyMapOpen')
    if 'system_name' in args:
        sleep(2)
        keys.send('UI_Up')
        sleep(.05)
        keys.send('UI_Select')
        sleep(.05)

        # type in the System name
        typewrite(args['system_name'], interval=0)
        sleep(0.05)

        # send enter key
        keys.send_key('Down', 28)
        sleep(0.05)
        keys.send_key('Up', 28)

        sleep(.15)
        keys.send('UI_Right')
        sleep(.15)
        keys.send('UI_Select')

        if 'start_navigation' in args and args['start_navigation']:
            sleep(0.25)
            keys.send('UI_Right')
            sleep(0.25)
            keys.send('UI_Back')
            sleep(0.25)
            keys.send('UI_Back')
            sleep(3.5)
            keys.send('UI_Select', hold=1)

            sleep(.2)
            keys.send('GalaxyMapOpen')

            return f"A route to {args['system_name']} has been plotted."

        return f"The galaxy map has opened. It is now zoomed in on \"{args['system_name']}\". No route was plotted yet, only the commander can do that."

    return f"Galaxy map opened/closed"


def galaxy_map_close(args):
    setGameWindowActive()

    if status_parser.current_status["GuiFocus"] == 'GalaxyMap':
        keys.send('GalaxyMapOpen')

    return f"Galaxy map closed"


def system_map_open(args):
    setGameWindowActive()
    keys.send('SystemMapOpen')
    return f"System map opened/closed"


# Mainship Actions

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


def toggle_cargo_scoop(args):
    setGameWindowActive()
    keys.send('ToggleCargoScoop')
    return "Cargo scoop toggled"


def hyper_super_combination(args):
    setGameWindowActive()
    keys.send('HyperSuperCombination')
    return f"Frame Shift Drive is charging for a jump"

def undock(args):
    setGameWindowActive()
    # Early return if we're not docked
    if not status_parser.current_status["flags"]["Docked"]:
        raise Exception("The ship currently isn't docked.")

    if status_parser.current_status["GuiFocus"] in ['InternalPanel', 'CommsPanel', 'RolePanel', 'ExternalPanel']:
        keys.send('UIFocus')
        sleep(1)
    elif status_parser.current_status["GuiFocus"] == 'NoFocus':
        pass
    else:
        raise Exception("The currently focused UI needs to be closed first")

    keys.send('UI_Down', None, 3)
    keys.send('UI_Up')
    keys.send('UI_Select')

    return 'The ship is now undocking'

def request_docking(args):
    screenreader = ScreenReader()
    setGameWindowActive()
    if status_parser.current_status["GuiFocus"] in ['NoFocus', 'InternalPanel', 'CommsPanel', 'RolePanel']:
        keys.send('FocusLeftPanel')
        sleep(1)
    elif status_parser.current_status["GuiFocus"] == 'ExternalPanel':
        pass
    else:
        raise Exception('Docking menu not available in current UI Mode.')

    mode = None
    for x in range(4):
        mode = screenreader.detect_lhs_screen_tab()
        if mode:
            break
        keys.send('CycleNextPanel', None, 1)

    log('debug', 'Docking request screen tab', mode)
    if not mode:
        raise Exception('Panel not found')
    if mode == 'system':
        keys.send('CycleNextPanel', None, 3)
    elif mode == 'navigation':
        keys.send('CycleNextPanel', None, 2)
    elif mode == 'transactions':
        keys.send('CycleNextPanel', None, 1)

    sleep(0.3)
    keys.send('UI_Left')
    keys.send('UI_Right')
    sleep(0.1)
    keys.send('UI_Select')
    keys.send('UIFocus')

    return f"Docking has been requested"


# Ship Launched Fighter Actions
def order_request_dock(args):
    setGameWindowActive()
    keys.send('OrderRequestDock')
    return f"A request for docking has been sent"


# NPC Crew Order Actions
def npc_order(args):
    setGameWindowActive()
    if 'orders' in args:
        for order in args['orders']:
            keys.send(order)
    return f"Orders {', '.join(str(x) for x in args['orders'])} have been transmitted."


# SRV Actions (Horizons)
def toggle_drive_assist(args):
    setGameWindowActive()
    keys.send('ToggleDriveAssist')
    return "Drive assist has been toggled."

def buggy_primary_fire(args):
    setGameWindowActive()
    keys.send('BuggyPrimaryFireButton')
    return "Buggy primary fire triggered."

def buggy_secondary_fire(args):
    setGameWindowActive()
    keys.send('BuggySecondaryFireButton')
    return "Buggy secondary fire triggered."

def auto_break_buggy(args):
    setGameWindowActive()
    keys.send('AutoBreakBuggyButton')
    return "Auto-brake for buggy toggled."

def headlights_buggy(args):
    setGameWindowActive()
    keys.send('HeadlightsBuggyButton')
    return "Buggy headlights toggled."

def toggle_buggy_turret(args):
    setGameWindowActive()
    keys.send('ToggleBuggyTurretButton')
    return "Buggy turret mode toggled."

def select_target_buggy(args):
    setGameWindowActive()
    keys.send('SelectTarget_Buggy')
    return "Buggy target selection activated."

def increase_engines_power_buggy(args):
    setGameWindowActive()
    keys.send('IncreaseEnginesPower_Buggy')
    return "Buggy engine power increased."

def increase_weapons_power_buggy(args):
    setGameWindowActive()
    keys.send('IncreaseWeaponsPower_Buggy')
    return "Buggy weapons power increased."

def increase_systems_power_buggy(args):
    setGameWindowActive()
    keys.send('IncreaseSystemsPower_Buggy', None, args['pips'])
    return "Buggy systems power increased."

def reset_power_distribution_buggy(args):
    setGameWindowActive()
    keys.send('ResetPowerDistribution_Buggy', None, args['pips'])
    return "Buggy power distribution reset."

def toggle_cargo_scoop_buggy(args):
    setGameWindowActive()
    keys.send('ToggleCargoScoop_Buggy', None, args['pips'])
    return "Buggy cargo scoop toggled."

def eject_all_cargo_buggy(args):
    setGameWindowActive()
    keys.send('EjectAllCargo_Buggy')
    return "All cargo ejected from buggy."

def recall_dismiss_ship_buggy(args):
    setGameWindowActive()
    keys.send('RecallDismissShip')
    return "Remote ship has been recalled or dismissed."

def galaxy_map_open_buggy(args):
    setGameWindowActive()
    keys.send('GalaxyMapOpen_Buggy')
    return "Galaxy map opened."

def system_map_open_buggy(args):
    setGameWindowActive()
    keys.send('SystemMapOpen_Buggy')
    return "System map opened."

# On-Foot Actions (Odyssey)
def primary_interact_humanoid(args):
    setGameWindowActive()
    keys.send('HumanoidPrimaryInteractButton')
    return "Primary interaction initiated."

def secondary_interact_humanoid(args):
    setGameWindowActive()
    keys.send('HumanoidSecondaryInteractButton')
    return "Secondary interaction initiated."

def equip_humanoid(args):
    if 'equipment' in args:
        keys.send(args['equipment'])
    return f"{args['equipment']} has been triggered."

def toggle_flashlight_humanoid(args):
    setGameWindowActive()
    keys.send('HumanoidToggleFlashlightButton')
    return "Flashlight toggled."

def toggle_night_vision_humanoid(args):
    setGameWindowActive()
    keys.send('HumanoidToggleNightVisionButton')
    return "Night vision toggled."

def toggle_shields_humanoid(args):
    setGameWindowActive()
    keys.send('HumanoidToggleShieldsButton')
    return "Shields toggled."

def clear_authority_level_humanoid(args):
    setGameWindowActive()
    keys.send('HumanoidClearAuthorityLevel')
    return "Authority level cleared."

def health_pack_humanoid(args):
    setGameWindowActive()
    keys.send('HumanoidHealthPack')
    return "Health pack used."

def battery_humanoid(args):
    setGameWindowActive()
    keys.send('HumanoidBattery')
    return "Battery used."

def galaxy_map_open_humanoid(args):
    setGameWindowActive()
    keys.send('GalaxyMapOpen_Humanoid')
    return "Galaxy map opened."

def system_map_open_humanoid(args):
    setGameWindowActive()
    keys.send('SystemMapOpen_Humanoid')
    return "System map opened."

def recall_dismiss_ship_humanoid(args):
    setGameWindowActive()
    keys.send('HumanoidOpenAccessPanelButton', state=1)
    sleep(.3)
    keys.send('HumanoidOpenAccessPanelButton', state=0)
    sleep(.05)
    keys.send('UI_Left')
    keys.send('UI_Up')
    sleep(.15)
    keys.send('UI_Select')
    keys.send('HumanoidOpenAccessPanelButton', state=1)
    sleep(.2)
    keys.send('HumanoidOpenAccessPanelButton', state=0)
    return "Remote ship has been recalled or dismissed."


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
            sleep(.15)
            log("debug", "Set game window as active")
        except:
            log("error", "Failed to set game window as active")
    else:
        log("info", "Unable to find Elite game window")


def screenshot(new_height: int = 720):
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
            log('error', e, traceback.format_exc())
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

    log('debug', 'Request data', dict)
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
        log('error', e, traceback.format_exc())
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


def educated_guesses_message(search_query, valid_list):
    split_string = search_query.split()

    caught_items = []

    # Iterate over each word in the split string
    for word in split_string:
        # Check if the word is part of any value in the array
        for element in valid_list:
            if word in element:
                caught_items.append(element)

    message = ""
    if caught_items:
        guesses_str = ', '.join(caught_items)
        message = (
            f"Restart search with valid inputs, here are suggestions: {guesses_str}"
        )

    return message


# Prepare a request for the spansh station finder
def prepare_station_request(obj):
    known_modules = [
        "AX Missile Rack",
        "AX Multi-Cannon",
        "Abrasion Blaster",
        "Advanced Docking Computer",
        "Advanced Missile Rack",
        "Advanced Multi-Cannon",
        "Advanced Planetary Approach Suite",
        "Advanced Plasma Accelerator",
        "Auto Field-Maintenance Unit",
        "Beam Laser",
        "Bi-Weave Shield Generator",
        "Burst Laser",
        "Business Class Passenger Cabin",
        "Cannon",
        "Cargo Rack",
        "Cargo Scanner",
        "Caustic Sink Launcher",
        "Chaff Launcher",
        "Collector Limpet Controller",
        "Corrosion Resistant Cargo Rack",
        "Cytoscrambler Burst Laser",
        "Decontamination Limpet Controller",
        "Detailed Surface Scanner",
        "Economy Class Passenger Cabin",
        "Electronic Countermeasure",
        "Enforcer Cannon",
        "Enhanced AX Missile Rack",
        "Enhanced AX Multi-Cannon",
        "Enhanced Performance Thrusters",
        "Enhanced Xeno Scanner",
        "Enzyme Missile Rack",
        "Experimental Weapon Stabiliser",
        "Fighter Hangar",
        "First Class Passenger Cabin",
        "Fragment Cannon",
        "Frame Shift Drive",
        "Frame Shift Drive (SCO)",
        "Frame Shift Drive Interdictor",
        "Frame Shift Wake Scanner",
        "Fuel Scoop",
        "Fuel Tank",
        "Fuel Transfer Limpet Controller",
        "Guardian FSD Booster",
        "Guardian Gauss Cannon",
        "Guardian Hull Reinforcement",
        "Guardian Hybrid Power Distributor",
        "Guardian Hybrid Power Plant",
        "Guardian Module Reinforcement",
        "Guardian Nanite Torpedo Pylon",
        "Guardian Plasma Charger",
        "Guardian Shard Cannon",
        "Guardian Shield Reinforcement",
        "Hatch Breaker Limpet Controller",
        "Heat Sink Launcher",
        "Hull Reinforcement Package",
        "Imperial Hammer Rail Gun",
        "Kill Warrant Scanner",
        "Life Support",
        "Lightweight Alloy",
        "Luxury Class Passenger Cabin",
        "Meta Alloy Hull Reinforcement",
        "Military Grade Composite",
        "Mine Launcher",
        "Mining Lance",
        "Mining Laser",
        "Mining Multi Limpet Controller",
        "Mirrored Surface Composite",
        "Missile Rack",
        "Module Reinforcement Package",
        "Multi-Cannon",
        "Operations Multi Limpet Controller",
        "Pacifier Frag-Cannon",
        "Pack-Hound Missile Rack",
        "Planetary Approach Suite",
        "Planetary Vehicle Hangar",
        "Plasma Accelerator",
        "Point Defence",
        "Power Distributor",
        "Power Plant",
        "Prismatic Shield Generator",
        "Prospector Limpet Controller",
        "Pulse Disruptor Laser",
        "Pulse Laser",
        "Pulse Wave Analyser",
        "Pulse Wave Xeno Scanner",
        "Rail Gun",
        "Reactive Surface Composite",
        "Recon Limpet Controller",
        "Refinery",
        "Reinforced Alloy",
        "Remote Release Flak Launcher",
        "Remote Release Flechette Launcher",
        "Repair Limpet Controller",
        "Rescue Multi Limpet Controller",
        "Research Limpet Controller",
        "Retributor Beam Laser",
        "Rocket Propelled FSD Disruptor",
        "Seeker Missile Rack",
        "Seismic Charge Launcher",
        "Sensors",
        "Shield Booster",
        "Shield Cell Bank",
        "Shield Generator",
        "Shock Cannon",
        "Shock Mine Launcher",
        "Shutdown Field Neutraliser",
        "Standard Docking Computer",
        "Sub-Surface Displacement Missile",
        "Sub-Surface Extraction Missile",
        "Supercruise Assist",
        "Thargoid Pulse Neutraliser",
        "Thrusters",
        "Torpedo Pylon",
        "Universal Multi Limpet Controller",
        "Xeno Multi Limpet Controller",
        "Xeno Scanner"
    ]
    known_commodities = [
        "AI Relics",
        "Advanced Catalysers",
        "Advanced Medicines",
        "Aepyornis Egg",
        "Aganippe Rush",
        "Agri-Medicines",
        "Agronomic Treatment",
        "Alacarakmo Skin Art",
        "Albino Quechua Mammoth Meat",
        "Alexandrite",
        "Algae",
        "Altairian Skin",
        "Aluminium",
        "Alya Body Soap",
        "Ancient Artefact",
        "Ancient Key",
        "Anduliga Fire Works",
        "Animal Meat",
        "Animal Monitors",
        "Anomaly Particles",
        "Antimatter Containment Unit",
        "Antique Jewellery",
        "Antiquities",
        "Any Na Coffee",
        "Apa Vietii",
        "Aquaponic Systems",
        "Arouca Conventual Sweets",
        "Articulation Motors",
        "Assault Plans",
        "Atmospheric Processors",
        "Auto-Fabricators",
        "Az Cancri Formula 42",
        "Azure Milk",
        "Baked Greebles",
        "Baltah'sine Vacuum Krill",
        "Banki Amphibious Leather",
        "Basic Medicines",
        "Bast Snake Gin",
        "Battle Weapons",
        "Bauxite",
        "Beer",
        "Belalans Ray Leather",
        "Benitoite",
        "Bertrandite",
        "Beryllium",
        "Bioreducing Lichen",
        "Biowaste",
        "Bismuth",
        "Black Box",
        "Bone Fragments",
        "Bootleg Liquor",
        "Borasetani Pathogenetics",
        "Bromellite",
        "Buckyball Beer Mats",
        "Building Fabricators",
        "Burnham Bile Distillate",
        "CD-75 Kitten Brand Coffee",
        "CMM Composite",
        "Caustic Tissue Sample",
        "Centauri Mega Gin",
        "Ceramic Composites",
        "Ceremonial Heike Tea",
        "Ceti Rabbits",
        "Chameleon Cloth",
        "Chateau De Aegaeon",
        "Chemical Waste",
        "Cherbones Blood Crystals",
        "Chi Eridani Marine Paste",
        "Classified Experimental Equipment",
        "Clothing",
        "Cobalt",
        "Coffee",
        "Coltan",
        "Combat Stabilisers",
        "Commercial Samples",
        "Computer Components",
        "Conductive Fabrics",
        "Consumer Technology",
        "Copper",
        "Coquim Spongiform Victuals",
        "Coral Sap",
        "Crom Silver Fesh",
        "Crop Harvesters",
        "Cryolite",
        "Crystalline Spheres",
        "Cyst Specimen",
        "Damaged Escape Pod",
        "Damna Carapaces",
        "Data Core",
        "Delta Phoenicis Palms",
        "Deuringas Truffles",
        "Diplomatic Bag",
        "Diso Ma Corn",
        "Domestic Appliances",
        "Duradrives",
        "Earth Relics",
        "Eden Apples of Aerial",
        "Eleu Thermals",
        "Emergency Power Cells",
        "Encrypted Correspondence",
        "Encrypted Data Storage",
        "Energy Grid Assembly",
        "Eranin Pearl Whisky",
        "Eshu Umbrellas",
        "Esuseku Caviar",
        "Ethgreze Tea Buds",
        "Evacuation Shelter",
        "Exhaust Manifold",
        "Experimental Chemicals",
        "Explosives",
        "Fish",
        "Food Cartridges",
        "Fossil Remnants",
        "Fruit and Vegetables",
        "Fujin Tea",
        "Galactic Travel Guide",
        "Gallite",
        "Gallium",
        "Geawen Dance Dust",
        "Gene Bank",
        "Geological Equipment",
        "Geological Samples",
        "Gerasian Gueuze Beer",
        "Giant Irukama Snails",
        "Giant Verrix",
        "Gilya Signature Weapons",
        "Gold",
        "Goman Yaupon Coffee",
        "Goslarite",
        "Grain",
        "Grandidierite",
        "Guardian Casket",
        "Guardian Orb",
        "Guardian Relic",
        "Guardian Tablet",
        "Guardian Totem",
        "Guardian Urn",
        "H.E. Suits",
        "HIP 10175 Bush Meat",
        "HIP 118311 Swarm",
        "HIP Organophosphates",
        "HIP Proto-Squid",
        "HN Shock Mount",
        "HR 7221 Wheat",
        "Hafnium 178",
        "Haiden Black Brew",
        "Hardware Diagnostic Sensor",
        "Harma Silver Sea Rum",
        "Havasupai Dream Catcher",
        "Heatsink Interlink",
        "Helvetitj Pearls",
        "Holva Duelling Blades",
        "Honesty Pills",
        "Hostages",
        "Hydrogen Fuel",
        "Hydrogen Peroxide",
        "Imperial Slaves",
        "Impure Spire Mineral",
        "Indi Bourbon",
        "Indite",
        "Indium",
        "Insulating Membrane",
        "Ion Distributor",
        "Jadeite",
        "Jaques Quinentian Still",
        "Jaradharre Puzzle Box",
        "Jaroua Rice",
        "Jotun Mookah",
        "Kachirigin Filter Leeches",
        "Kamitra Cigars",
        "Kamorin Historic Weapons",
        "Karetii Couture",
        "Karsuki Locusts",
        "Kinago Violins",
        "Kongga Ale",
        "Koro Kung Pellets",
        "LTT Hyper Sweet",
        "Land Enrichment Systems",
        "Landmines",
        "Lanthanum",
        "Large Survey Data Cache",
        "Lavian Brandy",
        "Leather",
        "Leathery Eggs",
        "Leestian Evil Juice",
        "Lepidolite",
        "Liquid oxygen",
        "Liquor",
        "Lithium",
        "Lithium Hydroxide",
        "Live Hecate Sea Worms",
        "Low Temperature Diamonds",
        "Lucan Onionhead",
        "Lyrae Weed",
        "Magnetic Emitter Coil",
        "Marine Equipment",
        "Master Chefs",
        "Mechucos High Tea",
        "Medb Starlube",
        "Medical Diagnostic Equipment",
        "Meta-Alloys",
        "Methane Clathrate",
        "Methanol Monohydrate Crystals",
        "Micro Controllers",
        "Micro-weave Cooling Hoses",
        "Microbial Furnaces",
        "Military Grade Fabrics",
        "Military Intelligence",
        "Military Plans",
        "Mineral Extractors",
        "Mineral Oil",
        "Modular Terminals",
        "Moissanite",
        "Mokojing Beast Feast",
        "Mollusc Brain Tissue",
        "Mollusc Fluid",
        "Mollusc Membrane",
        "Mollusc Mycelium",
        "Mollusc Soft Tissue",
        "Mollusc Spores",
        "Momus Bog Spaniel",
        "Monazite",
        "Motrona Experience Jelly",
        "Mukusubii Chitin-os",
        "Mulachi Giant Fungus",
        "Muon Imager",
        "Musgravite",
        "Mysterious Idol",
        "Nanobreakers",
        "Nanomedicines",
        "Narcotics",
        "Natural Fabrics",
        "Neofabric Insulation",
        "Neritus Berries",
        "Nerve Agents",
        "Ngadandari Fire Opals",
        "Nguna Modern Antiques",
        "Njangari Saddles",
        "Non Euclidian Exotanks",
        "Non-Lethal Weapons",
        "Occupied Escape Pod",
        "Ochoeng Chillies",
        "Onionhead",
        "Onionhead Alpha Strain",
        "Onionhead Beta Strain",
        "Onionhead Gamma Strain",
        "Ophiuch Exino Artefacts",
        "Organ Sample",
        "Orrerian Vicious Brew",
        "Osmium",
        "Painite",
        "Palladium",
        "Pantaa Prayer Sticks",
        "Pavonis Ear Grubs",
        "Performance Enhancers",
        "Personal Effects",
        "Personal Gifts",
        "Personal Weapons",
        "Pesticides",
        "Platinum",
        "Platinum Alloy",
        "Pod Core Tissue",
        "Pod Dead Tissue",
        "Pod Mesoglea",
        "Pod Outer Tissue",
        "Pod Shell Tissue",
        "Pod Surface Tissue",
        "Pod Tissue",
        "Political Prisoners",
        "Polymers",
        "Power Converter",
        "Power Generators",
        "Power Transfer Bus",
        "Praseodymium",
        "Precious Gems",
        "Progenitor Cells",
        "Prohibited Research Materials",
        "Protective Membrane Scrap",
        "Prototype Tech",
        "Pyrophyllite",
        "Radiation Baffle",
        "Rajukru Multi-Stoves",
        "Rapa Bao Snake Skins",
        "Rare Artwork",
        "Reactive Armour",
        "Rebel Transmissions",
        "Reinforced Mounting Plate",
        "Resonating Separators",
        "Rhodplumsite",
        "Robotics",
        "Rockforth Fertiliser",
        "Rusani Old Smokey",
        "Rutile",
        "SAP 8 Core Container",
        "Samarium",
        "Sanuma Decorative Meat",
        "Saxon Wine",
        "Scientific Research",
        "Scientific Samples",
        "Scrap",
        "Semi-Refined Spire Mineral",
        "Semiconductors",
        "Serendibite",
        "Shan's Charis Orchid",
        "Silver",
        "Skimmer Components",
        "Slaves",
        "Small Survey Data Cache",
        "Soontill Relics",
        "Sothis Crystalline Gold",
        "Space Pioneer Relics",
        "Structural Regulators",
        "Superconductors",
        "Surface Stabilisers",
        "Survival Equipment",
        "Synthetic Fabrics",
        "Synthetic Meat",
        "Synthetic Reagents",
        "Taaffeite",
        "Tactical Data",
        "Tanmark Tranquil Tea",
        "Tantalum",
        "Tarach Spice",
        "Tauri Chimes",
        "Tea",
        "Technical Blueprints",
        "Telemetry Suite",
        "Terra Mater Blood Bores",
        "Thallium",
        "Thargoid Basilisk Tissue Sample",
        "Thargoid Biological Matter",
        "Thargoid Cyclops Tissue Sample",
        "Thargoid Glaive Tissue Sample",
        "Thargoid Heart",
        "Thargoid Hydra Tissue Sample",
        "Thargoid Link",
        "Thargoid Medusa Tissue Sample",
        "Thargoid Orthrus Tissue Sample",
        "Thargoid Probe",
        "Thargoid Resin",
        "Thargoid Scout Tissue Sample",
        "Thargoid Scythe Tissue Sample",
        "Thargoid Sensor",
        "Thargoid Technology Samples",
        "The Hutton Mug",
        "The Waters of Shintara",
        "Thermal Cooling Units",
        "Thorium",
        "Thrutis Cream",
        "Tiegfries Synth Silk",
        "Time Capsule",
        "Tiolce Waste2Paste Units",
        "Titan Deep Tissue Sample",
        "Titan Drive Component",
        "Titan Maw Deep Tissue Sample",
        "Titan Maw Partial Tissue Sample",
        "Titan Maw Tissue Sample",
        "Titan Partial Tissue Sample",
        "Titan Tissue Sample",
        "Titanium",
        "Tobacco",
        "Toxandji Virocide",
        "Toxic Waste",
        "Trade Data",
        "Trinkets of Hidden Fortune",
        "Tritium",
        "Ultra-Compact Processor Prototypes",
        "Unclassified Relic",
        "Unoccupied Escape Pod",
        "Unstable Data Core",
        "Uraninite",
        "Uranium",
        "Uszaian Tree Grub",
        "Utgaroar Millennial Eggs",
        "Uzumoku Low-G Wings",
        "V Herculis Body Rub",
        "Vanayequi Ceratomorpha Fur",
        "Vega Slimweed",
        "Vidavantian Lace",
        "Void Extract Coffee",
        "Void Opal",
        "Volkhab Bee Drones",
        "Water",
        "Water Purifiers",
        "Wheemete Wheat Cakes",
        "Wine",
        "Witchhaul Kobe Beef",
        "Wolf Fesh",
        "Wreckage Components",
        "Wulpa Hyperbore Systems",
        "Wuthielo Ku Froth",
        "Xenobiological Prison Pod",
        "Xihe Biomorphic Companions",
        "Yaso Kondi Leaf",
        "Zeessze Ant Grub Glue"
    ]
    known_ships = [
        "Adder",
        "Alliance Challenger",
        "Alliance Chieftain",
        "Alliance Crusader",
        "Anaconda",
        "Asp Explorer",
        "Asp Scout",
        "Beluga Liner",
        "Cobra MkIII",
        "Cobra MkIV",
        "Diamondback Explorer",
        "Diamondback Scout",
        "Dolphin",
        "Eagle",
        "Federal Assault Ship",
        "Federal Corvette",
        "Federal Dropship",
        "Federal Gunship",
        "Fer-de-Lance",
        "Hauler",
        "Imperial Clipper",
        "Imperial Courier",
        "Imperial Cutter",
        "Imperial Eagle",
        "Keelback",
        "Krait MkII",
        "Krait Phantom",
        "Mamba",
        "Orca",
        "Python",
        "Python MkII",
        "Sidewinder",
        "Type-10 Defender",
        "Type-6 Transporter",
        "Type-7 Transporter",
        "Type-8 Transporter",
        "Type-9 Heavy",
        "Viper MkIII",
        "Viper MkIV",
        "Vulture"
    ]
    known_services = [
        "Apex Interstellar",
        "Bartender",
        "Black Market",
        "Crew Lounge",
        "Fleet Carrier Administration",
        "Fleet Carrier Fuel",
        "Fleet Carrier Management",
        "Fleet Carrier Vendor",
        "Frontline Solutions",
        "Interstellar Factors Contact",
        "Market",
        "Material Trader",
        "Missions",
        "Outfitting",
        "Pioneer Supplies",
        "Powerplay",
        "Redemption Office",
        "Refuel",
        "Repair",
        "Restock",
        "Search and Rescue",
        "Shipyard",
        "Shop",
        "Social Space",
        "Technology Broker",
        "Universal Cartographics",
        "Vista Genomics"
    ]
    log('debug', 'Station Finder Request', obj)
    filters = {
        "type": {
            "value": [
                "Asteroid base",
                "Coriolis Starport",
                "Mega ship",
                "Ocellus Starport",
                "Orbis Starport",
                "Outpost",
                "Planetary Outpost",
                "Planetary Port",
                "Settlement"
            ]
        },
        "distance": {
            "min": "0",
            "max": str(obj.get("distance", 50000))
        }
    }
    # Add optional filters if they exist
    if obj.get("has_large_pad", True):
        filters["has_large_pad"] = {"value": True}
    if "material_trader" in obj and obj["material_trader"]:
        filters["material_trader"] = {"value": obj["material_trader"]}
    if "technology_broker" in obj and obj["technology_broker"]:
        filters["technology_broker"] = {"value": obj["technology_broker"]}
    if "market" in obj and obj["market"]:
        market_filters = []
        for market_item in obj["market"]:
            market_item["name"] = ' '.join(word.capitalize() for word in market_item["name"].split())
            if not market_item["name"] in known_commodities:
                raise Exception(
                    f"Invalid commodity name: {market_item['name']}. {educated_guesses_message(market_item['name'], known_commodities)}")
            market_filter = {
                "name": market_item["name"]
            }
            if market_item["transaction"] == "Buy":
                market_filter["supply"] = {
                    "value": [
                        str(market_item["amount"]),
                        "999999999"
                    ],
                    "comparison": "<=>"
                }
            elif market_item["transaction"] == "Sell":
                market_filter["demand"] = {
                    "value": [
                        str(market_item["amount"]),
                        "999999999"
                    ],
                    "comparison": "<=>"
                }
            market_filters.append(market_filter)
        filters["market"] = market_filters
    if "modules" in obj:
        modules_filter = {}
        for module in obj["modules"]:
            module["name"] = ' '.join(word.capitalize() for word in module["name"].split())
            if module["name"] not in known_modules:
                raise Exception(
                    f"Invalid module name: {module['name']}. {educated_guesses_message(module['name'], known_modules)}")
        filters["modules"] = obj["modules"]
    if "ships" in obj:
        for ship in obj["ships"]:
            ship["name"] = ' '.join(word.capitalize() for word in ship["name"].split())
            if ship["name"] not in known_ships:
                raise Exception(
                    f"Invalid ship name: {ship['name']}. {educated_guesses_message(ship['name'], known_ships)}")
        filters["ships"] = {"value": obj["ships"]}
    if "services" in obj:
        for service in obj["services"]:
            service["name"] = ' '.join(word.capitalize() for word in service["name"].split())
            if service["name"] not in known_services:
                raise Exception(
                    f"Invalid service name: {service['name']}. {educated_guesses_message(service['name'], known_services)}")
        filters["services"] = {"value": obj["services"]}
    if "name" in obj and obj["name"]:
        filters["name"] = {
            "value": obj["name"]
        }
    # Build the request body
    request_body = {
        "filters": filters,
        "sort": [
            {
                "distance": {
                    "direction": "asc"
                }
            }
        ],
        "size": 3,
        "page": 0,
        "reference_system": obj.get("reference_system", "Sol")
    }
    return request_body


# filter a spansh station result set for only relevant information
def filter_station_response(request, response):
    # Extract requested commodities and modules
    commodities_requested = {item["name"] for item in request["filters"].get("market", {})}
    modules_requested = {item["name"] for item in request["filters"].get("modules", {})}
    ships_requested = {item["name"] for item in request["filters"].get("ships", {}).get("value", [])}
    services_requested = {item["name"] for item in request["filters"].get("services", {}).get("value", [])}

    log('debug', 'modules_requested', modules_requested)

    filtered_results = []

    for result in response["results"]:
        filtered_result = {
            "name": result["name"],
            "system": result["system_name"],
            "distance": result["distance"],
            "orbit": result["distance_to_arrival"],
            "has_large_pad": result["has_large_pad"],
            "is_planetary": result["is_planetary"]
        }

        if "market" in result:
            filtered_market = [
                commodity for commodity in result["market"]
                if commodity["commodity"] in commodities_requested
            ]
            filtered_result["market"] = filtered_market

        if "modules" in result:
            filtered_modules = []
            for module in result["modules"]:
                for requested_module in modules_requested:
                    if requested_module.lower() in module["name"].lower():
                        filtered_modules.append(
                            {"name": module["name"], "class": module["class"], "rating": module["rating"],
                             "price": module["price"]})

            if filtered_modules:
                filtered_result["modules"] = filtered_modules

        if "ships" in result:
            filtered_ships = []
            for ship in result["ships"]:
                for requested_ship in ships_requested:
                    if requested_ship.lower() in ship["name"].lower():
                        filtered_ships.append(ship)

            if filtered_ships:
                filtered_result["ships"] = filtered_ships

        if "services" in result:
            filtered_services = []
            for service in result["services"]:
                for requested_service in services_requested:
                    if requested_service.lower() in service["name"].lower():
                        filtered_services.append(service)

            if filtered_services:
                filtered_result["services"] = filtered_services

        filtered_results.append(filtered_result)

    return {
        "amount_total": response["count"],
        "amount_displayed": min(response["count"], response["size"]),
        "results": filtered_results
    }


def station_finder(obj):
    # Initialize the filters
    request_body = prepare_station_request(obj)

    url = "https://spansh.co.uk/api/stations/search"
    try:
        response = requests.post(url, json=request_body)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx and 5xx)

        data = response.json()

        filtered_data = filter_station_response(request_body, data)

        return f'Here is a list of stations: {json.dumps(filtered_data)}'
    except Exception as e:
        log('error', e, traceback.format_exc())
        return 'An error has occurred. The station finder seems currently not available.'


def prepare_system_request(obj):
    known_allegiances = [
        "Alliance", "Empire", "Federation", "Guardian",
        "Independent", "Pilots Federation", "Player Pilots", "Thargoid"
    ]
    known_governments = [
        "Anarchy", "Communism", "Confederacy", "Cooperative", "Corporate",
        "Democracy", "Dictatorship", "Feudal", "None", "Patronage",
        "Prison", "Prison Colony", "Theocracy"
    ]
    known_states = [
        "Blight", "Boom", "Bust", "Civil Liberty", "Civil Unrest", "Civil War",
        "Drought", "Election", "Expansion", "Famine", "Infrastructure Failure",
        "Investment", "Lockdown", "Natural Disaster", "None", "Outbreak",
        "Pirate Attack", "Public Holiday", "Retreat", "Terrorist Attack", "War"
    ]
    known_powers = ["A. Lavigny-Duval", "Aisling Duval", "Archon Delaine", "Denton Patreus", "Edmund Mahon",
                    "Felicia Winters", "Jerome Archer", "Li Yong-Rui", "Nakato Kaine", "Pranav Antal", "Yuri Grom",
                    "Zemina Torval"]
    known_economies = [
        "Agriculture", "Colony", "Extraction", "High Tech", "Industrial",
        "Military", "None", "Refinery", "Service", "Terraforming", "Tourism"
    ]
    known_security_levels = ["Anarchy", "High", "Low", "Medium"]
    known_thargoid_war_states = ["None", "Thargoid Controlled", "Thargoid Harvest", "Thargoid Probing",
                                 "Thargoid Recovery", "Thargoid Stronghold"]
    log('debug', 'System Finder Request', obj)
    filters = {
        "distance": {
            "min": "0",
            "max": str(obj.get("distance", 50000))
        }
    }

    # Add optional filters if they exist
    if "allegiance" in obj and obj["allegiance"]:
        for allegiance in obj["allegiance"]:
            if allegiance not in known_allegiances:
                raise Exception(
                    f"Invalid allegiance: {allegiance}. {educated_guesses_message(allegiance, known_allegiances)}")
        filters["allegiance"] = {"value": obj["allegiance"]}

    if "state" in obj and obj["state"]:
        for state in obj["state"]:
            if state not in known_states:
                raise Exception(
                    f"Invalid state: {state}. {educated_guesses_message(state, known_states)}")
        filters["state"] = {"value": obj["state"]}

    if "government" in obj and obj["government"]:
        for government in obj["government"]:
            if government not in known_governments:
                raise Exception(
                    f"Invalid government: {government}. {educated_guesses_message(government, known_governments)}")
        filters["government"] = {"value": obj["government"]}

    if "power" in obj and obj["power"]:
        for power in obj["power"]:
            if power not in known_powers:
                raise Exception(
                    f"Invalid power: {power}. {educated_guesses_message(power, known_powers)}")
        filters["controlling_power"] = {"value": obj["power"]}

    if "primary_economy" in obj and obj["primary_economy"]:
        for economy in obj["primary_economy"]:
            if economy not in known_economies:
                raise Exception(
                    f"Invalid primary economy: {economy}. {educated_guesses_message(economy, known_economies)}")
        filters["primary_economy"] = {"value": obj["primary_economy"]}

    if "security" in obj and obj["security"]:
        for security_level in obj["security"]:
            if security_level not in known_security_levels:
                raise Exception(
                    f"Invalid security level: {security_level}. {educated_guesses_message(security_level, known_security_levels)}")
        filters["security"] = {"value": obj["security"]}

    if "thargoid_war_state" in obj and obj["thargoid_war_state"]:
        for thargoid_war_state in obj["thargoid_war_state"]:
            if thargoid_war_state not in known_thargoid_war_states:
                raise Exception(
                    f"Invalid thargoid war state: {thargoid_war_state}. {educated_guesses_message(thargoid_war_state, known_thargoid_war_states)}")
        filters["thargoid_war_state"] = {"value": obj["thargoid_war_state"]}

    if "population" in obj and obj["population"]:
        comparison = obj["population"].get("comparison", ">")
        value = obj["population"].get("value", 0)

        lower_bound = value if comparison == ">" else 0
        upper_bound = value if comparison == "<" else 100000000000

        filters["population"] = {
            "comparison": "<=>",
            "value": [lower_bound, upper_bound]
        }

    if "name" in obj and obj["name"]:
        filters["name"] = {
            "value": obj["name"]
        }

    # Build the request body
    request_body = {
        "filters": filters,
        "sort": [
            {
                "distance": {
                    "direction": "asc"
                }
            }
        ],
        "size": 3,
        "page": 0,
        "reference_system": obj.get("reference_system", "Sol")
    }

    return request_body


# Function to filter and format the system response
def filter_system_response(request, response):
    filtered_results = []

    # Check which filters are in the request and adjust the response accordingly
    request_filters = request.get("filters", {})

    for system in response.get("results", []):
        filtered_system = {}

        # if "name" in system and system["name"]:
        filtered_system["name"] = system.get("name")
        filtered_system["allegiance"] = system.get("allegiance", "Independent")
        if "controlling_minor_faction" in system and system["controlling_minor_faction"]:
            filtered_system["minor_faction"] = system.get("controlling_minor_faction", )
        if "controlling_minor_faction_state" in system and system["controlling_minor_faction_state"]:
            filtered_system["minor_faction_state"] = system.get("controlling_minor_faction_state")
        # Only add power if it was requested
        if "power" in request_filters and "power" in system and system["power"]:
            filtered_system["power"] = system.get("power")
            filtered_system["power_state"] = system.get("power_state", "None")
        filtered_system["distance"] = system.get("distance")
        filtered_system["body_count"] = system.get("body_count", 0)
        filtered_system["station_count"] = len(system.get("stations", []))
        filtered_system["population"] = system.get("population", 0)
        # Only add government if it was requested
        if "government" in request_filters and "government" in system and system["government"]:
            filtered_system["government"] = system.get("government")

        filtered_system["primary_economy"] = system.get("primary_economy", "None")
        filtered_system["security"] = system.get("security", "Anarchy")

        # Only add thargoid war state if it was requested
        if "thargoid_war_state" in request_filters and "thargoid_war_state" in system and system["thargoid_war_state"]:
            filtered_system["thargoid_war_state"] = system.get("thargoid_war_state")

        # Only add if needs_permit is true
        if "needs_permit" in request_filters and "needs_permit" in system and system["needs_permit"]:
            filtered_system["needs_permit"] = system.get("needs_permit")

        # Add filtered system to the list
        filtered_results.append(filtered_system)

    # Construct and return the filtered response
    return {
        "amount_total": response["count"],
        "amount_displayed": min(response["count"], response["size"]),
        "results": filtered_results,
    }


# System finder function that sends the request to the Spansh API
def system_finder(obj):
    # Build the request body
    request_body = prepare_system_request(obj)

    url = "https://spansh.co.uk/api/systems/search"

    try:
        response = requests.post(url, json=request_body)
        response.raise_for_status()

        data = response.json()
        # Filter the response
        filtered_data = filter_system_response(request_body, data)

        return f'Here is a list of systems: {json.dumps(filtered_data)}'

    except Exception as e:
        log('error', e, traceback.format_exc())
        return 'An error occurred. The system finder seems to be currently unavailable.'


def prepare_body_request(obj):
    known_planet_types_obj = {
        "Planet": [
            "Ammonia world",
            "Class I gas giant",
            "Class II gas giant",
            "Class III gas giant",
            "Class IV gas giant",
            "Class V gas giant",
            "Earth-like world",
            "Gas giant with ammonia-based life",
            "Gas giant with water-based life",
            "Helium gas giant",
            "Helium-rich gas giant",
            "High metal content world",
            "Icy body",
            "Metal-rich body",
            "Rocky Ice world",
            "Rocky body",
            "Water giant",
            "Water world"
        ],
        "Star": [
            "A (Blue-White super giant) Star",
            "A (Blue-White) Star",
            "B (Blue-White super giant) Star",
            "B (Blue-White) Star",
            "Black Hole",
            "C Star",
            "CJ Star",
            "CN Star",
            "F (White super giant) Star",
            "F (White) Star",
            "G (White-Yellow super giant) Star",
            "G (White-Yellow) Star",
            "Herbig Ae/Be Star",
            "K (Yellow-Orange giant) Star",
            "K (Yellow-Orange) Star",
            "L (Brown dwarf) Star",
            "M (Red dwarf) Star",
            "M (Red giant) Star",
            "M (Red super giant) Star",
            "MS-type Star",
            "Neutron Star",
            "O (Blue-White) Star",
            "S-type Star",
            "Supermassive Black Hole",
            "T (Brown dwarf) Star",
            "T Tauri Star",
            "White Dwarf (D) Star",
            "White Dwarf (DA) Star",
            "White Dwarf (DAB) Star",
            "White Dwarf (DAV) Star",
            "White Dwarf (DAZ) Star",
            "White Dwarf (DB) Star",
            "White Dwarf (DBV) Star",
            "White Dwarf (DBZ) Star",
            "White Dwarf (DC) Star",
            "White Dwarf (DCV) Star",
            "White Dwarf (DQ) Star",
            "Wolf-Rayet C Star",
            "Wolf-Rayet N Star",
            "Wolf-Rayet NC Star",
            "Wolf-Rayet O Star",
            "Wolf-Rayet Star",
            "Y (Brown dwarf) Star"
        ]
    }
    known_planet_landmarks_obj = {
        "Abandoned Base": [
            "Abandoned Base"
        ],
        "Aleoida": [
            "Aleoida Arcus",
            "Aleoida Coronamus",
            "Aleoida Gravis",
            "Aleoida Laminiae",
            "Aleoida Spica"
        ],
        "Amphora Plant": [
            "Amphora Plant"
        ],
        "Anemone": [
            "Blatteum Bioluminescent Anemone",
            "Croceum Anemone",
            "Luteolum Anemone",
            "Prasinum Bioluminescent Anemone",
            "Puniceum Anemone",
            "Roseum Anemone",
            "Roseum Bioluminescent Anemone",
            "Rubeum Bioluminescent Anemone",
            "Unknown"
        ],
        "Aster": [
            "Cereum Aster Pod",
            "Cereum Aster Tree",
            "Lindigoticum Aster Pod",
            "Prasinum Aster Tree",
            "Rubellum Aster Tree"
        ],
        "Bacterium": [
            "Bacterium Acies",
            "Bacterium Alcyoneum",
            "Bacterium Aurasus",
            "Bacterium Bullaris",
            "Bacterium Cerbrus",
            "Bacterium Informem",
            "Bacterium Nebulus",
            "Bacterium Omentum",
            "Bacterium Scopulum",
            "Bacterium Tela",
            "Bacterium Verrata",
            "Bacterium Vesicula",
            "Bacterium Volu"
        ],
        "Bark Mounds": [
            "Bark Mounds"
        ],
        "Brain Tree": [
            "Aureum Brain Tree",
            "Gypseeum Brain Tree",
            "Lindigoticum Brain Tree",
            "Lividum Brain Tree",
            "Ostrinum Brain Tree",
            "Puniceum Brain Tree",
            "Roseum Brain Tree",
            "Viride Brain Tree"
        ],
        "Cactoida": [
            "Cactoida Cortexum",
            "Cactoida Lapis",
            "Cactoida Peperatis",
            "Cactoida Pullulanta",
            "Cactoida Vermis"
        ],
        "Calcite Plates": [
            "Lindigoticum Calcite Plates",
            "Luteolum Calcite Plates",
            "Rutulum Calcite Plates",
            "Viride Calcite Plates"
        ],
        "Chalice Pod": [
            "Albidum Chalice Pod",
            "Caeruleum Chalice Pod",
            "Ostrinum Chalice Pod",
            "Rubellum Chalice Pod",
            "Viride Chalice Pod"
        ],
        "Clypeus": [
            "Clypeus Lacrimam",
            "Clypeus Margaritus",
            "Clypeus Speculumi"
        ],
        "Collared Pod": [
            "Blatteum Collared Pod",
            "Lividum Collared Pod",
            "Rubicundum Collared Pod"
        ],
        "Concha": [
            "Concha Aureolas",
            "Concha Biconcavis",
            "Concha Labiata",
            "Concha Renibus"
        ],
        "Coral Tree": [
            "Coral Tree"
        ],
        "Crashed Ship": [
            "Crashed Ship"
        ],
        "Crystalline Shard": [
            "Crystalline Shards"
        ],
        "E-Type Anomaly": [
            "E02-Type Anomaly",
            "E03-Type Anomaly",
            "E04-Type Anomaly"
        ],
        "Electricae": [
            "Electricae Pluma",
            "Electricae Radialem"
        ],
        "Fonticulua": [
            "Fonticulua Campestris",
            "Fonticulua Digitos",
            "Fonticulua Fluctus",
            "Fonticulua Lapida",
            "Fonticulua Segmentatus",
            "Fonticulua Upupam"
        ],
        "Frutexa": [
            "Frutexa Acus",
            "Frutexa Collum",
            "Frutexa Fera",
            "Frutexa Flabellum",
            "Frutexa Flammasis",
            "Frutexa Metallicum",
            "Frutexa Sponsae"
        ],
        "Fumarole": [
            "Ammonia Ice Fumarole",
            "Carbon Dioxide Fumarole",
            "Carbon Dioxide Ice Fumarole",
            "Methane Ice Fumarole",
            "Nitrogen Ice Fumarole",
            "Silicate Vapour Fumarole",
            "Silicate Vapour Ice Fumarole",
            "Sulphur Dioxide Fumarole",
            "Sulphur Dioxide Ice Fumarole",
            "Water Fumarole",
            "Water Ice Fumarole"
        ],
        "Fumerola": [
            "Fumerola Aquatis",
            "Fumerola Carbosis",
            "Fumerola Extremus",
            "Fumerola Nitris"
        ],
        "Fungoida": [
            "Fungoida Bullarum",
            "Fungoida Gelata",
            "Fungoida Setisis",
            "Fungoida Stabitis"
        ],
        "Gas Vent": [
            "Carbon Dioxide Gas Vent",
            "Silicate Vapour Gas Vent",
            "Sulphur Dioxide Gas Vent",
            "Water Gas Vent"
        ],
        "Geyser": [
            "Ammonia Ice Geyser",
            "Carbon Dioxide Ice Geyser",
            "Methane Ice Geyser",
            "Nitrogen Ice Geyser",
            "Water Geyser",
            "Water Ice Geyser"
        ],
        "Guardian": [
            "Guardian Beacon",
            "Guardian Codex",
            "Guardian Data Terminal",
            "Guardian Pylon",
            "Guardian Relic Tower",
            "Guardian Sentinel"
        ],
        "Guardian Ruin": [
            "Unknown"
        ],
        "Guardian Structure": [
            "Bear",
            "Bowl",
            "Crossroads",
            "Fistbump",
            "Hammerbot",
            "Lacrosse",
            "Robolobster",
            "Squid",
            "Turtle",
            "Unknown"
        ],
        "Gyre": [
            "Aurarium Gyre Pod",
            "Aurarium Gyre Tree",
            "Roseum Gyre Pod",
            "Viride Gyre Tree"
        ],
        "Ice Crystals": [
            "Albidum Ice Crystals",
            "Flavum Ice Crystals",
            "Lindigoticum Ice Crystals",
            "Prasinum Ice Crystals",
            "Purpureum Ice Crystals",
            "Roseum Ice Crystals",
            "Rubeum Ice Crystals"
        ],
        "K-Type Anomaly": [
            "K01-Type Anomaly",
            "K03-Type Anomaly",
            "K04-Type Anomaly",
            "K05-Type Anomaly",
            "K06-Type Anomaly",
            "K08-Type Anomaly",
            "K09-Type Anomaly",
            "K10-Type Anomaly",
            "K12-Type Anomaly",
            "K13-Type Anomaly"
        ],
        "L-Type Anomaly": [
            "L01-Type Anomaly",
            "L04-Type Anomaly",
            "L06-Type Anomaly",
            "L07-Type Anomaly",
            "L08-Type Anomaly",
            "L09-Type Anomaly"
        ],
        "Lagrange Cloud": [
            "Caeruleum Lagrange Cloud",
            "Croceum Lagrange Cloud",
            "Luteolum Lagrange Cloud",
            "Proto-Lagrange Cloud",
            "Roseum Lagrange Cloud",
            "Rubicundum Lagrange Cloud",
            "Viride Lagrange Cloud"
        ],
        "Lava Spout": [
            "Iron Magma Lava Spout",
            "Silicate Magma Lava Spout"
        ],
        "Metallic Crystals": [
            "Flavum Metallic Crystals",
            "Prasinum Metallic Crystals",
            "Purpureum Metallic Crystals",
            "Rubeum Metallic Crystals"
        ],
        "Mineral Spheres": [
            "Lattice Mineral Spheres",
            "Solid Mineral Spheres"
        ],
        "Mollusc": [
            "Albens Bell Mollusc",
            "Albulum Gourd Mollusc",
            "Blatteum Bell Mollusc",
            "Caeruleum Gourd Mollusc",
            "Caeruleum Torus Mollusc",
            "Cereum Bullet Mollusc",
            "Cobalteum Globe Mollusc",
            "Croceum Globe Mollusc",
            "Croceum Gourd Mollusc",
            "Flavum Bullet Mollusc",
            "Flavum Torus Mollusc",
            "Gypseeum Bell Mollusc",
            "Lindigoticum Bell Mollusc",
            "Lindigoticum Bulb Mollusc",
            "Lindigoticum Capsule Mollusc",
            "Lindigoticum Parasol Mollusc",
            "Lindigoticum Reel Mollusc",
            "Lindigoticum Umbrella Mollusc",
            "Lividum Bullet Mollusc",
            "Luteolum Bell Mollusc",
            "Luteolum Bulb Mollusc",
            "Luteolum Capsule Mollusc",
            "Luteolum Parasol Mollusc",
            "Luteolum Reel Mollusc",
            "Luteolum Umbrella Mollusc",
            "Niveum Globe Mollusc",
            "Ostrinum Globe Mollusc",
            "Phoeniceum Gourd Mollusc",
            "Prasinum Globe Mollusc",
            "Purpureum Gourd Mollusc",
            "Roseum Globe Mollusc",
            "Rubeum Bullet Mollusc",
            "Rufum Gourd Mollusc",
            "Rutulum Globe Mollusc",
            "Viride Bulb Mollusc",
            "Viride Bullet Mollusc",
            "Viride Capsule Mollusc",
            "Viride Parasol Mollusc",
            "Viride Reel Mollusc",
            "Viride Umbrella Mollusc"
        ],
        "Osseus": [
            "Osseus Cornibus",
            "Osseus Discus",
            "Osseus Fractus",
            "Osseus Pellebantus",
            "Osseus Pumice",
            "Osseus Spiralis"
        ],
        "P-Type Anomaly": [
            "P01-Type Anomaly",
            "P02-Type Anomaly",
            "P03-Type Anomaly",
            "P04-Type Anomaly",
            "P05-Type Anomaly",
            "P07-Type Anomaly",
            "P09-Type Anomaly",
            "P11-Type Anomaly",
            "P12-Type Anomaly",
            "P13-Type Anomaly",
            "P14-Type Anomaly",
            "P15-Type Anomaly"
        ],
        "Peduncle": [
            "Albidum Peduncle Tree",
            "Caeruleum Peduncle Pod",
            "Caeruleum Peduncle Tree",
            "Candidum Peduncle Pod",
            "Gypseeum Peduncle Pod",
            "Ostrinum Peduncle Tree",
            "Purpureum Peduncle Pod",
            "Rubellum Peduncle Tree",
            "Rufum Peduncle Pod",
            "Viride Peduncle Tree"
        ],
        "Planets": [
            "Green Class I Gas Giant",
            "Green Class II Gas Giant",
            "Green Class III Gas Giant",
            "Green Class IV Gas Giant",
            "Green Gas Giant with Ammonia Life",
            "Green Water Giant"
        ],
        "Q-Type Anomaly": [
            "Q01-Type Anomaly",
            "Q02-Type Anomaly",
            "Q06-Type Anomaly",
            "Q08-Type Anomaly",
            "Q09-Type Anomaly"
        ],
        "Quadripartite": [
            "Albidum Quadripartite Pod",
            "Blatteum Quadripartite Pod",
            "Caeruleum Quadripartite Pod",
            "Viride Quadripartite Pod"
        ],
        "Recepta": [
            "Recepta Conditivus",
            "Recepta Deltahedronix",
            "Recepta Umbrux"
        ],
        "Rhizome": [
            "Candidum Rhizome Pod",
            "Cobalteum Rhizome Pod",
            "Gypseeum Rhizome Pod",
            "Purpureum Rhizome Pod",
            "Rubeum Rhizome Pod"
        ],
        "Shards": [
            "Crystalline Shards"
        ],
        "Silicate Crystals": [
            "Albidum Silicate Crystals",
            "Flavum Silicate Crystals",
            "Lindigoticum Silicate Crystals",
            "Prasinum Silicate Crystals",
            "Purpureum Silicate Crystals",
            "Roseum Silicate Crystals",
            "Rubeum Silicate Crystals"
        ],
        "Stolon": [
            "Stolon Pod"
        ],
        "Storm Cloud": [
            "Croceum Lagrange Storm Cloud",
            "Luteolum Lagrange Storm Cloud",
            "Roseum Lagrange Storm Cloud",
            "Rubicundum Lagrange Storm Cloud",
            "Viride Lagrange Storm Cloud"
        ],
        "Stratum": [
            "Stratum Araneamus",
            "Stratum Cucumisis",
            "Stratum Excutitus",
            "Stratum Frigus",
            "Stratum Laminamus",
            "Stratum Limaxus",
            "Stratum Paleas",
            "Stratum Tectonicas"
        ],
        "Surface Station": [
            "Crater Outpost",
            "Crater Port",
            "Installation",
            "Settlement",
            "Surface Station"
        ],
        "T-Type Anomaly": [
            "T01-Type Anomaly",
            "T03-Type Anomaly",
            "T04-Type Anomaly"
        ],
        "Thargoid": [
            "Common Thargoid Barnacle",
            "Coral Root",
            "Large Thargoid Barnacle",
            "Major Thargoid Spire",
            "Minor Thargoid Spire",
            "Primary Thargoid Spire",
            "Thargoid Banshees",
            "Thargoid Barnacle Barbs",
            "Thargoid Caustic Generator",
            "Thargoid Device",
            "Thargoid Interceptor Shipwreck",
            "Thargoid Mega Barnacles",
            "Thargoid Pod",
            "Thargoid Scavengers",
            "Thargoid Scout Shipwreck",
            "Thargoid Spire",
            "Thargoid Spires",
            "Thargoid Uplink Device"
        ],
        "Thargoid Barnacle": [
            "Unknown"
        ],
        "Thargoid Structure": [
            "Thargoid Structure"
        ],
        "Toughened Spear Roots": [
            "Toughened Spear Roots"
        ],
        "Tourist Beacon": [
            "Tourist Beacon"
        ],
        "Tubers": [
            "Albidum Sinuous Tubers",
            "Blatteum Sinuous Tubers",
            "Caeruleum Sinuous Tubers",
            "Lindigoticum Sinuous Tubers",
            "Prasinum Sinuous Tubers",
            "Roseum Sinuous Tubers",
            "Roseus Sinuous Tubers",
            "Violaceum Sinuous Tubers",
            "Viride Sinuous Tubers"
        ],
        "Tubus": [
            "Tubus Cavas",
            "Tubus Compagibus",
            "Tubus Conifer",
            "Tubus Rosarium",
            "Tubus Sororibus"
        ],
        "Tussock": [
            "Tussock Albata",
            "Tussock Capillum",
            "Tussock Caputus",
            "Tussock Catena",
            "Tussock Cultro",
            "Tussock Divisa",
            "Tussock Ignis",
            "Tussock Pennata",
            "Tussock Pennatis",
            "Tussock Propagito",
            "Tussock Serrati",
            "Tussock Stigmasis",
            "Tussock Triticum",
            "Tussock Ventusa",
            "Tussock Virgam"
        ],
        "Void": [
            "Caeruleum Octahedral Pod",
            "Chryseum Void Heart"
        ],
        "Wrecked Ship": [
            "Wrecked Ship"
        ]
    }

    known_subtypes = [item for sublist in known_planet_types_obj.values() for item in sublist]
    known_landmarks = [item for sublist in known_planet_landmarks_obj.values() for item in sublist]

    filters = {
        "distance": {
            "min": "0",
            "max": str(obj.get("distance", 50000))
        }
    }

    # Add optional filters if they exist
    if "subtype" in obj and obj["subtype"]:
        for subtype in obj["subtype"]:
            if subtype not in known_subtypes:
                raise Exception(
                    f"Invalid celestial body subtype: {subtype}. {educated_guesses_message(subtype, known_subtypes)}")
        filters["subtype"] = {"value": obj["subtype"]}

    if "landmark_subtype" in obj and obj["landmark_subtype"]:
        for landmark_subtype in obj["landmark_subtype"]:
            if landmark_subtype not in known_landmarks:
                raise Exception(
                    f"Invalid Landmark Subtype: {landmark_subtype}. {educated_guesses_message(landmark_subtype, known_landmarks)}")
        filters["landmarks"] = [{"subtype": obj["landmark_subtype"]}]

    if "name" in obj and obj["name"]:
        filters["name"] = {
            "value": obj["name"]
        }

    # Build the request body
    request_body = {
        "filters": filters,
        "sort": [
            {
                "distance": {
                    "direction": "asc"
                }
            }
        ],
        "size": 3,
        "page": 0,
        "reference_system": obj.get("reference_system", "Sol")
    }

    return request_body


# Function to filter and format the system response
def filter_body_response(request, response):
    filtered_results = []

    # Check which filters are in the request and adjust the response accordingly
    request_filters = request.get("filters", {})

    for body in response.get("results", []):
        filtered_body = {}

        # if "name" in system and system["name"]:
        filtered_body["name"] = body.get("name")
        filtered_body["subtype"] = body.get("subtype")
        filtered_body["system_name"] = body.get("name")
        # landmark_subtype
        if "landmark_subtype" in request_filters:
            if "landmark_subtype" in body and body["landmarks"]:
                filtered_landmarks = [
                    {
                        "latitude": landmark["latitude"],
                        "longitude": landmark["longitude"],
                        "subtype": landmark["subtype"],
                        "type": landmark["type"],
                        "variant": landmark["variant"]
                    }
                    for landmark in body.get("landmarks", [])
                    if landmark["subtype"] in request_filters["landmark_subtype"]
                ]

                filtered_body["landmarks"] = filtered_landmarks

        # Add filtered system to the list
        filtered_results.append(filtered_body)

    # Construct and return the filtered response
    return {
        "amount_total": response["count"],
        "amount_displayed": min(response["count"], response["size"]),
        "results": filtered_results,
    }


# System finder function that sends the request to the Spansh API
def body_finder(obj):
    # Build the request body
    request_body = prepare_body_request(obj)

    url = "https://spansh.co.uk/api/bodies/search"

    try:
        response = requests.post(url, json=request_body)
        response.raise_for_status()

        data = response.json()
        # Filter the response
        filtered_data = filter_body_response(request_body, data)

        return f'Here is a list of celestial bodies: {json.dumps(filtered_data)}'

    except Exception as e:
        log('error', f"Error: {e}")
        return 'An error occurred. The system finder seems to be currently unavailable.'


def register_actions(actionManager: ActionManager, eventManager: EventManager, llmClient: openai.OpenAI,
                     llmModelName: str, visionClient: Optional[openai.OpenAI], visionModelName: Optional[str],
                     statusParser: StatusParser, edKeys: EDKeys):
    global event_manager, vision_client, llm_client, llm_model_name, vision_model_name, status_parser, keys
    keys = edKeys
    event_manager = eventManager
    llm_client = llmClient
    llm_model_name = llmModelName
    vision_client = visionClient
    vision_model_name = visionModelName
    status_parser = statusParser

    setGameWindowActive()

    # Register actions - General Ship Actions
    actionManager.registerAction('fire', "start firing primary weapons", {
        "type": "object",
        "properties": {}
    }, fire_primary_weapon, 'ship')

    actionManager.registerAction('holdFire', "stop firing primary weapons", {
        "type": "object",
        "properties": {}
    }, hold_fire_primary_weapon, 'ship')

    actionManager.registerAction('fireSecondary', "start secondary primary weapons", {
        "type": "object",
        "properties": {}
    }, fire_secondary_weapon, 'ship')

    actionManager.registerAction('holdFireSecondary', "stop secondary primary weapons", {
        "type": "object",
        "properties": {}
    }, hold_fire_secondary_weapon, 'ship')

    actionManager.registerAction('setSpeedZero', "Set speed to 0%", {
        "type": "object",
        "properties": {}
    }, set_speed_zero, 'ship')

    actionManager.registerAction('setSpeed50', "Set speed to 50%", {
        "type": "object",
        "properties": {}
    }, set_speed_50, 'ship')

    actionManager.registerAction('setSpeed100', "Set speed to 100%", {
        "type": "object",
        "properties": {}
    }, set_speed_100, 'ship')

    actionManager.registerAction('deployHeatSink', "Deploy heat sink", {
        "type": "object",
        "properties": {}
    }, deploy_heat_sink, 'ship')

    actionManager.registerAction('deployHardpointToggle', "Deploy or retract hardpoints", {
        "type": "object",
        "properties": {}
    }, deploy_hardpoint_toggle, 'ship')

    actionManager.registerAction('increaseEnginesPower', "Increase engine power, can be done multiple times", {
        "type": "object",
        "properties": {
            "pips": {
                "type": "integer",
                "description": "Amount of pips to increase engine power, default: 1, maximum: 4",
            },
        },
        "required": ["pips"]
    }, increase_engines_power, 'ship')

    actionManager.registerAction('increaseWeaponsPower', "Increase weapon power, can be done multiple times", {
        "type": "object",
        "properties": {
            "pips": {
                "type": "integer",
                "description": "Amount of pips to increase weapon power, default: 1, maximum: 4",
            },
        },
        "required": ["pips"]
    }, increase_weapons_power, 'ship')

    actionManager.registerAction('increaseSystemsPower', "Increase systems power, can be done multiple times", {
        "type": "object",
        "properties": {
            "pips": {
                "type": "integer",
                "description": "Amount of pips to increase systems power, default: 1, maximum: 4",
            },
        },
        "required": ["pips"]
    }, increase_systems_power, 'ship')

    actionManager.registerAction('galaxyMapOpen', "Open galaxy map. Focus on a system or start a navigation route", {
        "type": "object",
        "properties": {
            "system_name": {
                "type": "string",
                "description": "System to display or plot to",
            },
            "start_navigation": {
                "type": "boolean",
                "description": "Start navigation route to the system",
            }
        },
    }, galaxy_map_open, 'ship')

    actionManager.registerAction('galaxyMapClose', "Close galaxy map", {
        "type": "object",
        "properties": {},
    }, galaxy_map_close, 'ship')

    actionManager.registerAction('systemMapOpen', "Open or close system map", {
        "type": "object",
        "properties": {}
    }, system_map_open, 'ship')

    actionManager.registerAction('cycleNextTarget', "Cycle to next target", {
        "type": "object",
        "properties": {}
    }, cycle_next_target, 'ship')

    actionManager.registerAction('cycleFireGroupNext', "Cycle to next fire group", {
        "type": "object",
        "properties": {}
    }, cycle_fire_group_next, 'ship')

    actionManager.registerAction('shipSpotLightToggle', "Toggle ship spotlight", {
        "type": "object",
        "properties": {}
    }, ship_spot_light_toggle, 'ship')

    actionManager.registerAction('fireChaffLauncher', "Fire chaff launcher", {
        "type": "object",
        "properties": {}
    }, fire_chaff_launcher, 'ship')

    actionManager.registerAction('nightVisionToggle', "Toggle night vision", {
        "type": "object",
        "properties": {}
    }, night_vision_toggle, 'ship')

    actionManager.registerAction('selectHighestThreat', "Target lock highest threat", {
        "type": "object",
        "properties": {}
    }, select_highest_threat, 'ship')

    actionManager.registerAction('chargeECM', "Charge ECM", {
        "type": "object",
        "properties": {}
    }, charge_ecm, 'ship')

    # Register actions - NPC Crew Order Actions
    actionManager.registerAction('npcOrder', "Order NPC crew ship", {
        "type": "object",
        "properties": {
            "orders": {
                "type": "array",
                "description": "Orders to give to the NPC pilot",
                "items": {
                    "type": "string",
                    "enum": [
                        "OrderDefensiveBehaviour",
                        "OrderAggressiveBehaviour",
                        "OrderFocusTarget",
                        "OrderHoldFire",
                        "OrderHoldPosition",
                        "OrderFollow",
                    ]
                }
            }
        }
    }, npc_order, 'ship')

    # Register actions - Mainship Actions
    actionManager.registerAction('hyperSuperCombination',
                                 "initiate FSD Jump, required to jump to the next system or to enter supercruise", {
                                     "type": "object",
                                     "properties": {}
                                 }, hyper_super_combination, 'mainship')

    actionManager.registerAction('toggleCargoScoop', "Toggles cargo scoop", {
        "type": "object",
        "properties": {}
    }, toggle_cargo_scoop, 'mainship')

    actionManager.registerAction('ejectAllCargo', "Eject all cargo", {
        "type": "object",
        "properties": {}
    }, eject_all_cargo, 'mainship')

    actionManager.registerAction('landingGearToggle', "Toggle landing gear", {
        "type": "object",
        "properties": {}
    }, landing_gear_toggle, 'mainship')

    actionManager.registerAction('useShieldCell', "Use shield cell", {
        "type": "object",
        "properties": {}
    }, use_shield_cell, 'mainship')

    actionManager.registerAction('requestDocking', "Request docking.", {
        "type": "object",
        "properties": {}
    }, request_docking, 'mainship')

    actionManager.registerAction('undockShip', "", {
        "type": "object",
        "properties": {}
    }, undock, 'mainship')

    # Register actions - Ship Launched Fighter Actions
    actionManager.registerAction('OrderRequestDock', "Request docking for Ship Launched Fighter", {
        "type": "object",
        "properties": {}
    }, order_request_dock, 'fighter')

    # Register actions - SRV Actions (Horizons)
    actionManager.registerAction('toggleDriveAssist', "Toggle drive assist", {
        "type": "object",
        "properties": {}
    }, toggle_drive_assist, 'buggy')

    actionManager.registerAction('primaryFireBuggy', "Primary fire", {
        "type": "object",
        "properties": {}
    }, buggy_primary_fire, 'buggy')

    actionManager.registerAction('secondaryFireBuggy', "Secondary fire", {
        "type": "object",
        "properties": {}
    }, buggy_secondary_fire, 'buggy')

    actionManager.registerAction('autoBreak', "Toggle auto-brake", {
        "type": "object",
        "properties": {}
    }, auto_break_buggy, 'buggy')

    actionManager.registerAction('headlights', "Toggle headlights", {
        "type": "object",
        "properties": {}
    }, headlights_buggy, 'buggy')

    actionManager.registerAction('nightVisionToggleBuggy', "Toggle night vision", {
        "type": "object",
        "properties": {}
    }, night_vision_toggle, 'buggy')

    actionManager.registerAction('toggleTurret', "Toggle turret mode", {
        "type": "object",
        "properties": {}
    }, toggle_buggy_turret, 'buggy')

    actionManager.registerAction('selectTargetBuggy', "Select target", {
        "type": "object",
        "properties": {}
    }, select_target_buggy, 'buggy')

    actionManager.registerAction('increaseEnginesPowerBuggy', "Increase engines power, can be done multiple times", {
        "type": "object",
        "properties": {
            "pips": {
                "type": "integer",
                "description": "Amount of pips to increase engines power, default: 1, maximum: 4",
            },
        },
        "required": ["pips"]
    }, increase_engines_power_buggy, 'buggy')

    actionManager.registerAction('increaseWeaponsPowerBuggy', "Increase weapons power, can be done multiple times", {
        "type": "object",
        "properties": {
            "pips": {
                "type": "integer",
                "description": "Amount of pips to increase weapons power, default: 1, maximum: 4",
            },
        },
        "required": ["pips"]
    }, increase_weapons_power_buggy, 'buggy')

    actionManager.registerAction('increaseSystemsPowerBuggy', "Increase systems power, can be done multiple times", {
        "type": "object",
        "properties": {
            "pips": {
                "type": "integer",
                "description": "Amount of pips to increase systems power, default: 1, maximum: 4",
            },
        },
        "required": ["pips"]
    }, increase_systems_power_buggy, 'buggy')

    actionManager.registerAction('resetPowerDistributionBuggy', "Reset power distribution", {
        "type": "object",
        "properties": {}
    }, reset_power_distribution_buggy, 'buggy')

    actionManager.registerAction('toggleCargoScoopBuggy', "Toggle cargo scoop", {
        "type": "object",
        "properties": {}
    }, toggle_cargo_scoop_buggy, 'buggy')

    actionManager.registerAction('ejectAllCargoBuggy', "Eject all cargo", {
        "type": "object",
        "properties": {}
    }, eject_all_cargo_buggy, 'buggy')

    actionManager.registerAction('recallDismissShipBuggy', "Recall or dismiss ship", {
        "type": "object",
        "properties": {}
    }, recall_dismiss_ship_buggy, 'buggy')

    actionManager.registerAction('galaxyMapOpenBuggy', "Open/close galaxy map", {
        "type": "object",
        "properties": {}
    }, galaxy_map_open_buggy, 'buggy')

    actionManager.registerAction('systemMapOpenBuggy', "Open/close system map", {
        "type": "object",
        "properties": {}
    }, system_map_open_buggy, 'buggy')

    # Register actions - On-Foot Actions
    actionManager.registerAction('primaryInteractHumanoid', "Primary interact action", {
        "type": "object",
        "properties": {}
    }, primary_interact_humanoid, 'humanoid')

    actionManager.registerAction('secondaryInteractHumanoid', "Secondary interact action", {
        "type": "object",
        "properties": {}
    }, secondary_interact_humanoid, 'humanoid')

    actionManager.registerAction('equipGearHumanoid', "Equip or hide a piece of gear", {
        "type": "object",
        "properties": {
        "equipment": {
            "type": "string",
            "description": "Gear to equip",
            "enum": [
                "HumanoidSelectPrimaryWeaponButton",
                "HumanoidSelectSecondaryWeaponButton",
                "HumanoidSelectUtilityWeaponButton",
                "HumanoidSwitchToRechargeTool",
                "HumanoidSwitchToCompAnalyser",
                "HumanoidSwitchToSuitTool",
                "HumanoidHideWeaponButton",
                "HumanoidSelectFragGrenade",
                "HumanoidSelectEMPGrenade",
                "HumanoidSelectShieldGrenade"
            ]
        }
    },
    "required": ["equipment"]
    }, equip_humanoid, 'humanoid')

    actionManager.registerAction('toggleFlashlightHumanoid', "Toggle flashlight", {
        "type": "object",
        "properties": {}
    }, toggle_flashlight_humanoid, 'humanoid')

    actionManager.registerAction('toggleNightVisionHumanoid', "Toggle night vision", {
        "type": "object",
        "properties": {}
    }, toggle_night_vision_humanoid, 'humanoid')

    actionManager.registerAction('toggleShieldsHumanoid', "Toggle shields", {
        "type": "object",
        "properties": {}
    }, toggle_shields_humanoid, 'humanoid')

    actionManager.registerAction('clearAuthorityLevelHumanoid', "Clear authority level", {
        "type": "object",
        "properties": {}
    }, clear_authority_level_humanoid, 'humanoid')

    actionManager.registerAction('healthPackHumanoid', "Use health pack", {
        "type": "object",
        "properties": {}
    }, health_pack_humanoid, 'humanoid')

    actionManager.registerAction('batteryHumanoid', "Use battery", {
        "type": "object",
        "properties": {}
    }, battery_humanoid, 'humanoid')

    actionManager.registerAction('galaxyMapOpenHumanoid', "Open Galaxy Map", {
        "type": "object",
        "properties": {}
    }, galaxy_map_open_humanoid, 'humanoid')

    actionManager.registerAction('systemMapOpenHumanoid', "Open System Map", {
        "type": "object",
        "properties": {}
    }, system_map_open_humanoid, 'humanoid')

    actionManager.registerAction('recallDismissShipHumanoid', "Recall or dismiss ship", {
        "type": "object",
        "properties": {}
    }, recall_dismiss_ship_humanoid, 'humanoid')

    # Register actions - Web Tools
    actionManager.registerAction(
        'getGalnetNews',
        "Retrieve current interstellar news from Galnet",
        {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Inquiry you are trying to answer. Example: 'What happened to the thargoids recently?'"
                },
            },
            "required": ["query"]
        },
        get_galnet_news,
        'global'
    )

    # if ARC:
    actionManager.registerAction(
        'trade_plotter',
        "Retrieve a trade route from the trade plotter. Ask for unknown values and make sure they are known.",
        {
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
        },
        trade_planner,
        'global'
    )

    # Register AI action for system finder
    actionManager.registerAction(
        'system_finder',
        "Find a star system based on allegiance, government, state, power, primary economy, and more. Ask for unknown values and ensure they are filled out.",
        {
            "type": "object",
            "properties": {
                "reference_system": {
                    "type": "string",
                    "description": "Name of the current system. Example: 'Sol'"
                },
                "name": {
                    "type": "string",
                    "description": "Required string in system name"
                },
                "distance": {
                    "type": "number",
                    "description": "The maximum distance to search",
                    "example": 50000.0
                },
                "allegiance": {
                    "type": "array",
                    "description": "System allegiance to filter by",
                    "items": {
                        "type": "string",
                        "enum": [
                            "Alliance",
                            "Empire",
                            "Federation",
                            "Guardian",
                            "Independent",
                            "Pilots Federation",
                            "Player Pilots",
                            "Thargoid"
                        ]
                    }
                },
                "state": {
                    "type": "array",
                    "description": "System state to filter by",
                    "items": {
                        "type": "string",
                    }
                },
                "government": {
                    "type": "array",
                    "description": "System government type to filter by",
                    "items": {
                        "type": "string",
                    }
                },
                "power": {
                    "type": "array",
                    "description": "Powers controlling or exploiting the system",
                    "items": {
                        "type": "string",
                    }
                },
                "primary_economy": {
                    "type": "array",
                    "description": "Primary economy type of the system",
                    "items": {
                        "type": "string",
                    }
                },
                "security": {
                    "type": "array",
                    "description": "Security level of the system",
                    "items": {
                        "type": "string",
                    }
                },
                "thargoid_war_state": {
                    "type": "array",
                    "description": "System's state in the Thargoid War",
                    "items": {
                        "type": "string",
                    }
                },
                "population": {
                    "type": "object",
                    "description": "Population comparison and value",
                    "properties": {
                        "comparison": {
                            "type": "string",
                            "description": "Comparison type",
                            "enum": ["<", ">"]
                        },
                        "value": {
                            "type": "number",
                            "description": "Size to compare with",
                        }
                    }
                }
            },
            "required": ["reference_system"]
        },
        system_finder,
        'global'
    )
    actionManager.registerAction(
        'station_finder',
        "Find a station to buy or sell a commodity, to buy an outfitting module, with a Material Trader or Technology Broker. Ask for unknown values and make sure they are known.",
        {
            "type": "object",
            "properties": {
                "reference_system": {
                    "type": "string",
                    "description": "Name of the current system. Example: 'Sol'"
                },
                "name": {
                    "type": "string",
                    "description": "Required string in station name"
                },
                "has_large_pad": {
                    "type": "boolean",
                    "description": "If the ship requires a large landing pad",
                    "example": False
                },
                "distance": {
                    "type": "number",
                    "description": "The maximum distance to search",
                    "example": 50000.0
                },
                "material_trader": {
                    "type": "array",
                    "description": "Material traders to find",
                    "items": {
                        "type": "string",
                        "enum": [
                            "Encoded",
                            "Manufactured",
                            "Raw"
                        ]
                    },
                    "minItems": 1,
                },
                "technology_broker": {
                    "type": "array",
                    "description": "Technology brokers to find",
                    "items": {
                        "type": "string",
                        "enum": [
                            "Guardian",
                            "Human"
                        ]
                    },
                    "minItems": 1,
                },
                "modules": {
                    "type": "array",
                    "description": "Outfitting modules to buy",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Name of the module.",
                                "example": "Frame Shift Drive"
                            },
                            "class": {
                                "type": "array",
                                "description": "Classes of the modules.",
                                "items": {
                                    "type": "string",
                                    "enum": [
                                        "0", "1", "2", "3", "4", "5", "6", "7", "8"
                                    ],
                                },
                                "minItems": 1,
                            },
                            "rating": {
                                "type": "array",
                                "description": "Ratings of the modules.",
                                "items": {
                                    "type": "string",
                                    "enum": [
                                        "A", "B", "C", "D", "E", "F", "G", "H", "I"
                                    ]
                                },
                                "example": ["A", "B", "C", "D"],
                                "minItems": 1
                            }
                        },
                        "required": ["name"]
                    },
                    "minItems": 1,
                },
                "market": {
                    "type": "array",
                    "description": "Market commodities to buy and sell",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Name of the commodity.",
                                "example": "Tritium"
                            },
                            "amount": {
                                "type": "integer",
                                "description": "Tons of cargo to sell or buy. Use maximum cargo capacity."
                            },
                            "transaction": {
                                "type": "string",
                                "description": "Type of transaction.",
                                "enum": [
                                    "Buy", "Sell"
                                ],
                            }
                        },
                        "required": ["name", "amount", "transaction"]
                    },
                    "minItems": 1,
                },
                "ships": {
                    "type": "array",
                    "description": "Ships to buy",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Name of ship",
                            }
                        },
                        "required": ["name"]
                    },
                    "minItems": 1,
                },
                "services": {
                    "type": "array",
                    "description": "Services to use",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Name services",
                                "enum": [
                                    "Black Market",
                                    "Interstellar Factors Contact"
                                ]
                            }
                        },
                        "required": ["name"]
                    },
                    "minItems": 1,
                }
            },
            "required": [
                "reference_system",
                "has_large_pad"
            ]
        },
        station_finder,
        'global'
    )
    actionManager.registerAction(
        'body_finder',
        "Find a planet or star of a certain type or with a landmark. Ask for unknown values and make sure they are known.",
        {
            "type": "object",
            "properties": {
                "reference_system": {
                    "type": "string",
                    "description": "Name of the current system. Example: 'Sol'"
                },
                "name": {
                    "type": "string",
                    "description": "Required string in station name"
                },
                "subtype": {
                    "type": "array",
                    "description": "Subtype of celestial body",
                    "items": {
                        "type": "string",
                    }
                },
                "landmark_subtype": {
                    "type": "array",
                    "description": "Landmark subtype on celestial body",
                    "items": {
                        "type": "string",
                    }
                },
                "distance": {
                    "type": "number",
                    "description": "Maximum distance to search",
                    "example": 50000.0
                },
            },
            "required": [
                "reference_system",
                "has_large_pad"
            ]
        },
        body_finder,
        'global'
    )

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
        }, get_visuals, 'global')


if __name__ == "__main__":
    req = prepare_station_request({'reference_system': 'Muang', 'has_large_pad': False,
                                   'market': [{'name': 'gold', 'amount': 10, 'transaction': 'Buy'}]})
    print(json.dumps(req))
