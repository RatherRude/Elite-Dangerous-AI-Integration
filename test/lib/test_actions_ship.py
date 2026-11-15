from pathlib import Path
import sys
from unittest.mock import Mock, call

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.lib.actions import Actions
from src.lib.projections.current_status import CurrentStatusState, StatusBaseFlags
from src.lib.projections.ship_info import ShipInfoStateModel


@pytest.fixture
def ship_keys(monkeypatch: pytest.MonkeyPatch) -> Mock:
    keys = Mock()
    monkeypatch.setattr(Actions, "keys", keys)
    monkeypatch.setattr(Actions, "setGameWindowActive", Mock())
    return keys


@pytest.mark.parametrize("has_docking_computer", [False, True])
def test_station_liftoff_only_initiates_undocking(
    ship_keys: Mock,
    has_docking_computer: bool,
) -> None:
    result = Actions.liftoff({}, {
        "CurrentStatus": CurrentStatusState(
            flags=StatusBaseFlags(Docked=True, InMainShip=True),
            GuiFocus="NoFocus",
        ),
        "ShipInfo": ShipInfoStateModel(hasDockingComputer=has_docking_computer),
    })

    assert ship_keys.send.call_args_list == [
        call("UI_Down", repeat=3),
        call("UI_Up"),
        call("UI_Select"),
    ]
    assert "Undocking initiated" in result
    assert "only confirms release from the landing pad" in result
    assert "Leave throttle unchanged and do not boost unless the commander explicitly requested it" in result


def test_planetary_liftoff_preserves_vertical_thrust_and_gear_retraction(ship_keys: Mock) -> None:
    result = Actions.liftoff({}, {
        "CurrentStatus": CurrentStatusState(flags=StatusBaseFlags(Landed=True)),
    })

    assert ship_keys.send.call_args_list == [
        call("UpThrustButton", hold=3),
        call("LandingGearToggle"),
    ]
    assert result == "Liftoff initiated and landing gear retracted."


@pytest.mark.parametrize("speed", [
    "Minus100", "Minus75", "Minus50", "Minus25", "Zero", "25", "50", "75", "100",
])
def test_explicit_speed_commands_remain_available_after_undocking(ship_keys: Mock, speed: str) -> None:
    result = Actions.set_speed({"speed": speed}, {
        "CurrentStatus": CurrentStatusState(flags=StatusBaseFlags(InMainShip=True)),
    })

    ship_keys.send.assert_called_once_with(f"SetSpeed{speed}")
    assert result == f"Speed set to {speed}%."
