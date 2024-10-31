from abc import ABC, abstractmethod
import dataclasses
import json
from typing import Literal, Callable, Optional
import sqlite3
import sqlite_vss

from .EDJournal import *
from .Event import GameEvent, Event, ConversationEvent, StatusEvent, ToolEvent, ExternalEvent
from .Logger import log
from .Projection import Projection


class EventManager:
    def __init__(self, on_reply_request: Callable[[List[Event], List[Event]], any], game_events: List[str],
                 continue_conversation: bool = False):
        self.incoming: List[Event] = []
        self.pending: List[Event] = []
        self.processed: List[Event] = []
        self.is_replying = False
        self.is_listening = False
        self.on_reply_request = on_reply_request
        self.game_events = game_events
        self.event_offset = 0
        
        self.event_classes = [ConversationEvent, ToolEvent, GameEvent, StatusEvent, ExternalEvent]
        self.projections: List[type[Projection]] = []
        
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
        sqlite_vss.load(conn)
        conn.enable_load_extension(False)
        cursor = conn.cursor()

        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class TEXT,
                kind TEXT,
                data TEXT,
                timestamp DATETIME
            )
        ''')
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS projections (
                class TEXT PRIMARY KEY,
                state TEXT,
                offset INTEGER,
                updated DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        conn.commit()
        
        return conn, cursor
        

    def add_game_event(self, content: Dict):
        event = GameEvent(content=content)
        self.incoming.append(event)
        log('Event', event)

    def add_external_event(self, content: Dict):
        event = ExternalEvent(content=content)
        self.incoming.append(event)
        log('Event', event)

    def add_status_event(self, status: Dict):
        event = StatusEvent(status=status)
        self.incoming.append(event)
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

    def add_tool_call(self, request: Dict, results: List[Dict]):
        event = ToolEvent(request=request, results=results)
        self.incoming.append(event)
        log('Action', [result['name'] + ': ' + result['content'] for result in results])

    def process(self):
        for event in self.incoming:
            self.event_offset += 1
            event.id = self.event_offset
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
            self.on_reply_request(self.processed, new_events)
            return True

        return False

    def update_projections(self, event: Event):
        for projection in self.projections:
            self.update_projection(projection, event)
    
    def update_projection(self, projection: Projection, event: Event):
        projection.process(event)
        projection.offset = event.id
        self.cursor.execute('''
            UPDATE projections SET state = ?, offset = ? WHERE class = ?
        ''', (json.dumps(projection.state), projection.offset, projection.__class__.__name__))
        self.conn.commit()
    
    def register_projection(self, projection_class: type[Projection]):
        # check if projection is already in db, if not insert, if yes load state
        projection_class_name = projection_class.__name__
        
        self.cursor.execute('''
            SELECT state, offset FROM projections WHERE class = ?
        ''', (projection_class_name,))
        row = self.cursor.fetchone()
        
        projection: Projection = projection_class()
        if row:
            state, offset = row
            log('debug', 'Loading state for', projection_class_name, state, offset)
            projection.state = json.loads(state)
            projection.offset = offset
        else:
            log('debug', 'Initializing state for', projection_class_name)
            self.cursor.execute('''
                INSERT INTO projections (class, state, offset) VALUES (?, ?, ?)
            ''', (projection_class_name, json.dumps(projection.get_default_state()), 0))
            self.conn.commit()
        
        
        for event in self.processed + self.pending:
            if event.id <= projection.offset:
                continue
            log('debug', 'updating', projection_class_name, 'with', event, 'after starting from', projection.offset)
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
            event_timestamp = event.timestamp
            event_class = event.__class__.__name__
            self.cursor.execute('''
                INSERT INTO events (id, class, kind, data, timestamp) VALUES (?, ?, ?, ?, ?)
            ''', (event.id, event_class, event.kind, event_data, event_timestamp))
        self.conn.commit()

    def load_history(self):
        self.cursor.execute('''
            SELECT class as class_name, data, timestamp FROM events
            ORDER BY timestamp DESC
            LIMIT 100
        ''')
        rows = self.cursor.fetchall()
        log('log', rows)
        for rawevent in reversed(rows):
            class_name = rawevent[0]
            event_data = json.loads(rawevent[1])
            event = self._instantiate_event(class_name, event_data)
            if event:
                self.processed.append(event)
            else:
                log('error', 'Could not instantiate event', class_name)
        self.event_offset = max([event.id for event in self.processed] + [0])+1
    
    def _instantiate_event(self, type_name: str, data: dict) -> GameEvent:
        for event_class in self.event_classes:
            if event_class.__name__ == type_name:
                return event_class(**data)
        return None

    def _json_serializer(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        raise TypeError(f'Object of type {type(o).__name__} is not JSON serializable')
    
    def clear_history(self):
        self.cursor.execute('''
            DELETE FROM events
        ''')
        self.cursor.execute('''
            DELETE FROM projections
        ''')
        self.conn.commit()

    def __del__(self):
        if 'conn' in self.__dict__:
            self.conn.close()