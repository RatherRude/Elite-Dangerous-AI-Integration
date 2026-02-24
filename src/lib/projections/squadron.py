from typing import cast

from typing_extensions import override
from pydantic import BaseModel, Field

from ..Event import Event, GameEvent
from ..EventModels import SquadronStartupEvent
from ..EventManager import Projection


class SquadronStateModel(BaseModel):
    """Current squadron membership state."""
    SquadronID: int = Field(default=0, description="Squadron identifier")
    SquadronName: str = Field(default="Unknown", description="Squadron name")
    CurrentRank: int = Field(default=0, description="Current squadron rank")
    CurrentRankName: str = Field(default="Unknown", description="Current squadron rank name")
    Status: str = Field(default="None", description="Membership status")
    Timestamp: str = Field(default="1970-01-01T00:00:00Z", description="Timestamp of last squadron event")


class Squadron(Projection[SquadronStateModel]):
    StateModel = SquadronStateModel

    def _reset_state(self) -> None:
        self.state.SquadronID = 0
        self.state.SquadronName = "Unknown"
        self.state.CurrentRank = 0
        self.state.CurrentRankName = "Unknown"
        self.state.Status = "None"
        self.state.Timestamp = "1970-01-01T00:00:00Z"

    @override
    def process(self, event: Event) -> None:
        if not isinstance(event, GameEvent):
            return

        event_name = event.content.get("event")

        if event_name == "SquadronStartup":
            payload = cast(SquadronStartupEvent, event.content)
            squadron_id = payload.get("SquadronID", 0)
            squadron_name = payload.get("SquadronName", "Unknown")
            current_rank = payload.get("CurrentRank", 0)
            current_rank_name = payload.get("CurrentRankName", "Unknown")
            self.state.SquadronID = squadron_id if isinstance(squadron_id, int) else 0
            self.state.SquadronName = squadron_name if isinstance(squadron_name, str) else "Unknown"
            self.state.CurrentRank = current_rank if isinstance(current_rank, int) else 0
            self.state.CurrentRankName = current_rank_name if isinstance(current_rank_name, str) else "Unknown"
            self.state.Status = "Member"
            if "timestamp" in payload:
                self.state.Timestamp = payload["timestamp"]

        if event_name == "AppliedToSquadron":
            squadron_name = event.content.get("SquadronName", self.state.SquadronName)
            if isinstance(squadron_name, str):
                self.state.SquadronName = squadron_name
            self.state.Status = "Applied"
            timestamp = event.content.get("timestamp")
            if isinstance(timestamp, str):
                self.state.Timestamp = timestamp

        if event_name == "InvitedToSquadron":
            squadron_name = event.content.get("SquadronName", self.state.SquadronName)
            if isinstance(squadron_name, str):
                self.state.SquadronName = squadron_name
            self.state.Status = "Invited"
            timestamp = event.content.get("timestamp")
            if isinstance(timestamp, str):
                self.state.Timestamp = timestamp

        if event_name == "JoinedSquadron":
            squadron_name = event.content.get("SquadronName", self.state.SquadronName)
            if isinstance(squadron_name, str):
                self.state.SquadronName = squadron_name
            self.state.Status = "Member"
            timestamp = event.content.get("timestamp")
            if isinstance(timestamp, str):
                self.state.Timestamp = timestamp

        if event_name == "SquadronCreated":
            squadron_name = event.content.get("SquadronName", self.state.SquadronName)
            if isinstance(squadron_name, str):
                self.state.SquadronName = squadron_name
            self.state.Status = "Member"
            timestamp = event.content.get("timestamp")
            if isinstance(timestamp, str):
                self.state.Timestamp = timestamp

        if event_name == "SquadronPromotion":
            squadron_id = event.content.get("SquadronID", self.state.SquadronID)
            squadron_name = event.content.get("SquadronName", self.state.SquadronName)
            new_rank = event.content.get("NewRank", self.state.CurrentRank)
            new_rank_name = event.content.get("NewRankName", self.state.CurrentRankName)
            if isinstance(squadron_id, int):
                self.state.SquadronID = squadron_id
            if isinstance(squadron_name, str):
                self.state.SquadronName = squadron_name
            if isinstance(new_rank, int):
                self.state.CurrentRank = new_rank
            if isinstance(new_rank_name, str):
                self.state.CurrentRankName = new_rank_name
            self.state.Status = "Member"
            timestamp = event.content.get("timestamp")
            if isinstance(timestamp, str):
                self.state.Timestamp = timestamp

        if event_name == "SquadronDemotion":
            squadron_id = event.content.get("SquadronID", self.state.SquadronID)
            squadron_name = event.content.get("SquadronName", self.state.SquadronName)
            new_rank = event.content.get("NewRank", self.state.CurrentRank)
            new_rank_name = event.content.get("NewRankName", self.state.CurrentRankName)
            if isinstance(squadron_id, int):
                self.state.SquadronID = squadron_id
            if isinstance(squadron_name, str):
                self.state.SquadronName = squadron_name
            if isinstance(new_rank, int):
                self.state.CurrentRank = new_rank
            if isinstance(new_rank_name, str):
                self.state.CurrentRankName = new_rank_name
            self.state.Status = "Member"
            timestamp = event.content.get("timestamp")
            if isinstance(timestamp, str):
                self.state.Timestamp = timestamp

        if event_name in ["LeftSquadron", "KickedFromSquadron", "DisbandedSquadron"]:
            self._reset_state()
