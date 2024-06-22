import base64
from threading import Thread
import kthread
import queue
import pyttsx3
from time import sleep
import keyboard

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
import io
from pathlib import Path

import AIActions
import STT
import TTS

# Add the parent directory to sys.path
parent_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(parent_dir))

from Voice import *
from EDKeys import *
from EDJournal import *

client = None
sttClient = None
ttsClient = None

aiActions = AIActions.AIActions()

# You can change some settings here
aiModel = "gpt-4o"
backstory = """I am Commander {commander_name}. You are the onboard AI of my starship. \
You will be addressed as 'Computer'. Acknowledge given orders. \
You possess extensive knowledge and can provide detailed and accurate information on a wide range of topics, \
including galactic navigation, ship status, the current system, and more. \
Do not inform about my ship status and my location unless it's relevant or requested by me. \
Guide and support me with witty and intelligent commentary. \
Provide clear mission briefings, sarcastic comments, and humorous observations. Answer within 3 sentences. \
Advance the narrative involving bounty hunting. \
I am a broke bounty hunter who can barely pay the fuel."""

conversationLength = 25
conversation = []

startupEvents = {
    "Cargo": "Commander {commanderName} has updated their cargo inventory.",
    "ClearSavedGame": "Commander {commanderName} has reset their game.",
    "LoadGame": "Commander {commanderName} has loaded the game.",
    "NewCommander": "Commander {commanderName} has started a new game.",
    "Materials": "Commander {commanderName} has updated their materials inventory.",
    "Missions": "Commander {commanderName} has updated their missions.",
    "Progress": "Commander {commanderName} has made progress in various activities.",
    "Rank": "Commander {commanderName} has updated their ranks.",
    "Reputation": "Commander {commanderName} has updated their reputation.",
    "Statistics": "Commander {commanderName} has updated their statistics."
}
powerplayEvents = {
    "PowerplayCollect": "Commander {commanderName} collected powerplay commodities.",
    "PowerplayDefect": "Commander {commanderName} defected from one power to another.",
    "PowerplayDeliver": "Commander {commanderName} delivered powerplay commodities.",
    "PowerplayFastTrack": "Commander {commanderName} fast-tracked powerplay allocation.",
    "PowerplayJoin": "Commander {commanderName} joined a power.",
    "PowerplayLeave": "Commander {commanderName} left a power.",
    "PowerplaySalary": "Commander {commanderName} received salary payment from a power.",
    "PowerplayVote": "Commander {commanderName} voted for system expansion.",
    "PowerplayVoucher": "Commander {commanderName} received payment for powerplay combat."
}
squadronEvents = {
    "AppliedToSquadron": "Commander {commanderName} applied to a squadron.",
    "DisbandedSquadron": "Commander {commanderName} disbanded a squadron.",
    "InvitedToSquadron": "Commander {commanderName} was invited to a squadron.",
    "JoinedSquadron": "Commander {commanderName} joined a squadron.",
    "KickedFromSquadron": "Commander {commanderName} was kicked from a squadron.",
    "LeftSquadron": "Commander {commanderName} left a squadron.",
    "SharedBookmarkToSquadron": "Commander {commanderName} shared a bookmark with a squadron.",
    "SquadronCreated": "A squadron was created by commander {commanderName}.",
    "SquadronDemotion": "Commander {commanderName} was demoted in a squadron.",
    "SquadronPromotion": "Commander {commanderName} was promoted in a squadron.",
    "SquadronStartup": "Commander {commanderName} is a member of a squadron (startup).",
    "WonATrophyForSquadron": "Commander {commanderName} won a trophy for a squadron."
}

explorationEvents = {
    "CodexEntry": "Commander {commanderName} has logged a Codex entry.",
    "DiscoveryScan": "Commander {commanderName} has performed a discovery scan.",
    "Scan": "Commander {commanderName} has conducted a scan."
}
tradeEvents = {
    "Trade": "Commander {commanderName} has performed a trade.",
    "AsteroidCracked": "Commander {commanderName} has cracked an asteroid.",
    "BuyTradeData": "Commander {commanderName} has bought trade data.",
    "CollectCargo": "Commander {commanderName} has collected cargo.",
    "EjectCargo": "Commander {commanderName} has ejected cargo.",
    "MarketBuy": "Commander {commanderName} has bought market goods.",
    "MarketSell": "Commander {commanderName} has sold market goods.",
    "MiningRefined": "Commander {commanderName} has refined a resource."
}
stationServiceEvents = {
    "StationServices": "Commander {commanderName} has accessed station services.",
    "BuyAmmo": "Commander {commanderName} has bought ammunition.",
    "BuyDrones": "Commander {commanderName} has bought drones.",
    "CargoDepot": "Commander {commanderName} has completed a cargo depot operation.",
    "ClearImpound": "Commander {commanderName} has cleared an impound.",
    "CommunityGoal": "Commander {commanderName} has engaged in a community goal.",
    "CommunityGoalDiscard": "Commander {commanderName} has discarded a community goal.",
    "CommunityGoalJoin": "Commander {commanderName} has joined a community goal.",
    "CommunityGoalReward": "Commander {commanderName} has received a reward for a community goal.",
    "CrewAssign": "Commander {commanderName} has assigned a crew member.",
    "CrewFire": "Commander {commanderName} has fired a crew member.",
    "CrewHire": "Commander {commanderName} has hired a crew member.",
    "EngineerContribution": "Commander {commanderName} has made a contribution to an engineer.",
    "EngineerCraft": "Commander {commanderName} has crafted a blueprint at an engineer.",
    "EngineerLegacyConvert": "Commander {commanderName} has converted a legacy blueprint at an engineer.",
    "EngineerProgress": "Commander {commanderName} has progressed with an engineer.",
    "FetchRemoteModule": "Commander {commanderName} has fetched a remote module.",
    "Market": "Commander {commanderName} has interacted with a market.",
    "MassModuleStore": "Commander {commanderName} has mass stored modules.",
    "MaterialTrade": "Commander {commanderName} has conducted a material trade.",
    "MissionAbandoned": "Commander {commanderName} has abandoned a mission.",
    "MissionAccepted": "Commander {commanderName} has accepted a mission.",
    "MissionCompleted": "Commander {commanderName} has completed a mission.",
    "MissionFailed": "Commander {commanderName} has failed a mission.",
    "MissionRedirected": "Commander {commanderName} has redirected a mission.",
    "ModuleBuy": "Commander {commanderName} has bought a module.",
    "ModuleRetrieve": "Commander {commanderName} has retrieved a module.",
    "ModuleSell": "Commander {commanderName} has sold a module.",
    "ModuleSellRemote": "Commander {commanderName} has sold a remote module.",
    "ModuleStore": "Commander {commanderName} has stored a module.",
    "ModuleSwap": "Commander {commanderName} has swapped modules.",
    "Outfitting": "Commander {commanderName} has visited an outfitting station.",
    "PayBounties": "Commander {commanderName} has paid bounties.",
    "PayFines": "Commander {commanderName} has paid fines.",
    "PayLegacyFines": "Commander {commanderName} has paid legacy fines.",
    "RedeemVoucher": "Commander {commanderName} has redeemed a voucher.",
    "RefuelAll": "Commander {commanderName} has refueled all.",
    "RefuelPartial": "Commander {commanderName} has partially refueled.",
    "Repair": "Commander {commanderName} has repaired.",
    "RepairAll": "Commander {commanderName} has repaired all.",
    "RestockVehicle": "Commander {commanderName} has restocked vehicle.",
    "ScientificResearch": "Commander {commanderName} has conducted scientific research.",
    "Shipyard": "Commander {commanderName} has visited a shipyard.",
    "ShipyardNew": "Commander {commanderName} has acquired a new ship.",
    "ShipyardSell": "Commander {commanderName} has sold a ship.",
    "ShipyardSwap": "Commander {commanderName} has swapped ships.",
    "ShipyardTransfer": "Commander {commanderName} has transfersd a ship.",
    "ShipyardBuy": "Commander {commanderName} has bought a ship.",
    "StoredShips": "Commander {commanderName} has stored ships.",
    "StoredModules": "Commander {commanderName} has stored modules.",
    "TechnologyBroker": "Commander {commanderName} has accessed a technology broker.",
    "Touchdown": "Commander {commanderName} has touched down on a planet surface.",
    "Undocked": "Commander {commanderName} has undocked from a station.",
    "Docked": "Commander {commanderName} has docked with a station.",
    "DockingRequested": "Commander {commander_name} has sent a request to dock with a station.",
    "DockingGranted": "Commander {commander_name}'s request to dock with a station has been granted.",
    "DockingDenied": "Commander {commander_name}'s request to dock with a station has been denied.",
    "DockingComplete": "Commander {commander_name} has docked with a station",
    "DockingTimeout": "Commander {commander_name}'s request to dock with a station has timed out.",
}
carrierEvents = {
    "CarrierJump": "Commander {commanderName} has performed a carrier jump.",
    "CarrierBuy": "Commander {commanderName} has purchased a carrier.",
    "CarrierStats": "Commander {commanderName} has updated carrier stats.",
    "CarrierJumpRequest": "Commander {commanderName} has requested a carrier jump.",
    "CarrierDecommission": "Commander {commanderName} has decommissioned a carrier.",
    "CarrierCancelDecommission": "Commander {commanderName} has canceled the decommission of a carrier.",
    "CarrierBankTransfer": "Commander {commanderName} has performed a bank transfer for carrier.",
    "CarrierDepositFuel": "Commander {commanderName} has deposited fuel to carrier.",
    "CarrierCrewServices": "Commander {commanderName} has performed crew services on carrier.",
    "CarrierFinance": "Commander {commanderName} has reviewed finance details for carrier.",
    "CarrierShipPack": "Commander {commanderName} has managed ship pack for carrier.",
    "CarrierModulePack": "Commander {commanderName} has managed module pack for carrier.",
    "CarrierTradeOrder": "Commander {commanderName} has placed a trade order on carrier.",
    "CarrierDockingPermission": "Commander {commanderName} has updated docking permissions for carrier.",
    "CarrierNameChanged": "Commander {commanderName} has changed the name of carrier.",
    "CarrierJumpCancelled": "Commander {commanderName} has canceled a jump request for carrier."
}
odysseyEvents = {
    'Backpack': "Commander {commanderName} has interacted with their backpack.",
    'BackpackChange': "Commander {commanderName} has changed items in their backpack.",
    'BookDropship': "Commander {commanderName} has booked a dropship.",
    'BookTaxi': "Commander {commanderName} has booked a taxi.",
    'BuyMicroResources': "Commander {commanderName} has bought micro resources.",
    'BuySuit': "Commander {commanderName} has bought a suit.",
    'BuyWeapon': "Commander {commanderName} has bought a weapon.",
    'CancelDropship': "Commander {commanderName} has cancelled a dropship booking.",
    'CancelTaxi': "Commander {commanderName} has cancelled a taxi booking.",
    'CollectItems': "Commander {commanderName} has collected items.",
    'CreateSuitLoadout': "Commander {commanderName} has created a suit loadout.",
    'DeleteSuitLoadout': "Commander {commanderName} has deleted a suit loadout.",
    'Disembark': "Commander {commanderName} has disembarked.",
    'DropItems': "Commander {commanderName} has dropped items.",
    'DropShipDeploy': "Commander {commanderName} has deployed their dropship.",
    'Embark': "Commander {commanderName} has embarked.",
    'FCMaterials': "Commander {commanderName} has managed fleet carrier materials.",
    'LoadoutEquipModule': "Commander {commanderName} has equipped a module in suit loadout.",
    'LoadoutRemoveModule': "Commander {commanderName} has removed a module from suit loadout.",
    'RenameSuitLoadout': "Commander {commanderName} has renamed a suit loadout.",
    'ScanOrganic': "Commander {commanderName} has scanned organic life.",
    'SellMicroResources': "Commander {commanderName} has sold micro resources.",
    'SellOrganicData': "Commander {commanderName} has sold organic data.",
    'SellWeapon': "Commander {commanderName} has sold a weapon.",
    'ShipLocker': "Commander {commanderName} has accessed ship locker.",
    'SwitchSuitLoadout': "Commander {commanderName} has switched to suit loadout.",
    'TransferMicroResources': "Commander {commanderName} has transferred micro resources.",
    'TradeMicroResources': "Commander {commanderName} has traded micro resources.",
    'UpgradeSuit': "Commander {commanderName} has upgraded a suit.",
    'UpgradeWeapon': "Commander {commanderName} has upgraded a weapon.",
    'UseConsumable': "Commander {commanderName} has used a consumable."
}
otherEvents = {
    "AfmuRepairs": "Commander {commanderName} has conducted repairs.",
    "ApproachSettlement": "Commander {commanderName} is approaching settlement.",
    "ChangeCrewRole": "Commander {commanderName} has changed crew role.",
    "CockpitBreached": "Commander {commanderName} has experienced a cockpit breach.",
    "CommitCrime": "Commander {commanderName} has committed a crime.",
    "Continued": "Commander {commanderName} has continued.",
    "CrewLaunchFighter": "Commander {commanderName} has launched a fighter.",
    "CrewMemberJoins": "Commander {commanderName} has a new crew member.",
    "CrewMemberQuits": "Commander {commanderName} has lost a crew member.",
    "CrewMemberRoleChange": "Commander {commanderName} has changed a crew member's role.",
    "CrimeVictim": "Commander {commanderName} has been victimized.",
    "DatalinkScan": "Commander {commanderName} has scanned a datalink.",
    "DatalinkVoucher": "Commander {commanderName} has received a datalink voucher.",
    "DataScanned": "Commander {commanderName} has scanned data.",
    "DockFighter": "Commander {commanderName} has docked a fighter.",
    "DockSRV": "Commander {commanderName} has docked an SRV.",
    "EndCrewSession": "Commander {commanderName} has ended a crew session.",
    "FighterRebuilt": "Commander {commanderName} has rebuilt a fighter.",
    "FuelScoop": "Commander {commanderName} has scooped fuel.",
    "Friends": "Commander {commanderName} has a friend request.",
    "Music": "Commander {commanderName} has triggered music playback.",
    "JetConeBoost": "Commander {commanderName} has executed a jet cone boost.",
    "JetConeDamage": "Commander {commanderName} has received damage from a jet cone.",
    "JoinACrew": "Commander {commanderName} has joined a crew.",
    "KickCrewMember": "Commander {commanderName} has kicked a crew member.",
    "LaunchDrone": "Commander {commanderName} has launched a drone.",
    "LaunchFighter": "Commander {commanderName} has launched a fighter.",
    "LaunchSRV": "Commander {commanderName} has launched an SRV.",
    "ModuleInfo": "Commander {commanderName} has received module info.",
    "NpcCrewPaidWage": "Commander {commanderName} has paid an NPC crew member.",
    "NpcCrewRank": "Commander {commanderName} has received NPC crew rank update.",
    "Promotion": "Commander {commanderName} has received a promotion.",
    "ProspectedAsteroid": "Commander {commanderName} has prospected an asteroid.",
    "QuitACrew": "Commander {commanderName} has quit a crew.",
    "RebootRepair": "Commander {commanderName} has initiated a reboot/repair.",
    "ReceiveText": "Commander {commanderName} has received a text message.",
    "RepairDrone": "Commander {commanderName} has repaired using a drone.",
    "ReservoirReplenished": "Commander {commanderName} has replenished reservoir.",
    "Resurrect": "Commander {commanderName} has resurrected.",
    "Scanned": "Commander {commanderName} has been scanned.",
    "SelfDestruct": "Commander {commanderName} has initiated self destruct.",
    "SendText": "Commander {commanderName} has sent a text message.",
    "Shutdown": "Commander {commanderName} has initiated a shutdown.",
    "Synthesis": "Commander {commanderName} has performed synthesis.",
    "SystemsShutdown": "Commander {commanderName} has shut down systems.",
    "USSDrop": "Commander {commanderName} has encountered a USS drop.",
    "VehicleSwitch": "Commander {commanderName} has switched vehicle.",
    "WingAdd": "Commander {commanderName} has added to a wing.",
    "WingInvite": "Commander {commanderName} has received a wing invite.",
    "WingJoin": "Commander {commanderName} has joined a wing.",
    "WingLeave": "Commander {commanderName} has left a wing.",
    "CargoTransfer": "Commander {commanderName} has transferred cargo.",
    "SupercruiseDestinationDrop": "Commander {commanderName} has dropped out at a supercruise destination."
}
allGameEvents = {
    **explorationEvents,
    **tradeEvents,
    **stationServiceEvents,
    **carrierEvents,
    **odysseyEvents,
    **startupEvents,
    **powerplayEvents,
    **squadronEvents,
    **otherEvents
}


sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Print that flushes, subprocess can return info to GUI
def printFlush(message, arg=''):
    print(message, arg)
    sys.stdout.flush()

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
    tts_voice = input("Enter TTS Voice: ")
    key_binding = input("Push-to-talk button: ")
    game_events = input("Please enter game events in the format of Dict[str, Dict[str, bool]] ☺")

    return api_key, llm_api_key, llm_endpoint, vision_model_name, vision_endpoint, vision_api_key, stt_model_name, stt_api_key, stt_endpoint, tts_model_name, tts_api_key, tts_endpoint, commander_name, character, ai_model, alternative_stt_var, alternative_tts_var, tools_var, vision_var, ptt_var, tts_voice, key_binding, game_events

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
            tts_voice = config.get('tts_voice', '')
            key_binding = config.get('key_binding', '')
            game_events = config.get('game_events', '[]')
    else:
        api_key, llm_api_key, llm_endpoint, vision_model_name, vision_endpoint, vision_api_key, stt_model_name, stt_api_key, stt_endpoint, tts_model_name, tts_api_key, tts_endpoint, commander_name, character, ai_model, alternative_stt_var, alternative_tts_var, tools_var, vision_var, ptt_var, tts_voice, key_binding, game_events = prompt_for_config()
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
                'tts_voice': tts_voice,
                'key_binding': key_binding,
                'game_events': game_events,
            }, f)

    return api_key, llm_api_key, llm_endpoint, vision_model_name, vision_endpoint, vision_api_key, stt_model_name, stt_api_key, stt_endpoint, tts_model_name, tts_api_key, tts_endpoint, commander_name, character, model_name, alternative_stt_var, alternative_tts_var, tools_var, vision_var, ptt_var, tts_voice, key_binding, game_events

handle = win32gui.FindWindow(0, "Elite - Dangerous (CLIENT)")
def setGameWindowActive():
    global handle

    if handle:
        try:
            win32gui.SetForegroundWindow(handle)  # give focus to ED
        except:
            printFlush("Failed to set game window as active")

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
        return im
    else:
        printFlush('Window not found!')
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

def handle_conversation(client, commander_name, user_input):
    printFlush(f"CMDR: {user_input}")
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
    backstory.replace("{commander_name}", commander_name)}
    status = {"role": "user", "content": "(Ship status: " + json.dumps(filteredState) + ")"}
    system = {
        "role": "user",
        "content": (
            f"(Location: {get_system_info(filteredState['location'])})"
        )
    }

    # printFlush('location')
    # printFlush(get_system_info(filteredState['location']))
    # printFlush('faction')
    # printFlush(get_faction_info(filteredState['location']))
    # printFlush('stations')
    # printFlush(get_station_info(filteredState['location']))
    

    # Context for AI, consists of conversation history, ships status, information about current system and the user input
    return [systemPrompt]+[status, system]+conversation

useTools = False

def run_chat_model(client, commander_name, chat_prompt):
    global conversation
    # Make a request to OpenAI with the updated conversation
    #printFlush("messages:", chat_prompt)
    args = {
         "model": aiModel,
         "messages": chat_prompt,
     }
    if useTools:
        args["tools"] = aiActions.getToolsList()
    completion = client.chat.completions.create(**args)

    if hasattr(completion, 'error'):
        printFlush("completion with error:", completion)
        return

    # Add the model's response to the conversation
    conversation.append(completion.choices[0].message)
    conversation.pop(0) if len(conversation) > conversationLength else None

    # Get and print the model's response
    response_text = completion.choices[0].message.content
    if (response_text):
        printFlush(f"AI: {response_text}")

        tts.say(response_text)

    response_actions = completion.choices[0].message.tool_calls
    if (response_actions):
        for action in response_actions:
            printFlush(f"ACTION: {action.function.name} {action.function.arguments}")
            action_result = aiActions.runAction(action)
            conversation.append(action_result)
            while(len(conversation) > conversationLength):
                conversation.pop(0)
        run_chat_model(client, commander_name, prepare_chat_prompt(commander_name))

def getCurrentState():
    keysToFilterOut = ["time"]
    rawState = jn.ship_state()

    return {key: value for key, value in rawState.items() if key not in keysToFilterOut}

previous_status = None
def checkForJournalUpdates(client, commanderName, boot):
    #printFlush('checkForJournalUpdates is checking')
    global previous_status
    if boot:
        previous_status['extra_events'].clear()
        return

    def check_status_changes(prev_status, current_status, keys):
        changes = []
        for key in keys:
            if prev_status[key] != current_status[key]:
                changes.append((key, prev_status[key], current_status[key]))
        return changes

    relevant_status = [
        'type',
        'target',
        'location',
        'shieldsup',
        'under_attack',
        'type',
        'fuel_percent',
        'interdicted'
    ]
    current_status = getCurrentState()
    #printFlush('check_status_changes')
    changes = check_status_changes(previous_status, current_status, relevant_status)

    for change in changes:
        key, old_value, new_value = change
        #printFlush(f"{key} changed from {old_value} to {new_value}")

        # Events

        #if key == 'type':
        #    ## type event is written twice to EDJournal, we only want one interaction
        #    second_call = not second_call and True
        #    if second_call and old_value != None and new_value != None:
        #        handle_conversation(client, commanderName, f"(Commander {commanderName} just swapped Vessels, from {old_value} to {new_value})")

        if key == 'location':
            if new_value != None and old_value != None:
                handle_conversation(client, commanderName, f"(Commander {commanderName} has reached a new location: {new_value}. System details: {get_system_info(new_value)}).")
        if key == 'target':
            if new_value != None:
                handle_conversation(client, commanderName, f"(Commander {commanderName} has locked in a new jump destination: {new_value}. Inform about relevant system details: {get_system_info(new_value)})")
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
            if new_value <= 24 and current_status['type'] != None and old_value != 0 and new_value != 0:
                handle_conversation(client, commanderName, f"(Commander {commanderName}'s ship has less than 25% fuel reserves! Warn about immediate danger!)")
        if key == 'interdicted':
            handle_conversation(client, commanderName, f"(Commander {commanderName}'s ship is being interdicted! Warn about immediate danger, advise to run or to prepare for a fight!)")
        if key == 'cockpit_breached':
            if new_value == True:
                handle_conversation(client, commanderName, f"(Commander {commanderName}'s ship cockpit has been breached! Warn about immediate danger!)")
                jn.reset_items()
        """
        if key == 'status':
            if new_value == 'landed':
                #handle_conversation(client, commanderName, f"(Commander {commanderName} has landed the ship.)")
            elif new_value == 'liftoff':
                #handle_conversation(client, commanderName, f"(Commander {commanderName}'s ship has lifted off from the surface.)")
            elif new_value == 'destroyed':
                #handle_conversation(client, commanderName, f"(Commander {commanderName}'s ship has been destroyed. Express sympathy.)")
            elif new_value == 'resurrected':
                #handle_conversation(client, commanderName, f"(Commander {commanderName} has been released from hospital.)")
            elif new_value == 'approaching_settlement':
                #handle_conversation(client, commanderName, f"(Commander {commanderName} is approaching a settlement.)")
            elif new_value == 'self_destruct':
                #handle_conversation(client, commanderName, f"(Commander {commanderName}'s ship is self-destructing! Make sure it's not a mistake.)")

        """
    if current_status['extra_events'] and len(current_status['extra_events']) > 0:
        while current_status['extra_events']:
            item = current_status['extra_events'][0]  # Get the first item
            if 'event_content' in item:
                if item['event_content'].get('ScanType') == "AutoScan":
                    current_status['extra_events'].pop(0)
                    continue

                elif 'Message_Localised' in item['event_content'] and item['event_content']['Message_Localised'].startswith("Entered Channel:"):
                    current_status['extra_events'].pop(0)
                    continue
            if 'event_type' in item:
                if item.get('event_type') == 'Progress' or item.get('event_type') == 'Reputation' or item.get('event_type') == 'Rank' or item.get('event_type') == 'Backpack' or item.get('event_type') == 'Statistics' or item.get('event_type') == 'Missions' or item.get('event_type') == 'SquadronStartup':
                    #printFlush(item.get('event_type') + '!')
                    #printFlush(item.get('event_content'))
                    # @ToDo: collect for loadgame event: if item.get('event_type') == 'LoadGame'
                    current_status['extra_events'].pop(0)
                    continue
            #printFlush(f"({allGameEvents[item['event_type']].format(commanderName=commanderName)} Details: {json.dumps(item['event_content'])})")
            handle_conversation(client, commanderName, f"({allGameEvents[item['event_type']].format(commanderName=commanderName)} Details: {json.dumps(item['event_content'])})")

            current_status['extra_events'].pop(0)

    # Update previous status
    previous_status = current_status
    #printFlush('checkForJournalUpdates end')

jn = None
keys = EDKeys()
tts = None
def main():
    global client, sttClient, ttsClient, v, tts, keys, aiModel, backstory, useTools, jn, previous_status
    setGameWindowActive()

    # Load or prompt for configuration
    apiKey, llm_api_key, llm_endpoint, vision_model_name, vision_endpoint, vision_api_key, stt_model_name, stt_api_key, stt_endpoint, tts_model_name, tts_api_key, tts_endpoint, commanderName, character, model_name, alternative_stt_var, alternative_tts_var, tools_var, vision_var, ptt_var, tts_voice, key_binding, game_events  = load_or_prompt_config()

    jn = EDJournal(game_events)
    previous_status = getCurrentState()

    printFlush('loading keys')

    # gets API Key from config.json
    client = OpenAI(
      base_url = "https://api.openai.com/v1" if llm_endpoint == '' else llm_endpoint,
      api_key = apiKey if llm_api_key == '' else llm_api_key,
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
          base_url = "https://api.openai.com/v1" if vision_endpoint == '' else vision_endpoint,
          api_key = apiKey if vision_api_key == '' else vision_api_key,
        )
        def get_visuals(obj):
            image = screenshot()
            if not image: return "Unable to take screenshot."

            completion = visionClient.chat.completions.create(
                extra_headers = {
                    "HTTP-Referer": "https://github.com/RatherRude/Elite-Dangerous-AI-Integration",
                    "X-Title": "Elite Dangerous AI Integration",
                },
                model = aiModel if vision_model_name == '' else vision_model_name,
                messages = format_image(image, obj.get("query")),
            )
            printFlush("get_visuals completion:", completion)

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

    sttClient = OpenAI(
        base_url = "https://api.openai.com/v1" if stt_endpoint == '' else stt_endpoint,
        api_key = apiKey if stt_api_key == '' else stt_api_key,
    )
    ttsClient = OpenAI(
        base_url = "https://api.openai.com/v1" if tts_endpoint == '' else tts_endpoint,
        api_key = apiKey if tts_api_key == '' else tts_api_key,
    )

    printFlush(f"Initializing CMDR {commanderName}'s personal AI...\n")
    printFlush("API Key: Loaded")
    printFlush(f"Using Push-to-Talk: {ptt_var}")
    printFlush(f"Using Function Calling: {useTools}")
    printFlush(f"Current model: {aiModel}")
    printFlush(f"Current TTS voice: {tts_voice}")
    printFlush("Current backstory: " + backstory.replace("{commander_name}", commanderName))
    printFlush("\nBasic configuration complete.\n")
    printFlush("Loading voice interface...")

    # TTS Setup
    if alternative_tts_var:
        printFlush('Local TTS')
        tts = Voice()
        tts.set_on()
    else:
        printFlush('remote TTS')
        tts = TTS.TTS(openai_client=ttsClient, model=tts_model_name, voice=tts_voice)

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
    if alternative_stt_var:
        printFlush('local STT')
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
                printFlush("Available microphone devices are: ")
                for index, name in enumerate(sr.Microphone.list_microphone_names()):
                    printFlush(f"Microphone with name \"{name}\" found")
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
            #printFlush('record callback')
            # Grab the raw bytes and push it into the thread safe queue.
            data = audio.get_raw_data()
            data_queue.put(data)

        # Create a background thread that will pass us raw audio bytes.
        # We could do this manually but SpeechRecognizer provides a nice helper.
        recorder.listen_in_background(source, record_callback, phrase_time_limit=record_timeout)

        # Cue the user that we're ready to go.
        printFlush("Voice interface ready.\n")

        counter = 0

        while True:
            try:
                #printFlush('while whisper')
                now = datetime.utcnow()
                # Pull raw recorded audio from the queue.
                if not data_queue.empty():
                    #printFlush('while whisper if')
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
                    printFlush('')

                else:
                    #printFlush('while whisper else')
                    counter += 1
                    if counter % 5 == 0:
                        checkForJournalUpdates(client, commanderName, counter<=5)

                    # Infinite loops are bad for processors, must sleep.
                    sleep(0.25)
            except KeyboardInterrupt:
                break
    else:
        printFlush('remote STT')
        # new whisper start
        stt = STT.STT(openai_client=sttClient, model=stt_model_name)

        if ptt_var and key_binding:
            push_to_talk_key = key_binding  # Change this to your desired key
            keyboard.on_press_key(push_to_talk_key, lambda _: stt.listen_once_start())
            keyboard.on_release_key(push_to_talk_key, lambda _: stt.listen_once_end())
        else:
            stt.listen_continuous()

        # Cue the user that we're ready to go.
        printFlush("Voice interface ready.\n")

        counter = 0

        while True:
            try:
                # check STT result queue
                if not stt.resultQueue.empty():
                    tts.abort()
                    text = stt.resultQueue.get().text
                    handle_conversation(client, commanderName, text)
                else:
                    counter += 1
                    if counter % 5 == 0:
                        checkForJournalUpdates(client, commanderName, counter<=5)

                    # Infinite loops are bad for processors, must sleep.
                    sleep(0.25)
            except KeyboardInterrupt:
                break

        # new whisper end



    printFlush("\n\nConversation:")
    for line in conversation:
        printFlush(line)

    # Teardown TTS
    tts.quit()


if __name__ == "__main__":
    main()
