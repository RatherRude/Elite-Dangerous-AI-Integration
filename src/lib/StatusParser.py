import json
import time
from datetime import datetime, timedelta
import queue
from sys import platform
import threading
from time import sleep
from .Logger import log

class StatusParser:
    def __init__(self, file_path=None):
        if platform != "win32":
            self.file_path = file_path if file_path else "./linux_ed/Status.json"
        else:
            from .WindowsKnownPaths import get_path, FOLDERID, UserHandle
            self.file_path = file_path if file_path else (get_path(FOLDERID.SavedGames, UserHandle.current) + "\Frontier Developments\Elite Dangerous\Status.json")

        self.current_status = self.get_cleaned_data()
        # self.watch_thread = threading.Thread(target=self._watch_file_thread, daemon=True)
        # self.watch_thread.start()
        # self.status_queue = queue.Queue()
        
    def _watch_file_thread(self):
        backoff = 1
        while True:
            try: 
                self._watch_file()
            except Exception as e:
                log('error', 'An error occurred when reading status file', e)
                sleep(backoff)
                log('debug', 'Attempting to restart status file reader after failure')
                backoff *= 2

    def _watch_file(self):
        """Detects changes in the Status.json file."""
        while True:
            status = self.get_cleaned_data()
            if status != self.current_status:
                self.status_queue.put(status)
                self.current_status = status
            sleep(1)

    def translate_flags(self, flags_value):
        """Translates flags integer to a dictionary of only True flags."""
        all_flags = {
            "Docked": bool(flags_value & 1),
            "Landed": bool(flags_value & 2),
            "Landing Gear Down": bool(flags_value & 4),
            "Shields Up": bool(flags_value & 8),
            "Supercruise": bool(flags_value & 16),
            "FlightAssist Off": bool(flags_value & 32),
            "Hardpoints Deployed": bool(flags_value & 64),
            "In Wing": bool(flags_value & 128),
            "Lights On": bool(flags_value & 256),
            "Cargo Scoop Deployed": bool(flags_value & 512),
            "Silent Running": bool(flags_value & 1024),
            "Scooping Fuel": bool(flags_value & 2048),
            "Srv Handbrake": bool(flags_value & 4096),
            "Srv using Turret view": bool(flags_value & 8192),
            "Srv Turret retracted (close to ship)": bool(flags_value & 16384),
            "Srv DriveAssist": bool(flags_value & 32768),
            "Fsd MassLocked": bool(flags_value & 65536),
            "Fsd Charging": bool(flags_value & 131072),
            "Fsd Cooldown": bool(flags_value & 262144),
            "Low Fuel (< 25%)": bool(flags_value & 524288),
            "Over Heating (> 100%)": bool(flags_value & 1048576),
            "Has Lat Long": bool(flags_value & 2097152),
            "IsInDanger": bool(flags_value & 4194304),
            "Being Interdicted": bool(flags_value & 8388608),
            "In MainShip": bool(flags_value & 16777216),
            "In Fighter": bool(flags_value & 33554432),
            "In SRV": bool(flags_value & 67108864),
            "Hud in Analysis mode": bool(flags_value & 134217728),
            "Night Vision": bool(flags_value & 268435456),
            "Altitude from Average radius": bool(flags_value & 536870912),
            "Fsd Jump": bool(flags_value & 1073741824),
            "Srv HighBeam": bool(flags_value & 2147483648),
        }

        # Return only flags that are True
        true_flags = {key: value for key, value in all_flags.items() if value}
        return true_flags

    def translate_flags2(self, flags2_value):
        """Translates Flags2 integer to a dictionary of only True flags."""
        all_flags2 = {
            "OnFoot": bool(flags2_value & 1),
            "InTaxi": bool(flags2_value & 2),
            "InMulticrew": bool(flags2_value & 4),
            "OnFootInStation": bool(flags2_value & 8),
            "OnFootOnPlanet": bool(flags2_value & 16),
            "AimDownSight": bool(flags2_value & 32),
            "LowOxygen": bool(flags2_value & 64),
            "LowHealth": bool(flags2_value & 128),
            "Cold": bool(flags2_value & 256),
            "Hot": bool(flags2_value & 512),
            "VeryCold": bool(flags2_value & 1024),
            "VeryHot": bool(flags2_value & 2048),
            "Glide Mode": bool(flags2_value & 4096),
            "OnFootInHangar": bool(flags2_value & 8192),
            "OnFootSocialSpace": bool(flags2_value & 16384),
            "OnFootExterior": bool(flags2_value & 32768),
            "BreathableAtmosphere": bool(flags2_value & 65536),
            "Telepresence Multicrew": bool(flags2_value & 131072),
            "Physical Multicrew": bool(flags2_value & 262144),
            "Fsd hyperdrive charging": bool(flags2_value & 524288),
        }

        # Return only flags that are True
        true_flags2 = {key: value for key, value in all_flags2.items() if value}
        return true_flags2

    def transform_pips(self, pips_list):
        """Transforms the pips list to a dictionary and halves each value."""
        return {
            'system': pips_list[0] / 2,
            'engine': pips_list[1] / 2,
            'weapons': pips_list[2] / 2
        }

    def adjust_year(self, timestamp):
        """Increases the year in the timestamp by 1286 years."""
        # Parse the timestamp string into a datetime object
        dt = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")

        # Increase the year by 1286
        dt = dt.replace(year=dt.year + 1286)

        # Format the datetime object back into a string
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    def get_cleaned_data(self):
        """Loads data from the JSON file and returns cleaned data with only the necessary fields."""
        with open(self.file_path, 'r') as file:
            data = json.load(file)

        # Combine flags from Flags and Flags2 into a single dictionary
        combined_flags = {**self.translate_flags(data['Flags'])}

        if 'Flags2' in data:
            combined_flags = {**combined_flags, **self.translate_flags2(data['Flags2'])}

        # Initialize cleaned_data with common fields
        cleaned_data = {
            'status': combined_flags,
            'time': (datetime.now() + timedelta(days=469711)).isoformat()
        }

        # Add optional status flags
        if 'LegalState' in data:
            cleaned_data['legalState'] = data['LegalState']
        if 'Balance' in data:
            cleaned_data['balance'] = data['Balance']
        if 'Pips' in data:
            cleaned_data['pips'] = self.transform_pips(data['Pips'])
        if 'Cargo' in data:
            cleaned_data['cargo'] = data['Cargo']

        return cleaned_data

    # Loads data from the JSON file and returns only GuiFocus field.
    def get_gui_focus(self):
        with open(self.file_path, 'r') as file:
            data = json.load(file)

        return data.get('GuiFocus', 0)

# Usage Example
if __name__ == "__main__":
    while True:
        parser = StatusParser()
        cleaned_data = parser.get_cleaned_data()
        print(json.dumps(cleaned_data, indent=4))
        time.sleep(1)
        print("\n"*10)