import json
import os
import sqlean as sqlite3
from typing import Any, final
import sqlite_vec
import threading

from .Config import get_cn_appdata_path

def get_db_path() -> str:
    return os.path.join(get_cn_appdata_path(), 'covas.db')

# Thread-local storage for connections
_thread_local = threading.local()

def get_connection():
    # Check if this thread already has a connection
    if not hasattr(_thread_local, 'conn'):
        # Use sqlite3 module instead of sqlean for better type annotation support
        _thread_local.conn = sqlite3.connect(get_db_path(), timeout=3) # Added timeout
        _thread_local.conn.execute("PRAGMA journal_mode=WAL;") # Enable WAL mode
        _thread_local.conn.enable_load_extension(True)
        sqlite_vec.load(_thread_local.conn)
        _thread_local.conn.enable_load_extension(False)
    return _thread_local.conn


def instantiate_class_by_name(classes: list[Any], class_name: str, data: dict[str, Any]) -> Any:
    for cls in classes:
        if cls.__name__ == class_name:
            return cls(**data)
    return None

# For testing purposes only
def set_connection_for_testing(conn):
    _thread_local.conn = conn

@final
class EventStore():
    def __init__(self, store_name: str, event_classes: list[Any]):
        self.store_name = store_name
        self.table_name = f'{store_name}_v1'
        self.event_classes = event_classes
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f'''                
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class TEXT,
                data TEXT,
                processed_at FLOAT,
                inserted_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        
    def commit(self) -> None:
        get_connection().commit()
    
    def insert_event(self, event: Any, processed_at: float, commit: bool = True) -> None:
        conn = get_connection()
        cursor = conn.cursor()
        event_data = json.dumps(event.__dict__)
        event_class = event.__class__.__name__
        _ = cursor.execute(f'''
            INSERT INTO {self.table_name} (class, data, processed_at)
            VALUES (?, ?, ?)
        ''', (event_class, event_data, processed_at))
        if commit:
            conn.commit()
    
    def get_latest(self, limit: int = 100) -> list[Any]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f'''
            SELECT class, data, processed_at
            FROM {self.table_name}
            ORDER BY processed_at DESC
            LIMIT (?)
        ''', (limit,))
        rows = cursor.fetchall()
        events = []
        for row in rows:
            instance = instantiate_class_by_name(self.event_classes, row[0], json.loads(row[1]))
            events.append(instance)
        return events
    
    def delete_all(self) -> None:
        conn = get_connection()
        cursor = conn.cursor()
        _ = cursor.execute(f'''
            DELETE FROM {self.table_name}
        ''')
        conn.commit()
    
    
@final
class KeyValueStore():
    def __init__(self, store_name: str):
        self.store_name = store_name
        self.table_name = f'{store_name}_v1'
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                key TEXT PRIMARY KEY,
                version TEXT,
                value TEXT,
                inserted_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
                        
    def get_version(self, key: str) -> str | None:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f'''
            SELECT version
            FROM {self.table_name}
            WHERE key = ?
        ''', (key,))
        row = cursor.fetchone()
        if row:
            return row[0]
        return None
    
    def init(self, key: str, version: str, value: Any) -> Any:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if the key already exists
        cursor.execute(f'''
            SELECT version, value
            FROM {self.table_name}
            WHERE key = ?
        ''', (key,))
        row = cursor.fetchone()
        
        if row is None:
            # Key doesn't exist, create it
            cursor.execute(f'''
                INSERT INTO {self.table_name} (key, version, value)
                VALUES (?, ?, ?)
            ''', (key, version, json.dumps(value)))
            conn.commit()
            return value
        
        existing_version, existing_value = row
        
        if existing_version != version:
            # Version is different, update it
            cursor.execute(f'''
                UPDATE {self.table_name}
                SET version = ?, value = ?
                WHERE key = ?
            ''', (version, json.dumps(value), key))
            conn.commit()
            return value
            
        # Version is the same, return existing value without changing it
        return json.loads(existing_value)
    
    def set(self, key: str, value: Any) -> None:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if the key exists
        cursor.execute(f'''
            SELECT COUNT(*)
            FROM {self.table_name}
            WHERE key = ?
        ''', (key,))
        row = cursor.fetchone()
        
        if row and row[0] > 0:
            # Key exists, update it
            cursor.execute(f'''
                UPDATE {self.table_name}
                SET value = ?
                WHERE key = ?
            ''', (json.dumps(value), key))
        else:
            # Key doesn't exist, insert it with a default version
            cursor.execute(f'''
                INSERT INTO {self.table_name} (key, version, value)
                VALUES (?, ?, ?)
            ''', (key, "1.0", json.dumps(value)))
        
        conn.commit()
    
    def get(self, key: str, default: Any = None) -> Any:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f'''
            SELECT value
            FROM {self.table_name}
            WHERE key = ?
        ''', (key,))
        row = cursor.fetchone()
        if row:
            return json.loads(row[0])
        return default

    def get_all(self) -> dict[str, Any]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f'''
            SELECT key, value
            FROM {self.table_name}
        ''')
        rows = cursor.fetchall()
        return {row[0]: json.loads(row[1]) for row in rows}
    
    def delete(self, key: str) -> None:
        conn = get_connection()
        cursor = conn.cursor()
        _ = cursor.execute(f'''
            DELETE FROM {self.table_name}
            WHERE key = ?
        ''', (key,))
        conn.commit()
    
    def delete_all(self) -> None:
        conn = get_connection()
        cursor = conn.cursor()
        _ = cursor.execute(f'''
            DELETE FROM {self.table_name}
        ''')
        conn.commit()