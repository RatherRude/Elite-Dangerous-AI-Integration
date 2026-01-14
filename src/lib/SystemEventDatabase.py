import threading
import time
from typing import Any, Callable, Dict, List, Optional

from .Database import KeyValueStore
from .Logger import log


class SystemEventDatabase:
    """
    Event-driven database that persists locally observed system data.

    This database is populated exclusively from game events (no online calls).
    It keeps a lightweight in-memory cache of the last record we attempted to
    persist so we can extend that record on subsequent writes. If nothing was
    cached, we fall back to the stored record; if none exists, we create a new
    record.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_items: Dict[str, Dict[str, Any]] = {}
        try:
            # Separate table from the online-backed SystemDatabase
            self.systems_store = KeyValueStore("systems_events")
        except Exception as exc:  # pragma: no cover - defensive
            log("error", f"Error creating systems_events store: {exc}")
            raise

    # Public API -----------------------------------------------------------------
    def record_discovery_scan(self, event: Dict[str, Any]) -> None:
        """
        Persist totals from FSSDiscoveryScan.
        Expected payload: BodyCount, NonBodyCount, SystemName, SystemAddress, Progress, timestamp.
        """
        system_address = event.get("SystemAddress")
        if system_address is None:
            return
        system_name = event.get("SystemName")
        body_count = int(event.get("BodyCount", 0))
        non_body_count = int(event.get("NonBodyCount", 0))

        def updater(record: Dict[str, Any]) -> None:
            self._ensure_defaults(record, system_name, system_address)
            totals = record.setdefault("totals", {})
            totals["bodies"] = body_count
            totals["non_bodies"] = non_body_count

        self._update(system_address, system_name, updater)

    def record_fsd_target(self, event: Dict[str, Any]) -> None:
        """
        Persist system name (and optional star class) from FSDTarget.
        """
        system_address = event.get("SystemAddress")
        if system_address is None:
            return
        system_name = event.get("Name")
        star_class = event.get("StarClass")

        def updater(record: Dict[str, Any]) -> None:
            self._ensure_defaults(record, system_name, system_address)
            if star_class:
                record["star_class"] = star_class

        self._update(system_address, system_name, updater)

    def record_scan(self, event: Dict[str, Any]) -> None:
        """
        Persist body scan details (basic/detailed) from Scan events.
        """
        system_address = event.get("SystemAddress")
        if system_address is None:
            return
        system_name = event.get("StarSystem")
        body_name = event.get("BodyName")
        body_id = event.get("BodyID")
        if body_id is None or body_name is None:
            return
        scan_type = event.get("ScanType", "Unknown")
        planet_class = event.get("PlanetClass") or event.get("BodyType") or "Unknown"
        was_discovered = bool(event.get("WasDiscovered", False))
        was_mapped = bool(event.get("WasMapped", False))
        was_footfalled = bool(event.get("WasFootfalled", False))
        timestamp = event.get("timestamp")
        parents = event.get("Parents")

        def updater(record: Dict[str, Any]) -> None:
            self._ensure_defaults(record, system_name, system_address)
            self._upsert_body(
                record,
                body_id=body_id,
                body_name=body_name,
                body_type=planet_class,
                scan_type=scan_type,
                was_discovered=was_discovered,
                was_mapped=was_mapped,
                was_footfalled=was_footfalled,
                timestamp=timestamp,
                parents=parents,
                scan_event=event,
            )

        self._update(system_address, system_name, updater)

    def record_signal(self, event: Dict[str, Any]) -> None:
        """
        Persist signals discovered via FSSSignalDiscovered.
        Stations are treated as signals with isStation=True and are also stored
        in the stations list.
        """
        system_address = event.get("SystemAddress")
        if system_address is None:
            return
        system_name = event.get("SystemName")
        signal_name = event.get("SignalName_Localised", "Unknown")
        signal_type = event.get("SignalType", "Unknown")
        is_station = bool(event.get("IsStation", False))

        def updater(record: Dict[str, Any]) -> None:
            self._ensure_defaults(record, system_name, system_address)
            signal_entry = {
                "name": signal_name,
                "type": signal_type,
            }
            # Record stations only in the stations list; carriers stay as signals.
            if is_station and signal_type not in ("FleetCarrier", "SquadCarrier"):
                self._add_station(record, signal_name, signal_type)
            else:
                self._add_unique(record, "signals", signal_entry, field_key="name")

        self._update(system_address, system_name, updater)

    def record_saa_signals_found(self, event: Dict[str, Any]) -> None:
        """
        Persist SAA signals (exobiology) for a specific body.
        """
        system_address = event.get("SystemAddress")
        if system_address is None:
            return
        system_name = event.get("StarSystem")
        body_name = event.get("BodyName")
        body_id = event.get("BodyID")
        if body_id is None:
            return

        signals = event.get("Signals", [])
        genuses = event.get("Genuses", [])

        def updater(record: Dict[str, Any]) -> None:
            self._ensure_defaults(record, system_name, system_address)
            body = self._ensure_body(record, body_id, body_name, None)
            existing_signals = {s.get("Type"): s for s in body.get("signals", []) if s.get("Type")}
            for sig in signals:
                sig_type = sig.get("Type")
                if sig_type in existing_signals:
                    existing_signals[sig_type].update(sig)
                else:
                    if sig_type:
                        existing_signals[sig_type] = sig
            body["signals"] = list(existing_signals.values())

            existing_genus = {g.get("Genus"): g for g in body.get("genuses", []) if g.get("Genus")}
            for g in genuses:
                genus_key = g.get("Genus")
                if genus_key in existing_genus:
                    existing = existing_genus[genus_key]
                    # preserve scanned flag if already set
                    scanned = existing.get("scanned", False)
                    existing.update(g)
                    existing["scanned"] = scanned
                else:
                    if genus_key:
                        entry = dict(g)
                        entry.setdefault("scanned", False)
                        existing_genus[genus_key] = entry
            body["genuses"] = list(existing_genus.values())

        self._update(system_address, system_name, updater)

    def record_scan_organic(self, event: Dict[str, Any]) -> None:
        """
        Mark a genus as scanned for a body when ScanOrganic (Analyse) is received.
        """
        if event.get("ScanType") != "Analyse":
            return
        system_address = event.get("SystemAddress")
        if system_address is None:
            return
        body_id = event.get("Body")
        if body_id is None:
            return
        system_name = event.get("StarSystem") or event.get("SystemName")
        genus = event.get("Genus")
        genus_localised = event.get("Genus_Localised")
        species = event.get("Species")
        species_localised = event.get("Species_Localised")

        def updater(record: Dict[str, Any]) -> None:
            self._ensure_defaults(record, system_name, system_address)
            body = self._ensure_body(record, body_id, None, None)
            genuses_list = body.get("genuses", [])
            genus_map = {g.get("Genus"): g for g in genuses_list if g.get("Genus")}

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

            body["genuses"] = genuses_list

        self._update(system_address, system_name, updater)

    def get_system(self, system_address: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve the persisted event data for a system by address.
        Returns a shallow copy of the stored record or None if not found.
        """
        try:
            key = self._make_key(system_address)
            with self._lock:
                record = self._last_items.get(key)
                if not record:
                    record = self.systems_store.get(key)
                if not record:
                    return None
                return record.copy()
        except Exception as exc:  # pragma: no cover - defensive
            log("error", f"Error reading event system data for {system_address}: {exc}")
            return None

    # Internal helpers -----------------------------------------------------------
    def _update(
        self,
        system_address: int,
        system_name: Optional[str],
        mutator: Callable[[Dict[str, Any]], None],
    ) -> None:
        """
        Load (or create) the record, allow the caller to mutate it, then persist.
        Uses an in-memory cache of the last record we touched to avoid
        rehydrating on every call.
        """
        try:
            with self._lock:
                record = self._get_record_for_update(system_address, system_name)
                mutator(record)
                record["last_updated"] = time.time()
                key = self._make_key(system_address)
                self.systems_store.set(key, record)
                self._last_items[key] = record
        except Exception as exc:  # pragma: no cover - defensive
            log("error", f"Error updating event system data for {system_address}: {exc}")

    def _get_record_for_update(self, system_address: int, system_name: Optional[str]) -> Dict[str, Any]:
        key = self._make_key(system_address)
        record = self._last_items.get(key)
        if not record:
            record = self.systems_store.get(key)

        if not record:
            record = self._blank_record(system_name, system_address)
        else:
            record = record.copy()
            self._ensure_defaults(record, system_name, system_address)
            if system_address and not record.get("system_address"):
                record["system_address"] = system_address
        return record

    def _blank_record(self, system_name: Optional[str], system_address: int) -> Dict[str, Any]:
        return {
            "name": system_name,
            "system_address": system_address,
            "last_updated": time.time(),
            "bodies": {},
            "signals": [],
            "stations": [],
            "totals": {},
        }

    def _ensure_defaults(
        self, record: Dict[str, Any], system_name: Optional[str], system_address: int
    ) -> None:
        if system_name and (not record.get("name") or record.get("name") == "Unknown"):
            record["name"] = system_name
        if not record.get("name"):
            record["name"] = "Unknown"
        if system_address and not record.get("system_address"):
            record["system_address"] = system_address
        record.setdefault("bodies", {})
        record.setdefault("signals", [])
        record.setdefault("stations", [])
        record.setdefault("totals", {})

    def _add_unique(
        self,
        record: Dict[str, Any],
        list_key: str,
        entry: Dict[str, Any],
        match: Optional[Callable[[Dict[str, Any]], bool]] = None,
        *,
        field_key: Optional[str] = None,
    ) -> None:
        """
        Append entry to record[list_key] if not already present.
        Uniqueness can be provided via a callable match or by a field name.
        """
        items: List[Dict[str, Any]] = record.get(list_key, [])
        if match:
            if any(match(item) for item in items):
                return
        elif field_key:
            if any(item.get(field_key) == entry.get(field_key) for item in items):
                return
        else:
            if entry in items:
                return
        items.append(entry)
        record[list_key] = items

    def _add_station(
        self, record: Dict[str, Any], station_name: str, station_type: Optional[str] = None
    ) -> None:
        station_entry = {
            "name": station_name,
            "type": station_type or "Station",
        }
        self._add_unique(record, "stations", station_entry, field_key="name")

    def _make_key(self, system_address: int) -> str:
        return str(system_address)

    def _upsert_body(
        self,
        record: Dict[str, Any],
        body_id: int,
        body_name: str,
        body_type: Optional[str],
        scan_type: Optional[str],
        was_discovered: bool,
        was_mapped: bool,
        was_footfalled: bool,
        timestamp: Optional[str],
        parents: Optional[Any],
        scan_event: Optional[Dict[str, Any]],
    ) -> None:
        body = self._ensure_body(record, body_id, body_name, body_type)

        if body_type and body.get("type") in ("Unknown", None):
            body["type"] = body_type

        scan_type_lower = (scan_type or "").lower()
        if scan_type_lower == "detailed" or scan_type_lower == "navbeacondetail":
            body["detailed_scanned"] = True
        else:
            body.setdefault("detailed_scanned", False)

        body["was_discovered"] = was_discovered or body.get("was_discovered", False)
        body["was_mapped"] = was_mapped or body.get("was_mapped", False)
        body["was_footfalled"] = was_footfalled or body.get("was_footfalled", False)

        if parents is not None:
            body["parents"] = parents

        if scan_event:
            self._merge_scan_properties(body, scan_event)

        record["bodies"][body_id] = body

    def _ensure_body(
        self,
        record: Dict[str, Any],
        body_id: int,
        body_name: Optional[str],
        body_type: Optional[str],
    ) -> Dict[str, Any]:
        bodies: Dict[int, Dict[str, Any]] = record.setdefault("bodies", {})
        if body_id not in bodies:
            bodies[body_id] = {
                "body_id": body_id,
                "name": body_name,
                "type": body_type or "Unknown",
                "detailed_scanned": False,
                "was_discovered": False,
                "was_mapped": False,
                "was_footfalled": False,
                "signals": [],
                "genuses": [],
            }
        else:
            if body_name and (not bodies[body_id].get("name") or bodies[body_id].get("name") == "Unknown"):
                bodies[body_id]["name"] = body_name
            if body_type and bodies[body_id].get("type") in ("Unknown", None):
                bodies[body_id]["type"] = body_type
        return bodies[body_id]

    def _merge_scan_properties(self, body: Dict[str, Any], scan_event: Dict[str, Any]) -> None:
        """
        Copy key orbital/physical properties from the scan payload for later use (e.g., orrery).
        """
        fields = [
            "DistanceFromArrivalLS",
            "MassEM",
            "Radius",
            "SurfaceGravity",
            "SurfaceTemperature",
            "SurfacePressure",
            "Landable",
            "Materials",
            "Composition",
            "SemiMajorAxis",
            "Eccentricity",
            "OrbitalInclination",
            "Periapsis",
            "OrbitalPeriod",
            "AscendingNode",
            "MeanAnomaly",
            "RotationPeriod",
            "AxialTilt",
            "TidalLock",
            "TerraformState",
            "Atmosphere",
            "AtmosphereType",
            "Volcanism",
            "PlanetClass",
            "StarType",
            "BodyType",
        ]
        for key in fields:
            if key in scan_event:
                body[key] = scan_event[key]
