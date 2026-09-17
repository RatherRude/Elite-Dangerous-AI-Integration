import json
import os
import pytest
import time

from src.lib.StatusParser import StatusParser, parse_odyssey_flags, parse_status_json

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
    
    # Update file with new status: not landed
    old_status = {
        "Flags": 16777218,
        "GuiFocus": 1
    }

    with open(os.path.join(status_file_path, "Status.json"), "w") as f:
        json.dump(old_status, f)

    # Wait for update
    status_event = parser.status_queue.get(timeout=1)
    assert status_event["event"] == "Status"
    assert status_event["flags"]["LandingGearDown"] == False

    # Update file with new status: landed
    new_status = {
        "Flags": 16777220,
        "GuiFocus": 1
    }

    with open(os.path.join(status_file_path, "Status.json"), "w") as f:
        json.dump(new_status, f)

    # Wait for update
    status_event = parser.status_queue.get(timeout=10)
    assert status_event["event"] == "Status"
    assert status_event["flags"]["LandingGearDown"] == True

    landinggear_event = parser.status_queue.get(timeout=10)
    assert landinggear_event["event"] == "LandingGearDown"


def test_parse_odyssey_flags_sco_and_sca():
    flags = parse_odyssey_flags(1048576 | 2097152)

    assert flags["ActiveSCO"] is True
    assert flags["ActiveSCA"] is True
    assert flags["FsdHyperdriveCharging"] is False


@pytest.mark.parametrize(
    ("old_flags2", "new_flags2", "expected_event"),
    [
        (0, 1048576, "SCOActivated"),
        (1048576, 0, "SCODeactivated"),
        (0, 2097152, "SCAActivated"),
        (2097152, 0, "SCADeactivated"),
    ],
)
def test_create_delta_events_for_sco_and_sca(old_flags2, new_flags2, expected_event):
    old_status = parse_status_json({"Flags": 16777216, "Flags2": old_flags2})
    new_status = parse_status_json({"Flags": 16777216, "Flags2": new_flags2})
    parser = StatusParser.__new__(StatusParser)

    assert parser._create_delta_events(old_status, new_status) == [{"event": expected_event}]
