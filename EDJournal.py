from os import environ, listdir
from os.path import join, isfile, getmtime, abspath
from json import loads
from time import sleep, time
from datetime import datetime

from EDlogger import logger
from WindowsKnownPaths import *

"""
File EDJournal.py  (leveraged the EDAutopilot on github, turned into a 
                   class and enhanced, see https://github.com/skai2/EDAutopilot
                   then leveraged again and enhanced to handle more event types
                   and create the state machine for the Elite Dangerous AI Integration

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

"""                             
TODO: thinking self.ship()[name]  uses the same names as in the journal, so can lookup same construct     
"""


class EDJournal:
    def __init__(self):
        self.log_file = None
        self.current_log = self.get_latest_log()
        self.open_journal(self.current_log)

        self.ship = {
            'disembark': False,
            'shieldsup': True,
            'under_attack': None,
            'fighter_destroyed': False,
            'mission_completed': 0,
            'mission_redirected': 0,
            'status': 'in_space',
            'star_class': None,
            'body': None,
            'no_dock_reason': None,
            'interdicted': False,
            'type': None,
            'fuel_level': None,
            'fuel_capacity': None,
            'fuel_percent': None,
            'is_scooping': False,
            'location': None,
            'target': None,
            'jumps_remains': 0,
            'dist_jumped': 0,
            'time': (datetime.now() - datetime.fromtimestamp(getmtime(self.current_log))).seconds,
            'cockpit_breached': False,
            'committed_crime': None,
            'fighter_launched': False,
            'srv_launched': False,
            'datalink_scan': None,
            'cargo_ejected': False,
            'mission_accepted': None,
            'mission_failed': None,
            'mission_abandoned': None,
            'odyssey': True  # Initialize odyssey state
        }
        self.ship_state()    # load up from file
        self.reset_items()

    # these items do not have respective log entries to clear them.  After initial reading of log file, clear these items
    # also the App will need to reset these to False after detecting they were True    
    def reset_items(self):
        defaultValues = {
            'under_attack' : False,
            'fighter_destroyed' : False,
            'cockpit_breached' : False,
            'committed_crime' : None,
            'datalink_scan' : None,
            'cargo_ejected' : False,
            'mission_accepted' : None,
            'mission_failed' : None,
            'mission_abandoned' : None
        }
        self.ship = {**self.ship, **defaultValues}

    def get_latest_log(self, path_logs=None):
        """Returns the full path of the latest (most recent) elite log file (journal) from specified path"""
        if not path_logs:
            path_logs = get_path(FOLDERID.SavedGames, UserHandle.current) + "\Frontier Developments\Elite Dangerous"
        list_of_logs = [join(path_logs, f) for f in listdir(path_logs) if isfile(join(path_logs, f)) and f.startswith('Journal.')]
        if not list_of_logs:
            return None
        latest_log = max(list_of_logs, key=getmtime)
        return latest_log

    def open_journal(self, log_name):
        # if journal file is open then close it
        if self.log_file is not None:
            self.log_file.close()

        logger.info("Opening new Journal: "+log_name)

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
            if log_event == 'Fileheader':
                self.ship['odyssey'] = True   # hardset to true for ED 4.0 since menus now same for Horizon
                return   # No need to do further processing on this record, should use elif: all the way down

            if log_event == 'ShieldState':
                self.ship['shieldsup'] = log['ShieldsUp']
                return   # No need to do further processing on this record

            if log_event == 'UnderAttack':
                self.ship['under_attack'] = True

            if log_event == 'Embark':
                self.ship['disembark'] = False
                #print('embark')
                #print(self.ship['Disembark'])

            if log_event == 'Disembark':
                self.ship['disembark'] = self.fill_disembark_object(log)
                #print('disembark')
                #print(log)
                #print(self.ship['disembark'])

            if log_event == 'FighterDestroyed':
                self.ship['fighter_destroyed'] = True
                self.ship['fighter_launched'] = False

            if log_event == 'MissionCompleted':
                self.ship['mission_completed'] += 1

            if log_event == 'MissionRedirected':
                self.ship['mission_redirected'] += 1

            if log_event == 'StartJump':
                self.ship['status'] = str('starting_' + log['JumpType']).lower()
                if log['JumpType'] == 'Hyperspace':
                    self.ship['star_class'] = log['StarClass']

            elif log_event == 'SupercruiseEntry' or log_event == 'FSDJump':
                self.ship['status'] = 'in_supercruise'

            elif log_event == "DockingGranted":
                self.ship['status'] = 'dockinggranted'

            elif log_event == "DockingDenied":
                self.ship['status'] = 'dockingdenied'
                self.ship['no_dock_reason'] = log['Reason']

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

            elif log_event == 'Interdicted':
                self.ship['interdicted'] = True

            # parse ship type
            if log_event == 'LoadGame' or log_event == 'Loadout':
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
                self.ship['fuel_percent'] = 10

            # parse scoop
            if log_event == 'FuelScoop' and self.ship['time'] < 10 and self.ship['fuel_percent'] < 100:
                self.ship['is_scooping'] = True
            else:
                self.ship['is_scooping'] = False

            # parse location
            if (log_event == 'Location' or log_event == 'FSDJump') and 'StarSystem' in log:
                self.ship['location'] = log['StarSystem']
        #TODO                if 'StarClass' in log:
        #TODO                    self.ship['star_class'] = log['StarClass']

            # parse target
            if log_event == 'FSDTarget':
                if log['Name'] == self.ship['location']:
                    self.ship['target'] = None
                    self.ship['jumps_remains'] = 0
                else:
                    self.ship['target'] = log['Name']
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
            if log_event == 'ApproachSettlement':
                self.ship['status'] = 'approaching_settlement'

            if log_event == 'Bounty':
                self.ship['bounty'] = log['Reward']

            if log_event == 'CockpitBreached':
                self.ship['cockpit_breached'] = True

            if log_event == 'CommitCrime':
                self.ship['committed_crime'] = log['CrimeType']

            if log_event == 'CrewLaunchFighter' or log_event == 'LaunchFighter':
                self.ship['fighter_launched'] = True

            if log_event == 'DockFighter':
                self.ship['fighter_launched'] = False

            if log_event == 'LaunchSRV':
                self.ship['srv_launched'] = True

            if log_event == 'DockSRV':
                self.ship['srv_launched'] = False

            if log_event == 'Touchdown':
                self.ship['status'] = 'landed'

            if log_event == 'Liftoff':
                self.ship['status'] = 'liftoff'

            if log_event == 'DatalinkScan':
                self.ship['datalink_scan'] = True

            if log_event == 'SelfDestruct':
                self.ship['status'] = 'self_destruct'

            if log_event == 'Died':
                self.ship['status'] = 'destroyed'

            if log_event == 'Resurrect':
                self.ship['status'] = 'resurrected'

            if log_event == 'EjectCargo':
                self.ship['cargo_ejected'] = True

            if log_event == 'Location':
                if log['Docked']:
                    self.ship['status'] = 'in_station'
                else:
                    self.ship['location'] = log['StarSystem']

            if log_event == 'MissionAccepted':
                self.ship['mission_accepted'] = log['MissionID']

            if log_event == 'MissionCompleted':
                self.ship['mission_completed'] += 1

            if log_event == 'MissionFailed':
                self.ship['mission_failed'] = log['MissionID']

            if log_event == 'MissionAbandoned':
                self.ship['mission_abandoned'] = log['MissionID']

            """
            # Travel Events:
            if log_event == 'ApproachBody':
                self.ship['status'] = 'approaching_body'

            if log_event == 'ApproachStar':
                self.ship['status'] = 'approaching_star'

            if log_event == 'HeatWarning':
                self.ship['status'] = 'heat_warning'

            if log_event == 'HeatDamage':
                self.ship['status'] = 'heat_damage'

            if log_event == 'ShieldHealth':
                self.ship['shield_health'] = log['Health']

            if log_event == 'UnderAttack':
                self.ship['under_attack'] = True

            if log_event == 'StartJump':
                self.ship['jumps_remains'] = log['JumpsRemaining']

            if log_event == 'CargoTransfer':
                self.ship['cargo_transfer'] = log['Direction']

            if log_event == 'DockingTimeout':
                self.ship['status'] = 'docking_timeout'

            if log_event == 'DockingRequested':
                self.ship['status'] = 'docking_requested'

            if log_event == 'DockingDenied':
                self.ship['status'] = 'docking_denied'
                self.ship['no_dock_reason'] = log['Reason']

            if log_event == 'DockingGranted':
                self.ship['status'] = 'docking_granted'

            if log_event == 'DockingComplete':
                self.ship['status'] = 'docking_complete'

            if log_event == 'DockingCancelled':
                self.ship['status'] = 'docking_cancelled'

            if log_event == 'MiningRefined':
                self.ship['mining_refined'] = log['Type']

            if log_event == 'USSDrop':
                self.ship['uss_type'] = log['USSType']
                self.ship['uss_scan_stage'] = log['USSType_Localised']

            if log_event == 'AsteroidCracked':
                self.ship['asteroid_cracked'] = log['Body']

            if log_event == 'ProspectedAsteroid':
                self.ship['asteroid_prospected'] = log['Materials']

            if log_event == 'Scan':
                self.ship['scan_complete'] = log['ScanType']

            if log_event == 'ReceiveText':
                self.ship['received_text'] = log['From']
                self.ship['message'] = log['Message']


            # Exploration Events:
            if log_event == 'CodexEntry':
                entry_data = {
                    "timestamp": log['timestamp'],
                    "event": log_event,
                    "EntryID": log['EntryID'],
                    "Name": log['Name'],
                    "Name_Localised": log['Name_Localised'],
                    "SubCategory": log['SubCategory'],
                    "SubCategory_Localised": log['SubCategory_Localised'],
                    "Category": log['Category'],
                    "Category_Localised": log['Category_Localised'],
                    "Region": log['Region'],
                    "Region_Localised": log['Region_Localised'],
                    "System": log['System'],
                    "SystemAddress": log['SystemAddress'],
                    "BodyID": log['BodyID'],
                    "NearestDestination": log.get('NearestDestination', None),
                    "NearestDestination_Localised": log.get('NearestDestination_Localised', None),
                    "IsNewEntry": log.get('IsNewEntry', False),
                    "VoucherAmount": log.get('VoucherAmount', None),
                    "NewTraitsDiscovered": log.get('NewTraitsDiscovered', False),
                    "Traits": log.get('Traits', [])
                }

            if log_event == 'DiscoveryScan':
                discovery_scan_data = {
                    "timestamp": log['timestamp'],
                    "event": log_event,
                    "SystemAddress": log['SystemAddress'],
                    "Bodies": log['Bodies']
                }

                if log_event == 'Scan':
                    scan_type = log['ScanType']
                    if scan_type == 'NavBeacon' or scan_type == 'NavBeaconDetail':
                        scan_data = {
                            "timestamp": log['timestamp'],
                            "event": log_event,
                            "ScanType": scan_type,
                            "BodyName": log['BodyName'],
                            "BodyID": log['BodyID'],
                            "SystemAddress": log['SystemAddress']
                        }
                    else:
                        scan_data = {
                            "timestamp": log['timestamp'],
                            "event": log_event,
                            "ScanType": scan_type,
                            "StarSystem": log['StarSystem'],
                            "SystemAddress": log['SystemAddress'],
                            "BodyName": log['BodyName'],
                            "BodyID": log['BodyID'],
                            "DistanceFromArrivalLS": log['DistanceFromArrivalLS'],
                            "StarType": log.get('StarType', None),
                            "Subclass": log.get('Subclass', None),
                            "StellarMass": log.get('StellarMass', None),
                            "Radius": log.get('Radius', None),
                            "AbsoluteMagnitude": log.get('AbsoluteMagnitude', None),
                            "RotationPeriod": log.get('RotationPeriod', None),
                            "SurfaceTemperature": log.get('SurfaceTemperature', None),
                            "Luminosity": log.get('Luminosity', None),
                            "Age_MY": log.get('Age_MY', None),
                            "Rings": log.get('Rings', []),
                            "WasDiscovered": log.get('WasDiscovered', None),
                            "WasMapped": log.get('WasMapped', None),
                            "Parents": log.get('Parents', None),
                            "TidalLock": log.get('TidalLock', None),
                            "TerraformState": log.get('TerraformState', None),
                            "PlanetClass": log.get('PlanetClass', None),
                            "Atmosphere": log.get('Atmosphere', None),
                            "AtmosphereType": log.get('AtmosphereType', None),
                            "AtmosphereComposition": log.get('AtmosphereComposition', []),
                            "Volcanism": log.get('Volcanism', None),
                            "SurfaceGravity": log.get('SurfaceGravity', None),
                            "SurfaceTemperature": log.get('SurfaceTemperature', None),
                            "SurfacePressure": log.get('SurfacePressure', None),
                            "Landable": log.get('Landable', None),
                            "Materials": log.get('Materials', []),
                            "Composition": log.get('Composition', {}),
                            "SemiMajorAxis": log.get('SemiMajorAxis', None),
                            "Eccentricity": log.get('Eccentricity', None),
                            "OrbitalInclination": log.get('OrbitalInclination', None),
                            "Periapsis": log.get('Periapsis', None),
                            "OrbitalPeriod": log.get('OrbitalPeriod', None),
                            "RotationPeriod": log.get('RotationPeriod', None),
                            "AxialTilt": log.get('AxialTilt', None),
                            "ReserveLevel": log.get('ReserveLevel', None)
                        }

            #Trade Events:
             if log_event == 'Trade':
                 trade_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "MarketID": log['MarketID'],
                     "Type": log['Type'],
                     "Count": log['Count'],
                     "BuyPrice": log['BuyPrice'],
                     "TotalCost": log['TotalCost']
                 }

             if log_event == 'AsteroidCracked':
                 asteroid_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Body": log['Body']
                 }

             if log_event == 'BuyTradeData':
                 buy_trade_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "System": log['System'],
                     "Cost": log['Cost']
                 }

             if log_event == 'CollectCargo':
                 collect_cargo_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Type": log['Type'],
                     "Stolen": log['Stolen'],
                     "MissionID": log.get('MissionID', None)
                 }

             if log_event == 'EjectCargo':
                 eject_cargo_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Type": log['Type'],
                     "Count": log['Count'],
                     "Abandoned": log['Abandoned'],
                     "PowerplayOrigin": log.get('PowerplayOrigin', None),
                     "MissionID": log.get('MissionID', None)
                 }

             if log_event == 'MarketBuy':
                 market_buy_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "MarketID": log['MarketID'],
                     "Type": log['Type'],
                     "Count": log['Count'],
                     "BuyPrice": log['BuyPrice'],
                     "TotalCost": log['TotalCost']
                 }

             if log_event == 'MarketSell':
                 market_sell_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "MarketID": log['MarketID'],
                     "Type": log['Type'],
                     "Count": log['Count'],
                     "SellPrice": log['SellPrice'],
                     "TotalSale": log['TotalSale'],
                     "AvgPricePaid": log['AvgPricePaid'],
                     "IllegalGoods": log.get('IllegalGoods', None),
                     "StolenGoods": log.get('StolenGoods', None),
                     "BlackMarket": log.get('BlackMarket', None)
                 }

             if log_event == 'MiningRefined':
                 mining_refined_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Type": log['Type']
                 }

             # Station Services Events:
             if log_event == 'StationServices':
                 station_services_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "StationName": log['StationName'],
                     "StationType": log['StationType']
                 }

             if log_event == 'BuyAmmo':
                 buy_ammo_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Cost": log['Cost']
                 }

             if log_event == 'BuyDrones':
                 buy_drones_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Type": log['Type'],
                     "Count": log['Count'],
                     "BuyPrice": log['BuyPrice'],
                     "TotalCost": log['TotalCost']
                 }

             if log_event == 'CargoDepot':
                 cargo_depot_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "MissionID": log['MissionID'],
                     "UpdateType": log['UpdateType'],
                     "CargoType": log['CargoType'],
                     "Count": log['Count'],
                     "StartMarketID": log['StartMarketID'],
                     "EndMarketID": log['EndMarketID'],
                     "ItemsCollected": log['ItemsCollected'],
                     "ItemsDelivered": log['ItemsDelivered'],
                     "TotalItemsToDeliver": log['TotalItemsToDeliver'],
                     "Progress": log['Progress']
                 }

             if log_event == 'CommunityGoal':
                 community_goal_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "CurrentGoals": log['CurrentGoals']
                 }

             if log_event == 'CommunityGoalDiscard':
                 community_goal_discard_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "CGID": log['CGID'],
                     "Name": log['Name'],
                     "System": log['System']
                 }

             if log_event == 'CommunityGoalJoin':
                 community_goal_join_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "CGID": log['CGID'],
                     "Name": log['Name'],
                     "System": log['System']
                 }

             if log_event == 'CommunityGoalReward':
                 community_goal_reward_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "CGID": log['CGID'],
                     "Name": log['Name'],
                     "System": log['System'],
                     "Reward": log['Reward']
                 }

             if log_event == 'CrewAssign':
                 crew_assign_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Name": log['Name'],
                     "CrewID": log['CrewID'],
                     "Role": log['Role']
                 }

             if log_event == 'CrewFire':
                 crew_fire_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Name": log['Name'],
                     "CrewID": log['CrewID']
                 }

             if log_event == 'CrewHire':
                 crew_hire_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Name": log['Name'],
                     "CrewID": log['CrewID'],
                     "Faction": log['Faction'],
                     "Cost": log['Cost'],
                     "CombatRank": log['CombatRank']
                 }

             if log_event == 'EngineerContribution':
                 engineer_contribution_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Engineer": log['Engineer'],
                     "EngineerID": log['EngineerID'],
                     "Type": log['Type'],
                     "Commodity": log.get('Commodity', None),
                     "Material": log.get('Material', None),
                     "Faction": log.get('Faction', None),
                     "Quantity": log['Quantity'],
                     "TotalQuantity": log['TotalQuantity']
                 }

             if log_event == 'EngineerCraft':
                 engineer_craft_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Engineer": log['Engineer'],
                     "EngineerID": log['EngineerID'],
                     "BlueprintName": log['BlueprintName'],
                     "BlueprintID": log['BlueprintID'],
                     "Level": log['Level'],
                     "Quality": log['Quality'],
                     "ApplyExperimentalEffect": log.get('ApplyExperimentalEffect', None),
                     "Ingredients": log.get('Ingredients', None),
                     "Modifiers": log['Modifiers']
                 }

             if log_event == 'EngineerLegacyConvert':
                 engineer_legacy_convert_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Engineer": log['Engineer'],
                     "EngineerID": log['EngineerID'],
                     "BlueprintName": log['BlueprintName'],
                     "BlueprintID": log['BlueprintID'],
                     "Level": log['Level'],
                     "Quality": log['Quality'],
                     "IsPreview": log['IsPreview']
                 }

             if log_event == 'EngineerProgress':
                 if 'Engineers' in log:
                     engineer_progress_data = {
                         "timestamp": log['timestamp'],
                         "event": log_event,
                         "Engineers": log['Engineers']
                     }
                 else:
                     engineer_progress_data = {
                         "timestamp": log['timestamp'],
                         "event": log_event,
                         "Engineer": log['Engineer'],
                         "EngineerID": log['EngineerID'],
                         "Rank": log['Rank'],
                         "Progress": log['Progress'],
                         "RankProgress": log['RankProgress']
                     }

             if log_event == 'FetchRemoteModule':
                 fetch_remote_module_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "StorageSlot": log['StorageSlot'],
                     "StoredItem": log['StoredItem'],
                     "ServerId": log['ServerId'],
                     "TransferCost": log['TransferCost'],
                     "Ship": log['Ship'],
                     "ShipId": log['ShipId'],
                     "TransferTime": log['TransferTime']
                 }

             if log_event == 'Market':
                 market_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "MarketID": log['MarketID'],
                     "StationName": log['StationName'],
                     "StarSystem": log['StarSystem']
                 }

             if log_event == 'MassModuleStore':
                 mass_module_store_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "MarketID": log['MarketID'],
                     "Ship": log['Ship'],
                     "ShipId": log['ShipId'],
                     "Items": log['Items']
                 }

             if log_event == 'MaterialTrade':
                 material_trade_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "MarketID": log['MarketID'],
                     "TraderType": log['TraderType'],
                     "Paid": {
                         "Material": log['Paid']['Material'],
                         "Category": log['Paid']['Category'],
                         "Quantity": log['Paid']['Quantity']
                     },
                     "Received": {
                         "Material": log['Received']['Material'],
                         "Quantity": log['Received']['Quantity']
                     }
                 }

             if log_event == 'MissionAbandoned':
                 mission_abandoned_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Name": log['Name'],
                     "MissionID": log['MissionID'],
                     "Fine": log.get('Fine', None)
                 }

             if log_event == 'MissionAccepted':
                 mission_accepted_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Faction": log['Faction'],
                     "Name": log['Name'],
                     "LocalisedName": log.get('LocalisedName', None),
                     "Commodity": log.get('Commodity', None),
                     "Count": log.get('Count', None),
                     "TargetFaction": log.get('TargetFaction', None),
                     "DestinationSystem": log.get('DestinationSystem', None),
                     "DestinationStation": log.get('DestinationStation', None),
                     "Expiry": log.get('Expiry', None),
                     "Wing": log.get('Wing', False),
                     "Influence": log.get('Influence', None),
                     "Reputation": log.get('Reputation', None),
                     "Reward": log.get('Reward', None),
                     "MissionID": log['MissionID']
                 }

             if log_event == 'MassModuleStore':
                 items = []
                 for item in log['Items']:
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
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "MarketID": log['MarketID'],
                     "Ship": log['Ship'],
                     "ShipID": log['ShipID'],
                     "Items": items
                 }

             if log_event == 'MaterialTrade':
                 material_trade_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "MarketID": log['MarketID'],
                     "TraderType": log['TraderType'],
                     "Paid": {
                         "Material": log['Paid']['Material'],
                         "Category": log['Paid']['Category'],
                         "Quantity": log['Paid']['Quantity']
                     },
                     "Received": {
                         "Material": log['Received']['Material'],
                         "Quantity": log['Received']['Quantity']
                     }
                 }

             if log_event == 'MissionAbandoned':
                 mission_abandoned_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Name": log['Name'],
                     "MissionID": log['MissionID'],
                     "Fine": log.get('Fine', None)
                 }

             if log_event == 'MissionCompleted':
                 mission_completed_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Name": log['Name'],
                     "Faction": log['Faction'],
                     "MissionID": log['MissionID'],
                     "Commodity": log.get('Commodity', None),
                     "Count": log.get('Count', None),
                     "Target": log.get('Target', None),
                     "TargetType": log.get('TargetType', None),
                     "TargetFaction": log.get('TargetFaction', None),
                     "DestinationSystem": log.get('DestinationSystem', None),
                     "DestinationStation": log.get('DestinationStation', None),
                     "DestinationSettlement": log.get('DestinationSettlement', None),
                     "Reward": log['Reward'],
                     "Donation": log.get('Donation', None),
                     "Donated": log.get('Donated', None),
                     "PermitsAwarded": log.get('PermitsAwarded', []),
                     "CommodityReward": log.get('CommodityReward', []),
                     "MaterialsReward": log.get('MaterialsReward', []),
                     "FactionEffects": log.get('FactionEffects', [])
                 }

             if log_event == 'MissionFailed':
                 mission_failed_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Name": log['Name'],
                     "MissionID": log['MissionID'],
                     "Fine": log.get('Fine', None)
                 }

             if log_event == 'MissionRedirected':
                 mission_redirected_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "MissionID": log['MissionID'],
                     "Name": log['Name'],
                     "NewDestinationStation": log['NewDestinationStation'],
                     "OldDestinationStation": log['OldDestinationStation'],
                     "NewDestinationSystem": log['NewDestinationSystem'],
                     "OldDestinationSystem": log['OldDestinationSystem']
                 }

             if log_event == 'ModuleBuy':
                 module_buy_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "MarketID": log['MarketID'],
                     "Slot": log['Slot'],
                     "BuyItem": log['BuyItem'],
                     "BuyPrice": log['BuyPrice'],
                     "Ship": log['Ship'],
                     "ShipID": log['ShipID'],
                     "StoredItem": log.get('StoredItem', None),
                     "StoredItem_Localised": log.get('StoredItem_Localised', None),
                     "SellItem": log.get('SellItem', None),
                     "SellPrice": log.get('SellPrice', None)
                 }

             if log_event == 'ModuleRetrieve':
                 module_retrieve_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "MarketID": log['MarketID'],
                     "Slot": log['Slot'],
                     "Ship": log['Ship'],
                     "ShipID": log['ShipID'],
                     "RetrievedItem": log['RetrievedItem'],
                     "Hot": log.get('Hot', False),
                     "EngineerModifications": log.get('EngineerModifications', None),
                     "Level": log.get('Level', None),
                     "Quality": log.get('Quality', None),
                     "SwapOutItem": log.get('SwapOutItem', None),
                     "Cost": log.get('Cost', None)
                 }

             if log_event == 'ModuleSell':
                 module_sell_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "MarketID": log['MarketID'],
                     "Slot": log['Slot'],
                     "SellItem": log['SellItem'],
                     "SellPrice": log['SellPrice'],
                     "Ship": log['Ship'],
                     "ShipID": log['ShipID']
                 }

             if log_event == 'ModuleSellRemote':
                 module_sell_remote_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "StorageSlot": log['StorageSlot'],
                     "SellItem": log['SellItem'],
                     "ServerId": log['ServerId'],
                     "SellPrice": log['SellPrice'],
                     "Ship": log['Ship'],
                     "ShipId": log['ShipId']
                 }

             if log_event == 'ModuleStore':
                 module_store_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "MarketID": log['MarketID'],
                     "Slot": log['Slot'],
                     "Ship": log['Ship'],
                     "ShipID": log['ShipID'],
                     "StoredItem": log['StoredItem'],
                     "StoredItem_Localised": log.get('StoredItem_Localised', None),
                     "Hot": log['Hot'],
                     "EngineerModifications": log.get('EngineerModifications', None),
                     "Level": log.get('Level', None),
                     "Quality": log.get('Quality', None),
                     "ReplacementItem": log.get('ReplacementItem', None),
                     "Cost": log.get('Cost', None)
                 }

             if log_event == 'ModuleSwap':
                 module_swap_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "MarketID": log['MarketID'],
                     "FromSlot": log['FromSlot'],
                     "ToSlot": log['ToSlot'],
                     "FromItem": log['FromItem'],
                     "ToItem": log['ToItem'],
                     "Ship": log['Ship'],
                     "ShipID": log['ShipID']
                 }

             if log_event == 'Outfitting':
                 outfitting_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "MarketID": log['MarketID'],
                     "StationName": log['StationName'],
                     "StarSystem": log['StarSystem'],
                     "Horizons": log.get('Horizons', False),
                     "Items": log.get('Items', [])
                 }

             if log_event == 'PayBounties':
                 pay_bounties_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Amount": log['Amount'],
                     "BrokerPercentage": log.get('BrokerPercentage', None),
                     "AllFines": log['AllFines'],
                     "Faction": log['Faction'],
                     "ShipID": log['ShipID']
                 }

             if log_event == 'PayFines':
                 pay_fines_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Amount": log['Amount'],
                     "BrokerPercentage": log.get('BrokerPercentage', None),
                     "AllFines": log['AllFines'],
                     "Faction": log.get('Faction', None),
                     "ShipID": log['ShipID']
                 }

             if log_event == 'PayLegacyFines':
                 pay_legacy_fines_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Amount": log['Amount'],
                     "BrokerPercentage": log.get('BrokerPercentage', None)
                 }

             if log_event == 'RedeemVoucher':
                 redeem_voucher_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Type": log['Type'],
                     "Amount": log['Amount'],
                     "Factions": log.get('Factions', []),
                     "Faction": log.get('Faction', None),
                     "BrokerPercentage": log.get('BrokerPercentage', None)
                 }

             if log_event == 'RefuelAll':
                 refuel_all_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Cost": log['Cost'],
                     "Amount": log['Amount']
                 }

             if log_event == 'RefuelPartial':
                 refuel_partial_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Cost": log['Cost'],
                     "Amount": log['Amount']
                 }

             if log_event == 'Repair':
                 repair_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Item": log['Item'],
                     "Cost": log['Cost']
                 }

             if log_event == 'RepairAll':
                 repair_all_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Items": log.get('Items', []),
                     "Cost": log['Cost']
                 }

             if log_event == 'RestockVehicle':
                 restock_vehicle_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Type": log['Type'],
                     "Loadout": log['Loadout'],
                     "Cost": log['Cost'],
                     "Count": log['Count']
                 }

             	if log_event == 'ScientificResearch':
                 scientific_research_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "MarketID": log['MarketID'],
                     "Name": log['Name'],
                     "Category": log['Category'],
                     "Count": log['Count']
                 }

             	if log_event == 'Shipyard':
                 shipyard_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "MarketID": log['MarketID'],
                     "StationName": log['StationName'],
                     "StarSystem": log['StarSystem'],
                     "Horizons": log['Horizons'],
                     "AllowCobraMkIV": log['AllowCobraMkIV'],
                     "PriceList": log['PriceList']
                 }

             if log_event == 'ShipyardBuy':
                 shipyard_buy_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "MarketID": log['MarketID'],
                     "ShipType": log['ShipType'],
                     "ShipPrice": log['ShipPrice'],
                     "StoreOldShip": log.get('StoreOldShip'),  # Optional
                     "StoreShipID": log.get('StoreShipID')    # Optional
                 }

             if log_event == 'ShipyardNew':
                 shipyard_new_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "ShipType": log['ShipType'],
                     "NewShipID": log['NewShipID']
                 }

             if log_event == 'ShipyardSell':
                 shipyard_sell_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "MarketID": log['MarketID'],
                     "ShipType": log['ShipType'],
                     "SellShipID": log['SellShipID'],
                     "ShipPrice": log['ShipPrice'],
                     "System": log.get('System')  # Optional
                 }

             if log_event == 'ShipyardTransfer':
                 shipyard_transfer_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "ShipType": log['ShipType'],
                     "ShipID": log['ShipID'],
                     "System": log['System'],
                     "ShipMarketID": log['ShipMarketID'],
                     "Distance": log['Distance'],
                     "TransferPrice": log['TransferPrice'],
                     "TransferTime": log['TransferTime']
                 }

             if log_event == 'ShipyardSwap':
                 shipyard_swap_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "MarketID": log['MarketID'],
                     "ShipType": log['ShipType'],
                     "ShipID": log['ShipID'],
                     "StoreOldShip": log.get('StoreOldShip'),  # Optional
                     "StoreShipID": log.get('StoreShipID'),    # Optional
                     "SellOldShip": log.get('SellOldShip'),    # Optional
                     "SellShipID": log.get('SellShipID')       # Optional
                 }

             if log_event == 'StoredModules':
                 stored_modules_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "MarketID": log['MarketID'],
                     "Items": log['Items']
                 }

             if log_event == 'StoredShips':
                 stored_ships_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "StationName": log['StationName'],
                     "StarSystem": log['StarSystem'],
                     "ShipsHere": log['ShipsHere'],
                     "ShipsRemote": log['ShipsRemote'],
                     "InTransit": log.get('InTransit', False)  # Optional
                 }

             if log_event == 'TechnologyBroker':
                 technology_broker_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "BrokerType": log['BrokerType'],
                     "MarketID": log['MarketID'],
                     "ItemsUnlocked": log['ItemsUnlocked'],
                     "Commodities": log.get('Commodities', []),
                     "Materials": log.get('Materials', [])
                 }

             if log_event == 'ClearImpound':
                 clear_impound_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "ShipType": log['ShipType'],
                     "ShipID": log['ShipID'],
                     "ShipMarketID": log['ShipMarketID'],
                     "MarketID": log['MarketID']
                 }

             # Fleet Carrier Events:
             if log_event == 'CarrierJump':
                 carrier_jump_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Docked": log['Docked'],
                     "StationName": log['StationName'],
                     "StationType": log['StationType'],
                     "MarketID": log['MarketID'],
                     "StationFaction": log['StationFaction'],
                     "StationGovernment": log['StationGovernment'],
                     "StationGovernment_Localised": log['StationGovernment_Localised'],
                     "StationServices": log['StationServices'],
                     "StationEconomy": log['StationEconomy'],
                     "StationEconomy_Localised": log['StationEconomy_Localised'],
                     "StationEconomies": log['StationEconomies'],
                     "StarSystem": log['StarSystem'],
                     "SystemAddress": log['SystemAddress'],
                     "StarPos": log['StarPos'],
                     "SystemAllegiance": log['SystemAllegiance'],
                     "SystemEconomy": log['SystemEconomy'],
                     "SystemEconomy_Localised": log['SystemEconomy_Localised'],
                     "SystemSecondEconomy": log['SystemSecondEconomy'],
                     "SystemSecondEconomy_Localised": log['SystemSecondEconomy_Localised'],
                     "SystemGovernment": log['SystemGovernment'],
                     "SystemGovernment_Localised": log['SystemGovernment_Localised'],
                     "SystemSecurity": log['SystemSecurity'],
                     "SystemSecurity_Localised": log['SystemSecurity_Localised'],
                     "Population": log['Population'],
                     "Body": log['Body'],
                     "BodyID": log['BodyID'],
                     "BodyType": log['BodyType'],
                     "SystemFaction": log['SystemFaction']
                 }

             if log_event == 'CarrierBuy':
                 carrier_buy_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "CarrierID": log['CarrierID'],
                     "BoughtAtMarket": log['BoughtAtMarket'],
                     "Location": log['Location'],
                     "Price": log['Price'],
                     "Variant": log['Variant'],
                     "Callsign": log['Callsign']
                 }

             if log_event == 'CarrierStats':
                 carrier_stats_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "CarrierID": log['CarrierID'],
                     "Callsign": log['Callsign'],
                     "Name": log['Name'],
                     "DockingAccess": log['DockingAccess'],
                     "AllowNotorious": log['AllowNotorious'],
                     "FuelLevel": log['FuelLevel'],
                     "JumpRangeCurr": log['JumpRangeCurr'],
                     "JumpRangeMax": log['JumpRangeMax'],
                     "PendingDecommission": log['PendingDecommission'],
                     "SpaceUsage": log['SpaceUsage'],
                     "Finance": log['Finance'],
                     "Crew": log['Crew'],
                     "ShipPacks": log['ShipPacks'],
                     "ModulePacks": log['ModulePacks']
                 }

             if log_event == 'CarrierJumpRequest':
                 carrier_jump_request_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "CarrierID": log['CarrierID'],
                     "SystemName": log['SystemName'],
                     "SystemID": log['SystemAddress'],
                     "Body": log['Body'],
                     "BodyID": log['BodyID'],
                     "DepartureTime": log['DepartureTime']
                 }

             if log_event == 'CarrierDecommission':
                 carrier_decommission_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "CarrierID": log['CarrierID'],
                     "ScrapRefund": log['ScrapRefund'],
                     "ScrapTime": log['ScrapTime']
                 }

             if log_event == 'CarrierCancelDecommission':
                 carrier_cancel_decommission_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "CarrierID": log['CarrierID']
                 }

             if log_event == 'CarrierBankTransfer':
                 carrier_bank_transfer_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "CarrierID": log['CarrierID'],
                     "Deposit": log['Deposit'],
                     "PlayerBalance": log['PlayerBalance'],
                     "CarrierBalance": log['CarrierBalance']
                 }

             if log_event == 'CarrierDepositFuel':
                 carrier_deposit_fuel_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "CarrierID": log['CarrierID'],
                     "Amount": log['Amount'],
                     "Total": log['Total']
                 }

             if log_event == 'CarrierCrewServices':
                 carrier_crew_services_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "CarrierID": log['CarrierID'],
                     "Operation": log['Operation'],
                     "CrewRole": log['CrewRole'],
                     "CrewName": log['CrewName']
                 }

             if log_event == 'CarrierFinance':
                 carrier_finance_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "CarrierID": log['CarrierID'],
                     "TaxRate": log['TaxRate'],
                     "CarrierBalance": log['CarrierBalance'],
                     "ReserveBalance": log['ReserveBalance'],
                     "AvailableBalance": log['AvailableBalance'],
                     "ReservePercent": log['ReservePercent']
                 }

             if log_event == 'CarrierShipPack':
                 carrier_ship_pack_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "CarrierID": log['CarrierID'],
                     "Operation": log['Operation'],
                     "PackTheme": log['PackTheme'],
                     "PackTier": log['PackTier'],
                     "Cost": log['Cost']
                 }

             if log_event == 'CarrierModulePack':
                 carrier_module_pack_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "CarrierID": log['CarrierID'],
                     "Operation": log['Operation'],
                     "PackTheme": log['PackTheme'],
                     "PackTier": log['PackTier'],
                     "Cost": log['Cost']
                 }

             if log_event == 'CarrierTradeOrder':
                 carrier_trade_order_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "CarrierID": log['CarrierID'],
                     "BlackMarket": log['BlackMarket'],
                     "Commodity": log['Commodity'],
                     "Commodity_Localised": log['Commodity_Localised'],
                     "PurchaseOrder": log.get('PurchaseOrder', None),
                     "SaleOrder": log.get('SaleOrder', None),
                     "CancelTrade": log.get('CancelTrade', False),
                     "Price": log['Price']
                 }

             if log_event == 'CarrierDockingPermission':
                 carrier_docking_permission_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "CarrierID": log['CarrierID'],
                     "DockingAccess": log['DockingAccess'],
                     "AllowNotorious": log['AllowNotorious']
                 }

             if log_event == 'CarrierNameChanged':
                 carrier_name_changed_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "CarrierID": log['CarrierID'],
                     "Callsign": log['Callsign'],
                     "Name": log['Name']
                 }

             if log_event == 'CarrierJumpCancelled':
                 carrier_jump_cancelled_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "CarrierID": log['CarrierID']
                 }

             #Odyssey Events
             if log_event == 'Backpack':
                 backpack_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Items": log['Items'],
                     "Components": log['Components'],
                     "Consumables": log['Consumables'],
                     "Data": log['Data']
                 }

             if log_event == 'BackpackChange':
                 backpack_change_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Added": log.get('Added', []),
                     "Removed": log.get('Removed', [])
                 }

             if log_event == 'BookDropship':
                 book_dropship_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "StarSystem": log['StarSystem'],
                     "SystemAddress": log['SystemAddress'],
                     "Body": log['Body'],
                     "BodyID": log['BodyID']
                 }

             if log_event == 'BookTaxi':
                 book_taxi_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Cost": log['Cost'],
                     "DestinationSystem": log['DestinationSystem'],
                     "DestinationLocation": log['DestinationLocation'],
                     "Retreat": log['Retreat']
                 }

             if log_event == 'BuyMicroResources':
                 buy_micro_resources_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "TotalCount": log['TotalCount'],
                     "Price": log['Price'],
                     "MarketID": log['MarketID'],
                     "MicroResources": log['MicroResources']
                 }

             if log_event == 'BuySuit':
                 buy_suit_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Name": log['Name'],
                     "Price": log['Price'],
                     "SuitID": log['SuitID'],
                     "SuitMods": log.get('SuitMods', [])
                 }

             if log_event == 'BuyWeapon':
                 buy_weapon_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Name": log['Name'],
                     "Price": log['Price'],
                     "SuitModuleID": log['SuitModuleID'],
                     "Class": log['Class'],
                     "WeaponMods": log.get('WeaponMods', [])
                 }

             if log_event == 'CancelDropship':
                 cancel_dropship_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "StarSystem": log['StarSystem'],
                     "SystemAddress": log['SystemAddress'],
                     "Body": log['Body'],
                     "BodyID": log['BodyID']
                 }

             if log_event == 'CancelTaxi':
                 cancel_taxi_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Refund": log['Refund']
                 }

             if log_event == 'CollectItems':
                 collect_items_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Name": log['Name'],
                     "Type": log['Type'],
                     "OwnerID": log['OwnerID'],
                     "Count": log['Count'],
                     "Stolen": log['Stolen']
                 }

             if log_event == 'CreateSuitLoadout':
                 create_suit_loadout_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "SuitID": log['SuitID'],
                     "SuitName": log['SuitName'],
                     "SuitMods": log.get('SuitMods', []),
                     "LoadoutID": log['LoadoutID'],
                     "LoadoutName": log['LoadoutName'],
                     "Modules": log['Modules']
                 }

             if log_event == 'DeleteSuitLoadout':
                 delete_suit_loadout_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "SuitID": log['SuitID'],
                     "SuitName": log['SuitName'],
                     "LoadoutID": log['LoadoutID'],
                     "LoadoutName": log['LoadoutName']
                 }

             if log_event == 'Disembark':
                 disembark_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "SRV": log['SRV'],
                     "Taxi": log['Taxi'],
                     "Multicrew": log['Multicrew'],
                     "ID": log['ID'],
                     "StarSystem": log['StarSystem'],
                     "SystemAddress": log['SystemAddress'],
                     "Body": log['Body'],
                     "BodyID": log['BodyID'],
                     "OnStation": log['OnStation'],
                     "OnPlanet": log['OnPlanet'],
                     "StationName": log.get('StationName', None),
                     "StationType": log['StationType'],
                     "MarketID": log['MarketID']
                 }

             if log_event == 'DropItems':
                 drop_items_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Name": log['Name'],
                     "Type": log['Type'],
                     "OwnerID": log['OwnerID'],
                     "MissionID": log.get('MissionID', None),
                     "Count": log['Count']
                 }

             if log_event == 'DropShipDeploy':
                 dropship_deploy_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "StarSystem": log['StarSystem'],
                     "SystemAddress": log['SystemAddress'],
                     "Body": log['Body'],
                     "BodyID": log['BodyID'],
                     "OnStation": log['OnStation'],
                     "OnPlanet": log['OnPlanet']
                 }

             if log_event == 'Embark':
                 embark_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "SRV": log['SRV'],
                     "Taxi": log['Taxi'],
                     "Multicrew": log['Multicrew'],
                     "ID": log['ID'],
                     "StarSystem": log['StarSystem'],
                     "SystemAddress": log['SystemAddress'],
                     "Body": log['Body'],
                     "BodyID": log['BodyID'],
                     "OnStation": log['OnStation'],
                     "OnPlanet": log['OnPlanet'],
                     "StationName": log.get('StationName', None),
                     "StationType": log['StationType'],
                     "MarketID": log['MarketID']
                 }

             if log_event == 'FCMaterials':
                 fc_materials_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "MarketID": log['MarketID'],
                     "CarrierName": log['CarrierName'],
                     "CarrierID": log['CarrierID'],
                     "Items": log['Items']
                 }

             if log_event == 'LoadoutEquipModule':
                 loadout_equip_module_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "SuitID": log['SuitID'],
                     "SuitName": log['SuitName'],
                     "SlotName": log['SlotName'],
                     "LoadoutID": log['LoadoutID'],
                     "LoadoutName": log['LoadoutName'],
                     "ModuleName": log['ModuleName'],
                     "SuitModuleID": log['SuitModuleID'],
                     "Class": log['Class'],
                     "WeaponMods": log.get('WeaponMods', [])
                 }

             if log_event == 'LoadoutRemoveModule':
                 loadout_remove_module_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "SuitID": log['SuitID'],
                     "SuitName": log['SuitName'],
                     "SlotName": log['SlotName'],
                     "LoadoutID": log['LoadoutID'],
                     "LoadoutName": log['LoadoutName'],
                     "ModuleName": log['ModuleName'],
                     "SuitModuleID": log['SuitModuleID'],
                     "Class": log['Class'],
                     "WeaponMods": log.get('WeaponMods', [])
                 }

             if log_event == 'RenameSuitLoadout':
                 rename_suit_loadout_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "SuitID": log['SuitID'],
                     "SuitName": log['SuitName'],
                     "LoadoutID": log['LoadoutID'],
                     "Loadoutname": log['Loadoutname']
                 }

             if log_event == 'ScanOrganic':
                 scan_organic_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "ScanType": log['ScanType'],
                     "Genus": log['Genus'],
                     "Genus_Localised": log['Genus_Localised'],
                     "Species": log['Species'],
                     "Species_Localised": log['Species_Localised'],
                     "Variant": log['Variant'],
                     "Variant_Localised": log['Variant_Localised'],
                     "SystemAddress": log['SystemAddress'],
                     "Body": log['Body']
                 }

             if log_event == 'SellMicroResources':
                 sell_micro_resources_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "MicroResources": log['MicroResources'],
                     "Price": log['Price'],
                     "MarketID": log['MarketID']
                 }

             if log_event == 'SellOrganicData':
                 sell_organic_data_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "MarketID": log['MarketID'],
                     "BioData": log['BioData']
                 }

             if log_event == 'SellWeapon':
                 sell_weapon_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Name": log['Name'],
                     "Name_Localised": log.get('Name_Localised', None),
                     "SuitModuleID": log['SuitModuleID'],
                     "Class": log['Class'],
                     "WeaponMods": log.get('WeaponMods', [])
                 }

             if log_event == 'ShipLocker':
                 ship_locker_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Items": log['Items'],
                     "Components": log['Components'],
                     "Consumables": log['Consumables'],
                     "Data": log['Data']
                 }

             if log_event == 'SwitchSuitLoadout':
                 switch_suit_loadout_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "SuitID": log['SuitID'],
                     "SuitName": log['SuitName'],
                     "SuitMods": log.get('SuitMods', []),
                     "LoadoutID": log['LoadoutID'],
                     "LoadoutName": log['LoadoutName'],
                     "Modules": log['Modules']
                 }

             if log_event == 'TransferMicroResources':
                 transfer_micro_resources_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Transfers": log['Transfers']
                 }

             if log_event == 'TradeMicroResources':
                 trade_micro_resources_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Offered": log['Offered'],
                     "Received": log['Received'],
                     "Count": log['Count'],
                     "MarketID": log['MarketID']
                 }

             if log_event == 'UpgradeSuit':
                 upgrade_suit_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Name": log['Name'],
                     "Name_Localised": log.get('Name_Localised', None),
                     "SuitID": log['SuitID'],
                     "Class": log['Class'],
                     "Cost": log['Cost'],
                     "Resources": log['Resources']
                 }

             if log_event == 'UpgradeWeapon':
                 upgrade_weapon_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Name": log['Name'],
                     "Name_Localised": log.get('Name_Localised', None),
                     "SuitModuleID": log['SuitModuleID'],
                     "Class": log['Class'],
                     "Cost": log['Cost'],
                     "Resources": log['Resources']
                 }

             if log_event == 'UseConsumable':
                 use_consumable_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Name": log['Name'],
                     "Type": log['Type']
                 }

             # Other Events:
             if log_event == 'AfmuRepairs':
                 afmu_repairs_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Module": log['Module'],
                     "Module_Localised": log.get('Module_Localised', None),
                     "FullyRepaired": log['FullyRepaired'],
                     "Health": log['Health']
                 }

             if log_event == 'ApproachSettlement':
                 approach_settlement_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Name": log['Name'],
                     "MarketID": log['MarketID'],
                     "Latitude": log['Latitude'],
                     "Longitude": log['Longitude'],
                     "SystemAddress": log['SystemAddress'],
                     "BodyID": log['BodyID'],
                     "BodyName": log['BodyName']
                 }

             if log_event == 'ChangeCrewRole':
                 change_crew_role_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Role": log['Role'],
                     "Telepresence": log['Telepresence']
                 }

             if log_event == 'CockpitBreached':
                 cockpit_breached_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event
                 }

             if log_event == 'CommitCrime':
                 commit_crime_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "CrimeType": log['CrimeType'],
                     "Faction": log['Faction'],
                     "Victim": log.get('Victim', None),
                     "Fine": log.get('Fine', None),
                     "Bounty": log.get('Bounty', None)
                 }

             if log_event == 'Continued':
                 continued_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Part": log['Part']
                 }

             if log_event == 'CrewLaunchFighter':
                 crew_launch_fighter_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Crew": log['Crew'],
                     "ID": log['ID'],
                     "Telepresence": log['Telepresence']
                 }

             if log_event == 'CrewMemberJoins':
                 crew_member_joins_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Crew": log['Crew'],
                     "Telepresence": log['Telepresence']
                 }

             if log_event == 'CrewMemberQuits':
                 crew_member_quits_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Crew": log['Crew'],
                     "Telepresence": log['Telepresence']
                 }

             if log_event == 'CrewMemberRoleChange':
                 crew_member_role_change_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Crew": log['Crew'],
                     "Role": log['Role'],
                     "Telepresence": log['Telepresence']
                 }

             if log_event == 'CrimeVictim':
                 crime_victim_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Offender": log['Offender'],
                     "CrimeType": log['CrimeType'],
                     "Fine_or_Bounty": log.get('Fine_or_Bounty', None)
                 }

             if log_event == 'DatalinkScan':
                 datalink_scan_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Message": log['Message']
                 }

             if log_event == 'DatalinkVoucher':
                 datalink_voucher_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Reward": log['Reward'],
                     "VictimFaction": log['VictimFaction'],
                     "PayeeFaction": log['PayeeFaction']
                 }

             if log_event == 'DataScanned':
                 data_scanned_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Type": log['Type']
                 }

             if log_event == 'DockFighter':
                 dock_fighter_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "ID": log['ID']
                 }

             if log_event == 'DockSRV':
                 dock_srv_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "ID": log['ID'],
                     "SRVType": log['SRVType']
                 }

             if log_event == 'EndCrewSession':
                 end_crew_session_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "OnCrime": log['OnCrime'],
                     "Telepresence": log['Telepresence']
                 }

             if log_event == 'FighterRebuilt':
                 fighter_rebuilt_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Loadout": log['Loadout'],
                     "ID": log['ID']
                 }

             if log_event == 'FuelScoop':
                 fuel_scoop_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Scooped": log['Scooped'],
                     "Total": log['Total']
                 }

             if log_event == 'Friends':
                 friends_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Status": log['Status'],
                     "Name": log['Name']
                 }

             if log_event == 'JetConeBoost':
                 jet_cone_boost_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "BoostValue": log['BoostValue']
                 }

             if log_event == 'JetConeDamage':
                 jet_cone_damage_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Module": log['Module']
                 }

             if log_event == 'JoinACrew':
                 join_a_crew_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Captain": log['Captain'],
                     "Telepresence": log['Telepresence']
                 }

             if log_event == 'KickCrewMember':
                 kick_crew_member_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Crew": log['Crew'],
                     "OnCrime": log['OnCrime'],
                     "Telepresence": log['Telepresence']
                 }

             if log_event == 'LaunchDrone':
                 launch_drone_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Type": log['Type']
                 }

             if log_event == 'LaunchFighter':
                 launch_fighter_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Loadout": log['Loadout'],
                     "ID": log['ID'],
                     "PlayerControlled": log['PlayerControlled']
                 }

             if log_event == 'LaunchSRV':
                 launch_srv_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Loadout": log['Loadout'],
                     "ID": log['ID'],
                     "SRVType": log['SRVType']
                 }

             if log_event == 'ModuleInfo':
                 # Handling ModuleInfo event can be complex due to the variable number of modules and attributes.
                 # This typically involves parsing the Modules array separately.
                 # Assuming the structure of ModulesInfo.json file is handled separately from this snippet.
                 module_info_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event
                     # ModulesInfo.json handling might include more specific parsing logic
                 }

             if log_event == 'Music':
                 music_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "MusicTrack": log['MusicTrack']
                 }

             if log_event == 'NpcCrewPaidWage':
                 npc_crew_paid_wage_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "NpcCrewId": log['NpcCrewId'],
                     "NpcCrewName": log['NpcCrewName'],
                     "Amount": log['Amount']
                 }

             if log_event == 'NpcCrewRank':
                 npc_crew_rank_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "NpcCrewId": log['NpcCrewId'],
                     "NpcCrewName": log['NpcCrewName'],
                     "RankCombat": log['RankCombat']
                 }

             if log_event == 'Promotion':
                 promotion_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Combat": log.get('Combat', None),
                     "Trade": log.get('Trade', None),
                     "Explore": log.get('Explore', None),
                     "CQC": log.get('CQC', None),
                     "Federation": log.get('Federation', None),
                     "Empire": log.get('Empire', None)
                 }

             if log_event == 'ProspectedAsteroid':
                 prospected_asteroid_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Materials": log['Materials'],
                     "Content": log['Content'],
                     "MotherlodeMaterial": log.get('MotherlodeMaterial', None),
                     "Remaining": log['Remaining']
                 }

             if log_event == 'QuitACrew':
                 quit_a_crew_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Captain": log['Captain'],
                     "Telepresence": log['Telepresence']
                 }

             if log_event == 'RebootRepair':
                 reboot_repair_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Modules": log['Modules']
                 }

             if log_event == 'ReceiveText':
                 receive_text_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "From": log['From'],
                     "Message": log['Message'],
                     "Channel": log['Channel']
                 }

             if log_event == 'RepairDrone':
                 repair_drone_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "HullRepaired": log['HullRepaired'],
                     "CockpitRepaired": log['CockpitRepaired'],
                     "CorrosionRepaired": log['CorrosionRepaired']
                 }

             if log_event == 'ReservoirReplenished':
                 reservoir_replenished_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "FuelMain": log['FuelMain'],
                     "FuelReservoir": log['FuelReservoir']
                 }

             if log_event == 'Resurrect':
                 resurrect_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Option": log['Option'],
                     "Cost": log['Cost'],
                     "Bankrupt": log['Bankrupt']
                 }

             if log_event == 'Scanned':
                 scanned_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "ScanType": log['ScanType']
                 }

             if log_event == 'SelfDestruct':
                 self_destruct_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event
                 }

             if log_event == 'SendText':
                 send_text_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "To": log['To'],
                     "Message": log['Message']
                 }

             if log_event == 'Shutdown':
                 shutdown_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event
                 }

             if log_event == 'Synthesis':
                 synthesis_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Name": log['Name'],
                     "Materials": log['Materials']
                 }

             if log_event == 'SystemsShutdown':
                 systems_shutdown_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event
                 }

             if log_event == 'USSDrop':
                 uss_drop_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "USSType": log['USSType'],
                     "USSThreat": log['USSThreat']
                 }

             if log_event == 'VehicleSwitch':
                 vehicle_switch_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "To": log['To']
                 }

             if log_event == 'WingAdd':
                 wing_add_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Name": log['Name']
                 }

             if log_event == 'WingInvite':
                 wing_invite_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Name": log['Name']
                 }

             if log_event == 'WingJoin':
                 wing_join_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Others": log['Others']
                 }

             if log_event == 'WingLeave':
                 wing_leave_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event
                 }

             if log_event == 'CargoTransfer':
                 cargo_transfer_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Transfers": log['Transfers']
                 }

             if log_event == 'SupercruiseDestinationDrop':
                 supercruise_destination_drop_data = {
                     "timestamp": log['timestamp'],
                     "event": log_event,
                     "Type": log['Type'],
                     "Threat": log['Threat'],
                     "MarketID": log.get('MarketID', None)
                 }
        """

        # exceptions
        except Exception as e:
            #logger.exception("Exception occurred")
            print(e)


    def ship_state(self):

        latest_log = self.get_latest_log()

        # open journal file if not open yet or there is a more recent journal
        if self.current_log == None or self.current_log != latest_log:
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

        logger.debug('read:  '+str(cnt)+' ship: '+str(self.ship))
        return self.ship


def main():
    jn = EDJournal()
    while True:
        sleep(5)
        print("Ship = ", jn.ship_state())


if __name__ == "__main__":
    main()



