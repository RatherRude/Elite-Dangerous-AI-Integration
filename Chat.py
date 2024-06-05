import base64
from threading import Thread
import kthread
import queue
import pyttsx3
from time import sleep

import argparse
import os
import numpy as np
import speech_recognition as sr
import whisper
import torch

from datetime import datetime, timedelta
from queue import Queue
from time import sleep
from sys import platform

import subprocess
import re
from pathlib import Path
from openai import OpenAI

import json

import pyautogui
import win32gui
import requests
from io import BytesIO

import getpass

import sys
from pathlib import Path

import AIActions

# Add the parent directory to sys.path
parent_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(parent_dir))

from Voice import *
from EDKeys import *
from EDJournal import *

client = None

aiModel = "gpt-4o"
backstory = """You will be addressed as 'Computer'. Acknowledge given orders. \
You possess extensive knowledge and can provide detailed and accurate information on a wide range of topics, \
including galactic navigation, ship status, the current system, and more. \
Do not inform about my ship status and my location unless it's relevant or requested by me. \
Guide and support me with witty and intelligent commentary. \
Provide clear mission briefings, sarcastic comments, and humorous observations. Answer within 3 sentences. \
Advance the narrative involving bounty hunting. \
I am a broke bounty hunter who can barely pay the fuel."""

conversationLength = 25
conversation = []

aiActions = AIActions.AIActions()

# Define functions for each action
def fire_primary_weapon(args):
    keys.send('PrimaryFire', state=1)
    return f"successfully opened fire with primary weapons."

def hold_fire_primary_weapon(args):
    keys.send('PrimaryFire', state=0)
    return f"successfully stopped firing with primary weapons."

def fire_secondary_weapon(args):
    keys.send('SecondaryFire', state=1)
    return f"successfully opened fire with secondary weapons."

def hold_fire_secondary_weapon(args):
    keys.send('SecondaryFire', state=0)
    return f"successfully stopped firing with secondary weapons."

def hyper_super_combination(args):
    keys.send('HyperSuperCombination')
    return f"Frame Shift Drive is charging for a jump"

def set_speed_zero(args):
    keys.send('SetSpeedZero')
    return f"Speed set to 0%"

def set_speed_50(args):
    keys.send('SetSpeed50')
    return f"Speed set to 50%"

def set_speed_100(args):
    keys.send('SetSpeed100')
    return f"Speed set to 100%"

def deploy_heat_sink(args):
    keys.send('DeployHeatSink')
    return f"Heat sink deployed"

def deploy_hardpoint_toggle(args):
    keys.send('DeployHardpointToggle')
    return f"Hardpoints deployed/retracted"

def increase_engines_power(args):
    keys.send('IncreaseEnginesPower', None, args['pips'])
    return f"Engine power increased"

def increase_weapons_power(args):
    keys.send('IncreaseWeaponsPower', None, args['pips'])
    return f"Weapon power increased"

def increase_systems_power(args):
    keys.send('IncreaseSystemsPower', None, args['pips'])
    return f"Systems power increased"

def galaxy_map_open(args):
    keys.send('GalaxyMapOpen')
    return f"Galaxy map opened/closed"

def system_map_open(args):
    keys.send('SystemMapOpen')
    return f"System map opened/closed"

def cycle_next_target(args):
    keys.send('CycleNextTarget')
    return f"Next target cycled"

def cycle_fire_group_next(args):
    keys.send('CycleFireGroupNext')
    return f"Fire group cycled"

def ship_spot_light_toggle(args):
    keys.send('ShipSpotLightToggle')
    return f"Ship spotlight toggled"

def eject_all_cargo(args):
    keys.send('EjectAllCargo')
    return f"All cargo ejected"

def landing_gear_toggle(args):
    keys.send('LandingGearToggle')
    return f"Landing gear toggled"

def use_shield_cell(args):
    keys.send('UseShieldCell')
    return f"Shield cell used"

def fire_chaff_launcher(args):
    keys.send('FireChaffLauncher')
    return f"Chaff launcher fired"

def night_vision_toggle(args):
    keys.send('NightVisionToggle')
    return f"Night vision toggled"

def recall_dismiss_ship(args):
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

aiActions.registerAction('hyperSuperCombination', "initiate FSD Jump, required to jump to the next system or to enter supercruise", {
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

# Function to prompt user for API key and Openrouter status
def prompt_for_config():
    commander_name = input("Enter your Commander name (without the CMDR): ").strip()
    openrouter = input("You use Openrouter instead of OpenAI (yes/no): ").strip().lower()

    # Validate Openrouter input
    while openrouter not in ['yes', 'no']:
        print("Invalid input. Please enter 'yes' or 'no'.")
        openrouter = input("Do you use Openrouter (yes/no): ").strip().lower()

    api_key = getpass.getpass("Enter your API key: ").strip()

    print("\nYour settings have been saved. Erase config.json to reenter information.\n")

    return api_key, openrouter == 'yes', commander_name

# Function to load configuration from file if exists, otherwise prompt user
def load_or_prompt_config():
    config_file = Path("config.json")
    if config_file.exists():
        with open(config_file, 'r') as f:
            config = json.load(f)
            api_key = config.get('api_key')
            openrouter = config.get('openrouter', False)
            commander_name = config.get('commander_name')
    else:
        api_key, openrouter, commander_name = prompt_for_config()
        with open(config_file, 'w') as f:
            json.dump({'api_key': api_key, 'openrouter': openrouter, 'commander_name': commander_name}, f)

    return api_key, openrouter, commander_name

handle = win32gui.FindWindow(0, "Elite - Dangerous (CLIENT)")
def screenshot():
    global handle
    if handle:
        win32gui.SetForegroundWindow(handle)
        x, y, x1, y1 = win32gui.GetClientRect(handle)
        x, y = win32gui.ClientToScreen(handle, (x, y))
        x1, y1 = win32gui.ClientToScreen(handle, (x1, y1))
        width = x1 - x
        height = y1 - y
        im = pyautogui.screenshot(region=(x, y, width, height))
        return im
    else:
        print('Window not found!')
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
            "text": "This is a screenshot of the game Elite:Dangerous Odyssey. Do not describe ship cockpit or game HUD. " +
            "Briefly describe celestial bodies, ships, humans and other surroundings. " + query
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

        print("get_station_info:", response.text)

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
        print("get_station_info completion:", completion)

        return completion.choices[0].message.content

    except:
        return "Currently no information on system available"

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

        print("get_faction_info:", response.text)

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
        print("get_faction_info completion:", completion)

        return completion.choices[0].message.content

    except:
        return "Currently no information on factions inside this system available"

def get_visuals(obj):
    image = screenshot()
    if not image: return "Unable to take screenshot."
    
    completion = client.chat.completions.create(
        extra_headers={
            "HTTP-Referer": "https://github.com/RatherRude/Elite-Dangerous-AI-Integration",
            "X-Title": "Elite Dangerous AI Integration",
        },
        model=aiModel,
        messages=format_image(image, obj.get("query")),
    ) 
    print("get_visuals completion:", completion)

    return completion.choices[0].message.content

aiActions.registerAction('getVisuals', "Get a description of what's currently visible to the Commander", {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Describe what you are curious about in the description. Example: 'Count the number of pirates'"
        }
    },
    "required": ["query"]
}, get_visuals)

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

jn = EDJournal()
def handle_conversation(client, commander_name, user_input):
    print(f"\033[1;33mCMDR\033[0m: {user_input}")
    chat_prompt = prepare_chat_prompt(commander_name)
    
    # Append user input to the conversation
    userChatMessage = {"role": "user", "content": user_input}
    conversation.append(userChatMessage)
    conversation.pop(0) if len(conversation) > conversationLength else None

    run_chat_model(client, commander_name, chat_prompt+[userChatMessage])

def prepare_chat_prompt(commander_name):
    rawState =jn.ship_state()
    keysToFilterOut = {
        "time",
        "odyssey",
        "fighter_destroyed",
        "interdicted",
        "no_dock_reason",
        "mission_completed",
        "mission_redirected"
    }
    filteredState = {key: value for key, value in rawState.items() if key not in keysToFilterOut}

    systemPrompt = {"role": "system", "content": "Let's roleplay in the universe of Elite: Dangerous. " +
    "I will provide game events in parentheses; do not create new ones. " +
    f"I am Commander {commander_name}. You are the onboard AI of my starship. " + backstory}
    status = {"role": "user", "content": "(Ship status: " + json.dumps(filteredState) + ")"}
    system = {
        "role": "user",
        "content": (
            f"(Location: {get_system_info(filteredState['location'])})"
        )
    }

    # print('location')
    # print(get_system_info(filteredState['location']))
    # print('faction')
    # print(get_faction_info(filteredState['location']))
    # print('stations')
    # print(get_station_info(filteredState['location']))
    

    # Context for AI, consists of conversation history, ships status, information about current system and the user input
    return [systemPrompt]+[status, system]+conversation


def run_chat_model(client, commander_name, chat_prompt):
    global conversation
    # Make a request to OpenAI with the updated conversation
    #print("messages:", chat_prompt)
    completion = client.chat.completions.create(
        extra_headers={
            "HTTP-Referer": "https://github.com/RatherRude/Elite-Dangerous-AI-Integration",
            "X-Title": "Elite Dangerous AI Integration",
        },
        tools=aiActions.getToolsList(),
        model=aiModel,
        messages=chat_prompt,
    )


    if hasattr(completion, 'error'):
        print("completion with error:", completion)
        return

    # Add the model's response to the conversation
    conversation.append(completion.choices[0].message)
    conversation.pop(0) if len(conversation) > conversationLength else None

    # Get and print the model's response
    response_text = completion.choices[0].message.content
    if (response_text):
        print(f"\033[1;34mAI\033[0m: {response_text}")
        v.say(response_text)

    response_actions = completion.choices[0].message.tool_calls
    if (response_actions):
        for action in response_actions:
            print(f"\033[1;33mACTION\033[0m: {action.function.name} {action.function.arguments}")
            action_result = aiActions.runAction(action)
            conversation.append(action_result)
            while(len(conversation) > conversationLength):
                conversation.pop(0)
        run_chat_model(client, commander_name, prepare_chat_prompt(commander_name))

def getCurrentState():
    keysToFilterOut = [
        "time",
        "odyssey",
        "fighter_destroyed",
        "no_dock_reason",
        "mission_completed",
        "mission_redirected"
    ]
    rawState = jn.ship_state()

    return {key: value for key, value in rawState.items() if key not in keysToFilterOut}

second_call = False
previous_status = getCurrentState()
def checkForJournalUpdates(client, commanderName):
    #print('checkForJournalUpdates is checking')
    global previous_status, second_call
    def check_status_changes(prev_status, current_status, keys):
        changes = []
        for key in keys:
            if prev_status[key] != current_status[key]:
                changes.append((key, prev_status[key], current_status[key]))
        return changes

    relevant_status = [
        'type',
        'target',
        'shieldsup',
        'under_attack',
        'type',
        'fuel_percent',
        'interdicted',
        'disembark'
    ]
    current_status = getCurrentState()
    #print('check_status_changes')
    changes = check_status_changes(previous_status, current_status, relevant_status)
    for change in changes:
        key, old_value, new_value = change
        print(f"{key} changed from {old_value} to {new_value}")

        # Events
        if key == 'type':
            # type event is written twice to EDJournal, we only want one interaction
            second_call = not second_call and True
            if second_call:
                handle_conversation(client, commanderName, f"(Commander {commanderName} just swapped Vessels, from {old_value} to {new_value})")
        if key == 'target':
            if new_value != None:
                handle_conversation(client, commanderName, f"(Commander {commanderName} has locked in a new jump destination: {new_value}. Detailed information: {get_system_info(new_value)})")
        if key == 'shieldsup':
            if new_value != True:
                handle_conversation(client, commanderName, f"(Commander {commanderName}'s ship has lost its shields! Warn about immediate danger!)")
            else:
                handle_conversation(client, commanderName, f"(Commander {commanderName}'s ship has regained its shields! Express your relief!)")
        if key == 'under_attack':
            if new_value == True:
                handle_conversation(client, commanderName, f"(Commander {commanderName}'s ship is under attack! Warn about immediate danger!)")
                jn.reset_items()
        if key == 'fuel_percent':
            if new_value <= 25:
                handle_conversation(client, commanderName, f"(Commander {commanderName}'s ship has less than 25% fuel reserves! Warn about immediate danger!)")
        if key == 'interdicted':
            handle_conversation(client, commanderName, f"(Commander {commanderName}'s ship is being interdicted! Warn about immediate danger, advise to run or to prepare for a fight!)")
        if key == 'cockpit_breached':
            if new_value == True:
                handle_conversation(client, commanderName, f"(Commander {commanderName}'s ship cockpit has been breached! Warn about immediate danger!)")
                jn.reset_items()
        if key == 'committed_crime':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has committed a crime: {new_value}. Advise caution!)")
            jn.reset_items()
        if key == 'fighter_launched':
            if new_value == True:
                handle_conversation(client, commanderName, f"(Commander {commanderName} has launched a fighter!)")
            else:
                handle_conversation(client, commanderName, f"(Commander {commanderName}'s fighter has docked again)")
        if key == 'fighter_destroyed':
            handle_conversation(client, commanderName, f"(Commander {commanderName}'s fighter was destroyed! Commander {commanderName} is safely back in the ship.)")
            jn.reset_items()
        if key == 'srv_launched':
            if new_value == True:
                handle_conversation(client, commanderName, f"(Commander {commanderName} has launched an SRV!)")
            else:
                handle_conversation(client, commanderName, f"(Commander {commanderName}'s SRV has docked again)")
        if key == 'status':
            if new_value == 'landed':
                handle_conversation(client, commanderName, f"(Commander {commanderName} has landed the ship.)")
            elif new_value == 'liftoff':
                handle_conversation(client, commanderName, f"(Commander {commanderName}'s ship has lifted off from the surface.)")
            elif new_value == 'destroyed':
                handle_conversation(client, commanderName, f"(Commander {commanderName}'s ship has been destroyed. Express sympathy.)")
            elif new_value == 'resurrected':
                handle_conversation(client, commanderName, f"(Commander {commanderName} has been released from hospital.)")
            elif new_value == 'approaching_settlement':
                handle_conversation(client, commanderName, f"(Commander {commanderName} is approaching a settlement.)")
            elif new_value == 'self_destruct':
                handle_conversation(client, commanderName, f"(Commander {commanderName}'s ship is self-destructing! Make sure it's not a mistake.)")
        if key == 'datalink_scan':
            if new_value == True:
                handle_conversation(client, commanderName, f"(Commander {commanderName} has performed a datalink scan.)")
                jn.reset_items()
        if key == 'cargo_ejected':
            if new_value == True:
                handle_conversation(client, commanderName, f"(Commander {commanderName} has ejected cargo.)")
                jn.reset_items()
        if key == 'mission_accepted':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has accepted a mission: {new_value}.)")
            jn.reset_items()
        if key == 'mission_completed':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has completed a mission. {new_value} missions have been completed.)")
        if key == 'mission_failed':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has failed a mission: {new_value}.)")
            jn.reset_items()
        if key == 'mission_abandoned':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has abandoned a mission: {new_value}.)")
            jn.reset_items()
        if key == 'disembark':
            if new_value != False:
                handle_conversation(client, commanderName, f"(Commander {commanderName} has disembarked: {new_value}.)")
            else:
                handle_conversation(client, commanderName, f"(Commander {commanderName} has embarked and is back on board.)")

        """
        #Travel Events:
        if log_event == 'ApproachBody':
            handle_conversation(client, commanderName, f"(Commander {commanderName} is approaching a celestial body.)")

        if log_event == 'ApproachStar':
            handle_conversation(client, commanderName, f"(Commander {commanderName} is approaching a star.)")

        if log_event == 'HeatWarning':
            handle_conversation(client, commanderName, f"(Commander {commanderName} is experiencing a heat warning.)")

        if log_event == 'HeatDamage':
            handle_conversation(client, commanderName, f"(Commander {commanderName} is taking heat damage.)")

        if log_event == 'ShieldHealth':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has updated shield health: {json.dumps({'Health': log['Health']})})")

        if log_event == 'UnderAttack':
            handle_conversation(client, commanderName, f"(Commander {commanderName} is under attack.)")

        if log_event == 'StartJump':
            handle_conversation(client, commanderName, f"(Commander {commanderName} is preparing to jump. {json.dumps({'JumpsRemaining': log['JumpsRemaining']})})")

        if log_event == 'CargoTransfer':
            handle_conversation(client, commanderName, f"(Commander {commanderName} is transferring cargo: {json.dumps({'Direction': log['Direction']})})")

        if log_event == 'DockingTimeout':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has experienced a docking timeout.)")

        if log_event == 'DockingRequested':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has requested docking.)")

        if log_event == 'DockingDenied':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has been denied docking: {json.dumps({'Reason': log['Reason']})})")

        if log_event == 'DockingGranted':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has been granted docking permission.)")

        if log_event == 'DockingComplete':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has completed docking.)")

        if log_event == 'DockingCancelled':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has cancelled docking.)")

        if log_event == 'MiningRefined':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has refined mining material: {json.dumps({'Type': log['Type']})})")

        if log_event == 'USSDrop':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has encountered a USS drop: {json.dumps({'USSType': log['USSType'], 'USSType_Localised': log['USSType_Localised']})})")

        if log_event == 'AsteroidCracked':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has cracked an asteroid: {json.dumps({'Body': log['Body']})})")

        if log_event == 'ProspectedAsteroid':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has prospected an asteroid: {json.dumps({'Materials': log['Materials']})})")

        if log_event == 'Scan':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has completed a scan: {json.dumps({'ScanType': log['ScanType']})})")

        if log_event == 'ReceiveText':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has received a message from {log['From']}: {json.dumps({'Message': log['Message']})})")

        # Exploration Events:
        if log_event == 'CodexEntry':
            entry_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "EntryID": new_value['EntryID'],
                "Name": new_value['Name'],
                "Name_Localised": new_value['Name_Localised'],
                "SubCategory": new_value['SubCategory'],
                "SubCategory_Localised": new_value['SubCategory_Localised'],
                "Category": new_value['Category'],
                "Category_Localised": new_value['Category_Localised'],
                "Region": new_value['Region'],
                "Region_Localised": new_value['Region_Localised'],
                "System": new_value['System'],
                "SystemAddress": new_value['SystemAddress'],
                "BodyID": new_value['BodyID'],
                "NearestDestination": new_value.get('NearestDestination', None),
                "NearestDestination_Localised": new_value.get('NearestDestination_Localised', None),
                "IsNewEntry": new_value.get('IsNewEntry', False),
                "VoucherAmount": new_value.get('VoucherAmount', None),
                "NewTraitsDiscovered": new_value.get('NewTraitsDiscovered', False),
                "Traits": new_value.get('Traits', [])
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has logged a Codex entry: {entry_data})")

        if log_event == 'DiscoveryScan':
            discovery_scan_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "SystemAddress": new_value['SystemAddress'],
                "Bodies": new_value['Bodies']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has performed a discovery scan in system {new_value['System']})")

        if log_event == 'Scan':
            scan_type = new_value['ScanType']
            if scan_type == 'NavBeacon' or scan_type == 'NavBeaconDetail':
                scan_data = {
                    "timestamp": new_value['timestamp'],
                    "event": log_event,
                    "ScanType": scan_type,
                    "BodyName": new_value['BodyName'],
                    "BodyID": new_value['BodyID'],
                    "SystemAddress": new_value['SystemAddress']
                }
            else:
                scan_data = {
                    "timestamp": new_value['timestamp'],
                    "event": log_event,
                    "ScanType": scan_type,
                    "StarSystem": new_value['StarSystem'],
                    "SystemAddress": new_value['SystemAddress'],
                    "BodyName": new_value['BodyName'],
                    "BodyID": new_value['BodyID'],
                    "DistanceFromArrivalLS": new_value['DistanceFromArrivalLS'],
                    "StarType": new_value.get('StarType', None),
                    "Subclass": new_value.get('Subclass', None),
                    "StellarMass": new_value.get('StellarMass', None),
                    "Radius": new_value.get('Radius', None),
                    "AbsoluteMagnitude": new_value.get('AbsoluteMagnitude', None),
                    "RotationPeriod": new_value.get('RotationPeriod', None),
                    "SurfaceTemperature": new_value.get('SurfaceTemperature', None),
                    "Luminosity": new_value.get('Luminosity', None),
                    "Age_MY": new_value.get('Age_MY', None),
                    "Rings": new_value.get('Rings', []),
                    "WasDiscovered": new_value.get('WasDiscovered', None),
                    "WasMapped": new_value.get('WasMapped', None),
                    "Parents": new_value.get('Parents', None),
                    "TidalLock": new_value.get('TidalLock', None),
                    "TerraformState": new_value.get('TerraformState', None),
                    "PlanetClass": new_value.get('PlanetClass', None),
                    "Atmosphere": new_value.get('Atmosphere', None),
                    "AtmosphereType": new_value.get('AtmosphereType', None),
                    "AtmosphereComposition": new_value.get('AtmosphereComposition', []),
                    "Volcanism": new_value.get('Volcanism', None),
                    "SurfaceGravity": new_value.get('SurfaceGravity', None),
                    "SurfacePressure": new_value.get('SurfacePressure', None),
                    "Landable": new_value.get('Landable', None),
                    "Materials": new_value.get('Materials', []),
                    "Composition": new_value.get('Composition', {}),
                    "SemiMajorAxis": new_value.get('SemiMajorAxis', None),
                    "Eccentricity": new_value.get('Eccentricity', None),
                    "OrbitalInclination": new_value.get('OrbitalInclination', None),
                    "Periapsis": new_value.get('Periapsis', None),
                    "OrbitalPeriod": new_value.get('OrbitalPeriod', None),
                    "RotationPeriod": new_value.get('RotationPeriod', None),
                    "AxialTilt": new_value.get('AxialTilt', None),
                    "ReserveLevel": new_value.get('ReserveLevel', None)
                }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has scanned a {scan_type} at {new_value['StarSystem']})")

        # Trade Events:
        if log_event == 'Trade':
            trade_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "MarketID": new_value['MarketID'],
                "Type": new_value['Type'],
                "Count": new_value['Count'],
                "BuyPrice": new_value['BuyPrice'],
                "TotalCost": new_value['TotalCost']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has performed a trade: {new_value['Type']} {new_value['Count']} units. Bought at {new_value['BuyPrice']} credits each, total cost {new_value['TotalCost']} credits.)")

        if log_event == 'AsteroidCracked':
            asteroid_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Body": new_value['Body']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has cracked an asteroid: {new_value['Body']}.)")

        if log_event == 'BuyTradeData':
            buy_trade_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "System": new_value['System'],
                "Cost": new_value['Cost']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has bought trade data for {new_value['System']} at {new_value['Cost']} credits.)")

        if log_event == 'CollectCargo':
            collect_cargo_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Type": new_value['Type'],
                "Stolen": new_value['Stolen'],
                "MissionID": new_value.get('MissionID', None)
            }
            if new_value['Stolen']:
                handle_conversation(client, commanderName, f"(Commander {commanderName} has collected stolen cargo: {new_value['Type']}. Mission ID: {new_value.get('MissionID', 'None')})")
            else:
                handle_conversation(client, commanderName, f"(Commander {commanderName} has collected cargo: {new_value['Type']}. Mission ID: {new_value.get('MissionID', 'None')})")

        if log_event == 'EjectCargo':
            eject_cargo_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Type": new_value['Type'],
                "Count": new_value['Count'],
                "Abandoned": new_value['Abandoned'],
                "PowerplayOrigin": new_value.get('PowerplayOrigin', None),
                "MissionID": new_value.get('MissionID', None)
            }
            if new_value['Abandoned']:
                handle_conversation(client, commanderName, f"(Commander {commanderName} has ejected cargo: {new_value['Count']} units of {new_value['Type']}, abandoned.)")
            else:
                handle_conversation(client, commanderName, f"(Commander {commanderName} has ejected cargo: {new_value['Count']} units of {new_value['Type']}. Mission ID: {new_value.get('MissionID', 'None')})")

        if log_event == 'MarketBuy':
            market_buy_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "MarketID": new_value['MarketID'],
                "Type": new_value['Type'],
                "Count": new_value['Count'],
                "BuyPrice": new_value['BuyPrice'],
                "TotalCost": new_value['TotalCost']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has bought {new_value['Count']} units of {new_value['Type']} at {new_value['BuyPrice']} credits each, total cost {new_value['TotalCost']} credits.)")

        if log_event == 'MarketSell':
            market_sell_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "MarketID": new_value['MarketID'],
                "Type": new_value['Type'],
                "Count": new_value['Count'],
                "SellPrice": new_value['SellPrice'],
                "TotalSale": new_value['TotalSale'],
                "AvgPricePaid": new_value['AvgPricePaid'],
                "IllegalGoods": new_value.get('IllegalGoods', None),
                "StolenGoods": new_value.get('StolenGoods', None),
                "BlackMarket": new_value.get('BlackMarket', None)
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has sold {new_value['Count']} units of {new_value['Type']} at {new_value['SellPrice']} credits each, total sale {new_value['TotalSale']} credits.)")

        if log_event == 'MiningRefined':
            mining_refined_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Type": new_value['Type']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has refined a resource: {new_value['Type']}.)")
        # Station Services
        if log_event == 'StationServices':
            station_services_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "StationName": new_value['StationName'],
                "StationType": new_value['StationType']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has accessed station services at {new_value['StationName']}.)")

        if log_event == 'BuyAmmo':
            buy_ammo_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Cost": new_value['Cost']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has bought ammunition for {new_value['Cost']} credits.)")

        if log_event == 'BuyDrones':
            buy_drones_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Type": new_value['Type'],
                "Count": new_value['Count'],
                "BuyPrice": new_value['BuyPrice'],
                "TotalCost": new_value['TotalCost']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has bought {new_value['Count']} {new_value['Type']} drones for {new_value['TotalCost']} credits.)")

        if log_event == 'CargoDepot':
            cargo_depot_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "MissionID": new_value['MissionID'],
                "UpdateType": new_value['UpdateType'],
                "CargoType": new_value['CargoType'],
                "Count": new_value['Count'],
                "StartMarketID": new_value['StartMarketID'],
                "EndMarketID": new_value['EndMarketID'],
                "ItemsCollected": new_value['ItemsCollected'],
                "ItemsDelivered": new_value['ItemsDelivered'],
                "TotalItemsToDeliver": new_value['TotalItemsToDeliver'],
                "Progress": new_value['Progress']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has completed a cargo depot operation for mission {new_value['MissionID']}. Collected {new_value['ItemsCollected']} items and delivered {new_value['ItemsDelivered']} items.)")

        if log_event == 'CommunityGoal':
            community_goal_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "CGID": new_value['CGID'],
                "Name": new_value['Name'],
                "System": new_value['System'],
                "CurrentTotal": new_value['CurrentTotal'],
                "PlayerContribution": new_value['PlayerContribution'],
                "NumContributors": new_value['NumContributors'],
                "TopRankSize": new_value['TopRankSize']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has engaged in community goal {new_value['Name']} in {new_value['System']}: Current total {new_value['CurrentTotal']}, Player contribution {new_value['PlayerContribution']}, Number of contributors {new_value['NumContributors']}, Top rank size {new_value['TopRankSize']})")


        if log_event == 'CommunityGoalDiscard':
            community_goal_discard_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "CGID": new_value['CGID'],
                "Name": new_value['Name'],
                "System": new_value['System']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has discarded a community goal: {new_value['Name']} in {new_value['System']})")

        if log_event == 'CommunityGoalJoin':
            community_goal_join_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "CGID": new_value['CGID'],
                "Name": new_value['Name'],
                "System": new_value['System']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has joined a community goal: {new_value['Name']} in {new_value['System']})")

        if log_event == 'CommunityGoalReward':
            community_goal_reward_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "CGID": new_value['CGID'],
                "Name": new_value['Name'],
                "System": new_value['System'],
                "Reward": new_value['Reward']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has received a reward for community goal {new_value['Name']} in {new_value['System']}: {new_value['Reward']} credits)")

        if log_event == 'CrewAssign':
            crew_assign_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Name": new_value['Name'],
                "CrewID": new_value['CrewID'],
                "Role": new_value['Role']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has assigned crew member {new_value['Name']} (ID: {new_value['CrewID']}) to {new_value['Role']} role)")

        if log_event == 'CrewFire':
            crew_fire_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Name": new_value['Name'],
                "CrewID": new_value['CrewID']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has fired crew member {new_value['Name']} (ID: {new_value['CrewID']})")

        if log_event == 'CrewHire':
            crew_hire_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Name": new_value['Name'],
                "CrewID": new_value['CrewID'],
                "Faction": new_value['Faction'],
                "Cost": new_value['Cost'],
                "CombatRank": new_value['CombatRank']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has hired crew member {new_value['Name']} (ID: {new_value['CrewID']}) from {new_value['Faction']} with combat rank {new_value['CombatRank']}")

        if log_event == 'EngineerContribution':
            engineer_contribution_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Engineer": new_value['Engineer'],
                "EngineerID": new_value['EngineerID'],
                "Type": new_value['Type'],
                "Commodity": new_value.get('Commodity', None),
                "Material": new_value.get('Material', None),
                "Faction": new_value.get('Faction', None),
                "Quantity": new_value['Quantity'],
                "TotalQuantity": new_value['TotalQuantity']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has made a contribution to engineer {new_value['Engineer']} (ID: {new_value['EngineerID']}) in {new_value['Type']}")

        if log_event == 'EngineerCraft':
            engineer_craft_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Engineer": new_value['Engineer'],
                "EngineerID": new_value['EngineerID'],
                "BlueprintName": new_value['BlueprintName'],
                "BlueprintID": new_value['BlueprintID'],
                "Level": new_value['Level'],
                "Quality": new_value['Quality'],
                "ApplyExperimentalEffect": new_value.get('ApplyExperimentalEffect', None),
                "Ingredients": new_value.get('Ingredients', None),
                "Modifiers": new_value['Modifiers']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has crafted {new_value['BlueprintName']} (ID: {new_value['BlueprintID']}) at engineer {new_value['Engineer']} (ID: {new_value['EngineerID']})")

        if log_event == 'EngineerLegacyConvert':
            engineer_legacy_convert_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Engineer": new_value['Engineer'],
                "EngineerID": new_value['EngineerID'],
                "BlueprintName": new_value['BlueprintName'],
                "BlueprintID": new_value['BlueprintID'],
                "Level": new_value['Level'],
                "Quality": new_value['Quality'],
                "IsPreview": new_value['IsPreview']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has converted legacy blueprint {new_value['BlueprintName']} (ID: {new_value['BlueprintID']}) at engineer {new_value['Engineer']} (ID: {new_value['EngineerID']})")

        if log_event == 'EngineerProgress':
            if 'Engineers' in new_value:
                engineer_progress_data = {
                    "timestamp": new_value['timestamp'],
                    "event": log_event,
                    "Engineers": new_value['Engineers']
                }
                handle_conversation(client, commanderName, f"(Commander {commanderName} has progressed with multiple engineers)")
            else:
                engineer_progress_data = {
                    "timestamp": new_value['timestamp'],
                    "event": log_event,
                    "Engineer": new_value['Engineer'],
                    "EngineerID": new_value['EngineerID'],
                    "Rank": new_value['Rank'],
                    "Progress": new_value['Progress'],
                    "RankProgress": new_value['RankProgress']
                }
                handle_conversation(client, commanderName, f"(Commander {commanderName} has progressed with engineer {new_value['Engineer']} (ID: {new_value['EngineerID']}) to rank {new_value['Rank']}")

        if log_event == 'FetchRemoteModule':
            fetch_remote_module_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "StorageSlot": new_value['StorageSlot'],
                "StoredItem": new_value['StoredItem'],
                "ServerId": new_value['ServerId'],
                "TransferCost": new_value['TransferCost'],
                "Ship": new_value['Ship'],
                "ShipId": new_value['ShipId'],
                "TransferTime": new_value['TransferTime']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has fetched a remote module. Details: {json.dumps(fetch_remote_module_data)})")

        if log_event == 'Market':
            market_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "MarketID": new_value['MarketID'],
                "StationName": new_value['StationName'],
                "StarSystem": new_value['StarSystem']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has interacted with a market. Details: {json.dumps(market_data)})")

        if log_event == 'MassModuleStore':
            items = []
            for item in new_value['Items']:
                module_data = {
                    "Slot": item['Slot'],
                    "Name": item['Name'],
                    "Hot": item['Hot'],
                    "EngineerModifications": item.get('EngineerModifications', None),
                    "Level": item['Level'],
                    "Quality": item['Quality']
                }
                items.append(module_data)

            mass_module_store_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "MarketID": new_value['MarketID'],
                "Ship": new_value['Ship'],
                "ShipID": new_value['ShipID'],
                "Items": items
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has mass stored modules. Details: {json.dumps(mass_module_store_data)})")

        if log_event == 'MaterialTrade':
            material_trade_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "MarketID": new_value['MarketID'],
                "TraderType": new_value['TraderType'],
                "Paid": {
                    "Material": new_value['Paid']['Material'],
                    "Category": new_value['Paid']['Category'],
                    "Quantity": new_value['Paid']['Quantity']
                },
                "Received": {
                    "Material": new_value['Received']['Material'],
                    "Quantity": new_value['Received']['Quantity']
                }
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has conducted a material trade. Details: {json.dumps(material_trade_data)})")

        if log_event == 'MissionAbandoned':
            mission_abandoned_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Name": new_value['Name'],
                "MissionID": new_value['MissionID'],
                "Fine": new_value.get('Fine', None)
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has abandoned a mission. Details: {json.dumps(mission_abandoned_data)})")

        if log_event == 'MissionAccepted':
            mission_accepted_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Faction": new_value['Faction'],
                "Name": new_value['Name'],
                "LocalisedName": new_value.get('LocalisedName', None),
                "Commodity": new_value.get('Commodity', None),
                "Count": new_value.get('Count', None),
                "TargetFaction": new_value.get('TargetFaction', None),
                "DestinationSystem": new_value.get('DestinationSystem', None),
                "DestinationStation": new_value.get('DestinationStation', None),
                "Expiry": new_value.get('Expiry', None),
                "Wing": new_value.get('Wing', False),
                "Influence": new_value.get('Influence', None),
                "Reputation": new_value.get('Reputation', None),
                "Reward": new_value.get('Reward', None),
                "MissionID": new_value['MissionID']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has accepted a mission. Details: {json.dumps(mission_accepted_data)})")

        if log_event == 'MissionCompleted':
            mission_completed_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Name": new_value['Name'],
                "Faction": new_value['Faction'],
                "MissionID": new_value['MissionID'],
                "Commodity": new_value.get('Commodity', None),
                "Count": new_value.get('Count', None),
                "Target": new_value.get('Target', None),
                "TargetType": new_value.get('TargetType', None),
                "TargetFaction": new_value.get('TargetFaction', None),
                "DestinationSystem": new_value.get('DestinationSystem', None),
                "DestinationStation": new_value.get('DestinationStation', None),
                "DestinationSettlement": new_value.get('DestinationSettlement', None),
                "Reward": new_value['Reward'],
                "Donation": new_value.get('Donation', None),
                "Donated": new_value.get('Donated', None),
                "PermitsAwarded": new_value.get('PermitsAwarded', []),
                "CommodityReward": new_value.get('CommodityReward', []),
                "MaterialsReward": new_value.get('MaterialsReward', []),
                "FactionEffects": new_value.get('FactionEffects', [])
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has completed a mission. Details: {json.dumps(mission_completed_data)})")

        if log_event == 'MissionFailed':
            mission_failed_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Name": new_value['Name'],
                "MissionID": new_value['MissionID'],
                "Fine": new_value.get('Fine', None)
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has failed a mission. Details: {json.dumps(mission_failed_data)})")

        if log_event == 'MissionRedirected':
            mission_redirected_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "MissionID": new_value['MissionID'],
                "Name": new_value['Name'],
                "NewDestinationStation": new_value['NewDestinationStation'],
                "OldDestinationStation": new_value['OldDestinationStation'],
                "NewDestinationSystem": new_value['NewDestinationSystem'],
                "OldDestinationSystem": new_value['OldDestinationSystem']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has redirected a mission. Details: {json.dumps(mission_redirected_data)})")

        if log_event == 'ModuleBuy':
            module_buy_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "MarketID": new_value['MarketID'],
                "Slot": new_value['Slot'],
                "BuyItem": new_value['BuyItem'],
                "BuyPrice": new_value['BuyPrice'],
                "Ship": new_value['Ship'],
                "ShipID": new_value['ShipID'],
                "StoredItem": new_value.get('StoredItem', None),
                "StoredItem_Localised": new_value.get('StoredItem_Localised', None),
                "SellItem": new_value.get('SellItem', None),
                "SellPrice": new_value.get('SellPrice', None)
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has bought a module. Details: {json.dumps(module_buy_data)})")

        if log_event == 'ModuleRetrieve':
            module_retrieve_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "MarketID": new_value['MarketID'],
                "Slot": new_value['Slot'],
                "Ship": new_value['Ship'],
                "ShipID": new_value['ShipID'],
                "RetrievedItem": new_value['RetrievedItem'],
                "Hot": new_value.get('Hot', False),
                "EngineerModifications": new_value.get('EngineerModifications', None),
                "Level": new_value.get('Level', None),
                "Quality": new_value.get('Quality', None),
                "SwapOutItem": new_value.get('SwapOutItem', None),
                "Cost": new_value.get('Cost', None)
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has retrieved a module. Details: {json.dumps(module_retrieve_data)})")

        if log_event == 'ModuleSell':
            module_sell_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "MarketID": new_value['MarketID'],
                "Slot": new_value['Slot'],
                "SellItem": new_value['SellItem'],
                "SellPrice": new_value['SellPrice'],
                "Ship": new_value['Ship'],
                "ShipID": new_value['ShipID']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has sold a module. Details: {json.dumps(module_sell_data)})")

        if log_event == 'ModuleSellRemote':
            module_sell_remote_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "StorageSlot": new_value['StorageSlot'],
                "SellItem": new_value['SellItem'],
                "ServerId": new_value['ServerId'],
                "SellPrice": new_value['SellPrice'],
                "Ship": new_value['Ship'],
                "ShipId": new_value['ShipId']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has sold a remote module. Details: {json.dumps(module_sell_remote_data)})")

        if log_event == 'ModuleStore':
            module_store_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "MarketID": new_value['MarketID'],
                "Slot": new_value['Slot'],
                "Ship": new_value['Ship'],
                "ShipID": new_value['ShipID'],
                "StoredItem": new_value['StoredItem'],
                "StoredItem_Localised": new_value.get('StoredItem_Localised', None),
                "Hot": new_value['Hot'],
                "EngineerModifications": new_value.get('EngineerModifications', None),
                "Level": new_value.get('Level', None),
                "Quality": new_value.get('Quality', None),
                "ReplacementItem": new_value.get('ReplacementItem', None),
                "Cost": new_value.get('Cost', None)
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has stored a module. Details: {json.dumps(module_store_data)})")

        if log_event == 'ModuleSwap':
            module_swap_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "MarketID": new_value['MarketID'],
                "FromSlot": new_value['FromSlot'],
                "ToSlot": new_value['ToSlot'],
                "FromItem": new_value['FromItem'],
                "ToItem": new_value['ToItem'],
                "Ship": new_value['Ship'],
                "ShipID": new_value['ShipID']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has swapped modules. Details: {json.dumps(module_swap_data)})")

        if log_event == 'Outfitting':
            outfitting_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "MarketID": new_value['MarketID'],
                "StationName": new_value['StationName'],
                "StarSystem": new_value['StarSystem'],
                "Horizons": new_value.get('Horizons', False),
                "Items": new_value.get('Items', [])
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has visited an outfitting station. Details: {json.dumps(outfitting_data)})")

        if log_event == 'PayBounties':
            pay_bounties_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Amount": new_value['Amount'],
                "BrokerPercentage": new_value.get('BrokerPercentage', None),
                "AllFines": new_value['AllFines'],
                "Faction": new_value['Faction'],
                "ShipID": new_value['ShipID']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has paid bounties. Details: {json.dumps(pay_bounties_data)})")

        if log_event == 'PayFines':
            pay_fines_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Amount": new_value['Amount'],
                "BrokerPercentage": new_value.get('BrokerPercentage', None),
                "AllFines": new_value['AllFines'],
                "Faction": new_value.get('Faction', None),
                "ShipID": new_value['ShipID']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has paid fines. Details: {json.dumps(pay_fines_data)})")

        if log_event == 'PayLegacyFines':
            pay_legacy_fines_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Amount": new_value['Amount'],
                "BrokerPercentage": new_value.get('BrokerPercentage', None)
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has paid legacy fines. Details: {json.dumps(pay_legacy_fines_data)})")

        if log_event == 'RedeemVoucher':
            redeem_voucher_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Type": new_value['Type'],
                "Amount": new_value['Amount'],
                "Factions": new_value.get('Factions', []),
                "Faction": new_value.get('Faction', None),
                "BrokerPercentage": new_value.get('BrokerPercentage', None)
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has redeemed a voucher. Details: {json.dumps(redeem_voucher_data)})")

        if log_event == 'RefuelAll':
            refuel_all_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Cost": new_value['Cost'],
                "Amount": new_value['Amount']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has refueled all. Details: {json.dumps(refuel_all_data)})")

        if log_event == 'RefuelPartial':
            refuel_partial_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Cost": new_value['Cost'],
                "Amount": new_value['Amount']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has partially refueled. Details: {json.dumps(refuel_partial_data)})")

        if log_event == 'Repair':
            repair_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Item": new_value['Item'],
                "Cost": new_value['Cost']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has repaired. Details: {json.dumps(repair_data)})")

        if log_event == 'RepairAll':
            repair_all_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Items": new_value.get('Items', []),
                "Cost": new_value['Cost']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has repaired all. Details: {json.dumps(repair_all_data)})")

        if log_event == 'RestockVehicle':
            restock_vehicle_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Type": new_value['Type'],
                "Loadout": new_value['Loadout'],
                "Cost": new_value['Cost'],
                "Count": new_value['Count']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has restocked vehicle. Details: {json.dumps(restock_vehicle_data)})")

        if log_event == 'ScientificResearch':
            scientific_research_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "MarketID": new_value['MarketID'],
                "Name": new_value['Name'],
                "Category": new_value['Category'],
                "Count": new_value['Count']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has conducted scientific research. Details: {json.dumps(scientific_research_data)})")

        if log_event == 'Shipyard':
            shipyard_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "MarketID": new_value['MarketID'],
                "StationName": new_value['StationName'],
                "StarSystem": new_value['StarSystem'],
                "Horizons": new_value['Horizons'],
                "AllowCobraMkIV": new_value['AllowCobraMkIV'],
                "PriceList": new_value['PriceList']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has visited a shipyard. Details: {json.dumps(shipyard_data)})")

        if log_event == 'ShipyardNew':
            shipyard_new_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "NewShipID": new_value['NewShipID'],
                "ShipType": new_value['ShipType']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has acquired a new ship. Details: {json.dumps(shipyard_new_data)})")

        if log_event == 'ShipyardSell':
            shipyard_sell_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "ShipType": new_value['ShipType'],
                "SellPrice": new_value['SellPrice'],
                "ShipID": new_value['ShipID']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has sold a ship. Details: {json.dumps(shipyard_sell_data)})")

        if log_event == 'StoredShips':
            stored_ships_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "StationName": new_value['StationName'],
                "StarSystem": new_value['StarSystem'],
                "Horizons": new_value['Horizons'],
                "ShipsHere": new_value['ShipsHere'],
                "ShipsRemote": new_value['ShipsRemote']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has stored ships. Details: {json.dumps(stored_ships_data)})")

        if log_event == 'StoredModules':
            stored_modules_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "StationName": new_value['StationName'],
                "StarSystem": new_value['StarSystem'],
                "Horizons": new_value['Horizons'],
                "Items": new_value['Items']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has stored modules. Details: {json.dumps(stored_modules_data)})")

        if log_event == 'TechnologyBroker':
            technology_broker_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "BrokerType": new_value['BrokerType'],
                "MarketID": new_value['MarketID'],
                "ItemsUnlocked": new_value['ItemsUnlocked']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has accessed a technology broker. Details: {json.dumps(technology_broker_data)})")

        if log_event == 'Touchdown':
            touchdown_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Latitude": new_value['Latitude'],
                "Longitude": new_value['Longitude'],
                "PlayerControlled": new_value.get('PlayerControlled', None),
                "Altitude": new_value.get('Altitude', None)
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has touched down on a planet surface. Details: {json.dumps(touchdown_data)})")

        if log_event == 'Undocked':
            undocked_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "StationName": new_value['StationName'],
                "StationType": new_value['StationType']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has undocked from a station. Details: {json.dumps(undocked_data)})")

        if log_event == 'USSDrop':
            uss_drop_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "USSType": new_value['USSType'],
                "USSThreat": new_value['USSThreat']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has dropped into a unidentified signal source. Details: {json.dumps(uss_drop_data)})")

        if log_event == 'VehicleSwitch':
            vehicle_switch_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "To": new_value['To']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has switched to a new SRV. Details: {json.dumps(vehicle_switch_data)})")

        if log_event == 'WingAdd':
            wing_add_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Name": new_value['Name']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has added a new wing member. Details: {json.dumps(wing_add_data)})")

        if log_event == 'WingInvite':
            wing_invite_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Name": new_value['Name']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has been invited to a wing. Details: {json.dumps(wing_invite_data)})")

        if log_event == 'WingJoin':
            wing_join_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Name": new_value['Name']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has joined a wing. Details: {json.dumps(wing_join_data)})")

        if log_event == 'WingLeave':
            wing_leave_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Name": new_value['Name']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has left a wing. Details: {json.dumps(wing_leave_data)})")

        # Fleet Carrier Events:
        if log_event == 'CarrierJump':
            carrier_jump_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Docked": new_value['Docked'],
                "StationName": new_value['StationName'],
                "StationType": new_value['StationType'],
                "MarketID": new_value['MarketID'],
                "StationFaction": new_value['StationFaction'],
                "StationGovernment": new_value['StationGovernment'],
                "StationGovernment_Localised": new_value['StationGovernment_Localised'],
                "StationServices": new_value['StationServices'],
                "StationEconomy": new_value['StationEconomy'],
                "StationEconomy_Localised": new_value['StationEconomy_Localised'],
                "StationEconomies": new_value['StationEconomies'],
                "StarSystem": new_value['StarSystem'],
                "SystemAddress": new_value['SystemAddress'],
                "StarPos": new_value['StarPos'],
                "SystemAllegiance": new_value['SystemAllegiance'],
                "SystemEconomy": new_value['SystemEconomy'],
                "SystemEconomy_Localised": new_value['SystemEconomy_Localised'],
                "SystemSecondEconomy": new_value['SystemSecondEconomy'],
                "SystemSecondEconomy_Localised": new_value['SystemSecondEconomy_Localised'],
                "SystemGovernment": new_value['SystemGovernment'],
                "SystemGovernment_Localised": new_value['SystemGovernment_Localised'],
                "SystemSecurity": new_value['SystemSecurity'],
                "SystemSecurity_Localised": new_value['SystemSecurity_Localised'],
                "Population": new_value['Population'],
                "Body": new_value['Body'],
                "BodyID": new_value['BodyID'],
                "BodyType": new_value['BodyType'],
                "SystemFaction": new_value['SystemFaction']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has performed a carrier jump.)")

        if log_event == 'CarrierBuy':
            carrier_buy_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "CarrierID": new_value['CarrierID'],
                "BoughtAtMarket": new_value['BoughtAtMarket'],
                "Location": new_value['Location'],
                "Price": new_value['Price'],
                "Variant": new_value['Variant'],
                "Callsign": new_value['Callsign']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has purchased a carrier: {new_value['Callsign']}.)")

        if log_event == 'CarrierStats':
            carrier_stats_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "CarrierID": new_value['CarrierID'],
                "Callsign": new_value['Callsign'],
                "Name": new_value['Name'],
                "DockingAccess": new_value['DockingAccess'],
                "AllowNotorious": new_value['AllowNotorious'],
                "FuelLevel": new_value['FuelLevel'],
                "JumpRangeCurr": new_value['JumpRangeCurr'],
                "JumpRangeMax": new_value['JumpRangeMax'],
                "PendingDecommission": new_value['PendingDecommission'],
                "SpaceUsage": new_value['SpaceUsage'],
                "Finance": new_value['Finance'],
                "Crew": new_value['Crew'],
                "ShipPacks": new_value['ShipPacks'],
                "ModulePacks": new_value['ModulePacks']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has updated carrier stats: {new_value['Callsign']}.)")

        if log_event == 'CarrierJumpRequest':
            carrier_jump_request_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "CarrierID": new_value['CarrierID'],
                "SystemName": new_value['SystemName'],
                "SystemID": new_value['SystemID'],
                "Body": new_value['Body'],
                "BodyID": new_value['BodyID'],
                "DepartureTime": new_value['DepartureTime']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has requested a carrier jump: {new_value['CarrierID']}.)")

        if log_event == 'CarrierDecommission':
            carrier_decommission_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "CarrierID": new_value['CarrierID'],
                "ScrapRefund": new_value['ScrapRefund'],
                "ScrapTime": new_value['ScrapTime']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has decommissioned a carrier: {new_value['CarrierID']}.)")

        if log_event == 'CarrierCancelDecommission':
            carrier_cancel_decommission_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "CarrierID": new_value['CarrierID']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has canceled the decommission of a carrier: {new_value['CarrierID']}.)")

        if log_event == 'CarrierBankTransfer':
            carrier_bank_transfer_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "CarrierID": new_value['CarrierID'],
                "Deposit": new_value['Deposit'],
                "PlayerBalance": new_value['PlayerBalance'],
                "CarrierBalance": new_value['CarrierBalance']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has performed a bank transfer for carrier {new_value['CarrierID']}: Deposit - {new_value['Deposit']}, Player Balance - {new_value['PlayerBalance']}, Carrier Balance - {new_value['CarrierBalance']})")

        if log_event == 'CarrierDepositFuel':
            carrier_deposit_fuel_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "CarrierID": new_value['CarrierID'],
                "Amount": new_value['Amount'],
                "Total": new_value['Total']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has deposited fuel to carrier {new_value['CarrierID']}: Amount - {new_value['Amount']}, Total - {new_value['Total']})")

        if log_event == 'CarrierCrewServices':
            carrier_crew_services_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "CarrierID": new_value['CarrierID'],
                "Operation": new_value['Operation'],
                "CrewRole": new_value['CrewRole'],
                "CrewName": new_value['CrewName']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has performed crew services on carrier {new_value['CarrierID']}: Operation - {new_value['Operation']}, Crew Role - {new_value['CrewRole']}, Crew Name - {new_value['CrewName']})")

        if log_event == 'CarrierFinance':
            carrier_finance_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "CarrierID": new_value['CarrierID'],
                "TaxRate": new_value['TaxRate'],
                "CarrierBalance": new_value['CarrierBalance'],
                "ReserveBalance": new_value['ReserveBalance'],
                "AvailableBalance": new_value['AvailableBalance'],
                "ReservePercent": new_value['ReservePercent']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has reviewed finance details for carrier {new_value['CarrierID']}: Tax Rate - {new_value['TaxRate']}, Carrier Balance - {new_value['CarrierBalance']}, Reserve Balance - {new_value['ReserveBalance']}, Available Balance - {new_value['AvailableBalance']}, Reserve Percent - {new_value['ReservePercent']})")

        if log_event == 'CarrierShipPack':
            carrier_ship_pack_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "CarrierID": new_value['CarrierID'],
                "Operation": new_value['Operation'],
                "PackTheme": new_value['PackTheme'],
                "PackTier": new_value['PackTier'],
                "Cost": new_value['Cost']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has managed ship pack for carrier {new_value['CarrierID']}: Operation - {new_value['Operation']}, Pack Theme - {new_value['PackTheme']}, Pack Tier - {new_value['PackTier']}, Cost - {new_value['Cost']})")

        if log_event == 'CarrierModulePack':
            carrier_module_pack_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "CarrierID": new_value['CarrierID'],
                "Operation": new_value['Operation'],
                "PackTheme": new_value['PackTheme'],
                "PackTier": new_value['PackTier'],
                "Cost": new_value['Cost']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has managed module pack for carrier {new_value['CarrierID']}: Operation - {new_value['Operation']}, Pack Theme - {new_value['PackTheme']}, Pack Tier - {new_value['PackTier']}, Cost - {new_value['Cost']})")

        if log_event == 'CarrierTradeOrder':
            carrier_trade_order_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "CarrierID": new_value['CarrierID'],
                "BlackMarket": new_value['BlackMarket'],
                "Commodity": new_value['Commodity'],
                "Commodity_Localised": new_value['Commodity_Localised'],
                "PurchaseOrder": new_value.get('PurchaseOrder', None),
                "SaleOrder": new_value.get('SaleOrder', None),
                "CancelTrade": new_value.get('CancelTrade', False),
                "Price": new_value['Price']
            }
            if new_value.get('CancelTrade', False):
                handle_conversation(client, commanderName, f"(Commander {commanderName} has canceled a trade order on carrier {new_value['CarrierID']}: Commodity - {new_value['Commodity_Localised']})")
            else:
                handle_conversation(client, commanderName, f"(Commander {commanderName} has placed a trade order on carrier {new_value['CarrierID']}: Commodity - {new_value['Commodity_Localised']}, Price - {new_value['Price']})")

        if log_event == 'CarrierDockingPermission':
            carrier_docking_permission_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "CarrierID": new_value['CarrierID'],
                "DockingAccess": new_value['DockingAccess'],
                "AllowNotorious": new_value['AllowNotorious']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has updated docking permissions for carrier {new_value['CarrierID']}: Docking Access - {new_value['DockingAccess']}, Allow Notorious - {new_value['AllowNotorious']})")

        if log_event == 'CarrierNameChanged':
            carrier_name_changed_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "CarrierID": new_value['CarrierID'],
                "Callsign": new_value['Callsign'],
                "Name": new_value['Name']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has changed the name of carrier {new_value['CarrierID']} to {new_value['Name']}. Callsign - {new_value['Callsign']})")

        if log_event == 'CarrierJumpCancelled':
            carrier_jump_cancelled_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "CarrierID": new_value['CarrierID']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has canceled a jump request for carrier {new_value['CarrierID']})")

        # Odyssey Events:
        if log_event == 'Backpack':
            backpack_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Items": new_value['Items'],
                "Components": new_value['Components'],
                "Consumables": new_value['Consumables'],
                "Data": new_value['Data']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has interacted with their backpack: {new_value}).")

        if log_event == 'BackpackChange':
            backpack_change_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Added": new_value.get('Added', []),
                "Removed": new_value.get('Removed', [])
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has changed items in their backpack: {new_value}).")

        if log_event == 'BookDropship':
            book_dropship_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "StarSystem": new_value['StarSystem'],
                "SystemAddress": new_value['SystemAddress'],
                "Body": new_value['Body'],
                "BodyID": new_value['BodyID']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has booked a dropship to {new_value['StarSystem']}).")

        if log_event == 'BookTaxi':
            book_taxi_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Cost": new_value['Cost'],
                "DestinationSystem": new_value['DestinationSystem'],
                "DestinationLocation": new_value['DestinationLocation'],
                "Retreat": new_value['Retreat']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has booked a taxi to {new_value['DestinationSystem']} at a cost of {new_value['Cost']} credits).")

        if log_event == 'BuyMicroResources':
            buy_micro_resources_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "TotalCount": new_value['TotalCount'],
                "Price": new_value['Price'],
                "MarketID": new_value['MarketID'],
                "MicroResources": new_value['MicroResources']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has bought micro resources: {new_value}).")

        if log_event == 'BuySuit':
            buy_suit_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Name": new_value['Name'],
                "Price": new_value['Price'],
                "SuitID": new_value['SuitID'],
                "SuitMods": new_value.get('SuitMods', [])
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has bought a suit: {new_value['Name']}).")

        if log_event == 'BuyWeapon':
            buy_weapon_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Name": new_value['Name'],
                "Price": new_value['Price'],
                "SuitModuleID": new_value['SuitModuleID'],
                "Class": new_value['Class'],
                "WeaponMods": new_value.get('WeaponMods', [])
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has bought a weapon: {new_value['Name']}).")

        if log_event == 'CancelDropship':
            cancel_dropship_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "StarSystem": new_value['StarSystem'],
                "SystemAddress": new_value['SystemAddress'],
                "Body": new_value['Body'],
                "BodyID": new_value['BodyID']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has cancelled a dropship booking to {new_value['StarSystem']}).")

        if log_event == 'CancelTaxi':
            cancel_taxi_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Refund": new_value['Refund']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has cancelled a taxi booking and received a refund of {new_value['Refund']} credits).")

        if log_event == 'CollectItems':
            collect_items_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Name": new_value['Name'],
                "Type": new_value['Type'],
                "OwnerID": new_value['OwnerID'],
                "Count": new_value['Count'],
                "Stolen": new_value['Stolen']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has collected items: {new_value['Name']} x {new_value['Count']}).")

        if log_event == 'CreateSuitLoadout':
            create_suit_loadout_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "SuitID": new_value['SuitID'],
                "SuitName": new_value['SuitName'],
                "SuitMods": new_value.get('SuitMods', []),
                "LoadoutID": new_value['LoadoutID'],
                "LoadoutName": new_value['LoadoutName'],
                "Modules": new_value['Modules']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has created a suit loadout: {new_value['SuitName']} - {new_value['LoadoutName']}).")


        if log_event == 'CreateSuitLoadout':
            create_suit_loadout_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "SuitID": new_value['SuitID'],
                "SuitName": new_value['SuitName'],
                "SuitMods": new_value.get('SuitMods', []),
                "LoadoutID": new_value['LoadoutID'],
                "LoadoutName": new_value['LoadoutName'],
                "Modules": new_value['Modules']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has created a suit loadout: {new_value['SuitName']} - {new_value['LoadoutName']}).")

        if log_event == 'DeleteSuitLoadout':
            delete_suit_loadout_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "SuitID": new_value['SuitID'],
                "SuitName": new_value['SuitName'],
                "LoadoutID": new_value['LoadoutID'],
                "LoadoutName": new_value['LoadoutName']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has deleted a suit loadout: {new_value['SuitName']} - {new_value['LoadoutName']}).")

        if log_event == 'Disembark':
            disembark_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "SRV": new_value['SRV'],
                "Taxi": new_value['Taxi'],
                "Multicrew": new_value['Multicrew'],
                "ID": new_value['ID'],
                "StarSystem": new_value['StarSystem'],
                "SystemAddress": new_value['SystemAddress'],
                "Body": new_value['Body'],
                "BodyID": new_value['BodyID'],
                "OnStation": new_value['OnStation'],
                "OnPlanet": new_value['OnPlanet'],
                "StationName": new_value.get('StationName', None),
                "StationType": new_value['StationType'],
                "MarketID": new_value['MarketID']
            }
            if new_value['SRV'] or new_value['Taxi'] or new_value['Multicrew']:
                handle_conversation(client, commanderName, f"(Commander {commanderName} has disembarked at {new_value['StarSystem']}, {new_value['Body']}).")
            else:
                handle_conversation(client, commanderName, f"(Commander {commanderName} has embarked and is back on board).")

        if log_event == 'DropItems':
            drop_items_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Name": new_value['Name'],
                "Type": new_value['Type'],
                "OwnerID": new_value['OwnerID'],
                "MissionID": new_value.get('MissionID', None),
                "Count": new_value['Count']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has dropped items: {new_value['Name']} x {new_value['Count']}).")

        if log_event == 'DropShipDeploy':
            dropship_deploy_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "StarSystem": new_value['StarSystem'],
                "SystemAddress": new_value['SystemAddress'],
                "Body": new_value['Body'],
                "BodyID": new_value['BodyID'],
                "OnStation": new_value['OnStation'],
                "OnPlanet": new_value['OnPlanet']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has deployed their dropship at {new_value['StarSystem']}, {new_value['Body']}).")

        if log_event == 'Embark':
            embark_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "SRV": new_value['SRV'],
                "Taxi": new_value['Taxi'],
                "Multicrew": new_value['Multicrew'],
                "ID": new_value['ID'],
                "StarSystem": new_value['StarSystem'],
                "SystemAddress": new_value['SystemAddress'],
                "Body": new_value['Body'],
                "BodyID": new_value['BodyID'],
                "OnStation": new_value['OnStation'],
                "OnPlanet": new_value['OnPlanet'],
                "StationName": new_value.get('StationName', None),
                "StationType": new_value['StationType'],
                "MarketID": new_value['MarketID']
            }
            if new_value['SRV'] or new_value['Taxi'] or new_value['Multicrew']:
                handle_conversation(client, commanderName, f"(Commander {commanderName} has embarked in an SRV, taxi, or multicrew ship at {new_value['StarSystem']}, {new_value['Body']}).")
            else:
                handle_conversation(client, commanderName, f"(Commander {commanderName} has embarked and is back on board).")

        if log_event == 'FCMaterials':
            fc_materials_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "MarketID": new_value['MarketID'],
                "CarrierName": new_value['CarrierName'],
                "CarrierID": new_value['CarrierID'],
                "Items": new_value['Items']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has managed fleet carrier materials: {new_value}).")

        if log_event == 'LoadoutEquipModule':
            loadout_equip_module_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "SuitID": new_value['SuitID'],
                "SuitName": new_value['SuitName'],
                "SlotName": new_value['SlotName'],
                "LoadoutID": new_value['LoadoutID'],
                "LoadoutName": new_value['LoadoutName'],
                "ModuleName": new_value['ModuleName'],
                "SuitModuleID": new_value['SuitModuleID'],
                "Class": new_value['Class'],
                "WeaponMods": new_value.get('WeaponMods', [])
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has equipped a module in suit loadout {new_value['SuitName']} - {new_value['LoadoutName']}).")

        if log_event == 'LoadoutRemoveModule':
            loadout_remove_module_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "SuitID": new_value['SuitID'],
                "SuitName": new_value['SuitName'],
                "SlotName": new_value['SlotName'],
                "LoadoutID": new_value['LoadoutID'],
                "LoadoutName": new_value['LoadoutName'],
                "ModuleName": new_value['ModuleName'],
                "SuitModuleID": new_value['SuitModuleID'],
                "Class": new_value['Class'],
                "WeaponMods": new_value.get('WeaponMods', [])
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has removed a module from suit loadout {new_value['SuitName']} - {new_value['LoadoutName']}).")

        if log_event == 'RenameSuitLoadout':
            rename_suit_loadout_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "SuitID": new_value['SuitID'],
                "SuitName": new_value['SuitName'],
                "LoadoutID": new_value['LoadoutID'],
                "Loadoutname": new_value['Loadoutname']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has renamed a suit loadout to {new_value['Loadoutname']} in suit {new_value['SuitName']}).")

        if log_event == 'ScanOrganic':
            scan_organic_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "ScanType": new_value['ScanType'],
                "Genus": new_value['Genus'],
                "Genus_Localised": new_value['Genus_Localised'],
                "Species": new_value['Species'],
                "Species_Localised": new_value['Species_Localised'],
                "Variant": new_value['Variant'],
                "Variant_Localised": new_value['Variant_Localised'],
                "SystemAddress": new_value['SystemAddress'],
                "Body": new_value['Body']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has scanned organic life: {new_value['Genus_Localised']} {new_value['Species_Localised']} - {new_value['Variant_Localised']} in {new_value['StarSystem']}, {new_value['Body']}).")

        if log_event == 'SellMicroResources':
            sell_micro_resources_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "MicroResources": new_value['MicroResources'],
                "Price": new_value['Price'],
                "MarketID": new_value['MarketID']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has sold micro resources: {new_value}).")

        if log_event == 'SellOrganicData':
            sell_organic_data_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "MarketID": new_value['MarketID'],
                "BioData": new_value['BioData']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has sold organic data: {new_value}).")

        if log_event == 'SellWeapon':
            sell_weapon_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Name": new_value['Name'],
                "Name_Localised": new_value.get('Name_Localised', None),
                "SuitModuleID": new_value['SuitModuleID'],
                "Class": new_value['Class'],
                "WeaponMods": new_value.get('WeaponMods', [])
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has sold a weapon: {new_value['Name']}).")

        if log_event == 'ShipLocker':
            ship_locker_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Items": new_value['Items'],
                "Components": new_value['Components'],
                "Consumables": new_value['Consumables'],
                "Data": new_value['Data']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has accessed ship locker: {new_value}).")

        if log_event == 'SwitchSuitLoadout':
            switch_suit_loadout_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "SuitID": new_value['SuitID'],
                "SuitName": new_value['SuitName'],
                "SuitMods": new_value.get('SuitMods', []),
                "LoadoutID": new_value['LoadoutID'],
                "LoadoutName": new_value['LoadoutName'],
                "Modules": new_value['Modules']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has switched to suit loadout: {new_value['SuitName']} - {new_value['LoadoutName']}).")

        if log_event == 'TransferMicroResources':
            transfer_micro_resources_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Transfers": new_value['Transfers']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has transferred micro resources: {new_value}).")

        if log_event == 'TradeMicroResources':
            trade_micro_resources_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Offered": new_value['Offered'],
                "Received": new_value['Received'],
                "Count": new_value['Count'],
                "MarketID": new_value['MarketID']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has traded micro resources: Offered {new_value['Offered']} - Received {new_value['Received']}).")

        if log_event == 'UpgradeSuit':
            upgrade_suit_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Name": new_value['Name'],
                "Name_Localised": new_value.get('Name_Localised', None),
                "SuitID": new_value['SuitID'],
                "Class": new_value['Class'],
                "Cost": new_value['Cost'],
                "Resources": new_value['Resources']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has upgraded a suit: {new_value['Name']}).")

        if log_event == 'UpgradeSuit':
            upgrade_suit_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Name": new_value['Name'],
                "Name_Localised": new_value.get('Name_Localised', None),
                "SuitID": new_value['SuitID'],
                "Class": new_value['Class'],
                "Cost": new_value['Cost'],
                "Resources": new_value['Resources']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has upgraded a suit: {new_value['Name']}).")

        if log_event == 'UpgradeWeapon':
            upgrade_weapon_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Name": new_value['Name'],
                "Name_Localised": new_value.get('Name_Localised', None),
                "SuitModuleID": new_value['SuitModuleID'],
                "Class": new_value['Class'],
                "Cost": new_value['Cost'],
                "Resources": new_value['Resources']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has upgraded a weapon: {new_value['Name']}).")

        if log_event == 'UseConsumable':
            use_consumable_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Name": new_value['Name'],
                "Type": new_value['Type']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has used a consumable: {new_value['Name']}).")

        # Other Events:
        if log_event == 'AfmuRepairs':
            afmu_repairs_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Module": new_value['Module'],
                "Module_Localised": new_value.get('Module_Localised', None),
                "FullyRepaired": new_value['FullyRepaired'],
                "Health": new_value['Health']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has conducted repairs on {new_value['Module']}.)")

        if log_event == 'ApproachSettlement':
            approach_settlement_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Name": new_value['Name'],
                "MarketID": new_value['MarketID'],
                "Latitude": new_value['Latitude'],
                "Longitude": new_value['Longitude'],
                "SystemAddress": new_value['SystemAddress'],
                "BodyID": new_value['BodyID'],
                "BodyName": new_value['BodyName']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} is approaching settlement {new_value['Name']}.)")

        if log_event == 'ChangeCrewRole':
            change_crew_role_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Role": new_value['Role'],
                "Telepresence": new_value['Telepresence']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has changed crew role to {new_value['Role']}.)")

        if log_event == 'CockpitBreached':
            cockpit_breached_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has experienced a cockpit breach.)")

        if log_event == 'CommitCrime':
            commit_crime_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "CrimeType": new_value['CrimeType'],
                "Faction": new_value['Faction'],
                "Victim": new_value.get('Victim', None),
                "Fine": new_value.get('Fine', None),
                "Bounty": new_value.get('Bounty', None)
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has committed {new_value['CrimeType']} against {new_value['Victim'] if 'Victim' in new_value else new_value['Faction']}.)")

        if log_event == 'Continued':
            continued_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Part": new_value['Part']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has continued {new_value['Part']}.)")

        if log_event == 'CrewLaunchFighter':
            crew_launch_fighter_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Crew": new_value['Crew'],
                "ID": new_value['ID'],
                "Telepresence": new_value['Telepresence']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has launched a fighter with ID {new_value['ID']}.)")

        if log_event == 'CrewMemberJoins':
            crew_member_joins_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Crew": new_value['Crew'],
                "Telepresence": new_value['Telepresence']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has a new crew member {new_value['Crew']}.)")

        if log_event == 'CrewMemberQuits':
            crew_member_quits_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Crew": new_value['Crew'],
                "Telepresence": new_value['Telepresence']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has lost crew member {new_value['Crew']}.)")

        if log_event == 'CrewMemberRoleChange':
            crew_member_role_change_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Crew": new_value['Crew'],
                "Role": new_value['Role'],
                "Telepresence": new_value['Telepresence']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has changed crew member {new_value['Crew']}'s role to {new_value['Role']}.)")

        if log_event == 'CrimeVictim':
            crime_victim_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Offender": new_value['Offender'],
                "CrimeType": new_value['CrimeType'],
                "Fine_or_Bounty": new_value.get('Fine_or_Bounty', None)
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has been victimized by {new_value['Offender']} for {new_value['CrimeType']}.)")

        if log_event == 'DatalinkScan':
            datalink_scan_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Message": new_value['Message']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has scanned a datalink with message: {new_value['Message']}.)")

        if log_event == 'DatalinkVoucher':
            datalink_voucher_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Reward": new_value['Reward'],
                "VictimFaction": new_value['VictimFaction'],
                "PayeeFaction": new_value['PayeeFaction']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has received a datalink voucher worth {new_value['Reward']}.)")

        if log_event == 'DataScanned':
            data_scanned_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Type": new_value['Type']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has scanned data of type: {new_value['Type']}.)")

        if log_event == 'DockFighter':
            dock_fighter_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "ID": new_value['ID']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has docked the fighter with ID {new_value['ID']}.)")

        if log_event == 'DockSRV':
            dock_srv_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "ID": new_value['ID'],
                "SRVType": new_value['SRVType']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has docked the SRV with ID {new_value['ID']}.)")

        if log_event == 'EndCrewSession':
            end_crew_session_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "OnCrime": new_value['OnCrime'],
                "Telepresence": new_value['Telepresence']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has ended a crew session.)")

        if log_event == 'FighterRebuilt':
            fighter_rebuilt_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Loadout": new_value['Loadout'],
                "ID": new_value['ID']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has rebuilt fighter {new_value['ID']}.)")

        if log_event == 'FuelScoop':
            fuel_scoop_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Scooped": new_value['Scooped'],
                "Total": new_value['Total']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has scooped {new_value['Scooped']} fuel, total {new_value['Total']}.)")

        if log_event == 'Friends':
            friends_data = {
                "timestamp": new_value['timestamp'],
                "event": log_event,
                "Status": new_value['Status'],
                "Name": new_value['Name']
            }
            handle_conversation(client, commanderName, f"(Commander {commanderName} has {new_value['Status']} friend request from {new_value['Name']}.)")


        if log_event == 'JetConeBoost':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has executed a jet cone boost. Boost Value: {new_value['BoostValue']})")

        if log_event == 'JetConeDamage':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has received damage from a jet cone. Module: {new_value['Module']})")

        if log_event == 'JoinACrew':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has joined a crew. Captain: {new_value['Captain']}, Telepresence: {new_value['Telepresence']})")

        if log_event == 'KickCrewMember':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has kicked a crew member. Crew: {new_value['Crew']}, OnCrime: {new_value['OnCrime']}, Telepresence: {new_value['Telepresence']})")

        if log_event == 'LaunchDrone':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has launched a drone. Type: {new_value['Type']})")

        if log_event == 'LaunchFighter':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has launched a fighter. Loadout: {new_value['Loadout']}, ID: {new_value['ID']}, Player Controlled: {new_value['PlayerControlled']})")

        if log_event == 'LaunchSRV':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has launched an SRV. Loadout: {new_value['Loadout']}, ID: {new_value['ID']}, SRV Type: {new_value['SRVType']})")

        if log_event == 'ModuleInfo':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has received module info. This event may require additional parsing.)")

        if log_event == 'Music':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has triggered music playback. Track: {new_value['MusicTrack']})")

        if log_event == 'NpcCrewPaidWage':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has paid an NPC crew member. NPC Crew ID: {new_value['NpcCrewId']}, Name: {new_value['NpcCrewName']}, Amount: {new_value['Amount']})")

        if log_event == 'NpcCrewRank':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has received NPC crew rank update. NPC Crew ID: {new_value['NpcCrewId']}, Name: {new_value['NpcCrewName']}, Combat Rank: {new_value['RankCombat']})")

        if log_event == 'Promotion':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has received a promotion. Combat: {new_value.get('Combat', 'N/A')}, Trade: {new_value.get('Trade', 'N/A')}, Explore: {new_value.get('Explore', 'N/A')}, CQC: {new_value.get('CQC', 'N/A')}, Federation: {new_value.get('Federation', 'N/A')}, Empire: {new_value.get('Empire', 'N/A')})")

        if log_event == 'ProspectedAsteroid':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has prospected an asteroid. Materials: {new_value['Materials']}, Content: {new_value['Content']}, Motherlode Material: {new_value.get('MotherlodeMaterial', 'N/A')}, Remaining: {new_value['Remaining']})")

        if log_event == 'QuitACrew':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has quit a crew. Captain: {new_value['Captain']}, Telepresence: {new_value['Telepresence']})")

        if log_event == 'RebootRepair':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has initiated a reboot/repair. Modules: {new_value['Modules']})")

        if log_event == 'ReceiveText':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has received a text message. From: {new_value['From']}, Message: {new_value['Message']}, Channel: {new_value['Channel']})")

        if log_event == 'RepairDrone':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has repaired using a drone. Hull Repaired: {new_value['HullRepaired']}, Cockpit Repaired: {new_value['CockpitRepaired']}, Corrosion Repaired: {new_value['CorrosionRepaired']})")

        if log_event == 'ReservoirReplenished':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has replenished reservoir. Main Fuel: {new_value['FuelMain']}, Reservoir Fuel: {new_value['FuelReservoir']})")

        if log_event == 'Resurrect':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has resurrected. Option: {new_value['Option']}, Cost: {new_value['Cost']}, Bankrupt: {new_value['Bankrupt']})")

        if log_event == 'Scanned':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has been scanned. Scan Type: {new_value['ScanType']})")

        if log_event == 'SelfDestruct':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has initiated self destruct.)")

        if log_event == 'SendText':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has sent a text message. To: {new_value['To']}, Message: {new_value['Message']})")

        if log_event == 'Shutdown':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has initiated a shutdown.)")

        if log_event == 'Synthesis':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has performed synthesis. Name: {new_value['Name']}, Materials: {new_value['Materials']})")

        if log_event == 'SystemsShutdown':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has shut down systems.)")

        if log_event == 'USSDrop':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has encountered a USS drop. Type: {new_value['USSType']}, Threat: {new_value['USSThreat']}, Market ID: {new_value.get('MarketID', 'N/A')})")

        if log_event == 'VehicleSwitch':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has switched vehicle. To: {new_value['To']})")

        if log_event == 'WingAdd':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has added to a wing. Name: {new_value['Name']})")

        if log_event == 'WingInvite':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has received a wing invite. Name: {new_value['Name']})")

        if log_event == 'WingJoin':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has joined a wing. Other Members: {new_value['Others']})")

        if log_event == 'WingLeave':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has left a wing.)")

        if log_event == 'CargoTransfer':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has transferred cargo. Transfers: {new_value['Transfers']})")

        if log_event == 'SupercruiseDestinationDrop':
            handle_conversation(client, commanderName, f"(Commander {commanderName} has dropped out at a supercruise destination. Type: {new_value['Type']}, Threat: {new_value['Threat']}, Market ID: {new_value.get('MarketID', 'N/A')})")
        """
    # Update previous status
    previous_status = current_status
    #print('checkForJournalUpdates end')

v = Voice()
keys = EDKeys()
def main():
    global client, v, keys, aiModel, handle
    if handle:
        win32gui.SetForegroundWindow(handle)  # give focus to ED

    # Load or prompt for configuration
    apiKey, useOpenrouter, commanderName = load_or_prompt_config()

    print('loading keys')
    

    # Now you can use api_key and use_openrouter in your script
    # gets API Key from config.json
    client = OpenAI(
      base_url = "https://openrouter.ai/api/v1" if useOpenrouter else "https://api.openai.com/v1",
      api_key=apiKey,
    )
    # openrotuer model naming convention
    if useOpenrouter:
        aiModel = f"openai/{aiModel}"

    print(f"Initializing CMDR {commanderName}'s personal AI...\n")
    print("API Key: Loaded")
    print(f"Using Openrouter: {useOpenrouter}")
    print(f"Current model: {aiModel}")
    print(f"Current backstory: {backstory}")
    print("\nBasic configuration complete.\n")
    print("Loading voice interface...")

    # TTS Setup
    v.set_on()

    # STT Setup
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="small", help="Model to use",
                        choices=["tiny", "base", "small", "medium", "large"])
    parser.add_argument("--non_english", action='store_true',
                        help="Don't use the english model.")
    parser.add_argument("--energy_threshold", default=1000,
                        help="Energy level for mic to detect.", type=int)
    parser.add_argument("--record_timeout", default=15,
                        help="How real time the recording is in seconds.", type=float)
    parser.add_argument("--phrase_timeout", default=5,
                        help="How much empty space between recordings before we "
                             "consider it a new line in the transcription.", type=float)
    if 'linux' in platform:
        parser.add_argument("--default_microphone", default='pulse',
                            help="Default microphone name for SpeechRecognition. "
                                 "Run this with 'list' to view available Microphones.", type=str)
    args = parser.parse_args()

    # The last time a recording was retrieved from the queue.
    phrase_time = datetime.utcnow()
    # Thread safe Queue for passing data from the threaded recording callback.
    data_queue = Queue()
    # We use SpeechRecognizer to record our audio because it has a nice feature where it can detect when speech ends.
    recorder = sr.Recognizer()
    recorder.energy_threshold = args.energy_threshold
    # Definitely do this, dynamic energy compensation lowers the energy threshold dramatically to a point where the SpeechRecognizer never stops recording.
    recorder.dynamic_energy_threshold = False

    # Important for linux users.
    # Prevents permanent application hang and crash by using the wrong Microphone
    if 'linux' in platform:
        mic_name = args.default_microphone
        if not mic_name or mic_name == 'list':
            print("Available microphone devices are: ")
            for index, name in enumerate(sr.Microphone.list_microphone_names()):
                print(f"Microphone with name \"{name}\" found")
            return
        else:
            for index, name in enumerate(sr.Microphone.list_microphone_names()):
                if mic_name in name:
                    source = sr.Microphone(sample_rate=16000, device_index=index)
                    break
    else:
        source = sr.Microphone(sample_rate=16000)

    # Load / Download model
    model = args.model
    if not args.non_english:
        model = model + ".en"
    audio_model = whisper.load_model(model)

    record_timeout = args.record_timeout
    phrase_timeout = args.phrase_timeout

    transcription = ['']

    with source:
        recorder.adjust_for_ambient_noise(source)

    def record_callback(_, audio:sr.AudioData) -> None:
        """
        Threaded callback function to receive audio data when recordings finish.
        audio: An AudioData containing the recorded bytes.
        """
        #print('record callback')
        # Grab the raw bytes and push it into the thread safe queue.
        data = audio.get_raw_data()
        data_queue.put(data)

    # Create a background thread that will pass us raw audio bytes.
    # We could do this manually but SpeechRecognizer provides a nice helper.
    recorder.listen_in_background(source, record_callback, phrase_time_limit=record_timeout)

    # Cue the user that we're ready to go.
    print("Voice interface ready.\n")

    counter = 0

    while True:
        try:
            #print('while whisper')
            now = datetime.utcnow()
            # Pull raw recorded audio from the queue.
            if not data_queue.empty():
                #print('while whisper if')
                phrase_complete = False
                # If enough time has passed between recordings, consider the phrase complete.
                # Clear the current working audio buffer to start over with the new data.
                if phrase_time and now - phrase_time > timedelta(seconds=phrase_timeout):
                    phrase_complete = True
                # This is the last time we received new audio data from the queue.
                phrase_time = now

                # Combine audio data from queue
                audio_data = b''.join(data_queue.queue)
                data_queue.queue.clear()

                # Convert in-ram buffer to something the model can use directly without needing a temp file.
                # Convert data from 16 bit wide integers to floating point with a width of 32 bits.
                # Clamp the audio stream frequency to a PCM wavelength compatible default of 32768hz max.
                audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

                # Read the transcription.
                result = audio_model.transcribe(audio_np, fp16=torch.cuda.is_available())
                text = result['text'].strip()

                # If we detected a pause between recordings, add a new item to our transcription.
                # Otherwise edit the existing one.
                if phrase_complete:
                    transcription.append(text)

                    handle_conversation(client, commanderName, text)

                else:
                    transcription[-1] = text

                # Flush stdout.
                print('', end='', flush=True)

            else:
                #print('while whisper else')
                counter += 1
                if counter % 5 == 0:
                    checkForJournalUpdates(client, commanderName)

                # Infinite loops are bad for processors, must sleep.
                sleep(0.25)
        except KeyboardInterrupt:
            break

    print("\n\nConversation:")
    for line in conversation:
        print(line)

    # Teardown TTS
    v.quit()


if __name__ == "__main__":
    main()
