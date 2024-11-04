from abc import ABC, abstractmethod
from datetime import timezone
import hashlib
import inspect
import json
from typing import Any, Literal, Callable, Optional, final
import sqlite3
import sqlite_vec

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
        self.incoming: list[Event] = []
        self.pending: list[Event] = []
        self.processed: list[Event] = []
        self.is_replying = False
        self.is_listening = False
        self.on_reply_request = on_reply_request
        self.game_events = game_events
        
        self.event_classes: list[type[Event]] = [ConversationEvent, ToolEvent, GameEvent, StatusEvent, ExternalEvent]
        self.projections: list[Projection] = []
        
        self.conn, self.cursor = self.init_db()

        if continue_conversation:
            self.load_history()
            log('info', 'Continuing conversation with', len(self.processed), 'events.')
        else:
            self.clear_history()
            log('info', 'Starting a new conversation.')
            
    def init_db(self):
        conn = sqlite3.connect('./covas.db')
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        cursor = conn.cursor()

        _ = cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS events_v1 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class TEXT,
                kind TEXT,
                data TEXT,
                processed_at FLOAT,
                timestamp DATETIME
            )
        ''')
        _ = cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS projections_v1 (
                class TEXT PRIMARY KEY,
                version INTEGER,
                state TEXT,
                last_processed FLOAT,
                updated DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        conn.commit()
        
        return conn, cursor
        
    def add_game_event(self, content: dict[str, Any]):
        event = GameEvent(content=content)
        self.incoming.append(event)
        log('Event', event)

    def add_external_event(self, content: dict[str, Any]):
        event = ExternalEvent(content=content)
        self.incoming.append(event)
        log('Event', event)

    def add_status_event(self, status: dict[str, Any]):
        event = StatusEvent(status=status)
        self.incoming.append(event)
        if status.get("event") != 'Status':
            log('Event', event)

    def add_conversation_event(self, role: Literal['user', 'assistant'], content: str):
        event = ConversationEvent(kind=role, content=content)
        self.incoming.append(event)
        if role == 'user':
            log('CMDR', content)
        elif role == 'assistant':
            log('COVAS', content)

    def add_assistant_complete_event(self):
        event = ConversationEvent(kind='assistant_completed', content='')
        self.incoming.append(event)
        self.is_replying = False
        # log('debug', event)

    def add_tool_call(self, request: list[dict[str, Any]], results: list[dict[str, Any]]):
        event = ToolEvent(request=request, results=results)
        self.incoming.append(event)
        log('Action', [result['name'] + ': ' + result['content'] for result in results])

    def process(self):
        for event in self.incoming:
            timestamp = datetime.now(timezone.utc).timestamp()
            event.processed_at = timestamp
            self.update_projections(event)
        self.save_incoming_history()
        for event in self.incoming:
            self.incoming.remove(event)
            self.pending.append(event)
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

    def update_projections(self, event: Event):
        for projection in self.projections:
            self.update_projection(projection, event)
    
    def update_projection(self, projection: Projection, event: Event):
        projection.process(event)
        if event.processed_at < projection.last_processed:
            log('warn', 'Projection', projection.__class__.__name__, 'is running backwards in time!', 'Event:', event.processed_at, 'Projection:', projection.last_processed)
        projection.last_processed = event.processed_at
        _ = self.cursor.execute('''
            UPDATE projections_v1 SET state = ?, last_processed = ? WHERE class = ?
        ''', (json.dumps(projection.state), projection.last_processed, projection.__class__.__name__))
        self.conn.commit()
    
    def register_projection(self, projection: Projection):
        # check if projection is already in db, if not insert, if yes load state
        projection_class_name = projection.__class__.__name__
        projection_source = inspect.getsource(projection.__class__)
        log('debug', 'Projection source', projection_source)
        projection_version = hashlib.sha256(projection_source.encode()).hexdigest()
        log('debug', 'Register projection', projection_class_name, 'version', projection_version)
        
        _ = self.cursor.execute('''
            SELECT state, last_processed FROM projections_v1 WHERE class = ? AND version = ?
        ''', (projection_class_name, projection_version, ))
        row = self.cursor.fetchone()
        
        if row:
            state, last_processed = row
            log('debug', 'Loading state for', projection_class_name, projection_version, state, last_processed)
            projection.state = json.loads(state)
            projection.last_processed = last_processed
        else:
            log('debug', 'Initializing new state for', projection_class_name, projection_version)
            _ = self.cursor.execute('''
                DELETE FROM projections_v1 WHERE class = ?
            ''', (projection_class_name,))
            _ = self.cursor.execute('''
                INSERT INTO projections_v1 (class, version, state, last_processed) VALUES (?, ?, ?, ?)
            ''', (projection_class_name, projection_version, json.dumps(projection.get_default_state()), 0.0))
            self.conn.commit()
        
        for event in self.processed + self.pending:
            if event.processed_at <= projection.last_processed:
                continue
            log('debug', 'updating', projection_class_name, 'with', event, 'after starting from', projection.last_processed)
            self.update_projection(projection, event)
        
        self.conn.commit()
        self.projections.append(projection)

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

    def save_incoming_history(self):
        for event in self.incoming:
            event_data = json.dumps(event.__dict__, default=self._json_serializer)
            event_class = event.__class__.__name__
            _ = self.cursor.execute('''
                INSERT INTO events_v1 (class, kind, data, processed_at, timestamp) VALUES (?, ?, ?, ?, ?)
            ''', (event_class, event.kind, event_data, event.processed_at, event.timestamp))
        self.conn.commit()

    def load_history(self):
        _ = self.cursor.execute('''
            SELECT class as class_name, data, timestamp FROM events_v1
            ORDER BY timestamp DESC
            LIMIT 100
        ''')
        rows = self.cursor.fetchall()
        for rawevent in reversed(rows):
            class_name = rawevent[0]
            event_data = json.loads(rawevent[1])
            event = self._instantiate_event(class_name, event_data)
            if event:
                self.processed.append(event)
            else:
                log('error', 'Could not instantiate event', class_name)
    
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
        _ = self.cursor.execute('''
            DELETE FROM events_v1
        ''')
        # TODO do we want to clear projections as well?
        _ = self.cursor.execute('''
            DELETE FROM projections_v1
        ''')
        self.conn.commit()

    def __del__(self):
        if 'conn' in self.__dict__:
            self.conn.close()