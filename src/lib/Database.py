import json
import os
import sqlean as sqlite3
from typing import Any, final
import sqlite_vec
import threading

from .Logger import log
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
        
        """Alter table to add deleted column if it doesn't exist yet"""
        cursor.execute(f'''
            PRAGMA table_info({self.table_name})
        ''')
        columns = cursor.fetchall()
        if not any(col[1] == 'responded_at' for col in columns):
            cursor.execute(f'''
                ALTER TABLE {self.table_name}
                ADD COLUMN responded_at FLOAT DEFAULT 0.0
            ''')
        if not any(col[1] == 'memorized_at' for col in columns):
            cursor.execute(f'''
                ALTER TABLE {self.table_name}
                ADD COLUMN memorized_at FLOAT DEFAULT null
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
            INSERT INTO {self.table_name} (class, data, processed_at, memorized_at, responded_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (event_class, event_data, processed_at, None, None))
        if commit:
            conn.commit()

    def get_latest(self, limit: int = 100) -> list[Any]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f'''
            SELECT class, data, processed_at, memorized_at, responded_at
            FROM {self.table_name}
            WHERE memorized_at is NULL
            ORDER BY processed_at DESC
            LIMIT (?)
        ''', (limit,))
        rows = cursor.fetchall()
        events = []
        for row in rows:
            instance = instantiate_class_by_name(self.event_classes, row[0], json.loads(row[1]))
            instance.memorized_at = row[3]
            instance.responded_at = row[4]
            events.append(instance)
        return events

    def replied_before(self, processed_at: float) -> None:
        """Mark events as responded before a certain processed_at timestamp"""
        conn = get_connection()
        cursor = conn.cursor()
        _ = cursor.execute(f'''
            UPDATE {self.table_name}
            SET responded_at = ?
            WHERE processed_at <= ? and responded_at is NULL
        ''', (processed_at,processed_at,))
        conn.commit()

    def memorize_before(self, processed_at: float) -> None:
        """Mark events as memorized before a certain processed_at timestamp"""
        conn = get_connection()
        cursor = conn.cursor()
        _ = cursor.execute(f'''
            UPDATE {self.table_name}
            SET memorized_at = ?
            WHERE processed_at <= ? and memorized_at is NULL
        ''', (processed_at,processed_at,))
        conn.commit()

    def delete_all(self) -> None:
        conn = get_connection()
        cursor = conn.cursor()
        _ = cursor.execute(f'''
            DELETE FROM {self.table_name}
        ''')
        conn.commit()

@final
class VectorStore():
    def __init__(self, store_name: str):
        self.store_name = store_name
        self.table_name = f'{store_name}_v1'
        self.vector_table = f'{store_name}_vec_v1'
        self.meta_table = f'{store_name}_vec_meta_v1'
        self.initialized = False
    
    def get_current_embedding_dim(self) -> int | None:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f'''
            PRAGMA table_info({self.vector_table})
        ''')
        columns = cursor.fetchall()
        if columns:
            # Table exists, check embedding dimension
            cursor.execute(f'''
                SELECT sql
                FROM sqlite_master
                WHERE type='table' AND name=?
            ''', (self.vector_table,))
            row = cursor.fetchone()
            if row:
                create_sql = row[0]
                start = create_sql.find('FLOAT[') + len('FLOAT[')
                end = create_sql.find(']', start)
                if start != -1 and end != -1:
                    try:
                        return int(create_sql[start:end])
                    except ValueError:
                        return None
        return None
    
    def initialize(self, model_name: str, embedding_dim: int) -> None:
        # check if vector table exists and has correct dimension and model name
        current_dim = self.get_current_embedding_dim()
        conn = get_connection()
        cursor = conn.cursor()

        # Attempt to read existing model name metadata
        stored_model_name: str | None = None
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (self.meta_table,),
        )
        if cursor.fetchone():
            cursor.execute(
                f"SELECT value FROM {self.meta_table} WHERE key='model_name'"
            )
            row = cursor.fetchone()
            if row:
                stored_model_name = row[0]

        # Determine mismatch conditions
        mismatches: list[str] = []
        if current_dim is not None and current_dim != embedding_dim:
            mismatches.append(f"dimension {current_dim} (expected {embedding_dim})")
        if stored_model_name is not None and stored_model_name != model_name:
            mismatches.append(f"model '{stored_model_name}' (expected '{model_name}')")

        # On any mismatch, drop existing tables to recreate them fresh
        if mismatches:
            log('warn', f"VectorStore '{self.store_name}' already initialized with {' and '.join(mismatches)}, dropping existing data.")
            cursor.execute(f'DROP TABLE IF EXISTS {self.vector_table}')
            cursor.execute(f'DROP TABLE IF EXISTS {self.table_name}')
            cursor.execute(f'DROP TABLE IF EXISTS {self.meta_table}')
            

        # Always ensure required tables exist (recreate after drop or create if missing)
        # Create table for metadata/content
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT,
                metadata TEXT,
                inserted_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create virtual table for vector storage using sqlite-vec
        cursor.execute(f'''
            CREATE VIRTUAL TABLE IF NOT EXISTS {self.vector_table} USING vec0(
                embedding FLOAT[{embedding_dim}],
            )
        ''')
        
        # Create table for store-level metadata and persist parameters
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {self.meta_table} (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        cursor.execute(f'''
            INSERT INTO {self.meta_table} (key, value)
            VALUES ('model_name', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        ''', (model_name,))
        cursor.execute(f'''
            INSERT INTO {self.meta_table} (key, value)
            VALUES ('embedding_dim', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        ''', (str(embedding_dim),))
        conn.commit()
        
        self.initialized = True


    def store(self, model_name: str, content: str, embedding: list[float], metadata: dict[str, Any]) -> None:
        """
        Store an embedding vector with associated metadata. The AUTOINCREMENT id
        generated for the metadata/content row is reused as the rowid of the
        vector in the virtual table so both can be joined later.
        
        Args:
            content: Raw text/content tied to the embedding
            embedding: List of floats representing the embedding vector
            metadata: Dictionary of metadata to store with the embedding
        """
        if not self.initialized:
            self.initialize(model_name, len(embedding))
        conn = get_connection()
        cursor = conn.cursor()
        # Store metadata in the main table
        cursor.execute(f'''
            INSERT OR REPLACE INTO {self.table_name} (content, metadata)
            VALUES (?, ?)
        ''', (content, json.dumps(metadata)))

        # Get the AUTOINCREMENT primary key for the just inserted row
        row_id = cursor.lastrowid

        # Convert embedding to JSON format for the vec table
        embedding_json = json.dumps(embedding)

        # Store the embedding in the vector table, using the id as rowid
        cursor.execute(f'''
            INSERT OR REPLACE INTO {self.vector_table} (rowid, embedding)
            VALUES (?, ?)
        ''', (row_id, embedding_json))

        conn.commit()

    def search(self, query: str, model_name: str, query_embedding: list[float], n: int = 5) -> list[tuple[int, str, dict[str, Any], float]]:
        """
        Search for similar embeddings
        
        Args:
            query_embedding: The embedding vector to search for
            n: Number of results to return
            
        Returns:
            List of tuples containing (id, metadata, similarity_score)
        """
        if not self.initialized:
            self.initialize(model_name, len(query_embedding))
            return []
        conn = get_connection()
        cursor = conn.cursor()
        # Convert query embedding to JSON for the match query
        query_json = json.dumps(query_embedding)

        # Query for nearest neighbors using vector similarity
        cursor.execute(f'''
            with knn_matches as (
                select
                    rowid,
                    distance
                from {self.vector_table}
                where embedding match :query
                    and k = :n
            )
            select
            d.id,
            d.content,
            d.metadata,
            knn_matches.distance
            from knn_matches
            left join {self.table_name} d on d.id = knn_matches.rowid
        ''', {"query": query_json, "n": n})

        results = cursor.fetchall()

        # Convert results to the expected format
        return [(row[0], row[1], json.loads(row[2]) if row[2] is not None else {}, 1.0 - row[3]) for row in results]

    def delete(self, id: str) -> None:
        """Delete an embedding by id"""
        if not self.initialized:
            log('error', f"VectorStore '{self.store_name}' not initialized. Call 'initialize' first.")
            return
        conn = get_connection()
        cursor = conn.cursor()
        # Delete from metadata table
        cursor.execute(f'''
            DELETE FROM {self.table_name}
            WHERE id = ?
        ''', (id,))

        # Delete from vector table
        cursor.execute(f'''
            DELETE FROM {self.vector_table}
            WHERE rowid = ?
        ''', (id,))

        conn.commit()

    def delete_all(self) -> None:
        """Delete all embeddings"""
        if not self.initialized:
            log('error', f"VectorStore '{self.store_name}' not initialized. Call 'initialize' first.")
            return
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f'''
            DELETE FROM {self.table_name}
        ''')

        cursor.execute(f'''
            DELETE FROM {self.vector_table}
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