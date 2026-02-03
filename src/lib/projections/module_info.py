from typing import cast

from typing import Any, cast

from typing_extensions import override

from ..Event import Event, GameEvent
from ..EventManager import Projection
from pydantic import BaseModel

from ..EventModels import ModuleInfoEvent


class ModuleInfoModule(BaseModel):

    Slot: str | None = None
    Item: str | None = None
    Health: float | None = None
    Value: int | None = None
    AmmoInHopper: int | None = None
    AmmoInClip: int | None = None
    On: bool | None = None
    Priority: int | None = None
    Engineering: dict | None = None


class ModuleInfoState(BaseModel):
    event: str | None = None
    timestamp: str | None = None
    Ship: str | None = None
    ShipID: int | None = None
    Modules: list[ModuleInfoModule] | None = None


class ModuleInfo(Projection[ModuleInfoState]):
    StateModel = ModuleInfoState

    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent) and event.content.get("event") == "ModuleInfo":
            payload = cast(ModuleInfoEvent, event.content)
            raw = cast(dict[str, Any], event.content)
            self.state.event = payload.get("event")
            self.state.timestamp = payload.get("timestamp")
            self.state.Ship = cast(str | None, raw.get("Ship"))
            self.state.ShipID = cast(int | None, raw.get("ShipID"))
            modules = raw.get("Modules")
            if isinstance(modules, list):
                self.state.Modules = [ModuleInfoModule(**module) for module in modules]
