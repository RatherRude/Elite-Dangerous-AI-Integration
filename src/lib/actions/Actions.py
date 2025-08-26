import json
import platform
import threading
from time import sleep
import math
from typing import Any, Literal
from pyautogui import typewrite

import openai
import requests

from .actions_web import register_web_actions
from .actions_ui import register_ui_actions

from ..Logger import log, show_chat_message
from ..EDKeys import EDKeys
from ..EventManager import EventManager
from ..ActionManager import ActionManager

keys: EDKeys = None
vision_client: openai.OpenAI | None = None
llm_client: openai.OpenAI = None
llm_model_name: str = None
vision_model_name: str | None = None
event_manager: EventManager = None

# Checking status projection to exit game actions early if not applicable
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
    checkStatus(projected_states, {'Docked': True, 'Landed': True})
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
    checkStatus(projected_states, {'Docked': True, 'Landed': True})
    setGameWindowActive()

    if 'speed' in args:
        if args['speed'] in ["Minus100", "Minus75", "Minus50", "Minus25", "Zero", "25", "50", "75", "100"]:
            keys.send(f"SetSpeed{args['speed']}")
        else:
            raise Exception(f"Invalid speed {args['speed']}")

    return f"Speed set to {args['speed']}%."


def deploy_heat_sink(args, projected_states):
    checkStatus(projected_states, {'Docked': True, 'Landed': True})
    setGameWindowActive()
    keys.send('DeployHeatSink')
    return f"Heat sink deployed"


def deploy_hardpoint_toggle(args, projected_states):
    checkStatus(projected_states, {'Docked': True, 'Landed': True})
    setGameWindowActive()
    keys.send('DeployHardpointToggle')
    return f"Hardpoints {'deployed ' if not projected_states.get('CurrentStatus').get('flags').get('HardpointsDeployed') else 'retracted'}"


def manage_power_distribution(args, projected_states):
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


def target_ship(args, projected_states):
    """Unified target selection function that handles cycling and highest threat selection."""
    setGameWindowActive()

    # Get the target selection mode - can be 'next', 'previous', or 'highest_threat'
    mode = args.get('mode', 'next').lower()
    wing = projected_states.get('Wing', {}).get('Members', [])

    if mode == 'highest_threat':
        keys.send('SelectHighestThreat')
        return "Highest threat (if one exists) is now target locked"
    elif mode == 'previous':
        keys.send('CyclePreviousTarget')
        return "Selected previous target"
    elif mode == 'next_hostile':
        keys.send('CycleNextHostileTarget')
        return "Selected next hostile target"
    elif mode == 'previous_hostile':
        keys.send('CyclePreviousHostileTarget')
        return "Selected previous hostile target"
    elif mode == 'wingman_1':
        if len(wing) < 1:
            raise Exception(f'Can\'t select first wingman: Wing has {len(wing)} Members')
        keys.send('TargetWingman0')
        return "Targeting wingman 1"
    elif mode == 'wingman_2':
        if len(wing) < 2:
            raise Exception(f'Can\'t select second wingman: Wing has {len(wing)} Members')
        keys.send('TargetWingman1')
        return "Targeting wingman 2"
    elif mode == 'wingman_3':
        if len(wing) < 3:
            raise Exception(f'Can\'t select third wingman: Wing has {len(wing)} Members')
        keys.send('TargetWingman2')
        return "Targeting wingman 3"
    elif mode == 'wingman_1_target':
        if len(wing) < 1:
            raise Exception(f'Can\'t select first wingman: Wing has {len(wing)} Members')
        keys.send('TargetWingman0')
        keys.send('SelectTargetsTarget')
        return "Targeting wingman 1's target"
    elif mode == 'wingman_2_target':
        if len(wing) < 2:
            raise Exception(f'Can\'t select second wingman: Wing has {len(wing)} Members')
        keys.send('TargetWingman1')
        keys.send('SelectTargetsTarget')
        return "Targeting wingman 2's target"
    elif mode == 'wingman_3_target':
        if len(wing) < 3:
            raise Exception(f'Can\'t select third wingman: Wing has {len(wing)} Members')
        keys.send('TargetWingman2')
        keys.send('SelectTargetsTarget')
        return "Targeting wingman 3's target"
    else:
        # Default to 'next' for any invalid mode
        keys.send('CycleNextTarget')
        return "Selected next target"


def toggle_wing_nav_lock(args, projected_states):
    setGameWindowActive()
    wing = projected_states.get('Wing', {}).get('Members', [])
    if len(wing) < 1:
        raise Exception(f'Can\'t toggle wing nav lock: Not in a team')
    keys.send('WingNavLock')
    return "Wing nav lock toggled"


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
    firegroup_ask = args.get('fire_group', None)

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
    elif firegroup_ask > 7:  # max allowed is up to H which is 7 starting with A=0
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
        # handles case where we cycle back round to zero
        return "Failed to cycle to requested fire group. Please ensure it exists."

    return f"Fire group {chr(65 + new_firegroup)} is now selected."


def ship_spot_light_toggle(args, projected_states):
    setGameWindowActive()
    keys.send('ShipSpotLightToggle')
    return f"Ship spotlight {'activated ' if not projected_states.get('CurrentStatus').get('flags').get('LightsOn') else 'deactivated'}"


def fire_chaff_launcher(args, projected_states):
    checkStatus(projected_states, {'Docked': True, 'Landed': True, 'Supercruise': True})
    setGameWindowActive()
    keys.send('FireChaffLauncher')
    return f"Chaff launcher fired"


def night_vision_toggle(args, projected_states):
    setGameWindowActive()
    keys.send('NightVisionToggle')
    return f"Night vision {'activated ' if not projected_states.get('CurrentStatus').get('flags').get('NightVision') else 'deactivated'}"





def charge_ecm(args, projected_states):
    checkStatus(projected_states, {'Docked': True, 'Landed': True, 'Supercruise': True})
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
        # collisions = keys.get_collisions('UI_Up')
        #
        # if 'CamTranslateForward' in collisions:
        #     raise Exception(
        #         "Unable to enter system name due to a collision between the 'UI Panel Up' and 'Galaxy Cam Translate Forward' keys. "
        #         + "Please change the keybinding for 'Galaxy Cam Translate' to Shift + WASD under General Controls > Galaxy Map.")

        keys.send('CamZoomIn')
        sleep(0.05)

        keys.send('UI_Up')
        sleep(.15)
        if current_gui == "GalaxyMap":
            keys.send('UI_Left', repeat=3)
            sleep(.05)
            keys.send('UI_Right')
            sleep(.05)
            keys.send('UI_Up')
            sleep(.05)
        keys.send('UI_Select')
        sleep(.15)

        # type in the System name
        typewrite(args['system_name'], interval=0.1)
        sleep(0.15)

        # send enter key
        keys.send_key('Down', 'Key_Enter')
        sleep(0.05)
        keys.send_key('Up', 'Key_Enter')

        sleep(0.15)
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


def system_map_open_or_close(args, projected_states, sys_map_key='SystemMapOpen'):
    # Trigger the GUI open
    setGameWindowActive()

    current_gui = projected_states.get('CurrentStatus', {}).get('GuiFocus', '')

    if args['desired_state'] == "close":
        if current_gui == "SystemMap":
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
    checkStatus(projected_states, {'Docked': True, 'Landed': True, 'Supercruise': True})
    setGameWindowActive()
    keys.send('LandingGearToggle')
    return f"Landing gear {'deployed ' if not projected_states.get('CurrentStatus').get('flags').get('LandingGearDown') else 'retracted'}"


def use_shield_cell(args, projected_states):
    setGameWindowActive()
    keys.send('UseShieldCell')
    return f"Shield cell used"


def toggle_cargo_scoop(args, projected_states):
    checkStatus(projected_states, {'Docked': True, 'Landed': True, 'Supercruise': True})
    setGameWindowActive()
    keys.send('ToggleCargoScoop')
    return f"Cargo scoop {'deployed ' if not projected_states.get('CurrentStatus').get('flags').get('CargoScoopDeployed') else 'retracted'}"


def fsd_jump(args, projected_states):
    checkStatus(projected_states, {'Docked': True, 'Landed': True, 'FsdMassLocked': True, 'FsdCooldown': True, 'FsdCharging': True})
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
    keys.send("UI_Select", hold=0.2)
    for _ in range(6):
        if stop_event.is_set():
            break
        keys.send("CyclePreviousPanel")
        keys.send('UI_Left')
        keys.send('UI_Right')
        keys.send("UI_Select", hold=0.2)


def request_docking(args, projected_states):
    checkStatus(projected_states, {'Supercruise': True})
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

    stop_event.set()  # stop the keypress thread

    keys.send('UIFocus')
    return msg


# Ship Launched Fighter Actions
def fighter_request_dock(args, projected_states):
    setGameWindowActive()
    keys.send('OrderRequestDock')
    return f"A request for docking has been sent"


# NPC Crew Order Actions
def npc_order(args, projected_states):
    checkStatus(projected_states, {'Docked': True, 'Landed': True, 'Supercruise': True})
    fighters = projected_states.get('ShipInfo').get('Fighters', [])
    if len(fighters) == 0:
        raise Exception("No figher bay installed in this ship.")

    setGameWindowActive()
    if 'orders' in args:
        for order in args['orders']:
            if order in ['LaunchFighter1', 'LaunchFighter2']:
                if len(fighters) == 1 and order == 'LaunchFighter2':
                    raise Exception("No second figher bay installed in this ship.")
                keys.send('FocusRadarPanel')
                keys.send('UI_Left', repeat=2)
                keys.send('UI_Up', repeat=3)
                keys.send('UI_Down')
                keys.send('UI_Right')
                if order == 'LaunchFighter1':
                    keys.send('UI_Up')
                else:
                    keys.send('UI_Down')
                keys.send('UI_Select')
                keys.send('UI_Up')
                keys.send('UI_Down')
                keys.send('UI_Select')
                keys.send('UIFocus')
                event_manager.wait_for_condition('ShipInfo',
                                                 lambda s: any(fighter.get('Status') == 'Launched' and fighter.get('Pilot') == 'NPC Crew' for fighter in s.get('Fighters', [])), 1)
            else:
                if order == 'ReturnToShip':
                    order = 'RequestDock'
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
    checkStatus(projected_states, {'SrvTurretRetracted': True})
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
    checkStatus(projected_states, {'SrvTurretRetracted': True})
    setGameWindowActive()
    keys.send('BuggyPrimaryFireButton')
    return "Buggy primary fire triggered."


def buggy_secondary_fire(args, projected_states):
    checkStatus(projected_states, {'SrvTurretRetracted': True})
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
    checkStatus(projected_states, {'SrvTurretRetracted': True})
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
    checkStatus(projected_states, {'OnFootInStation': True, 'OnFootInHangar': True, 'OnFootSocialSpace': True})
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
    checkStatus(projected_states, {'OnFootInStation': True, 'OnFootInHangar': True, 'OnFootSocialSpace': True})
    setGameWindowActive()
    keys.send('HumanoidToggleShieldsButton')

    return f"Shields {'activated ' if not projected_states.get('CurrentStatus').get('flags').get('ShieldsUp') else 'deactivated'}."


def clear_authority_level_humanoid(args, projected_states):
    checkStatus(projected_states, {'OnFootInStation': True, 'OnFootInHangar': True, 'OnFootSocialSpace': True})
    setGameWindowActive()
    keys.send('HumanoidClearAuthorityLevel')
    return "Authority level cleared."


def health_pack_humanoid(args, projected_states):
    checkStatus(projected_states, {'OnFootInStation': True, 'OnFootInHangar': True, 'OnFootSocialSpace': True})
    setGameWindowActive()
    keys.send('HumanoidHealthPack')
    return "Health pack used."


def battery_humanoid(args, projected_states):
    checkStatus(projected_states, {'OnFootInStation': True, 'OnFootInHangar': True, 'OnFootSocialSpace': True})
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
    checkStatus(projected_states, {'OnFootInStation': True, 'OnFootInHangar': True, 'OnFootSocialSpace': True})
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
            log("warn", "Failed to set game window as active")
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
        log("warn", 'Window not found!')
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
                keys.send('UI_Down', repeat=2)
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
            show_chat_message('info', 'Target lost, abort cycle')
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
                     llmModelName: str, visionClient: openai.OpenAI | None, visionModelName: str | None,
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
    }, fire_weapons, 'ship', cache_prefill={
        "fire primary weapon": {"weaponType": "primary", "action":"fire"},
        "fire": {"weaponType": "primary", "action":"fire"},
        "fire secondary": {"weaponType": "secondary", "action":"fire"},
        "fire missiles": {"weaponType": "secondary", "action":"fire"},
        "start firing": {"weaponType": "primary", "action":"start"},
        "open fire": {"weaponType": "primary", "action":"start"},
        "stop firing": {"weaponType": "primary", "action":"stop"},
        "cease fire": {"weaponType": "primary", "action":"stop"},
        "weapons fire": {"weaponType": "primary", "action":"fire"},
        "engage weapons": {"weaponType": "primary", "action":"fire"},
        "discovery scanner": {"weaponType": "discovery_scanner", "action":"fire"},
        "honk": {"weaponType": "discovery_scanner", "action":"fire"},
    })

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
    }, set_speed, 'ship', cache_prefill={
        "full stop": {"speed": "Zero"},
        "half speed": {"speed": "50"},
        "full speed": {"speed": "100"},
        "reverse": {"speed": "Minus100"},
    })

    actionManager.registerAction('deployHeatSink', "Deploy heat sink", {
        "type": "object",
        "properties": {}
    }, deploy_heat_sink, 'ship', cache_prefill={
        "heat sink": {},
        "deploy heat sink": {},
        "use heat sink": {},
        "activate heat sink": {},
        "heatsink": {},
        "deploy heatsink": {},
        "cooling": {},
    })

    actionManager.registerAction('deployHardpointToggle', "Deploy or retract hardpoints. Do not call this action when asked to switch hud mode", {
        "type": "object",
        "properties": {}
    }, deploy_hardpoint_toggle, 'ship', cache_prefill={
        "hardpoints": {},
        "deploy hardpoints": {},
        "retract hardpoints": {},
        "toggle hardpoints": {},
        "hardpoints up": {},
        "hardpoints down": {},
        "weapons out": {},
        "weapons away": {},
    })

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
                                 }, manage_power_distribution, 'ship', cache_prefill={
        "balance power": {"power_category": ["Engines", "Weapons", "Systems"], "balance_power": True},
        "reset power": {"power_category": ["Engines", "Weapons", "Systems"], "balance_power": True},
        "four pips to engines": {"power_category": ["Engines"], "pips": [4]},
        "four pips to weapons": {"power_category": ["Weapons"], "pips": [4]},
        "four pips to systems": {"power_category": ["Systems"], "pips": [4]},
        "max engines": {"power_category": ["Engines"], "pips": [4]},
        "max weapons": {"power_category": ["Weapons"], "pips": [4]},
        "max systems": {"power_category": ["Systems"], "pips": [4]},
        "pips to engines": {"power_category": ["Engines"], "pips": [2]},
        "pips to weapons": {"power_category": ["Weapons"], "pips": [2]},
        "pips to systems": {"power_category": ["Systems"], "pips": [2]},
    })

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
    }, galaxy_map_open, 'ship', cache_prefill={
        "galaxy map": {},
        "open galaxy map": {},
        "galmap": {},
        "navigation": {},
        "star map": {},
        "show galaxy map": {},
        "nav map": {},
    })

    actionManager.registerAction('galaxyMapClose', "Close galaxy map", {
        "type": "object",
        "properties": {},
    }, galaxy_map_close, 'ship', cache_prefill={
        "close galaxy map": {},
    })

    actionManager.registerAction('systemMapOpenOrClose', "Open or close system map", {
        "type": "object",
        "properties": {
            "desired_state": {
                "type": "string",
                "enum": ["open", "close"],
                "description": "Desired state for the system map: open or close.",
            },
        },
    }, system_map_open_or_close, 'ship', cache_prefill={
        "system map": {"desired_state": "open"},
        "open system map": {"desired_state": "open"},
        "close system map": {"desired_state": "close"},
        "orrery": {"desired_state": "open"},
        "local map": {"desired_state": "open"},
        "sysmap": {"desired_state": "open"},
        "show system map": {"desired_state": "open"},
    })

    actionManager.registerAction('targetShip', "Target a ship - cycle to next/previous target or select highest threat", {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "description": "Target selection mode",
                "enum": ["next", "previous", "highest_threat", "next_hostile", "previous_hostile", "wingman_1", "wingman_2", "wingman_3", "wingman_1_target", "wingman_2_target", "wingman_3_target"],
                "default": "next"
            }
        }
    }, target_ship, 'ship', cache_prefill={
        "next target": {"mode": "next"},
        "previous target": {"mode": "previous"},
        "highest threat": {"mode": "highest_threat"},
        "target highest threat": {"mode": "highest_threat"},
        "target biggest threat": {"mode": "highest_threat"},
        "target enemy": {"mode": "next_hostile"},
        "cycle target": {"mode": "next"},
        "select target": {"mode": "next"},
        "next hostile": {"mode": "next_hostile"},
        "next enemy": {"mode": "next_hostile"},
        "cycle hostile": {"mode": "next_hostile"},
        "hostile target": {"mode": "next_hostile"},
        "previous hostile": {"mode": "previous_hostile"},
        "previous enemy": {"mode": "previous_hostile"},
        "first wingman": {"mode": "wingman_1"},
        "target first wingman": {"mode": "wingman_1"},
        "first wingmate": {"mode": "wingman_1"},
        "target first wingmate": {"mode": "wingman_1"},
        "first teammate": {"mode": "wingman_1"},
        "target first teammate": {"mode": "wingman_1"},
        "second wingman": {"mode": "wingman_2"},
        "target second wingman": {"mode": "wingman_2"},
        "second wingmate": {"mode": "wingman_2"},
        "target second wingmate": {"mode": "wingman_2"},
        "second teammate": {"mode": "wingman_2"},
        "target second teammate": {"mode": "wingman_2"},
        "third wingman": {"mode": "wingman_3"},
        "target third wingman": {"mode": "wingman_3"},
        "third wingmate": {"mode": "wingman_3"},
        "target third wingmate": {"mode": "wingman_3"},
        "third teammate": {"mode": "wingman_3"},
        "target third teammate": {"mode": "wingman_3"},
        "first wingman target": {"mode": "wingman_1_target"},
        "target first wingman's target": {"mode": "wingman_1_target"},
        "first wingmate target": {"mode": "wingman_1_target"},
        "target first wingmate's target": {"mode": "wingman_1_target"},
        "first teammate target": {"mode": "wingman_1_target"},
        "target first teammate's target": {"mode": "wingman_1_target"},
        "second wingman target": {"mode": "wingman_2_target"},
        "target second wingman's target": {"mode": "wingman_2_target"},
        "second wingmate target": {"mode": "wingman_2_target"},
        "target second wingmate's target": {"mode": "wingman_2_target"},
        "second teammate target": {"mode": "wingman_2_target"},
        "target second teammate's target": {"mode": "wingman_2_target"},
        "third wingman target": {"mode": "wingman_3_target"},
        "target third wingman's target": {"mode": "wingman_3_target"},
        "third wingmate target": {"mode": "wingman_3_target"},
        "target third wingmate's target": {"mode": "wingman_3_target"},
        "third teammate target": {"mode": "wingman_3_target"},
        "target third teammate's target": {"mode": "wingman_3_target"},
    })

    actionManager.registerAction('toggleWingNavLock', "Toggle wing nav lock", {
        "type": "object",
        "properties": {}
    }, toggle_wing_nav_lock, 'ship', cache_prefill={
        "wing nav lock": {},
        "disable wing nav lock": {},
        "disengage wing nav lock": {},
        "enable wing nav lock": {},
        "engage wing nav lock": {},
        "toggle wing nav lock": {},
        "wing navigation lock": {},
        "wing nav": {},
        "nav lock": {},
        "navigation lock": {},
        "wing follow": {},
        "follow wing": {},
    })

    actionManager.registerAction(
        'cycle_fire_group',
        "call this tool if the user asks to cycle, select or switch to specific firegroup, the the next firegroup or to the previous firegroup",
        {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "description": "If next or previous is give: Cycle direction: 'next' or 'previous'.",
                    "enum": ["next", "previous"],
                    "default": "next"
                },
                "fire_group": {
                    "type": "integer",
                    "description": "Specific firegroup index to select. Letters A=0, B=1, C=2, etc."
                }
            },
        },
        cycle_fire_group,
        'ship',
        cache_prefill={
            "next fire group": {"direction":"next"},
            "previous fire group": {"direction":"previous"},
            "select next fire group": {"direction":"next"},
            "select previous fire group": {"direction":"previous"},
        }
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
    }, change_hud_mode, 'mainship', cache_prefill={
        "combat mode": {"hud mode": "combat"},
        "analysis mode": {"hud mode": "analysis"},
        "switch to combat": {"hud mode": "combat"},
        "switch to analysis": {"hud mode": "analysis"},
        "toggle hud mode": {"hud mode": "toggle"},
        "hud mode": {"hud mode": "toggle"},
        "change hud": {"hud mode": "toggle"},
    })

    actionManager.registerAction('shipSpotLightToggle', "Toggle ship spotlight", {
        "type": "object",
        "properties": {}
    }, ship_spot_light_toggle, 'ship', cache_prefill={
        "ship light": {},
        "lights": {},
        "lights on": {},
        "turn on lights": {},
        "lights off": {},
        "toggle lights": {},
        "toggle the lights": {}
    })

    actionManager.registerAction('fireChaffLauncher', "Fire chaff launcher", {
        "type": "object",
        "properties": {}
    }, fire_chaff_launcher, 'ship', cache_prefill={
        "chaff": {},
        "fire chaff": {},
        "launch chaff": {},
        "deploy chaff": {},
        "countermeasures": {},
        "evade": {},
    })

    actionManager.registerAction('nightVisionToggle', "Toggle night vision", {
        "type": "object",
        "properties": {}
    }, night_vision_toggle, 'ship', cache_prefill={
        "nightvision": {},
        "night vision": {},
        "toggle nightvision": {},
        "thermal vision": {},
        "enhanced vision": {},
        "infrared": {},
    })



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
    }, target_subsystem, 'ship', cache_prefill={
        "target drive": {"subsystem":"Drive"},
        "target drives": {"subsystem":"Drive"},
        "target power distributor": {"subsystem":"Power Distributor"},
        "target distributor": {"subsystem":"Power Distributor"},
        "target shields": {"subsystem":"Shield Generator"},
        "target shield generator": {"subsystem":"Shield Generator"},
        "target life support": {"subsystem":"Life Support"},
        "target frame shift drive": {"subsystem":"FSD"},
        "target fsd": {"subsystem":"FSD"},
        "target power": {"subsystem":"Power Plant"},
        "target power plant": {"subsystem":"Power Plant"},
        "target the drive": {"subsystem":"Drive"},
        "target the drives": {"subsystem":"Drive"},
        "target the power distributor": {"subsystem":"Power Distributor"},
        "target the distributor": {"subsystem":"Power Distributor"},
        "target the shields": {"subsystem":"Shield Generator"},
        "target the shield generator": {"subsystem":"Shield Generator"},
        "target the life support": {"subsystem":"Life Support"},
        "target the frame shift drive": {"subsystem":"FSD"},
        "target the fsd": {"subsystem":"FSD"},
        "target the power": {"subsystem":"Power Plant"},
        "target the power plant": {"subsystem":"Power Plant"},
    })

    actionManager.registerAction('chargeECM', "Charge ECM", {
        "type": "object",
        "properties": {}
    }, charge_ecm, 'ship', cache_prefill={
        "ecm": {},
        "charge ecm": {},
        "electronic countermeasures": {},
        "activate ecm": {},
        "ecm blast": {},
        "disrupt": {},
    })

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
                        "ReturnToShip",
                        "LaunchFighter1",
                        "LaunchFighter2",
                    ]
                }
            }
        }
    }, npc_order, 'ship', cache_prefill={
        "launch fighter": {"orders": ["LaunchFighter1"]},
        "deploy fighter": {"orders": ["LaunchFighter1"]},
        "recall fighter": {"orders": ["ReturnToShip"]},
        "attack my target": {"orders": ["FocusTarget"]},
        "engage target": {"orders": ["FocusTarget"]},
        "defend me": {"orders": ["DefensiveBehaviour"]},
        "be aggressive": {"orders": ["AggressiveBehaviour"]},
        "hold fire": {"orders": ["HoldFire"]},
        "cease fire": {"orders": ["HoldFire"]},
        "hold position": {"orders": ["HoldPosition"]},
        "follow me": {"orders": ["Follow"]},
    })

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
                                 }, fsd_jump, 'mainship', cache_prefill={
        "jump": {"jump_type": "auto"},
        "engage fsd": {"jump_type": "auto"},
        "frame shift drive": {"jump_type": "auto"},
        "jump to next system": {"jump_type": "next_system"},
        "hyperspace jump": {"jump_type": "next_system"},
        "supercruise": {"jump_type": "supercruise"},
        "enter supercruise": {"jump_type": "supercruise"},
        "punch it": {"jump_type": "auto"},
        "let's go": {"jump_type": "auto"},
    })

    actionManager.registerAction('target_next_system_in_route',
                                 "When we have a nav route set, this will automatically target the next system in the route",
                                 {
                                     "type": "object",
                                     "properties": {}
                                 }, next_system_in_route, 'mainship', cache_prefill={
        "next system": {},
        "target next system": {},
        "next destination": {},
        "next waypoint": {},
        "continue route": {},
        "next in route": {},
    })

    actionManager.registerAction('toggleCargoScoop', "Toggles cargo scoop", {
        "type": "object",
        "properties": {}
    }, toggle_cargo_scoop, 'mainship', cache_prefill={
        "cargo scoop": {},
        "scoop": {},
        "deploy scoop": {},
        "retract scoop": {},
        "toggle scoop": {},
        "open cargo scoop": {},
        "close cargo scoop": {},
    })

    actionManager.registerAction('ejectAllCargo', "Eject all cargo", {
        "type": "object",
        "properties": {}
    }, eject_all_cargo, 'mainship', cache_prefill={
        "eject cargo": {},
        "dump cargo": {},
        "jettison cargo": {},
        "drop cargo": {},
        "emergency cargo drop": {},
        "purge cargo": {},
    })

    actionManager.registerAction('landingGearToggle', "Toggle landing gear", {
        "type": "object",
        "properties": {}
    }, landing_gear_toggle, 'mainship', cache_prefill={
        "landing gear": {},
        "gear": {},
        "deploy gear": {},
        "retract gear": {},
        "landing gear up": {},
        "landing gear down": {},
        "gear up": {},
        "gear down": {},
    })

    actionManager.registerAction('useShieldCell', "Use shield cell", {
        "type": "object",
        "properties": {}
    }, use_shield_cell, 'mainship', cache_prefill={
        "shield cell": {},
        "use shield cell": {},
        "scb": {},
        "activate scb": {},
        "shield boost": {},
        "repair shields": {},
        "restore shields": {},
    })

    actionManager.registerAction('requestDocking', "Request docking.", {
        "type": "object",
        "properties": {}
    }, request_docking, 'mainship', cache_prefill={
        "request docking": {},
        "dock": {},
        "docking request": {},
        "permission to dock": {},
        "requesting docking": {},
        "docking permission": {},
    })

    actionManager.registerAction('undockShip', "", {
        "type": "object",
        "properties": {}
    }, undock, 'mainship', cache_prefill={
        "undock": {},
        "launch": {},
        "depart": {},
        "leave station": {},
        "takeoff": {},
        "disengage": {},
    })

    # Register actions - Ship Launched Fighter Actions
    actionManager.registerAction('fighterRequestDock', "Request docking for Ship Launched Fighter", {
        "type": "object",
        "properties": {}
    }, fighter_request_dock, 'fighter', cache_prefill={
        "request docking": {},
        "dock": {},
        "docking request": {},
        "permission to dock": {},
        "requesting docking": {},
        "docking permission": {},
    })

    # Register actions - SRV Actions (Horizons)
    actionManager.registerAction('toggleDriveAssist', "Toggle drive assist", {
        "type": "object",
        "properties": {}
    }, toggle_drive_assist, 'buggy', cache_prefill={
        "drive assist": {},
        "toggle drive assist": {},
        "assistance": {},
        "auto drive": {},
        "driving assistance": {},
        "stability": {},
    })

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
    }, fire_weapons_buggy, 'buggy', cache_prefill={
        "fire srv weapons": {"weaponType": "primary", "action": "fire"},
        "shoot": {"weaponType": "primary", "action": "fire"},
        "fire plasma": {"weaponType": "primary", "action": "fire"},
        "fire missiles": {"weaponType": "secondary", "action": "fire"},
        "srv weapons": {"weaponType": "primary", "action": "fire"},
        "engage weapons": {"weaponType": "primary", "action": "fire"},
    })

    actionManager.registerAction('autoBreak', "Toggle auto-brake", {
        "type": "object",
        "properties": {}
    }, auto_break_buggy, 'buggy', cache_prefill={
        "auto brake": {},
        "toggle brake": {},
        "automatic braking": {},
        "brake assist": {},
        "handbrake": {},
        "parking brake": {},
    })

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
    }, headlights_buggy, 'buggy', cache_prefill={
        "lights": {"desired_state": "toggle"},
        "headlights": {"desired_state": "toggle"},
        "toggle lights": {"desired_state": "toggle"},
        "lights on": {"desired_state": "high"},
        "lights off": {"desired_state": "off"},
        "bright lights": {"desired_state": "high"},
        "dim lights": {"desired_state": "low"},
        "full beam": {"desired_state": "high"},
    })

    actionManager.registerAction('nightVisionToggleBuggy', "Toggle night vision", {
        "type": "object",
        "properties": {}
    }, night_vision_toggle, 'buggy', cache_prefill={
        "nightvision": {},
        "night vision": {},
        "toggle nightvision": {},
        "thermal vision": {},
        "enhanced vision": {},
        "infrared": {},
    })

    actionManager.registerAction('toggleTurret', "Toggle turret mode", {
        "type": "object",
        "properties": {}
    }, toggle_buggy_turret, 'buggy', cache_prefill={
        "turret": {},
        "toggle turret": {},
        "turret mode": {},
        "gun turret": {},
        "deploy turret": {},
        "retract turret": {},
    })

    actionManager.registerAction('selectTargetBuggy', "Select target", {
        "type": "object",
        "properties": {}
    }, select_target_buggy, 'buggy', cache_prefill={
        "target": {},
        "select target": {},
        "lock target": {},
        "acquire target": {},
        "scan": {},
        "focus": {},
    })

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
                                 }, manage_power_distribution_buggy, 'buggy', cache_prefill={
        "balance power": {"power_category": ["Engines", "Weapons", "Systems"], "balance_power": True},
        "reset power": {"power_category": ["Engines", "Weapons", "Systems"], "balance_power": True},
        "four pips to engines": {"power_category": ["Engines"], "pips": [4]},
        "four pips to weapons": {"power_category": ["Weapons"], "pips": [4]},
        "four pips to systems": {"power_category": ["Systems"], "pips": [4]},
        "max engines": {"power_category": ["Engines"], "pips": [4]},
        "max weapons": {"power_category": ["Weapons"], "pips": [4]},
        "max systems": {"power_category": ["Systems"], "pips": [4]},
        "pips to engines": {"power_category": ["Engines"], "pips": [2]},
        "pips to weapons": {"power_category": ["Weapons"], "pips": [2]},
        "pips to systems": {"power_category": ["Systems"], "pips": [2]},
    })

    actionManager.registerAction('toggleCargoScoopBuggy', "Toggle cargo scoop", {
        "type": "object",
        "properties": {}
    }, toggle_cargo_scoop_buggy, 'buggy', cache_prefill={
        "cargo scoop": {},
        "scoop": {},
        "deploy scoop": {},
        "retract scoop": {},
        "toggle scoop": {},
        "collect materials": {},
    })

    actionManager.registerAction('ejectAllCargoBuggy', "Eject all cargo", {
        "type": "object",
        "properties": {}
    }, eject_all_cargo_buggy, 'buggy', cache_prefill={
        "eject cargo": {},
        "dump cargo": {},
        "jettison cargo": {},
        "drop cargo": {},
        "purge cargo": {},
        "drop materials": {},
    })

    actionManager.registerAction('recallDismissShipBuggy', "Recall or dismiss ship", {
        "type": "object",
        "properties": {}
    }, recall_dismiss_ship_buggy, 'buggy', cache_prefill={
        "recall ship": {},
        "dismiss ship": {},
        "call ship": {},
        "send ship away": {},
        "summon ship": {},
        "ship pickup": {},
    })

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
    }, galaxy_map_open_buggy, 'buggy', cache_prefill={
        "galaxy map": {"desired_state": "open"},
        "open galaxy map": {"desired_state": "open"},
        "close galaxy map": {"desired_state": "close"},
        "galmap": {"desired_state": "open"},
        "navigation": {"desired_state": "open"},
        "star map": {"desired_state": "open"},
        "nav map": {"desired_state": "open"},
    })

    actionManager.registerAction('systemMapOpenOrCloseBuggy', "Open/close system map.", {
        "type": "object",
        "properties": {
            "desired_state": {
                "type": "string",
                "enum": ["open", "close"],
                "description": "Desired state for the system map: open or close.",
            },
        },
    }, system_map_open_buggy, 'buggy', cache_prefill={
        "system map": {"desired_state": "open"},
        "open system map": {"desired_state": "open"},
        "close system map": {"desired_state": "close"},
        "orrery": {"desired_state": "open"},
        "local map": {"desired_state": "open"},
        "sysmap": {"desired_state": "open"},
        "show system map": {"desired_state": "open"},
    })

    # Register actions - On-Foot Actions
    actionManager.registerAction('primaryInteractHumanoid', "Primary interact action", {
        "type": "object",
        "properties": {}
    }, primary_interact_humanoid, 'humanoid', cache_prefill={
        "interact": {},
        "primary interact": {},
        "use": {},
        "activate": {},
        "press": {},
        "engage": {},
    })

    actionManager.registerAction('secondaryInteractHumanoid', "Secondary interact action", {
        "type": "object",
        "properties": {}
    }, secondary_interact_humanoid, 'humanoid', cache_prefill={
        "secondary interact": {},
        "alternate use": {},
        "secondary action": {},
        "hold interact": {},
        "long press": {},
        "alternative": {},
    })

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
    }, equip_humanoid, 'humanoid', cache_prefill={
        "primary weapon": {"equipment": "HumanoidSelectPrimaryWeaponButton"},
        "secondary weapon": {"equipment": "HumanoidSelectSecondaryWeaponButton"},
        "utility weapon": {"equipment": "HumanoidSelectUtilityWeaponButton"},
        "recharge tool": {"equipment": "HumanoidSwitchToRechargeTool"},
        "comp analyser": {"equipment": "HumanoidSwitchToCompAnalyser"},
        "composition scanner": {"equipment": "HumanoidSwitchToCompAnalyser"},
        "suit tool": {"equipment": "HumanoidSwitchToSuitTool"},
        "hide weapon": {"equipment": "HumanoidHideWeaponButton"},
        "holster": {"equipment": "HumanoidHideWeaponButton"},
        "frag grenade": {"equipment": "HumanoidSelectFragGrenade"},
        "emp grenade": {"equipment": "HumanoidSelectEMPGrenade"},
        "shield grenade": {"equipment": "HumanoidSelectShieldGrenade"},
        "scanner": {"equipment": "HumanoidSwitchToCompAnalyser"},
        "energylink": {"equipment": "HumanoidSwitchToRechargeTool"},
        "profile analyser": {"equipment": "HumanoidSwitchToSuitTool"},
    })

    actionManager.registerAction('toggleFlashlightHumanoid', "Toggle flashlight", {
        "type": "object",
        "properties": {}
    }, toggle_flashlight_humanoid, 'humanoid', cache_prefill={
        "flashlight": {},
        "torch": {},
        "lights": {},
        "toggle lights": {},
        "illumination": {},
        "helmet light": {},
    })

    actionManager.registerAction('toggleNightVisionHumanoid', "Toggle night vision", {
        "type": "object",
        "properties": {}
    }, toggle_night_vision_humanoid, 'humanoid', cache_prefill={
        "nightvision": {},
        "night vision": {},
        "toggle nightvision": {},
        "thermal vision": {},
        "enhanced vision": {},
        "infrared": {},
    })

    actionManager.registerAction('toggleShieldsHumanoid', "Toggle shields", {
        "type": "object",
        "properties": {}
    }, toggle_shields_humanoid, 'humanoid', cache_prefill={
        "suit shields": {},
        "personal shields": {},
        "toggle shields": {},
        "energy shield": {},
        "shield generator": {},
        "protective field": {},
    })

    actionManager.registerAction('clearAuthorityLevelHumanoid', "Clear authority level", {
        "type": "object",
        "properties": {}
    }, clear_authority_level_humanoid, 'humanoid', cache_prefill={
        "clear authority": {},
        "reset authority": {},
        "clear wanted level": {},
        "clear notoriety": {},
        "authority reset": {},
        "clean record": {},
    })

    actionManager.registerAction('healthPackHumanoid', "Use health pack", {
        "type": "object",
        "properties": {}
    }, health_pack_humanoid, 'humanoid', cache_prefill={
        "health pack": {},
        "medkit": {},
        "heal": {},
        "use medkit": {},
        "medical": {},
        "first aid": {},
    })

    actionManager.registerAction('batteryHumanoid', "Use battery", {
        "type": "object",
        "properties": {}
    }, battery_humanoid, 'humanoid', cache_prefill={
        "battery": {},
        "energy cell": {},
        "recharge": {},
        "power up": {},
        "restore power": {},
        "charge suit": {},
    })

    actionManager.registerAction('galaxyMapOpenOrCloseHumanoid', "Open or Close Galaxy Map", {
        "type": "object",
        "properties": {}
    }, galaxy_map_open_humanoid, 'humanoid', cache_prefill={
        "galaxy map": {},
        "open galaxy map": {},
        "galmap": {},
        "navigation": {},
        "star map": {},
        "nav map": {},
        "show galaxy map": {},
    })

    actionManager.registerAction('systemMapOpenOrCloseHumanoid', "Open or Close System Map", {
        "type": "object",
        "properties": {}
    }, system_map_open_humanoid, 'humanoid', cache_prefill={
        "system map": {},
        "open system map": {},
        "close system map": {},
        "orrery": {},
        "local map": {},
        "sysmap": {},
        "show system map": {},
    })

    actionManager.registerAction('recallDismissShipHumanoid', "Recall or dismiss ship", {
        "type": "object",
        "properties": {}
    }, recall_dismiss_ship_humanoid, 'humanoid', cache_prefill={
        "recall ship": {},
        "dismiss ship": {},
        "call ship": {},
        "send ship away": {},
        "summon ship": {},
        "ship pickup": {},
    })

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
        "required": ["message", "channel"]
    }, send_message, 'global')
    
    register_web_actions(
        actionManager, eventManager, 
        llmClient, llmModelName, edKeys
    )

    register_ui_actions(
        actionManager, eventManager
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

