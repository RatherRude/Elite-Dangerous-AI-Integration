import json
from datetime import datetime

from WindowsKnownPaths import *
class StatusParser:
    def __init__(self, file_path=get_path(FOLDERID.SavedGames, UserHandle.current) + "\Frontier Developments\Elite Dangerous\status.json"):
        self.file_path = file_path

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

        cleaned_data = {
            'status': self.translate_flags(data['Flags']),
            'pips': self.transform_pips(data['Pips']),
            'cargo': data['Cargo'],
            'legalState': data['LegalState'],
            'balance': data['Balance'],
            'time': self.adjust_year(data['timestamp'])
        }

        return cleaned_data

# Usage Example
if __name__ == "__main__":
    parser = StatusParser()
    cleaned_data = parser.get_cleaned_data()
    print(json.dumps(cleaned_data, indent=4))