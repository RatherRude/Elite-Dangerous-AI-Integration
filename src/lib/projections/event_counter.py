from typing_extensions import override
from pydantic import BaseModel

from ..Event import Event
from ..EventManager import Projection


class EventCounterState(BaseModel):
    count: int = 0


class EventCounter(Projection[EventCounterState]):
    StateModel = EventCounterState

    @override
    def process(self, event: Event) -> None:
        self.state.count += 1
