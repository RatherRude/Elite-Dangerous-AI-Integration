from datetime import datetime
from json import loads
from os import listdir
from os.path import join, isfile, getmtime
from sys import platform
from time import sleep
from typing import Dict, List

from .EDlogger import logger

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
            'star_class': None,
            'body': None,
            'ship_type': None,
            'location': None,
            'target': None,
            'jumps_remains': 0,
            'dist_jumped': 0,
            'cargo_capacity': 0,
            'extra_events': []
        }
        self.ship_state()  # load up from file

    def get_latest_log(self, path_logs=None):
        """Returns the full path of the latest (most recent) elite log file (journal) from specified path"""
        if platform != "win32":
            return None
        
        import WindowsKnownPaths as winpaths
        if not path_logs:
            path_logs = winpaths.get_path(winpaths.FOLDERID.SavedGames, winpaths.UserHandle.current) + "\Frontier Developments\Elite Dangerous"
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
            if log_event == 'StartJump':
                if log['JumpType'] == 'Hyperspace':
                    self.ship['star_class'] = log['StarClass']

            elif log_event == 'SupercruiseExit':
                self.ship['body'] = log['Body']

            # parse ship type
            elif log_event == 'Loadout':
                self.ship['ship_type'] = log['Ship']
                self.ship['cargo_capacity'] = log['CargoCapacity']

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


            elif log_event == 'MissionCompleted':
                self.ship['mission_completed'] += 1


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

        # print('read:  ' + str(cnt) + ' ship: ' + str(self.ship))
        return self.ship


def main():
    jn = EDJournal()
    while True:
        sleep(5)
        print("Ship = ", jn.ship_state())


if __name__ == "__main__":
    main()
