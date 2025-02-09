import hashlib
import inspect
from abc import ABC, abstractmethod
from datetime import timezone, datetime
from typing import Any, Generic, Literal, Callable, TypeVar, final

from .Database import EventStore, KeyValueStore
from .EDJournal import *
from .Event import Event, GameEvent, ConversationEvent, StatusEvent, ToolEvent, ExternalEvent, ProjectedEvent
from .Logger import log

import threading
from collections import defaultdict

ProjectedState = TypeVar("ProjectedState")

class Projection(ABC, Generic[ProjectedState]):
    @abstractmethod
    def get_default_state(self) -> ProjectedState:
        pass
    
    def __init__(self):
        self.state: ProjectedState = self.get_default_state()
        self.last_processed: float = 0.0
        pass

    @abstractmethod
    def process(self, event: Event) -> None | list[ProjectedEvent]:
        pass

@final
class EventManager:
    def __init__(self, on_reply_request: Callable[[list[Event], list[Event], dict[str, dict[str, Any]]], Any], game_events: list[str],
                 continue_conversation: bool = False, react_to_text_local: bool = True, react_to_text_starsystem: bool = True, react_to_text_npc: bool = False,
                 react_to_text_squadron: bool = True, react_to_material:str = '', react_to_danger_mining:bool = False,
                 react_to_danger_onfoot:bool = False):
        self.incoming: Queue[Event] = Queue()
        self.pending: list[Event] = []
        self.processed: list[Event] = []
        self.is_replying = False
        self.is_listening = False
        self.on_reply_request = on_reply_request
        self.game_events = game_events
        self.react_to_text_local = react_to_text_local
        self.react_to_text_starsystem = react_to_text_starsystem
        self.react_to_text_npc = react_to_text_npc
        self.react_to_text_squadron = react_to_text_squadron
        self.react_to_material = react_to_material
        self.react_to_danger_mining = react_to_danger_mining
        self.react_to_danger_onfoot = react_to_danger_onfoot
        self._conditions_registry = defaultdict(list)
        self._registry_lock = threading.Lock()

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
        log('Event', event.content['event'])
        log('debug', 'Event', event)

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
        log('Event', event.content['event'])
        log('debug', 'Event', event)

    def add_status_event(self, status: dict[str, Any]):
        event = StatusEvent(status=status)
        self.incoming.put(event)
        if status.get("event") != 'Status':
            log('Event', event.status['event'])
            log('debug', 'Event', event)

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

    def add_projected_event(self, event: ProjectedEvent, source: Event):
        event.processed_at = source.processed_at
        if not isinstance(source, GameEvent) or not source.historic:
            self.pending.append(event)
            log('Event', 'projected', event.content['event'])
            log('debug', 'Event', event)

    def add_tool_call(self, request: list[dict[str, Any]], results: list[dict[str, Any]], text: list[str] | None = None):
        event = ToolEvent(request=request, results=results, text=text)
        self.incoming.put(event)
        log('Action', [result['name'] + ': ' + result['content'] for result in results])

    def process(self):
        while not self.incoming.empty():
            event = self.incoming.get()
            timestamp = datetime.now(timezone.utc).timestamp()
            event.processed_at = timestamp
            self.event_store.insert_event(event, timestamp)
            self.update_projections(event, save_later=True)
            
            if isinstance(event, GameEvent) and event.historic:
                #self.processed.append(event)
                pass
            else:
                self.pending.append(event)
        
        self.save_projections()

        projected_states: dict[str, Any] = {}
        for projection in self.projections:
            projected_states[projection.__class__.__name__] = projection.state.copy()

        if not self.is_replying and not self.is_listening and self.should_reply(projected_states):
            self.is_replying = True
            new_events = self.pending
            self.processed += self.pending
            self.pending = []
            log('debug', 'eventmanager requesting reply')

            self.on_reply_request(self.processed, new_events, projected_states)
            return True

        return False

    def update_projections(self, event: Event, save_later: bool = False):
        for projection in self.projections:
            self.update_projection(projection, event, save_later=save_later)
    
    def update_projection(self, projection: Projection, event: Event, save_later: bool = False):
        projection_name = projection.__class__.__name__
        try:
            projected_events = projection.process(event)
            self.check_conditions(projection_name, projection.state)
            if projected_events:
                for e in projected_events:
                    self.add_projected_event(e, event)
                    self.event_store.insert_event(event, datetime.now(timezone.utc).timestamp())
        except Exception as e:
            log('error', 'Error processing event', event, 'with projection', projection, e, traceback.format_exc())
            return
        if event.processed_at < projection.last_processed:
            log('warn', 'Projection', projection_name, 'is running backwards in time!', 'Event:', event.processed_at, 'Projection:', projection.last_processed)
        projection.last_processed = event.processed_at
        if not save_later:
            self.projection_store.set(projection_name, {"state": projection.state, "last_processed": projection.last_processed})
    
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
            #log('debug', 'updating', projection_class_name, 'with', event, 'after starting from', projection.last_processed)
            self.update_projection(projection, event, save_later=True)
        
        self.projections.append(projection)
        self.save_projections()

    def wait_for_condition(self, projection_name: str, condition_fn, timeout=None):
        """
        Block until `condition_fn` is satisfied by the current or future
        state of the specified projection.

        :param projection_name: Name/identifier of the projection to watch.
        :param condition_fn: A callable that takes a dict (the current projection state)
                             and returns True/False.
        :param timeout: Optional timeout (seconds).
        :return: The state dict that satisfied the condition.
        :raises TimeoutError: If the condition isn't met within `timeout`.
        """
        event = threading.Event()
        # We'll store the state that satisfies the condition once it occurs.
        # A single-element list is a convenient way to mutate from an inner function.
        satisfying_state = [None]

        # First, check if the projection already satisfies the condition
        with self._registry_lock:
            # Check for early return
            for projection in self.projections:
                if projection.__class__.__name__ == projection_name:
                    if condition_fn(projection.state):
                        return projection.state

            # Otherwise, register our (condition, event, placeholder) so that
            # future state updates can unblock us
            self._conditions_registry[projection_name].append((condition_fn, event, satisfying_state))

        # Block until event is set or we time out
        is_met_in_time = event.wait(timeout=timeout)
        if not is_met_in_time:
            # Clean up the registry, so we don't leave a stale condition around
            with self._registry_lock:
                waiting_list = self._conditions_registry[projection_name]
                if (condition_fn, event, satisfying_state) in waiting_list:
                    waiting_list.remove((condition_fn, event, satisfying_state))
            raise TimeoutError(f"Condition not met within {timeout} seconds.")
        return satisfying_state[0]

    def check_conditions(self, projection_name: str, new_state: dict):
        """
        Call this after updating the state of `projections[projection_name]`.
        Checks if any registered conditions are satisfied by the latest state.
        Any that are satisfied will be signaled (their events set),
        so their waiting threads can continue.
        """
        with self._registry_lock:
            if projection_name not in self._conditions_registry:
                return  # No conditions are waiting for this projection

            # new_state = self.projections[projection_name].state
            still_waiting = []

            for (condition_fn, event, state_container) in self._conditions_registry[projection_name]:
                if condition_fn(new_state):
                    # Condition met, set state and trigger the event
                    state_container[0] = new_state
                    event.set()
                else:
                    still_waiting.append((condition_fn, event, state_container))

            # Only keep conditions that are still not satisfied
            self._conditions_registry[projection_name] = still_waiting

    def should_reply(self, states:dict[str, Any]):
        if len(self.pending) == 0:
            return False

        for event in self.pending:
            # check if pending contains conversational events
            if isinstance(event, ConversationEvent) and event.kind == "user":
                return True

            if isinstance(event, ToolEvent):
                return True

            if isinstance(event, GameEvent) and event.content.get("event") in self.game_events:
                if event.content.get("event") == "ReceiveText":
                    if event.content.get("Channel") not in ['wing', 'voicechat', 'friend', 'player'] and (
                        (not self.react_to_text_local and event.content.get("Channel") == 'local') or
                        (not self.react_to_text_starsystem and event.content.get("Channel") == 'starsystem') or
                        (not self.react_to_text_npc and event.content.get("Channel") == 'npc') or
                        (not self.react_to_text_squadron and event.content.get("Channel") == 'squadron')):
                        continue

                if event.content.get("event") == "ProspectedAsteroid":
                    chunks = [chunk.strip() for chunk in self.react_to_material.split(",")]
                    contains_material = False
                    for chunk in chunks:
                        for material in event.content.get("Materials"):
                            if chunk.lower() in material["Name"].lower():
                                contains_material = True
                        if event.content.get("MotherlodeMaterial_Localised", False):
                            if chunk.lower() in event.content['MotherlodeMaterial_Localised'].lower():
                                contains_material = True

                    if not contains_material:
                        continue

                if event.content.get("event") == "ScanOrganic":
                    continue

                return True

            if isinstance(event, StatusEvent) and event.status.get("event") in self.game_events:
                if not self.react_to_danger_mining and (event.status.get("event") in ["InDanger", "OutOfDanger"]):
                    if states.get('ShipInfo', {}).get('IsMiningShip', False) and states.get('Location', {}).get('PlanetaryRing', False):
                        continue
                if not self.react_to_danger_onfoot and (event.status.get("event") in ["InDanger", "OutOfDanger"]):
                    if states.get('CurrentStatus', {}).get('flags2').get('OnFoot'):
                        continue
                return True

            if isinstance(event, ExternalEvent):
                return True

            if isinstance(event, ProjectedEvent):
                if event.content.get("event").startswith('ScanOrganic'):
                    if not 'ScanOrganic' in self.game_events:
                        continue
                return True

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
