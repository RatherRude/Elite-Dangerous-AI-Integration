from typing_extensions import override
from pydantic import BaseModel, Field

from ..Event import Event, GameEvent, ProjectedEvent, StatusEvent
from ..EventManager import Projection


class InDockingRangeStateModel(BaseModel):
    """Tracks prerequisites for emitting InDockingRange."""

    ReceivedFsdMassLocked: bool = Field(
        default=False, description="Whether FsdMassLocked has been observed"
    )
    ReceivedNoFireZoneEntered: bool = Field(
        default=False,
        description="Whether station no-fire-zone entry text has been observed",
    )
    SkipAnnouncement: bool = Field(
        default=False,
        description="Whether InDockingRange emission is suppressed for the current approach",
    )


class InDockingRange(Projection[InDockingRangeStateModel]):
    StateModel = InDockingRangeStateModel

    @override
    def process(self, event: Event) -> list[ProjectedEvent]:
        projected_events: list[ProjectedEvent] = []

        if (
            isinstance(event, StatusEvent)
            and event.status.get("event") == "FsdMassLocked"
        ):
            self.state.ReceivedFsdMassLocked = True
            if self.state.ReceivedNoFireZoneEntered and not self.state.SkipAnnouncement:
                projected_events.append(
                    ProjectedEvent(content={"event": "InDockingRange"})
                )
                self.state.SkipAnnouncement = True

        if not isinstance(event, GameEvent):
            return projected_events

        name = event.content.get("event")

        if name == "SupercruiseExit":
            taxi_mode = bool(event.content.get("Taxi", False))
            self.state = InDockingRangeStateModel(
                ReceivedFsdMassLocked=False,
                ReceivedNoFireZoneEntered=False,
                SkipAnnouncement=taxi_mode,
            )
            return projected_events

        if name == "ReceiveText":
            if (
                event.content.get("Channel") != "npc"
                or event.content.get("Message") != "$STATION_NoFireZone_entered;"
            ):
                return projected_events

            self.state.ReceivedNoFireZoneEntered = True
            if self.state.ReceivedFsdMassLocked and not self.state.SkipAnnouncement:
                projected_events.append(
                    ProjectedEvent(content={"event": "InDockingRange"})
                )
                self.state.SkipAnnouncement = True
            return projected_events

        if name in {
            "DockingGranted",
            "DockingDenied",
            "DockingCancelled",
            "DockingCanceled",
            "DockingTimeout",
            "DockingRequested",
        }:
            self.state.SkipAnnouncement = True

        return projected_events
