from pathlib import Path
import sys
from unittest.mock import MagicMock, call

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.lib.actions import Actions
from src.lib.EDKeys import EDKeys


@pytest.fixture
def chat_input(monkeypatch):
    keys = MagicMock(spec=EDKeys)
    monkeypatch.setattr(Actions, "keys", keys)
    monkeypatch.setattr(Actions, "setGameWindowActive", MagicMock())
    monkeypatch.setattr(Actions, "sleep", lambda _: None)
    for channel in ("local", "wing", "system", "squadron", "direct"):
        monkeypatch.setattr(Actions, f"chat_{channel}_tabbed", False)
    return keys


@pytest.mark.parametrize("channel, prefix", [
    (None, "/l "),
    ("local", "/l "),
    ("LOCAL", "/l "),
    ("wing", "/w "),
    ("system", "/sy "),
    ("squadron", "/s "),
    ("commander", "/d CMDR Étoile 🚀 "),
])
@pytest.mark.parametrize("status, panel", [
    ({"flags": {"InMainShip": True}}, "QuickCommsPanel"),
    ({"flags": {"InFighter": True}}, "QuickCommsPanel"),
    ({"flags": {"InSRV": True}}, "QuickCommsPanel_Buggy"),
    ({"flags2": {"OnFoot": True}}, "QuickCommsPanel_Humanoid"),
])
def test_chat_uses_shared_text_sender_for_commands_and_messages(
    chat_input, monkeypatch, channel, prefix, status, panel
):
    monkeypatch.setattr(Actions, "get_state_dict", lambda states, name: status)
    message = "Wolf 397, BD+21 55 — rendez-vous à l’étoile 🚀"

    result = Actions.send_message(
        {"channel": channel, "recipient": "CMDR Étoile 🚀", "message": message}, {}
    )

    assert result.startswith("Message sent")
    assert chat_input.method_calls == [
        call.send(panel),
        call.send_text(prefix),
        call.send_text(message),
        call.send_key("Down", "Key_Enter"),
        call.send_key("Up", "Key_Enter"),
    ]


@pytest.mark.parametrize("channel, setting, prefix", [
    ("local", "local", "/l "),
    ("wing", "wing", "/w "),
    ("system", "system", "/sy "),
    ("squadron", "squadron", "/s "),
    ("commander", "direct", "/d Étoile "),
])
def test_tabbed_chat_selection_stays_a_physical_binding(
    chat_input, monkeypatch, channel, setting, prefix
):
    monkeypatch.setattr(Actions, "get_state_dict", lambda states, name: {"flags": {"InMainShip": True}})
    monkeypatch.setattr(Actions, f"chat_{setting}_tabbed", True)

    Actions.send_message({"channel": channel, "recipient": "Étoile", "message": "Hello"}, {})

    assert chat_input.method_calls == [
        call.send("QuickCommsPanel"),
        call.send_text(prefix),
        call.send("UI_Select"),
        call.send_text("Hello"),
        call.send_key("Down", "Key_Enter"),
        call.send_key("Up", "Key_Enter"),
    ]


def test_long_messages_keep_chunking_and_unicode_text(chat_input, monkeypatch):
    monkeypatch.setattr(Actions, "get_state_dict", lambda states, name: {"flags": {"InMainShip": True}})
    message = "é" * 99 + "🚀" + "Wolf 397 " * 12

    Actions.send_message({"channel": "wing", "message": message}, {})

    chunks = [message[start:start + 100] for start in range(0, len(message), 100)]
    expected_calls = []
    for chunk in chunks:
        expected_calls.extend([
            call.send("QuickCommsPanel"),
            call.send_text("/w "),
            call.send_text(chunk),
            call.send_key("Down", "Key_Enter"),
            call.send_key("Up", "Key_Enter"),
        ])
    assert chat_input.method_calls == expected_calls


@pytest.mark.parametrize("fail_on_prefix", [True, False])
def test_text_input_failure_does_not_submit_partial_chat(chat_input, monkeypatch, fail_on_prefix):
    monkeypatch.setattr(Actions, "get_state_dict", lambda states, name: {"flags": {"InMainShip": True}})
    failure = RuntimeError("Windows rejected Unicode input")
    chat_input.send_text.side_effect = [failure] if fail_on_prefix else [None, failure]

    with pytest.raises(RuntimeError, match="Windows rejected Unicode input"):
        Actions.send_message({"channel": "local", "message": "Wolf 397"}, {})

    chat_input.send_key.assert_not_called()
    assert chat_input.send_text.call_count == (1 if fail_on_prefix else 2)
