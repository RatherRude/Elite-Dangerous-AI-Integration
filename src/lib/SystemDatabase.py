import json
import time
import urllib.parse
import traceback
import requests
from typing import Any, Dict, List, Optional, cast

from .Database import Table, get_connection, debug_examine_database
from .Logger import log

class SystemDatabase:
    """A class for storing and retrieving system-specific data with EDSM integration"""
    
    def __init__(self):
        """Initialize the system database"""
        print("Initializing SystemDatabase...")
        self._ensure_table_created()
        # Debug: examine database contents
        print("Examining database contents:")
        debug_examine_database()
        
        # Debug: test insert
        self.test_insert_sample_data()
        
        # Register a background timer to periodically check and dump database contents
        from threading import Timer
        self.check_timer = Timer(60.0, self.periodic_check)
        self.check_timer.daemon = True  # Allow the timer to be terminated when the program exits
        self.check_timer.start()
    
    def _ensure_table_created(self) -> None:
        """Ensure the systems table is created"""
        try:
            print("Creating systems table...")
            self.systems_table = Table[Dict[str, Any]](
                'systems',
                {
                    'name': 'TEXT',
                    'system_address': 'INTEGER',
                    'star_class': 'TEXT',
                    'system_info': 'TEXT',
                    'stations': 'TEXT',
                    'last_updated': 'REAL',
                    'fetch_attempted': 'INTEGER',
                    'fsd_target': 'TEXT',
                    'nav_route': 'TEXT'
                },
                'name'
            )
            print(f"Systems table created successfully: {self.systems_table.table_name}")
            
            # Check if table exists by querying it
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{self.systems_table.table_name}'")
                result = cursor.fetchone()
                print(f"Table exists check: {result}")
                
                # Get table info
                cursor.execute(f"PRAGMA table_info({self.systems_table.table_name})")
                columns = cursor.fetchall()
                print(f"Table columns: {columns}")
                
                # Check number of records
                cursor.execute(f"SELECT COUNT(*) FROM {self.systems_table.table_name}")
                count = cursor.fetchone()[0]
                print(f"Current record count: {count}")
            except Exception as e:
                print(f"Error checking table: {e}")
            
        except Exception as e:
            print(f"Error creating systems table: {e}")
            import traceback
            print(traceback.format_exc())
    
    def store_fsd_target(self, system_name: str, target_system: str) -> None:
        """Store FSD target for a system"""
        try:
            print(f"Attempting to store FSD target: {system_name} -> {target_system}")
            # Check if system exists
            existing = self.systems_table.get(system_name)
            print(f"Existing record: {existing}")
            
            if existing:
                # Update existing record
                before_update = self.systems_table.get(system_name)
                print(f"Before update: {before_update}")
                
                self.systems_table.update(system_name, {'fsd_target': target_system})
                
                after_update = self.systems_table.get(system_name)
                print(f"After update: {after_update}")
                print(f"Updated FSD target for {system_name}: {target_system}")
            else:
                # Create new record
                data = {
                    'name': system_name,
                    'fsd_target': target_system,
                    'nav_route': json.dumps([]),
                    'fetch_attempted': 0,
                    'last_updated': time.time()
                }
                print(f"Inserting new record with data: {data}")
                
                result = self.systems_table.insert(data)
                
                new_record = self.systems_table.get(system_name)
                print(f"New record after insert: {new_record}")
                print(f"Created new system record for {system_name} with FSD target: {target_system}, result: {result}")
                
                # Double check the record count
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute(f"SELECT COUNT(*) FROM {self.systems_table.table_name}")
                count = cursor.fetchone()[0]
                print(f"Current record count after insert: {count}")
                
        except Exception as e:
            print(f"Error storing FSD target for {system_name}: {e}")
            import traceback
            print(traceback.format_exc())
    
    def store_nav_route(self, system_name: str, nav_route: List[Dict[str, Any]]) -> None:
        """Store nav route for a system and initiate EDSM data fetching"""
        try:
            # Check if system exists
            existing = self.systems_table.get(system_name)
            
            if existing:
                # Update existing record
                self.systems_table.update(system_name, {'nav_route': json.dumps(nav_route)})
                print(f"Updated nav route for {system_name} with {len(nav_route)} waypoints")
            else:
                # Create new record
                result = self.systems_table.insert({
                    'name': system_name,
                    'fsd_target': '',
                    'nav_route': json.dumps(nav_route),
                    'fetch_attempted': 0,
                    'last_updated': time.time()
                })
                print(f"Created new system record for {system_name} with nav route ({len(nav_route)} waypoints), result: {result}")
            
            # Get waypoint system names and fetch data for them
            systems_to_fetch = []
            for waypoint in nav_route:
                waypoint_system = waypoint.get('StarSystem')
                if waypoint_system:
                    systems_to_fetch.append(waypoint_system)
            
            # Fetch system data in background
            if systems_to_fetch:
                print(f"Will fetch data for {len(systems_to_fetch)} systems in the nav route")
                self._fetch_multiple_systems(systems_to_fetch)
                
        except Exception as e:
            print(f"Error storing nav route for {system_name}: {e}")
    
    def clear_nav_route(self, system_name: str) -> None:
        """Clear the nav route for a system"""
        try:
            # Check if system exists
            existing = self.systems_table.get(system_name)
            
            if existing:
                # Update existing record
                self.systems_table.update(system_name, {'nav_route': json.dumps([])})
                print(f"Cleared nav route for {system_name}")
            else:
                # Create new record with empty route
                result = self.systems_table.insert({
                    'name': system_name,
                    'fsd_target': '',
                    'nav_route': json.dumps([]),
                    'fetch_attempted': 0,
                    'last_updated': time.time()
                })
                print(f"Created new system record for {system_name} with empty nav route, result: {result}")
        except Exception as e:
            print(f"Error clearing nav route for {system_name}: {e}")
    
    def get_fsd_target(self, system_name: str) -> Optional[str]:
        """Get FSD target for a system"""
        try:
            system_data = self.systems_table.get(system_name)
            if system_data and 'fsd_target' in system_data:
                return system_data['fsd_target']
            return None
        except Exception as e:
            print(f"Error getting FSD target for {system_name}: {e}")
            return None
    
    def get_nav_route(self, system_name: str) -> List[Dict[str, Any]]:
        """Get nav route for a system"""
        try:
            system_data = self.systems_table.get(system_name)
            if system_data and 'nav_route' in system_data:
                return json.loads(system_data['nav_route'])
            return []
        except Exception as e:
            print(f"Error getting nav route for {system_name}: {e}")
            return []
    
    def get_system_info(self, system_name: str) -> Dict[str, Any]:
        """Get system information (including EDSM data if available)"""
        try:
            system_data = self.systems_table.get(system_name)
            if not system_data:
                return self._init_system_record(system_name)
                
            # If we have system info, return it
            if 'system_info' in system_data and system_data['system_info']:
                try:
                    return json.loads(system_data['system_info'])
                except json.JSONDecodeError:
                    pass
            
            # If we haven't attempted to fetch or it's been a while, fetch the data
            fetch_attempted = bool(system_data.get('fetch_attempted', 0))
            last_updated = system_data.get('last_updated', 0)
            if not fetch_attempted or (time.time() - last_updated) > 86400:  # 24 hours
                self._fetch_system_data(system_name)
                # Get fresh data
                system_data = self.systems_table.get(system_name)
                if system_data and 'system_info' in system_data and system_data['system_info']:
                    try:
                        return json.loads(system_data['system_info'])
                    except json.JSONDecodeError:
                        pass
            
            # Return empty dict if nothing found or error
            return {}
        except Exception as e:
            print(f"Error getting system info for {system_name}: {e}")
            return {}
    
    def get_stations(self, system_name: str) -> List[Dict[str, Any]]:
        """Get stations in a system"""
        try:
            system_data = self.systems_table.get(system_name)
            if not system_data:
                return []
                
            # If we have stations info, return it
            if 'stations' in system_data and system_data['stations']:
                try:
                    return json.loads(system_data['stations'])
                except json.JSONDecodeError:
                    pass
            
            # If we haven't fetched yet, trigger a fetch
            fetch_attempted = bool(system_data.get('fetch_attempted', 0))
            last_updated = system_data.get('last_updated', 0)
            if not fetch_attempted or (time.time() - last_updated) > 86400:  # 24 hours
                self._fetch_system_data(system_name)
                # Get fresh data
                system_data = self.systems_table.get(system_name)
                if system_data and 'stations' in system_data and system_data['stations']:
                    try:
                        return json.loads(system_data['stations'])
                    except json.JSONDecodeError:
                        pass
            
            # Return empty list if nothing found or error
            return []
        except Exception as e:
            print(f"Error getting stations for {system_name}: {e}")
            return []
    
    def _init_system_record(self, system_name: str) -> Dict[str, Any]:
        """Initialize a system record in the database"""
        try:
            result = self.systems_table.insert({
                'name': system_name,
                'fsd_target': '',
                'nav_route': json.dumps([]),
                'fetch_attempted': 0,
                'last_updated': time.time()
            })
            print(f"Initialized system record for {system_name}, result: {result}")
            return {}
        except Exception as e:
            print(f"Error initializing system record for {system_name}: {e}")
            return {}
    
    def _fetch_system_data(self, system_name: str) -> None:
        """Fetch system and station data from EDSM API"""
        # Mark that we've attempted to fetch data
        try:
            system_data = self.systems_table.get(system_name)
            if system_data:
                self.systems_table.update(system_name, {
                    'fetch_attempted': 1,
                    'last_updated': time.time()
                })
            else:
                self._init_system_record(system_name)
                self.systems_table.update(system_name, {'fetch_attempted': 1})
        except Exception as e:
            print(f"Error updating fetch status for {system_name}: {e}")
            return
        
        # Fetch system info from EDSM
        try:
            url = "https://www.edsm.net/api-v1/system"
            params = {
                "systemName": system_name,
                "showInformation": 1,
                "showPrimaryStar": 1,
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            system_info = response.json()
            
            # Update system info in database
            if system_info:
                self.systems_table.update(system_name, {
                    'system_info': json.dumps(system_info),
                    'system_address': system_info.get('id64', 0)
                })
                
                # Update star class if primary star info is available
                if 'primaryStar' in system_info and 'type' in system_info['primaryStar']:
                    self.systems_table.update(system_name, {
                        'star_class': system_info['primaryStar']['type']
                    })
                    
                print(f"Updated system info for {system_name}")
            
        except Exception as e:
            error_msg = str(e)
            log('error', f"Error fetching system info for {system_name}: {error_msg}", traceback.format_exc())
            
            # Store error in system info
            self.systems_table.update(system_name, {
                'system_info': json.dumps({"error": error_msg})
            })
        
        # Fetch station info from EDSM
        try:
            url = "https://www.edsm.net/api-system-v1/stations"
            params = {
                "systemName": system_name,
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            stations = [
                {
                    "name": station.get("name", "Unknown"),
                    "type": station.get("type", "Unknown"),
                    "orbit": station.get("distanceToArrival", "Unknown"),
                    "allegiance": station.get("allegiance", "None"),
                    "government": station.get("government", "None"),
                    "economy": station.get("economy", "None"),
                    "secondEconomy": station.get("secondEconomy", "None"),
                    "controllingFaction": station.get("controllingFaction", {}).get(
                        "name", "Unknown"
                    ),
                    "services": [
                        service
                        for service, has_service in {
                            "market": station.get("haveMarket", False),
                            "shipyard": station.get("haveShipyard", False),
                            "outfitting": station.get("haveOutfitting", False),
                        }.items()
                        if has_service
                    ],
                    **(
                        {"body": station["body"]["name"]}
                        if "body" in station and "name" in station["body"]
                        else {}
                    ),
                }
                for station in data.get("stations", [])
                if station.get("type") != "Fleet Carrier"
            ]
            
            # Update stations in database
            self.systems_table.update(system_name, {
                'stations': json.dumps(stations)
            })
            
            print(f"Updated station info for {system_name}, found {len(stations)} stations")
            
        except Exception as e:
            error_msg = str(e)
            log('error', f"Error fetching station info for {system_name}: {error_msg}", traceback.format_exc())
            
            # Store empty list for stations on error
            self.systems_table.update(system_name, {
                'stations': json.dumps([])
            })
    
    def _fetch_multiple_systems(self, system_names: List[str], chunk_size: int = 50) -> None:
        """
        Fetch information for multiple systems in a single API call
        
        Args:
            system_names: List of system names to fetch
            chunk_size: Size of chunks to split the request into (default: 50)
        """
        if not system_names:
            return
        
        # Process systems in chunks to avoid URL length issues
        system_chunks = [system_names[i:i + chunk_size] for i in range(0, len(system_names), chunk_size)]
        
        log('debug', f"Fetching information for {len(system_names)} systems in bulk ({len(system_chunks)} chunks)")
        
        # Mark all systems as attempted
        current_time = time.time()
        for system_name in system_names:
            try:
                system_data = self.systems_table.get(system_name)
                if system_data:
                    self.systems_table.update(system_name, {
                        'fetch_attempted': 1,
                        'last_updated': current_time
                    })
                else:
                    self._init_system_record(system_name)
                    self.systems_table.update(system_name, {'fetch_attempted': 1})
            except Exception as e:
                print(f"Error updating fetch status for {system_name}: {e}")
        
        # Process each chunk
        for chunk_index, chunk in enumerate(system_chunks):
            log('debug', f"Processing chunk {chunk_index + 1}/{len(system_chunks)} with {len(chunk)} systems")
            
            try:
                url = "https://www.edsm.net/api-v1/systems"
                params = {
                    "showInformation": 1,
                    "showPrimaryStar": 1,
                    "systemName[]": chunk  # Pass the entire chunk as a list - requests will format it properly
                }
                
                response = requests.get(url, params=params)
                response.raise_for_status()
                systems_data = response.json()
                
                # Process the response and update our state
                for system_data in systems_data:
                    system_name = system_data.get('name')
                    if system_name:
                        try:
                            # Update system info in database
                            self.systems_table.update(system_name, {
                                'system_info': json.dumps(system_data),
                                'system_address': system_data.get('id64', 0)
                            })
                            
                            # Update star class if primary star info is available
                            if 'primaryStar' in system_data and 'type' in system_data['primaryStar']:
                                self.systems_table.update(system_name, {
                                    'star_class': system_data['primaryStar']['type']
                                })
                                
                            print(f"Updated system info for {system_name} (bulk)")
                            
                            # Also fetch stations for this system
                            self._fetch_stations_for_system(system_name)
                        except Exception as e:
                            log('error', f"Error saving bulk system data for {system_name}: {e}", traceback.format_exc())
                
            except Exception as e:
                error_msg = str(e)
                log('error', f"Error fetching systems chunk {chunk_index + 1}: {error_msg}", traceback.format_exc())
                
                # Mark systems with error
                for system_name in chunk:
                    try:
                        self.systems_table.update(system_name, {
                            'system_info': json.dumps({"error": error_msg})
                        })
                    except Exception as update_err:
                        log('error', f"Error updating system {system_name} with error info: {update_err}")
    
    def _fetch_stations_for_system(self, system_name: str) -> None:
        """Fetch stations for a single system"""
        try:
            url = "https://www.edsm.net/api-system-v1/stations"
            params = {
                "systemName": system_name,
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            stations = [
                {
                    "name": station.get("name", "Unknown"),
                    "type": station.get("type", "Unknown"),
                    "orbit": station.get("distanceToArrival", "Unknown"),
                    "allegiance": station.get("allegiance", "None"),
                    "government": station.get("government", "None"),
                    "economy": station.get("economy", "None"),
                    "secondEconomy": station.get("secondEconomy", "None"),
                    "controllingFaction": station.get("controllingFaction", {}).get(
                        "name", "Unknown"
                    ),
                    "services": [
                        service
                        for service, has_service in {
                            "market": station.get("haveMarket", False),
                            "shipyard": station.get("haveShipyard", False),
                            "outfitting": station.get("haveOutfitting", False),
                        }.items()
                        if has_service
                    ],
                    **(
                        {"body": station["body"]["name"]}
                        if "body" in station and "name" in station["body"]
                        else {}
                    ),
                }
                for station in data.get("stations", [])
                if station.get("type") != "Fleet Carrier"
            ]
            
            # Update stations in database
            self.systems_table.update(system_name, {
                'stations': json.dumps(stations)
            })
            
            print(f"Updated station info for {system_name}, found {len(stations)} stations")
            
        except Exception as e:
            error_msg = str(e)
            log('error', f"Error fetching station info for {system_name}: {error_msg}", traceback.format_exc())
            
            # Store empty list for stations on error
            self.systems_table.update(system_name, {
                'stations': json.dumps([])
            })
    
    def test_insert_sample_data(self) -> None:
        """Insert sample data for testing"""
        try:
            print("\n--- TESTING DATABASE OPERATIONS ---")
            # Insert test FSD target
            test_system = "Test-System"
            test_target = "Test-Target"
            
            print(f"Inserting test FSD target: {test_system} -> {test_target}")
            self.store_fsd_target(test_system, test_target)
            
            # Insert test nav route
            test_route = [
                {"StarSystem": "Test-System-1", "Scoopable": True},
                {"StarSystem": "Test-System-2", "Scoopable": False}
            ]
            print(f"Inserting test nav route with {len(test_route)} waypoints")
            self.store_nav_route(test_system, test_route)
            
            # Read back data
            print("Reading back test data:")
            fsd_target = self.get_fsd_target(test_system)
            nav_route = self.get_nav_route(test_system)
            
            print(f"Retrieved FSD Target: {fsd_target}")
            print(f"Retrieved Nav Route: {nav_route}")
            
            # Check database again
            print("Checking database after test inserts:")
            debug_examine_database()
            
            print("--- END TEST ---\n")
        except Exception as e:
            print(f"Error in test: {e}")
            traceback.print_exc()
    
    def periodic_check(self):
        """Periodically check and dump database contents"""
        try:
            print("\n=== PERIODIC DATABASE CHECK ===")
            self.dump_database_contents()
            
            # Re-schedule the check
            from threading import Timer
            self.check_timer = Timer(60.0, self.periodic_check)
            self.check_timer.daemon = True
            self.check_timer.start()
        except Exception as e:
            print(f"Error in periodic check: {e}")
    
    def dump_database_contents(self):
        """Dump the contents of the systems table for debugging"""
        try:
            print("=== DATABASE CONTENTS ===")
            conn = get_connection()
            cursor = conn.cursor()
            
            # Check if table exists
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{self.systems_table.table_name}'")
            result = cursor.fetchone()
            if not result:
                print(f"Table {self.systems_table.table_name} does not exist")
                return
            
            # Get record count
            cursor.execute(f"SELECT COUNT(*) FROM {self.systems_table.table_name}")
            count = cursor.fetchone()[0]
            print(f"Total records: {count}")
            
            if count > 0:
                # Get all records
                cursor.execute(f"SELECT name, fsd_target, nav_route FROM {self.systems_table.table_name}")
                records = cursor.fetchall()
                
                print(f"Records:")
                for record in records:
                    name = record[0]
                    fsd_target = record[1] or "None"
                    nav_route = record[2][:50] + "..." if record[2] and len(record[2]) > 50 else record[2]
                    print(f"  System: {name}, FSD Target: {fsd_target}, Nav Route: {nav_route}")
            
            print("=== END DATABASE CONTENTS ===")
        except Exception as e:
            print(f"Error dumping database contents: {e}")
            import traceback
            print(traceback.format_exc())
    
    def process_event(self, event_type: str, content: dict) -> None:
        """Process an event directly and update the database accordingly"""
        print(f"SystemDatabase processing event: {event_type}")
        
        # Get current system from different event types
        current_system = "Unknown"
        if event_type == 'FSDJump' or event_type == 'Location':
            current_system = content.get('StarSystem', 'Unknown')
        elif event_type == 'FSDTarget':
            # For FSDTarget, we need the current system from somewhere else, but content includes target
            # Use the current system if one was passed in
            current_system = content.get('CurrentSystem', 'Unknown')
            # If we have an unknown current system, we can't save properly
            if current_system == 'Unknown':
                print(f"WARNING: Cannot process {event_type} event properly - current system is unknown")
        else:
            # For other events, try to get current system
            current_system = content.get('CurrentSystem', content.get('StarSystem', 'Unknown'))
        
        print(f"Current system determined to be: {current_system}")
        
        # Process specific event types
        if event_type == 'FSDTarget':
            if 'Name' in content:
                target_system = content.get('Name', 'Unknown')
                print(f"Processing FSDTarget: {current_system} -> {target_system}")
                self.store_fsd_target(current_system, target_system)
        
        elif event_type == 'NavRoute':
            if 'Route' in content and content['Route']:
                nav_route_data = []
                
                # Log the entire route for debugging
                print(f"NavRoute event contains route with {len(content['Route'])} systems")
                
                # Process new route, skip current system (first entry)
                for entry in content['Route'][1:]:
                    star_class = entry.get("StarClass", "")
                    is_scoopable = star_class in ['K','G','B','F','O','A','M']
                    system_name = entry.get("StarSystem", "Unknown")
                    
                    nav_route_data.append({
                        "StarSystem": system_name,
                        "Scoopable": is_scoopable
                    })
                    print(f"  - Route entry: {system_name}, class {star_class}, scoopable: {is_scoopable}")
                
                print(f"Processing NavRoute for {current_system} with {len(nav_route_data)} systems")
                self.store_nav_route(current_system, nav_route_data)
        
        elif event_type == 'NavRouteClear':
            print(f"Processing NavRouteClear for {current_system}")
            self.clear_nav_route(current_system)
            
        elif event_type == 'FSDJump' or event_type == 'Location':
            # Just update the current system record if it doesn't exist
            print(f"Processing {event_type} for {current_system}")
            system_data = self.systems_table.get(current_system)
            if not system_data:
                print(f"Creating new system record for {current_system}")
                self._init_system_record(current_system)

# Create a singleton instance
system_db = SystemDatabase() 