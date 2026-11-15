from pathlib import Path
import sys

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.lib.PromptGenerator import PromptGenerator


@pytest.mark.parametrize("raw_format", [False, True], ids=["projection", "raw-api"])
@pytest.mark.parametrize(
    ("government_fields", "expected_government", "engineer"),
    [
        pytest.param({}, "Federation None", False, id="missing"),
        pytest.param({"government": None}, "Federation None", False, id="null"),
        pytest.param({"government": ""}, "Federation ", False, id="empty"),
        pytest.param({"government": "Corporate"}, "Federation Corporate", False, id="corporate"),
        pytest.param({"government": " Engineer "}, "Federation  Engineer ", True, id="padded-engineer"),
        pytest.param({"government": "eNgInEeR"}, "Federation eNgInEeR", True, id="mixed-case-engineer"),
    ],
)
def test_format_stations_data_handles_optional_government(
    raw_format, government_fields, expected_government, engineer
):
    generator = PromptGenerator.__new__(PromptGenerator)
    station = {
        "name": "Test station",
        "type": "Coriolis Starport",
        "economy": "Industrial",
        "allegiance": "Federation",
        "controllingFaction": "Test faction",
        "materialTrader": "Raw",
        "technologyBroker": "Guardian",
        **government_fields,
    }
    if raw_format:
        station["haveMarket"] = True
        stations_data = {"stations": [station]}
        expected_services = ["market"]
    else:
        station["services"] = ["Market"]
        stations_data = [station]
        expected_services = ["Market"]
    if engineer:
        expected_services.append("Engineer")
    expected_services.extend(["Raw Material Trader", "Guardian Technology Broker"])

    assert generator.format_stations_data(stations_data) == {
        "In Orbit around Primary Star": {
            "Coriolis Starport": [
                {
                    "name": "Test station",
                    "economy": "Industrial",
                    "services": expected_services,
                    "government": expected_government,
                    "controllingFaction": "Test faction",
                }
            ]
        }
    }
