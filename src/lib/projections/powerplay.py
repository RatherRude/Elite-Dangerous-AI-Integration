from typing import cast

from typing_extensions import override
from pydantic import BaseModel, Field

from ..Event import Event, GameEvent
from ..EventModels import PowerplayEvent, PowerplayJoinEvent
from ..EventManager import Projection


class PowerplayStateModel(BaseModel):
    """Powerplay status of the commander."""
    Power: str = Field(default="Unknown", description="Power name")
    Rank: int = Field(default=0, description="Powerplay rank")
    Merits: int = Field(default=0, description="Current merits")
    TimePledged: int = Field(default=0, description="Seconds pledged to the power")
    Timestamp: str = Field(default="1970-01-01T00:00:00Z", description="Timestamp of last Powerplay event")


class Powerplay(Projection[PowerplayStateModel]):
    StateModel = PowerplayStateModel

    def _reset_state(self) -> None:
        self.state.Power = "Unknown"
        self.state.Rank = 0
        self.state.Merits = 0
        self.state.TimePledged = 0
        self.state.Timestamp = "1970-01-01T00:00:00Z"

    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent):
            event_name = event.content.get("event")

            if event_name == "Powerplay":
                payload = cast(PowerplayEvent, event.content)
                power_name = payload.get("Power", "Unknown")
                rank_value = payload.get("Rank", 0)
                merits_value = payload.get("Merits", 0)
                time_pledged = payload.get("TimePledged", 0)
                self.state.Power = power_name if isinstance(power_name, str) else "Unknown"
                self.state.Rank = rank_value if isinstance(rank_value, int) else 0
                self.state.Merits = merits_value if isinstance(merits_value, int) else 0
                self.state.TimePledged = time_pledged if isinstance(time_pledged, int) else 0
                if "timestamp" in payload:
                    self.state.Timestamp = payload["timestamp"]

            if event_name == "PowerplayMerits":
                total_merits = event.content.get("TotalMerits", self.state.Merits)
                if isinstance(total_merits, int):
                    self.state.Merits = total_merits
                timestamp = event.content.get("timestamp")
                if isinstance(timestamp, str):
                    self.state.Timestamp = timestamp

            if event_name == "PowerplayRank":
                rank_value = event.content.get("Rank", self.state.Rank)
                if isinstance(rank_value, int):
                    self.state.Rank = rank_value
                timestamp = event.content.get("timestamp")
                if isinstance(timestamp, str):
                    self.state.Timestamp = timestamp

            if event_name == "PowerplayJoin":
                payload = cast(PowerplayJoinEvent, event.content)
                self.state.Power = payload.get("Power", "Unknown")
                self.state.Rank = 0
                self.state.Merits = 0
                self.state.TimePledged = 0
                if "timestamp" in payload:
                    self.state.Timestamp = payload["timestamp"]

            if event_name == "PowerplayDefect":
                power_name = event.content.get("ToPower", "Unknown")
                if isinstance(power_name, str):
                    self.state.Power = power_name
                self.state.Rank = 0
                self.state.Merits = 0
                self.state.TimePledged = 0
                timestamp = event.content.get("timestamp")
                if isinstance(timestamp, str):
                    self.state.Timestamp = timestamp

            if event_name == "PowerplayLeave":
                self._reset_state()
