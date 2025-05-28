import json
import platform
import threading
from time import sleep
import traceback
from typing import Optional
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
    checkStatus(projected_states, {'Docked':True,'Landed':True,'HudInAnalysisMode':True})
    setGameWindowActive()

    # Parse arguments with defaults
    weapon_type = args.get('weaponType', 'primary').lower()
    action = args.get('action', 'fire').lower()
    duration = args.get('duration', None)  # Duration to hold fire button
    repetitions = args.get('repetitions', 0)  # 0 = one action, 1+ = repeat

    # Determine key mapping
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

    direction = args.get('direction', 'next').lower()

    if direction == 'previous':
        keys.send('CycleFireGroupPrevious')
        return "Cycled to previous fire group"
    else:
        # Default to 'next' for any invalid direction
        keys.send('CycleFireGroupNext')
        return "Cycled to next fire group"

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


def galaxy_map_open(args, projected_states, galaxymap_key="GalaxyMapOpen"):
    # Trigger the GUI open
    setGameWindowActive()
    current_gui = projected_states.get('CurrentStatus', {}).get('GuiFocus', '')

    if current_gui in ['SAA', 'FSS', 'Codex']:
        raise Exception('Galaxy map can not be opened currently, the active GUI needs to be closed first')

    if current_gui == 'GalaxyMap':
        if not 'system_name' in args:
            return "Galaxy map is already open"
    else:
        keys.send(galaxymap_key)

    try:
        event_manager.wait_for_condition('CurrentStatus', lambda s: s.get('GuiFocus') == "GalaxyMap", 4)
        gm_open = True
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

        keys.send('CamZoomOut')
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
        sleep(.5)

        if 'start_navigation' in args and args['start_navigation']:
            keys.send('CamZoomOut')
            sleep(0.15)
            keys.send('UI_Select', hold=0.75)

            sleep(0.05)
            if not current_gui == "GalaxyMap":  # if we are already in the galaxy map we don't want to close it
                keys.send(galaxymap_key)

            return ((f"Best location found: {json.dumps(args['details'])}. " if 'details' in args else '') +
                    f"Plotting a route to {args['system_name']} has been attempted. Check event history to see if it was successful, if you see no event it has failed.")

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
        return "a target next system in route as no navigation route is currently set set"

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

def galaxy_map_open_buggy(args, projected_states):
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
def prepare_station_request(obj, projected_states):
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
            # Find matching commodity name while preserving original capitalization
            market_item_name_lower = market_item["name"].lower()
            matching_commodity = next((commodity for commodity in known_commodities if commodity.lower() == market_item_name_lower), None)
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
            # Find matching module name while preserving original capitalization
            module_name_lower = module["name"].lower()
            matching_module = next((m for m in known_modules if m.lower() == module_name_lower), None)
            if not matching_module:
                raise Exception(
                    f"Invalid module name: {module['name']}. {educated_guesses_message(module['name'], known_modules)}")
            module["name"] = matching_module
        filters["modules"] = obj["modules"]
    if "ships" in obj:
        for ship in obj["ships"]:
            # Find matching ship name while preserving original capitalization
            ship_name_lower = ship["name"].lower()
            matching_ship = next((s for s in known_ships if s.lower() == ship_name_lower), None)
            if not matching_ship:
                raise Exception(
                    f"Invalid ship name: {ship['name']}. {educated_guesses_message(ship['name'], known_ships)}")
            ship["name"] = matching_ship
        filters["ships"] = {"value": obj["ships"]}
    if "services" in obj:
        for service in obj["services"]:
            # Find matching service name while preserving original capitalization
            service_name_lower = service["name"].lower()
            matching_service = next((s for s in known_services if s.lower() == service_name_lower), None)
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
        response = requests.post(url, json=request_body)
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
            # Find matching allegiance while preserving original capitalization
            allegiance_lower = allegiance.lower()
            matching_allegiance = next((a for a in known_allegiances if a.lower() == allegiance_lower), None)
            if not matching_allegiance:
                raise Exception(
                    f"Invalid allegiance: {allegiance}. {educated_guesses_message(allegiance, known_allegiances)}")
        filters["allegiance"] = {"value": [a for a in obj["allegiance"] if next((k for k in known_allegiances if k.lower() == a.lower()), None)]}

    if "state" in obj and obj["state"]:
        for state in obj["state"]:
            # Find matching state while preserving original capitalization
            state_lower = state.lower()
            matching_state = next((s for s in known_states if s.lower() == state_lower), None)
            if not matching_state:
                raise Exception(
                    f"Invalid state: {state}. {educated_guesses_message(state, known_states)}")
        filters["state"] = {"value": [s for s in obj["state"] if next((k for k in known_states if k.lower() == s.lower()), None)]}

    if "government" in obj and obj["government"]:
        for government in obj["government"]:
            # Find matching government while preserving original capitalization
            government_lower = government.lower()
            matching_government = next((g for g in known_governments if g.lower() == government_lower), None)
            if not matching_government:
                raise Exception(
                    f"Invalid government: {government}. {educated_guesses_message(government, known_governments)}")
        filters["government"] = {"value": [g for g in obj["government"] if next((k for k in known_governments if k.lower() == g.lower()), None)]}

    if "power" in obj and obj["power"]:
        for power in obj["power"]:
            # Find matching power while preserving original capitalization
            power_lower = power.lower()
            matching_power = next((p for p in known_powers if p.lower() == power_lower), None)
            if not matching_power:
                raise Exception(
                    f"Invalid power: {power}. {educated_guesses_message(power, known_powers)}")
        filters["controlling_power"] = {"value": [p for p in obj["power"] if next((k for k in known_powers if k.lower() == p.lower()), None)]}

    if "primary_economy" in obj and obj["primary_economy"]:
        for economy in obj["primary_economy"]:
            # Find matching economy while preserving original capitalization
            economy_lower = economy.lower()
            matching_economy = next((e for e in known_economies if e.lower() == economy_lower), None)
            if not matching_economy:
                raise Exception(
                    f"Invalid primary economy: {economy}. {educated_guesses_message(economy, known_economies)}")
        filters["primary_economy"] = {"value": [e for e in obj["primary_economy"] if next((k for k in known_economies if k.lower() == e.lower()), None)]}

    if "security" in obj and obj["security"]:
        for security_level in obj["security"]:
            # Find matching security level while preserving original capitalization
            security_lower = security_level.lower()
            matching_security = next((s for s in known_security_levels if s.lower() == security_lower), None)
            if not matching_security:
                raise Exception(
                    f"Invalid security level: {security_level}. {educated_guesses_message(security_level, known_security_levels)}")
        filters["security"] = {"value": [s for s in obj["security"] if next((k for k in known_security_levels if k.lower() == s.lower()), None)]}

    if "thargoid_war_state" in obj and obj["thargoid_war_state"]:
        for thargoid_war_state in obj["thargoid_war_state"]:
            # Find matching thargoid war state while preserving original capitalization
            state_lower = thargoid_war_state.lower()
            matching_state = next((s for s in known_thargoid_war_states if s.lower() == state_lower), None)
            if not matching_state:
                raise Exception(
                    f"Invalid thargoid war state: {thargoid_war_state}. {educated_guesses_message(thargoid_war_state, known_thargoid_war_states)}")
        filters["thargoid_war_state"] = {"value": [s for s in obj["thargoid_war_state"] if next((k for k in known_thargoid_war_states if k.lower() == s.lower()), None)]}

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
        response = requests.post(url, json=request_body)
        response.raise_for_status()

        data = response.json()
        # Filter the response
        filtered_data = filter_system_response(request_body, data)

        return f'Here is a list of systems: {json.dumps(filtered_data)}'

    except Exception as e:
        log('error', e, traceback.format_exc())
        return 'An error occurred. The system finder seems to be currently unavailable.'


def prepare_body_request(obj, projected_states):
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
            # Find matching subtype while preserving original capitalization
            subtype_lower = subtype.lower()
            matching_subtype = next((s for s in known_subtypes if s.lower() == subtype_lower), None)
            if not matching_subtype:
                raise Exception(
                    f"Invalid celestial body subtype: {subtype}. {educated_guesses_message(subtype, known_subtypes)}")
        filters["subtype"] = {"value": [s for s in obj["subtype"] if next((k for k in known_subtypes if k.lower() == s.lower()), None)]}

    if "landmark_subtype" in obj and obj["landmark_subtype"]:
        for landmark_subtype in obj["landmark_subtype"]:
            # Find matching landmark subtype while preserving original capitalization
            landmark_lower = landmark_subtype.lower()
            matching_landmark = next((l for l in known_landmarks if l.lower() == landmark_lower), None)
            if not matching_landmark:
                raise Exception(
                    f"Invalid Landmark Subtype: {landmark_subtype}. {educated_guesses_message(landmark_subtype, known_landmarks)}")
        filters["landmarks"] = [{"subtype": next((k for k in known_landmarks if k.lower() == obj["landmark_subtype"].lower()), None)}]

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


# System finder function that sends the request to the Spansh API
def body_finder(obj,projected_states):
    # Build the request body
    request_body = prepare_body_request(obj,projected_states)

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
                "minimum": 0.1,
                "maximum": 30.0
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
