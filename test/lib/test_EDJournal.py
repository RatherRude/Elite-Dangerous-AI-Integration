import json
import pytest
import time
from datetime import datetime, timezone
from pathlib import Path
from src.lib.EDJournal import EDJournal

@pytest.fixture
def journal_dir(tmp_path):
    return str(tmp_path)

@pytest.fixture
def journal_file(journal_dir):
    timestamp = "2024-01-01T12:00:00Z"
    initial_events = [
        {"timestamp": timestamp, "event": "Startup"},
        {"timestamp": timestamp, "event": "LoadGame"},
    ]
    
    file_path = Path(journal_dir) / "Journal.2024-01-01T120000.01.log"
    with open(file_path, "w") as f:
        for event in initial_events:
            f.write(json.dumps(event) + "\n")
    return str(file_path)

def write_event(file_path, event_name="TestEvent"):
    """Helper to write a test event to journal file"""
    event_data = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event": event_name
    }
    with open(file_path, "a") as f:
        f.write(json.dumps(event_data) + "\n")
    return event_data

def test_edjournal_new_events(journal_file):
    """Test background thread detects new events"""
    journal = EDJournal({}, Path(journal_file).parent.as_posix())

    # Write new event
    new_event = write_event(journal_file)

    # Wait for event to be processed  
    event = journal.events.get(timeout=1)
    assert event["event"] == new_event["event"]
    assert event["timestamp"] == new_event["timestamp"]
    assert event["id"].endswith(".000003")
    
def test_edjournal_init_empty(journal_dir):
    """Test initialization with empty directory"""
    journal = EDJournal({}, journal_dir)
    assert journal.historic_events == []
    assert journal.events.empty()

def test_edjournal_load_history(journal_file):
    """Test loading historic events"""
    journal = EDJournal({}, Path(journal_file).parent.as_posix())
    assert len(journal.historic_events) == 2
    assert journal.historic_events[0]["event"] == "Startup"
    assert journal.historic_events[1]["event"] == "LoadGame"
    
    # Verify event IDs are correctly generated
    assert journal.historic_events[0]["id"].endswith(".000001")
    assert journal.historic_events[1]["id"].endswith(".000002")

def test_edjournal_multiple_files(journal_dir):
    """Test handling multiple journal files"""
    # Create two journal files
    file1 = Path(journal_dir) / "Journal.2024-01-01T120000.01.log"
    file2 = Path(journal_dir) / "Journal.2024-01-01T130000.01.log"
    
    with open(file1, "w") as f:
        f.write(json.dumps({"timestamp": "2024-01-01T12:00:00Z", "event": "File1Event"}) + "\n")
    time.sleep(0.1)  # Ensure different modification times
    with open(file2, "w") as f:
        f.write(json.dumps({"timestamp": "2024-01-01T13:00:00Z", "event": "File2Event"}) + "\n")
        
    journal = EDJournal({}, journal_dir)
    
    # Should load from most recent file (file2)
    assert len(journal.historic_events) == 1
    assert journal.historic_events[0]["event"] == "File2Event"

def test_edjournal_switch_to_new_file(journal_dir):
    """Test switching to newer journal file during runtime"""
    # Create initial journal file
    file1 = Path(journal_dir) / "Journal.2024-01-01T120000.01.log"

    # Initialize journal reader
    journal = EDJournal({}, journal_dir)
    time.sleep(0.1)  # Let reader start monitoring
    
    write_event(file1, "File1Event2")

    event = journal.events.get(timeout=1)
    assert event["event"] == "File1Event2"
        
    # Create newer journal file
    file2 = Path(journal_dir) / "Journal.2024-01-01T130000.01.log" 
        
    write_event(file2, "File2Event1")

    # Verify event from new file is detected
    event = journal.events.get(timeout=1)
    assert event["event"] == "File2Event1"
    assert file2.name in event["id"]
