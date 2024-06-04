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


    # Update previous status
    previous_status = current_status
    #print('checkForJournalUpdates end')

v = Voice()
keys = EDKeys()
def main():
    global client, v, keys, aiModel
    if handle != None:
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
