import ast
from collections import defaultdict
from pathlib import Path
import sys
import threading
from time import monotonic
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from openai.types.chat import ChatCompletionMessageFunctionToolCall

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.lib.ActionManager import ActionManager
from src.lib.EventManager import EventManager
from src.lib.projections.common import ProjectedStates, get_state_dict
from src.lib.projections.current_status import CurrentStatus, CurrentStatusState, StatusBaseFlags


@pytest.fixture
def actions():
    # Isolate the real action and registration from optional vision/audio and input imports.
    path = ROOT_DIR / "src" / "lib" / "actions" / "Actions.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    functions = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in ('checkStatus', 'landing_gear_toggle')
    ]
    registration = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and node.value.func.attr == 'registerAction'
        and isinstance(node.value.args[0], ast.Constant)
        and node.value.args[0].value == 'landingGearToggle'
    )
    manager = MagicMock()
    namespace = {
        'ProjectedStates': ProjectedStates,
        'get_state_dict': get_state_dict,
        'setGameWindowActive': MagicMock(),
        'keys': MagicMock(),
        'event_manager': MagicMock(),
        'actionManager': manager,
    }
    exec(compile(ast.Module(body=[*functions, registration], type_ignores=[]), str(path), 'exec'), namespace)
    return SimpleNamespace(
        run=namespace['landing_gear_toggle'],
        keys=namespace['keys'],
        focus=namespace['setGameWindowActive'],
        events=namespace['event_manager'],
        registration=manager.registerAction.call_args,
    )


def status(gear_down, **flags):
    return CurrentStatusState(flags=StatusBaseFlags(LandingGearDown=gear_down, **flags))


@pytest.mark.parametrize(('args', 'initial', 'target'), [
    ({'action': 'deploy'}, False, True),
    ({'action': 'retract'}, True, False),
    ({'action': 'toggle'}, False, True),
    ({'action': 'toggle'}, True, False),
    ({}, False, True),
    ({}, True, False),
])
def test_success_requires_requested_game_status(actions, args, initial, target):
    confirmed = False

    def wait(projection, condition, timeout):
        nonlocal confirmed
        actions.focus.assert_called_once_with()
        actions.keys.send.assert_called_once_with('LandingGearToggle')
        assert projection == 'CurrentStatus'
        assert timeout == 5
        assert not condition(status(initial))
        assert condition(status(target))
        confirmed = True
        return status(target)

    actions.events.wait_for_condition.side_effect = wait

    result = actions.run(args, {'CurrentStatus': status(initial)})

    assert confirmed
    assert result == f"Landing gear {'deployed' if target else 'retracted'}."


@pytest.mark.parametrize(('action', 'gear_down'), [('deploy', True), ('retract', False)])
def test_explicit_request_does_not_toggle_already_correct_gear(actions, action, gear_down):
    result = actions.run({'action': action}, {'CurrentStatus': status(gear_down)})

    assert result == f"Landing gear already {'deployed' if gear_down else 'retracted'}. No changes."
    actions.focus.assert_not_called()
    actions.keys.send.assert_not_called()
    actions.events.wait_for_condition.assert_not_called()


@pytest.mark.parametrize(('action', 'gear_down'), [('deploy', False), ('retract', True)])
def test_unresponsive_game_reports_error_without_retry(actions, action, gear_down):
    actions.events.wait_for_condition.side_effect = TimeoutError('No status change')

    with pytest.raises(TimeoutError, match='not confirmed by the game within 5 seconds'):
        actions.run({'action': action}, {'CurrentStatus': status(gear_down)})

    actions.keys.send.assert_called_once_with('LandingGearToggle')


@pytest.mark.parametrize('flag', ['Docked', 'Landed', 'Supercruise'])
def test_blocked_state_does_not_send_input(actions, flag):
    with pytest.raises(Exception, match=flag):
        actions.run({'action': 'deploy'}, {'CurrentStatus': status(False, **{flag: True})})

    actions.focus.assert_not_called()
    actions.keys.send.assert_not_called()
    actions.events.wait_for_condition.assert_not_called()


def test_invalid_action_does_not_send_input(actions):
    with pytest.raises(ValueError, match='deploy, retract, or toggle'):
        actions.run({'action': 'invalid'}, {'CurrentStatus': status(False)})

    actions.keys.send.assert_not_called()


def test_missing_status_does_not_assume_gear_is_retracted(actions):
    with pytest.raises(RuntimeError, match='status is unavailable'):
        actions.run({'action': 'deploy'}, {})

    actions.keys.send.assert_not_called()


def test_binding_error_is_propagated_without_success(actions):
    actions.keys.send.side_effect = RuntimeError('Missing LandingGearToggle binding')

    with pytest.raises(RuntimeError, match='Missing LandingGearToggle binding'):
        actions.run({'action': 'deploy'}, {'CurrentStatus': status(False)})

    actions.events.wait_for_condition.assert_not_called()


@pytest.fixture
def status_events():
    projection = CurrentStatus()
    projection.state = status(False)
    manager = object.__new__(EventManager)
    manager.projections = [projection]
    manager._registry_lock = threading.Lock()
    manager._conditions_registry = defaultdict(list)
    return manager, projection


def test_status_update_during_key_send_is_confirmed(actions, status_events):
    manager, projection = status_events
    actions.events.wait_for_condition.side_effect = manager.wait_for_condition

    def send(key):
        projection.state = status(True)
        manager.check_conditions('CurrentStatus', projection.state)

    actions.keys.send.side_effect = send

    assert actions.run({'action': 'deploy'}, {'CurrentStatus': projection.state}) == 'Landing gear deployed.'
    actions.events.wait_for_condition.assert_called_once()


def test_unchanged_game_status_times_out_after_five_seconds(actions, status_events):
    manager, projection = status_events
    actions.events.wait_for_condition.side_effect = manager.wait_for_condition
    started = monotonic()

    with pytest.raises(TimeoutError, match='not confirmed by the game within 5 seconds'):
        actions.run({'action': 'deploy'}, {'CurrentStatus': projection.state})

    assert monotonic() - started >= 5
    assert not manager._conditions_registry['CurrentStatus']
    actions.keys.send.assert_called_once_with('LandingGearToggle')


def test_timeout_is_returned_as_tool_error(actions):
    actions.events.wait_for_condition.side_effect = TimeoutError('No status change')
    manager = object.__new__(ActionManager)
    manager.actions = {'landingGearToggle': {'method': actions.run}}
    tool_call = ChatCompletionMessageFunctionToolCall(
        type='function',
        id='call_gear',
        function={'name': 'landingGearToggle', 'arguments': '{"action": "deploy"}'},
    )

    result = manager.runAction(tool_call, {'CurrentStatus': status(False)})

    assert result['tool_call_id'] == 'call_gear'
    assert result['role'] == 'tool'
    assert result['name'] == 'landingGearToggle'
    assert result['content'].startswith('ERROR: TimeoutError(')
    assert result['content'] == (
        "ERROR: TimeoutError('Landing gear deployed was not confirmed by the game within 5 seconds.')"
    )


def test_tool_schema_and_cached_commands_preserve_direction(actions):
    args, kwargs = actions.registration
    assert args[0] == 'landingGearToggle'
    assert args[2]['properties']['action'] == {
        'type': 'string',
        'description': 'Requested landing gear operation',
        'enum': ['deploy', 'retract', 'toggle'],
        'default': 'toggle',
    }
    assert args[4] == ['mainship', 'nomad']
    assert kwargs['permission'] == 'landingGearToggle'
    assert kwargs['cache_prefill'] == {
        'landing gear': {},
        'gear': {},
        'deploy gear': {'action': 'deploy'},
        'retract gear': {'action': 'retract'},
        'landing gear up': {'action': 'retract'},
        'landing gear down': {'action': 'deploy'},
        'gear up': {'action': 'retract'},
        'gear down': {'action': 'deploy'},
    }
