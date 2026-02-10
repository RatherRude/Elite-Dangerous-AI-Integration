from typing import cast

from typing_extensions import override
from pydantic import BaseModel, Field

from ..Event import Event, GameEvent, ProjectedEvent
from ..EventModels import FSSSignalDiscoveredEvent, LocationEvent
from ..EventManager import Projection


class FSSSignalsStateModel(BaseModel):
    """Current FSS signal discoveries in the system."""
    SystemAddress: int = Field(default=0, description="Unique system identifier")
    FleetCarrier: list[str] = Field(default_factory=list, description="Fleet carrier signals")
    ResourceExtraction: list[str] = Field(default_factory=list, description="Resource extraction site signals")
    Installation: list[str] = Field(default_factory=list, description="Installation signals")
    NavBeacon: list[str] = Field(default_factory=list, description="Navigation beacon signals")
    TouristBeacon: list[str] = Field(default_factory=list, description="Tourist beacon signals")
    Megaship: list[str] = Field(default_factory=list, description="Megaship signals")
    Generic: list[str] = Field(default_factory=list, description="Generic signals")
    Outpost: list[str] = Field(default_factory=list, description="Outpost signals")
    Combat: list[str] = Field(default_factory=list, description="Combat zone signals")
    Station: list[str] = Field(default_factory=list, description="Station signals")
    UnknownSignal: list[str] = Field(default_factory=list, description="Unknown signal types")


class FSSSignals(Projection[FSSSignalsStateModel]):
    StateModel = FSSSignalsStateModel

    def _reset_state(self, system_address: int) -> None:
        self.state.SystemAddress = system_address
        self.state.FleetCarrier.clear()
        self.state.ResourceExtraction.clear()
        self.state.Installation.clear()
        self.state.NavBeacon.clear()
        self.state.TouristBeacon.clear()
        self.state.Megaship.clear()
        self.state.Generic.clear()
        self.state.Outpost.clear()
        self.state.Combat.clear()
        self.state.Station.clear()
        self.state.UnknownSignal.clear()

    @override
    def process(self, event: Event) -> list[ProjectedEvent]:
        projected_events: list[ProjectedEvent] = []
        if isinstance(event, GameEvent) and event.content.get("event") == "Location":
            location = cast(LocationEvent, event.content)
            system_address = location.get("SystemAddress", 0)
            if not isinstance(system_address, int):
                system_address = 0
            self._reset_state(system_address)
        if isinstance(event, GameEvent) and event.content.get("event") == "FSSSignalDiscovered":
            signal = cast(FSSSignalDiscoveredEvent, event.content)
            signal_type = signal.get("SignalType", "Unknown")
            signal_name = signal.get("SignalName", "Unknown")
            system_address = signal.get("SystemAddress", 0)
            if not isinstance(signal_type, str):
                signal_type = "Unknown"
            if not isinstance(signal_name, str):
                signal_name = "Unknown"
            if not isinstance(system_address, int):
                system_address = 0
            if system_address != self.state.SystemAddress:
                # New system, clear previous signals
                self._reset_state(system_address)

            if hasattr(self.state, signal_type):
                getattr(self.state, signal_type).append(signal_name)
            else:
                if signal.get("IsStation"):
                    self.state.Station.append(signal_name)
                    signal_type = "Station"
                else:
                    self.state.UnknownSignal.append(signal_name)
                    signal_type = "UnknownSignal"

            projected_events.append(ProjectedEvent(content={"event": f"{signal_type}Discovered", "SignalName": signal_name}))

        if isinstance(event, GameEvent) and event.content.get("event") in ["FSDJump", "SupercruiseExit", "FSSDiscoveryScan"]:
            # These indicate that no more signals are discovered immediately, so we could batch on those
            pass

        return projected_events
