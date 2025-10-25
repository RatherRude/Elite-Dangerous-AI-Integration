import pytest
import sqlean as sqlite3
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Generator
from typing import cast

import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
from src.lib.Database import EventStore, KeyValueStore, VectorStore, set_connection_for_testing
import sqlite_vec

# Test event classes
@dataclass
class SampleEvent1:
    name: str
    value: int

@dataclass 
class SampleEvent2:
    message: str

# Fixtures
@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "test.db")

@pytest.fixture
def mock_connection(db_path: str, monkeypatch: pytest.MonkeyPatch) -> Generator[sqlite3.Connection, None, None]:
    def mock_get_db_path() -> str:
        return db_path
    
    monkeypatch.setattr('src.lib.Database.get_db_path', mock_get_db_path)
    conn = sqlite3.connect(db_path)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    
    # Reset tables that might exist from other tests
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS test_events_v1")
    cursor.execute("DROP TABLE IF EXISTS test_store_v1")
    cursor.execute("DROP TABLE IF EXISTS test_vectors_v1")
    cursor.execute("DROP TABLE IF EXISTS test_vectors_vec_v1")
    cursor.execute("DROP TABLE IF EXISTS test_vectors_vec_meta_v1")
    cursor.execute("DROP TABLE IF EXISTS test_vectors_vec_keywords_v1")
    conn.commit()
    
    # Ensure our tests use this specific connection
    set_connection_for_testing(conn)
    
    try:
        yield conn
    finally:
        conn.close()

@pytest.fixture
def event_store(mock_connection: sqlite3.Connection) -> EventStore:
    _ = mock_connection
    return EventStore("test_events", [SampleEvent1, SampleEvent2])

@pytest.fixture
def kv_store(mock_connection: sqlite3.Connection) -> KeyValueStore:
    _ = mock_connection
    return KeyValueStore("test_store")

@pytest.fixture
def vector_store(mock_connection: sqlite3.Connection) -> VectorStore:
    _ = mock_connection
    return VectorStore("test_vectors")

# EventStore Tests
def test_event_store_init(event_store: EventStore, mock_connection: sqlite3.Connection) -> None:
    """Test EventStore initialization creates table"""
    assert isinstance(event_store, EventStore)
    cursor = mock_connection.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test_events_v1'")
    assert cursor.fetchone() is not None

def test_event_store_insert(event_store: EventStore) -> None:
    """Test inserting events"""
    # Clean start
    event_store.delete_all()
    
    event = SampleEvent1(name="test", value=42)
    processed_at = datetime.now().timestamp()
    
    event_store.insert_event(event, processed_at)
    
    events = event_store.get_latest(1)
    assert len(events) == 1
    assert isinstance(events[0], SampleEvent1)
    assert events[0].name == "test"
    assert events[0].value == 42

def test_event_store_get_latest(event_store: EventStore) -> None:
    """Test retrieving latest events with limit"""
    # Clean start
    event_store.delete_all()
    
    for i in range(5):
        event = SampleEvent1(name=f"test_{i}", value=i)
        event_store.insert_event(event, float(i))
    
    events = event_store.get_latest(3)
    assert len(events) == 3
    assert isinstance(events[0], SampleEvent1)
    assert isinstance(events[2], SampleEvent1)
    assert events[0].value == 4  # Latest event first
    assert events[2].value == 2

def test_event_store_delete_all(event_store: EventStore) -> None:
    """Test deleting all events"""
    event = SampleEvent1(name="test", value=42)
    event_store.insert_event(event, 1.0)
    
    event_store.delete_all()
    events = event_store.get_latest()
    assert len(events) == 0

# KeyValueStore Tests
def test_kv_store_init(kv_store: KeyValueStore, mock_connection: sqlite3.Connection) -> None:
    """Test KeyValueStore initialization creates table"""
    assert isinstance(kv_store, KeyValueStore)
    cursor = mock_connection.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test_store_v1'")
    assert cursor.fetchone() is not None

def test_kv_store_init_method(kv_store: KeyValueStore) -> None:
    """Test init method with version check"""
    # Clean start
    kv_store.delete_all()
    
    value = {"data": "test"}
    
    # Initial set
    result = cast(dict[str, str], kv_store.init("key1", "10", value))
    assert result == value
    
    # Same version should return existing value
    new_value = {"data": "different"}
    assert kv_store.get_version("key1") == "10"
    result = cast(dict[str, str], kv_store.init("key1", "10", new_value))
    assert result == value
    
    # New version should update value
    result = cast(dict[str, str], kv_store.init("key1", "2.0", new_value))
    assert result == new_value

def test_kv_store_set_get(kv_store: KeyValueStore) -> None:
    """Test setting and getting values"""
    # Clean start
    kv_store.delete_all()
    
    kv_store.init("key1", "1.0", "test")
    kv_store.set("key1", "updated")
    
    assert kv_store.get("key1") == "updated"
    assert kv_store.get("nonexistent", "default") == "default"

def test_kv_store_get_all(kv_store: KeyValueStore) -> None:
    """Test getting all values"""
    # Clean start
    kv_store.delete_all()
    
    kv_store.init("key1", "1.0", "value1")
    kv_store.init("key2", "1.0", "value2")
    
    all_values = kv_store.get_all()
    assert len(all_values) == 2
    assert all_values["key1"] == "value1"
    assert all_values["key2"] == "value2"

def test_kv_store_delete(kv_store: KeyValueStore) -> None:
    """Test deleting specific key"""
    # Clean start
    kv_store.delete_all()
    
    kv_store.init("key1", "1.0", "value1")
    kv_store.delete("key1")
    
    assert kv_store.get("key1") is None

def test_kv_store_delete_all(kv_store: KeyValueStore) -> None:
    """Test deleting all keys"""
    # Clean start
    kv_store.delete_all()
    
    kv_store.init("key1", "1.0", "value1")
    kv_store.init("key2", "1.0", "value2")
    
    kv_store.delete_all()
    assert len(kv_store.get_all()) == 0


# VectorStore Tests
def test_vector_store_vector_and_keyword_search(vector_store: VectorStore, mock_connection: sqlite3.Connection) -> None:
    """Vector search ranks hybrid scores and returns typed payloads"""
    _ = mock_connection
    vector_store.delete_all()

    embedding_a = [0.1, 0.2, 0.3]
    embedding_b = [0.9, 0.8, 0.7]

    vector_store.store(
        model_name="test-model",
        content="apple banana smoothie",
        embedding=embedding_a,
        metadata={"tag": "fruit"},
    )
    vector_store.store(
        model_name="test-model",
        content="spicy chili pepper",
        embedding=embedding_b,
        metadata={"tag": "spice"},
    )

    results = vector_store.search(
        query="banana",
        model_name="test-model",
        query_embedding=embedding_a,
        n=2,
    )

    assert len(results) == 2
    first, second = results
    assert first["id"] != second["id"]
    assert first["score"] >= second["score"]
    assert first["metadata"]["tag"] == "fruit"
    assert first["vector_score"] is not None
    assert first["vector_score"] > 0
    assert first["keyword_score"] is not None
    assert first["keyword_score"] > 0
    # Second result should at least retain vector similarity, keyword may be missing
    assert second["vector_score"] is not None