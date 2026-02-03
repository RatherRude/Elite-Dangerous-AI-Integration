from typing import cast

from typing_extensions import override
from pydantic import BaseModel, Field

from ..Event import Event, GameEvent, ProjectedEvent
from ..EventManager import Projection
from ..EventModels import (
    DockedEvent,
    DockingCancelledEvent,
    DockingDeniedEvent,
    DockingGrantedEvent,
    DockingRequestedEvent,
    DockingTimeoutEvent,
    MusicEvent,
    UndockedEvent,
)


class DockingEventsStateModel(BaseModel):
    """Current docking status and events."""
    StationType: str = Field(default="Unknown", description="Type of station (Coriolis/Orbis/Ocellus/Outpost/etc.)")
    LastEventType: str = Field(default="Unknown", description="Last docking-related event type")
    DockingComputerState: str = Field(default="deactivated", description="Docking computer state: deactivated/activated/auto-docking")
    Timestamp: str = Field(default="1970-01-01T00:00:00Z", description="Timestamp of last docking event")


class DockingEvents(Projection[DockingEventsStateModel]):
    StateModel = DockingEventsStateModel

    @override
    def process(self, event: Event) -> list[ProjectedEvent] | None:
        projected_events: list[ProjectedEvent] = []

        if isinstance(event, GameEvent) and event.content.get("event") in [
            "Docked",
            "Undocked",
            "DockingGranted",
            "DockingRequested",
            "DockingCanceled",
            "DockingDenied",
            "DockingTimeout",
        ]:
            payload = cast(
                DockedEvent | UndockedEvent | DockingGrantedEvent | DockingRequestedEvent | DockingCancelledEvent | DockingDeniedEvent | DockingTimeoutEvent,
                event.content,
            )
            station_type = payload.get("StationType", "Unknown")
            if not isinstance(station_type, str):
                station_type = "Unknown"
            event_type = payload.get("event", "Unknown")
            if not isinstance(event_type, str):
                event_type = "Unknown"
            self.state.DockingComputerState = "deactivated"
            self.state.StationType = station_type
            self.state.LastEventType = event_type
            timestamp = payload.get("timestamp")
            if isinstance(timestamp, str):
                self.state.Timestamp = timestamp

        if isinstance(event, GameEvent) and event.content.get("event") == "Music":
            payload = cast(MusicEvent, event.content)
            if payload.get("MusicTrack", "Unknown") == "DockingComputer":
                self.state.DockingComputerState = "activated"
                if self.state.LastEventType == "DockingGranted":
                    self.state.DockingComputerState = "auto-docking"
                    projected_events.append(ProjectedEvent(content={"event": "DockingComputerDocking"}))

                elif self.state.LastEventType == "Undocked" and self.state.StationType in ["Coriolis", "Orbis", "Ocellus"]:
                    self.state.DockingComputerState = "auto-docking"
                    projected_events.append(ProjectedEvent(content={"event": "DockingComputerUndocking"}))

            elif self.state.DockingComputerState == "auto-docking":
                self.state.DockingComputerState = "deactivated"
                projected_events.append(ProjectedEvent(content={"event": "DockingComputerDeactivated"}))

        return projected_events
