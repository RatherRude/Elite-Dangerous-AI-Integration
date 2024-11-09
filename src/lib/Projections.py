from typing import Any
from typing_extensions import override
from .StatusParser import parse_status_flags, parse_status_json
from .Event import Event, StatusEvent, GameEvent
from .Logger import log
from .EventManager import EventManager, Projection

def latest_event_projection_factory(projectionName: str, gameEvent: str):
    class LatestEvent(Projection):
        @override
        def get_default_state(self) -> dict[str, Any]:
            return {}
        
        @override
        def process(self, event: Event) -> None:
            if isinstance(event, GameEvent):
                if gameEvent and event.content.get('event', '') == gameEvent:
                    self.state = event.content
    
    LatestEvent.__name__ = projectionName
                
    return LatestEvent
            
  
class EventCounter(Projection):
    @override
    def get_default_state(self) -> dict[str, Any]:
        return {"count": 0}
    
    @override
    def process(self, event: Event) -> None:
        self.state["count"] += 1

class CurrentStatus(Projection):
    @override
    def get_default_state(self) -> dict[str, Any]:
        return parse_status_json({"flags": parse_status_flags(0)})  # type: ignore
    
    @override
    def process(self, event: Event) -> None:
        if isinstance(event, StatusEvent) and event.status.get("event") == "Status":
            self.state = event.status

def registerProjections(event_manager: EventManager):
    event_manager.register_projection(EventCounter())
    event_manager.register_projection(CurrentStatus())
    
    for proj in [
        'Commander',
        'Materials',
        'Rank',
        'Progress',
        'Reputation',
        'EngineerProgress',
        'SquadronStartup',
        'Statistics',
        'Location',
        'Powerplay',
        'ShipLocker',
        'Loadout',
        'Shipyard',
        'StoredShips',
    ]:
        p = latest_event_projection_factory(proj, proj)
        event_manager.register_projection(p())