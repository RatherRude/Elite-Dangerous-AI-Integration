from typing import Optional, cast

from typing_extensions import override
from pydantic import BaseModel, Field

from ..Event import Event, GameEvent, ProjectedEvent
from ..EventModels import ShipTargetedEvent
from ..EventManager import Projection


class TargetStateModel(BaseModel):
    """Information about the currently targeted ship or entity."""
    EventID: Optional[str] = Field(default=None, description="Event identifier")
    Ship: Optional[str] = Field(default=None, description="Target ship type")
    ScanStage: Optional[int] = Field(default=None, description="Scan completion stage (0-3)")
    PilotName: Optional[str] = Field(default=None, description="Target pilot name")
    PilotRank: Optional[str] = Field(default=None, description="Target pilot combat rank")
    Faction: Optional[str] = Field(default=None, description="Target's faction")
    LegalStatus: Optional[str] = Field(default=None, description="Target's legal status")
    Bounty: Optional[int] = Field(default=None, description="Bounty on target in credits")
    ShieldHealth: Optional[float] = Field(default=None, description="Target shield health percentage")
    HullHealth: Optional[float] = Field(default=None, description="Target hull health percentage")
    SubsystemHealth: Optional[float] = Field(default=None, description="Targeted subsystem health percentage")
    Subsystem: Optional[str] = Field(default=None, description="Currently targeted subsystem name")


class Target(Projection[TargetStateModel]):
    StateModel = TargetStateModel

    def _reset_state(self) -> None:
        self.state.EventID = None
        self.state.Ship = None
        self.state.ScanStage = None
        self.state.PilotName = None
        self.state.PilotRank = None
        self.state.Faction = None
        self.state.LegalStatus = None
        self.state.Bounty = None
        self.state.ShieldHealth = None
        self.state.HullHealth = None
        self.state.SubsystemHealth = None
        self.state.Subsystem = None

    @override
    def process(self, event: Event) -> list[ProjectedEvent]:
        projected_events: list[ProjectedEvent] = []

        if isinstance(event, GameEvent) and event.content.get("event") in ["LoadGame", "Shutdown"]:
            self._reset_state()
        if isinstance(event, GameEvent) and event.content.get("event") == "ShipTargeted":
            payload = cast(ShipTargetedEvent, event.content)
            if not payload.get("TargetLocked", False):
                self._reset_state()
            else:
                self._reset_state()
                ship_name = payload.get("Ship_Localised", payload.get("Ship", ""))
                if isinstance(ship_name, str):
                    self.state.Ship = ship_name
                scan_stage = payload.get("ScanStage", 0)
                if isinstance(scan_stage, int):
                    self.state.ScanStage = scan_stage

                pilot_name_value = payload.get("PilotName_Localised") or payload.get("PilotName")
                if isinstance(pilot_name_value, str) and pilot_name_value:
                    self.state.PilotName = pilot_name_value

                if "PilotRank" in payload:
                    pilot_rank = payload.get("PilotRank", "")
                    if isinstance(pilot_rank, str):
                        self.state.PilotRank = pilot_rank

                if "Faction" in payload:
                    faction = payload.get("Faction", "")
                    if isinstance(faction, str):
                        self.state.Faction = faction

                if "LegalStatus" in payload:
                    legal_status = payload.get("LegalStatus", "")
                    if isinstance(legal_status, str):
                        self.state.LegalStatus = legal_status

                if "Bounty" in payload:
                    bounty_value = payload.get("Bounty", 0)
                    if isinstance(bounty_value, int):
                        self.state.Bounty = bounty_value
                        if bounty_value > 1 and not payload.get("Subsystem", False):
                            projected_events.append(ProjectedEvent(content={"event": "BountyScanned"}))

                if "ShieldHealth" in payload:
                    shield_value = payload.get("ShieldHealth", 0.0)
                    if isinstance(shield_value, (int, float)):
                        self.state.ShieldHealth = float(shield_value)

                if "HullHealth" in payload:
                    hull_value = payload.get("HullHealth", 0.0)
                    if isinstance(hull_value, (int, float)):
                        self.state.HullHealth = float(hull_value)

                if "SubsystemHealth" in payload:
                    subsystem_health = payload.get("SubsystemHealth", 0.0)
                    if isinstance(subsystem_health, (int, float)):
                        self.state.SubsystemHealth = float(subsystem_health)

                subsystem_value = payload.get("Subsystem_Localised", payload.get("Subsystem", ""))
                if isinstance(subsystem_value, str) and subsystem_value:
                    self.state.Subsystem = subsystem_value
            event_id = event.content.get("id")
            if event_id is not None:
                self.state.EventID = str(event_id)
        return projected_events
