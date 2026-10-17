import importlib
import json
from pathlib import Path
import queue
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
ChatModule = importlib.import_module("Chat")
from lib.STT import STTResult
from lib.TTS import TTSLine
from lib.VoiceActivation import VoiceActivation, load_voice_phrases


@pytest.fixture
def chat(monkeypatch):
    instance = ChatModule.Chat.__new__(ChatModule.Chat)
    model = MagicMock()
    session = VoiceActivation("Simone", 10, model, model)
    instance.stt = SimpleNamespace(
        voice_activation=session, recording=False, processing=False, resultQueue=queue.Queue()
    )
    instance.tts = MagicMock()
    instance.tts.get_is_playing.return_value = False
    instance.tts.say.side_effect = lambda *args, **kwargs: TTSLine()
    instance.ttsModel = model
    instance.assistant = SimpleNamespace(reply_pending=False, is_replying=False)
    instance.event_manager = MagicMock()
    instance._voice_mode_enabled = True
    instance._voice_activation_provider = "test-stt"
    instance._voice_activation_warning = ""
    instance._last_voice_state = None
    instance._voice_control_line = None
    instance.config = {"wake_word_name": "Simone"}
    monkeypatch.setattr(ChatModule, "emit_message", MagicMock())
    return instance


def input_result(chat, text):
    session = chat.stt.voice_activation
    result = session.recognize(session.begin_audio(), lambda _: text)
    session.end_audio()
    return STTResult(result.text, None, 0, result)


def test_invocation_command_is_added_once(chat):
    chat._handle_stt_result(input_result(chat, "Hey Simone, plot a route"))
    chat.event_manager.add_conversation_event.assert_called_once_with("user", "plot a route")
    chat.tts.abort.assert_called_once()


def test_call_alone_uses_direct_tts_without_llm(chat):
    chat._handle_stt_result(input_result(chat, "OK Simone"))
    assert chat.tts.say.call_args.args[0] in ("Yes?", "What is it?")
    assert chat.tts.say.call_args.kwargs["retry_on_error"] is False
    chat.event_manager.add_conversation_event.assert_not_called()
    assert chat.stt.voice_activation.suppressed
    chat._voice_control_line.mark_completed()
    chat._update_voice_activation()
    assert not chat.stt.voice_activation.suppressed
    assert chat.stt.voice_activation.active
    chat.event_manager.add_assistant_complete_event.assert_called_once()


def test_close_confirmation_does_not_reopen_dialogue(chat):
    input_result(chat, "Simone, plot a route")
    chat._handle_stt_result(input_result(chat, "j'ai termin\u00e9"))
    assert chat.tts.say.call_args.args[0] in ("d'accord", "tr\u00e8s bien")
    assert chat.stt.voice_activation.state == "standby"
    chat._voice_control_line.mark_completed()
    chat._update_voice_activation()
    assert chat.stt.voice_activation.state == "standby"
    chat.event_manager.add_conversation_event.assert_not_called()


@pytest.mark.parametrize("utterance,response,state", [
    ("Listen up Simone?", "Ready.", "active"),
    ("Simone, conversation finished", "Understood.", "standby"),
])
def test_control_acknowledgments_use_external_phrase_file(chat, tmp_path, utterance, response, state):
    path = tmp_path / "voice_phrases.json"
    path.write_text(json.dumps({
        "default_language": "en",
        "languages": {
            "en": {
                "invocation_prefixes": ["Listen up"],
                "closing_phrases": ["conversation finished"],
                "wake_acknowledgments": ["Ready."],
                "close_acknowledgments": ["Understood."],
            },
        },
    }), encoding="utf-8")
    model = MagicMock()
    chat.stt.voice_activation = VoiceActivation(
        "Simone", 10, model, model, phrases=load_voice_phrases(path)
    )
    chat._handle_stt_result(input_result(chat, utterance))
    chat.tts.say.assert_called_once()
    assert chat.tts.say.call_args.args[0] == response
    assert chat.stt.voice_activation.state == state
    chat.event_manager.add_conversation_event.assert_not_called()
    chat._voice_control_line.mark_completed()
    chat._update_voice_activation()
    assert chat.stt.voice_activation.state == state
    assert not chat.stt.voice_activation.suppressed


@pytest.mark.parametrize("tts_language,stt_language,utterance,language", [
    ("fr-FR", "en", "Simone?", "fr"),
    ("en-US", "fr", "Simone, j'ai termin\u00e9", "en"),
    (None, "fr", "Simone?", "fr"),
    (None, None, "Simone, I'm done", "en"),
    (None, None, "Simone, j'ai termin\u00e9", "fr"),
])
def test_acknowledgments_follow_language_priority(chat, tts_language, stt_language, utterance, language):
    model = MagicMock()
    session = VoiceActivation(
        "Simone", 10, model, model, tts_language=tts_language, stt_language=stt_language,
    )
    chat.stt.voice_activation = session
    result = input_result(chat, utterance)
    chat._handle_stt_result(result)
    localized = session.phrases.languages[language]
    responses = localized.wake_acknowledgments if result.voice_input.kind == "wake" else localized.close_acknowledgments
    assert chat.tts.say.call_args.args[0] in responses
    chat.event_manager.add_conversation_event.assert_not_called()


def test_name_only_acknowledgment_uses_language_of_previous_command(chat):
    model = MagicMock()
    chat.stt.voice_activation = VoiceActivation(
        "Simone", 10, model, model, detect_language=lambda _: "fr",
    )
    chat._handle_stt_result(input_result(chat, "Simone, pr\u00e9pare une route vers Sol"))
    chat._handle_stt_result(input_result(chat, "Simone?"))
    assert chat.tts.say.call_args.args[0] in ("Oui", "Qu'y a-t-il ?")


def test_stale_command_is_not_executed_after_closing(chat):
    old = input_result(chat, "Simone, plot a route")
    chat._handle_stt_result(input_result(chat, "that's all"))
    chat.tts.abort.reset_mock()
    chat._handle_stt_result(old)
    chat.tts.abort.assert_not_called()
    chat.event_manager.add_conversation_event.assert_not_called()


def test_tts_disabled_releases_control_and_reports_it(chat, monkeypatch):
    notify = MagicMock()
    monkeypatch.setattr(ChatModule, "show_chat_message", notify)
    chat.ttsModel = None
    chat._handle_stt_result(input_result(chat, "Simone"))
    assert chat._voice_control_line is None
    assert not chat.stt.voice_activation.suppressed
    assert any(call.args[0] == "warning" for call in notify.call_args_list)
    chat.tts.say.assert_not_called()


@pytest.mark.parametrize("owner,flag", [
    ("assistant", "reply_pending"), ("assistant", "is_replying"),
    ("stt", "processing"), ("stt", "recording"),
])
def test_runtime_keeps_session_open_while_exchange_is_busy(chat, owner, flag):
    now = [0.0]
    session = chat.stt.voice_activation
    session._clock = lambda: now[0]
    input_result(chat, "Simone, plot a route")
    chat._update_voice_activation()
    setattr(getattr(chat, owner), flag, True)
    now[0] = 5
    chat._update_voice_activation()
    now[0] = 50
    chat._update_voice_activation()
    assert session.active
    setattr(getattr(chat, owner), flag, False)
    chat._update_voice_activation()
    now[0] = 59.999
    chat._update_voice_activation()
    assert session.active
    now[0] = 60
    chat._update_voice_activation()
    assert session.state == "standby"


def test_runtime_emits_state_only_on_change_and_on_resynchronization(chat):
    chat._emit_voice_activation()
    chat._emit_voice_activation()
    assert ChatModule.emit_message.call_count == 1
    chat._emit_voice_activation(force=True)
    assert ChatModule.emit_message.call_count == 2
    assert ChatModule.emit_message.call_args.kwargs["state"] == "standby"


def test_legacy_and_keyboard_input_are_not_gated_by_voice_state(chat):
    chat.stt.voice_activation = None
    chat._handle_stt_result(STTResult("legacy command", None, 0))
    chat.event_manager.add_conversation_event.assert_called_once_with("user", "legacy command")
    chat.event_manager.reset_mock()
    chat.submit_input("typed command")
    chat.event_manager.add_conversation_event.assert_called_once_with("user", "typed command")
