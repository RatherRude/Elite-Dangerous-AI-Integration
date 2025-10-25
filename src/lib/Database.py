import json
import math
import os
import sqlean as sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping, TypedDict, final
import sqlite_vec
import threading

from .Logger import log
from .Config import get_cn_appdata_path

def get_db_path() -> str:
    return os.path.join(get_cn_appdata_path(), 'covas.db')

def sanitize_fts5_query(query: str) -> str:
    """
    Sanitize a query string for FTS5 MATCH by escaping quotes and wrapping in quotes.
    This prevents syntax errors from special FTS5 characters like '.', ':', '(', ')', etc.
    """
    # Escape double quotes by doubling them (FTS5 syntax)
    escaped = query.replace('"', '""')
    # Wrap in double quotes to treat as literal phrase
    return f'"{escaped}"'

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


@dataclass
class _HybridEntry:
    content: str
    metadata: dict[str, object]
    vector_score: float | None = None
    keyword_score: float | None = None
    vector_rank: int | None = None
    keyword_rank: int | None = None


class VectorSearchResult(TypedDict):
    id: int
    content: str
    metadata: dict[str, object]
    score: float
    vector_score: float | None
    keyword_score: float | None


class VectorStoreEntry(TypedDict):
    id: int
    content: str
    metadata: dict[str, object]
    inserted_at: str | None


class VectorStoreDateSummary(TypedDict):
    date: str
    count: int

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
    RRF_K = 0

    def __init__(self, store_name: str):
        self.store_name = store_name
        self.table_name = f'{store_name}_v1'
        self.vector_table = f'{store_name}_vec_v1'
        self.meta_table = f'{store_name}_vec_meta_v1'
        self.keyword_table = f'{store_name}_vec_keywords_v1'
        self.initialized = False
        self.keywords_enabled = False
    
    @staticmethod
    def _load_metadata(raw: str | None) -> dict[str, object]:
        if raw is None:
            return {}
        loaded: object = json.loads(raw)
        if isinstance(loaded, dict):
            return {str(key): value for key, value in loaded.items()}
        return {}

    def _table_exists(self, table_name: str) -> bool:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return cursor.fetchone() is not None

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
            cursor.execute(f'DROP TABLE IF EXISTS {self.keyword_table}')
            

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
        self.keywords_enabled = False
        try:
            cursor.execute(f'''
                CREATE VIRTUAL TABLE IF NOT EXISTS {self.keyword_table} USING fts5(
                    content,
                    tokenize='porter'
                )
            ''')
            self.keywords_enabled = True
        except Exception as exc:
            self.keywords_enabled = False
            log('warn', f"VectorStore '{self.store_name}' keyword index unavailable: {exc}")
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


    def store(self, model_name: str, content: str, embedding: list[float], metadata: Mapping[str, object]) -> None:
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
        metadata_payload = dict(metadata)
        cursor.execute(f'''
            INSERT OR REPLACE INTO {self.table_name} (content, metadata)
            VALUES (?, ?)
        ''', (content, json.dumps(metadata_payload)))

        # Get the AUTOINCREMENT primary key for the just inserted row
        row_id = cursor.lastrowid

        # Convert embedding to JSON format for the vec table
        embedding_json = json.dumps(embedding)

        # Store the embedding in the vector table, using the id as rowid
        cursor.execute(f'''
            INSERT OR REPLACE INTO {self.vector_table} (rowid, embedding)
            VALUES (?, ?)
        ''', (row_id, embedding_json))

        if self.keywords_enabled:
            cursor.execute(f'''
                INSERT OR REPLACE INTO {self.keyword_table} (rowid, content)
                VALUES (?, ?)
            ''', (row_id, content))

        conn.commit()

    def search(self, query: str, model_name: str, query_embedding: list[float], n: int = 5) -> list[VectorSearchResult]:
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

        combined: dict[int, _HybridEntry] = {}
        vector_entries: list[tuple[int, str, dict[str, object], float]] = []
        for row in results:
            record_id = row[0]
            content = row[1]
            metadata = self._load_metadata(row[2])
            distance = float(row[3]) if row[3] is not None else 0.0
            vector_score = max(0.0, 1.0 - distance)
            vector_entries.append((record_id, content, metadata, vector_score))

        vector_entries.sort(key=lambda item: item[3], reverse=True)
        for rank, (record_id, content, metadata, vector_score) in enumerate(vector_entries, start=1):
            entry = combined.get(record_id)
            if entry is None:
                combined[record_id] = _HybridEntry(
                    content=content,
                    metadata=metadata,
                    vector_score=vector_score,
                    vector_rank=rank,
                )
            else:
                entry.content = content
                entry.metadata = metadata
                entry.vector_score = vector_score
                entry.vector_rank = rank

        keyword_rows: list[tuple[int, str, str, float]] = []
        if self.keywords_enabled and query.strip():
            sanitized_query = sanitize_fts5_query(query)
            cursor.execute(f'''
                SELECT d.id, d.content, d.metadata, bm25({self.keyword_table}) as score
                FROM {self.keyword_table}
                JOIN {self.table_name} d ON d.id = {self.keyword_table}.rowid
                WHERE {self.keyword_table} MATCH ?
                ORDER BY score
                LIMIT ?
            ''', (sanitized_query, max(n * 2, n)))
            keyword_rows = cursor.fetchall()

        keyword_entries: list[tuple[int, str, dict[str, object], float]] = []
        for row in keyword_rows:
            record_id = row[0]
            content = row[1]
            metadata = self._load_metadata(row[2])
            raw_keyword_distance = float(row[3]) if row[3] is not None else None
            if raw_keyword_distance is None:
                continue
            if not math.isfinite(raw_keyword_distance):
                log('warn', "VectorStore keyword search returned non-finite bm25 distance", {
                    'store': self.store_name,
                    'record_id': record_id,
                    'bm25': raw_keyword_distance,
                })
                continue
            if raw_keyword_distance < 0.0:
                log('warn', "VectorStore keyword search returned negative bm25 distance", {
                    'store': self.store_name,
                    'record_id': record_id,
                    'bm25': raw_keyword_distance,
                })
                raw_keyword_distance = 0.0
            keyword_score = 1.0 / (1.0 + raw_keyword_distance)
            keyword_entries.append((record_id, content, metadata, keyword_score))

        keyword_entries.sort(key=lambda item: item[3], reverse=True)
        for rank, (record_id, content, metadata, keyword_score) in enumerate(keyword_entries, start=1):
            entry = combined.get(record_id)
            if entry is None:
                combined[record_id] = _HybridEntry(
                    content=content,
                    metadata=metadata,
                    keyword_score=keyword_score,
                    keyword_rank=rank,
                )
            else:
                entry.content = content
                entry.metadata = metadata
                entry.keyword_score = keyword_score
                entry.keyword_rank = rank

        ranked: list[VectorSearchResult] = []
        for record_id, entry in combined.items():
            vector_score = entry.vector_score
            keyword_score = entry.keyword_score
            final_score = 0.0
            if entry.vector_rank is not None:
                final_score += 1.0 / (self.RRF_K + entry.vector_rank)
            if entry.keyword_rank is not None:
                final_score += 1.0 / (self.RRF_K + entry.keyword_rank)
            if final_score == 0.0:
                continue
            ranked.append(
                VectorSearchResult(
                    id=record_id,
                    content=entry.content,
                    metadata=entry.metadata,
                    score=final_score,
                    vector_score=vector_score,
                    keyword_score=keyword_score,
                )
            )

        ranked.sort(key=lambda item: item['score'], reverse=True)
        log('info', 'vectorstore search result', ranked)
        return ranked[:n]

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

        if self.keywords_enabled:
            cursor.execute(f'''
                DELETE FROM {self.keyword_table}
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

        if self.keywords_enabled:
            cursor.execute(f'''
                DELETE FROM {self.keyword_table}
            ''')

        conn.commit()

    def get_entries_by_date(self, target_date: date | str) -> list[VectorStoreEntry]:
        """Return stored entries for a given calendar date."""
        date_value = target_date.isoformat() if isinstance(target_date, date) else target_date
        if not self._table_exists(self.table_name):
            return []
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            f'''
                SELECT id, content, metadata, inserted_at
                FROM {self.table_name}
                WHERE DATE(inserted_at) = ?
                ORDER BY inserted_at ASC
            ''',
            (date_value,),
        )
        rows = cursor.fetchall()
        entries: list[VectorStoreEntry] = []
        for row in rows:
            entries.append(
                VectorStoreEntry(
                    id=row[0],
                    content=row[1],
                    metadata=self._load_metadata(row[2]),
                    inserted_at=row[3],
                )
            )
        return entries

    def get_available_dates(self, limit: int = 365) -> list[VectorStoreDateSummary]:
        """Return the most recent dates that contain stored entries."""
        if not self._table_exists(self.table_name):
            return []
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            f'''
                SELECT DATE(inserted_at) as date, COUNT(*) as count
                FROM {self.table_name}
                WHERE inserted_at IS NOT NULL
                GROUP BY DATE(inserted_at)
                ORDER BY date DESC
                LIMIT ?
            ''',
            (limit,),
        )
        rows = cursor.fetchall()
        summaries: list[VectorStoreDateSummary] = []
        for row in rows:
            summaries.append(
                VectorStoreDateSummary(
                    date=row[0],
                    count=int(row[1]) if row[1] is not None else 0,
                )
            )
        return summaries

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