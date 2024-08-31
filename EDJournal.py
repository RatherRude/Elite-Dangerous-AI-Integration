from datetime import datetime
from json import loads
from os import listdir
from os.path import join, isfile, getmtime
from time import sleep
from typing import Dict, List

from EDlogger import logger
from WindowsKnownPaths import *

"""
Description: This file perform journal file processing.  It opens the latest updated Journal* 
file in the Saved directory, loads in the entries.  Specific entries are stored in a dictionary.
Every time the dictionary is access the file will be read and if new lines exist those will be loaded
and parsed.

The dictionary can be accesses via:  
    jn = EDJournal()

    print("Ship = ", jn.ship_state())
    ... jn.ship_state()['shieldsup']

Design:
  - open the file once
  - when accessing a field in the ship_state() first see if more to read from open file, if so 
    process it
    - also check if a new journal file present, if so close current one and open new one

"""


class EDJournal:
    def __init__(self, game_events: Dict[str, Dict[str, bool]]):
        self.log_file = None
        self.current_log = self.get_latest_log()
        if self.current_log:
            self.open_journal(self.current_log)

        # game events that can be written into self.ship.extra_events
        self.enabled_game_events: List[str] = []
        if game_events:
            for category, events in game_events.items():
                for event, state in events.items():
                    if event != "Music":
                        self.enabled_game_events.append(event)

        self.ship = {
            'disembark': False,
            'shieldsup': True,
            'under_attack': None,
            'mission_completed': 0,
            'mission_redirected': 0,
            'status': 'in_space',
            'star_class': None,
            'body': None,
            'type': None,
            'fuel_level': None,
            'fuel_capacity': None,
            'fuel_percent': None,
            'is_scooping': False,
            'location': None,
            'target': None,
            'jumps_remains': 0,
            'dist_jumped': 0,
            'time': (datetime.now() - datetime.fromtimestamp(
                getmtime(self.current_log))).seconds if self.current_log else 0,
            'cockpit_breached': False,
            'extra_events': []
        }
        self.ship_state()  # load up from file
        self.reset_items()

    # these items do not have respective log entries to clear them.  After initial reading of log file, clear these items
    # also the App will need to reset these to False after detecting they were True
    def reset_items(self):
        defaultValues = {
            'under_attack': False,
            'fighter_destroyed': False,
            'cockpit_breached': False
        }
        self.ship = {**self.ship, **defaultValues}

    def get_latest_log(self, path_logs=None):
        """Returns the full path of the latest (most recent) elite log file (journal) from specified path"""
        if not path_logs:
            path_logs = get_path(FOLDERID.SavedGames, UserHandle.current) + "\Frontier Developments\Elite Dangerous"
        try:
            list_of_logs = [join(path_logs, f) for f in listdir(path_logs) if
                            isfile(join(path_logs, f)) and f.startswith('Journal.')]
        except:
            return None
        if not list_of_logs:
            return None
        latest_log = max(list_of_logs, key=getmtime)
        return latest_log

    def open_journal(self, log_name):
        # if journal file is open then close it
        if self.log_file is not None:
            self.log_file.close()

        logger.info("Opening new Journal: " + log_name)

        # open the latest journal
        self.log_file = open(log_name, encoding="utf-8")

    def fill_disembark_object(self, data):
        disembark_data = {
            'StarSystem': data.get('StarSystem'),
            'Body': data.get('Body'),
            'OnStation': data.get('OnStation'),
            'OnPlanet': data.get('OnPlanet'),
            'StationName': data.get('StationName'),
            'StationType': data.get('StationType')
        }

        if data.get('SRV'):
            disembark_data['SRV'] = data.get('SRV')
        if data.get('Taxi'):
            disembark_data['Taxi'] = data.get('Taxi')
        if data.get('Multicrew'):
            disembark_data['Multicrew'] = data.get('Multicrew')

        return disembark_data

    def parse_line(self, log):
        # parse data
        try:
            # parse ship status
            log_event = log['event']

            # Event processing
            # if log_event == 'Fileheader':
            #    self.ship['odyssey'] = True   # hardset to true for ED 4.0 since menus now same for Horizon
            #    return   # No need to do further processing on this record, should use elif: all the way down

            if log_event == 'ShieldState':
                self.ship['shieldsup'] = log['ShieldsUp']

            elif log_event == 'UnderAttack':
                self.ship['under_attack'] = True

            elif log_event == 'Embark':
                self.ship['disembark'] = False
                # print('embark')
                # print(self.ship['Disembark'])

            elif log_event == 'Disembark':
                self.ship['disembark'] = self.fill_disembark_object(log)
                # print('disembark')
                # print(log)
                # print(self.ship['disembark'])

            elif log_event == 'FighterDestroyed':
                self.ship['fighter_destroyed'] = True
                self.ship['fighter_launched'] = False

            elif log_event == 'MissionCompleted':
                self.ship['mission_completed'] += 1

            # elif log_event == 'MissionRedirected':
            #    self.ship['mission_redirected'] += 1

            elif log_event == 'StartJump':
                self.ship['status'] = str('starting_' + log['JumpType']).lower()
                if log['JumpType'] == 'Hyperspace':
                    self.ship['star_class'] = log['StarClass']

            elif log_event == 'SupercruiseEntry' or log_event == 'FSDJump':
                self.ship['status'] = 'in_supercruise'

            elif log_event == "DockingGranted":
                self.ship['status'] = 'dockinggranted'

            elif log_event == "DockingDenied":
                self.ship['status'] = 'dockingdenied'
                # self.ship['no_dock_reason'] = log['Reason']

            elif log_event == 'SupercruiseExit':
                self.ship['status'] = 'in_space'
                self.ship['body'] = log['Body']

            elif log_event == 'DockingCancelled':
                self.ship['status'] = 'in_space'

            elif log_event == 'Undocked':
                self.ship['status'] = 'starting_undocking'

            elif log_event == 'DockingRequested':
                self.ship['status'] = 'starting_docking'

            elif log_event == "Music" and log['MusicTrack'] == "DockingComputer":
                if self.ship['status'] == 'starting_undocking':
                    self.ship['status'] = 'in_undocking'
                elif self.ship['status'] == 'starting_docking':
                    self.ship['status'] = 'in_docking'

            elif log_event == "Music" and log['MusicTrack'] == "NoTrack" and self.ship['status'] == 'in_undocking':
                self.ship['status'] = 'in_space'

            elif log_event == "Music" and log['MusicTrack'] == "Exploration" and self.ship['status'] == 'in_undocking':
                self.ship['status'] = 'in_space'

            elif log_event == 'Docked':
                self.ship['status'] = 'in_station'

            elif log_event == 'Location' and log['Docked']:
                self.ship['status'] = 'in_station'

            # parse ship type
            elif log_event == 'Loadout':
                self.ship['type'] = log['Ship']

            # parse fuel
            if 'FuelLevel' in log and self.ship['type'] != 'TestBuggy':
                self.ship['fuel_level'] = log['FuelLevel']
            if 'FuelCapacity' in log and self.ship['type'] != 'TestBuggy':
                try:
                    self.ship['fuel_capacity'] = log['FuelCapacity']['Main']
                except:
                    self.ship['fuel_capacity'] = log['FuelCapacity']
            if log_event == 'FuelScoop' and 'Total' in log:
                self.ship['fuel_level'] = log['Total']
            if self.ship['fuel_level'] and self.ship['fuel_capacity']:
                self.ship['fuel_percent'] = round((self.ship['fuel_level'] / self.ship['fuel_capacity']) * 100)
            else:
                self.ship['fuel_percent'] = 100

            # parse scoop
            if log_event == 'FuelScoop' and self.ship['time'] < 10 and self.ship['fuel_percent'] < 100:
                self.ship['is_scooping'] = True
            else:
                self.ship['is_scooping'] = False

            # parse location
            if log_event == 'Location':
                # List of properties to check in the log entry
                properties = [
                    'DistFromStarLS', 'Docked', 'StationName', 'StationType',
                    'StationGovernment_Localised', 'StationEconomy_Localised', 'Taxi',
                    'StarSystem', 'SystemAllegiance', 'SystemEconomy_Localised',
                    'SystemSecondEconomy_Localised', 'SystemGovernment_Localised',
                    'SystemSecurity_Localised', 'Population', 'SystemFaction'
                    # , 'Conflicts'
                ]

                self.ship['location'] = {}

                for prop in properties:
                    if prop in log:
                        self.ship['location'][prop.replace('_Localised', '') if prop.endswith('_Localised') else prop] = \
                        log[prop]

                # Filter Factions list
                if 'Factions' in log:
                    filtered_factions = []

                    for faction in log['Factions']:
                        filtered_faction = {}

                        for key in ['Name', 'FactionState', 'MyReputation']:
                            if key in faction:
                                filtered_faction[key] = faction[key]

                        filtered_factions.append(filtered_faction)

                    self.ship['location']['Factions'] = filtered_factions

            if log_event == 'FSDJump' and 'StarSystem' in log:
                self.ship['location'] = {'StarSystem': log['StarSystem']}

            # parse target
            if log_event == 'FSDTarget':
                if log['Name'] == self.ship['location']:
                    self.ship['target'] = None
                    self.ship['jumps_remains'] = 0
                else:
                    self.ship['target'] = {'StarSystem': log['Name']}
                    try:
                        self.ship['jumps_remains'] = log['RemainingJumpsInRoute']
                    except:
                        pass
                        #
                        #    'Log did not have jumps remaining. This happens most if you have less than .' +
                        #    '3 jumps remaining. Jumps remaining will be inaccurate for this jump.')

            elif log_event == 'FSDJump':
                if self.ship['location'] == self.ship['target']:
                    self.ship['target'] = None
                self.ship['dist_jumped'] = log["JumpDist"]

            # New event types
            elif log_event == 'ApproachSettlement':
                self.ship['status'] = 'approaching_settlement'

            # elif log_event == 'Bounty':
            #     self.ship['bounty'] = log['Reward']

            elif log_event == 'CockpitBreached':
                self.ship['cockpit_breached'] = True

            elif log_event == 'CommitCrime':
                self.ship['committed_crime'] = log['CrimeType']

            elif log_event == 'CrewLaunchFighter' or log_event == 'LaunchFighter':
                self.ship['fighter_launched'] = True

            elif log_event == 'DockFighter':
                self.ship['fighter_launched'] = False

            elif log_event == 'LaunchSRV':
                self.ship['srv_launched'] = True

            elif log_event == 'DockSRV':
                self.ship['srv_launched'] = False

            elif log_event == 'Touchdown':
                self.ship['status'] = 'landed'

            elif log_event == 'Liftoff':
                self.ship['status'] = 'liftoff'

            elif log_event == 'DatalinkScan':
                self.ship['datalink_scan'] = True

            elif log_event == 'SelfDestruct':
                self.ship['status'] = 'self_destruct'

            elif log_event == 'Died':
                self.ship['status'] = 'destroyed'

            elif log_event == 'Resurrect':
                self.ship['status'] = 'resurrected'

            elif log_event == 'EjectCargo':
                self.ship['cargo_ejected'] = True

            elif log_event == 'Location':
                if log['Docked']:
                    self.ship['status'] = 'in_station'
                # else:
                # self.ship['location'] = log['StarSystem']

            elif log_event == 'MissionAccepted':
                self.ship['mission_accepted'] = log['MissionID']

            elif log_event == 'MissionCompleted':
                self.ship['mission_completed'] += 1

            elif log_event == 'MissionFailed':
                self.ship['mission_failed'] = log['MissionID']

            elif log_event == 'MissionAbandoned':
                self.ship['mission_abandoned'] = log['MissionID']

            # Travel Events:
            elif log_event == 'ApproachBody':
                self.ship['status'] = 'approaching_body'

            elif log_event == 'ApproachStar':
                self.ship['status'] = 'approaching_star'

            elif log_event == 'HeatWarning':
                self.ship['status'] = 'heat_warning'

            elif log_event == 'HeatDamage':
                self.ship['status'] = 'heat_damage'

            # elif log_event == 'ShieldHealth':
            #    self.ship['shield_health'] = log['Health']

            # elif log_event == 'UnderAttack':
            #     self.ship['under_attack'] = True

            # elif log_event == 'StartJump':
            #     self.ship['jumps_remains'] = log['JumpsRemaining']

            # elif log_event == 'CargoTransfer':
            #    self.ship['cargo_transfer'] = log['Direction']

            elif log_event == 'DockingTimeout':
                self.ship['status'] = 'docking_timeout'

            elif log_event == 'DockingRequested':
                self.ship['status'] = 'docking_requested'

            elif log_event == 'DockingDenied':
                self.ship['status'] = 'docking_denied'
                # self.ship['no_dock_reason'] = log['Reason']

            elif log_event == 'DockingGranted':
                self.ship['status'] = 'docking_granted'

            elif log_event == 'DockingComplete':
                self.ship['status'] = 'docking_complete'

            elif log_event == 'DockingCancelled':
                self.ship['status'] = 'docking_cancelled'

            # elif log_event == 'MiningRefined':
            #     self.ship['mining_refined'] = log['Type']

            # elif log_event == 'USSDrop':
            #     self.ship['uss_type'] = log['USSType']
            #     self.ship['uss_scan_stage'] = log['USSType_Localised']

            #  elif log_event == 'AsteroidCracked':
            #      self.ship['asteroid_cracked'] = log['Body']

            #   elif log_event == 'ProspectedAsteroid':
            #       self.ship['asteroid_prospected'] = log['Materials']

            #  elif log_event == 'Scan':
            #      self.ship['scan_complete'] = log['ScanType']

            #  elif log_event == 'ReceiveText':
            #      self.ship['received_text'] = log['From']
            #      self.ship['message'] = log['Message']

            if log_event in self.enabled_game_events:
                self.ship['extra_events'].append({
                    "event_type": log_event,
                    "event_content": log
                })

        # exceptions
        except Exception as e:
            print(f'Exception on EDJournal Read: {e}')

    def ship_state(self):
        latest_log = self.get_latest_log()

        if not latest_log:
            return self.ship

        # open journal file if not open yet or there is a more recent journal
        if self.current_log != latest_log:
            self.current_log = latest_log
            self.open_journal(latest_log)

        cnt = 0

        while True:
            line = self.log_file.readline()
            # if end of file then break from while True
            if not line:
                break
            else:
                log = loads(line)
                cnt = cnt + 1
                self.parse_line(log)

        logger.debug('read:  ' + str(cnt) + ' ship: ' + str(self.ship))
        return self.ship


def main():
    jn = EDJournal()
    while True:
        sleep(5)
        print("Ship = ", jn.ship_state())


if __name__ == "__main__":
    main()
