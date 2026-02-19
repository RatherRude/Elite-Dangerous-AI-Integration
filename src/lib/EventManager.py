from pydantic import ValidationError
import hashlib
import inspect
import traceback
from abc import ABC, abstractmethod
from datetime import timezone, datetime
from typing import Any, Generic, Literal, Callable, TypeVar, final, get_type_hints, get_args, get_origin, cast
from typing_extensions import deprecated
from pydantic import BaseModel, ValidationError

from .Database import EventStore, KeyValueStore, VectorStore
from .EDJournal import *
from .Event import Event, EventClasses, GameEvent, ConversationEvent, MemoryEvent, PluginEvent, StatusEvent, ToolEvent, ExternalEvent, ProjectedEvent, QuestEvent
from .Logger import log, show_chat_message

import threading
from collections import defaultdict

# Type alias for projected states dictionary
ProjectedStates = dict[str, BaseModel]

StateModel = TypeVar("StateModel", bound=BaseModel)

class Projection(ABC, Generic[StateModel]):
    """
    Base class for projections. Subclasses should define a StateModel class attribute
    that is a Pydantic BaseModel with default values.
    """
    StateModel: type[BaseModel]  # Should be overridden by subclasses
    
    def __init__(self):
        # Get the StateModel from class attribute or type hints
        state_model_type = self._get_state_model_type()
        try:
            self.state: StateModel = state_model_type()  # type: ignore
        except ValidationError as exc:
            log("error", "Projection state init failed:", self.__class__.__name__, exc)
            self.state = cast(StateModel, state_model_type.model_construct())
        except Exception as exc:
            log("error", "Projection state init error:", self.__class__.__name__, exc)
            self.state = cast(StateModel, state_model_type.model_construct())
        self.last_processed: float = 0.0

    def _get_state_model_type(self) -> type[BaseModel]:
        """Get the StateModel type from class attribute or Generic type parameter."""
        # First try class attribute - check if it's actually defined on the subclass, not just inherited as a type annotation
        subclass_state_model = self.__class__.__dict__.get('StateModel')
        if subclass_state_model is not None and isinstance(subclass_state_model, type) and issubclass(subclass_state_model, BaseModel):
            return subclass_state_model

        # Then try to extract from Generic type parameter
        for base in getattr(self.__class__, '__orig_bases__', []):
            origin = get_origin(base)
            if origin is Projection or (isinstance(origin, type) and issubclass(origin, Projection)):
                args = get_args(base)
                if args and isinstance(args[0], type) and issubclass(args[0], BaseModel):
                    return args[0]

        raise TypeError(f"Projection subclass {self.__class__.__name__} must define a StateModel class attribute or use a Pydantic BaseModel as the generic type parameter")

    def get_default_state(self) -> StateModel:
        """Returns a new instance of the state model with default values."""
        state_model_type = self._get_state_model_type()
        try:
            return state_model_type()  # type: ignore
        except ValidationError as exc:
            log("error", "Projection default state init failed:", self.__class__.__name__, exc)
            return cast(StateModel, state_model_type.model_construct())

    @abstractmethod
    def process(self, event: Event) -> None | list[ProjectedEvent]:
        pass

    def process_timer(self) -> None | list[ProjectedEvent]:
        return []

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
            memory_hook: Callable[[Any, list[Event]], None] = lambda manager, events: None,
        ):
        self.incoming: Queue[Event] = Queue()
        self.pending: list[Event] = []
        self.processed: list[Event] = []
        self.game_events = game_events
        self._conditions_registry = defaultdict(list)
        self._registry_lock = threading.Lock()

        self.event_classes: list[type[Event]] = EventClasses
        self.projections: list[Projection] = []
        self.sideeffects: list[Callable[[Event, ProjectedStates], None]] = []
        
        self.short_term_memory = EventStore('events', self.event_classes)
        self.projection_store = KeyValueStore('projections')
        self.long_term_memory = VectorStore('memory')
        self._processing_lock = threading.Lock()
        self._timer_interval = 10.0
        self._timer_stop_event = threading.Event()
        self._timer_thread = threading.Thread(target=self._run_projection_timer, daemon=True)
        self._timer_thread.start()

        min_history_id, max_history_id = self.load_history()
        self.min_history_id = min_history_id
        self.max_history_id = max_history_id

        if self.processed:
            show_chat_message('info', 'Continuing conversation with', len(self.processed), 'events.')
        else:
            show_chat_message('info', 'Starting new conversation.')
            
        
    def add_game_event(self, content: dict[str, Any]):
        event = GameEvent(content=content, historic=False)
        self.incoming.put(event)

    def add_quest_event(self, content: dict[str, Any]):
        event = QuestEvent(content=content)
        self.incoming.put(event)

    def add_historic_game_events(self, events = list[dict[str, Any]]):
        events_before = []
        events_after = []
        while events:
            content = events.pop(0)
            event = GameEvent(content=content, historic=True)
            id = event.content.get('id')
            if id > self.max_history_id:
                events_after.append(event)
            elif id < self.min_history_id:
                events_before.insert(0, event)
        for event in events_before:
            self.processed.insert(0, event)
        for event in events_after:
            self.incoming.put(event)
        
    @deprecated("Use plugins instead")
    def add_external_event(self, application: str, content: dict[str, Any]):
        event = ExternalEvent(content={**content, 'event': application})
        self.incoming.put(event)

    def add_status_event(self, status: dict[str, Any]):
        event = StatusEvent(status=status)
        self.incoming.put(event)

    def add_conversation_event(self, role: Literal['user', 'assistant'], content: str, processed_at: float = 0.0, reasons: list[str] | None = None):
        event = ConversationEvent(kind=role, content=content, reasons=reasons)
        if role == 'assistant':
            self.short_term_memory.replied_before(processed_at)
        self.incoming.put(event)

    def add_user_speaking(self):
        event = ConversationEvent(kind='user_speaking', content='')
        self.incoming.put(event)
        # log('debug', event)

    def add_assistant_speaking(self):
        event = ConversationEvent(kind='assistant_speaking', content='')
        self.incoming.put(event)
        # log('debug', event)

    def add_assistant_complete_event(self):
        event = ConversationEvent(kind='assistant_completed', content='')
        self.incoming.put(event)
        # log('debug', event)

    def add_assistant_acting(self, processed_at: float):
        event = ConversationEvent(kind='assistant_acting', content='')
        self.short_term_memory.replied_before(processed_at)
        self.incoming.put(event)

    def add_play_sound(
        self,
        url: str,
        transcription: str,
        actor_id: str | None = None,
        voice: str | None = None,
    ):
        payload: dict[str, Any] = {
            "event": "QuestEvent",
            "action": "play_sound",
            "url": url,
            "transcription": transcription,
        }
        if actor_id:
            payload["actor_id"] = actor_id
        if voice:
            payload["voice"] = voice
        self.add_quest_event(payload)

    def add_npc_message(
        self,
        actor_id: str,
        voice: str,
        transcription: str,
        actor_name: str | None = None,
        actor_name_color: str | None = None,
        avatar_url: str | None = None,
        prompt: str | None = None,
    ):
        payload: dict[str, Any] = {
            "event": "QuestEvent",
            "action": "npc_message",
            "actor_id": actor_id,
            "voice": voice,
            "transcription": transcription,
        }
        if actor_name:
            payload["actor_name"] = actor_name
        if actor_name_color:
            payload["actor_name_color"] = actor_name_color
        if avatar_url:
            payload["avatar_url"] = avatar_url
        if prompt:
            payload["prompt"] = prompt
        self.add_quest_event(payload)

    def add_projected_event(self, event: ProjectedEvent, source: Event):
        event.processed_at = source.processed_at
        if not isinstance(source, GameEvent) or not source.historic:
            self.pending.append(event)

    def add_tool_call(self, request: list[dict[str, Any]], results: list[dict[str, Any]], text: list[str] | None = None):
        event = ToolEvent(request=request, results=results, text=text)
        self.incoming.put(event)

    def add_memory_event(self, model_name: str, last_processed_at: float, content: str, metadata: dict, embedding: list[float]):
        event = MemoryEvent(content=content, metadata=metadata, embedding=embedding)
        event.processed_at = last_processed_at
        self.short_term_memory.memorize_before(event.processed_at)
        self.long_term_memory.store(model_name, event.content, event.embedding, event.metadata)
        self.incoming.put(event)
        
    def get_short_term_memory(self, limit: int = 100) -> list[Event]:
        return self.short_term_memory.get_latest(limit=limit)

    def get_latest_memories(self, limit: int = 10) -> list[MemoryEvent]:
        mems = self.long_term_memory.get_most_recent_entries(limit=limit)
        return [MemoryEvent(content=mem['content'], metadata=mem['metadata'], embedding=[]) for mem in mems]

    def process(self):
        with self._processing_lock:
            projected_states: ProjectedStates | None = None
            while not self.incoming.empty():
                event = self.incoming.get()

                timestamp = datetime.now(timezone.utc).timestamp()
                event.processed_at = timestamp

                self.short_term_memory.insert_event(event, event.processed_at, commit=False)
                projected_events = self.update_projections(event, save_later=True)

                self.pending.append(event)

                if isinstance(event, GameEvent) and event.historic:
                    #self.processed.append(event)
                    continue

                projected_states = {}
                for projection in self.projections:
                    projected_states[projection.__class__.__name__] = projection.state

                self.trigger_sideeffects(event, projected_states)
                for projected_event in projected_events:
                    self.trigger_sideeffects(projected_event, projected_states)

            self.short_term_memory.commit()
            self.save_projections()
            self.processed += self.pending
            self.pending = []

            return projected_states
    

    def trigger_sideeffects(self, event: Event, projected_states: ProjectedStates):
        for sideeffect in self.sideeffects:
            try:
                sideeffect(event, projected_states)
            except Exception as e:
                log('error', 'Error triggering sideeffect', sideeffect, e, traceback.format_exc())
    
    def register_sideeffect(self, sideeffect: Callable[[Event, ProjectedStates], None]):
        self.sideeffects.append(sideeffect)
        
    def get_current_state(self) -> tuple[list[Event], ProjectedStates]:
        """
        Returns the current state of the event manager.
        :return: A tuple containing the list of processed events and a dictionary of projection states.
        """
        projected_states: ProjectedStates = {}
        for projection in self.projections:
            projected_states[projection.__class__.__name__] = projection.state
        return self.processed, projected_states

    def update_projections(self, event: Event, save_later: bool = False) -> list[ProjectedEvent]:
        projected_events: list[ProjectedEvent] = []
        for projection in self.projections:
            evts = self.update_projection(projection, event, save_later=save_later)
            projected_events.extend(evts)
        return projected_events
    
    def update_projection(self, projection: Projection[BaseModel], event: Event, save_later: bool = False) -> list[ProjectedEvent]:
        projection_name = projection.__class__.__name__
        try:
            projected_events = projection.process(event)
            try:
                cls = type(projection.state)
                # Re-run validation using the same model class
                cls.model_validate(projection.state.model_dump())
            except ValidationError as ve:
                log('error', 'Validation error in projection state after processing event', event, 'in projection', projection_name, ve)
                raise ve

            self.check_conditions(projection_name, projection.state)
            if projected_events:
                for e in projected_events:
                    self.add_projected_event(e, event)
                    self.short_term_memory.insert_event(e, event.processed_at)
        except Exception as e:
            log('error', 'Error processing event', event, 'with projection', projection, e, traceback.format_exc())
            return []
        if event.processed_at and projection.last_processed and event.processed_at < projection.last_processed:
            log('warn', 'Projection', projection_name, 'is running backwards in time!', 'Event:', event.processed_at, 'Projection:', projection.last_processed)
        if event.processed_at > 0:
            projection.last_processed = max(projection.last_processed, event.processed_at)
        if not save_later:
            self.projection_store.set(projection_name, {"state": projection.state.model_dump(), "last_processed": projection.last_processed})
        return projected_events if projected_events else []

    def _run_projection_timer(self):
        while not self._timer_stop_event.wait(self._timer_interval):
            try:
                self.process_timer_tick()
            except Exception as e:
                log('error', 'Error running projection timer', e, traceback.format_exc())

    def process_timer_tick(self):
        with self._processing_lock:
            timestamp = datetime.now(timezone.utc).timestamp()
            projected_events: list[ProjectedEvent] = []
            projected_states: dict[str, Any] | None = None
            timer_projection_names = {"Idle", "StoredShips", "StoredModules", "FleetCarriers"}

            for projection in self.projections:
                if projection.__class__.__name__ not in timer_projection_names:
                    continue
                projection_name = projection.__class__.__name__
                try:
                    evts = projection.process_timer() or []
                    self.check_conditions(projection_name, projection.state)
                    if evts:
                        projected_events.extend(evts)
                except Exception as e:
                    log('error', 'Error processing timer for projection', projection_name, e, traceback.format_exc())
                    continue
                projection.last_processed = timestamp
                # Persist Pydantic state as plain dict to keep JSON serialization working
                self.projection_store.set(
                    projection_name,
                    {"state": projection.state.model_dump(), "last_processed": projection.last_processed},
                )

            if projected_events:
                projected_states = {p.__class__.__name__: p.state.copy() for p in self.projections}
                for evt in projected_events:
                    evt.processed_at = timestamp
                    self.pending.append(evt)
                    self.short_term_memory.insert_event(evt, evt.processed_at, commit=False)
                    self.trigger_sideeffects(evt, projected_states)

                self.short_term_memory.commit()
                self.save_projections()
                self.processed += self.pending
                self.pending = []

    def save_projections(self):
        for projection in self.projections:
            self.projection_store.set(projection.__class__.__name__, {"state": projection.state.model_dump(), "last_processed": projection.last_processed})
    
    def register_projection(self, projection: Projection, raise_error: bool = True):
        projection_class_name = projection.__class__.__name__
        projection_source = inspect.getsource(projection.__class__)
        projection_version = hashlib.sha256(projection_source.encode()).hexdigest()
        log('debug', 'Register projection', projection_class_name, 'version', projection_version)
        
        try:
            # Get the state model type for deserialization
            state_model_type = projection._get_state_model_type()
            default_state_dict = projection.get_default_state().model_dump()
            stored = self.projection_store.init(projection_class_name, projection_version, {"state": default_state_dict, "last_processed": 0.0})

            # Deserialize state from dict to Pydantic model
            try:
                projection.state = state_model_type.model_validate(stored["state"])
                projection.last_processed = stored["last_processed"]
            except ValidationError as ve:
                log('error', 'Validation error while deserializing state for projection', projection_class_name, ve)
                try:
                    projection.state = state_model_type.model_validate(default_state_dict)
                except ValidationError as default_exc:
                    log('error', 'Default state validation failed for projection', projection_class_name, default_exc)
                    projection.state = state_model_type.model_construct()  # type: ignore[assignment]
                    projection.last_processed = 0.0

            for event in self.processed + self.pending:
                if event.processed_at > 0.0 and event.processed_at <= projection.last_processed:
                    # log('debug', 'skipping update due to timestamp')
                    continue
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

    def check_conditions(self, projection_name: str, new_state: BaseModel):
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

    def get_projection_state(self, projection_name: str) -> dict:
        proj = None
        for p in self.projections:
            if p.__class__.__name__ == projection_name:
                proj = p
                break
        if proj is None:
            raise ValueError(f"Projection with name '{projection_name}' not found.")
        return proj.state

    def load_history(self):
        events: list[Event] = self.short_term_memory.get_latest()
        for event in reversed(events):
            self.processed.append(event)
        min_event_id = min([event.content.get('id') for event in self.processed if isinstance(event, GameEvent)], default='')
        max_event_id = max([event.content.get('id') for event in self.processed if isinstance(event, GameEvent)], default='')
        return min_event_id, max_event_id
