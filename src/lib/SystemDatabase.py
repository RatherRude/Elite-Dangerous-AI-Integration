import json
import time
import urllib.parse
import traceback
import requests
from typing import Any, Dict, List, Optional, cast

from .Database import KeyValueStore
from .Event import Event, GameEvent
from .Logger import log

class SystemDatabase:
    """A class for storing and retrieving system-specific data with EDSM integration"""
    
    def __init__(self):
        """Initialize the system database"""
        self._initialize_store()
        
        # Register a background timer to periodically check and dump database contents
        from threading import Timer
        self.check_timer = Timer(60.0, self.periodic_check)
        self.check_timer.daemon = True  # Allow the timer to be terminated when the program exits
        self.check_timer.start()
    
    def _initialize_store(self) -> None:
        """Initialize the systems key-value store"""
        try:
            self.systems_store = KeyValueStore('systems')
        except Exception as e:
            log('error', f"Error creating systems store: {e}")
            traceback.print_exc()
    
    def get_system_info(self, system_name: str) -> Dict[str, Any]:
        """Get system information (including EDSM data if available)"""
        try:
            system_data = self.systems_store.get(system_name)
            if not system_data:
                return self._init_system_record(system_name)
                
            # If we have system info, return it
            if 'system_info' in system_data and system_data['system_info']:
                # Check if it's already a dict (already deserialized)
                if isinstance(system_data['system_info'], dict):
                    return system_data['system_info']
                # Otherwise, try to parse it as JSON
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
                system_data = self.systems_store.get(system_name)
                if system_data and 'system_info' in system_data and system_data['system_info']:
                    # Check if it's already a dict (already deserialized)
                    if isinstance(system_data['system_info'], dict):
                        return system_data['system_info']
                    # Otherwise, try to parse it as JSON
                    try:
                        return json.loads(system_data['system_info'])
                    except json.JSONDecodeError:
                        pass
            
            # Return empty dict if nothing found or error
            return {}
        except Exception as e:
            log('error', f"Error getting system info for {system_name}: {e}")
            return {}
    
    def get_stations(self, system_name: str) -> List[Dict[str, Any]]:
        """Get stations in a system"""
        try:
            system_data = self.systems_store.get(system_name)
            if not system_data:
                return []
                
            # If we have stations info, return it
            if 'stations' in system_data and system_data['stations']:
                # Check if it's already a list (already deserialized)
                if isinstance(system_data['stations'], list):
                    return system_data['stations']
                # Otherwise, try to parse it as JSON
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
                system_data = self.systems_store.get(system_name)
                if system_data and 'stations' in system_data and system_data['stations']:
                    # Check if it's already a list (already deserialized)
                    if isinstance(system_data['stations'], list):
                        return system_data['stations']
                    # Otherwise, try to parse it as JSON
                    try:
                        return json.loads(system_data['stations'])
                    except json.JSONDecodeError:
                        pass
            
            # Return empty list if nothing found or error
            return []
        except Exception as e:
            log('error', f"Error getting stations for {system_name}: {e}")
            return []
    
    def _init_system_record(self, system_name: str) -> Dict[str, Any]:
        """Initialize a system record in the store"""
        try:
            system_data = {
                'name': system_name,
                'fetch_attempted': 0,
                'last_updated': time.time()
            }
            self.systems_store.init(system_name, 'v1', system_data)
            return {}
        except Exception as e:
            log('error', f"Error initializing system record for {system_name}: {e}")
            return {}
    
    def _fetch_system_data(self, system_name: str) -> None:
        """Fetch system and station data from EDSM API"""
        # Mark that we've attempted to fetch data
        try:
            system_data = self.systems_store.get(system_name)
            if system_data:
                system_data['fetch_attempted'] = 1
                system_data['last_updated'] = time.time()
                self.systems_store.set(system_name, system_data)
            else:
                self._init_system_record(system_name)
                system_data = self.systems_store.get(system_name, {})
                system_data['fetch_attempted'] = 1
                self.systems_store.set(system_name, system_data)
        except Exception as e:
            log('error', f"Error updating fetch status for {system_name}: {e}")
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
            
            # Update system info in store
            if system_info:
                system_data = self.systems_store.get(system_name, {})
                system_data['system_info'] = system_info
                system_data['system_address'] = system_info.get('id64', 0)
                
                # Update star class if primary star info is available
                if 'primaryStar' in system_info and 'type' in system_info['primaryStar']:
                    system_data['star_class'] = system_info['primaryStar']['type']
                
                self.systems_store.set(system_name, system_data)
            
        except Exception as e:
            error_msg = str(e)
            log('error', f"Error fetching system info for {system_name}: {error_msg}", traceback.format_exc())
            
            # Store error in system info
            system_data = self.systems_store.get(system_name, {})
            system_data['system_info'] = {"error": error_msg}
            self.systems_store.set(system_name, system_data)
        
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
            
            # Update stations in store
            system_data = self.systems_store.get(system_name, {})
            system_data['stations'] = stations
            self.systems_store.set(system_name, system_data)
            
        except Exception as e:
            error_msg = str(e)
            log('error', f"Error fetching station info for {system_name}: {error_msg}", traceback.format_exc())
            
            # Store empty list for stations on error
            system_data = self.systems_store.get(system_name, {})
            system_data['stations'] = []
            self.systems_store.set(system_name, system_data)
    
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
        
        # Mark all systems as attempted
        current_time = time.time()
        for system_name in system_names:
            try:
                system_data = self.systems_store.get(system_name)
                if system_data:
                    system_data['fetch_attempted'] = 1
                    system_data['last_updated'] = current_time
                    self.systems_store.set(system_name, system_data)
                else:
                    self._init_system_record(system_name)
                    system_data = self.systems_store.get(system_name, {})
                    system_data['fetch_attempted'] = 1
                    self.systems_store.set(system_name, system_data)
            except Exception as e:
                log('error', f"Error updating fetch status for {system_name}: {e}")
        
        # Process each chunk
        for chunk_index, chunk in enumerate(system_chunks):
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
                            # Update system info in store
                            stored_data = self.systems_store.get(system_name, {})
                            stored_data['system_info'] = system_data
                            stored_data['system_address'] = system_data.get('id64', 0)
                            
                            # Update star class if primary star info is available
                            if 'primaryStar' in system_data and 'type' in system_data['primaryStar']:
                                stored_data['star_class'] = system_data['primaryStar']['type']
                            
                            self.systems_store.set(system_name, stored_data)
                            
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
                        system_data = self.systems_store.get(system_name, {})
                        system_data['system_info'] = {"error": error_msg}
                        self.systems_store.set(system_name, system_data)
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
            
            # Update stations in store
            system_data = self.systems_store.get(system_name, {})
            system_data['stations'] = stations
            self.systems_store.set(system_name, system_data)
            
        except Exception as e:
            error_msg = str(e)
            log('error', f"Error fetching station info for {system_name}: {error_msg}", traceback.format_exc())
            
            # Store empty list for stations on error
            system_data = self.systems_store.get(system_name, {})
            system_data['stations'] = []
            self.systems_store.set(system_name, system_data)
    
    def periodic_check(self):
        """Periodically check database"""
        try:
            # Re-schedule the check
            from threading import Timer
            self.check_timer = Timer(60.0, self.periodic_check)
            self.check_timer.daemon = True
            self.check_timer.start()
        except Exception as e:
            log('error', f"Error in periodic check: {e}")
    
    def dump_database_contents(self) -> None:
        """Log a summary of the systems stored in the database"""
        try:
            # Get all systems
            all_systems = self.systems_store.get_all()
            total_systems = len(all_systems)
            
            # Count systems with info and stations
            systems_with_info = sum(1 for system_data in all_systems.values() if system_data.get('system_info'))
            systems_with_stations = sum(1 for system_data in all_systems.values() if system_data.get('stations'))
            
            log('info', f"SystemDatabase summary: {total_systems} total systems, {systems_with_info} with system info, {systems_with_stations} with station data")
            
        except Exception as e:
            log('error', f"Error dumping database contents: {e}")
    
    def process_event(self, event_type: str, content: dict) -> None:
        """Process an event directly and update the database accordingly"""
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
                log('warn', f"Cannot process {event_type} event properly - current system is unknown")
        else:
            # For other events, try to get current system
            current_system = content.get('CurrentSystem', content.get('StarSystem', 'Unknown'))
                    
        # Process FSDJump or Location to update the system record
        if event_type == 'FSDJump' or event_type == 'Location':
            # Just update the current system record if it doesn't exist
            system_data = self.systems_store.get(current_system)
            if not system_data:
                self._init_system_record(current_system)