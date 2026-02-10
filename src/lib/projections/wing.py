from typing_extensions import override
from pydantic import BaseModel, Field

from ..Event import Event, GameEvent
from ..EventManager import Projection


class WingStateModel(BaseModel):
    """Current wing membership status."""
    Members: list[str] = Field(default_factory=list, description="Names of wing members")


class Wing(Projection[WingStateModel]):
    StateModel = WingStateModel

    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent) and event.content.get("event") == "WingJoin":
            # Initialize with existing members if any
            others = event.content.get("Others", [])
            if isinstance(others, list) and others:
                members: list[str] = []
                for member in others:
                    if isinstance(member, dict):
                        name = member.get("Name", "Unknown")
                        if isinstance(name, str):
                            members.append(name)
                self.state.Members = members
            else:
                self.state.Members = []

        if isinstance(event, GameEvent) and event.content.get("event") == "WingAdd":
            name = event.content.get("Name", "Unknown")
            if isinstance(name, str) and name and name not in self.state.Members:
                self.state.Members.append(name)

        if isinstance(event, GameEvent) and event.content.get("event") in ["WingLeave", "LoadGame"]:
            self.state.Members = []
