from abc import ABC, abstractmethod
from datetime import timezone, datetime
import hashlib
import inspect
import json
from typing import Any, Literal, Callable, Optional, final
import sqlite3
import sqlite_vec

from .Database import EventStore, KeyValueStore
from .EDJournal import *
from .Event import Event, GameEvent, ConversationEvent, StatusEvent, ToolEvent, ExternalEvent
from .Logger import log


class Projection(ABC):
    @abstractmethod
    def get_default_state(self) -> dict[str, Any]:
        return {}
    
    def __init__(self):
        self.state: dict[str, Any] = self.get_default_state()
        self.last_processed: float = 0.0
        pass

    @abstractmethod
    def process(self, event: Event) -> None:
        pass

@final
class EventManager:
    def __init__(self, on_reply_request: Callable[[list[Event], list[Event], dict[str, dict[str, Any]]], Any], game_events: list[str],
                 continue_conversation: bool = False):
        self.incoming: Queue[Event] = Queue()
        self.pending: list[Event] = []
        self.processed: list[Event] = []
        self.is_replying = False
        self.is_listening = False
        self.on_reply_request = on_reply_request
        self.game_events = game_events
        
        self.event_classes: list[type[Event]] = [ConversationEvent, ToolEvent, GameEvent, StatusEvent, ExternalEvent]
        self.projections: list[Projection] = []
        
        self.event_store = EventStore('events', self.event_classes)
        self.projection_store = KeyValueStore('projections')

        if continue_conversation:
            self.load_history()
            log('info', 'Continuing conversation with', len(self.processed), 'events.')
        else:
            self.clear_history()
            log('info', 'Starting a new conversation.')
            
        
    def add_game_event(self, content: dict[str, Any]):
        event = GameEvent(content=content, historic=False)
        self.incoming.put(event)
        log('Event', event)

    def add_historic_game_event(self, content: dict[str, Any]):
        max_event_id = max([event.content.get('id') for event in self.processed if isinstance(event, GameEvent)], default='') # TODO: this is not efficient
        if content.get('id', '') <= max_event_id:
            return
        event = GameEvent(content=content, historic=True)
        self.incoming.put(event)
        # log('Event', event)
        
    def add_external_event(self, content: dict[str, Any]):
        event = ExternalEvent(content=content)
        self.incoming.put(event)
        log('Event', event)

    def add_status_event(self, status: dict[str, Any]):
        event = StatusEvent(status=status)
        self.incoming.put(event)
        if status.get("event") != 'Status':
            log('Event', event)

    def add_conversation_event(self, role: Literal['user', 'assistant'], content: str):
        event = ConversationEvent(kind=role, content=content)
        self.incoming.put(event)
        if role == 'user':
            log('CMDR', content)
        elif role == 'assistant':
            log('COVAS', content)

    def add_assistant_complete_event(self):
        event = ConversationEvent(kind='assistant_completed', content='')
        self.incoming.put(event)
        self.is_replying = False
        # log('debug', event)

    def add_tool_call(self, request: list[dict[str, Any]], results: list[dict[str, Any]]):
        event = ToolEvent(request=request, results=results)
        self.incoming.put(event)
        log('Action', [result['name'] + ': ' + result['content'] for result in results])

    def process(self):
        while not self.incoming.empty():
            event = self.incoming.get()
            timestamp = datetime.now(timezone.utc).timestamp()
            event.processed_at = timestamp
            self.update_projections(event, save_later=True)
            self.event_store.insert_event(event, timestamp)  
            
            if isinstance(event, GameEvent) and event.historic:
                #self.processed.append(event)
                pass
            else:
                self.pending.append(event)
        
        self.save_projections()
        
        if not self.is_replying and not self.is_listening and self.should_reply():
            self.is_replying = True
            new_events = self.pending
            self.processed += self.pending
            self.pending = []
            log('debug', 'eventmanager requesting reply')
            projected_states: dict[str, Any] = {}
            for projection in self.projections:
                projected_states[projection.__class__.__name__] = projection.state.copy()
            self.on_reply_request(self.processed, new_events, projected_states)
            return True

        return False

    def update_projections(self, event: Event, save_later: bool = False):
        for projection in self.projections:
            self.update_projection(projection, event, save_later=save_later)
    
    def update_projection(self, projection: Projection, event: Event, save_later: bool = False):
        try:
            projection.process(event)
        except Exception as e:
            log('error', 'Error processing event', event, 'with projection', projection, e, traceback.format_exc())
            return
        if event.processed_at < projection.last_processed:
            log('warn', 'Projection', projection.__class__.__name__, 'is running backwards in time!', 'Event:', event.processed_at, 'Projection:', projection.last_processed)
        projection.last_processed = event.processed_at
        if not save_later:
            self.projection_store.set(projection.__class__.__name__, {"state": projection.state, "last_processed": projection.last_processed})
    
    def save_projections(self):
        for projection in self.projections:
            self.projection_store.set(projection.__class__.__name__, {"state": projection.state, "last_processed": projection.last_processed})
    
    def register_projection(self, projection: Projection):
        projection_class_name = projection.__class__.__name__
        projection_source = inspect.getsource(projection.__class__)
        projection_version = hashlib.sha256(projection_source.encode()).hexdigest()
        log('debug', 'Register projection', projection_class_name, 'version', projection_version)
        
        state = self.projection_store.init(projection_class_name, projection_version, {"state": projection.get_default_state(), "last_processed": 0.0})
        projection.state = state["state"]
        projection.last_processed = state["last_processed"]
        
        for event in self.processed + self.pending:
            if event.processed_at <= projection.last_processed:
                continue
            log('debug', 'updating', projection_class_name, 'with', event, 'after starting from', projection.last_processed)
            self.update_projection(projection, event, save_later=True)
        
        self.projections.append(projection)
        self.save_projections()

    def should_reply(self):
        if len(self.pending) == 0:
            return False

        for event in self.pending:
            # check if pending contains conversational events
            if isinstance(event, ConversationEvent) and event.kind == "user":
                return True

            if isinstance(event, ToolEvent):
                return True

            if isinstance(event, GameEvent) and event.content.get("event") in self.game_events:
                return True

            if isinstance(event, StatusEvent) and event.status.get("event") in self.game_events:
                return True
            
            if isinstance(event, ExternalEvent):
                return True

            # if isinstance(event, GameEvent) and event.content.get("event") == 'ProspectedAsteroid' and any([material['Name'] == 'LowTemperatureDiamond' for material in event.content.get("Materials")]) and event.content.get("Remaining") != 0:
            #     return True

        return False

    def save_incoming_history(self, incoming: list[Event]):
        for event in incoming:
            self.event_store.insert_event(event, event.processed_at)

    def load_history(self):
        events: list[Event] = self.event_store.get_latest()
        for event in reversed(events):
            self.processed.append(event)
    
    def _instantiate_event(self, type_name: str, data: dict[str, Any]) -> (Event | None):
        for event_class in self.event_classes:
            if event_class.__name__ == type_name:
                return event_class(**data)
        return None

    def _json_serializer(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        raise TypeError(f'Object of type {type(o).__name__} is not JSON serializable')
    
    def clear_history(self):
        # TODO do we want to clear all events or just conversation?
        self.event_store.delete_all()
        # TODO do we want to clear projections as well?
        self.projection_store.delete_all()
