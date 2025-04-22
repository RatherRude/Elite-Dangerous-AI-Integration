import uu
from uuid import uuid4
import uuid
import pytest
import sqlite3
from datetime import datetime
import json
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch
from src.lib.Database import EventStore, KeyValueStore, set_connection_for_testing

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
def db_path(tmp_path):
    return str(tmp_path / "test.db")

@pytest.fixture
def mock_connection(db_path, monkeypatch):
    def mock_get_db_path():
        return db_path
    
    monkeypatch.setattr('src.lib.Database.get_db_path', mock_get_db_path)
    conn = sqlite3.connect(db_path)
    
    # Reset tables that might exist from other tests
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS test_events_v1")
    cursor.execute("DROP TABLE IF EXISTS test_store_v1")
    conn.commit()
    
    # Ensure our tests use this specific connection
    set_connection_for_testing(conn)
    
    return conn

@pytest.fixture
def event_store(mock_connection):
    return EventStore("test_events", [SampleEvent1, SampleEvent2])

@pytest.fixture
def kv_store(mock_connection):
    return KeyValueStore("test_store")

# EventStore Tests
def test_event_store_init(event_store, mock_connection):
    """Test EventStore initialization creates table"""
    cursor = mock_connection.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test_events_v1'")
    assert cursor.fetchone() is not None

def test_event_store_insert(event_store):
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

def test_event_store_get_latest(event_store):
    """Test retrieving latest events with limit"""
    # Clean start
    event_store.delete_all()
    
    for i in range(5):
        event = SampleEvent1(name=f"test_{i}", value=i)
        event_store.insert_event(event, float(i))
    
    events = event_store.get_latest(3)
    assert len(events) == 3
    assert events[0].value == 4  # Latest event first
    assert events[2].value == 2

def test_event_store_delete_all(event_store):
    """Test deleting all events"""
    event = SampleEvent1(name="test", value=42)
    event_store.insert_event(event, 1.0)
    
    event_store.delete_all()
    events = event_store.get_latest()
    assert len(events) == 0

# KeyValueStore Tests
def test_kv_store_init(kv_store, mock_connection):
    """Test KeyValueStore initialization creates table"""
    cursor = mock_connection.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test_store_v1'")
    assert cursor.fetchone() is not None

def test_kv_store_init_method(kv_store):
    """Test init method with version check"""
    # Clean start
    kv_store.delete_all()
    
    value = {"data": "test"}
    
    # Initial set
    result = kv_store.init("key1", "10", value)
    assert result == value
    
    # Same version should return existing value
    new_value = {"data": "different"}
    assert kv_store.get_version("key1") == "10"
    result = kv_store.init("key1", "10", new_value)
    assert result == value
    
    # New version should update value
    result = kv_store.init("key1", "2.0", new_value)
    assert result == new_value

def test_kv_store_set_get(kv_store):
    """Test setting and getting values"""
    # Clean start
    kv_store.delete_all()
    
    kv_store.init("key1", "1.0", "test")
    kv_store.set("key1", "updated")
    
    assert kv_store.get("key1") == "updated"
    assert kv_store.get("nonexistent", "default") == "default"

def test_kv_store_get_all(kv_store):
    """Test getting all values"""
    # Clean start
    kv_store.delete_all()
    
    kv_store.init("key1", "1.0", "value1")
    kv_store.init("key2", "1.0", "value2")
    
    all_values = kv_store.get_all()
    assert len(all_values) == 2
    assert all_values["key1"] == "value1"
    assert all_values["key2"] == "value2"

def test_kv_store_delete(kv_store):
    """Test deleting specific key"""
    # Clean start
    kv_store.delete_all()
    
    kv_store.init("key1", "1.0", "value1")
    kv_store.delete("key1")
    
    assert kv_store.get("key1") is None

def test_kv_store_delete_all(kv_store):
    """Test deleting all keys"""
    # Clean start
    kv_store.delete_all()
    
    kv_store.init("key1", "1.0", "value1")
    kv_store.init("key2", "1.0", "value2")
    
    kv_store.delete_all()
    assert len(kv_store.get_all()) == 0