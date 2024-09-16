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
            f"Here is a list of similar and valid items: {guesses_str}?"
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
    log('Debug Station Finder Request', obj)
    filters = {
        "distance": {
            "min": "0",
            "max": "50"
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
        valid_market_filters = []
        for market_item in obj["market"]:
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
        filters["market"] = {"value": market_filters}
    if "modules" in obj:
        for module in obj["modules"]:
            if module["name"] not in known_modules:
                raise Exception(
                    f"Invalid module name: {module['name']}. {educated_guesses_message(module['name'], known_modules)}")
        filters["modules"] = {"value": obj["modules"]}
    if "ships" in obj:
        for ship in obj["ships"]:
            if ship["name"] not in known_ships:
                raise Exception(
                    f"Invalid ship name: {ship['name']}. {educated_guesses_message(ship['name'], known_ships)}")
        filters["ships"] = {"value": obj["ships"]}
    if "services" in obj:
        for service in obj["services"]:
            if service["name"] not in known_services:
                raise Exception(
                    f"Invalid service name: {service['name']}. {educated_guesses_message(service['name'], known_services)}")
        filters["services"] = {"value": obj["services"]}
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
def filter_station_response(response, request):
    # Extract requested commodities and modules
    commodities_requested = {item["name"] for item in request["filters"].get("market", {}).get("value", [])}
    modules_requested = {item["name"] for item in request["filters"].get("modules", {}).get("value", [])}
    ships_requested = {item["name"] for item in request["filters"].get("ships", {}).get("value", [])}
    services_requested = {item["name"] for item in request["filters"].get("services", {}).get("value", [])}

    for module_filter in request["filters"].get("modules", []):
        if isinstance(module_filter, dict) and "name" in module_filter:
            modules_requested.update(module_filter["name"])

    filtered_results = []

    for result in response["results"]:
        filtered_result = {
            "name": result["name"],
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

            filtered_result["modules"] = filtered_modules

        if "ships" in result:
            filtered_ships = []
            for ship in result["ships"]:
                for requested_ship in ships_requested:
                    if requested_ship.lower() in ship["name"].lower():
                        filtered_ships.append(ship)

            filtered_result["ships"] = filtered_ships

        if "services" in result:
            filtered_services = []
            for service in result["services"]:
                for requested_service in services_requested:
                    if requested_service.lower() in service["name"].lower():
                        filtered_services.append(service)

            filtered_result["services"] = filtered_services

        filtered_results.append(filtered_result)

    return {
        "amount_total": response["count"],
        "amount_displayed": response["size"],
        "results": filtered_results
    }


# find a station within 50ly with certaion material_trader, technology_broker, market, and modules info
def station_finder(obj):
    # Initialize the filters
    request_body = prepare_station_request(obj)

    url = "https://spansh.co.uk/api/stations/search"
    try:
        response = requests.post(url, json=request_body)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx and 5xx)

        data = response.json()

        filtered_data = filter_station_response(data, request_body)

        return f'Here is a list of stations: {json.dumps(filtered_data)}'
    except Exception as e:
        log('error', f"Error: {e}")
        return 'An error has occurred. The station finder seems currently not available.'


def register_actions(actionManager: ActionManager, eventManager: EventManager, llmClient: openai.OpenAI,
                     llmModelName: str, visionClient: Optional[openai.OpenAI], visionModelName: Optional[str]):
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

    actionManager.registerAction('trade_plotter',
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
                                 }, trade_planner)

    actionManager.registerAction('station_finder',
                                 "Find a station to buy or sell a commodity, to buy an outfitting module, with a Material Trader or Technology Broker. Ask for unknown values and make sure they are known.",
                                 {
                                     "type": "object",
                                     "properties": {
                                         "reference_system": {
                                             "type": "string",
                                             "description": "Name of the current system. Example: 'Sol'"
                                         },
                                         "has_large_pad": {
                                             "type": "boolean",
                                             "description": "If the ship requires a large landing pad",
                                             "example": True
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
                                             "example": ["Encoded", "Manufactured"]
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
                                             "example": ["Guardian"]
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
                                                             ]
                                                         },
                                                         "example": ["5"]
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
                                                         "example": ["A", "B", "C", "D"]
                                                     }
                                                 },
                                                 "required": ["name", "class", "rating"]
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
                                                         "example": "Sidewinder"
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
                                                         "example": "Sidewinder",
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
                                 station_finder
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
        }, get_visuals)
