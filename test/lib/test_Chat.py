from pathlib import Path
import queue
import sys
from unittest.mock import MagicMock

import pytest

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import Chat as ChatModule


@pytest.fixture
def chat(monkeypatch):
    for name in (
        "show_chat_message",
        "log",
        "registerProjections",
        "register_actions",
        "load_hud_color_matrix",
    ):
        monkeypatch.setattr(ChatModule, name, MagicMock())

    chat = MagicMock()
    chat.config = {
        "commander_name": "Test Commander",
        "ptt_var": "toggle",
        "ptt_key": "Key.space",
    }
    chat.character = {"tts_speed": "1.0"}
    chat.backstory = "Test backstory"
    chat.assistant.reply_pending = False
    chat.stt = object.__new__(ChatModule.STT)
    chat.stt.continuous_listening_paused = False
    chat.stt.continuous_listening_paused_for_response = False
    chat.stt.recording = False
    chat.stt.resultQueue = queue.Queue()
    chat.stt.listen_continuous = MagicMock()
    chat.stt.listen_once_start = MagicMock()
    chat.stt.listen_once_end = MagicMock()
    return chat


@pytest.mark.parametrize("start_muted", [False, True])
@pytest.mark.parametrize("mute_during_response", [False, True])
@pytest.mark.parametrize("secondary_only", [False, True])
def test_toggle_listening_preserves_manual_state_during_responses(
    chat, monkeypatch, start_muted, mute_during_response, secondary_only
):
    chat.config.update({
        "ptt_inverted_var": start_muted,
        "mute_during_response_var": mute_during_response,
    })
    if secondary_only:
        chat.config.update({"ptt_key": "", "ptt_key_secondary": "Button.x2"})

    startup_states = []
    chat.stt.listen_continuous.side_effect = lambda: startup_states.append(
        chat.stt.continuous_listening_paused
    )
    playing_states = [False, True, True, False, False, False, True, False]
    observed_states = []
    chat.tts.get_is_playing.return_value = playing_states[0]

    def tick(_duration):
        observed_states.append((
            chat.stt.continuous_listening_paused,
            chat.stt.continuous_listening_paused_for_response,
        ))
        tick_index = len(observed_states) - 1
        if tick_index in (0, 2, 4):
            on_press, on_release = chat.controller_manager.register_hotkey.call_args.args[1:]
            on_press(None)
            on_release(None)
        if len(observed_states) == len(playing_states):
            raise KeyboardInterrupt
        chat.tts.get_is_playing.return_value = playing_states[len(observed_states)]

    monkeypatch.setattr(ChatModule, "sleep", tick)

    ChatModule.Chat.run(chat)

    assert startup_states == [start_muted]
    manual_states = [
        start_muted, not start_muted, not start_muted, start_muted,
        start_muted, not start_muted, not start_muted, not start_muted,
    ]
    assert observed_states == [
        (manual_paused, mute_during_response and playing)
        for manual_paused, playing in zip(manual_states, playing_states)
    ]
    expected_key = "Button.x2" if secondary_only else "Key.space"
    assert chat.controller_manager.register_hotkey.call_args.args[0] == [expected_key]


def test_push_to_mute_stays_muted_until_release_during_responses(chat, monkeypatch):
    chat.config.update({"ptt_var": "push_to_mute", "mute_during_response_var": True})
    chat.tts.get_is_playing.return_value = False
    observed_states = []

    def tick(_duration):
        observed_states.append(chat.stt.continuous_listening_paused)
        on_press, on_release = chat.controller_manager.register_hotkey.call_args.args[1:]
        if len(observed_states) == 1:
            on_press(None)
            chat.tts.get_is_playing.return_value = True
        elif len(observed_states) == 2:
            chat.tts.get_is_playing.return_value = False
        elif len(observed_states) == 3:
            on_release(None)
        else:
            raise KeyboardInterrupt

    monkeypatch.setattr(ChatModule, "sleep", tick)

    ChatModule.Chat.run(chat)

    assert observed_states == [False, True, True, False]
