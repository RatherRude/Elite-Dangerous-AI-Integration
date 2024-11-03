
from .StatusParser import BaseFlags, Status
from .Event import Event, StatusEvent
from .Logger import log
from .EventManager import EventManager, Projection

  
class EventCounter(Projection):
    def get_default_state(self) -> dict:
        return {"count": 0}
    
    def process(self, event: Event) -> None:
        self.state["count"] += 1
        log('info','Event count:', self.state["count"])

class CurrentStatus(Projection):
    def get_default_state(self) -> None:
        return Status(flags=BaseFlags.from_status_flag(0))
    
    def process(self, event: Event) -> None:
        if isinstance(event, StatusEvent) and event.status.get("event") == "Status":
            log('info', 'Current Status:', event.status)
            self.state = event.status

def registerProjections(event_manager: EventManager):
    event_manager.register_projection(EventCounter())
    event_manager.register_projection(CurrentStatus())