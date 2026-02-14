from typing import Optional, cast

from typing_extensions import override
from pydantic import BaseModel, Field

from ..Event import Event, GameEvent, ProjectedEvent
from ..EventModels import FSDJumpEvent, FSDTargetEvent, NavRouteEvent, ScanEvent, FSSBodySignalsEvent
from ..EventManager import Projection
from ..SystemDatabase import SystemDatabase


class NavRouteItem(BaseModel):
    """A waypoint in the navigation route."""
    StarSystem: str = Field(description="Star system name")
    Scoopable: bool = Field(description="Whether the star is fuel-scoopable (K/G/B/F/O/A/M class)")
    StarClass: str | None = Field(default=None, description="Star class (K/G/B/F/O/A/M/etc.)")
    SystemAddress: int | None = Field(default=None, description="System address")
    StarPos: list[float] | None = Field(default=None, description="System position in galactic coordinates")


class NavInfoStateModel(BaseModel):
    """Current navigation and route information."""
    NextJumpTarget: Optional[str] = Field(default="Unknown", description="Next FSD target system")
    NavRoute: list[NavRouteItem] = Field(default_factory=list, description="Remaining systems in plotted route")


class NavInfo(Projection[NavInfoStateModel]):
    StateModel = NavInfoStateModel

    def __init__(self, system_db: SystemDatabase):
        super().__init__()
        self.system_db = system_db

    @staticmethod
    def _normalize_token(value: str) -> str:
        return value.strip().lower().replace(" ", "").replace("_", "").replace("-", "")

    def _extract_faction_states(self, event_content: object) -> set[str]:
        states: set[str] = set()
        if not isinstance(event_content, dict):
            return states

        system_faction = event_content.get("SystemFaction", {})
        if isinstance(system_faction, dict):
            faction_state = system_faction.get("FactionState")
            if isinstance(faction_state, str) and faction_state:
                states.add(self._normalize_token(faction_state))

        factions = event_content.get("Factions", [])
        if isinstance(factions, list):
            for faction in factions:
                if not isinstance(faction, dict):
                    continue
                faction_state = faction.get("FactionState")
                if isinstance(faction_state, str) and faction_state:
                    states.add(self._normalize_token(faction_state))

                active_states = faction.get("ActiveStates", [])
                if isinstance(active_states, list):
                    for active_state in active_states:
                        if not isinstance(active_state, dict):
                            continue
                        state_name = active_state.get("State")
                        if isinstance(state_name, str) and state_name:
                            states.add(self._normalize_token(state_name))

        return states

    def _get_hge_candidate_materials(self, event_content: object) -> tuple[list[str], set[str]]:
        if not isinstance(event_content, dict):
            return [], set()

        population = event_content.get("Population", 0)
        if not isinstance(population, int) or population <= 1_000_000:
            return [], set()

        allegiance_value = event_content.get("SystemAllegiance", "")
        allegiance = self._normalize_token(allegiance_value) if isinstance(allegiance_value, str) else ""
        states = self._extract_faction_states(event_content)
        materials: set[str] = set()

        if "outbreak" in states:
            materials.add("Pharmaceutical Isolators")
        if {"war", "civilwar", "civilunrest"} & states:
            materials.add("Military Grade Alloys")
        if "boom" in states:
            materials.add("Proto Heat Radiators")
            materials.add("Proto Radiolic Alloys")
        if allegiance == "independent" and "civilunrest" in states:
            materials.add("Improvised Components")
        if allegiance in {"independent", "alliance"} and {"war", "civilwar"} & states:
            materials.add("Military Supercapacitors")
        if allegiance == "imperial" and ({"none", "election"} & states):
            materials.add("Imperial Shielding")
        if allegiance == "federation":
            materials.add("Core Dynamics Composites")

        return sorted(materials), states


    @override
    def process(self, event: Event) -> list[ProjectedEvent]:
        projected_events: list[ProjectedEvent] = []

        # Process NavRoute event
        if isinstance(event, GameEvent) and event.content.get("event") == "NavRoute":
            payload = cast(NavRouteEvent, event.content)
            route_entries = payload.get("Route")
            if isinstance(route_entries, list) and route_entries:
                self.state.NavRoute = []
                systems_to_lookup = []

                # Process all systems in a single loop
                is_first_system = True
                for entry in route_entries:
                    if not isinstance(entry, dict):
                        continue
                    star_system = entry.get("StarSystem", "Unknown")
                    if not isinstance(star_system, str):
                        star_system = "Unknown"
                    star_class = entry.get("StarClass", "")
                    if not isinstance(star_class, str):
                        star_class = ""
                    is_scoopable = star_class in ["K", "G", "B", "F", "O", "A", "M"]
                    system_address = entry.get("SystemAddress")
                    star_pos = entry.get("StarPos")

                    # Add all systems to the lookup list
                    systems_to_lookup.append(star_system)

                    # Add to projection state (skip the first one)
                    if not is_first_system:
                        self.state.NavRoute.append(NavRouteItem(
                            StarSystem=star_system,
                            Scoopable=is_scoopable,
                            StarClass=star_class or None,
                            SystemAddress=system_address if isinstance(system_address, int) else None,
                            StarPos=star_pos if isinstance(star_pos, list) else None,
                        ))
                    else:
                        # No longer the first system after the first iteration
                        is_first_system = False

                # Fetch system data for systems in the route asynchronously
                if len(systems_to_lookup) > 1:
                    systems_to_lookup.pop(0)
                    self.system_db.fetch_multiple_systems_nonblocking(systems_to_lookup)

        # Process NavRouteClear
        if isinstance(event, GameEvent) and event.content.get("event") == "NavRouteClear":
            self.state.NavRoute = []

        # Process FSDJump - remove visited systems from route
        if isinstance(event, GameEvent) and event.content.get("event") == "FSDJump":
            payload = cast(FSDJumpEvent, event.content)
            for index, entry in enumerate(self.state.NavRoute):
                if entry.StarSystem == payload.get("StarSystem"):
                    self.state.NavRoute = self.state.NavRoute[index + 1 :]
                    break

            if len(self.state.NavRoute) == 0 and self.state.NextJumpTarget is not None:
                self.state.NextJumpTarget = None

            # Calculate remaining jumps based on fuel
            fuel_level = payload.get("FuelLevel", 0.0)
            fuel_used = payload.get("FuelUsed", 0.0)
            if isinstance(fuel_level, (int, float)) and isinstance(fuel_used, (int, float)) and fuel_used:
                remaining_jumps = int(fuel_level / fuel_used)
            else:
                remaining_jumps = 0

            # Check if we have enough scoopable stars between current and destination system)
            if not len(self.state.NavRoute) == 0 and remaining_jumps < len(self.state.NavRoute) - 1:
                # Count scoopable stars in the remaining jumps
                scoopable_stars = sum(
                    1
                    for entry in self.state.NavRoute[:remaining_jumps]
                    if entry.Scoopable
                )

                # Only warn if we can't reach any scoopable stars
                if scoopable_stars == 0:
                    projected_events.append(ProjectedEvent(content={"event": "NoScoopableStars"}))

            hge_materials, matched_states = self._get_hge_candidate_materials(event.content)
            if hge_materials:
                projected_events.append(ProjectedEvent(content={
                    "event": "HGECandidateFound",
                    "StarSystem": event.content.get("StarSystem", "Unknown"),
                    "SystemAddress": event.content.get("SystemAddress"),
                    "SystemAllegiance": event.content.get("SystemAllegiance"),
                    "Population": event.content.get("Population", 0),
                    "HGECandidateMaterials": hge_materials,
                    "HGEMatchedStates": sorted(matched_states),
                }))

        # Process FSDTarget
        if isinstance(event, GameEvent) and event.content.get("event") == "FSDTarget":
            payload = cast(FSDTargetEvent, event.content)
            system_name = payload.get("Name")
            if isinstance(system_name, str):
                self.state.NextJumpTarget = system_name

        if isinstance(event, GameEvent) and event.content.get("event") == "Scan":
            payload = cast(ScanEvent, event.content)
            auto_scan = payload.get("ScanType")
            if not isinstance(auto_scan, str):
                auto_scan = ""
            distancefromarrival = payload.get("DistanceFromArrivalLS", 1.0)
            
            if auto_scan == "AutoScan" and isinstance(distancefromarrival, (int, float)) and distancefromarrival < 0.2:
                was_discovered = payload.get("WasDiscovered", True)

                if was_discovered is False:
                    projected_events.append(ProjectedEvent(content={"event": "FirstPlayerSystemDiscovered"}))

        if isinstance(event, GameEvent) and event.content.get("event") == "FSSBodySignals":
            payload = cast(FSSBodySignalsEvent, event.content)
            signals = payload.get("Signals", [])
            if isinstance(signals, list):
                biological_count: int | None = None
                for s in signals:
                    if isinstance(s, dict) and s.get("Type") == "$SAA_SignalType_Biological;":
                        biological_count = s.get("Count")
                        break
                if biological_count is not None:
                    count = biological_count if isinstance(biological_count, int) else 0
                    projected_events.append(ProjectedEvent(content={
                        "event": "FSSBiologicalSignals",
                        "BodyName": payload.get("BodyName"),
                        "Count": count,
                    }))

        return projected_events
