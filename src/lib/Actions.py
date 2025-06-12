import json
import platform
import threading
from time import sleep
import traceback
import math
import yaml
from typing import Any, Literal, Optional
from pyautogui import typewrite
from datetime import datetime, timezone

import openai
import requests

from .ScreenReader import ScreenReader
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

#Checking status projection to exit game actions early if not applicable
def checkStatus(projected_states: dict[str, dict], blocked_status_dict: dict[str, bool]):
    current_status = projected_states.get("CurrentStatus")

    if current_status:
        for blocked_status, expected_value in blocked_status_dict.items():
            for flag_group in ['flags', 'flags2']:
                if flag_group in current_status and blocked_status in current_status[flag_group]:
                    if current_status[flag_group][blocked_status] == expected_value:
                        raise Exception(f"Action not possible due to {'not ' if not expected_value else ''}being in a state of {blocked_status}!")

# Define functions for each action
# General Ship Actions
def fire_weapons(args, projected_states):
    checkStatus(projected_states, {'Docked':True,'Landed':True})
    setGameWindowActive()

    # Parse arguments with defaults
    weapon_type = args.get('weaponType', 'primary').lower()
    action = args.get('action', 'fire').lower()
    duration = args.get('duration', None)  # Duration to hold fire button
    repetitions = args.get('repetitions', 0)  # 0 = one action, 1+ = repeat

    # Determine key mapping
    if weapon_type == 'discovery_scanner':
        change_hud_mode({'hud mode': 'analysis'}, projected_states)
        cycle_fire_group({'fire_group': 0}, projected_states)
        keys.send('PrimaryFire', hold=6)
        return 'Discovery scan has been performed.'

    change_hud_mode({'hud mode': 'combat'}, projected_states)
    if weapon_type == 'secondary':
        key_name = 'SecondaryFire'
        weapon_desc = 'secondary weapons'
    else:  # default to primary
        key_name = 'PrimaryFire'
        weapon_desc = 'primary weapons'

    # Handle different actions
    if action == 'fire':
        # Single shot with optional duration and repetitions
        repeat_count = repetitions + 1  # 0 repetitions = 1 shot total

        if duration:
            keys.send(key_name, hold=duration, repeat=repeat_count)
            if repetitions > 0:
                return f"Fired {weapon_desc} {repeat_count} times, {duration}s each."
            else:
                return f"Fired {weapon_desc} for {duration}s."
        else:
            keys.send(key_name, repeat=repeat_count)
            if repetitions > 0:
                return f"Fired {weapon_desc} {repeat_count} times."
            else:
                return f"Fired {weapon_desc}."

    elif action == 'start':
        # Start continuous firing
        keys.send(key_name, state=1)
        return f"Started continuous firing with {weapon_desc}."

    elif action == 'stop':
        # Stop continuous firing
        keys.send(key_name, state=0)
        return f"Stopped firing {weapon_desc}."

    else:
        return f"Invalid action '{action}'. Use: fire, start, or stop."


def set_speed(args, projected_states):
    checkStatus(projected_states, {'Docked':True,'Landed':True})
    setGameWindowActive()

    if 'speed' in args:
        if args['speed'] in ["Minus100","Minus75","Minus50","Minus25","Zero","25","50","75","100"]:
            keys.send(f"SetSpeed{args['speed']}")
        else:
            raise Exception(f"Invalid speed {args['speed']}")

    return f"Speed set to {args['speed']}%."


def deploy_heat_sink(args, projected_states):
    checkStatus(projected_states, {'Docked':True,'Landed':True})
    setGameWindowActive()
    keys.send('DeployHeatSink')
    return f"Heat sink deployed"


def deploy_hardpoint_toggle(args, projected_states):
    checkStatus(projected_states, {'Docked':True,'Landed':True})
    setGameWindowActive()
    keys.send('DeployHardpointToggle')
    return f"Hardpoints {'deployed ' if not projected_states.get('CurrentStatus').get('flags').get('HardpointsDeployed') else 'retracted'}"


def manage_power_distribution(args, projected_states):
    """
    Handle power distribution between ship systems.

    Args:
        args (dict): {
            "power_category": ["engines", "weapons"],
            "balance_power": True/False,
            "pips": [3, 2]  # only if balance_power is False
        }
        projected_states (dict): (optional, can be used for context)

    Returns:
        str: A summary message for the tool response.
    """
    power_categories = args.get("power_category", [])
    balance_power = args.get("balance_power", False)
    pips = args.get("pips", [])
    message = ""

    if balance_power:
        # Balance power across all systems
        if power_categories == [] or len(power_categories) == 3:
            keys.send("ResetPowerDistribution")
            message = "Power balanced."
        else:
            message = f"Balancing power equally across {', '.join(power_categories)}."
            keys.send("ResetPowerDistribution")
            for _ in range(2):
                for pwr_system in power_categories:
                    keys.send(f"Increase{pwr_system.capitalize()}Power")

    else:
        # Apply specific pips per system
        if len(power_categories) != len(pips):
            return "ERROR: Number of pips does not match number of power categories."

        assignments = []
        for pwr_system, pip_count in zip(power_categories, pips):
            assignments.append(f"{pip_count} pips to {pwr_system}")
            for _ in range(pip_count):
                keys.send(f"Increase{pwr_system.capitalize()}Power")

        message = f"Applied: {', '.join(assignments)}."

    return message

def cycle_target(args, projected_states):
    setGameWindowActive()

    direction = args.get('direction', 'next').lower()

    if direction == 'previous':
        keys.send('CyclePreviousTarget')
        return "Selected previous target"
    else:
        # Default to 'next' for any invalid direction
        keys.send('CycleNextTarget')
        return "Selected next target"

def change_hud_mode(args, projected_states):

    mode = args.get('hud mode', 'toggle').lower()
    if projected_states.get('CurrentStatus').get('flags').get('HudInAnalysisMode'):
        current_hud_mode = "analysis"
    else:
        current_hud_mode = "combat"

    if mode == "toggle":
        keys.send('PlayerHUDModeToggle')
        return "combat mode activated" if current_hud_mode == "analysis" else "analysis mode activated"

    if mode == current_hud_mode:
        return f"hud already in {current_hud_mode}"
    else:
        keys.send('PlayerHUDModeToggle')
        return f"{mode} mode activated"


def cycle_fire_group(args, projected_states):
    setGameWindowActive()
    firegroup_ask = args.get('fire_group')

    initial_firegroup = projected_states.get("CurrentStatus").get('FireGroup')

    if firegroup_ask is None:
        direction = args.get('direction', 'next').lower()

        if direction == 'previous':
            keys.send('CycleFireGroupPrevious')
            return "Previous fire group selected."
        else:
            keys.send('CycleFireGroupNext')
            return "Next fire group selected."


    elif firegroup_ask == initial_firegroup:
        return f"Fire group {chr(65 + firegroup_ask)} was already selected. No changes."
    elif firegroup_ask > 7:   # max allowed is up to H which is 7 starting with A=0
        return f"Cannot switch to Firegroup {firegroup_ask} as it does not exist."
    else:
        for loop in range(abs(firegroup_ask - initial_firegroup)):
            if firegroup_ask > initial_firegroup:
                keys.send("CycleFireGroupNext")
            else:
                keys.send("CycleFireGroupPrevious")

    try:

        status_event = event_manager.wait_for_condition('CurrentStatus',
                                                            lambda s: s.get('FireGroup') == firegroup_ask, 2)
        new_firegroup = status_event["FireGroup"]
    except TimeoutError:
        #handles case where we cycle back round to zero
        return "Failed to cycle to requested fire group. Please ensure it exists."

    return f"Fire group {chr(65 + new_firegroup)} is now selected."


def ship_spot_light_toggle(args, projected_states):
    setGameWindowActive()
    keys.send('ShipSpotLightToggle')
    return f"Ship spotlight {'activated ' if not projected_states.get('CurrentStatus').get('flags').get('LightsOn') else 'deactivated'}"


def fire_chaff_launcher(args, projected_states):
    checkStatus(projected_states, {'Docked':True,'Landed':True,'Supercruise':True})
    setGameWindowActive()
    keys.send('FireChaffLauncher')
    return f"Chaff launcher fired"


def night_vision_toggle(args, projected_states):
    setGameWindowActive()
    keys.send('NightVisionToggle')
    return f"Night vision {'activated ' if not projected_states.get('CurrentStatus').get('flags').get('NightVision') else 'deactivated'}"


def select_highest_threat(args, projected_states):
    setGameWindowActive()
    keys.send('SelectHighestThreat')
    return f"Highest threat (if one exists) is now target locked"


def charge_ecm(args, projected_states):
    checkStatus(projected_states, {'Docked':True,'Landed':True,'Supercruise':True})
    setGameWindowActive()
    keys.send('ChargeECM')
    return "ECM is attempting to charge"


def calculate_navigation_distance_and_timing(current_system: str, target_system: str) -> tuple[float, int]:
    distance_ly = 0.0  # Default value in case API call fails
    
    if current_system != 'Unknown' and target_system:
        try:
            # Request coordinates for both systems from EDSM API
            edsm_url = "https://www.edsm.net/api-v1/systems"
            params = {
                'systemName[]': [current_system, target_system],
                'showCoordinates': 1
            }
            
            log('debug', 'Distance Calculation', f"Requesting coordinates for {current_system} -> {target_system}")
            response = requests.get(edsm_url, params=params, timeout=5)
            
            if response.status_code == 200:
                systems_data = response.json()
                
                if len(systems_data) >= 2:
                    # Find the systems in the response
                    current_coords = None
                    target_coords = None
                    
                    for system in systems_data:
                        if system.get('name', '').lower() == current_system.lower():
                            current_coords = system.get('coords')
                        elif system.get('name', '').lower() == target_system.lower():
                            target_coords = system.get('coords')
                    
                    # Calculate distance if both coordinate sets are available
                    if current_coords and target_coords:
                        x1, y1, z1 = current_coords['x'], current_coords['y'], current_coords['z']
                        x2, y2, z2 = target_coords['x'], target_coords['y'], target_coords['z']
                        
                        distance_ly = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2 + (z2 - z1) ** 2)
                        distance_ly = round(distance_ly, 2)
                        
                        # Check if distance is too far to plot
                        if distance_ly > 20000:
                            raise Exception(f"Distance of {distance_ly} LY from {current_system} to {target_system} is too far to plot (max 20000 LY)")
                    else:
                        log('warn', 'Distance Calculation', f"Could not find coordinates for one or both systems: {current_system}, {target_system}")
                else:
                    log('warn', 'Distance Calculation', f"EDSM API returned insufficient data for systems: {current_system}, {target_system}")
            else:
                log('warn', 'Distance Calculation', f"EDSM API request failed with status {response.status_code}")
                
        except requests.RequestException as e:
            log('error', 'Distance Calculation', f"Failed to request system coordinates from EDSM API: {str(e)}")
        except Exception as e:
            # Re-raise if it's our distance check exception
            if "too far to plot" in str(e):
                raise
            log('error', 'Distance Calculation', f"Unexpected error during distance calculation: {str(e)}")
    
    # Determine wait time based on distance
    zoom_wait_time = 3
    
    # Add additional second for every 1000 LY
    if distance_ly > 0:
        additional_time = int(distance_ly / 1000)
        zoom_wait_time += additional_time
    
    # Add additional 2 seconds if distance couldn't be determined (still 0)
    if distance_ly == 0:
        zoom_wait_time += 2
        log('warn', 'Navigation Timing', f"Distance could not be determined, adding 2 extra seconds to wait time")
        
    return distance_ly, zoom_wait_time


def galaxy_map_open(args, projected_states, galaxymap_key="GalaxyMapOpen"):
    # Trigger the GUI open
    setGameWindowActive()
    current_gui = projected_states.get('CurrentStatus', {}).get('GuiFocus', '')



    if 'start_navigation' in args and args['start_navigation']:
        nav_route = projected_states.get('NavInfo', {}).get('NavRoute', [])
        if nav_route and nav_route[-1].get('StarSystem') == args.get('system_name'):
            return f"The route to {args['system_name']} is already set"

    if current_gui in ['SAA', 'FSS', 'Codex']:
        raise Exception('Galaxy map can not be opened currently, the active GUI needs to be closed first')

    if current_gui == 'GalaxyMap':
        if not 'system_name' in args:
            return "Galaxy map is already open"
    else:
        keys.send(galaxymap_key)

    try:
        event_manager.wait_for_condition('CurrentStatus', lambda s: s.get('GuiFocus') == "GalaxyMap", 4)

    except TimeoutError:
        keys.send("UI_Back", repeat=10, repeat_delay=0.05)
        keys.send(galaxymap_key)
        try:
            event_manager.wait_for_condition('CurrentStatus', lambda s: s.get('GuiFocus') == "GalaxyMap", 5)
        except TimeoutError:
            return "Galaxy map can not be opened currently, the current GUI needs to be closed first"


    if 'system_name' in args:

        # Check if UI keys have a collision with CamTranslate
        collisions = keys.get_collisions('UI_Up')

        if 'CamTranslateForward' in collisions:
            raise Exception(
                "Unable to enter system name due to a collision between the 'UI Panel Up' and 'Galaxy Cam Translate Forward' keys. "
                + "Please change the keybinding for 'Galaxy Cam Translate' to Shift + WASD under General Controls > Galaxy Map.")

        collisions = keys.get_collisions('UI_Right')

        if 'CamTranslateRight' in collisions:
            raise Exception(
                "Unable to enter system name due to a collision between the 'UI Panel Right' and 'Galaxy Cam Translate Right' keys. "
                + "Please change the keybinding for 'Galaxy Cam Translate' to Shift + WASD under General Controls > Galaxy Map.")

        keys.send('CamZoomIn')
        sleep(0.05)

        keys.send('UI_Up')
        sleep(.05)
        if current_gui == "GalaxyMap":
            keys.send('UI_Left', repeat=3)
            sleep(.05)
            keys.send('UI_Right')
            sleep(.05)
            keys.send('UI_Up')
            sleep(.05)
        keys.send('UI_Select')
        sleep(.05)

        # type in the System name
        typewrite(args['system_name'], interval=0.02)
        sleep(0.05)

        # send enter key
        keys.send_key('Down', 'Key_Enter')
        sleep(0.05)
        keys.send_key('Up', 'Key_Enter')

        sleep(0.05)
        keys.send('UI_Right')
        sleep(.5)
        keys.send('UI_Select')

        if 'start_navigation' in args and args['start_navigation']:
            # Get current location from projected states and calculate distance/timing
            current_system = projected_states.get('Location', {}).get('StarSystem', 'Unknown')
            target_system = args['system_name']
            
            distance_ly, zoom_wait_time = calculate_navigation_distance_and_timing(current_system, target_system)
            log('info', 'zoom_wait_time', zoom_wait_time)
            # Continue with the navigation logic
            sleep(0.05)
            keys.send('CamZoomOut')
            sleep(zoom_wait_time)
            keys.send('UI_Select', hold=1)

            sleep(0.05)

            try:
                data = event_manager.wait_for_condition('NavInfo',
                                                                     lambda s: s.get('NavRoute') and len(s.get('NavRoute', [])) > 0 and s.get('NavRoute')[-1].get('StarSystem').lower() == args['system_name'].lower(), zoom_wait_time)
                jumpAmount = len(data.get('NavRoute', []))  # amount of jumps to do

                if not current_gui == "GalaxyMap":  # if we are already in the galaxy map we don't want to close it
                    keys.send(galaxymap_key)

                return (f"Best location found: {json.dumps(args['details'])}. " if 'details' in args else '') + f"Route to {args['system_name']} successfully plotted ({f"Distance: {distance_ly} LY, " if distance_ly > 0 else ""}Jumps: {jumpAmount})"

            except TimeoutError:
                return f"Failed to plot a route to {args['system_name']}"

        return f"The galaxy map has opened. It is now zoomed in on \"{args['system_name']}\". No route was plotted yet, only the commander can do that."

    return "Galaxy map opened"



def galaxy_map_close(args, projected_states, galaxymap_key="GalaxyMapOpen"):

    if projected_states.get('CurrentStatus').get('GuiFocus') == 'GalaxyMap':
        keys.send(galaxymap_key)
    else:
        return "Galaxy map is already closed"

    return "Galaxy map closed"


def system_map_open_or_close(args, projected_states, sys_map_key = 'SystemMapOpen'):
    # Trigger the GUI open
    setGameWindowActive()

    current_gui = projected_states.get('CurrentStatus', {}).get('GuiFocus', '')

    if args['desired_state'] == "close":
        if  current_gui == "SystemMap":
            keys.send(sys_map_key)
            return "System map has been closed."
        else:
            return "System map is not open, nothing to close."


    if current_gui in ['SAA', 'FSS', 'Codex']:
        raise Exception('System map can not be opened currently, the active GUI needs to be closed first')

    if current_gui == 'SystemMap':
            return "System map is already open"

    keys.send(sys_map_key)

    try:
        event_manager.wait_for_condition('CurrentStatus', lambda s: s.get('GuiFocus') == "SystemMap", 4)
    except TimeoutError:
        keys.send("UI_Back", repeat=10, repeat_delay=0.05)
        keys.send(sys_map_key)
        try:
            event_manager.wait_for_condition('CurrentStatus', lambda s: s.get('GuiFocus') == "SystemMap", 4)
        except TimeoutError:
            return "System map can not be opened currently, the current GUI needs to be closed first"

    return "System map opened"


# Mainship Actions

def eject_all_cargo(args, projected_states):
    setGameWindowActive()
    keys.send('EjectAllCargo')
    return f"All cargo ejected"

def landing_gear_toggle(args, projected_states):
    checkStatus(projected_states, {'Docked':True,'Landed':True,'Supercruise':True})
    setGameWindowActive()
    keys.send('LandingGearToggle')
    return f"Landing gear {'deployed ' if not projected_states.get('CurrentStatus').get('flags').get('LandingGearDown') else 'retracted'}"


def use_shield_cell(args, projected_states):
    setGameWindowActive()
    keys.send('UseShieldCell')
    return f"Shield cell used"


def toggle_cargo_scoop(args, projected_states):
    checkStatus(projected_states, {'Docked':True,'Landed':True,'Supercruise':True})
    setGameWindowActive()
    keys.send('ToggleCargoScoop')
    return f"Cargo scoop {'deployed ' if not projected_states.get('CurrentStatus').get('flags').get('CargoScoopDeployed') else 'retracted'}"


def fsd_jump(args, projected_states):
    checkStatus(projected_states, {'Docked':True,'Landed':True,'FsdMassLocked':True,'FsdCooldown':True,'FsdCharging':True})
    setGameWindowActive()

    return_message = ""

    if projected_states.get('CurrentStatus').get('flags').get('LandingGearDown'):
        keys.send('LandingGearToggle')
        return_message += "Landing Gear Retracted. "
    if projected_states.get('CurrentStatus').get('flags').get('CargoScoopDeployed'):
        keys.send('ToggleCargoScoop')
        return_message += "Cargo Scoop Retracted. "
    if projected_states.get('CurrentStatus').get('flags').get('HardpointsDeployed'):
        keys.send('DeployHardpointToggle')
        return_message += "Hardpoints Retracted. "

    jump_type = args.get('jump_type', 'auto')

    if jump_type == 'next_system':
        if projected_states.get('NavInfo').get('NextJumpTarget'):
            keys.send('Hyperspace')
        else:
            return "No system targeted for hyperjump"
    elif jump_type == 'supercruise':
        keys.send('Supercruise')
    else:
        keys.send('HyperSuperCombination')

    keys.send('SetSpeed100')

    return return_message + "Frame Shift Drive is now charging for a jump"

def next_system_in_route(args, projected_states):
    nav_info = projected_states.get('NavInfo', {})
    if not nav_info['NextJumpTarget']:
        return "cannot target next system in route as no navigation route is currently set"

    keys.send('TargetNextRouteSystem')
    return "Targeting next system in route"

def undock(args, projected_states):
    setGameWindowActive()
    # Early return if we're not docked
    if not projected_states.get('CurrentStatus').get('flags').get('Docked'):
        raise Exception("The ship currently isn't docked.")


    if projected_states.get('CurrentStatus').get('GuiFocus') in ['InternalPanel', 'CommsPanel', 'RolePanel', 'ExternalPanel']:
        keys.send('UIFocus')
        sleep(1)
    elif projected_states.get('CurrentStatus').get('GuiFocus') == 'NoFocus':
        pass
    else:
        raise Exception("The currently focused UI needs to be closed first")

    keys.send('UI_Down', None, 3)
    keys.send('UI_Up')
    keys.send('UI_Select')

    return 'The ship is now undocking'

def docking_key_press_sequence(stop_event):
    keys.send('UI_Left')
    keys.send('UI_Right')
    keys.send("UI_Select",hold = 0.2)
    for _ in range(6):
        if stop_event.is_set():
            break
        keys.send("CyclePreviousPanel")
        keys.send('UI_Left')
        keys.send('UI_Right')
        keys.send("UI_Select",hold = 0.2)


def request_docking(args, projected_states):
    checkStatus(projected_states, {'Supercruise':True})
    setGameWindowActive()
    if projected_states.get('CurrentStatus').get('GuiFocus') in ['NoFocus', 'InternalPanel', 'CommsPanel', 'RolePanel']:
        keys.send('FocusLeftPanel')
        sleep(1)
    elif projected_states.get('CurrentStatus').get('GuiFocus') == 'ExternalPanel':
        pass
    else:
        raise Exception('Docking menu not available in current UI Mode.')

    # Start the key press sequence
    stop_event = threading.Event()
    t = threading.Thread(target=docking_key_press_sequence, args=(stop_event,))
    t.start()

    try:
        old_timestamp = projected_states.get('DockingEvents').get('Timestamp', "1970-01-01T00:00:01Z")
        # Wait for a docking event with a timestamp newer than when we started
        event_manager.wait_for_condition('DockingEvents',
            lambda s: ((s.get('LastEventType') in ['DockingGranted', 'DockingRequested', 'DockingCanceled', 'DockingDenied', 'DockingTimeout'])
                      and (s.get('Timestamp', "1970-01-01T00:00:02Z") != old_timestamp)), 10)
        msg = ""
    except:
        msg = "Failed to request docking via menu"

    stop_event.set() # stop the keypress thread

    keys.send('UIFocus')
    return msg



# Ship Launched Fighter Actions
def fighter_request_dock(args, projected_states):
    setGameWindowActive()
    keys.send('OrderRequestDock')
    return f"A request for docking has been sent"


# NPC Crew Order Actions
def npc_order(args, projected_states):
    checkStatus(projected_states, {'Docked':True,'Landed':True,'Supercruise':True})
    setGameWindowActive()
    if 'orders' in args:
        for order in args['orders']:
            keys.send(f"Order{order}")
    return f"Orders {', '.join(str(x) for x in args['orders'])} have been transmitted."


# SRV Actions (Horizons)
def toggle_drive_assist(args, projected_states):
    setGameWindowActive()
    keys.send('ToggleDriveAssist')

    # return f"Landing gear {'deployed ' if not projected_states.get('CurrentStatus').get('flags').get('HardpointsDeployed') else 'retracted'}"
    return f"Drive assist has been {'activated ' if not projected_states.get('CurrentStatus').get('flags').get('SrvDriveAssist') else 'deactivated'}."

def fire_weapons_buggy(args, projected_states):
    """
    Simple buggy weapon firing action with three clear controls.
    Actions:
    - fire: Single shot (with optional duration and repetitions)
    - start: Begin continuous firing
    - stop: Stop continuous firing
    """
    checkStatus(projected_states, {'SrvTurretRetracted':True})
    setGameWindowActive()
    
    # Parse arguments with defaults
    weapon_type = args.get('weaponType', 'primary').lower()
    action = args.get('action', 'fire').lower()
    duration = args.get('duration', None)  # Duration to hold fire button
    repetitions = args.get('repetitions', 0)  # 0 = one action, 1+ = repeat
    
    # Determine key mapping
    if weapon_type == 'secondary':
        key_name = 'BuggySecondaryFireButton'
        weapon_desc = 'buggy secondary weapons'
    else:  # default to primary
        key_name = 'BuggyPrimaryFireButton'
        weapon_desc = 'buggy primary weapons'
    
    # Handle different actions
    if action == 'fire':
        # Single shot with optional duration and repetitions
        repeat_count = repetitions + 1  # 0 repetitions = 1 shot total
        
        if duration:
            keys.send(key_name, hold=duration, repeat=repeat_count)
            if repetitions > 0:
                return f"Fired {weapon_desc} {repeat_count} times, {duration}s each."
            else:
                return f"Fired {weapon_desc} for {duration}s."
        else:
            keys.send(key_name, repeat=repeat_count)
            if repetitions > 0:
                return f"Fired {weapon_desc} {repeat_count} times."
            else:
                return f"Fired {weapon_desc}."
        
    elif action == 'start':
        # Start continuous firing
        keys.send(key_name, state=1)
        return f"Started continuous firing with {weapon_desc}."
        
    elif action == 'stop':
        # Stop continuous firing
        keys.send(key_name, state=0)
        return f"Stopped firing {weapon_desc}."
        
    else:
        return f"Invalid action '{action}'. Use: fire, start, or stop."

def buggy_primary_fire(args, projected_states):
    checkStatus(projected_states, {'SrvTurretRetracted':True})
    setGameWindowActive()
    keys.send('BuggyPrimaryFireButton')
    return "Buggy primary fire triggered."

def buggy_secondary_fire(args, projected_states):
    checkStatus(projected_states, {'SrvTurretRetracted':True})
    setGameWindowActive()
    keys.send('BuggySecondaryFireButton')
    return "Buggy secondary fire triggered."

def auto_break_buggy(args, projected_states):
    setGameWindowActive()
    keys.send('AutoBreakBuggyButton')
    return "Auto-brake for buggy  {'activated ' if not projected_states.get('CurrentStatus').get('flags').get('SrvHandbrake') else 'deactivated'}."

def headlights_buggy(args, projected_states):
    setGameWindowActive()

    # Get current state
    current_flags = projected_states.get('CurrentStatus', {}).get('flags', {})
    lights_on = current_flags.get('LightsOn', False)
    high_beam = current_flags.get('SrvHighBeam', False)

    # Determine current mode: 0=off, 1=low, 2=high
    if not lights_on:
        current_mode = 0  # off
    elif lights_on and not high_beam:
        current_mode = 1  # low
    else:  # lights_on and high_beam
        current_mode = 2  # high

    # If no desired state specified, just toggle once
    desired_state = args.get('desired_state', 'toggle')

    if desired_state == 'toggle':
        keys.send('HeadlightsBuggyButton')
        key_presses = 1
    else:
        # Map desired state to mode number
        state_to_mode = {'off': 0, 'low': 1, 'high': 2}
        desired_mode = state_to_mode.get(desired_state.lower())

        if desired_mode is None:
            return f"Invalid desired state '{desired_state}'. Valid options: off, low, high, toggle"

        # Calculate number of key presses needed (cycling: off->low->high->off...)
        key_presses = (desired_mode - current_mode) % 3

        # Send the appropriate number of key presses
        for _ in range(key_presses):
            keys.send('HeadlightsBuggyButton')

    # Generate response message based on final state
    mode_names = ['off', 'low beam', 'high beam']
    final_mode = (current_mode + key_presses) % 3

    if desired_state == 'toggle':
        return f"Buggy headlights toggled to {mode_names[final_mode]} mode."
    else:
        return f"Buggy headlights set to {mode_names[final_mode]} mode."

def toggle_buggy_turret(args, projected_states):
    checkStatus(projected_states, {'SrvTurretRetracted':True})
    setGameWindowActive()
    keys.send('ToggleBuggyTurretButton')
    return f"Buggy turret mode  {'activated ' if not projected_states.get('CurrentStatus').get('flags').get('SrvUsingTurretView') else 'deactivated'}."

def select_target_buggy(args, projected_states):
    setGameWindowActive()
    keys.send('SelectTarget_Buggy')
    return "Buggy target selection activated."

def manage_power_distribution_buggy(args, projected_states):
    """
    Handle power distribution between buggy systems.

    Args:
        args (dict): {
            "power_category": ["engines", "weapons"],
            "balance_power": True/False,
            "pips": [3, 2]  # only if balance_power is False
        }
        projected_states (dict): (optional, can be used for context)

    Returns:
        str: A summary message for the tool response.
    """
    power_categories = args.get("power_category", [])
    balance_power = args.get("balance_power", False)
    pips = args.get("pips", [])
    message = ""

    if balance_power:
        # Balance power across all systems
        if power_categories == [] or len(power_categories) == 3:
            keys.send("ResetPowerDistribution_Buggy")
            message = "Power balanced."
        else:
            message = f"Balancing power equally across {', '.join(power_categories)}."
            keys.send("ResetPowerDistribution_Buggy")
            for _ in range(2):
                for pwr_system in power_categories:
                    keys.send(f"Increase{pwr_system.capitalize()}Power_Buggy")

    else:
        # Apply specific pips per system
        if len(power_categories) != len(pips):
            return "ERROR: Number of pips does not match number of power categories."

        assignments = []
        for pwr_system, pip_count in zip(power_categories, pips):
            assignments.append(f"{pip_count} pips to {pwr_system}")
            for _ in range(pip_count):
                keys.send(f"Increase{pwr_system.capitalize()}Power_Buggy")

        message = f"Applied: {', '.join(assignments)}."

    return message


def toggle_cargo_scoop_buggy(args, projected_states):
    setGameWindowActive()
    keys.send('ToggleCargoScoop_Buggy')
    return f"Buggy cargo scoop {'deployed ' if not projected_states.get('CurrentStatus').get('flags').get('CargoScoopDeployed') else 'retracted'}"

def eject_all_cargo_buggy(args, projected_states):
    setGameWindowActive()
    keys.send('EjectAllCargo_Buggy')
    return "All cargo ejected from buggy."

def recall_dismiss_ship_buggy(args, projected_states):
    setGameWindowActive()
    keys.send('RecallDismissShip')
    return "Remote ship has been recalled or dismissed."

def galaxy_map_open_buggy(args, projected_states) -> Any | Literal['Galaxy map is already closed', 'Galaxy map closed']:
    setGameWindowActive()
    if args['desired_state'] == "open":
        response = galaxy_map_open(args, projected_states, "GalaxyMapOpen_Buggy")
    else:
        response = galaxy_map_close(args, projected_states, "GalaxyMapOpen_Buggy")

    return response

def system_map_open_buggy(args, projected_states):
    setGameWindowActive()
    current_gui = projected_states.get('CurrentStatus', {}).get('GuiFocus', '')

    msg = ""

    if args['desired_state'] == "close":
        if current_gui == "SystemMap":
            keys.send("SystemMapOpen_Buggy")
            msg = "System map has been closed."
        else:
            return "System map is not open, nothing to close."
    else:
        if current_gui == "SystemMap":
            msg = "System map is already open"

        else:
            keys.send("SystemMapOpen_Buggy")
            msg = "System map opened."

    return msg

# On-Foot Actions (Odyssey)
def primary_interact_humanoid(args, projected_states):
    setGameWindowActive()
    keys.send('HumanoidPrimaryInteractButton')
    return "Primary interaction initiated."

def secondary_interact_humanoid(args, projected_states):
    setGameWindowActive()
    keys.send('HumanoidSecondaryInteractButton')
    return "Secondary interaction initiated."

def equip_humanoid(args, projected_states):
    checkStatus(projected_states, {'OnFootInStation':True,'OnFootInHangar':True,'OnFootSocialSpace':True})
    if 'equipment' in args:
        keys.send(args['equipment'])
    return f"{args['equipment']} has been triggered."

def toggle_flashlight_humanoid(args, projected_states):
    setGameWindowActive()
    keys.send('HumanoidToggleFlashlightButton')
    return "Flashlight toggled."

def toggle_night_vision_humanoid(args, projected_states):
    setGameWindowActive()
    keys.send('HumanoidToggleNightVisionButton')
    return f"Night vision {'activated ' if not projected_states.get('CurrentStatus').get('flags').get('NightVision') else 'deactivated'}"

def toggle_shields_humanoid(args, projected_states):
    checkStatus(projected_states, {'OnFootInStation':True,'OnFootInHangar':True,'OnFootSocialSpace':True})
    setGameWindowActive()
    keys.send('HumanoidToggleShieldsButton')

    return f"Shields {'activated ' if not projected_states.get('CurrentStatus').get('flags').get('ShieldsUp') else 'deactivated'}."

def clear_authority_level_humanoid(args, projected_states):
    checkStatus(projected_states, {'OnFootInStation':True,'OnFootInHangar':True,'OnFootSocialSpace':True})
    setGameWindowActive()
    keys.send('HumanoidClearAuthorityLevel')
    return "Authority level cleared."

def health_pack_humanoid(args, projected_states):
    checkStatus(projected_states, {'OnFootInStation':True,'OnFootInHangar':True,'OnFootSocialSpace':True})
    setGameWindowActive()
    keys.send('HumanoidHealthPack')
    return "Health pack used."

def battery_humanoid(args, projected_states):
    checkStatus(projected_states, {'OnFootInStation':True,'OnFootInHangar':True,'OnFootSocialSpace':True})
    setGameWindowActive()
    keys.send('HumanoidBattery')
    return "Battery used."

def galaxy_map_open_humanoid(args, projected_states):
    setGameWindowActive()
    keys.send('GalaxyMapOpen_Humanoid')
    return "Galaxy map opened or closed."

def system_map_open_humanoid(args, projected_states):
    setGameWindowActive()
    keys.send('SystemMapOpen_Humanoid')
    return "System map opened or closed."

def recall_dismiss_ship_humanoid(args, projected_states):
    checkStatus(projected_states, {'OnFootInStation':True,'OnFootInHangar':True,'OnFootSocialSpace':True})
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
    if platform.system() != 'Windows':
        return None
    import win32gui

    if not handle:
        handle = win32gui.FindWindow(0, "Elite - Dangerous (CLIENT)")
    return handle


def setGameWindowActive():
    if platform.system() != 'Windows':
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
    if platform.system() != 'Windows':
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
def get_galnet_news(obj, projected_states):
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

# Here could be a json

# Engineering modifications database
ENGINEERING_MODIFICATIONS = {
    "Efficient": {
        "module_recipes": {
            "Beam Laser": {
                "grade_1": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_2": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_3": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_4": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]},
                "grade_5": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]}
            },
            "Burst Laser": {
                "grade_1": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_2": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_3": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_4": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]},
                "grade_5": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]}
            },
            "Cannon": {
                "grade_1": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_2": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_3": {"cost": {}, "engineers": ["The Sarge"]},
                "grade_4": {"cost": {}, "engineers": ["The Sarge"]},
                "grade_5": {"cost": {}, "engineers": ["The Sarge", "Marsha Hicks"]}
            },
            "Fragment Cannon": {
                "grade_1": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_2": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_3": {"cost": {}, "engineers": ["Zacariah Nemo"]},
                "grade_4": {"cost": {}, "engineers": ["Zacariah Nemo"]},
                "grade_5": {"cost": {}, "engineers": ["Zacariah Nemo", "Marsha Hicks"]}
            },
            "Multi-cannon": {
                "grade_1": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Zacariah Nemo"]},
                "grade_2": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Zacariah Nemo"]},
                "grade_3": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Zacariah Nemo"]},
                "grade_4": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Marsha Hicks"]},
                "grade_5": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Marsha Hicks"]}
            },
            "Plasma Accelerator": {
                "grade_1": {"cost": {}, "engineers": ["Zacariah Nemo"]},
                "grade_2": {"cost": {}, "engineers": ["Zacariah Nemo"]},
                "grade_3": {"cost": {}, "engineers": ["Bill Turner"]},
                "grade_4": {"cost": {}, "engineers": ["Bill Turner"]},
                "grade_5": {"cost": {}, "engineers": ["Bill Turner", "Etienne Dorn"]}
            },
            "Pulse Laser": {
                "grade_1": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_2": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_3": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_4": {"cost": {}, "engineers": ["The Dweller", "Broo Tarquin", "Mel Brandon"]},
                "grade_5": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]}
            }
        }
    },
    "Lightweight": {
        "module_recipes": {
            "Beam Laser": {
                "grade_1": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_2": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_3": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_4": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]},
                "grade_5": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]}
            },
            "Burst Laser": {
                "grade_1": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_2": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_3": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_4": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]},
                "grade_5": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]}
            },
            "Cannon": {
                "grade_1": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_2": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_3": {"cost": {}, "engineers": ["The Sarge"]},
                "grade_4": {"cost": {}, "engineers": ["The Sarge"]},
                "grade_5": {"cost": {}, "engineers": ["The Sarge", "Marsha Hicks"]}
            },
            "Fragment Cannon": {
                "grade_1": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_2": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_3": {"cost": {}, "engineers": ["Zacariah Nemo"]},
                "grade_4": {"cost": {}, "engineers": ["Zacariah Nemo"]},
                "grade_5": {"cost": {}, "engineers": ["Zacariah Nemo", "Marsha Hicks"]}
            },
            "Mine Launcher": {
                "grade_1": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_2": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_3": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_4": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_5": {"cost": {}, "engineers": ["Juri Ishmaak", "Petra Olmanova"]}
            },
            "Missile Rack": {
                "grade_1": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_2": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_3": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_4": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_5": {"cost": {}, "engineers": ["Liz Ryder", "Petra Olmanova"]}
            },
            "Multi-cannon": {
                "grade_1": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Zacariah Nemo"]},
                "grade_2": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Zacariah Nemo"]},
                "grade_3": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Zacariah Nemo"]},
                "grade_4": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Marsha Hicks"]},
                "grade_5": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Marsha Hicks"]}
            },
            "Plasma Accelerator": {
                "grade_1": {"cost": {}, "engineers": ["Zacariah Nemo"]},
                "grade_2": {"cost": {}, "engineers": ["Zacariah Nemo"]},
                "grade_3": {"cost": {}, "engineers": ["Bill Turner"]},
                "grade_4": {"cost": {}, "engineers": ["Bill Turner"]},
                "grade_5": {"cost": {}, "engineers": ["Bill Turner", "Etienne Dorn"]}
            },
            "Pulse Laser": {
                "grade_1": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_2": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_3": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_4": {"cost": {}, "engineers": ["The Dweller", "Broo Tarquin", "Mel Brandon"]},
                "grade_5": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]}
            },
            "Rail Gun": {
                "grade_1": {"cost": {}, "engineers": ["The Sarge"]},
                "grade_2": {"cost": {}, "engineers": ["The Sarge"]},
                "grade_3": {"cost": {}, "engineers": ["The Sarge"]},
                "grade_4": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_5": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Etienne Dorn"]}
            },
            "Seeker Missile Rack": {
                "grade_1": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_2": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_3": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_4": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_5": {"cost": {}, "engineers": ["Liz Ryder", "Petra Olmanova"]}
            },
            "Torpedo Pylon": {
                "grade_1": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_2": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_3": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_4": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_5": {"cost": {}, "engineers": ["Liz Ryder", "Petra Olmanova"]}
            },
            "Chaff Launcher": {
                "grade_1": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_2": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_3": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_4": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_5": {"cost": {}, "engineers": ["Ram Tah", "Petra Olmanova"]}
            },
            "Electronic Countermeasure": {
                "grade_1": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_2": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_3": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_4": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_5": {"cost": {}, "engineers": ["Ram Tah", "Petra Olmanova"]}
            },
            "Frame Shift Wake Scanner": {
                "grade_1": {"cost": {}, "engineers": ["Juri Ishmaak", "Bill Turner", "Lori Jameson"]},
                "grade_2": {"cost": {}, "engineers": ["Juri Ishmaak", "Bill Turner", "Lori Jameson"]},
                "grade_3": {"cost": {}, "engineers": ["Juri Ishmaak", "Bill Turner", "Lori Jameson"]},
                "grade_4": {"cost": {}, "engineers": ["Tiana Fortune"]},
                "grade_5": {"cost": {}, "engineers": ["Tiana Fortune", "Etienne Dorn"]}
            },
            "Heat Sink Launcher": {
                "grade_1": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_2": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_3": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_4": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_5": {"cost": {}, "engineers": ["Ram Tah", "Petra Olmanova"]}
            },
            "Kill Warrant Scanner": {
                "grade_1": {"cost": {}, "engineers": ["Juri Ishmaak", "Bill Turner", "Lori Jameson"]},
                "grade_2": {"cost": {}, "engineers": ["Juri Ishmaak", "Bill Turner", "Lori Jameson"]},
                "grade_3": {"cost": {}, "engineers": ["Juri Ishmaak", "Bill Turner", "Lori Jameson"]},
                "grade_4": {"cost": {}, "engineers": ["Tiana Fortune"]},
                "grade_5": {"cost": {}, "engineers": ["Tiana Fortune", "Etienne Dorn"]}
            },
            "Manifest Scanner": {
                "grade_1": {"cost": {}, "engineers": ["Juri Ishmaak", "Bill Turner", "Lori Jameson"]},
                "grade_2": {"cost": {}, "engineers": ["Juri Ishmaak", "Bill Turner", "Lori Jameson"]},
                "grade_3": {"cost": {}, "engineers": ["Juri Ishmaak", "Bill Turner", "Lori Jameson"]},
                "grade_4": {"cost": {}, "engineers": ["Tiana Fortune"]},
                "grade_5": {"cost": {}, "engineers": ["Tiana Fortune", "Etienne Dorn"]}
            },
            "Point Defence": {
                "grade_1": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_2": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_3": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_4": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_5": {"cost": {}, "engineers": ["Ram Tah", "Petra Olmanova"]}
            },
            "Collector Limpet Controller": {
                "grade_1": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_2": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_3": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_4": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_5": {"cost": {}, "engineers": ["Tiana Fortune", "The Sarge"]}
            },
            "Fuel Transfer Limpet Controller": {
                "grade_1": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_2": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_3": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_4": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_5": {"cost": {}, "engineers": ["Tiana Fortune", "The Sarge", "Marsha Hicks"]}
            },
            "Hatch Breaker Limpet Controller": {
                "grade_1": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_2": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_3": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_4": {"cost": {}, "engineers": []},
                "grade_5": {"cost": {}, "engineers": ["Tiana Fortune", "The Sarge", "Marsha Hicks"]}
            },
            "Hull Reinforcement Package": {
                "grade_1": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_2": {"cost": {}, "engineers": []},
                "grade_3": {"cost": {}, "engineers": []},
                "grade_4": {"cost": {}, "engineers": []},
                "grade_5": {"cost": {}, "engineers": ["Selene Jean", "Petra Olmanova"]}
            },
            "Prospector Limpet Controller": {
                "grade_1": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_2": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_3": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_4": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_5": {"cost": {}, "engineers": ["Tiana Fortune", "The Sarge", "Marsha Hicks"]}
            },
            "Life Support": {
                "grade_1": {"cost": {}, "engineers": ["Bill Turner", "Lori Jameson"]},
                "grade_2": {"cost": {}, "engineers": ["Bill Turner", "Lori Jameson"]},
                "grade_3": {"cost": {}, "engineers": ["Bill Turner", "Lori Jameson"]},
                "grade_4": {"cost": {}, "engineers": ["Lori Jameson"]},
                "grade_5": {"cost": {}, "engineers": ["Etienne Dorn"]}
            },
            "Sensors": {
                "grade_1": {"cost": {}, "engineers": ["Felicity Farseer", "Lei Cheung", "Hera Tani"]},
                "grade_2": {"cost": {}, "engineers": ["Felicity Farseer", "Lei Cheung", "Hera Tani"]},
                "grade_3": {"cost": {}, "engineers": ["Felicity Farseer", "Lei Cheung", "Hera Tani"]},
                "grade_4": {"cost": {}, "engineers": ["Lei Cheung"]},
                "grade_5": {"cost": {}, "engineers": ["Lei Cheung", "Juri Ishmaak", "Bill Turner", "Lori Jameson", "Tiana Fortune", "Etienne Dorn"]}
            },
            "Armour": {
                "grade_1": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_2": {"cost": {}, "engineers": []},
                "grade_3": {"cost": {}, "engineers": []},
                "grade_4": {"cost": {}, "engineers": []},
                "grade_5": {"cost": {}, "engineers": ["Selene Jean", "Petra Olmanova"]}
            }
        }
    },
    "Long range": {
        "module_recipes": {
            "Beam Laser": {
                "grade_1": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_2": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_3": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_4": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]},
                "grade_5": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]}
            },
            "Burst Laser": {
                "grade_1": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_2": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_3": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_4": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]},
                "grade_5": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]}
            },
            "Cannon": {
                "grade_1": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_2": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_3": {"cost": {}, "engineers": ["The Sarge"]},
                "grade_4": {"cost": {}, "engineers": ["The Sarge"]},
                "grade_5": {"cost": {}, "engineers": ["The Sarge", "Marsha Hicks"]}
            },
            "Multi-cannon": {
                "grade_1": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Zacariah Nemo"]},
                "grade_2": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Zacariah Nemo"]},
                "grade_3": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Zacariah Nemo"]},
                "grade_4": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Marsha Hicks"]},
                "grade_5": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Marsha Hicks"]}
            },
            "Plasma Accelerator": {
                "grade_1": {"cost": {}, "engineers": ["Zacariah Nemo"]},
                "grade_2": {"cost": {}, "engineers": ["Zacariah Nemo"]},
                "grade_3": {"cost": {}, "engineers": ["Bill Turner"]},
                "grade_4": {"cost": {}, "engineers": ["Bill Turner"]},
                "grade_5": {"cost": {}, "engineers": ["Bill Turner", "Etienne Dorn"]}
            },
            "Pulse Laser": {
                "grade_1": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_2": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_3": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_4": {"cost": {}, "engineers": ["The Dweller", "Broo Tarquin", "Mel Brandon"]},
                "grade_5": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]}
            },
            "Rail Gun": {
                "grade_1": {"cost": {}, "engineers": ["The Sarge"]},
                "grade_2": {"cost": {}, "engineers": ["The Sarge"]},
                "grade_3": {"cost": {}, "engineers": ["The Sarge"]},
                "grade_4": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_5": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Etienne Dorn"]}
            },
            "Frame Shift Wake Scanner": {
                "grade_1": {"cost": {}, "engineers": ["Juri Ishmaak", "Bill Turner", "Lori Jameson"]},
                "grade_2": {"cost": {}, "engineers": ["Juri Ishmaak", "Bill Turner", "Lori Jameson"]},
                "grade_3": {"cost": {}, "engineers": ["Juri Ishmaak", "Bill Turner", "Lori Jameson"]},
                "grade_4": {"cost": {}, "engineers": ["Tiana Fortune"]},
                "grade_5": {"cost": {}, "engineers": ["Tiana Fortune", "Etienne Dorn"]}
            },
            "Kill Warrant Scanner": {
                "grade_1": {"cost": {}, "engineers": ["Juri Ishmaak", "Bill Turner", "Lori Jameson"]},
                "grade_2": {"cost": {}, "engineers": ["Juri Ishmaak", "Bill Turner", "Lori Jameson"]},
                "grade_3": {"cost": {}, "engineers": ["Juri Ishmaak", "Bill Turner", "Lori Jameson"]},
                "grade_4": {"cost": {}, "engineers": ["Tiana Fortune"]},
                "grade_5": {"cost": {}, "engineers": ["Tiana Fortune", "Etienne Dorn"]}
            },
            "Manifest Scanner": {
                "grade_1": {"cost": {}, "engineers": ["Juri Ishmaak", "Bill Turner", "Lori Jameson"]},
                "grade_2": {"cost": {}, "engineers": ["Juri Ishmaak", "Bill Turner", "Lori Jameson"]},
                "grade_3": {"cost": {}, "engineers": ["Juri Ishmaak", "Bill Turner", "Lori Jameson"]},
                "grade_4": {"cost": {}, "engineers": ["Tiana Fortune"]},
                "grade_5": {"cost": {}, "engineers": ["Tiana Fortune", "Etienne Dorn"]}
            },
            "Frame Shift Drive Interdictor": {
                "grade_1": {"cost": {}, "engineers": ["Felicity Farseer", "Tiana Fortune"]},
                "grade_2": {"cost": {}, "engineers": ["Tiana Fortune"]},
                "grade_3": {"cost": {}, "engineers": ["Tiana Fortune", "Colonel Bris Dekker"]},
                "grade_4": {"cost": {}, "engineers": ["Colonel Bris Dekker"]},
                "grade_5": {"cost": {}, "engineers": ["Mel Brandon"]}
            },
            "Sensors": {
                "grade_1": {"cost": {}, "engineers": ["Felicity Farseer", "Lei Cheung", "Hera Tani"]},
                "grade_2": {"cost": {}, "engineers": ["Felicity Farseer", "Lei Cheung", "Hera Tani"]},
                "grade_3": {"cost": {}, "engineers": ["Felicity Farseer", "Lei Cheung", "Hera Tani"]},
                "grade_4": {"cost": {}, "engineers": ["Lei Cheung"]},
                "grade_5": {"cost": {}, "engineers": ["Lei Cheung", "Juri Ishmaak", "Bill Turner", "Lori Jameson", "Tiana Fortune", "Etienne Dorn"]}
            }
        }
    },
    "Overcharged": {
        "module_recipes": {
            "Beam Laser": {
                "grade_1": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_2": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_3": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_4": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]},
                "grade_5": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]}
            },
            "Burst Laser": {
                "grade_1": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_2": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_3": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_4": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]},
                "grade_5": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]}
            },
            "Cannon": {
                "grade_1": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_2": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_3": {"cost": {}, "engineers": ["The Sarge"]},
                "grade_4": {"cost": {}, "engineers": ["The Sarge"]},
                "grade_5": {"cost": {}, "engineers": ["The Sarge", "Marsha Hicks"]}
            },
            "Fragment Cannon": {
                "grade_1": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_2": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_3": {"cost": {}, "engineers": ["Zacariah Nemo"]},
                "grade_4": {"cost": {}, "engineers": ["Zacariah Nemo"]},
                "grade_5": {"cost": {}, "engineers": ["Zacariah Nemo", "Marsha Hicks"]}
            },
            "Multi-cannon": {
                "grade_1": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Zacariah Nemo"]},
                "grade_2": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Zacariah Nemo"]},
                "grade_3": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Zacariah Nemo"]},
                "grade_4": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Marsha Hicks"]},
                "grade_5": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Marsha Hicks"]}
            },
            "Plasma Accelerator": {
                "grade_1": {"cost": {}, "engineers": ["Zacariah Nemo"]},
                "grade_2": {"cost": {}, "engineers": ["Zacariah Nemo"]},
                "grade_3": {"cost": {}, "engineers": ["Bill Turner"]},
                "grade_4": {"cost": {}, "engineers": ["Bill Turner"]},
                "grade_5": {"cost": {}, "engineers": ["Bill Turner", "Etienne Dorn"]}
            },
            "Pulse Laser": {
                "grade_1": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_2": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_3": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_4": {"cost": {}, "engineers": ["The Dweller", "Broo Tarquin", "Mel Brandon"]},
                "grade_5": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]}
            },
            "Power Plant": {
                "grade_1": {"cost": {}, "engineers": ["Felicity Farseer"]},
                "grade_2": {"cost": {}, "engineers": ["Marco Qwent"]},
                "grade_3": {"cost": {}, "engineers": ["Marco Qwent", "Hera Tani"]},
                "grade_4": {"cost": {}, "engineers": ["Marco Qwent", "Hera Tani"]},
                "grade_5": {"cost": {}, "engineers": ["Hera Tani", "Etienne Dorn"]}
            }
        }
    },
    "Short range": {
        "module_recipes": {
            "Beam Laser": {
                "grade_1": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_2": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_3": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_4": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]},
                "grade_5": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]}
            },
            "Burst Laser": {
                "grade_1": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_2": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_3": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_4": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]},
                "grade_5": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]}
            },
            "Cannon": {
                "grade_1": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_2": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_3": {"cost": {}, "engineers": ["The Sarge"]},
                "grade_4": {"cost": {}, "engineers": ["The Sarge"]},
                "grade_5": {"cost": {}, "engineers": ["The Sarge", "Marsha Hicks"]}
            },
            "Multi-cannon": {
                "grade_1": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Zacariah Nemo"]},
                "grade_2": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Zacariah Nemo"]},
                "grade_3": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Zacariah Nemo"]},
                "grade_4": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Marsha Hicks"]},
                "grade_5": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Marsha Hicks"]}
            },
            "Plasma Accelerator": {
                "grade_1": {"cost": {}, "engineers": ["Zacariah Nemo"]},
                "grade_2": {"cost": {}, "engineers": ["Zacariah Nemo"]},
                "grade_3": {"cost": {}, "engineers": ["Bill Turner"]},
                "grade_4": {"cost": {}, "engineers": ["Bill Turner"]},
                "grade_5": {"cost": {}, "engineers": ["Bill Turner", "Etienne Dorn"]}
            },
            "Pulse Laser": {
                "grade_1": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_2": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_3": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_4": {"cost": {}, "engineers": ["The Dweller", "Broo Tarquin", "Mel Brandon"]},
                "grade_5": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]}
            },
            "Rail Gun": {
                "grade_1": {"cost": {}, "engineers": ["The Sarge"]},
                "grade_2": {"cost": {}, "engineers": ["The Sarge"]},
                "grade_3": {"cost": {}, "engineers": ["The Sarge"]},
                "grade_4": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_5": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Etienne Dorn"]}
            }
        }
    },
    "Sturdy": {
        "module_recipes": {
            "Beam Laser": {
                "grade_1": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_2": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_3": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_4": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]},
                "grade_5": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]}
            },
            "Burst Laser": {
                "grade_1": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_2": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_3": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_4": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]},
                "grade_5": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]}
            },
            "Cannon": {
                "grade_1": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_2": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_3": {"cost": {}, "engineers": ["The Sarge"]},
                "grade_4": {"cost": {}, "engineers": ["The Sarge"]},
                "grade_5": {"cost": {}, "engineers": ["The Sarge", "Marsha Hicks"]}
            },
            "Fragment Cannon": {
                "grade_1": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_2": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_3": {"cost": {}, "engineers": ["Zacariah Nemo"]},
                "grade_4": {"cost": {}, "engineers": ["Zacariah Nemo"]},
                "grade_5": {"cost": {}, "engineers": ["Zacariah Nemo", "Marsha Hicks"]}
            },
            "Mine Launcher": {
                "grade_1": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_2": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_3": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_4": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_5": {"cost": {}, "engineers": ["Juri Ishmaak", "Petra Olmanova"]}
            },
            "Missile Rack": {
                "grade_1": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_2": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_3": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_4": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_5": {"cost": {}, "engineers": ["Liz Ryder", "Petra Olmanova"]}
            },
            "Multi-cannon": {
                "grade_1": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Zacariah Nemo"]},
                "grade_2": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Zacariah Nemo"]},
                "grade_3": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Zacariah Nemo"]},
                "grade_4": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Marsha Hicks"]},
                "grade_5": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Marsha Hicks"]}
            },
            "Plasma Accelerator": {
                "grade_1": {"cost": {}, "engineers": ["Zacariah Nemo"]},
                "grade_2": {"cost": {}, "engineers": ["Zacariah Nemo"]},
                "grade_3": {"cost": {}, "engineers": ["Bill Turner"]},
                "grade_4": {"cost": {}, "engineers": ["Bill Turner"]},
                "grade_5": {"cost": {}, "engineers": ["Bill Turner", "Etienne Dorn"]}
            },
            "Pulse Laser": {
                "grade_1": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_2": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_3": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_4": {"cost": {}, "engineers": ["The Dweller", "Broo Tarquin", "Mel Brandon"]},
                "grade_5": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]}
            },
            "Rail Gun": {
                "grade_1": {"cost": {}, "engineers": ["The Sarge"]},
                "grade_2": {"cost": {}, "engineers": ["The Sarge"]},
                "grade_3": {"cost": {}, "engineers": ["The Sarge"]},
                "grade_4": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_5": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Etienne Dorn"]}
            },
            "Seeker Missile Rack": {
                "grade_1": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_2": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_3": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_4": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_5": {"cost": {}, "engineers": ["Liz Ryder", "Petra Olmanova"]}
            },
            "Torpedo Pylon": {
                "grade_1": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_2": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_3": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_4": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_5": {"cost": {}, "engineers": ["Liz Ryder", "Petra Olmanova"]}
            }
        }
    },
    "Focused": {
        "module_recipes": {
            "Burst Laser": {
                "grade_1": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_2": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_3": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_4": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]},
                "grade_5": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]}
            },
            "Plasma Accelerator": {
                "grade_1": {"cost": {}, "engineers": ["Zacariah Nemo"]},
                "grade_2": {"cost": {}, "engineers": ["Zacariah Nemo"]},
                "grade_3": {"cost": {}, "engineers": ["Bill Turner"]},
                "grade_4": {"cost": {}, "engineers": ["Bill Turner"]},
                "grade_5": {"cost": {}, "engineers": ["Bill Turner", "Etienne Dorn"]}
            },
            "Pulse Laser": {
                "grade_1": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_2": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_3": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_4": {"cost": {}, "engineers": ["The Dweller", "Broo Tarquin", "Mel Brandon"]},
                "grade_5": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]}
            }
        }
    },
    "Rapid fire": {
        "module_recipes": {
            "Burst Laser": {
                "grade_1": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_2": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_3": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_4": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]},
                "grade_5": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]}
            },
            "Cannon": {
                "grade_1": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_2": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_3": {"cost": {}, "engineers": ["The Sarge"]},
                "grade_4": {"cost": {}, "engineers": ["The Sarge"]},
                "grade_5": {"cost": {}, "engineers": ["The Sarge", "Marsha Hicks"]}
            },
            "Fragment Cannon": {
                "grade_1": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_2": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_3": {"cost": {}, "engineers": ["Zacariah Nemo"]},
                "grade_4": {"cost": {}, "engineers": ["Zacariah Nemo"]},
                "grade_5": {"cost": {}, "engineers": ["Zacariah Nemo", "Marsha Hicks"]}
            },
            "Mine Launcher": {
                "grade_1": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_2": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_3": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_4": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_5": {"cost": {}, "engineers": ["Juri Ishmaak", "Petra Olmanova"]}
            },
            "Missile Rack": {
                "grade_1": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_2": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_3": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_4": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_5": {"cost": {}, "engineers": ["Liz Ryder", "Petra Olmanova"]}
            },
            "Multi-cannon": {
                "grade_1": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Zacariah Nemo"]},
                "grade_2": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Zacariah Nemo"]},
                "grade_3": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Zacariah Nemo"]},
                "grade_4": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Marsha Hicks"]},
                "grade_5": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Marsha Hicks"]}
            },
            "Plasma Accelerator": {
                "grade_1": {"cost": {}, "engineers": ["Zacariah Nemo"]},
                "grade_2": {"cost": {}, "engineers": ["Zacariah Nemo"]},
                "grade_3": {"cost": {}, "engineers": ["Bill Turner"]},
                "grade_4": {"cost": {}, "engineers": ["Bill Turner"]},
                "grade_5": {"cost": {}, "engineers": ["Bill Turner", "Etienne Dorn"]}
            },
            "Pulse Laser": {
                "grade_1": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_2": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_3": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_4": {"cost": {}, "engineers": ["The Dweller", "Broo Tarquin", "Mel Brandon"]},
                "grade_5": {"cost": {}, "engineers": ["Broo Tarquin", "Mel Brandon"]}
            },
            "Seeker Missile Rack": {
                "grade_1": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_2": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_3": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_4": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_5": {"cost": {}, "engineers": ["Liz Ryder", "Petra Olmanova"]}
            }
        }
    },
    "High capacity": {
        "module_recipes": {
            "Cannon": {
                "grade_1": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_2": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_3": {"cost": {}, "engineers": ["The Sarge"]},
                "grade_4": {"cost": {}, "engineers": ["The Sarge"]},
                "grade_5": {"cost": {}, "engineers": ["The Sarge", "Marsha Hicks"]}
            },
            "Fragment Cannon": {
                "grade_1": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_2": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_3": {"cost": {}, "engineers": ["Zacariah Nemo"]},
                "grade_4": {"cost": {}, "engineers": ["Zacariah Nemo"]},
                "grade_5": {"cost": {}, "engineers": ["Zacariah Nemo", "Marsha Hicks"]}
            },
            "Mine Launcher": {
                "grade_1": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_2": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_3": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_4": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_5": {"cost": {}, "engineers": ["Juri Ishmaak", "Petra Olmanova"]}
            },
            "Missile Rack": {
                "grade_1": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_2": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_3": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_4": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_5": {"cost": {}, "engineers": ["Liz Ryder", "Petra Olmanova"]}
            },
            "Multi-cannon": {
                "grade_1": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Zacariah Nemo"]},
                "grade_2": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Zacariah Nemo"]},
                "grade_3": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Zacariah Nemo"]},
                "grade_4": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Marsha Hicks"]},
                "grade_5": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Marsha Hicks"]}
            },
            "Rail Gun": {
                "grade_1": {"cost": {}, "engineers": ["The Sarge"]},
                "grade_2": {"cost": {}, "engineers": ["The Sarge"]},
                "grade_3": {"cost": {}, "engineers": ["The Sarge"]},
                "grade_4": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_5": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn", "Etienne Dorn"]}
            },
            "Seeker Missile Rack": {
                "grade_1": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_2": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_3": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_4": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_5": {"cost": {}, "engineers": ["Liz Ryder", "Petra Olmanova"]}
            },
            "Power Distributor": {
                "grade_1": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_2": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_3": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_4": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_5": {"cost": {}, "engineers": ["The Dweller"]}
            }
        }
    },
    "Double shot": {
        "module_recipes": {
            "Fragment Cannon": {
                "grade_1": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_2": {"cost": {}, "engineers": ["Tod 'The Blaster' McQuinn"]},
                "grade_3": {"cost": {}, "engineers": ["Zacariah Nemo"]},
                "grade_4": {"cost": {}, "engineers": ["Zacariah Nemo"]},
                "grade_5": {"cost": {}, "engineers": ["Zacariah Nemo", "Marsha Hicks"]}
            }
        }
    },
    "Anti-Guardian Zone Resistance": {
        "module_recipes": {
            "Guardian Gauss Cannon": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Guardian Nanite Torpedo Pylon": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Guardian Plasma Charger": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Guardian Shard Cannon": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Guardian FSD Booster": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Guardian Hull Reinforcement": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Guardian Module Reinforcement": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Guardian Shield Reinforcement": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Guardian Hybrid Power Distributor": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Guardian Power Plant": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            }
        }
    },
    "Ammo capacity": {
        "module_recipes": {
            "Caustic Sink Launcher": {
                "grade_1": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_2": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_3": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_4": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_5": {"cost": {}, "engineers": ["Ram Tah"]}
            },
            "Chaff Launcher": {
                "grade_1": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_2": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_3": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_4": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_5": {"cost": {}, "engineers": ["Juri Ishmaak"]}
            },
            "Heat Sink Launcher": {
                "grade_1": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_2": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_3": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_4": {"cost": {}, "engineers": ["Ram Tah"]},
                "grade_5": {"cost": {}, "engineers": ["Ram Tah"]}
            },
            "Point Defence": {
                "grade_1": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_2": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_3": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_4": {"cost": {}, "engineers": ["Juri Ishmaak"]},
                "grade_5": {"cost": {}, "engineers": ["Juri Ishmaak"]}
            }
        }
    },
    "Reinforced": {
        "module_recipes": {
            "Caustic Sink Launcher": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Chaff Launcher": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Electronic Countermeasure": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Frame Shift Wake Scanner": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Heat Sink Launcher": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Kill Warrant Scanner": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Manifest Scanner": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Point Defence": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Collector Limpet Controller": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Fuel Transfer Limpet Controller": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Hatch Breaker Limpet Controller": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Prospector Limpet Controller": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Shield Generator": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Life Support": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Thrusters": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            }
        }
    },
    "Shielded": {
        "module_recipes": {
            "Caustic Sink Launcher": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Chaff Launcher": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Electronic Countermeasure": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Frame Shift Wake Scanner": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Heat Sink Launcher": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Kill Warrant Scanner": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Manifest Scanner": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Point Defence": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Auto Field-Maintenance Unit": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Collector Limpet Controller": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Fuel Scoop": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Fuel Transfer Limpet Controller": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Hatch Breaker Limpet Controller": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Prospector Limpet Controller": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Refinery": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Frame Shift Drive": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Life Support": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            },
            "Power Distributor": {
                "grade_1": {
                    "cost": {},
                    "engineers": []
                }
            }
        }
    },
    "Fast scan": {
        "module_recipes": {
            "Frame Shift Wake Scanner": {
                "grade_1": {"cost": {}, "engineers": ["Tiana Fortune"]},
                "grade_2": {"cost": {}, "engineers": ["Tiana Fortune"]},
                "grade_3": {"cost": {}, "engineers": ["Tiana Fortune"]},
                "grade_4": {"cost": {}, "engineers": ["Tiana Fortune"]},
                "grade_5": {"cost": {}, "engineers": ["Tiana Fortune"]}
            },
            "Kill Warrant Scanner": {
                "grade_1": {"cost": {}, "engineers": ["Lori Jameson"]},
                "grade_2": {"cost": {}, "engineers": ["Lori Jameson"]},
                "grade_3": {"cost": {}, "engineers": ["Lori Jameson"]},
                "grade_4": {"cost": {}, "engineers": ["Lori Jameson"]},
                "grade_5": {"cost": {}, "engineers": ["Lori Jameson"]}
            },
            "Manifest Scanner": {
                "grade_1": {"cost": {}, "engineers": ["Lori Jameson"]},
                "grade_2": {"cost": {}, "engineers": ["Lori Jameson"]},
                "grade_3": {"cost": {}, "engineers": ["Lori Jameson"]},
                "grade_4": {"cost": {}, "engineers": ["Lori Jameson"]},
                "grade_5": {"cost": {}, "engineers": ["Lori Jameson"]}
            }
        }
    },
    "Wide angle": {
        "module_recipes": {
            "Frame Shift Wake Scanner": {
                "grade_1": {"cost": {}, "engineers": ["Tiana Fortune"]},
                "grade_2": {"cost": {}, "engineers": ["Tiana Fortune"]},
                "grade_3": {"cost": {}, "engineers": ["Tiana Fortune"]},
                "grade_4": {"cost": {}, "engineers": ["Tiana Fortune"]},
                "grade_5": {"cost": {}, "engineers": ["Tiana Fortune"]}
            },
            "Kill Warrant Scanner": {
                "grade_1": {"cost": {}, "engineers": ["Lori Jameson"]},
                "grade_2": {"cost": {}, "engineers": ["Lori Jameson"]},
                "grade_3": {"cost": {}, "engineers": ["Lori Jameson"]},
                "grade_4": {"cost": {}, "engineers": ["Lori Jameson"]},
                "grade_5": {"cost": {}, "engineers": ["Lori Jameson"]}
            },
            "Manifest Scanner": {
                "grade_1": {"cost": {}, "engineers": ["Lori Jameson"]},
                "grade_2": {"cost": {}, "engineers": ["Lori Jameson"]},
                "grade_3": {"cost": {}, "engineers": ["Lori Jameson"]},
                "grade_4": {"cost": {}, "engineers": ["Lori Jameson"]},
                "grade_5": {"cost": {}, "engineers": ["Lori Jameson"]}
            },
            "Sensors": {
                "grade_1": {"cost": {}, "engineers": ["Felicity Farseer"]},
                "grade_2": {"cost": {}, "engineers": ["Felicity Farseer"]},
                "grade_3": {"cost": {}, "engineers": ["Felicity Farseer"]},
                "grade_4": {"cost": {}, "engineers": ["Lori Jameson"]},
                "grade_5": {"cost": {}, "engineers": ["Lori Jameson"]}
            }
        }
    },
    "Blast resistant": {
        "module_recipes": {
            "Shield Booster": {
                "grade_1": {"cost": {}, "engineers": ["Didi Vatermann"]},
                "grade_2": {"cost": {}, "engineers": ["Didi Vatermann"]},
                "grade_3": {"cost": {}, "engineers": ["Didi Vatermann"]},
                "grade_4": {"cost": {}, "engineers": ["Lei Cheung"]},
                "grade_5": {"cost": {}, "engineers": ["Lei Cheung"]}
            },
            "Hull Reinforcement Package": {
                "grade_1": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_2": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_3": {"cost": {}, "engineers": ["Petra Olmanova"]},
                "grade_4": {"cost": {}, "engineers": ["Petra Olmanova"]},
                "grade_5": {"cost": {}, "engineers": ["Petra Olmanova"]}
            },
            "Armour": {
                "grade_1": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_2": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_3": {"cost": {}, "engineers": ["Petra Olmanova"]},
                "grade_4": {"cost": {}, "engineers": ["Petra Olmanova"]},
                "grade_5": {"cost": {}, "engineers": ["Petra Olmanova"]}
            }
        }
    },
    "Heavy duty": {
        "module_recipes": {
            "Shield Booster": {
                "grade_1": {"cost": {}, "engineers": ["Didi Vatermann"]},
                "grade_2": {"cost": {}, "engineers": ["Didi Vatermann"]},
                "grade_3": {"cost": {}, "engineers": ["Didi Vatermann"]},
                "grade_4": {"cost": {}, "engineers": ["Lei Cheung"]},
                "grade_5": {"cost": {}, "engineers": ["Lei Cheung"]}
            },
            "Hull Reinforcement Package": {
                "grade_1": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_2": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_3": {"cost": {}, "engineers": ["Petra Olmanova"]},
                "grade_4": {"cost": {}, "engineers": ["Petra Olmanova"]},
                "grade_5": {"cost": {}, "engineers": ["Petra Olmanova"]}
            },
            "Armour": {
                "grade_1": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_2": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_3": {"cost": {}, "engineers": ["Petra Olmanova"]},
                "grade_4": {"cost": {}, "engineers": ["Petra Olmanova"]},
                "grade_5": {"cost": {}, "engineers": ["Petra Olmanova"]}
            }
        }
    },
    "Kinetic resistant": {
        "module_recipes": {
            "Shield Booster": {
                "grade_1": {"cost": {}, "engineers": ["Didi Vatermann"]},
                "grade_2": {"cost": {}, "engineers": ["Didi Vatermann"]},
                "grade_3": {"cost": {}, "engineers": ["Didi Vatermann"]},
                "grade_4": {"cost": {}, "engineers": ["Lei Cheung"]},
                "grade_5": {"cost": {}, "engineers": ["Lei Cheung"]}
            },
            "Hull Reinforcement Package": {
                "grade_1": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_2": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_3": {"cost": {}, "engineers": ["Petra Olmanova"]},
                "grade_4": {"cost": {}, "engineers": ["Petra Olmanova"]},
                "grade_5": {"cost": {}, "engineers": ["Petra Olmanova"]}
            },
            "Shield Generator": {
                "grade_1": {"cost": {}, "engineers": ["Elvira Martuuk"]},
                "grade_2": {"cost": {}, "engineers": ["Didi Vatermann", "Lei Cheung"]},
                "grade_3": {"cost": {}, "engineers": ["Didi Vatermann", "Lei Cheung"]},
                "grade_4": {"cost": {}, "engineers": ["Didi Vatermann", "Lei Cheung"]},
                "grade_5": {"cost": {}, "engineers": ["Didi Vatermann", "Lei Cheung"]}
            },
            "Armour": {
                "grade_1": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_2": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_3": {"cost": {}, "engineers": ["Petra Olmanova"]},
                "grade_4": {"cost": {}, "engineers": ["Petra Olmanova"]},
                "grade_5": {"cost": {}, "engineers": ["Petra Olmanova"]}
            }
        }
    },
    "Resistance augmented": {
        "module_recipes": {
            "Shield Booster": {
                "grade_1": {"cost": {}, "engineers": ["Didi Vatermann"]},
                "grade_2": {"cost": {}, "engineers": ["Didi Vatermann"]},
                "grade_3": {"cost": {}, "engineers": ["Didi Vatermann"]},
                "grade_4": {"cost": {}, "engineers": ["Lei Cheung"]},
                "grade_5": {"cost": {}, "engineers": ["Lei Cheung"]}
            }
        }
    },
    "Thermal resistant": {
        "module_recipes": {
            "Shield Booster": {
                "grade_1": {"cost": {}, "engineers": ["Didi Vatermann"]},
                "grade_2": {"cost": {}, "engineers": ["Didi Vatermann"]},
                "grade_3": {"cost": {}, "engineers": ["Didi Vatermann"]},
                "grade_4": {"cost": {}, "engineers": ["Lei Cheung"]},
                "grade_5": {"cost": {}, "engineers": ["Lei Cheung"]}
            },
            "Hull Reinforcement Package": {
                "grade_1": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_2": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_3": {"cost": {}, "engineers": ["Petra Olmanova"]},
                "grade_4": {"cost": {}, "engineers": ["Petra Olmanova"]},
                "grade_5": {"cost": {}, "engineers": ["Petra Olmanova"]}
            },
            "Shield Generator": {
                "grade_1": {"cost": {}, "engineers": ["Elvira Martuuk"]},
                "grade_2": {"cost": {}, "engineers": ["Didi Vatermann", "Lei Cheung"]},
                "grade_3": {"cost": {}, "engineers": ["Didi Vatermann", "Lei Cheung"]},
                "grade_4": {"cost": {}, "engineers": ["Didi Vatermann", "Lei Cheung"]},
                "grade_5": {"cost": {}, "engineers": ["Didi Vatermann", "Lei Cheung"]}
            },
            "Armour": {
                "grade_1": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_2": {"cost": {}, "engineers": ["Liz Ryder"]},
                "grade_3": {"cost": {}, "engineers": ["Petra Olmanova"]},
                "grade_4": {"cost": {}, "engineers": ["Petra Olmanova"]},
                "grade_5": {"cost": {}, "engineers": ["Petra Olmanova"]}
            }
        }
    },
    "Expanded probe scanning radius": {
        "module_recipes": {
            "Detailed Surface Scanner": {
                "grade_1": {"cost": {}, "engineers": ["Felicity Farseer", "Juri Ishmaak", "Tiana Fortune", "Bill Turner", "Lori Jameson", "Etienne Dorn"]},
                "grade_2": {"cost": {}, "engineers": ["Juri Ishmaak", "Tiana Fortune", "Bill Turner", "Lori Jameson", "Etienne Dorn"]},
                "grade_3": {"cost": {}, "engineers": ["Felicity Farseer", "Juri Ishmaak", "Tiana Fortune", "Bill Turner", "Lori Jameson", "Etienne Dorn"]},
                "grade_4": {"cost": {}, "engineers": ["Lei Cheung", "Hera Tani", "Bill Turner", "Lori Jameson", "Etienne Dorn"]},
                "grade_5": {"cost": {}, "engineers": ["Lei Cheung", "Hera Tani", "Juri Ishmaak", "Tiana Fortune", "Bill Turner", "Lori Jameson", "Etienne Dorn"]}
            }
        }
    },
    "Expanded capture arc": {
        "module_recipes": {
            "Frame Shift Drive Interdictor": {
                "grade_1": {"cost": {}, "engineers": ["Felicity Farseer"]},
                "grade_2": {"cost": {}, "engineers": ["Tiana Fortune"]},
                "grade_3": {"cost": {}, "engineers": ["Tiana Fortune"]},
                "grade_4": {"cost": {}, "engineers": ["Colonel Bris Dekker"]},
                "grade_5": {"cost": {}, "engineers": ["Mel Brandon"]}
            }
        }
    },
    "Rapid charge": {
        "module_recipes": {
            "Shield Cell Bank": {
                "grade_1": {"cost": {}, "engineers": ["Elvira Martuuk"]},
                "grade_2": {"cost": {}, "engineers": ["Lori Jameson"]},
                "grade_3": {"cost": {}, "engineers": ["Lori Jameson"]},
                "grade_4": {"cost": {}, "engineers": ["Mel Brandon"]},
                "grade_5": {"cost": {}, "engineers": ["Mel Brandon"]}
            }
        }
    },
    "Specialised": {
        "module_recipes": {
            "Shield Cell Bank": {
                "grade_1": {"cost": {}, "engineers": ["Elvira Martuuk"]},
                "grade_2": {"cost": {}, "engineers": ["Lori Jameson"]},
                "grade_3": {"cost": {}, "engineers": ["Lori Jameson"]},
                "grade_4": {"cost": {}, "engineers": ["Mel Brandon"]},
                "grade_5": {"cost": {}, "engineers": ["Mel Brandon"]}
            }
        }
    },
    "Enhanced low power": {
        "module_recipes": {
            "Shield Generator": {
                "grade_1": {"cost": {}, "engineers": ["Elvira Martuuk"]},
                "grade_2": {"cost": {}, "engineers": ["Didi Vatermann", "Lei Cheung"]},
                "grade_3": {"cost": {}, "engineers": ["Elvira Martuuk", "Didi Vatermann", "Lei Cheung"]},
                "grade_4": {"cost": {}, "engineers": ["Didi Vatermann", "Lei Cheung"]},
                "grade_5": {"cost": {}, "engineers": ["Didi Vatermann", "Lei Cheung", "Mel Brandon"]}
            }
        }
    },
    "Faster boot sequence": {
        "module_recipes": {
            "Frame Shift Drive": {
                "grade_1": {"cost": {}, "engineers": ["Felicity Farseer", "Elvira Martuuk", "Colonel Bris Dekker", "Professor Palin", "Chloe Sedesi"]},
                "grade_2": {"cost": {}, "engineers": ["Elvira Martuuk", "Colonel Bris Dekker", "Professor Palin", "Chloe Sedesi"]},
                "grade_3": {"cost": {}, "engineers": ["Elvira Martuuk", "Colonel Bris Dekker", "Professor Palin", "Chloe Sedesi"]},
                "grade_4": {"cost": {}, "engineers": ["Felicity Farseer", "Elvira Martuuk"]},
                "grade_5": {"cost": {}, "engineers": ["Felicity Farseer", "Elvira Martuuk", "Mel Brandon"]}
            }
        }
    },
    "Increased range": {
        "module_recipes": {
            "Frame Shift Drive": {
                "grade_1": {"cost": {}, "engineers": ["Felicity Farseer", "Elvira Martuuk", "Colonel Bris Dekker", "Professor Palin", "Chloe Sedesi"]},
                "grade_2": {"cost": {}, "engineers": ["Elvira Martuuk", "Colonel Bris Dekker", "Professor Palin", "Chloe Sedesi"]},
                "grade_3": {"cost": {}, "engineers": ["Elvira Martuuk", "Colonel Bris Dekker", "Professor Palin", "Chloe Sedesi"]},
                "grade_4": {"cost": {}, "engineers": ["Felicity Farseer", "Elvira Martuuk"]},
                "grade_5": {"cost": {}, "engineers": ["Felicity Farseer", "Elvira Martuuk", "Mel Brandon"]}
            }
        }
    },
    "Charge enhanced": {
        "module_recipes": {
            "Power Distributor": {
                "grade_1": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_2": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_3": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_4": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_5": {"cost": {}, "engineers": ["The Dweller"]}
            }
        }
    },
    "Engine focused": {
        "module_recipes": {
            "Power Distributor": {
                "grade_1": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_2": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_3": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_4": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_5": {"cost": {}, "engineers": ["The Dweller"]}
            }
        }
    },
    "System focused": {
        "module_recipes": {
            "Power Distributor": {
                "grade_1": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_2": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_3": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_4": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_5": {"cost": {}, "engineers": ["The Dweller"]}
            }
        }
    },
    "Weapon focused": {
        "module_recipes": {
            "Power Distributor": {
                "grade_1": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_2": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_3": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_4": {"cost": {}, "engineers": ["The Dweller"]},
                "grade_5": {"cost": {}, "engineers": ["The Dweller"]}
            }
        }
    },
    "Armoured": {
        "module_recipes": {
            "Power Plant": {
                "grade_1": {"cost": {}, "engineers": ["Felicity Farseer"]},
                "grade_2": {"cost": {}, "engineers": ["Marco Qwent"]},
                "grade_3": {"cost": {}, "engineers": ["Marco Qwent", "Hera Tani"]},
                "grade_4": {"cost": {}, "engineers": ["Marco Qwent", "Hera Tani"]},
                "grade_5": {"cost": {}, "engineers": ["Hera Tani", "Etienne Dorn"]}
            }
        }
    },
    "Low emissions": {
        "module_recipes": {
            "Power Plant": {
                "grade_1": {"cost": {}, "engineers": ["Felicity Farseer"]},
                "grade_2": {"cost": {}, "engineers": ["Marco Qwent"]},
                "grade_3": {"cost": {}, "engineers": ["Marco Qwent", "Hera Tani"]},
                "grade_4": {"cost": {}, "engineers": ["Marco Qwent", "Hera Tani"]},
                "grade_5": {"cost": {}, "engineers": ["Hera Tani", "Etienne Dorn"]}
            }
        }
    },
    "Clean": {
        "module_recipes": {
            "Thrusters": {
                "grade_1": {"cost": {}, "engineers": ["Felicity Farseer"]},
                "grade_2": {"cost": {}, "engineers": ["Elvira Martuuk"]},
                "grade_3": {"cost": {}, "engineers": ["Felicity Farseer", "Elvira Martuuk", "Professor Palin"]},
                "grade_4": {"cost": {}, "engineers": ["Professor Palin", "Mel Brandon", "Chloe Sedesi"]},
                "grade_5": {"cost": {}, "engineers": ["Professor Palin", "Mel Brandon", "Chloe Sedesi"]}
            }
        }
    },
    "Dirty": {
        "module_recipes": {
            "Thrusters": {
                "grade_1": {"cost": {}, "engineers": ["Felicity Farseer"]},
                "grade_2": {"cost": {}, "engineers": ["Elvira Martuuk"]},
                "grade_3": {"cost": {}, "engineers": ["Felicity Farseer", "Elvira Martuuk", "Professor Palin"]},
                "grade_4": {"cost": {}, "engineers": ["Professor Palin", "Mel Brandon", "Chloe Sedesi"]},
                "grade_5": {"cost": {}, "engineers": ["Professor Palin", "Mel Brandon", "Chloe Sedesi"]}
            }
        }
    }
}


def engineer_finder(obj, projected_states):
    ship_engineers = {
        300260: {"Engineer": "Tod 'The Blaster' McQuinn", "Location": "Wolf 397", 
                "Modifies": {"Multi-cannon": 5, "Rail Gun": 5, "Cannon": 2, "Fragment Cannon": 2}, 
                "HowToFind": "Available from start", "HowToGetInvite": "15 bounty vouchers earned", 
                "HowToUnlock": "100,001 CR of bounty vouchers provided", "HowToGainRep": "Modules crafted or Alliance vouchers handed in"},
        300100: {"Engineer": "Felicity Farseer", "Location": "Deciat", 
                "Modifies": {"Frame Shift Drive": 5, "Detailed Surface Scanner": 3, "Sensors": 3, "Thrusters": 3, "Power Plant": 1, "Frame Shift Drive Interdictor": 1, "Shield Booster": 1}, 
                "HowToFind": "Available from start", "HowToGetInvite": "Exploration rank Scout or higher reached", 
                "HowToUnlock": "1 Meta-Alloy provided", "HowToGainRep": "Modules crafted or exploration data sold"},
        300160: {"Engineer": "Elvira Martuuk", "Location": "Khun", 
                "Modifies": {"Frame Shift Drive": 5, "Shield Generator": 3, "Thrusters": 2, "Shield Cell Bank": 1}, 
                "HowToFind": "Available from start", "HowToGetInvite": "300+ ly from starting system traveled", 
                "HowToUnlock": "3 Soontill Relics provided", "HowToGainRep": "Modules crafted or exploration data sold"},
        300080: {"Engineer": "Liz Ryder", "Location": "Eurybia", 
                "Modifies": {"Missile Rack": 5, "Seeker Missile Rack": 5, "Torpedo Pylon": 5, "Mine Launcher": 3, "Hull Reinforcement Package": 1, "Armour": 1}, 
                "HowToFind": "Available from start", "HowToGetInvite": "Friendly with Eurybia Blue Mafia achieved", 
                "HowToUnlock": "200 Landmines provided", "HowToGainRep": "Modules crafted or commodities sold"},
        300180: {"Engineer": "The Dweller", "Location": "Wyrd", 
                "Modifies": {"Beam Laser": 3, "Burst Laser": 3, "Pulse Laser": 4, "Power Distributor": 5}, 
                "HowToFind": "Available from start", "HowToGetInvite": "5 Black Markets dealt with", 
                "HowToUnlock": "500,000 CR paid", "HowToGainRep": "Modules crafted or commodities sold"},
        300120: {"Engineer": "Lei Cheung", "Location": "Laksak", 
                "Modifies": {"Shield Generator": 5, "Detailed Surface Scanner": 5, "Sensors": 5, "Shield Booster": 3}, 
                "HowToFind": "Introduced by The Dweller", "HowToGetInvite": "50 markets traded with", 
                "HowToUnlock": "200 Gold provided", "HowToGainRep": "Modules crafted"},
        300210: {"Engineer": "Selene Jean", "Location": "Kuk", 
                "Modifies": {"Armour": 5, "Hull Reinforcement Package": 5}, 
                "HowToFind": "Introduced by Tod McQuinn", "HowToGetInvite": "500 tons of ore mined", 
                "HowToUnlock": "10 Painite provided", "HowToGainRep": "Modules crafted or commodities/data sold"},
        300090: {"Engineer": "Hera Tani", "Location": "Kuwemaki", 
                "Modifies": {"Detailed Surface Scanner": 5, "Power Plant": 5, "Power Distributor": 3, "Sensors": 3}, 
                "HowToFind": "Introduced by Liz Ryder", "HowToGetInvite": "Imperial Navy rank Outsider achieved", 
                "HowToUnlock": "50 Kamitra Cigars provided", "HowToGainRep": "Modules crafted or commodities sold"},
        300030: {"Engineer": "Broo Tarquin", "Location": "Muang", 
                "Modifies": {"Beam Laser": 5, "Burst Laser": 5, "Pulse Laser": 5}, 
                "HowToFind": "Introduced by Hera Tani", "HowToGetInvite": "Combat rank Competent or higher achieved", 
                "HowToUnlock": "50 Fujin Tea provided", "HowToGainRep": "Modules crafted"},
        300200: {"Engineer": "Marco Qwent", "Location": "Sirius (Permit Required)", 
                "Modifies": {"Power Plant": 4, "Power Distributor": 3}, 
                "HowToFind": "Introduced by Elvira Martuuk", "HowToGetInvite": "Sirius Corporation invitation obtained", 
                "HowToUnlock": "25 Modular Terminals provided", "HowToGainRep": "Modules crafted or commodities sold"},
        300050: {"Engineer": "Zacariah Nemo", "Location": "Yoru", 
                "Modifies": {"Fragment Cannon": 5, "Multi-cannon": 3, "Plasma Accelerator": 2}, 
                "HowToFind": "Introduced by Elvira Martuuk", "HowToGetInvite": "Party of Yoru invitation received", 
                "HowToUnlock": "25 Xihe Biomorphic Companions provided", "HowToGainRep": "Modules crafted or commodities sold"},
        300000: {"Engineer": "Didi Vatermann", "Location": "Leesti", 
                "Modifies": {"Shield Booster": 5, "Shield Generator": 3}, 
                "HowToFind": "Introduced by Selene Jean", "HowToGetInvite": "Trade rank Merchant or higher achieved", 
                "HowToUnlock": "50 Lavian Brandy provided", "HowToGainRep": "Modules crafted"},
        300140: {"Engineer": "Colonel Bris Dekker", "Location": "Sol (Permit Required)", 
                "Modifies": {"Frame Shift Drive Interdictor": 4, "Frame Shift Drive": 3}, 
                "HowToFind": "Introduced by Juri Ishmaak", "HowToGetInvite": "Federation friendly status achieved", 
                "HowToUnlock": "1,000,000 CR of combat bonds provided", "HowToGainRep": "Modules crafted"},
        300250: {"Engineer": "Juri Ishmaak", "Location": "Giryak", 
                "Modifies": {"Detailed Surface Scanner": 5, "Mine Launcher": 5, "Sensors": 5, "Frame Shift Wake Scanner": 3, "Kill Warrant Scanner": 3, "Manifest Scanner": 3, "Missile Rack": 3, "Seeker Missile Rack": 3, "Torpedo Pylon": 3}, 
                "HowToFind": "Introduced by Felicity Farseer", "HowToGetInvite": "50+ combat bonds earned", 
                "HowToUnlock": "100,000 CR of combat bonds provided", "HowToGainRep": "Modules crafted or combat bonds handed in"},
        300220: {"Engineer": "Professor Palin", "Location": "Arque", 
                "Modifies": {"Thrusters": 5, "Frame Shift Drive": 3}, 
                "HowToFind": "Introduced by Marco Qwent", "HowToGetInvite": "5,000 ly from start location traveled", 
                "HowToUnlock": "25 Sensor Fragments provided", "HowToGainRep": "Modules crafted or exploration data sold"},
        300010: {"Engineer": "Bill Turner", "Location": "Alioth (Permit Required)", 
                "Modifies": {"Sensors": 5, "Plasma Accelerator": 5, "AFMU": 3, "Detailed Surface Scanner": 5, "Frame Shift Wake Scanner": 3, "Fuel Scoop": 3, "Kill Warrant Scanner": 3, "Life Support": 3, "Manifest Scanner": 3, "Refinery": 3}, 
                "HowToFind": "Introduced by Selene Jean", "HowToGetInvite": "Alliance friendly status achieved", 
                "HowToUnlock": "50 Bromellite provided", "HowToGainRep": "Modules crafted"},
        300230: {"Engineer": "Lori Jameson", "Location": "Shinrarta Dezhra (Permit Required)", 
                "Modifies": {"Detailed Surface Scanner": 5, "Sensors": 5, "AFMU": 4, "Fuel Scoop": 4, "Life Support": 4, "Refinery": 4, "Frame Shift Wake Scanner": 3, "Manifest Scanner": 3, "Shield Cell Bank": 3}, 
                "HowToFind": "Introduced by Marco Qwent", "HowToGetInvite": "Combat rank Dangerous or higher achieved", 
                "HowToUnlock": "25 Konnga Ale provided", "HowToGainRep": "Modules crafted or exploration data sold"},
        300110: {"Engineer": "Ram Tah", "Location": "Meene", 
                "Modifies": {"Chaff Launcher": 5, "ECM": 5, "Heat Sink Launcher": 5, "Point Defence": 5, "Collector Limpet Controller": 4, "Fuel Transfer Limpet Controller": 4, "Prospector Limpet Controller": 4, "Hatch Breaker Limpet Controller": 3}, 
                "HowToFind": "Introduced by Lei Cheung", "HowToGetInvite": "Exploration rank Surveyor or higher achieved", 
                "HowToUnlock": "50 Classified Scan Databanks provided", "HowToGainRep": "Modules crafted or exploration data sold"},
        300270: {"Engineer": "Tiana Fortune", "Location": "Achenar (Permit Required)", 
                "Modifies": {"Manifest Scanner": 5, "Collector Limpet Controller": 5, "Frame Shift Wake Scanner": 5, "Fuel Transfer Limpet Controller": 5, "Hatch Breaker Limpet Controller": 5, "Kill Warrant Scanner": 5, "Prospector Limpet Controller": 5, "Sensors": 5, "Detailed Surface Scanner": 3, "Frame Shift Drive Interdictor": 3}, 
                "HowToFind": "Introduced by Hera Tani", "HowToGetInvite": "Empire friendly status achieved", 
                "HowToUnlock": "50 Decoded Emission Data provided", "HowToGainRep": "Modules crafted or commodities sold"},
        300040: {"Engineer": "The Sarge", "Location": "Beta-3 Tucani", 
                "Modifies": {"Cannon": 5, "Collector Limpet Controller": 5, "Fuel Transfer Limpet Controller": 5, "Hatch Breaker Limpet Controller": 5, "Prospector Limpet Controller": 5, "Rail Gun": 3}, 
                "HowToFind": "Introduced by Juri Ishmaak", "HowToGetInvite": "Federal Navy rank Midshipman achieved", 
                "HowToUnlock": "50 Aberrant Shield Pattern Analysis provided", "HowToGainRep": "Modules crafted or exploration data sold"},
        300290: {"Engineer": "Etienne Dorn", "Location": "Los", 
                "Modifies": {"Detailed Surface Scanner": 5, "Frame Shift Wake Scanner": 5, "Kill Warrant Scanner": 5, "Life Support": 5, "Manifest Scanner": 5, "Plasma Accelerator": 5, "Power Distributor": 5, "Power Plant": 5, "Sensors": 5, "Rail Gun": 5}, 
                "HowToFind": "Introduced by Liz Ryder", "HowToGetInvite": "Trade rank Dealer or higher achieved", 
                "HowToUnlock": "25 Occupied Escape Pods provided", "HowToGainRep": "Modules crafted"},
        300150: {"Engineer": "Marsha Hicks", "Location": "Tir", 
                "Modifies": {"Cannon": 5, "Fragment Cannon": 5, "Fuel Scoop": 5, "Fuel Transfer Limpet Controller": 5, "Hatch Breaker Limpet Controller": 5, "Multi-cannon": 5, "Prospector Limpet Controller": 5, "Refinery": 5}, 
                "HowToFind": "Introduced by The Dweller", "HowToGetInvite": "Exploration rank Surveyor or higher achieved", 
                "HowToUnlock": "10 Osmium mined", "HowToGainRep": "Modules crafted"},
        300280: {"Engineer": "Mel Brandon", "Location": "Luchtaine", 
                "Modifies": {"Beam Laser": 5, "Burst Laser": 5, "Pulse Laser": 5, "Shield Generator": 5, "Thrusters": 5, "Shield Booster": 5, "Frame Shift Drive": 5, "Frame Shift Drive Interdictor": 5, "Shield Cell Bank": 4}, 
                "HowToFind": "Introduced by Elvira Martuuk", "HowToGetInvite": "Colonia Council invitation received", 
                "HowToUnlock": "100,000 CR of bounty vouchers provided", "HowToGainRep": "Modules crafted"},
        300130: {"Engineer": "Petra Olmanova", "Location": "Asura", 
                "Modifies": {"Armour": 5, "AFMU": 5, "Chaff Launcher": 5, "ECM": 5, "Heat Sink Launcher": 5, "Hull Reinforcement Package": 5, "Mine Launcher": 5, "Missile Rack": 5, "Point Defence": 5, "Seeker Missile Rack": 5, "Torpedo Pylon": 5}, 
                "HowToFind": "Introduced by Tod McQuinn", "HowToGetInvite": "Combat rank Expert or higher achieved", 
                "HowToUnlock": "200 Progenitor Cells provided", "HowToGainRep": "Modules crafted"},
        300300: {"Engineer": "Chloe Sedesi", "Location": "Shenve", 
                "Modifies": {"Thrusters": 5, "Frame Shift Drive": 3}, 
                "HowToFind": "Introduced by Marco Qwent", "HowToGetInvite": "5,000 ly from start location traveled", 
                "HowToUnlock": "25 Sensor Fragments provided", "HowToGainRep": "Modules crafted or exploration data sold"}
    }
    
    # Define suit engineers data
    suit_engineers = {
        400002: {"Engineer": "Domino Green", "Location": "Orishis", 
                "Modifies": {"Enhanced Tracking": 1, "Extra Backpack Capacity": 1, "Reduced Tool Battery Consumption": 1, "Greater Range": 1, "Stability": 1},
                "HowToFind": "Available from start", "HowToGetInvite": "100ly in Apex Transport traveled", 
                "HowToReferral": "5 Push required"},
        400003: {"Engineer": "Hero Ferrari", "Location": "Siris", 
                "Modifies": {"Improved Jump Assist": 1, "Increased Air Reserves": 1, "Faster Handling": 1, "Noise Suppressor": 1},
                "HowToFind": "Available from start", "HowToGetInvite": "10 Conflict Zones completed", 
                "HowToReferral": "15 Settlement Defence Plans required"},
        400001: {"Engineer": "Jude Navarro", "Location": "Aurai", 
                "Modifies": {"Added Melee Damage": 1, "Damage Resistance": 1, "Extra Ammo Capacity": 1, "Magazine Size": 1, "Reload Speed": 1},
                "HowToFind": "Available from start", "HowToGetInvite": "10 Restore/Reactivation missions completed", 
                "HowToReferral": "5 Genetic Repair Meds required"},
        400004: {"Engineer": "Kit Fowler", "Location": "Capoya", 
                "Modifies": {"Added Melee Damage": 1, "Extra Ammo Capacity": 1, "Faster Shield Regen": 1, "Magazine Size": 1, "Stowed Reloading": 1},
                "HowToFind": "Introduced by Domino Green", "HowToGetInvite": "10 Opinion Polls sold to Bartenders", 
                "HowToReferral": "5 Surveillance Equipment required"},
        400008: {"Engineer": "Oden Geiger", "Location": "Candiaei", 
                "Modifies": {"Enhanced Tracking": 1, "Improved Battery Capacity": 1, "Night Vision": 1, "Scope": 1, "Stability": 1},
                "HowToFind": "Introduced by Terra Velasquez", "HowToGetInvite": "20 Biological/Genetic items sold to Bartenders", 
                "HowToReferral": "N/A"},
        400006: {"Engineer": "Terra Velasquez", "Location": "Shou Xing", 
                "Modifies": {"Combat Movement Speed": 1, "Increased Air Reserves": 1, "Increased Sprint Duration": 1, "Improved Hip Fire Accuracy": 1, "Noise Suppressor": 1},
                "HowToFind": "Introduced by Jude Navarro", "HowToGetInvite": "12 Covert missions completed", 
                "HowToReferral": "15 Financial Projections required"},
        400007: {"Engineer": "Uma Laszlo", "Location": "Xuane", 
                "Modifies": {"Damage Resistance": 1, "Faster Shield Regen": 1, "Headshot Damage": 1, "Reload Speed": 1, "Stowed Reloading": 1},
                "HowToFind": "Introduced by Wellington Beck", "HowToGetInvite": "Sirius Corp unfriendly status reached", 
                "HowToReferral": "N/A"},
        400005: {"Engineer": "Wellington Beck", "Location": "Jolapa", 
                "Modifies": {"Extra Backpack Capacity": 1, "Improved Battery Capacity": 1, "Reduced Tool Battery Consumption": 1, "Greater Range": 1, "Scope": 1},
                "HowToFind": "Introduced by Hero Ferrari", "HowToGetInvite": "25 Entertainment items sold to Bartenders", 
                "HowToReferral": "5 InSight Entertainment Suites required"},
        400009: {"Engineer": "Yarden Bond", "Location": "Bayan", 
                "Modifies": {"Combat Movement Speed": 1, "Improved Jump Assist": 1, "Quieter Footsteps": 1, "Audio Masking": 1, "Faster Handling": 1, "Improved Hip Fire Accuracy": 1},
                "HowToFind": "Introduced by Kit Fowler", "HowToGetInvite": "8 Smear Campaign Plans sold to Bartenders", 
                "HowToReferral": "N/A"},
        400010: {"Engineer": "Baltanos", "Location": "Deriso", 
                "Modifies": {"Combat Movement Speed": 1, "Improved Jump Assist": 1, "Increased Air Reserves": 1, "Increased Sprint Duration": 1, "Faster Handling": 1, "Improved Hip Fire Accuracy": 1, "Noise Suppressor": 1},
                "HowToFind": "Available in Colonia", "HowToGetInvite": "Colonia Council friendly status achieved", 
                "HowToReferral": "10 Faction Associates required"},
        400011: {"Engineer": "Eleanor Bresa", "Location": "Desy", 
                "Modifies": {"Added Melee Damage": 1, "Damage Resistance": 1, "Extra Ammo Capacity": 1, "Faster Shield Regen": 1, "Magazine Size": 1, "Reload Speed": 1, "Stowed Reloading": 1},
                "HowToFind": "Available in Colonia", "HowToGetInvite": "5 Settlements in Colonia visited", 
                "HowToReferral": "10 Digital Designs required"},
        400012: {"Engineer": "Rosa Dayette", "Location": "Kojeara", 
                "Modifies": {"Enhanced Tracking": 1, "Extra Backpack Capacity": 1, "Improved Battery Capacity": 1, "Reduced Tool Battery Consumption": 1, "Greater Range": 1, "Scope": 1, "Stability": 1},
                "HowToFind": "Available in Colonia", "HowToGetInvite": "10 Recipe items sold to Bartenders in Colonia", 
                "HowToReferral": "10 Manufacturing Instructions required"},
        400013: {"Engineer": "Yi Shen", "Location": "Einheriar", 
                "Modifies": {"Night Vision": 1, "Quieter Footsteps": 1, "Audio Masking": 1, "Headshot Damage": 1},
                "HowToFind": "Introduced by Colonia engineers", "HowToGetInvite": "All Colonia engineers' referral tasks completed", 
                "HowToReferral": "N/A"}
    }
    
    # Extract search parameters - can be combined
    search_name = obj.get('name', '').lower().strip() if obj else ''
    search_system = obj.get('system', '').lower().strip() if obj else ''
    search_modifications = obj.get('modifications', '').lower().strip() if obj else ''
    search_progress = obj.get('progress', '').strip() if obj else ''
    
    engineer_progress = projected_states.get('EngineerProgress')

    if not engineer_progress:
        return "No engineer progress found"

    engineers = engineer_progress.get('Engineers', [])

    # Create a lookup for engineers from game data
    game_engineers = {}
    for engineer in engineers:
        game_engineers[engineer.get('EngineerID')] = engineer

    # Helper function for Levenshtein distance
    def levenshtein_distance(s1, s2):
        if len(s1) < len(s2):
            return levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    # Helper function for fuzzy matching modifications using Levenshtein distance
    def matches_modifications(modifies_dict, search_term):
        search_terms = search_term.split()
        modifies_words = []
        
        # Extract all words from modification names
        for mod_name in modifies_dict.keys():
            mod_lower = mod_name.lower()
            # First check for exact substring matches
            for term in search_terms:
                if term in mod_lower:
                    return True
            # Add words for fuzzy matching
            mod_words = mod_lower.replace(',', ' ').replace('(', ' ').replace(')', ' ').split()
            modifies_words.extend(mod_words)
        
        # Fuzzy matching using Levenshtein distance
        for search_word in search_terms:
            for modifies_word in modifies_words:
                # Allow some fuzzy matching based on word length
                max_distance = max(1, len(search_word) // 3)  # Allow 1 error per 3 characters
                if levenshtein_distance(search_word, modifies_word) <= max_distance:
                    return True
        
        return False
    
    # Helper function to check if engineer matches search criteria
    def matches_search_criteria(engineer_info, engineer_name, engineer_progress):
        # Check name match
        if search_name and search_name not in engineer_name.lower():
            return False
        
        # Check system/location match
        if search_system:
            location = engineer_info.get('Location', '').lower()
            # Remove permit required text for matching
            location_clean = location.replace(' (permit required)', '')
            if search_system not in location_clean:
                return False
        
        # Check modifications match
        if search_modifications:
            modifies = engineer_info.get('Modifies', '')
            if not matches_modifications(modifies, search_modifications):
                return False
        
        # Check progress match
        if search_progress and search_progress != engineer_progress:
            return False
        
        return True
    
    # Build the comprehensive engineer overview
    engineer_overview = {
        'ship_engineers': {},
        'suit_engineers': {}
    }
    
    # Process ALL ship engineers
    for engineer_id, engineer_info in ship_engineers.items():
        engineer_name = engineer_info['Engineer']
        
        engineer_data = engineer_info.copy()
        game_data = game_engineers.get(engineer_id)
        
        if game_data:
            # Engineer is known in game
            progress = game_data.get('Progress')
            rank = game_data.get('Rank')
            rank_progress = game_data.get('RankProgress', 0)
            
            engineer_data['Progress'] = progress
            
            if progress == 'Unlocked':
                engineer_data['Rank'] = rank
                if rank_progress > 0:
                    engineer_data['RankProgress'] = f"{rank_progress}% towards rank {rank + 1}"
                else:
                    engineer_data['RankProgress'] = "Max rank achieved" if rank >= 5 else "No progress towards next rank"
                
                # Keep HowToGainRep if not max rank
                if rank < 5:
                    engineer_data['HowToGainRep'] = engineer_info['HowToGainRep']
                    
            elif progress == 'Invited':
                engineer_data['NextStep'] = f"To unlock: {engineer_info['HowToUnlock']}"
            elif progress == 'Known':
                engineer_data['NextStep'] = f"To get invite: {engineer_info['HowToGetInvite']}"
        else:
            # Engineer is unknown - show how to find them
            progress = 'Unknown'
            engineer_data['Progress'] = progress
            engineer_data['NextStep'] = f"To discover: {engineer_info['HowToFind']}"
        
        # Check if engineer matches search criteria
        if not matches_search_criteria(engineer_info, engineer_name, progress):
            continue
        
        # Clean up fields not needed in final output (except HowToGainRep for unlocked engineers with rank < 5)
        fields_to_remove = ['HowToGetInvite', 'HowToUnlock', 'HowToFind']
        if game_data and game_data.get('Progress') == 'Unlocked' and game_data.get('Rank', 0) < 5:
            # Keep HowToGainRep for unlocked engineers not at max rank
            fields_to_remove.append('HowToGainRep')  # Remove from list since we want to keep it
            fields_to_remove = ['HowToGetInvite', 'HowToUnlock', 'HowToFind']
        else:
            fields_to_remove.append('HowToGainRep')
            
        for field in fields_to_remove:
            engineer_data.pop(field, None)
        
        engineer_overview['ship_engineers'][engineer_name] = engineer_data
    
    # Process ALL suit engineers
    for engineer_id, engineer_info in suit_engineers.items():
        engineer_name = engineer_info['Engineer']
        
        engineer_data = engineer_info.copy()
        game_data = game_engineers.get(engineer_id)
        
        if game_data:
            # Engineer is known in game
            progress = game_data.get('Progress')
            engineer_data['Progress'] = progress
            
            if progress == 'Unlocked':
                engineer_data['Status'] = 'Available for modifications'
                if engineer_info.get('HowToReferral') != 'N/A':
                    engineer_data['ReferralTask'] = engineer_info['HowToReferral']
            elif progress == 'Invited':
                engineer_data['NextStep'] = f"To unlock: Visit {engineer_info['Location']}"
            elif progress == 'Known':
                engineer_data['NextStep'] = f"To get invite: {engineer_info['HowToGetInvite']}"
        else:
            # Engineer is unknown - show how to find them
            progress = 'Unknown'
            engineer_data['Progress'] = progress
            engineer_data['NextStep'] = f"To discover: {engineer_info['HowToFind']}"
        
        # Check if engineer matches search criteria
        if not matches_search_criteria(engineer_info, engineer_name, progress):
            continue
        
        # Clean up fields not needed in final output for suit engineers
        fields_to_remove = ['HowToGetInvite', 'HowToFind', 'HowToReferral']
        for field in fields_to_remove:
            engineer_data.pop(field, None)
        
        # Convert modifications from dict to list for suit engineers (no ranks)
        if 'Modifies' in engineer_data:
            engineer_data['Modifies'] = list(engineer_data['Modifies'].keys())
        
        engineer_overview['suit_engineers'][engineer_name] = engineer_data
    
    # Check if any engineers were found
    total_engineers = len(engineer_overview['ship_engineers']) + len(engineer_overview['suit_engineers'])
    if total_engineers == 0:
        search_terms = []
        if search_name:
            search_terms.append(f"name: '{search_name}'")
        if search_system:
            search_terms.append(f"system: '{search_system}'")
        if search_modifications:
            search_terms.append(f"modifications: '{search_modifications}'")
        if search_progress:
            search_terms.append(f"progress: '{search_progress}'")
        
        if search_terms:
            # If searching by modifications failed, show available options
            if search_modifications:
                # Collect all unique modification values
                all_modifications = set()
                for engineer_info in ship_engineers.values():
                    mods = engineer_info.get('Modifies', {})
                    # Add all modification names from dict keys
                    for mod_name in mods.keys():
                        all_modifications.add(mod_name)
                
                for engineer_info in suit_engineers.values():
                    mods = engineer_info.get('Modifies', {})
                    # Add all modification names from dict keys
                    for mod_name in mods.keys():
                        all_modifications.add(mod_name)
                
                sorted_mods = sorted(list(all_modifications))
                return f"No engineers found matching modifications: '{search_modifications}'\n\nValid modification types:\n" + yaml.dump(sorted_mods)
            
            return f"No engineers found matching search criteria: {', '.join(search_terms)}"
        else:
            return "No engineers found"
    
    # Convert to YAML format
    yaml_output = yaml.dump(engineer_overview, default_flow_style=False, sort_keys=False)
    # log('debug', 'engineers', yaml_output)
    
    # Add search info to the output if filters were applied
    search_info = []
    if search_name:
        search_info.append(f"name: '{search_name}'")
    if search_system:
        search_info.append(f"system: '{search_system}'")
    if search_modifications:
        search_info.append(f"modifications: '{search_modifications}'")
    if search_progress:
        search_info.append(f"progress: '{search_progress}'")
    
    if search_info:
        return f"Engineer Progress Overview (filtered by {', '.join(search_info)}):\n\n```yaml\n{yaml_output}```"
    else:
        return f"Engineer Progress Overview:\n\n```yaml\n{yaml_output}```"


def material_finder(obj, projected_states):
    """
    Find materials for both ship and suit engineering.
    
    Supports 6 material types:
    - Ship materials: Raw, Manufactured, Encoded (from Materials projection)
    - Suit materials: Items, Components, Data (from ShipLocker projection)
    
    Suit materials don't have grades, only counts.
    """
    import yaml
    
    # Ship engineering materials (from Materials projection)
    ship_raw_materials_map = {
        1: { 1: ['carbon'], 2: ['vanadium'], 3: ['niobium'], 4: ['yttrium'] },
        2: { 1: ['phosphorus'], 2: ['chromium'], 3: ['molybdenum'], 4: ['technetium'] },
        3: { 1: ['sulphur'], 2: ['manganese'], 3: ['cadmium'], 4: ['ruthenium'] },
        4: { 1: ['iron'], 2: ['zinc'], 3: ['tin'], 4: ['selenium'] },
        5: { 1: ['nickel'], 2: ['germanium'], 3: ['tungsten'], 4: ['tellurium'] },
        6: { 1: ['rhenium'], 2: ['arsenic'], 3: ['mercury'], 4: ['polonium'] },
        7: { 1: ['lead'], 2: ['zirconium'], 3: ['boron'], 4: ['antimony'] }
    }

    ship_manufactured_materials_map = {
        'Chemical': {
            1: ['chemicalstorageunits'], 2: ['chemicalprocessors'], 3: ['chemicaldistillery'],
            4: ['chemicalmanipulators'], 5: ['pharmaceuticalisolators']
        },
        'Thermic': {
            1: ['temperedalloys'], 2: ['heatresistantceramics'], 3: ['precipitatedalloys'],
            4: ['thermicalloys'], 5: ['militarygradealloys']
        },
        'Heat': {
            1: ['heatconductionwiring'], 2: ['heatdispersionplate'], 3: ['heatexchangers'],
            4: ['heatvanes'], 5: ['protoheatradiators']
        },
        'Conductive': {
            1: ['basicconductors'], 2: ['conductivecomponents'], 3: ['conductiveceramics'],
            4: ['conductivepolymers'], 5: ['biotechconductors']
        },
        'Mechanical Components': {
            1: ['mechanicalscrap'], 2: ['mechanicalequipment'], 3: ['mechanicalcomponents'],
            4: ['configurablecomponents'], 5: ['improvisedcomponents']
        },
        'Capacitors': {
            1: ['gridresistors'], 2: ['hybridcapacitors'], 3: ['electrochemicalarrays'],
            4: ['polymercapacitors'], 5: ['militarysupercapacitors']
        },
        'Shielding': {
            1: ['wornshieldemitters'], 2: ['shieldemitters'], 3: ['shieldingsensors'],
            4: ['compoundshielding'], 5: ['imperialshielding']
        },
        'Composite': {
            1: ['compactcomposites'], 2: ['filamentcomposites'], 3: ['highdensitycomposites'],
            4: ['proprietarycomposites'], 5: ['coredynamicscomposites']
        },
        'Crystals': {
            1: ['crystalshards'], 2: ['flawedfocuscrystals'], 3: ['focuscrystals'],
            4: ['refinedfocuscrystals'], 5: ['exquisitefocuscrystals']
        },
        'Alloys': {
            1: ['salvagedalloys'], 2: ['galvanisingalloys'], 3: ['phasealloys'],
            4: ['protolightalloys'], 5: ['protoradiolicalloys']
        },
        'Guardian Technology': {
            1: ['guardian_sentinel_wreckagecomponents', 'guardianwreckagecomponents'],
            2: ['guardian_powercell', 'guardianpowercell'],
            3: ['guardian_powerconduit', 'guardianpowerconduit'],
            4: ['guardian_sentinel_weaponparts', 'guardiansentinelweaponparts'],
            5: ['guardian_techcomponent', 'techcomponent']
        },
        'Thargoid Technology': {
            1: ['tg_wreckagecomponents', 'wreckagecomponents', 'tg_abrasion02', 'tgabrasion02'],
            2: ['tg_biomechanicalconduits', 'biomechanicalconduits', 'tg_abrasion03', 'tgabrasion03'],
            3: ['tg_weaponparts', 'weaponparts', 'unknowncarapace', 'tg_causticshard', 'tgcausticshard'],
            4: ['tg_propulsionelement', 'propulsionelement', 'unknownenergycell', 'unknowncorechip'],
            5: ['tg_causticgeneratorparts', 'causticgeneratorparts', 'tg_causticcrystal', 'tgcausticcrystal', 'unknowntechnologycomponents']
        }
    }

    ship_encoded_materials_map = {
        'Emission Data': {
            1: ['scrambledemissiondata'], 2: ['archivedemissiondata'], 3: ['emissiondata'],
            4: ['decodedemissiondata'], 5: ['compactemissionsdata']
        },
        'Wake Scans': {
            1: ['disruptedwakeechoes'], 2: ['fsdtelemetry'], 3: ['wakesolutions'],
            4: ['hyperspacetrajectories'], 5: ['dataminedwake']
        },
        'Shield Data': {
            1: ['shieldcyclerecordings'], 2: ['shieldsoakanalysis'], 3: ['shielddensityreports'],
            4: ['shieldpatternanalysis'], 5: ['shieldfrequencydata']
        },
        'Encryption Files': {
            1: ['encryptedfiles'], 2: ['encryptioncodes'], 3: ['symmetrickeys'],
            4: ['encryptionarchives'], 5: ['adaptiveencryptors']
        },
        'Data Archives': {
            1: ['bulkscandata'], 2: ['scanarchives'], 3: ['scandatabanks'],
            4: ['encodedscandata'], 5: ['classifiedscandata']
        },
        'Encoded Firmware': {
            1: ['legacyfirmware'], 2: ['consumerfirmware'], 3: ['industrialfirmware'],
            4: ['securityfirmware'], 5: ['embeddedfirmware']
        },
        'Guardian Data': {
            1: ['ancientbiologicaldata'],
            2: ['ancientculturaldata'],
            3: ['ancienthistoricaldata'],
            4: ['ancienttechnologicaldata'],
            5: ['guardian_vesselblueprint']
        },
        'Thargoid Data': {
            1: ['tg_interdictiondata'],
            2: ['tg_shipflightdata'],
            3: ['tg_shipsystemsdata'],
            4: ['tg_shutdowndata'],
            5: ['unknownshipsignature']
        }
    }

    # Suit engineering materials (from ShipLocker projection) - no grades
    suit_items_materials = [
        'weaponschematic', 'chemicalprocesssample', 'insightdatabank', 'personaldocuments',
        'chemicalsample', 'biochemicalagent', 'geneticsample', 'gmeds', 'healthmonitor',
        'inertiacanister', 'insight', 'ionisedgas', 'personalcomputer', 'syntheticgenome',
        'geneticrepairmeds', 'buildingschematic', 'compactlibrary', 'deepmantlesample',
        'hush', 'infinity', 'insightentertainmentsuite', 'lazarus', 'microbialinhibitor',
        'nutritionalconcentrate', 'push', 'shipschematic', 'surveillanceequipment',
        'universaltranslator', 'vehicleschematic', 'pyrolyticcatalyst', 'inorganiccontaminant',
        'agriculturalprocesssample', 'refinementprocesssample', 'compressionliquefiedgas',
        'degradedpowerregulator', 'largecapacitypowerregulator', 'powermiscindust',
        'powermisccomputer', 'powerequipment'
    ]

    suit_components_materials = [
        'aerogel', 'chemicalcatalyst', 'chemicalsuperbase', 'circuitboard', 'circuitswitch',
        'electricalfuse', 'electricalwiring', 'encryptedmemorychip', 'epoxyadhesive',
        'memorychip', 'metalcoil', 'microhydraulics', 'microsupercapacitor', 'microthrusters',
        'microtransformer', 'motor', 'opticalfibre', 'opticallens', 'scrambler',
        'titaniumplating', 'transmitter', 'tungstencarbide', 'viscoelasticpolymer', 'rdx',
        'electromagnet', 'oxygenicbacteria', 'epinephrine', 'phneutraliser', 'microelectrode',
        'ionbattery', 'weaponcomponent'
    ]

    suit_data_materials = [
        'internalcorrespondence', 'biometricdata', 'nocdata', 'axcombatlogs', 'airqualityreports',
        'audiologs', 'ballisticsdata', 'biologicalweapondata', 'catmedia', 'chemicalexperimentdata',
        'chemicalformulae', 'chemicalinventory', 'chemicalpatents', 'cocktailrecipes',
        'combatantperformance', 'conflicthistory', 'digitaldesigns', 'dutyrota', 'espionagematerial',
        'evacuationprotocols', 'explorationjournals', 'extractionyielddata', 'factionassociates',
        'financialprojections', 'factionnews', 'geneticresearch', 'influenceprojections',
        'kompromat', 'maintenancelogs', 'manufacturinginstructions', 'medicalrecords',
        'medicaltrialrecords', 'meetingminutes', 'mininganalytics', 'networkaccesshistory',
        'operationalmanual', 'opinionpolls', 'patrolroutes', 'politicalaffiliations',
        'productionreports', 'productionschedule', 'propaganda', 'radioactivitydata',
        'reactoroutputreview', 'recyclinglogs', 'securityexpenses', 'seedgeneaology',
        'settlementassaultplans', 'settlementdefenceplans', 'shareholderinformation',
        'smearcampaignplans', 'spectralanalysisdata', 'stellaractivitylogs', 'surveilleancelogs',
        'tacticalplans', 'taxrecords', 'topographicalsurveys', 'vaccineresearch',
        'visitorregister', 'weaponinventory', 'weapontestdata', 'xenodefenceprotocols',
        'geologicaldata', 'factiondonatorlist', 'pharmaceuticalpatents', 'powerresearchdata',
        'powerpropagandadata', 'poweremployeedata', 'powerclassifieddata', 'powerpreparationspyware'
    ]

    suit_consumables_materials = [
        'healthpack', 'energycell', 'amm_grenade_emp', 'amm_grenade_frag', 
        'amm_grenade_shield', 'bypass'
    ]

    # Display names from game data
    display_names = {
        # Ship materials - Raw
        'carbon': 'Carbon', 'vanadium': 'Vanadium', 'niobium': 'Niobium', 'yttrium': 'Yttrium',
        'phosphorus': 'Phosphorus', 'chromium': 'Chromium', 'molybdenum': 'Molybdenum',
        'technetium': 'Technetium', 'sulphur': 'Sulphur', 'manganese': 'Manganese',
        'cadmium': 'Cadmium', 'ruthenium': 'Ruthenium', 'iron': 'Iron', 'zinc': 'Zinc',
        'tin': 'Tin', 'selenium': 'Selenium', 'nickel': 'Nickel', 'germanium': 'Germanium',
        'tungsten': 'Tungsten', 'tellurium': 'Tellurium', 'rhenium': 'Rhenium',
        'arsenic': 'Arsenic', 'mercury': 'Mercury', 'polonium': 'Polonium', 'lead': 'Lead',
        'zirconium': 'Zirconium', 'boron': 'Boron', 'antimony': 'Antimony',
        
        # Ship materials - Manufactured (key examples)
        'chemicalstorageunits': 'Chemical Storage Units', 'temperedalloys': 'Tempered Alloys',
        'heatconductionwiring': 'Heat Conduction Wiring', 'basicconductors': 'Basic Conductors',
        'mechanicalscrap': 'Mechanical Scrap', 'gridresistors': 'Grid Resistors',
        'wornshieldemitters': 'Worn Shield Emitters', 'compactcomposites': 'Compact Composites',
        'crystalshards': 'Crystal Shards', 'salvagedalloys': 'Salvaged Alloys',
        
        # Ship materials - Encoded (key examples)
        'scrambledemissiondata': 'Exceptional Scrambled Emission Data',
        'disruptedwakeechoes': 'Atypical Disrupted Wake Echoes',
        'shieldcyclerecordings': 'Distorted Shield Cycle Recordings',
        'encryptedfiles': 'Unusual Encrypted Files', 'bulkscandata': 'Anomalous Bulk Scan Data',
        'legacyfirmware': 'Specialised Legacy Firmware',
        
        # Suit materials - Items
        'weaponschematic': 'Weapon Schematic', 'chemicalprocesssample': 'Chemical Process Sample',
        'insightdatabank': 'Insight Data Bank', 'personaldocuments': 'Personal Documents',
        'chemicalsample': 'Chemical Sample', 'biochemicalagent': 'Biochemical Agent',
        'geneticsample': 'Biological Sample', 'gmeds': 'G-Meds', 'healthmonitor': 'Health Monitor',
        'inertiacanister': 'Inertia Canister', 'ionisedgas': 'Ionised Gas',
        'personalcomputer': 'Personal Computer', 'syntheticgenome': 'Synthetic Genome',
        'geneticrepairmeds': 'Genetic Repair Meds', 'buildingschematic': 'Building Schematic',
        'compactlibrary': 'Compact Library', 'deepmantlesample': 'Deep Mantle Sample',
        'insightentertainmentsuite': 'Insight Entertainment Suite',
        'microbialinhibitor': 'Microbial Inhibitor', 'nutritionalconcentrate': 'Nutritional Concentrate',
        'shipschematic': 'Ship Schematic', 'surveillanceequipment': 'Surveillance Equipment',
        'universaltranslator': 'Universal Translator', 'vehicleschematic': 'Vehicle Schematic',
        'pyrolyticcatalyst': 'Pyrolytic Catalyst', 'inorganiccontaminant': 'Inorganic Contaminant',
        'agriculturalprocesssample': 'Agricultural Process Sample',
        'refinementprocesssample': 'Refinement Process Sample',
        'compressionliquefiedgas': 'Compression-Liquefied Gas',
        'degradedpowerregulator': 'Degraded Power Regulator',
        'largecapacitypowerregulator': 'Power Regulator', 'powermiscindust': 'Industrial Machinery',
        'powermisccomputer': 'Data Storage Device', 'powerequipment': 'Personal Protective Equipment',
        
        # Suit materials - Components
        'chemicalcatalyst': 'Chemical Catalyst', 'chemicalsuperbase': 'Chemical Superbase',
        'circuitboard': 'Circuit Board', 'circuitswitch': 'Circuit Switch',
        'electricalfuse': 'Electrical Fuse', 'electricalwiring': 'Electrical Wiring',
        'encryptedmemorychip': 'Encrypted Memory Chip', 'epoxyadhesive': 'Epoxy Adhesive',
        'memorychip': 'Memory Chip', 'metalcoil': 'Metal Coil', 'microhydraulics': 'Micro Hydraulics',
        'microsupercapacitor': 'Micro Supercapacitor', 'microthrusters': 'Micro Thrusters',
        'microtransformer': 'Micro Transformer', 'opticalfibre': 'Optical Fibre',
        'opticallens': 'Optical Lens', 'titaniumplating': 'Titanium Plating',
        'tungstencarbide': 'Tungsten Carbide', 'viscoelasticpolymer': 'Viscoelastic Polymer',
        'oxygenicbacteria': 'Oxygenic Bacteria', 'phneutraliser': 'pH Neutraliser',
        'ionbattery': 'Ion Battery', 'weaponcomponent': 'Weapon Component',
        
        # Suit materials - Data
        'internalcorrespondence': 'Internal Correspondence', 'biometricdata': 'Biometric Data',
        'nocdata': 'NOC Data', 'axcombatlogs': 'AX Combat Logs', 'airqualityreports': 'Air Quality Reports',
        'audiologs': 'Audio Logs', 'ballisticsdata': 'Ballistics Data',
        'biologicalweapondata': 'Biological Weapon Data', 'catmedia': 'Cat Media',
        'chemicalexperimentdata': 'Chemical Experiment Data', 'chemicalformulae': 'Chemical Formulae',
        'chemicalinventory': 'Chemical Inventory', 'chemicalpatents': 'Chemical Patents',
        'cocktailrecipes': 'Cocktail Recipes', 'combatantperformance': 'Combatant Performance',
        'conflicthistory': 'Conflict History', 'digitaldesigns': 'Digital Designs',
        'dutyrota': 'Duty Rota', 'espionagematerial': 'Espionage Material',
        'evacuationprotocols': 'Evacuation Protocols', 'explorationjournals': 'Exploration Journals',
        'extractionyielddata': 'Extraction Yield Data', 'factionassociates': 'Faction Associates',
        'financialprojections': 'Financial Projections', 'factionnews': 'Faction News',
        'geneticresearch': 'Genetic Research', 'influenceprojections': 'Influence Projections',
        'maintenancelogs': 'Maintenance Logs', 'manufacturinginstructions': 'Manufacturing Instructions',
        'medicalrecords': 'Medical Records', 'medicaltrialrecords': 'Clinical Trial Records',
        'meetingminutes': 'Meeting Minutes', 'mininganalytics': 'Mining Analytics',
        'networkaccesshistory': 'Network Access History', 'operationalmanual': 'Operational Manual',
        'opinionpolls': 'Opinion Polls', 'patrolroutes': 'Patrol Routes',
        'politicalaffiliations': 'Political Affiliations', 'productionreports': 'Production Reports',
        'productionschedule': 'Production Schedule', 'radioactivitydata': 'Radioactivity Data',
        'reactoroutputreview': 'Reactor Output Review', 'recyclinglogs': 'Recycling Logs',
        'securityexpenses': 'Security Expenses', 'seedgeneaology': 'Seed Geneaology',
        'settlementassaultplans': 'Settlement Assault Plans',
        'settlementdefenceplans': 'Settlement Defence Plans',
        'shareholderinformation': 'Shareholder Information',
        'smearcampaignplans': 'Smear Campaign Plans', 'spectralanalysisdata': 'Spectral Analysis Data',
        'stellaractivitylogs': 'Stellar Activity Logs', 'surveilleancelogs': 'Surveillance Logs',
        'tacticalplans': 'Tactical Plans', 'taxrecords': 'Tax Records',
        'topographicalsurveys': 'Topographical Surveys', 'vaccineresearch': 'Vaccine Research',
        'visitorregister': 'Visitor Register', 'weaponinventory': 'Weapon Inventory',
        'weapontestdata': 'Weapon Test Data', 'xenodefenceprotocols': 'Xeno-Defence Protocols',
        'geologicaldata': 'Geological Data', 'factiondonatorlist': 'Faction Donator List',
        'pharmaceuticalpatents': 'Pharmaceutical Patents', 'powerresearchdata': 'Power Research Data',
        'powerpropagandadata': 'Power Political Data', 'poweremployeedata': 'Power Association Data',
        'powerclassifieddata': 'Power Classified Data', 'powerpreparationspyware': 'Power Injection Malware',
        
        # Suit materials - Consumables
        'healthpack': 'Medkit', 'energycell': 'Energy Cell', 'amm_grenade_emp': 'Shield Disruptor',
        'amm_grenade_frag': 'Frag Grenade', 'amm_grenade_shield': 'Shield Projector', 'bypass': 'E-Breach'
    }

    # Extract search parameters
    search_names = []
    if obj and obj.get('name'):
        name_param = obj.get('name')
        if isinstance(name_param, list):
            search_names = [name.lower().strip() for name in name_param if name]
        else:
            search_names = [name_param.lower().strip()] if name_param else []
    
    search_grade = obj.get('grade', 0) if obj else 0
    search_type = obj.get('type', '').lower().strip() if obj else ''

    # Get data from projected states
    materials_data = projected_states.get('Materials', {})
    shiploader_data = projected_states.get('ShipLocker', {})

    # Helper function for Levenshtein distance
    def levenshtein_distance(s1, s2):
        if len(s1) < len(s2):
            return levenshtein_distance(s2, s1)
        if len(s2) == 0:
            return len(s1)
        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        return previous_row[-1]

    # Helper function to find ship material info
    def find_ship_material_info(material_name):
        material_name_lower = material_name.lower()
        
        # Check raw materials
        for category, grades in ship_raw_materials_map.items():
            for grade, materials in grades.items():
                if material_name_lower in materials:
                    return {'category': 'Ship', 'type': 'Raw', 'grade': grade, 'section': f'Category {category}'}
        
        # Check manufactured materials
        for section, grades in ship_manufactured_materials_map.items():
            for grade, materials in grades.items():
                if material_name_lower in materials:
                    return {'category': 'Ship', 'type': 'Manufactured', 'grade': grade, 'section': section}
        
        # Check encoded materials
        for section, grades in ship_encoded_materials_map.items():
            for grade, materials in grades.items():
                if material_name_lower in materials:
                    return {'category': 'Ship', 'type': 'Encoded', 'grade': grade, 'section': section}
        
        return None

    # Helper function to find suit material info
    def find_suit_material_info(material_name):
        material_name_lower = material_name.lower()
        
        if material_name_lower in suit_items_materials:
            return {'category': 'Suit', 'type': 'Items', 'grade': None, 'section': 'Items'}
        elif material_name_lower in suit_components_materials:
            return {'category': 'Suit', 'type': 'Components', 'grade': None, 'section': 'Components'}
        elif material_name_lower in suit_data_materials:
            return {'category': 'Suit', 'type': 'Data', 'grade': None, 'section': 'Data'}
        elif material_name_lower in suit_consumables_materials:
            return {'category': 'Suit', 'type': 'Consumables', 'grade': None, 'section': 'Consumables'}
        
        return None

    # Helper function to get higher grade materials from the same family
    def get_higher_grade_materials(material_info, current_material):
        higher_grade_materials = []
        
        if material_info['category'] != 'Ship' or material_info['grade'] is None:
            return higher_grade_materials  # Only ship materials have grades
        
        if material_info['type'] == 'Raw':
            materials_map = ship_raw_materials_map
            max_grade = 4  # Raw materials go up to grade 4
            # For raw materials, find the category that contains this material
            material_category = None
            for category, grades in materials_map.items():
                for grade, materials in grades.items():
                    if current_material in materials:
                        material_category = category
                        break
                if material_category:
                    break
                    
            if material_category and material_category in materials_map:
                for grade in range(material_info['grade'] + 1, max_grade + 1):
                    if grade in materials_map[material_category]:
                        for mat_name in materials_map[material_category][grade]:
                            # Check if player has this material
                            player_materials = materials_data.get('Raw', [])
                            for player_mat in player_materials:
                                if player_mat.get('Name', '').lower() == mat_name:
                                    display_name = display_names.get(mat_name, mat_name.title())
                                    higher_grade_materials.append({
                                        'name': display_name,
                                        'count': player_mat.get('Count', 0),
                                        'grade': grade
                                    })
        
        elif material_info['type'] in ['Manufactured', 'Encoded']:
            materials_map = ship_manufactured_materials_map if material_info['type'] == 'Manufactured' else ship_encoded_materials_map
            max_grade = 5  # Manufactured and Encoded materials go up to grade 5
            
            # Find the section that contains this material
            material_section = material_info['section']
            if material_section in materials_map:
                for grade in range(material_info['grade'] + 1, max_grade + 1):
                    if grade in materials_map[material_section]:
                        for mat_name in materials_map[material_section][grade]:
                            # Check if player has this material
                            player_materials = materials_data.get(material_info['type'], [])
                            for player_mat in player_materials:
                                if player_mat.get('Name', '').lower() == mat_name:
                                    display_name = display_names.get(mat_name, mat_name.title())
                                    higher_grade_materials.append({
                                        'name': display_name,
                                        'count': player_mat.get('Count', 0),
                                        'grade': grade
                                    })
        
        return higher_grade_materials

    # Helper function to check if material matches search criteria
    def matches_criteria(material_name, material_info, count):
        # Check name match using fuzzy search
        if search_names:
            display_name = display_names.get(material_name, material_name)
            name_match = False
            for search_name in search_names:
                if levenshtein_distance(search_name, material_name) <= 3 or levenshtein_distance(search_name, display_name.lower()) <= 3:
                    name_match = True
                    break
            if not name_match:
                return False
        
        # Check grade match (only for ship materials)
        if search_grade > 0 and material_info['grade'] is not None:
            if material_info['grade'] != search_grade:
                return False
        
        # Check type match
        if search_type:
            type_matches = {
                'raw': 'Raw', 'manufactured': 'Manufactured', 'encoded': 'Encoded',
                'items': 'Items', 'components': 'Components', 'data': 'Data', 'consumables': 'Consumables',
                'ship': 'Ship', 'suit': 'Suit'
            }
            expected_type = type_matches.get(search_type)
            if expected_type in ['Raw', 'Manufactured', 'Encoded', 'Items', 'Components', 'Data', 'Consumables']:
                if material_info['type'] != expected_type:
                    return False
            elif expected_type in ['Ship', 'Suit']:
                if material_info['category'] != expected_type:
                    return False
        
        return True

    # Build results
    results = []
    
    # Process ship materials from Materials projection
    if materials_data:
        for material_type in ['Raw', 'Manufactured', 'Encoded']:
            type_materials = materials_data.get(material_type, [])
            
            for material in type_materials:
                material_name = material.get('Name', '').lower()
                count = material.get('Count', 0)
                
                if count == 0:
                    continue
                
                material_info = find_ship_material_info(material_name)
                if not material_info:
                    continue
                
                if not matches_criteria(material_name, material_info, count):
                    continue
                
                display_name = display_names.get(material_name, material_name.title())
                
                # Get higher grade materials for trading info
                higher_grade_materials = get_higher_grade_materials(material_info, material_name)
                
                result = {
                    'name': display_name,
                    'count': count,
                    'category': material_info['category'],
                    'type': material_info['type'],
                    'grade': material_info['grade'],
                    'section': material_info['section']
                }
                
                if higher_grade_materials:
                    result['tradeable_higher_grades'] = higher_grade_materials
                
                results.append(result)

    # Process suit materials from ShipLocker projection
    if shiploader_data:
        # Process Items
        for item in shiploader_data.get('Items', []):
            material_name = item.get('Name', '').lower()
            count = item.get('Count', 0)
            
            if count == 0:
                continue
            
            material_info = find_suit_material_info(material_name)
            if not material_info:
                continue
            
            if not matches_criteria(material_name, material_info, count):
                continue
            
            display_name = display_names.get(material_name, item.get('Name_Localised', material_name.title()))
            
            result = {
                'name': display_name,
                'count': count,
                'category': material_info['category'],
                'type': material_info['type'],
                'section': material_info['section']
            }
            
            results.append(result)
        
        # Process Components
        for component in shiploader_data.get('Components', []):
            material_name = component.get('Name', '').lower()
            count = component.get('Count', 0)
            
            if count == 0:
                continue
            
            material_info = find_suit_material_info(material_name)
            if not material_info:
                continue
            
            if not matches_criteria(material_name, material_info, count):
                continue
            
            display_name = display_names.get(material_name, component.get('Name_Localised', material_name.title()))
            
            result = {
                'name': display_name,
                'count': count,
                'category': material_info['category'],
                'type': material_info['type'],
                'section': material_info['section']
            }
            
            results.append(result)
        
        # Process Data
        for data_item in shiploader_data.get('Data', []):
            material_name = data_item.get('Name', '').lower()
            count = data_item.get('Count', 0)
            
            if count == 0:
                continue
            
            material_info = find_suit_material_info(material_name)
            if not material_info:
                continue
            
            if not matches_criteria(material_name, material_info, count):
                continue
            
            display_name = display_names.get(material_name, data_item.get('Name_Localised', material_name.title()))
            
            result = {
                'name': display_name,
                'count': count,
                'category': material_info['category'],
                'type': material_info['type'],
                'section': material_info['section']
            }
            
            results.append(result)
        
        # Process Consumables
        for consumable in shiploader_data.get('Consumables', []):
            material_name = consumable.get('Name', '').lower()
            count = consumable.get('Count', 0)
            
            if count == 0:
                continue
            
            material_info = find_suit_material_info(material_name)
            if not material_info:
                continue
            
            if not matches_criteria(material_name, material_info, count):
                continue
            
            display_name = display_names.get(material_name, consumable.get('Name_Localised', material_name.title()))
            
            result = {
                'name': display_name,
                'count': count,
                'category': material_info['category'],
                'type': material_info['type'],
                'section': material_info['section']
            }
            
            results.append(result)

    # Check if any materials were found
    if not results:
        search_terms = []
        if search_names:
            name_list = ', '.join([f"'{name}'" for name in search_names])
            search_terms.append(f"name(s): {name_list}")
        if search_grade > 0:
            search_terms.append(f"grade: {search_grade}")
        if search_type:
            search_terms.append(f"type: '{search_type}'")
        
        if search_terms:
            return f"No materials found matching search criteria: {', '.join(search_terms)}"
        else:
            return "No materials found"

    # Format results
    formatted_results = []
    for result in results:
        if result['category'] == 'Ship':
            material_line = f"{result['count']}x {result['name']} ({result['category']} {result['type']}, Grade {result['grade']})"
        else:  # Suit materials
            material_line = f"{result['count']}x {result['name']} ({result['category']} {result['type']})"
        
        if result.get('tradeable_higher_grades'):
            trading_lines = ["Tradeable, higher grades:"]
            for higher_mat in result['tradeable_higher_grades']:
                if higher_mat['count'] > 0:
                    trading_lines.append(f"- {higher_mat['count']}x {higher_mat['name']} (Grade {higher_mat['grade']})")
            
            if len(trading_lines) > 1:  # Only add if there are actual tradeable materials
                formatted_results.append(material_line)
                formatted_results.extend(trading_lines)
            else:
                formatted_results.append(material_line)
        else:
            formatted_results.append(material_line)
    
    # Sort results while preserving trading info structure
    def sort_key(item):
        if isinstance(item, str) and 'x ' in item and '(' in item:
            if 'Ship Raw' in item:
                type_order = 0
            elif 'Ship Manufactured' in item:
                type_order = 1
            elif 'Ship Encoded' in item:
                type_order = 2
            elif 'Suit Items' in item:
                type_order = 3
            elif 'Suit Components' in item:
                type_order = 4
            elif 'Suit Data' in item:
                type_order = 5
            elif 'Suit Consumables' in item:
                type_order = 6
            else:
                type_order = 7
            
            # Extract grade for ship materials
            import re
            grade_match = re.search(r'Grade (\d)', item)
            grade = int(grade_match.group(1)) if grade_match else 0
            
            # Extract name for sorting
            name_match = re.search(r'\d+x ([^(]+)', item)
            name = name_match.group(1).strip() if name_match else ''
            
            return (type_order, grade, name)
        else:
            return (999, 999, item)  # Put non-material lines at end
    
    # Sort while preserving trading info structure
    material_blocks = []
    current_block = []
    
    for line in formatted_results:
        if isinstance(line, str) and 'x ' in line and '(' in line:
            if current_block:
                material_blocks.append(current_block)
            current_block = [line]
        else:
            current_block.append(line)
    
    if current_block:
        material_blocks.append(current_block)
    
    # Sort blocks by their main material line
    material_blocks.sort(key=lambda block: sort_key(block[0]))
    
    # Flatten back to single list
    sorted_results = []
    for block in material_blocks:
        sorted_results.extend(block)
    
    # Add search info to the output if filters were applied
    search_info = []
    if search_names:
        if len(search_names) == 1:
            search_info.append(f"name: '{search_names[0]}'")
        else:
            name_list = ', '.join([f"'{name}'" for name in search_names])
            search_info.append(f"names: {name_list}")
    if search_grade > 0:
        search_info.append(f"grade: {search_grade}")
    if search_type:
        search_info.append(f"type: '{search_type}'")
    
    yaml_output = yaml.dump(sorted_results, default_flow_style=False, sort_keys=False)
    
    if search_info:
        return f"Materials Inventory (filtered by {', '.join(search_info)}):\n\n```yaml\n{yaml_output}```"
    else:
        return f"Materials Inventory:\n\n```yaml\n{yaml_output}```"

def send_message(obj, projected_states):
    from pyautogui import typewrite
    setGameWindowActive()

    return_message = "No message sent"

    if obj:
        chunk_size = 100
        start = 0


        in_ship = projected_states.get('CurrentStatus').get('flags').get('InMainShip') or projected_states.get('CurrentStatus').get('flags').get('InFighter')
        in_buggy = projected_states.get('CurrentStatus').get('flags').get('InSRV')
        on_foot = projected_states.get('CurrentStatus').get('flags2').get('OnFoot')

        while start < len(obj.get("message", "")):
            return_message = "Message sent"
            if start != 0:
                sleep(0.25)
            chunk = obj.get("message", "")[start:start + chunk_size]
            start += chunk_size

            if in_ship:
                keys.send("QuickCommsPanel")
            elif in_buggy:
                keys.send("QuickCommsPanel_Buggy")
            elif on_foot:
                keys.send("QuickCommsPanel_Humanoid")
            else:
                raise Exception("Can not send message.")

            if not obj.get("channel") or obj.get("channel").lower() == "local":
                typewrite("/l ", interval=0.02)
                return_message += " to local chat"
            elif obj.get("channel").lower() == "wing":
                typewrite("/w ", interval=0.02)
                return_message += " to wing chat"
            elif obj.get("channel").lower() == "system":
                typewrite("/sy ", interval=0.02)
                keys.send('UI_Down',repeat=2)
                keys.send('UI_Select')
                return_message += " to squadron chat"
            elif obj.get("channel").lower() == "squadron":
                typewrite("/s ", interval=0.02)
                return_message += " to squadron chat"
            elif obj.get("channel").lower() == "commander":
                typewrite(f"/d {obj.get('recipient')} ", interval=0.02)
                return_message += f" to {obj.get('recipient')}"
            else:
                log('debug', f'invalid channel {obj.get("channel")}')

            sleep(0.05)
            typewrite(chunk, interval=0.02)

            sleep(0.05)
            # send enter key
            keys.send_key('Down', 'Key_Enter')
            sleep(0.05)
            keys.send_key('Up', 'Key_Enter')

    return return_message + '.'


def get_visuals(obj, projected_states):
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
    # Helper function for Levenshtein distance
    def levenshtein_distance(s1, s2):
        if len(s1) < len(s2):
            return levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    search_lower = search_query.lower()
    suggestions = []
    
    # First try substring matching (existing behavior)
    split_string = search_query.split()
    for word in split_string:
        for element in valid_list:
            if word.lower() in element.lower() and element not in suggestions:
                suggestions.append(element)
    
    # If we don't have enough suggestions, add fuzzy matches
    if len(suggestions) < 5:
        scored_matches = []
        max_distance = max(2, len(search_query) // 3)  # Allow more errors for suggestions
        
        for element in valid_list:
            if element not in suggestions:  # Don't duplicate existing suggestions
                distance = levenshtein_distance(search_lower, element.lower())
                if distance <= max_distance:
                    scored_matches.append((distance, element))
        
        # Sort by distance and add the best fuzzy matches
        scored_matches.sort(key=lambda x: x[0])
        for distance, element in scored_matches[:5 - len(suggestions)]:
            suggestions.append(element)

    message = ""
    if suggestions:
        guesses_str = ', '.join(suggestions[:5])  # Limit to 5 suggestions
        message = (
            f"Restart search with valid inputs, here are suggestions: {guesses_str}"
        )

    return message


# Prepare a request for the spansh station finder
def prepare_station_request(obj, projected_states):
    # Helper function for Levenshtein distance
    def levenshtein_distance(s1, s2):
        if len(s1) < len(s2):
            return levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    # Helper function for fuzzy matching
    def find_best_match(search_term, known_list):
        search_lower = search_term.lower()
        
        # First try exact match
        for item in known_list:
            if item.lower() == search_lower:
                return item
        
        # Then try fuzzy matching
        best_match = None
        best_distance = float('inf')
        max_distance = max(1, len(search_term) // 3)  # Allow 1 error per 3 characters
        
        for item in known_list:
            distance = levenshtein_distance(search_lower, item.lower())
            if distance <= max_distance and distance < best_distance:
                best_distance = distance
                best_match = item
        
        return best_match
    
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
        "Haematite",
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
        "Steel",
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
        "Corsair",
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
        "Colonisation Services",
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
        "Refinery Contact",
        "Refuel",
        "Repair",
        "Restock",
        "Search and Rescue",
        "Shipyard",
        "Shop",
        "Social Space",
        "System Colonisation"
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
    requires_large_pad = projected_states.get('ShipInfo').get('LandingPadSize') == 'L'
    if requires_large_pad:
        filters["has_large_pad"] = {"value": True}
    if "material_trader" in obj and obj["material_trader"]:
        filters["material_trader"] = {"value": obj["material_trader"]}
    if "technology_broker" in obj and obj["technology_broker"]:
        filters["technology_broker"] = {"value": obj["technology_broker"]}
    if "commodities" in obj and obj["commodities"]:
        market_filters = []
        for market_item in obj["commodities"]:
            # Find matching commodity name using fuzzy matching
            matching_commodity = find_best_match(market_item["name"], known_commodities)
            if not matching_commodity:
                raise Exception(
                    f"Invalid commodity name: {market_item['name']}. {educated_guesses_message(market_item['name'], known_commodities)}")
            market_item["name"] = matching_commodity
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
            # Find matching module name using exact matching only
            module_name_lower = module["name"].lower()
            matching_module = next((m for m in known_modules if m.lower() == module_name_lower), None)
            if not matching_module:
                raise Exception(
                    f"Invalid module name: {module['name']}. {educated_guesses_message(module['name'], known_modules)}")
            module["name"] = matching_module
        filters["modules"] = obj["modules"]
    if "ships" in obj:
        for ship in obj["ships"]:
            # Find matching ship name using fuzzy matching
            matching_ship = find_best_match(ship["name"], known_ships)
            if not matching_ship:
                raise Exception(
                    f"Invalid ship name: {ship['name']}. {educated_guesses_message(ship['name'], known_ships)}")
            ship["name"] = matching_ship
        filters["ships"] = {"value": obj["ships"]}
    if "services" in obj:
        for service in obj["services"]:
            # Find matching service name using fuzzy matching
            matching_service = find_best_match(service["name"], known_services)
            if not matching_service:
                raise Exception(
                    f"Invalid service name: {service['name']}. {educated_guesses_message(service['name'], known_services)}")
            service["name"] = matching_service
        filters["services"] = {"value": obj["services"]}
    if "name" in obj and obj["name"]:
        filters["name"] = {
            "value": obj["name"]
        }

    sort_object = { "distance": { "direction": "asc" } }
    if filters.get("market") and len(filters["market"]) > 0:
        if filters.get("market")[0].get("demand"):
            sort_object = {"market_sell_price":[{"name":filters["market"][0]["name"],"direction":"desc"}]}
        elif filters["market"][0].get("demand"):
            sort_object = {"market_buy_price":[{"name":filters["market"][0]["name"],"direction":"asc"}]}

    # Build the request body
    request_body = {
        "filters": filters,
        "sort": [
            sort_object
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


def station_finder(obj,projected_states):
    # Initialize the filters
    request_body = prepare_station_request(obj, projected_states)
    log('debug', 'station search input', request_body)

    url = "https://spansh.co.uk/api/stations/search"
    try:
        response = requests.post(url, json=request_body, timeout=15)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx and 5xx)

        data = response.json()

        filtered_data = filter_station_response(request_body, data)
        # tech broker, material trader
        if obj.get("technology_broker") or obj.get("material_trader"):
            if len(filtered_data["results"]) > 0:
                return galaxy_map_open({
                    "system_name":filtered_data["results"][0]["system"],
                    "start_navigation":True,
                    "details": filtered_data["results"][0]
                }, projected_states)
            else:
                return 'No stations were found, so no route was plotted.'

        return f'Here is a list of stations: {json.dumps(filtered_data)}'
    except Exception as e:
        log('error', e, traceback.format_exc())
        return 'An error has occurred. The station finder seems currently not available.'


def prepare_system_request(obj, projected_states):
    # Helper function for Levenshtein distance
    def levenshtein_distance(s1, s2):
        if len(s1) < len(s2):
            return levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    # Helper function for fuzzy matching
    def find_best_match(search_term, known_list):
        search_lower = search_term.lower()
        
        # First try exact match
        for item in known_list:
            if item.lower() == search_lower:
                return item
        
        # Then try fuzzy matching
        best_match = None
        best_distance = float('inf')
        max_distance = max(1, len(search_term) // 3)  # Allow 1 error per 3 characters
        
        for item in known_list:
            distance = levenshtein_distance(search_lower, item.lower())
            if distance <= max_distance and distance < best_distance:
                best_distance = distance
                best_match = item
        
        return best_match
    
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
        validated_allegiances = []
        for allegiance in obj["allegiance"]:
            # Find matching allegiance using fuzzy matching
            matching_allegiance = find_best_match(allegiance, known_allegiances)
            if not matching_allegiance:
                raise Exception(
                    f"Invalid allegiance: {allegiance}. {educated_guesses_message(allegiance, known_allegiances)}")
            validated_allegiances.append(matching_allegiance)
        filters["allegiance"] = {"value": validated_allegiances}

    if "state" in obj and obj["state"]:
        validated_states = []
        for state in obj["state"]:
            # Find matching state using fuzzy matching
            matching_state = find_best_match(state, known_states)
            if not matching_state:
                raise Exception(
                    f"Invalid state: {state}. {educated_guesses_message(state, known_states)}")
            validated_states.append(matching_state)
        filters["state"] = {"value": validated_states}

    if "government" in obj and obj["government"]:
        validated_governments = []
        for government in obj["government"]:
            # Find matching government using fuzzy matching
            matching_government = find_best_match(government, known_governments)
            if not matching_government:
                raise Exception(
                    f"Invalid government: {government}. {educated_guesses_message(government, known_governments)}")
            validated_governments.append(matching_government)
        filters["government"] = {"value": validated_governments}

    if "power" in obj and obj["power"]:
        validated_powers = []
        for power in obj["power"]:
            # Find matching power using fuzzy matching
            matching_power = find_best_match(power, known_powers)
            if not matching_power:
                raise Exception(
                    f"Invalid power: {power}. {educated_guesses_message(power, known_powers)}")
            validated_powers.append(matching_power)
        filters["controlling_power"] = {"value": validated_powers}

    if "primary_economy" in obj and obj["primary_economy"]:
        validated_economies = []
        for economy in obj["primary_economy"]:
            # Find matching economy using fuzzy matching
            matching_economy = find_best_match(economy, known_economies)
            if not matching_economy:
                raise Exception(
                    f"Invalid primary economy: {economy}. {educated_guesses_message(economy, known_economies)}")
            validated_economies.append(matching_economy)
        filters["primary_economy"] = {"value": validated_economies}

    if "security" in obj and obj["security"]:
        validated_security = []
        for security_level in obj["security"]:
            # Find matching security level using fuzzy matching
            matching_security = find_best_match(security_level, known_security_levels)
            if not matching_security:
                raise Exception(
                    f"Invalid security level: {security_level}. {educated_guesses_message(security_level, known_security_levels)}")
            validated_security.append(matching_security)
        filters["security"] = {"value": validated_security}

    if "thargoid_war_state" in obj and obj["thargoid_war_state"]:
        validated_thargoid_states = []
        for thargoid_war_state in obj["thargoid_war_state"]:
            # Find matching thargoid war state using fuzzy matching
            matching_state = find_best_match(thargoid_war_state, known_thargoid_war_states)
            if not matching_state:
                raise Exception(
                    f"Invalid thargoid war state: {thargoid_war_state}. {educated_guesses_message(thargoid_war_state, known_thargoid_war_states)}")
            validated_thargoid_states.append(matching_state)
        filters["thargoid_war_state"] = {"value": validated_thargoid_states}

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
def system_finder(obj, projected_states):
    # Build the request body
    request_body = prepare_system_request(obj,projected_states)

    url = "https://spansh.co.uk/api/systems/search"

    try:
        response = requests.post(url, json=request_body, timeout=15)
        response.raise_for_status()

        data = response.json()
        # Filter the response
        filtered_data = filter_system_response(request_body, data)

        return f'Here is a list of systems: {json.dumps(filtered_data)}'

    except Exception as e:
        log('error', e, traceback.format_exc())
        return 'An error occurred. The system finder seems to be currently unavailable.'


def prepare_body_request(obj, projected_states):
    # Helper function for Levenshtein distance
    def levenshtein_distance(s1, s2):
        if len(s1) < len(s2):
            return levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    # Helper function for fuzzy matching
    def find_best_match(search_term, known_list):
        search_lower = search_term.lower()
        
        # First try exact match
        for item in known_list:
            if item.lower() == search_lower:
                return item
        
        # Then try fuzzy matching
        best_match = None
        best_distance = float('inf')
        max_distance = max(1, len(search_term) // 3)  # Allow 1 error per 3 characters
        
        for item in known_list:
            distance = levenshtein_distance(search_lower, item.lower())
            if distance <= max_distance and distance < best_distance:
                best_distance = distance
                best_match = item
        
        return best_match
    
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
        validated_subtypes = []
        for subtype in obj["subtype"]:
            # Find matching subtype using fuzzy matching
            matching_subtype = find_best_match(subtype, known_subtypes)
            if not matching_subtype:
                raise Exception(
                    f"Invalid celestial body subtype: {subtype}. {educated_guesses_message(subtype, known_subtypes)}")
            validated_subtypes.append(matching_subtype)
        filters["subtype"] = {"value": validated_subtypes}

    if "landmark_subtype" in obj and obj["landmark_subtype"]:
        for landmark_subtype in obj["landmark_subtype"]:
            # Find matching landmark subtype using fuzzy matching
            matching_landmark = find_best_match(landmark_subtype, known_landmarks)
            if not matching_landmark:
                raise Exception(
                    f"Invalid Landmark Subtype: {landmark_subtype}. {educated_guesses_message(landmark_subtype, known_landmarks)}")
        filters["landmarks"] = [{"subtype": matching_landmark}]

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
        filtered_body["system_name"] = body.get("system_name")
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


# Body finder function that sends the request to the Spansh API
def body_finder(obj,projected_states):
    # Build the request body
    request_body = prepare_body_request(obj,projected_states)

    url = "https://spansh.co.uk/api/bodies/search"

    try:
        response = requests.post(url, json=request_body, timeout=15)
        response.raise_for_status()

        data = response.json()
        # Filter the response
        filtered_data = filter_body_response(request_body, data)

        return f'Here is a list of celestial bodies: {json.dumps(filtered_data)}'

    except Exception as e:
        log('error', f"Error: {e}")
        return 'An error occurred. The system finder seems to be currently unavailable.'

def target_subsystem_thread(current_subsystem: str, current_event_id: str, desired_subsystem: str):
    if not current_subsystem:
        keys.send('CycleNextSubsystem')
        log('debug', 'CycleNextSubsystem key sent first time')
        new_state = event_manager.wait_for_condition('Target', lambda s: s.get('Subsystem'))
        current_subsystem = new_state.get('Subsystem')
        current_event_id = new_state.get('EventID')
    subsystem_loop = False
    while current_subsystem != desired_subsystem:
        keys.send('CycleNextSubsystem')
        log('debug', 'CycleNextSubsystem key sent')
        new_state = event_manager.wait_for_condition('Target', lambda s: s.get('EventID') != current_event_id)
        if 'Subsystem' not in new_state:
            log('info', 'target lost, abort cycle')
            return
        if new_state.get('Subsystem') == 'Power Plant':
            if subsystem_loop:
                break
            subsystem_loop = True

        log('debug', 'new subsystem targeted', new_state.get('Subsystem'))
        current_subsystem = new_state.get('Subsystem')
        current_event_id = new_state.get('EventID')
    log('debug', 'desired subsystem targeted', current_subsystem)

def target_subsystem(args, projected_states):
    current_target = projected_states.get('Target')

    if not current_target.get('Ship', False):
        raise Exception('No ship is currently targeted')
    if not current_target.get('Scanned', False):
        raise Exception('Targeted ship isn\'t scanned yet')

    if 'subsystem' not in args:
        raise Exception('Something went wrong!')

    threading.Thread(target=target_subsystem_thread, args=(current_target.get('Subsystem'), current_target.get('EventID'), args['subsystem'],), daemon=True).start()

    return f"The submodule {args['subsystem']} is being targeted."

def register_actions(actionManager: ActionManager, eventManager: EventManager, llmClient: openai.OpenAI,
                     llmModelName: str, visionClient: Optional[openai.OpenAI], visionModelName: Optional[str],
                     edKeys: EDKeys):
    global event_manager, vision_client, llm_client, llm_model_name, vision_model_name, keys
    keys = edKeys
    event_manager = eventManager
    llm_client = llmClient
    llm_model_name = llmModelName
    vision_client = visionClient
    vision_model_name = visionModelName

    setGameWindowActive()

    # Register actions - General Ship Actions
    actionManager.registerAction('fireWeapons', "Fire weapons with simple controls: single shot, start continuous, or stop", {
        "type": "object",
        "properties": {
          "weaponType": {
            "type": "string",
            "description": "Type of weapons to fire",
            "enum": [
              "primary",
              "secondary",
              "discovery_scanner"
            ],
            "default": "primary"
          },
          "action": {
            "type": "string",
            "description": "Action to perform with weapons",
            "enum": [
              "fire",
              "start",
              "stop"
            ],
            "default": "fire"
          },
          "duration": {
            "type": "number",
            "description": "Duration to hold fire button in seconds (for fire action only)",
            "minimum": 0,
            "maximum": 30
          },
          "repetitions": {
            "type": "integer",
            "description": "Number of additional repetitions (0 = single action, 1+ = repeat that many extra times)",
            "minimum": 0,
            "maximum": 10,
            "default": 0
          }
        },
        "required": ["weaponType", "action"]
    }, fire_weapons, 'ship')

    actionManager.registerAction('setSpeed', "Change flight thrust", {
        "type": "object",
        "properties": {
            "speed": {
                "type": "string",
                "description": "New speed value",
                "enum": [
                    "Minus100",
                    "Minus75",
                    "Minus50",
                    "Minus25",
                    "Zero",
                    "25",
                    "50",
                    "75",
                    "100"
                ]
            }
        },
        "required": ["speed"]
    }, set_speed, 'ship')

    actionManager.registerAction('deployHeatSink', "Deploy heat sink", {
        "type": "object",
        "properties": {}
    }, deploy_heat_sink, 'ship')

    actionManager.registerAction('deployHardpointToggle', "Deploy or retract hardpoints. Do not call this action when asked to switch hud mode", {
        "type": "object",
        "properties": {}
    }, deploy_hardpoint_toggle, 'ship')

    actionManager.registerAction('managePowerDistribution',
     "Manage power distribution between ship systems. Apply pips to one or more power systems or balance the power across two or if unspecified, across all 3",
     {
         "type": "object",
         "properties": {
             "power_category": {
                 "type": "array",
                 "description": "Array of the system(s) being asked to change. if not specified return default",
                 "items": {
                     "type": "string",
                     "enum": ["Engines", "Weapons", "Systems"],
                     "default":["Engines", "Weapons", "Systems"]
                 }
             },
             "balance_power": {
                 "type": "boolean",
                 "description": "Whether the user asks to balance power"
             },
             "pips": {
                 "type": "array",
                 "description": "Number of pips to allocate (ignored for balance), one per power_category",
                 "items": {
                     "type": "integer",
                     "minimum": 1,
                     "maximum": 4,
                     "default": 1
                 }
             }
         },
         "required": ["power_category"]
     }, manage_power_distribution, 'ship')

    actionManager.registerAction('galaxyMapOpen', "Open galaxy map. If asked, also focus on a system or start a navigation route", {
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

    actionManager.registerAction('systemMapOpenOrClose', "Open or close system map", {
        "type": "object",
        "properties": {
            "desired_state": {
                "type": "string",
                "enum": ["open", "close"],
                "description": "Desired state for the system map: open or close.",
            },
        },
    }, system_map_open_or_close, 'ship')

    actionManager.registerAction('cycleTarget', "Cycle to next target", {
        "type": "object",
        "properties": {
            "direction": {
                "type": "string",
                "description": "Direction to cycle (next or previous)",
                "enum": ["next", "previous"],
                "default": "next"
            }
        }
    }, cycle_target, 'ship')


    actionManager.registerAction(
        'cycle_fire_group',
        "call this tool if the user asks to cycle, select or switch to specific firegroup, the the next firegroup or to the previous firegroup",
        {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "description": "If next or previous is give: Cycle direction: 'next' or 'previous'.",
                    "enum": ["next", "previous"]
                },
                "fire_group": {
                    "type": "integer",
                    "description": "Specific firegroup index to select. Letters A=0, B=1, C=2, etc.",
                    "default": None
                }
            },
        },
        cycle_fire_group,
        'mainship'
    )

    actionManager.registerAction('Change_ship_HUD_mode', "Switch to combat or analysis mode", {
        "type": "object",
        "properties": {
            "hud mode": {
                "type": "string",
                "description": "mode to switch to",
                "enum": ["combat", "analysis", "toggle"],
            }
        },
        "required": ["hud mode"],
    }, change_hud_mode, 'mainship')

    actionManager.registerAction('cycleFireGroup', "Cycle to next fire group", {
        "type": "object",
        "properties": {
            "direction": {
                "type": "string",
                "description": "Direction to cycle (next or previous)",
                "enum": ["next", "previous"],
            }
        }
    }, cycle_fire_group, 'ship')

    


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

    actionManager.registerAction('targetSubmodule', "Target a subsystem on locked ship", {
        "type": "object",
        "properties": {
            "subsystem": {
                "type": "string",
                "description": "subsystem/module to target",
                "enum": [
                    "Drive",
                    "Shield Generator",
                    "Power Distributor",
                    "Life Support",
                    "FSD",
                    "Point Defence Turret"
                    "Power Plant"
                ],
            },
        },
        "required": ["subsystem"],
    }, target_subsystem, 'ship')

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
                        "DefensiveBehaviour",
                        "AggressiveBehaviour",
                        "FocusTarget",
                        "HoldFire",
                        "HoldPosition",
                        "Follow",
                        "RequestDock",
                    ]
                }
            }
        }
    }, npc_order, 'ship')

    # Register actions - Mainship Actions
    actionManager.registerAction('FsdJump',
        "initiate FSD jump (jump to the next system or enter supercruise)", {
        "type": "object",
        "properties": {
            "jump_type": {
                "type": "string",
                "description": "Jump to next system, enter supercruise or auto if unspecified",
                "enum": ["next_system", "supercruise", "auto"]
            }
        }
    }, fsd_jump, 'mainship')

    actionManager.registerAction('target_next_system_in_route',
        "When we have a nav route set, this will automatically target the next system in the route",
        {
        "type": "object",
        "properties": {}
    }, next_system_in_route, 'mainship')

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
    actionManager.registerAction('fighterRequestDock', "Request docking for Ship Launched Fighter", {
        "type": "object",
        "properties": {}
    }, fighter_request_dock, 'fighter')

    # Register actions - SRV Actions (Horizons)
    actionManager.registerAction('toggleDriveAssist', "Toggle drive assist", {
        "type": "object",
        "properties": {}
    }, toggle_drive_assist, 'buggy')

    actionManager.registerAction('fireWeaponsBuggy', "Fire buggy weapons with simple controls: single shot, start continuous, or stop", {
        "type": "object",
        "properties": {
            "weaponType": {
                "type": "string",
                "description": "Type of weapons to fire",
                "enum": [
                    "primary",
                    "secondary"
                ],
                "default": "primary"
            },
            "action": {
                "type": "string",
                "description": "Action to perform with weapons",
                "enum": [
                    "fire",
                    "start",
                    "stop"
                ],
                "default": "fire"
            },
            "duration": {
                "type": "number",
                "description": "Duration to hold fire button in seconds (for fire action only)",
                "minimum": 0,
                "maximum": 30
            },
            "repetitions": {
                "type": "integer",
                "description": "Number of additional repetitions (0 = single action, 1+ = repeat that many extra times)",
                "minimum": 0,
                "maximum": 10,
                "default": 0
            }
        },
        "required": [
            "weaponType",
            "action"
        ]
    }, fire_weapons_buggy, 'buggy')

    actionManager.registerAction('autoBreak', "Toggle auto-brake", {
        "type": "object",
        "properties": {}
    }, auto_break_buggy, 'buggy')

    actionManager.registerAction('headlights', "Control SRV headlights - toggle or set to specific mode (off/low/high)", {
        "type": "object",
        "properties": {
            "desired_state": {
                "type": "string",
                "enum": ["off", "low", "high", "toggle"],
                "description": "Desired headlight mode. 'toggle' cycles to next mode, or specify exact mode (off/low/high)",
                "default": "toggle"
            }
        }
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


    actionManager.registerAction('managePowerDistributionBuggy',
     "Manage power distribution between buggy power systems. Apply pips to one or more power systems or balance the power across two or if unspecified, across all 3",
     {
         "type": "object",
         "properties": {
             "power_category": {
                 "type": "array",
                 "description": "Array of the system(s) being asked to change. if not specified return default",
                 "items": {
                     "type": "string",
                     "enum": ["Engines", "Weapons", "Systems"],
                     "default": ["Engines", "Weapons", "Systems"]
                 }
             },
             "balance_power": {
                 "type": "boolean",
                 "description": "Whether the user asks to balance power"
             },
             "pips": {
                 "type": "array",
                 "description": "Number of pips to allocate (ignored for balance), one per power_category",
                 "items": {
                     "type": "integer",
                     "minimum": 1,
                     "maximum": 4,
                     "default": 1
                 }
             }
         },
         "required": ["power_category"]
     }, manage_power_distribution_buggy, 'buggy')


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

    actionManager.registerAction('galaxyMapOpenOrCloseBuggy', "Open galaxy map. If asked, also focus on a system or start a navigation route", {
        "type": "object",
        "properties": {
            "desired_state": {
                "type": "string",
                "enum": ["open", "close"],
                "description": "Open or close galaxy map",
            },
            "system_name": {
                "type": "string",
                "description": "System to display or plot to.",
            },
            "start_navigation": {
                "type": "boolean",
                "description": "Start navigation route to the system",
            }
        },
    }, galaxy_map_open_buggy, 'buggy')

    actionManager.registerAction('systemMapOpenOrCloseBuggy', "Open/close system map.", {
        "type": "object",
        "properties": {
            "desired_state": {
                "type": "string",
                "enum": ["open", "close"],
                "description": "Desired state for the system map: open or close.",
            },
        },
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

    actionManager.registerAction('galaxyMapOpenOrCloseHumanoid', "Open or Close Galaxy Map", {
        "type": "object",
        "properties": {}
    }, galaxy_map_open_humanoid, 'humanoid')

    actionManager.registerAction('systemMapOpenOrCloseHumanoid', "Open or Close System Map", {
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
        'web'
    )

    # if ARC:
    # Register AI action for system finder
    actionManager.registerAction(
        'system_finder',
        "Find a star system based on allegiance, government, state, power, primary economy, and more. Ask for unknown values and ensure they are filled out.",
        input_template=lambda i, s: f"""Searching for systems
            {'called ' + i.get('name', '') if i.get('name', '') else ''}
            {'with allegiance to ' + ' and '.join(i.get('allegiance', [])) if i.get('allegiance', []) else ''}
            {'in state ' + ' and '.join(i.get('state', [])) if i.get('state', []) else ''}
            {'with government type ' + ' and '.join(i.get('government', [])) if i.get('government', []) else ''}
            {'controlled by ' + ' and '.join(i.get('power', [])) if i.get('power', []) else ''}
            {'with primary economy type ' + ' and '.join(i.get('primary_economy', [])) if i.get('primary_economy', []) else ''}
            {'with security level ' + ' and '.join(i.get('security', [])) if i.get('security', []) else ''}
            {'in Thargoid war state ' + ' and '.join(i.get('thargoid_war_state', [])) if i.get('thargoid_war_state', []) else ''}
            {'with a population over ' + i.get('population', {}).get('comparison', '') + ' ' + str(i.get('population', {}).get('value', '')) if i.get('population', {}) else ''}
            near {i.get('reference_system', 'Sol')}.
        """,
        parameters={
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
        method=system_finder,
        action_type='web'
    )
    actionManager.registerAction(
        'station_finder',
        "Find a station for commodities, modules and ships. Ask for unknown values and make sure they are known.",
        input_template=lambda i, s: f"""Searching for stations
            {'called ' + i.get('name', '') if i.get('name', '') else ''}
            {'with large pad' if i.get('has_large_pad', False) else ''}
            {'with material traders for ' + ' and '.join(i.get('material_trader', [])) + ' Materials' if i.get('material_trader', []) else ''}
            {'with technology brokers for ' + ' and '.join(i.get('technology_broker', [])) + ' Technology' if i.get('technology_broker', []) else ''}
            {'selling a ' + ' and a '.join([f"{module['name']} module class {module.get('class', 'any')} {module.get('class', '')} " for module in i.get('modules', [])]) if i.get('modules', []) else ''}
            {'selling a ' + ' and a '.join([f"{ship['name']}" for ship in i.get('ships', [])]) if i.get('ships', []) else ''}
            {' and '.join([f"where we can {market.get('transaction')} {market.get('amount', 'some')} {market.get('name')}" for market in i.get('commodities', [])])}
            {'with a ' + ' and '.join([service['name'] for service in i.get('services', [])]) if i.get('services', []) else ''}
            near {i.get('reference_system', 'Sol')}
            {'within ' + str(i.get('distance', 50000)) + ' light years' if i.get('distance', 50000) else ''}.
        """,
        parameters={
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
                "distance": {
                    "type": "number",
                    "description": "The maximum distance to search",
                    "default": 50000.0
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
                "commodities": {
                    "type": "array",
                    "description": "Commodities to buy or sell at a station. This is not the station name and must map to a commodity name",
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
                "reference_system"
            ]
        },
        method=station_finder,
        action_type='web'
    )
    actionManager.registerAction(
        'body_finder',
        "Find a planet or star of a certain type or with a landmark. Ask for unknown values and make sure they are known.",
        input_template=lambda i, s: f"""Searching for bodies 
            {'called ' + i.get('name', '') if i.get('name', '') else ''}
            {'of subtype ' + ', '.join(i.get('subtype', [])) if i.get('subtype', []) else ''}
            {'with a landmark of subtype ' + ', '.join(i.get('landmark_subtype', [])) if i.get('landmark_subtype', []) else ''}
            near {i.get('reference_system', 'Sol')}
            {'within ' + str(i.get('distance', 50000)) + ' light years.' if i.get('distance', 50000) else ''}.
        """,
        parameters={
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
                "reference_system"
            ]
        },
        method=body_finder,
        action_type='web'
    )

    actionManager.registerAction('textMessage', "Send message to commander or local", {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Message to send"
            },
            "channel": {
                "type": "string",
                "description": "Channel to send the message on.",
                "example": "commander",
                "enum": ['local', 'system', 'wing', 'squadron', 'commander']
            },
            "recipient": {
                "type": "string",
                "description": "Commander name to send message to. Only used if channel is commander.",
                "example": "RatherRude.TTV",
            },
        },
        "required": ["message","channel"]
    }, send_message, 'global')

    actionManager.registerAction('engineer_finder', "Get information about engineers' location, standing and modifications.",
        {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Filter engineers by name"
                },
                "system": {
                    "type": "string", 
                    "description": "Filter engineers by system/location"
                },
                "modifications": {
                    "type": "string",
                    "description": "Filter engineers by what they modify"
                },
                "progress": {
                    "type": "string",
                    "enum": ["Unknown", "Known", "Invited", "Unlocked"],
                    "description": "Filter engineers by their current progress status"
                }
            }
        },
        engineer_finder,
        'web'
    )

    actionManager.registerAction('material_finder', "Find and search materials for both ship and suit engineering from commander's inventory.",
        {
            "type": "object",
            "properties": {
                "name": {
                    "oneOf": [
                        {"type": "string", "description": "Single material name to search for"},
                        {"type": "array", "items": {"type": "string"}, "description": "Multiple material names to search for"}
                    ],
                    "description": "Filter materials by name(s) - supports fuzzy search. Can be a single string or array of strings."
                },
                "grade": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "description": "Filter ship materials by grade (1-5). Suit materials don't have grades."
                },
                "type": {
                    "type": "string",
                    "enum": ["raw", "manufactured", "encoded", "items", "components", "data", "consumables", "ship", "suit"],
                    "description": "Filter by material type. Ship types: raw, manufactured, encoded. Suit types: items, components, data, consumables. Category filters: ship, suit."
                }
            }
        },
        material_finder,
        'web'
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


def format_commodity_name(name: str) -> str:
    """
    Format a commodity name according to Elite Dangerous conventions.
    Handles special cases like:
    - Hyphenated words (e.g., "Agri-Medicines")
    - Acronyms (e.g., "CMM Composite")
    - Multiple words (e.g., "Advanced Catalysers")
    """
    # Handle empty or single word cases
    if not name or ' ' not in name:
        return name.capitalize()

    # Split by spaces and process each part
    parts = name.split()
    formatted_parts = []

    for part in parts:
        # Handle acronyms (2-4 uppercase letters)
        if len(part) <= 4 and part.isalpha() and part.isupper():
            formatted_parts.append(part)
            continue

        # Handle hyphenated words
        if '-' in part:
            hyphen_parts = part.split('-')
            formatted_hyphen_parts = [p.capitalize() for p in hyphen_parts]
            formatted_parts.append('-'.join(formatted_hyphen_parts))
            continue

        # Handle regular words
        formatted_parts.append(part.capitalize())

    return ' '.join(formatted_parts)

def normalize_string(s: str) -> str:
    """
    Normalize a string for comparison by converting to lowercase.
    """
    return s.lower()


if __name__ == "__main__":
    req = prepare_station_request({'reference_system': 'Coelho', 'market': [{'name': 'Gold', 'amount': 8, 'transaction': 'Buy'}]})
    print(json.dumps(req))
