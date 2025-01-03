import json
import os
import pytest
import time

from src.lib.StatusParser import StatusParser

@pytest.fixture
def status_file_path(tmp_path):
    status_data = {
        "event": "Status",
        "timestamp": "2024-11-12T13:14:15Z",
        "Flags": 16777216,
        "GuiFocus": 0
    }
    file_path = tmp_path / "Status.json"
    with open(file_path, "w") as f:
        json.dump(status_data, f)
    return tmp_path

def test_statusparser_file_update(status_file_path):
    parser = StatusParser(str(status_file_path))
    time.sleep(0.1)  # Let the watch thread start
    
    # Update file with new status
    new_status = {
        "Flags": 16777220,
        "GuiFocus": 1
    }
    with open(os.path.join(status_file_path, "Status.json"), "w") as f:
        json.dump(new_status, f)
    
    # Wait for update
    status_event = parser.status_queue.get(timeout=1)
    assert status_event["event"] == "Status"
    assert status_event["flags"]["LandingGearDown"] == True
    landinggear_event = parser.status_queue.get(timeout=1)
    assert landinggear_event["event"] == "LandingGearDown"
