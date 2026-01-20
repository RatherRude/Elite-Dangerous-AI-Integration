import json
import time
import urllib.parse
import traceback
import requests
from typing import Any, Callable, Dict, List, Optional
import asyncio
import aiohttp
import threading

from .Database import get_connection
from .Event import Event, GameEvent
from .Logger import log

# User agent for all EDSM API requests
EDSM_USER_AGENT = "COVAS:NEXT"


class SystemDatabase:
    """A class for storing and retrieving system-specific data with EDSM integration"""

    def __init__(self):
        """Initialize the system database"""
        self._initialize_store()
        
        # Add a lock for concurrent fetches
        self._fetch_locks = {}
        self._fetch_locks_lock = threading.Lock()

        # Register a background timer to periodically check and dump database contents
        from threading import Timer
        self.check_timer = Timer(60.0, self.periodic_check)
        self.check_timer.daemon = True  # Allow the timer to be terminated when the program exits
        self.check_timer.start()

    def _initialize_store(self) -> None:
        """Initialize the systems key-value store"""
        try:
            self.table_name = "systems_v2"
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    name TEXT PRIMARY KEY,
                    star_address INTEGER,
                    system_info TEXT,
                    fetch_attempted INTEGER DEFAULT 0,
                    last_updated FLOAT DEFAULT 0,
                    inserted_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute(f'''
                CREATE INDEX IF NOT EXISTS {self.table_name}_star_address_idx
                ON {self.table_name} (star_address)
            ''')
            conn.commit()
        except Exception as e:
            log('error', f"Error creating systems store: {e}")
            traceback.print_exc()

    def _serialize_value(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        return json.dumps(value)

    def _deserialize_value(self, raw: Optional[str]) -> Any:
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def _get_system_record(self, system_name: str) -> Optional[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f'''
            SELECT name, star_address, system_info, fetch_attempted, last_updated
            FROM {self.table_name}
            WHERE name = ?
        ''', (system_name,))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            'name': row[0],
            'star_address': row[1],
            'system_info': self._deserialize_value(row[2]),
            'fetch_attempted': row[3] or 0,
            'last_updated': row[4] or 0
        }

    def _upsert_system_fields(self, system_name: str, fields: Dict[str, Any]) -> None:
        if not fields:
            return
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f'''
            INSERT INTO {self.table_name} (name)
            VALUES (?)
            ON CONFLICT(name) DO NOTHING
        ''', (system_name,))

        normalized_fields: Dict[str, Any] = {}
        for key, value in fields.items():
            if key == 'system_info':
                normalized_fields[key] = self._serialize_value(value)
            else:
                normalized_fields[key] = value

        set_clause = ", ".join([f"{key} = ?" for key in normalized_fields.keys()])
        values = list(normalized_fields.values())
        cursor.execute(f'''
            UPDATE {self.table_name}
            SET {set_clause}
            WHERE name = ?
        ''', (*values, system_name))
        conn.commit()

    def _get_system_record_by_address(self, star_address: int) -> Optional[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f'''
            SELECT name, star_address, system_info, fetch_attempted, last_updated
            FROM {self.table_name}
            WHERE star_address = ?
            LIMIT 1
        ''', (star_address,))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            'name': row[0],
            'star_address': row[1],
            'system_info': self._deserialize_value(row[2]),
            'fetch_attempted': row[3] or 0,
            'last_updated': row[4] or 0
        }

    def _with_system_info(
        self,
        system_name: Optional[str],
        star_address: Optional[int],
        updater: Callable[[Dict[str, Any]], None]
    ) -> None:
        if not system_name and star_address is not None:
            record_by_address = self._get_system_record_by_address(star_address)
            if record_by_address:
                system_name = record_by_address.get('name')
            else:
                system_name = f"Unknown-{star_address}"
                self._init_system_record(system_name)
                self._upsert_system_fields(system_name, {'star_address': star_address})
        if not system_name:
            return
        record = self._get_system_record(system_name)
        if not record:
            self._init_system_record(system_name)
            record = self._get_system_record(system_name) or {'name': system_name}
        system_info = record.get('system_info')
        if not isinstance(system_info, dict):
            system_info = {}
        system_info = dict(system_info)
        updater(system_info)
        update_fields: Dict[str, Any] = {'system_info': system_info}
        if star_address is not None:
            update_fields['star_address'] = star_address
        self._upsert_system_fields(system_name, update_fields)

    def get_system_info(self, system_name: str, async_fetch: bool = False) -> Dict[str, Any]:
        """Get system information (including EDSM data if available)"""
        try:
            system_data = self._get_system_record(system_name)

            # For async_fetch mode, just check if data exists and trigger async fetch if needed
            if async_fetch:
                if not system_data:
                    # Initialize the record and trigger async fetch
                    self._init_system_record(system_name)
                    self.fetch_system_data_nonblocking(system_name)
                    return {}

            if not system_data:
                return self._init_system_record(system_name)

            # If we have system info, return it
            if 'system_info' in system_data and system_data['system_info']:
                if isinstance(system_data['system_info'], dict):
                    return system_data['system_info']

            # If we haven't attempted to fetch or it's been a while, fetch the data
            fetch_attempted = bool(system_data.get('fetch_attempted', 0))
            last_updated = system_data.get('last_updated', 0)
            if not fetch_attempted or (time.time() - last_updated) > 604800:  # 7 days
                self._fetch_system_data(system_name)
                # Get fresh data
                system_data = self._get_system_record(system_name)
                if system_data and 'system_info' in system_data and system_data['system_info']:
                    if isinstance(system_data['system_info'], dict):
                        return system_data['system_info']

            # Return empty dict if nothing found or error
            return {}
        except Exception as e:
            log('error', f"Error getting system info for {system_name}: {e}")
            return {}

    def get_system_by_address(self, star_address: int) -> Optional[Dict[str, Any]]:
        """Get system record by star address (id64)."""
        try:
            return self._get_system_record_by_address(star_address)
        except Exception as e:
            log('error', f"Error getting system by address {star_address}: {e}")
            return None

    def has_system(self, system_name: str) -> bool:
        """Return True if we already have a record for the system name."""
        try:
            return self._get_system_record(system_name) is not None
        except Exception as e:
            log('error', f"Error checking system record for {system_name}: {e}")
            return False

    def get_stations(self, system_name: str) -> List[Dict[str, Any]]:
        """Get stations in a system"""
        try:
            system_data = self._get_system_record(system_name)
            if not system_data:
                return []

            # If we have stations info, return it
            system_info = system_data.get('system_info') or {}
            if isinstance(system_info, dict) and system_info.get('stations'):
                if isinstance(system_info['stations'], list):
                    return system_info['stations']

            # If we haven't fetched yet, trigger a fetch
            fetch_attempted = bool(system_data.get('fetch_attempted', 0))
            last_updated = system_data.get('last_updated', 0)
            if not fetch_attempted or (time.time() - last_updated) > 604800:  # 7 days
                self._fetch_system_data(system_name)
                # Get fresh data
                system_data = self._get_system_record(system_name)
                if system_data:
                    system_info = system_data.get('system_info') or {}
                    if isinstance(system_info, dict) and system_info.get('stations'):
                        if isinstance(system_info['stations'], list):
                            return system_info['stations']

            # Return empty list if nothing found or error
            return []
        except Exception as e:
            log('error', f"Error getting stations for {system_name}: {e}")
            return []

    def get_bodies(self, system_name: str) -> List[Dict[str, Any]]:
        """Get bodies in a system"""
        try:
            system_data = self._get_system_record(system_name)
            if not system_data:
                return []

            # If we have bodies info, return it
            system_info = system_data.get('system_info') or {}
            if isinstance(system_info, dict) and system_info.get('bodies'):
                if isinstance(system_info['bodies'], list):
                    return system_info['bodies']

            # If we haven't fetched yet, trigger a fetch
            fetch_attempted = bool(system_data.get('fetch_attempted', 0))
            last_updated = system_data.get('last_updated', 0)
            if not fetch_attempted or (time.time() - last_updated) > 604800:  # 7 days
                self._fetch_system_data(system_name)
                # Get fresh data
                system_data = self._get_system_record(system_name)
                if system_data:
                    system_info = system_data.get('system_info') or {}
                    if isinstance(system_info, dict) and system_info.get('bodies'):
                        if isinstance(system_info['bodies'], list):
                            return system_info['bodies']

            # Return empty list if nothing found or error
            return []
        except Exception as e:
            log('error', f"Error getting bodies for {system_name}: {e}")
            return []

    # Event-driven updates (game-reported data) ---------------------------------
    def record_discovery_scan(self, event: Dict[str, Any]) -> None:
        system_name = event.get("SystemName")
        system_address = event.get("SystemAddress")
        if system_address is None:
            return
        body_count = int(event.get("BodyCount", 0))
        non_body_count = int(event.get("NonBodyCount", 0))
        progress = event.get("Progress")

        def updater(system_info: Dict[str, Any]) -> None:
            totals = system_info.get("totals")
            if not isinstance(totals, dict):
                totals = {}
            system_info["totals"] = totals
            totals["bodies"] = body_count
            totals["non_bodies"] = non_body_count
            if progress is not None:
                totals["progress"] = progress

        self._with_system_info(system_name, system_address, updater)

    def record_fsd_target(self, event: Dict[str, Any]) -> None:
        system_name = event.get("Name")
        system_address = event.get("SystemAddress")
        if system_address is None:
            return
        star_class = event.get("StarClass")
        if not star_class:
            return

        def updater(system_info: Dict[str, Any]) -> None:
            system_info["star_class"] = star_class

        self._with_system_info(system_name, system_address, updater)

    def record_scan(self, event: Dict[str, Any]) -> None:
        system_name = event.get("StarSystem")
        system_address = event.get("SystemAddress")
        body_id = event.get("BodyID")
        body_name = event.get("BodyName")
        if system_address is None or body_id is None or body_name is None:
            return

        scan_type = event.get("ScanType", "Unknown")
        planet_class = event.get("PlanetClass", "Unknown")
        was_discovered = bool(event.get("WasDiscovered", False))
        was_mapped = bool(event.get("WasMapped", False))
        was_footfalled = bool(event.get("WasFootfalled", False))
        timestamp = event.get("timestamp")
        parents = event.get("Parents")

        def updater(system_info: Dict[str, Any]) -> None:
            bodies = system_info.setdefault("bodies", [])
            body_entry = None
            for body in bodies:
                if body.get("bodyId") == body_id or body.get("body_id") == body_id:
                    body_entry = body
                    break
            if body_entry is None:
                body_entry = {
                    "bodyId": body_id,
                    "name": body_name,
                    "type": planet_class,
                }
                bodies.append(body_entry)

            body_entry.setdefault("signals", [])
            body_entry.setdefault("genuses", [])
            if body_name and (not body_entry.get("name") or body_entry.get("name") == "Unknown"):
                body_entry["name"] = body_name
            if planet_class and (not body_entry.get("type") or body_entry.get("type") == "Unknown"):
                body_entry["type"] = planet_class
            body_entry["scanType"] = scan_type
            body_entry["wasDiscovered"] = was_discovered
            body_entry["wasMapped"] = was_mapped
            body_entry["wasFootfalled"] = was_footfalled
            if timestamp is not None:
                body_entry["timestamp"] = timestamp
            if parents is not None:
                body_entry["parents"] = parents

        self._with_system_info(system_name, system_address, updater)

    def record_signal(self, event: Dict[str, Any]) -> None:
        system_name = event.get("SystemName")
        system_address = event.get("SystemAddress")
        if system_address is None:
            return
        signal_name = event.get("SignalName_Localised", event.get("SignalName", 'Unknown'))
        signal_type = event.get("SignalType", "Unknown")
        is_station = bool(event.get("IsStation", False))

        if signal_type in ("FleetCarrier", "SquadronCarrier", "SquadCarrier"):
            return

        def updater(system_info: Dict[str, Any]) -> None:
            stations = system_info.setdefault("stations", [])
            station_names = {s.get("name") for s in stations if isinstance(s, dict)}
            if is_station:
                if signal_name not in station_names:
                    stations.append({
                        "name": signal_name,
                        "type": signal_type or "Station"
                    })
                return

            if signal_name in station_names:
                return

            signals = system_info.setdefault("signals", [])
            if any(isinstance(s, dict) and s.get("name") == signal_name for s in signals):
                return
            signals.append({
                "name": signal_name,
                "type": signal_type
            })

        self._with_system_info(system_name, system_address, updater)

    def record_saa_signals_found(self, event: Dict[str, Any]) -> None:
        system_name = None
        system_address = event.get("SystemAddress")
        body_id = event.get("BodyID")
        body_name = event.get("BodyName")
        if system_address is None or body_id is None:
            return

        signals = event.get("Signals") or []
        genuses = event.get("Genuses") or []

        def updater(system_info: Dict[str, Any]) -> None:
            bodies = system_info.setdefault("bodies", [])
            body_entry = None
            ring_entry = None
            for body in bodies:
                if body.get("bodyId") == body_id or body.get("body_id") == body_id:
                    body_entry = body
                    break
            if body_entry is None and body_name:
                for body in bodies:
                    rings = body.get("rings")
                    if isinstance(rings, list):
                        for ring in rings:
                            if isinstance(ring, dict) and ring.get("name") == body_name:
                                ring_entry = ring
                                break
                    if ring_entry is not None:
                        break
            if body_entry is None:
                body_entry = {"bodyId": body_id, "name": body_name}
                # bodies.append(body_entry)

            target_entry = ring_entry if ring_entry is not None else body_entry
            current_signals = target_entry.get("signals") or []
            existing_signals = {s.get("Type"): s for s in current_signals if isinstance(s, dict) and s.get("Type")}
            for sig in signals:
                sig_type = sig.get("Type") if isinstance(sig, dict) else None
                if sig_type in existing_signals:
                    existing_signals[sig_type].update(sig)
                else:
                    if sig_type:
                        existing_signals[sig_type] = dict(sig)
            target_entry["signals"] = list(existing_signals.values())

            if target_entry is body_entry:
                current_genuses = body_entry.get("genuses") or []
                existing_genus = {
                    g.get("Genus"): g
                    for g in current_genuses
                    if isinstance(g, dict) and g.get("Genus")
                }
                for g in genuses:
                    genus_key = g.get("Genus") if isinstance(g, dict) else None
                    if genus_key in existing_genus:
                        existing = existing_genus[genus_key]
                        scanned = existing.get("scanned", False)
                        existing.update(g)
                        existing["scanned"] = scanned
                    else:
                        if genus_key:
                            entry = dict(g)
                            entry.setdefault("scanned", False)
                            existing_genus[genus_key] = entry
                body_entry["genuses"] = list(existing_genus.values())

        self._with_system_info(system_name, system_address, updater)

    def record_fss_body_signals(self, event: Dict[str, Any]) -> None:
        system_name = None
        system_address = event.get("SystemAddress")
        body_id = event.get("BodyID")
        body_name = event.get("BodyName")
        if system_address is None or body_id is None:
            return

        signals = event.get("Signals") or []

        def updater(system_info: Dict[str, Any]) -> None:
            bodies = system_info.setdefault("bodies", [])
            body_entry = None
            for body in bodies:
                if body.get("bodyId") == body_id or body.get("body_id") == body_id:
                    body_entry = body
                    break
            if body_entry is None:
                body_entry = {"bodyId": body_id, "name": body_name}
                bodies.append(body_entry)

            current_signals = body_entry.get("signals") or []
            existing_signals = {s.get("Type"): s for s in current_signals if isinstance(s, dict) and s.get("Type")}
            for sig in signals:
                sig_type = sig.get("Type") if isinstance(sig, dict) else None
                if sig_type in existing_signals:
                    existing_signals[sig_type].update(sig)
                else:
                    if sig_type:
                        existing_signals[sig_type] = dict(sig)
            body_entry["signals"] = list(existing_signals.values())

        self._with_system_info(system_name, system_address, updater)

    def record_scan_organic(self, event: Dict[str, Any]) -> None:
        if event.get("ScanType") != "Analyse":
            return
        system_address = event.get("SystemAddress")
        if system_address is None:
            return
        body_id = event.get("Body")
        if body_id is None:
            return
        system_name = None
        genus = event.get("Genus")
        genus_localised = event.get("Genus_Localised")
        species = event.get("Species")
        species_localised = event.get("Species_Localised")

        def updater(system_info: Dict[str, Any]) -> None:
            bodies = system_info.setdefault("bodies", [])
            body_entry = None
            for body in bodies:
                if body.get("bodyId") == body_id or body.get("body_id") == body_id:
                    body_entry = body
                    break
            if body_entry is None:
                body_entry = {"bodyId": body_id}
                bodies.append(body_entry)

            genuses_list = body_entry.get("genuses") or []
            genus_map = {g.get("Genus"): g for g in genuses_list if isinstance(g, dict) and g.get("Genus")}

            if genus in genus_map:
                genus_entry = genus_map[genus]
            else:
                genus_entry = {"Genus": genus, "Genus_Localised": genus_localised, "scanned": False}
                genuses_list.append(genus_entry)

            if genus_localised:
                genus_entry["Genus_Localised"] = genus_localised
            genus_entry["scanned"] = True
            if species:
                genus_entry["Species"] = species
            if species_localised:
                genus_entry["Species_Localised"] = species_localised

            body_entry["genuses"] = genuses_list

        self._with_system_info(system_name, system_address, updater)

    def _init_system_record(self, system_name: str) -> Dict[str, Any]:
        """Initialize a system record in the store"""
        try:
            self._upsert_system_fields(system_name, {
                'fetch_attempted': 0,
                'last_updated': time.time()
            })
            return {}
        except Exception as e:
            log('error', f"Error initializing system record for {system_name}: {e}")
            return {}

    def _fetch_system_data(self, system_name: str) -> None:
        """Fetch system, station, and body data from EDSM API"""
        # Mark that we've attempted to fetch data
        try:
            self._upsert_system_fields(system_name, {
                'fetch_attempted': 1,
                'last_updated': time.time()
            })
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
            headers = {
                "User-Agent": EDSM_USER_AGENT
            }

            response = requests.get(url, params=params, headers=headers, timeout=1)
            response.raise_for_status()
            system_info = response.json()

            # Update system info in store
            if system_info:
                existing_data = self._get_system_record(system_name) or {}
                existing_info = existing_data.get('system_info')
                if isinstance(existing_info, dict):
                    merged_info = dict(system_info)
                    if 'stations' in existing_info:
                        merged_info['stations'] = existing_info['stations']
                    if 'bodies' in existing_info:
                        merged_info['bodies'] = existing_info['bodies']
                    system_info = merged_info

                update_fields = {
                    'system_info': system_info,
                    'star_address': system_info.get('id64', 0)
                }

                self._upsert_system_fields(system_name, update_fields)

        except Exception as e:
            error_msg = str(e)
            log('error', f"Error fetching system info for {system_name}: {error_msg}", traceback.format_exc())

            # Store error in system info
            self._upsert_system_fields(system_name, {
                'system_info': {"error": error_msg}
            })

        # Fetch station info from EDSM
        try:
            url = "https://www.edsm.net/api-system-v1/stations"
            params = {
                "systemName": system_name,
            }
            headers = {
                "User-Agent": EDSM_USER_AGENT
            }

            response = requests.get(url, params=params, headers=headers, timeout=1)
            response.raise_for_status()
            data = response.json()
            star_address = data.get("id64")

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

            # Update stations inside system_info
            existing_data = self._get_system_record(system_name) or {}
            system_info = existing_data.get('system_info')
            if not isinstance(system_info, dict):
                system_info = {}
            system_info = dict(system_info)
            system_info['stations'] = stations

            update_fields = {'system_info': system_info}
            if star_address is not None:
                update_fields['star_address'] = star_address
            self._upsert_system_fields(system_name, update_fields)

        except Exception as e:
            error_msg = str(e)
            log('error', f"Error fetching station info for {system_name}: {error_msg}", traceback.format_exc())

            # Store empty list for stations on error
            existing_data = self._get_system_record(system_name) or {}
            system_info = existing_data.get('system_info')
            if not isinstance(system_info, dict):
                system_info = {}
            system_info = dict(system_info)
            system_info['stations'] = []
            self._upsert_system_fields(system_name, {'system_info': system_info})

        # Fetch bodies info from EDSM
        try:
            url = "https://www.edsm.net/api-system-v1/bodies"
            params = {
                "systemName": system_name,
            }
            headers = {
                "User-Agent": EDSM_USER_AGENT
            }

            response = requests.get(url, params=params, headers=headers, timeout=1)
            response.raise_for_status()
            data = response.json()
            star_address = data.get("id64")
            bodies = data.get("bodies", [])

            existing_data = self._get_system_record(system_name) or {}
            system_info = existing_data.get('system_info')
            if not isinstance(system_info, dict):
                system_info = {}
            system_info = dict(system_info)
            system_info['bodies'] = bodies

            update_fields = {'system_info': system_info}
            if star_address is not None:
                update_fields['star_address'] = star_address
            self._upsert_system_fields(system_name, update_fields)

        except Exception as e:
            error_msg = str(e)
            log('error', f"Error fetching bodies for {system_name}: {error_msg}", traceback.format_exc())

            # Store empty list for bodies on error
            existing_data = self._get_system_record(system_name) or {}
            system_info = existing_data.get('system_info')
            if not isinstance(system_info, dict):
                system_info = {}
            system_info = dict(system_info)
            system_info['bodies'] = []
            self._upsert_system_fields(system_name, {'system_info': system_info})

        # Update body signals/genuses/ring signals/landmarks from Spansh
        try:
            self._update_bodies_from_spansh(system_name)
        except Exception as e:
            error_msg = str(e)
            log('error', f"Error fetching Spansh bodies for {system_name}: {error_msg}", traceback.format_exc())

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
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(f'''
                SELECT name, system_info
                FROM {self.table_name}
            ''')
            rows = cursor.fetchall()
            total_systems = len(rows)

            # Count systems with info, stations, and bodies
            systems_with_info = sum(1 for row in rows if row[1])
            systems_with_stations = 0
            systems_with_bodies = 0
            for row in rows:
                system_info = self._deserialize_value(row[1])
                if isinstance(system_info, dict):
                    if system_info.get('stations'):
                        systems_with_stations += 1
                    if system_info.get('bodies'):
                        systems_with_bodies += 1

            log('info',
                f"SystemDatabase summary: {total_systems} total systems, {systems_with_info} with system info, {systems_with_stations} with station data, {systems_with_bodies} with body data")

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
            system_data = self._get_system_record(current_system)
            if not system_data:
                self._init_system_record(current_system)

    async def _fetch_system_data_async(self, system_name: str) -> None:
        """Fetch system, station, and body data from EDSM API asynchronously"""
        # Mark that we've attempted to fetch data
        try:
            self._upsert_system_fields(system_name, {
                'fetch_attempted': 1,
                'last_updated': time.time()
            })
        except Exception as e:
            log('error', f"Error updating fetch status for {system_name}: {e}")
            return

        # Start API calls concurrently
        try:
            async with aiohttp.ClientSession() as session:
                # Create tasks for API calls
                system_task = self._fetch_system_info_async(session, system_name)
                stations_task = self._fetch_stations_async(session, system_name)
                bodies_task = self._fetch_bodies_async(session, system_name)

                # Wait for all tasks to complete
                await asyncio.gather(system_task, stations_task, bodies_task)

        except Exception as e:
            error_msg = str(e)
            log('error', f"Error in async fetch for {system_name}: {error_msg}", traceback.format_exc())

    async def _fetch_system_info_async(self, session: aiohttp.ClientSession, system_name: str) -> None:
        """Fetch system info from EDSM API asynchronously"""
        try:
            url = "https://www.edsm.net/api-v1/system"
            params = {
                "systemName": system_name,
                "showInformation": 1,
                "showPrimaryStar": 1,
            }
            headers = {
                "User-Agent": EDSM_USER_AGENT
            }

            async with session.get(url, params=params, headers=headers) as response:
                response.raise_for_status()
                system_info = await response.json()

                # Create a new system record with the fetched info
                if system_info:
                    # Get the current timestamp
                    current_time = time.time()

                    try:
                        # We need to read first to get any existing data like stations
                        # that we want to preserve
                        existing_data = self._get_system_record(system_name) or {}

                        # Create a new record with the updated system info,
                        # but preserving existing data like stations
                        system_data = existing_data.copy()
                        existing_info = existing_data.get('system_info')
                        if isinstance(existing_info, dict):
                            merged_info = dict(system_info)
                            if 'stations' in existing_info:
                                merged_info['stations'] = existing_info['stations']
                            if 'bodies' in existing_info:
                                merged_info['bodies'] = existing_info['bodies']
                            system_info = merged_info
                        system_data['system_info'] = system_info
                        system_data['star_address'] = system_info.get('id64', 0)
                        system_data['fetch_attempted'] = 1
                        system_data['last_updated'] = current_time

                        # Write the updated data
                        self._upsert_system_fields(system_name, system_data)
                    except Exception as e:
                        # If we can't get the existing data, create a new minimal record
                        log('warn',
                            f"Couldn't retrieve existing system data for {system_name} when updating system info: {e}")

                        # Create minimal system data
                        system_data = {
                            'name': system_name,
                            'fetch_attempted': 1,
                            'last_updated': current_time,
                            'system_info': system_info,
                            'star_address': system_info.get('id64', 0)
                        }

                        self._upsert_system_fields(system_name, system_data)

        except Exception as e:
            error_msg = str(e)
            log('error', f"Error fetching system info async for {system_name}: {error_msg}", traceback.format_exc())

            # Create a minimal error system record
            try:
                current_time = time.time()
                self._upsert_system_fields(system_name, {
                    'fetch_attempted': 1,
                    'last_updated': current_time,
                    'system_info': {"error": error_msg}
                })
            except Exception as update_err:
                log('error', f"Error updating system {system_name} with error info: {update_err}")

    async def _fetch_stations_async(self, session: aiohttp.ClientSession, system_name: str) -> None:
        """Fetch station info from EDSM API asynchronously"""
        try:
            url = "https://www.edsm.net/api-system-v1/stations"
            params = {
                "systemName": system_name,
            }
            headers = {
                "User-Agent": EDSM_USER_AGENT
            }

            async with session.get(url, params=params, headers=headers) as response:
                response.raise_for_status()
                data = await response.json()
                star_address = data.get("id64")

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

                # Create a new system data record with stations info
                # Get the current timestamp to keep records consistent
                current_time = time.time()

                try:
                    # We need to read first to get any existing system info
                    # This is safe because we're not modifying any fields
                    # other than 'stations'
                    system_data = self._get_system_record(system_name) or {}

                    # Only update stations within system_info, preserving other data
                    system_info = system_data.get('system_info')
                    if not isinstance(system_info, dict):
                        system_info = {}
                    system_info = dict(system_info)
                    system_info['stations'] = stations
                    system_data['system_info'] = system_info
                    system_data['fetch_attempted'] = 1
                    system_data['last_updated'] = current_time
                    if star_address is not None:
                        system_data['star_address'] = star_address

                    # Write back to database
                    self._upsert_system_fields(system_name, system_data)
                except Exception as e:
                    # If we can't get the existing data, create a new minimal record
                    log('warn', f"Couldn't retrieve existing system data for {system_name} when updating stations: {e}")
                    system_info = {}
                    system_info['stations'] = stations
                    self._upsert_system_fields(system_name, {
                        'fetch_attempted': 1,
                        'last_updated': current_time,
                        'system_info': system_info
                    })

        except Exception as e:
            error_msg = str(e)
            log('error', f"Error fetching station info async for {system_name}: {error_msg}", traceback.format_exc())

            # Create a minimal error system record with empty stations
            try:
                current_time = time.time()
                system_info = {}
                system_info['stations'] = []
                self._upsert_system_fields(system_name, {
                    'fetch_attempted': 1,
                    'last_updated': current_time,
                    'system_info': system_info
                })
            except Exception as update_err:
                log('error', f"Error updating system {system_name} with empty stations: {update_err}")

    async def _fetch_bodies_async(self, session: aiohttp.ClientSession, system_name: str) -> None:
        """Fetch bodies info from EDSM API asynchronously"""
        try:
            url = "https://www.edsm.net/api-system-v1/bodies"
            params = {
                "systemName": system_name,
            }
            headers = {
                "User-Agent": EDSM_USER_AGENT
            }

            async with session.get(url, params=params, headers=headers) as response:
                response.raise_for_status()
                data = await response.json()
                star_address = data.get("id64")
                bodies = data.get("bodies", [])

                # Create a new system data record with bodies info
                # Get the current timestamp to keep records consistent
                current_time = time.time()

                try:
                    # We need to read first to get any existing system info
                    # This is safe because we're not modifying any fields
                    # other than 'bodies'
                    system_data = self._get_system_record(system_name) or {}

                    # Only update bodies within system_info, preserving other data
                    system_info = system_data.get('system_info')
                    if not isinstance(system_info, dict):
                        system_info = {}
                    system_info = dict(system_info)
                    system_info['bodies'] = bodies
                    system_data['system_info'] = system_info
                    system_data['fetch_attempted'] = 1
                    system_data['last_updated'] = current_time
                    if star_address is not None:
                        system_data['star_address'] = star_address

                    # Write back to database
                    self._upsert_system_fields(system_name, system_data)
                except Exception as e:
                    # If we can't get the existing data, create a new minimal record
                    log('warn', f"Couldn't retrieve existing system data for {system_name} when updating bodies: {e}")
                    system_info = {}
                    system_info['bodies'] = bodies
                    self._upsert_system_fields(system_name, {
                        'fetch_attempted': 1,
                        'last_updated': current_time,
                        'system_info': system_info
                    })

        except Exception as e:
            error_msg = str(e)
            log('error', f"Error fetching bodies async for {system_name}: {error_msg}", traceback.format_exc())

            # Create a minimal error system record with empty bodies
            try:
                current_time = time.time()
                system_info = {}
                system_info['bodies'] = []
                self._upsert_system_fields(system_name, {
                    'fetch_attempted': 1,
                    'last_updated': current_time,
                    'system_info': system_info
                })
            except Exception as update_err:
                log('error', f"Error updating system {system_name} with empty bodies: {update_err}")

        # Update body signals/genuses/ring signals/landmarks from Spansh
        try:
            await self._update_bodies_from_spansh_async(session, system_name)
        except Exception as e:
            error_msg = str(e)
            log('error', f"Error fetching Spansh bodies async for {system_name}: {error_msg}", traceback.format_exc())

    def _build_spansh_bodies_request(self, system_name: str) -> Dict[str, Any]:
        return {
            "filters": {
                "type": {
                    "value": [
                        "Planet",
                        "Star"
                    ]
                },
                "distance": {
                    "min": "0",
                    "max": "1"
                }
            },
            "sort": [
                {
                    "distance_to_arrival": {
                        "direction": "asc"
                    }
                }
            ],
            "size": 99,
            "page": 0,
            "reference_system": system_name
        }

    @staticmethod
    def _normalize_body_id(body_id: Any) -> Any:
        if body_id is None:
            return None
        try:
            return int(body_id)
        except (TypeError, ValueError):
            return body_id

    @staticmethod
    def _map_spansh_signals(signals: Any) -> Optional[List[Dict[str, Any]]]:
        if not isinstance(signals, list):
            return None
        mapped: List[Dict[str, Any]] = []
        for signal in signals:
            if not isinstance(signal, dict):
                continue
            name = signal.get("name") or signal.get("type")
            if not name:
                continue
            entry: Dict[str, Any] = {
                "Type": name,
                "Type_Localised": name
            }
            if "count" in signal:
                entry["Count"] = signal.get("count")
            mapped.append(entry)
        return mapped

    @staticmethod
    def _map_spansh_genuses(genuses: Any) -> Optional[List[Dict[str, Any]]]:
        if not isinstance(genuses, list):
            return None
        mapped: List[Dict[str, Any]] = []
        for genus in genuses:
            if not isinstance(genus, dict):
                continue
            name = genus.get("name")
            if not name:
                continue
            mapped.append({
                "Genus": name,
                "Genus_Localised": name,
                "scanned": False
            })
        return mapped

    @staticmethod
    def _extract_spansh_system_id64(spansh_bodies: Any) -> Optional[int]:
        if not isinstance(spansh_bodies, list):
            return None
        for body in spansh_bodies:
            if not isinstance(body, dict):
                continue
            value = body.get("system_id64")
            if value is None:
                continue
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
        return None

    def _merge_spansh_bodies(self, system_name: str, spansh_bodies: Any) -> None:
        if not isinstance(spansh_bodies, list) or not spansh_bodies:
            return

        existing_data = self._get_system_record(system_name) or {}
        if not existing_data.get('star_address'):
            spansh_system_id64 = self._extract_spansh_system_id64(spansh_bodies)
            if spansh_system_id64 is not None:
                self._upsert_system_fields(system_name, {'star_address': spansh_system_id64})
        system_info = existing_data.get('system_info')
        if not isinstance(system_info, dict):
            return
        bodies = system_info.get('bodies')
        if not isinstance(bodies, list):
            return

        body_index: Dict[Any, Dict[str, Any]] = {}
        for body in bodies:
            if not isinstance(body, dict):
                continue
            raw_body_id = body.get("bodyId")
            if raw_body_id is None:
                raw_body_id = body.get("body_id")
            normalized_id = self._normalize_body_id(raw_body_id)
            if normalized_id is not None:
                body_index[normalized_id] = body

        updated = False
        for spansh_body in spansh_bodies:
            if not isinstance(spansh_body, dict):
                continue
            spansh_body_id = spansh_body.get("body_id")
            normalized_id = self._normalize_body_id(spansh_body_id)
            if normalized_id is None:
                continue
            body_entry = body_index.get(normalized_id)
            if body_entry is None:
                continue

            if "signals" in spansh_body:
                mapped_signals = self._map_spansh_signals(spansh_body.get("signals"))
                if mapped_signals is not None:
                    body_entry["signals"] = mapped_signals
                    updated = True

            if "genuses" in spansh_body:
                mapped_genuses = self._map_spansh_genuses(spansh_body.get("genuses"))
                if mapped_genuses is not None:
                    body_entry["genuses"] = mapped_genuses
                    updated = True

            if "landmarks" in spansh_body:
                landmarks = spansh_body.get("landmarks")
                if isinstance(landmarks, list):
                    body_entry["landmarks"] = landmarks
                    updated = True

            if "rings" in spansh_body and isinstance(spansh_body.get("rings"), list):
                target_rings = body_entry.get("rings")
                if isinstance(target_rings, list):
                    for spansh_ring in spansh_body.get("rings", []):
                        if not isinstance(spansh_ring, dict):
                            continue
                        if "signals" not in spansh_ring:
                            continue
                        ring_name = spansh_ring.get("name")
                        if not ring_name:
                            continue
                        for ring in target_rings:
                            if not isinstance(ring, dict):
                                continue
                            if ring.get("name") != ring_name:
                                continue
                            mapped_signals = self._map_spansh_signals(spansh_ring.get("signals"))
                            if mapped_signals is not None:
                                ring["signals"] = mapped_signals
                                updated = True
                            break

        if updated:
            self._upsert_system_fields(system_name, {'system_info': system_info})

    def _update_bodies_from_spansh(self, system_name: str) -> None:
        url = "https://spansh.co.uk/api/bodies/search"
        payload = self._build_spansh_bodies_request(system_name)
        headers = {
            "User-Agent": EDSM_USER_AGENT
        }
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        spansh_bodies = data.get("results", [])
        self._merge_spansh_bodies(system_name, spansh_bodies)

    async def _update_bodies_from_spansh_async(self, session: aiohttp.ClientSession, system_name: str) -> None:
        url = "https://spansh.co.uk/api/bodies/search"
        payload = self._build_spansh_bodies_request(system_name)
        headers = {
            "User-Agent": EDSM_USER_AGENT
        }
        async with session.post(url, json=payload, headers=headers) as response:
            response.raise_for_status()
            data = await response.json()
            spansh_bodies = data.get("results", [])
            self._merge_spansh_bodies(system_name, spansh_bodies)

    async def _fetch_multiple_systems_async(self, system_names: List[str], chunk_size: int = 50) -> None:
        """
        Fetch information for multiple systems in a single API call asynchronously

        Args:
            system_names: List of system names to fetch
            chunk_size: Size of chunks to split the request into (default: 50)
        """
        if not system_names:
            return

        # Process systems in chunks to avoid URL length issues
        system_chunks = [system_names[i:i + chunk_size] for i in range(0, len(system_names), chunk_size)]

        # Initialize empty records for all systems we're about to fetch
        # This avoids having to read before write in the processing methods
        current_time = time.time()
        for system_name in system_names:
            try:
                # Check if the system already exists
                system_data = self._get_system_record(system_name)
                if not system_data:
                    # Create a fresh record
                    self._upsert_system_fields(system_name, {
                        'fetch_attempted': 1,
                        'last_updated': current_time
                    })
            except Exception as e:
                log('error', f"Error initializing record for {system_name}: {e}")

        # Process chunks concurrently
        async with aiohttp.ClientSession() as session:
            tasks = []
            for chunk_index, chunk in enumerate(system_chunks):
                task = self._process_systems_chunk_async(session, chunk_index, chunk)
                tasks.append(task)

            # Wait for all chunks to be processed
            await asyncio.gather(*tasks)

    async def _process_systems_chunk_async(self, session: aiohttp.ClientSession, chunk_index: int,
                                           chunk: List[str]) -> None:
        """Process a chunk of systems asynchronously"""
        try:
            url = "https://www.edsm.net/api-v1/systems"
            params = {
                "showInformation": 1,
                "showPrimaryStar": 1,
                "systemName[]": chunk  # Pass the entire chunk as a list - aiohttp will format it properly
            }
            headers = {
                "User-Agent": EDSM_USER_AGENT
            }

            async with session.get(url, params=params, headers=headers) as response:
                response.raise_for_status()
                systems_data = await response.json()

                # Process the response and update our state
                station_tasks = []
                bodies_tasks = []
                for system_data in systems_data:
                    system_name = system_data.get('name')
                    if system_name:
                        try:
                            # Create a new record with this system info
                            # Instead of reading from the database and then writing,
                            # just create a new record with the data we have from the API
                            stored_data = {
                                'name': system_name,
                                'fetch_attempted': 1,
                                'last_updated': time.time(),
                                'system_info': system_data,
                                'star_address': system_data.get('id64', 0)
                            }

                            # Update the database with the new data
                            self._upsert_system_fields(system_name, stored_data)

                            # Queue station and bodies fetches for processing concurrently
                            station_tasks.append(self._fetch_stations_async(session, system_name))
                            bodies_tasks.append(self._fetch_bodies_async(session, system_name))
                        except Exception as e:
                            log('error', f"Error saving bulk system data for {system_name}: {e}",
                                traceback.format_exc())

                # Wait for all station and bodies fetches to complete
                tasks = station_tasks + bodies_tasks
                if tasks:
                    await asyncio.gather(*tasks)

        except Exception as e:
            error_msg = str(e)
            log('error', f"Error fetching systems chunk {chunk_index + 1} async: {error_msg}", traceback.format_exc())

            # Mark systems with error
            for system_name in chunk:
                try:
                    # Create a new error record instead of reading then updating
                    system_data = {
                        'name': system_name,
                        'fetch_attempted': 1,
                        'last_updated': time.time(),
                        'system_info': {"error": error_msg}
                    }
                    self._upsert_system_fields(system_name, system_data)
                except Exception as update_err:
                    log('error', f"Error updating system {system_name} with error info: {update_err}")

    # Methods to initiate async fetches but not block the caller
    def fetch_system_data_nonblocking(self, system_name: str) -> None:
        """
        Non-blocking wrapper to fetch system data asynchronously
        This spawns a thread that runs the async event loop
        """
        # Acquire a lock for this specific system
        with self._fetch_locks_lock:
            # Check if we're already fetching this system
            if system_name in self._fetch_locks:
                # Already fetching, don't start another thread
                return
            # Create a lock for this system
            self._fetch_locks[system_name] = threading.Lock()
        
        def run_async_fetch():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._fetch_system_data_async(system_name))
                finally:
                    loop.close()
            finally:
                # Clean up the lock when done
                with self._fetch_locks_lock:
                    if system_name in self._fetch_locks:
                        del self._fetch_locks[system_name]

        # Start the async operation in a separate thread
        thread = threading.Thread(target=run_async_fetch)
        thread.daemon = True
        thread.start()

    def fetch_multiple_systems_nonblocking(self, system_names: List[str], chunk_size: int = 50) -> None:
        """
        Non-blocking wrapper to fetch multiple systems asynchronously
        This spawns a thread that runs the async event loop
        """

        def run_async_fetch():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._fetch_multiple_systems_async(system_names, chunk_size))
            finally:
                loop.close()

        # Start the async operation in a separate thread
        thread = threading.Thread(target=run_async_fetch)
        thread.daemon = True
        thread.start()