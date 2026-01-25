from typing import cast

from typing_extensions import override
from pydantic import BaseModel, Field

from ..Event import Event, GameEvent
from ..EventManager import Projection
from ..EventModels import FileheaderEvent, FriendsEvent


class OnlineFriendsStateModel(BaseModel):
    """Commander's friends list status."""
    Online: list[str] = Field(default_factory=list, description="Names of currently online friends")
    Pending: list[str] = Field(default_factory=list, description="Names of pending friend requests")


class Friends(Projection[OnlineFriendsStateModel]):
    StateModel = OnlineFriendsStateModel

    @override
    def process(self, event: Event) -> None:
        # Clear the list on Fileheader event (new game session)
        if isinstance(event, GameEvent) and event.content.get("event") == "Fileheader":
            payload = cast(FileheaderEvent, event.content)
            self.state.Online = []
            self.state.Pending = []

        # Process Friends events
        if isinstance(event, GameEvent) and event.content.get("event") == "Friends":
            payload = cast(FriendsEvent, event.content)
            friend_name = payload.get("Name", "")
            friend_status = payload.get("Status", "")

            # Skip if missing crucial information
            if not friend_name or not friend_status:
                return

            # If the friend is coming online, add them to the list
            if friend_status in ["Online", "Added"]:
                if friend_name not in self.state.Online:
                    self.state.Online.append(friend_name)
                if friend_name in self.state.Pending:
                    self.state.Pending.remove(friend_name)

            elif friend_status == "Requested":
                if friend_name not in self.state.Pending:
                    self.state.Pending.append(friend_name)

            # If the friend was previously online but now has a different status, remove them
            elif friend_name in self.state.Online and friend_status in ["Offline", "Lost"]:
                self.state.Online.remove(friend_name)

            elif friend_status == "Declined":
                if friend_name in self.state.Pending:
                    self.state.Pending.remove(friend_name)
