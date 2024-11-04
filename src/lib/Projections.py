from typing import Any
from typing_extensions import override
from .StatusParser import parse_status_flags, parse_status_json
from .Event import Event, StatusEvent
from .Logger import log
from .EventManager import EventManager, Projection

  
class EventCounter(Projection):
    @override
    def get_default_state(self) -> dict[str, Any]:
        return {"count": 0}
    
    @override
    def process(self, event: Event) -> None:
        self.state["count"] += 1
        log('info','Event count:', self.state["count"])

class CurrentStatus(Projection):
    @override
    def get_default_state(self) -> dict[str, Any]:
        return parse_status_json({"flags": parse_status_flags(0)})  # type: ignore
    
    @override
    def process(self, event: Event) -> None:
        if isinstance(event, StatusEvent) and event.status.get("event") == "Status":
            log('info', 'Current Status:', event.status)
            self.state = event.status

def registerProjections(event_manager: EventManager):
    event_manager.register_projection(EventCounter())
    event_manager.register_projection(CurrentStatus())