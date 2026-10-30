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
ConfigModule = importlib.import_module("lib.Config")
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
    instance.tts.play_listening_end_tone.side_effect = lambda: TTSLine()
    instance.ttsModel = model
    instance.assistant = SimpleNamespace(reply_pending=False, is_replying=False)
    instance.event_manager = MagicMock()
    instance._voice_mode_enabled = True
    instance._voice_activation_provider = "test-stt"
    instance._voice_activation_warning = ""
    instance._last_voice_state = None
    instance._voice_control_line = None
    instance._voice_timeout_line = None
    instance.config = {}
    instance.character = {"name": "Default (Copy)", "first_name": "Simone"}
    monkeypatch.setattr(ChatModule, "emit_message", MagicMock())
    return instance


@pytest.mark.parametrize("index,name", [
    (0, "Simone"), (1, "Simone"), (1, "Astra"), (1, "L\u00e9a Marie"),
])
def test_session_start_uses_first_name_not_technical_profile_name(monkeypatch, tmp_path, index, name):
    monkeypatch.chdir(tmp_path)
    config = ConfigModule.load_config()
    config["characters"].append({
        **config["characters"][0], "name": "Default (Copy)", "first_name": "Astra",
    })
    config["characters"][index]["first_name"] = name
    config["active_character_index"] = index
    config["ptt_var"] = "wake_word"
    config["stt_provider"] = ChatModule.PARAKEET_PROVIDER
    model = SimpleNamespace(language="en")
    manager = MagicMock()
    manager.create_plugin_model.return_value = model
    manager.get_plugin_provider.return_value = None
    manager.detect_language.return_value = None
    for dependency in ("ControllerManager", "ActionManager", "EDJournal", "TTS"):
        monkeypatch.setattr(ChatModule, dependency, MagicMock())
    monkeypatch.setattr(ChatModule, "get_ed_journals_path", lambda _: str(tmp_path))
    emitted = MagicMock()
    monkeypatch.setattr(ChatModule, "emit_message", emitted)

    class SpeechSetupComplete(Exception):
        pass

    stt = MagicMock(side_effect=SpeechSetupComplete)
    monkeypatch.setattr(ChatModule, "STT", stt)
    with pytest.raises(SpeechSetupComplete):
        ChatModule.Chat(config, manager)

    session = stt.call_args.kwargs["voice_activation"]
    assert session.name == name
    emitted.assert_any_call("voice_activation", state="preparing", name=name)
    technical_name = config["characters"][index]["name"]
    assert session.recognize(session.begin_audio(), lambda _: f"{technical_name}, plot a route") is None
    session.end_audio()
    other = "Simone" if name != "Simone" else "Astra"
    assert session.recognize(session.begin_audio(), lambda _: f"{other}, plot a route") is None
    session.end_audio()
    result = session.recognize(session.begin_audio(), lambda _: f"{name}, plot a route")
    session.end_audio()
    assert result is not None
    assert result.kind == "command"
    assert result.text == "plot a route"


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


@pytest.mark.parametrize("tts_enabled", [True, False])
def test_keep_listening_is_a_direct_control_and_close_restores_timeout(chat, tts_enabled):
    now = [0.0]
    session = chat.stt.voice_activation
    session._clock = lambda: now[0]
    if not tts_enabled:
        chat.ttsModel = None
    chat._handle_stt_result(input_result(chat, "Simone, reste en \u00e9coute"))
    if tts_enabled:
        assert chat.tts.say.call_args.args[0] in ("d'accord", "tr\u00e8s bien")
        assert session.suppressed
        chat._voice_control_line.mark_completed()
    else:
        chat.tts.say.assert_not_called()
    chat._update_voice_activation()
    assert not session.suppressed
    chat.tts.play_listening_end_tone.assert_not_called()
    now[0] = 1000
    chat._update_voice_activation()
    assert session.active
    chat.tts.play_listening_end_tone.assert_not_called()
    chat._handle_stt_result(input_result(chat, "\u00c7a sera tout"))
    if tts_enabled:
        chat._voice_control_line.mark_completed()
    chat._update_voice_activation()
    assert session.state == "standby"
    chat.tts.play_listening_end_tone.assert_not_called()
    chat.event_manager.add_conversation_event.assert_not_called()
    chat._handle_stt_result(input_result(chat, "Simone, plot a route"))
    chat.event_manager.add_conversation_event.assert_called_once_with("user", "plot a route")
    chat._update_voice_activation()
    now[0] = 1010
    chat._update_voice_activation()
    assert session.state == "standby"


@pytest.mark.parametrize("tts_enabled", [True, False])
def test_timeout_plays_only_one_local_tone_without_speech_or_history(chat, tts_enabled):
    now = [0.0]
    session = chat.stt.voice_activation
    session._clock = lambda: now[0]
    if not tts_enabled:
        chat.ttsModel = None
    input_result(chat, "Simone, plot a route")
    chat._update_voice_activation()
    now[0] = 9.999
    chat._update_voice_activation()
    chat.tts.play_listening_end_tone.assert_not_called()
    now[0] = 10
    chat._update_voice_activation()
    assert session.state == "standby"
    assert session.suppressed
    chat.tts.play_listening_end_tone.assert_called_once_with()
    for _ in range(3):
        chat._update_voice_activation()
    chat._voice_timeout_line.mark_completed()
    chat._update_voice_activation()
    assert not session.suppressed
    assert chat._voice_timeout_line is None
    chat.tts.play_listening_end_tone.assert_called_once_with()
    chat.tts.say.assert_not_called()
    chat.tts.abort.assert_not_called()
    chat.event_manager.add_conversation_event.assert_not_called()
    chat.event_manager.add_assistant_speaking.assert_not_called()
    chat.event_manager.add_assistant_complete_event.assert_not_called()
    input_result(chat, "Simone, plot another route")
    chat._update_voice_activation()
    now[0] = 20
    chat._update_voice_activation()
    assert chat.tts.play_listening_end_tone.call_count == 2


def test_timeout_from_audio_thread_is_announced_on_next_runtime_update(chat):
    now = [0.0]
    session = chat.stt.voice_activation
    session._clock = lambda: now[0]
    input_result(chat, "Simone, plot a route")
    chat._update_voice_activation()
    now[0] = 10
    assert session.begin_audio() is None
    chat._update_voice_activation()
    chat.tts.play_listening_end_tone.assert_called_once_with()
    chat.tts.say.assert_not_called()


@pytest.mark.parametrize("utterance,response,state", [
    ("Listen up Simone?", "Ready.", "active"),
    ("Simone, conversation finished", "Understood.", "standby"),
    ("Simone, listen without timeout", "Understood.", "active"),
])
def test_control_acknowledgments_use_external_phrase_file(chat, tmp_path, utterance, response, state):
    path = tmp_path / "voice_phrases.json"
    path.write_text(json.dumps({
        "default_language": "en",
        "languages": {
            "en": {
                "invocation_prefixes": ["Listen up"],
                "closing_phrases": ["conversation finished"],
                "keep_listening_phrases": ["listen without timeout"],
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
    ("en-US", "fr", "Simone, reste en \u00e9coute", "en"),
    (None, None, "Simone, reste en \u00e9coute", "fr"),
    (None, None, "Simone, keep listening", "en"),
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


def test_runtime_without_session_reports_first_name_not_profile_name(chat):
    chat.stt.voice_activation = None
    chat.character["first_name"] = "Astra"
    chat._emit_voice_activation(force=True)
    assert ChatModule.emit_message.call_args.kwargs["name"] == "Astra"


def test_legacy_and_keyboard_input_are_not_gated_by_voice_state(chat):
    chat.stt.voice_activation = None
    chat._handle_stt_result(STTResult("legacy command", None, 0))
    chat.event_manager.add_conversation_event.assert_called_once_with("user", "legacy command")
    chat.event_manager.reset_mock()
    chat.submit_input("typed command")
    chat.event_manager.add_conversation_event.assert_called_once_with("user", "typed command")
