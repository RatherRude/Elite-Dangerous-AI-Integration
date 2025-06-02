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
    @staticmethod
    def clear_history():
        event_store = EventStore('events', [])
        event_store.delete_all()
        projection_store = KeyValueStore('projections')
        projection_store.delete_all()
    
    def __init__(
            self, 
            game_events: list[str],
            plugin_event_classes: list[type[Event]],
        ):
        self.incoming: Queue[Event] = Queue()
        self.pending: list[Event] = []
        self.processed: list[Event] = []
        self.game_events = game_events
        self._conditions_registry = defaultdict(list)
        self._registry_lock = threading.Lock()

        self.event_classes: list[type[Event]] = [ConversationEvent, ToolEvent, GameEvent, StatusEvent, ExternalEvent]
        self.event_classes += plugin_event_classes # Adds the plugin provided event classes
        self.projections: list[Projection] = []
        self.sideeffects: list[Callable[[Event, dict[str, Any]], None]] = []
        
        self.event_store = EventStore('events', self.event_classes)
        self.projection_store = KeyValueStore('projections')
        
        self.load_history()
        if self.processed:
            log('info', 'Continuing conversation with', len(self.processed), 'events.')
        else:
            log('info', 'Starting new conversation.')
            
        
    def add_game_event(self, content: dict[str, Any]):
        event = GameEvent(content=content, historic=False)
        self.incoming.put(event)

    def add_historic_game_event(self, content: dict[str, Any]):
        max_event_id = max([event.content.get('id') for event in self.processed if isinstance(event, GameEvent)], default='') # TODO: this is not efficient
        if content.get('id', '') <= max_event_id:
            return
        event = GameEvent(content=content, historic=True)
        self.incoming.put(event)
        
    def add_external_event(self, application: str, content: dict[str, Any]):
        event = ExternalEvent(content={**content, 'event': application})
        self.incoming.put(event)

    def add_status_event(self, status: dict[str, Any]):
        event = StatusEvent(status=status)
        self.incoming.put(event)

    def add_conversation_event(self, role: Literal['user', 'assistant'], content: str):
        event = ConversationEvent(kind=role, content=content)
        self.incoming.put(event)

    def add_assistant_complete_event(self):
        event = ConversationEvent(kind='assistant_completed', content='')
        self.incoming.put(event)
        # log('debug', event)

    def add_projected_event(self, event: ProjectedEvent, source: Event):
        event.processed_at = source.processed_at
        if not isinstance(source, GameEvent) or not source.historic:
            self.pending.append(event)

    def add_tool_call(self, request: list[dict[str, Any]], results: list[dict[str, Any]], text: list[str] | None = None):
        event = ToolEvent(request=request, results=results, text=text)
        self.incoming.put(event)

    def process(self):
        projected_states: dict[str, Any] | None = None
        while not self.incoming.empty():
            event = self.incoming.get()
            timestamp = datetime.now(timezone.utc).timestamp()
            event.processed_at = timestamp
            self.event_store.insert_event(event, timestamp, commit=False)
            projected_events = self.update_projections(event, save_later=True)
            
            self.pending.append(event)
            
            if isinstance(event, GameEvent) and event.historic:
                #self.processed.append(event)
                continue
                
            projected_states = {}
            for projection in self.projections:
                projected_states[projection.__class__.__name__] = projection.state.copy()
            
            self.trigger_sideeffects(event, projected_states)
            for projected_event in projected_events:
                self.trigger_sideeffects(projected_event, projected_states)

        self.event_store.commit()
        self.save_projections()
        self.processed += self.pending
        self.pending = []
        
        return projected_states
    
    def trigger_sideeffects(self, event: Event, projected_states: dict[str, Any]):
        for sideeffect in self.sideeffects:
            try:
                sideeffect(event, projected_states)
            except Exception as e:
                log('error', 'Error triggering sideeffect', sideeffect, e, traceback.format_exc())
    
    def register_sideeffect(self, sideeffect: Callable[[Event, dict[str, Any]], None]):
        self.sideeffects.append(sideeffect)
        
    def get_current_state(self) -> tuple[list[Event], dict[str, Any]]:
        """
        Returns the current state of the event manager.
        :return: A tuple containing the list of processed events and a dictionary of projection states.
        """
        projected_states = {}
        for projection in self.projections:
            projected_states[projection.__class__.__name__] = projection.state.copy()
        return self.processed, projected_states

    def update_projections(self, event: Event, save_later: bool = False) -> list[ProjectedEvent]:
        projected_events: list[ProjectedEvent] = []
        for projection in self.projections:
            evts = self.update_projection(projection, event, save_later=save_later)
            projected_events.extend(evts)
        return projected_events
    
    def update_projection(self, projection: Projection, event: Event, save_later: bool = False) -> list[ProjectedEvent]:
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
            return []
        if event.processed_at < projection.last_processed:
            log('warn', 'Projection', projection_name, 'is running backwards in time!', 'Event:', event.processed_at, 'Projection:', projection.last_processed)
        projection.last_processed = event.processed_at
        if not save_later:
            self.projection_store.set(projection_name, {"state": projection.state, "last_processed": projection.last_processed})
        return projected_events if projected_events else []

    def save_projections(self):
        for projection in self.projections:
            self.projection_store.set(projection.__class__.__name__, {"state": projection.state, "last_processed": projection.last_processed})
    
    def register_projection(self, projection: Projection, raise_error: bool = True):
        projection_class_name = projection.__class__.__name__
        projection_source = inspect.getsource(projection.__class__)
        projection_version = hashlib.sha256(projection_source.encode()).hexdigest()
        log('debug', 'Register projection', projection_class_name, 'version', projection_version)
        
        try:
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
        except Exception as e:
            if raise_error:
                raise
            log('error', 'Error registering projection', projection, e, traceback.format_exc())

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

    def get_projection(self, projection_type: type) -> Projection[object] | None:
        return next((proj for proj in self.projections if isinstance(proj, projection_type)), None)

    def save_incoming_history(self, incoming: list[Event]):
        for event in incoming:
            self.event_store.insert_event(event, event.processed_at)

    def load_history(self):
        events: list[Event] = self.event_store.get_latest()
        for event in reversed(events):
            self.processed.append(event)
    