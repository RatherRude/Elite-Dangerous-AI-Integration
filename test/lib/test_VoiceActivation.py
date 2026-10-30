import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest

import src.lib.VoiceActivation as voice_activation_module
from src.lib.VoiceActivation import (
    PARAKEET_PROVIDER,
    VoiceActivation,
    load_voice_phrases,
    normalize_voice_language,
    resolve_activation_model,
    voice_config_error,
)


@pytest.fixture
def session():
    main = Mock()
    main.transcribe.return_value = "Simone, plot a route to Sol"
    return VoiceActivation("Simone", 10, main, main)


def recognize(session, text):
    ticket = session.begin_audio()
    assert ticket is not None
    result = session.recognize(ticket, lambda _: text)
    session.end_audio()
    return result


@pytest.fixture
def phrase_file(tmp_path):
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
            "fr": {
                "invocation_prefixes": [],
                "closing_phrases": ["conversation termin\u00e9e"],
                "wake_acknowledgments": ["Pr\u00eat."],
                "close_acknowledgments": ["Compris."],
            },
        },
    }, ensure_ascii=False), encoding="utf-8")
    return path


def test_custom_file_controls_prefixes_and_closing_phrases(phrase_file):
    phrases = load_voice_phrases(phrase_file)
    session = VoiceActivation("Simone", 10, Mock(), Mock(), phrases=phrases)
    assert session.strip_invocation("Hey Simone") is None
    assert session.strip_invocation("Listen upstairs Simone") is None
    assert session.strip_invocation("LISTEN UP, Simone: plot a route") == "plot a route"
    assert session.strip_invocation("Simone?") == ""
    assert recognize(session, "Listen up Simone, plot a route").kind == "command"
    assert recognize(session, "I'm done").kind == "command"
    assert recognize(session, "Explain conversation terminee").kind == "command"
    result = recognize(session, "CONVERSATION TERMINEE!")
    assert result.kind == "close"
    assert result.language == "fr"
    assert session.state == "standby"
    assert phrases.languages["en"].wake_acknowledgments == ("Ready.",)
    assert phrases.languages["en"].close_acknowledgments == ("Understood.",)


def test_empty_prefix_list_still_allows_name_alone(phrase_file):
    data = json.loads(phrase_file.read_text(encoding="utf-8"))
    data["languages"]["en"]["invocation_prefixes"] = []
    phrase_file.write_text(json.dumps(data), encoding="utf-8")
    session = VoiceActivation("Simone", 10, Mock(), Mock(), phrases=load_voice_phrases(phrase_file))
    assert session.strip_invocation("Simone?") == ""
    assert session.strip_invocation("Listen up Simone") is None
    assert session.strip_invocation("Hey Simone") is None


@pytest.mark.parametrize("key", [
    "invocation_prefixes", "closing_phrases", "wake_acknowledgments", "close_acknowledgments",
])
def test_missing_phrase_fields_are_rejected(phrase_file, key):
    data = json.loads(phrase_file.read_text(encoding="utf-8"))
    del data["languages"]["en"][key]
    phrase_file.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match=key):
        load_voice_phrases(phrase_file)


@pytest.mark.parametrize("key", [
    "closing_phrases", "wake_acknowledgments", "close_acknowledgments",
])
def test_required_phrase_lists_cannot_be_empty(phrase_file, key):
    data = json.loads(phrase_file.read_text(encoding="utf-8"))
    data["languages"]["en"][key] = []
    phrase_file.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match=key):
        load_voice_phrases(phrase_file)


@pytest.mark.parametrize("value", [
    None, "one phrase", 123, {}, [None], [123], [True], [""], [" \t "], ["?!"],
])
def test_invalid_phrase_entries_are_rejected(phrase_file, value):
    data = json.loads(phrase_file.read_text(encoding="utf-8"))
    data["languages"]["en"]["closing_phrases"] = value
    phrase_file.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="closing_phrases"):
        load_voice_phrases(phrase_file)


@pytest.mark.parametrize("text", ["[]", "null", '"phrases"', "1", "{"])
def test_invalid_phrase_documents_are_rejected(phrase_file, text):
    phrase_file.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="voice_phrases.json"):
        load_voice_phrases(phrase_file)


def test_missing_phrase_file_is_reported_without_fallback(tmp_path):
    with pytest.raises(ValueError, match="voice_phrases.json"):
        load_voice_phrases(tmp_path / "voice_phrases.json")


def test_invalid_phrase_encoding_is_reported(phrase_file):
    phrase_file.write_bytes(b"\xff")
    with pytest.raises(ValueError, match="voice_phrases.json"):
        load_voice_phrases(phrase_file)


def test_default_phrase_path_is_independent_of_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    phrases = load_voice_phrases()
    assert phrases.default_language == "en"
    assert phrases.languages["en"].wake_acknowledgments == ("Yes?", "What is it?")
    assert phrases.languages["fr"].wake_acknowledgments == ("Oui", "Qu'y a-t-il ?")


def test_phrase_loading_uses_bundled_data_layout(phrase_file, tmp_path, monkeypatch):
    bundle = tmp_path / "backend" / "_internal"
    data_dir = bundle / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "voice_phrases.json").write_bytes(phrase_file.read_bytes())
    monkeypatch.setattr(voice_activation_module, "__file__", str(bundle / "lib" / "VoiceActivation.py"))
    monkeypatch.chdir(tmp_path)
    assert load_voice_phrases().languages["en"].wake_acknowledgments == ("Ready.",)


@pytest.mark.parametrize("field,value", [
    ("default_language", None), ("default_language", "de"),
    ("languages", {}), ("languages", []), ("languages", None),
    ("languages", {"English": {}}), ("languages", {"xx": {}}),
    ("languages", {"en": []}),
])
def test_invalid_language_catalog_is_rejected(phrase_file, field, value):
    data = json.loads(phrase_file.read_text(encoding="utf-8"))
    data[field] = value
    phrase_file.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="voice_phrases.json"):
        load_voice_phrases(phrase_file)


@pytest.mark.parametrize("value,expected", [
    ("en", "en"), ("fr-FR", "fr"), ("fr_CA", "fr"), ("English", "en"), ("French", "fr"),
    ("Fran\u00e7ais", "fr"),
    (None, None), ("", None), ("auto", None), ("multilingual", None),
    ("en,fr", None), (["en", "fr"], None), (["fr-FR"], "fr"),
    (["fr", "fr-CA"], "fr"), ([], None),
])
def test_speech_language_settings_are_normalized(value, expected):
    assert normalize_voice_language(value) == expected


@pytest.mark.parametrize("value", ["xxx", "not a language", 123, True, {}, ["en", 123]])
def test_invalid_speech_language_settings_are_reported(value):
    with pytest.raises(ValueError, match="language"):
        normalize_voice_language(value)


@pytest.mark.parametrize("tts_language,stt_language,expected", [
    ("fr-FR", "en", "fr"),
    ("en-US", "fr", "en"),
    (None, "fr", "fr"),
    ("auto", "fr", "fr"),
    (["en", "fr"], "fr", "fr"),
])
def test_explicit_tts_language_precedes_stt_and_detection(tts_language, stt_language, expected):
    detect = Mock(return_value="de")
    session = VoiceActivation(
        "Simone", 10, Mock(), Mock(),
        tts_language=tts_language, stt_language=stt_language, detect_language=detect,
    )
    assert recognize(session, "Simone?").language == expected
    session.finish_control()
    assert recognize(session, "plot a route").language == expected
    assert recognize(session, "j'ai termin\u00e9").language == expected
    detect.assert_not_called()


def test_multilingual_dialogue_remembers_language_between_sessions():
    detect = Mock(side_effect=["fr", "en"])
    session = VoiceActivation(
        "Simone", 10, Mock(), Mock(),
        tts_language="multilingual", stt_language="auto", detect_language=detect,
    )
    assert recognize(session, "Simone?").language == "en"
    detect.assert_not_called()
    session.finish_control()
    assert recognize(session, "pr\u00e9pare une route vers Sol").language == "fr"
    assert recognize(session, "Simone?").language == "fr"
    session.finish_control()
    assert recognize(session, "please avoid neutron stars").language == "en"
    assert recognize(session, "j'ai termin\u00e9").language == "fr"
    session.finish_control()
    assert recognize(session, "Hey Simone?").language == "fr"
    assert detect.call_count == 2


def test_ambiguous_commands_do_not_replace_last_known_language():
    detect = Mock(side_effect=["fr", None])
    session = VoiceActivation("Simone", 10, Mock(), Mock(), detect_language=detect)
    recognize(session, "Simone, pr\u00e9pare une route")
    assert recognize(session, "Sol").language == "fr"
    assert recognize(session, "Simone?").language == "fr"


@pytest.mark.parametrize("phrase,language", [
    ("that's all", "en"), ("I'm done", "en"), ("j'ai termin\u00e9", "fr"), ("\u00e7a sera tout", "fr"),
])
def test_closing_phrase_identifies_its_language_without_detection(phrase, language):
    detect = Mock()
    session = VoiceActivation("Simone", 10, Mock(), Mock(), detect_language=detect)
    result = recognize(session, f"Simone, {phrase}")
    assert result.kind == "close"
    assert result.language == language
    detect.assert_not_called()


def test_rejected_standby_speech_does_not_change_language():
    detect = Mock()
    session = VoiceActivation("Simone", 10, Mock(), Mock(), detect_language=detect)
    assert recognize(session, "a private ambient conversation in another language") is None
    assert recognize(session, "Simone?").language == "en"
    detect.assert_not_called()


def test_stale_detection_cannot_change_language():
    session = VoiceActivation("Simone", 10, Mock(), Mock())

    def detect(text):
        session.fail()
        return "fr"

    session._detect_language = detect
    assert recognize(session, "Simone, pr\u00e9pare une route") is None
    assert recognize(session, "Simone?").language == "en"


def test_unsupported_acknowledgment_language_warns_once_without_user_content(monkeypatch):
    notify = Mock()
    monkeypatch.setattr(voice_activation_module, "log", notify)
    session = VoiceActivation("Simone", 10, Mock(), Mock(), detect_language=lambda _: "de")
    assert recognize(session, "Simone, bitte plane eine Route").language == "en"
    assert recognize(session, "Simone?").language == "en"
    notify.assert_called_once()
    assert notify.call_args.args[0] == "warn"
    assert "de" in notify.call_args.args[1]
    assert "bitte" not in notify.call_args.args[1]


def test_dialogue_without_a_detector_uses_catalog_and_remembered_language():
    session = VoiceActivation("Simone", 10, Mock(), Mock())
    assert recognize(session, "Simone?").language == "en"
    session.finish_control()
    assert recognize(session, "Bonjour, pr\u00e9pare une route").language == "en"
    assert recognize(session, "j'ai termin\u00e9").language == "fr"
    session.finish_control()
    assert recognize(session, "Simone?").language == "fr"


def test_core_imports_and_voice_mode_do_not_require_lingua():
    source = Path(__file__).resolve().parents[2] / "src"
    script = """
import importlib.abc
import sys
from unittest.mock import Mock

class NoLingua(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'lingua' or fullname.startswith('lingua.'):
            raise ImportError('Lingua is not installed')

sys.meta_path.insert(0, NoLingua())
sys.path.insert(0, sys.argv[1])
import Chat
from lib.VoiceActivation import VoiceActivation
session = VoiceActivation('Simone', 10, Mock(), Mock())
result = session.recognize(session.begin_audio(), lambda _: 'Simone?')
assert result.kind == 'wake' and result.language == 'en'
assert not any(name == 'lingua' or name.startswith('lingua.') for name in sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(source)], capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("phrase,command", [
    ("Simone", ""), ("Simone?", ""), ("SIMONE!", ""), ("Hey, Simone...", ""),
    ("OK, Simone, plot a route to Sol", "plot a route to Sol"),
    ("Dis Simone, pr\u00e9pare une route", "pr\u00e9pare une route"),
    ("simone: Sol", "Sol"), ("Okay Simone: Sol", "Sol"),
    ("Simone\u2026", ""),
])
def test_invocation_prefixes(session, phrase, command):
    assert session.strip_invocation(phrase) == command


@pytest.mark.parametrize("phrase", [
    "Simonet, plot a route", "I spoke to Simone", "hey Simon", "someone else", "",
])
def test_no_activation_for_other_speech(session, phrase):
    assert recognize(session, phrase) is None
    assert session.state == "standby"


def test_custom_accented_multiword_name():
    session = VoiceActivation("L\u00e9a Marie", 10, Mock(), Mock())
    assert session.strip_invocation("Hey LEA MARIE, go to Sol") == "go to Sol"
    assert session.strip_invocation("Le\u0301a Marie, go to Sol") == "go to Sol"
    assert session.strip_invocation("Lea Marielle, go to Sol") is None


@pytest.mark.parametrize("source", ["main", "parakeet"])
@pytest.mark.parametrize("strategy", ["reuse", "retranscribe"])
def test_parakeet_main_is_created_and_transcribed_only_once(source, strategy):
    create_main = Mock(return_value=Mock())
    main = create_main()
    create_extra = Mock()
    activation, fallback = resolve_activation_model(main, PARAKEET_PROVIDER, source, True, create_extra)
    session = VoiceActivation("Simone", 10, main, activation, strategy)
    main.transcribe.return_value = "Hey Simone, plot a route to Sol"
    ticket = session.begin_audio()
    result = session.recognize(ticket, lambda model: model.transcribe("one phrase"))
    assert result.text == "plot a route to Sol"
    assert result.kind == "command"
    assert not fallback
    create_main.assert_called_once()
    create_extra.assert_not_called()
    main.transcribe.assert_called_once_with("one phrase")


@pytest.mark.parametrize("available", [True, False])
def test_main_source_never_creates_an_extra_model(available):
    main, create = Mock(), Mock()
    assert resolve_activation_model(main, "another-stt", "main", available, create) == (main, False)
    create.assert_not_called()


def test_missing_optional_plugin_falls_back_to_configured_stt():
    main, create = Mock(), Mock()
    assert resolve_activation_model(main, "remote", "parakeet", False, create) == (main, True)
    create.assert_not_called()


def test_plugin_initialization_failure_has_no_remote_fallback():
    create = Mock(return_value=None)
    with pytest.raises(RuntimeError, match="No remote fallback"):
        resolve_activation_model(Mock(), "remote", "parakeet", True, create)


@pytest.mark.parametrize("strategy,main_calls", [("reuse", 0), ("retranscribe", 1)])
@pytest.mark.parametrize("remote_text", ["Simone, plot a route to Sol", "plot a route to Sol"])
def test_hybrid_first_command_and_followup(strategy, main_calls, remote_text):
    main, local = Mock(), Mock()
    local.transcribe.return_value = "Simone, plot a route to Sol"
    main.transcribe.return_value = remote_text
    session = VoiceActivation("Simone", 10, main, local, strategy)
    ticket = session.begin_audio()
    result = session.recognize(ticket, lambda model: model.transcribe("activation audio"))
    session.end_audio()
    assert result.text == "plot a route to Sol"
    assert session.accepts(result)
    assert main.transcribe.call_count == main_calls
    local.transcribe.assert_called_once_with("activation audio")

    main.transcribe.return_value = "avoid neutron stars"
    ticket = session.begin_audio()
    result = session.recognize(ticket, lambda model: model.transcribe("followup audio"))
    assert result.text == "avoid neutron stars"
    assert main.transcribe.call_count == main_calls + 1
    assert local.transcribe.call_count == 1


def test_standby_speech_never_calls_hybrid_main():
    main, local = Mock(), Mock()
    local.transcribe.return_value = "private ambient conversation"
    session = VoiceActivation("Simone", 10, main, local)
    assert session.recognize(session.begin_audio(), lambda model: model.transcribe("ambient")) is None
    main.transcribe.assert_not_called()
    assert session.state == "standby"


def test_call_alone_uses_only_activation_model_and_blocks_self_activation():
    main, local = Mock(), Mock()
    local.transcribe.return_value = "Hey Simone"
    session = VoiceActivation("Simone", 10, main, local)
    result = session.recognize(session.begin_audio(), lambda model: model.transcribe("name"))
    session.end_audio()
    assert result.kind == "wake"
    assert session.active
    assert session.begin_audio() is None
    main.transcribe.assert_not_called()
    session.finish_control()
    assert session.begin_audio().active


@pytest.mark.parametrize("phrase", [
    "\u00c7a sera tout !", "j'ai termin\u00e9.", "J\u2019AI TERMINE !",
    "that's all", "I'm done", "Simone, j'ai termin\u00e9",
])
def test_explicit_close_is_immediate_and_invalidates_earlier_results(session, phrase):
    first = recognize(session, "Simone, plot a route")
    result = recognize(session, phrase)
    assert result.kind == "close"
    assert session.state == "standby"
    assert session.accepts(result)
    assert not session.accepts(first)
    assert session.begin_audio() is None
    session.finish_control()
    assert session.begin_audio().active is False


@pytest.mark.parametrize("phrase", ["Explain the phrase j'ai termin\u00e9", "j'ai termin\u00e9 la route, continue"])
def test_closing_substrings_do_not_close_the_session(session, phrase):
    recognize(session, "Simone, plot a route")
    assert recognize(session, phrase).kind == "command"
    assert session.active


@pytest.mark.parametrize("phrase", [
    "reste en \u00e9coute", "RESTE EN ECOUTE !", "Simone, reste en \u00e9coute",
    "Keep listening.", "Hey Simone, keep listening",
])
def test_keep_listening_survives_idle_processing_followups_and_repeated_calls(phrase):
    now = [0.0]
    session = VoiceActivation("Simone", 10, Mock(), Mock(), clock=lambda: now[0])
    recognize(session, "Simone, plot a route")
    session.tick(False)
    now[0] = 9.999
    result = recognize(session, phrase)
    assert result.kind == "hold"
    assert result.text == ""
    assert session.accepts(result)
    assert session.begin_audio() is None
    session.finish_control()
    session.tick(False)
    now[0] = 100
    session.tick(False)
    assert session.active
    session.tick(True, output_busy=True)
    now[0] = 1000
    session.tick(False)
    assert session.active
    now[0] = 2000
    assert recognize(session, "avoid neutron stars").kind == "command"
    result = recognize(session, "Simone?")
    assert result.kind == "wake"
    session.finish_control()
    assert recognize(session, phrase).kind == "hold"
    session.finish_control()
    session.tick(False)
    now[0] = 10000
    session.tick(False)
    assert session.active


@pytest.mark.parametrize("phrase", ["reste en \u00e9coute", "keep listening"])
def test_keep_listening_does_not_activate_from_standby(session, phrase):
    assert recognize(session, phrase) is None
    assert session.state == "standby"


@pytest.mark.parametrize("phrase", [
    "Explique la phrase reste en \u00e9coute",
    "reste en \u00e9coute et pr\u00e9pare une route",
    "don't keep listening",
])
def test_keep_listening_substrings_do_not_disable_timeout(phrase):
    now = [0.0]
    session = VoiceActivation("Simone", 10, Mock(), Mock(), clock=lambda: now[0])
    recognize(session, "Simone, plot a route")
    assert recognize(session, phrase).kind == "command"
    session.tick(False)
    now[0] = 10
    session.tick(False)
    assert session.state == "standby"


@pytest.mark.parametrize("closing", ["\u00c7a sera tout !", "j'ai termin\u00e9", "that's all", "I'm done"])
def test_explicit_close_ends_keep_listening_and_next_session_times_out(closing):
    now = [0.0]
    session = VoiceActivation("Simone", 10, Mock(), Mock(), clock=lambda: now[0])
    hold = recognize(session, "Simone, reste en \u00e9coute")
    session.finish_control()
    late_ticket = session.begin_audio()
    session.end_audio()
    now[0] = 1000
    closing_result = recognize(session, closing)
    assert closing_result.kind == "close"
    assert session.accepts(closing_result)
    assert not session.accepts(hold)
    assert session.recognize(late_ticket, lambda _: "reste en \u00e9coute") is None
    assert session.state == "standby"
    session.finish_control()
    recognize(session, "Simone, plot a route")
    session.tick(False)
    now[0] = 1009.999
    session.tick(False)
    assert session.active
    now[0] = 1010
    session.tick(False)
    assert session.state == "standby"
    assert session.timeout == 10


def test_keep_listening_is_reset_after_recognition_failure(session):
    recognize(session, "Simone, reste en \u00e9coute")
    session.finish_control()
    session.fail()
    now = [0.0]
    session._clock = lambda: now[0]
    recognize(session, "Simone, plot a route")
    session.tick(False)
    now[0] = 10
    session.tick(False)
    assert session.state == "standby"


def test_stop_still_closes_keep_listening(session):
    hold = recognize(session, "Simone, keep listening")
    session.stop()
    session.finish_control()
    session.tick(False)
    assert session.state == "disabled"
    assert not session.accepts(hold)
    assert session.begin_audio() is None


def test_keep_listening_uses_custom_catalog_and_identifies_language(phrase_file):
    data = json.loads(phrase_file.read_text(encoding="utf-8"))
    data["languages"]["fr"]["keep_listening_phrases"] = ["\u00e9coute sans limite"]
    phrase_file.write_text(json.dumps(data), encoding="utf-8")
    detect = Mock()
    session = VoiceActivation(
        "Simone", 10, Mock(), Mock(), phrases=load_voice_phrases(phrase_file),
        detect_language=detect,
    )
    result = recognize(session, "Simone, ECOUTE SANS LIMITE !")
    assert result.kind == "hold"
    assert result.language == "fr"
    detect.assert_not_called()
    session.finish_control()
    assert recognize(session, "reste en \u00e9coute").kind == "command"


@pytest.mark.parametrize("value", [None, "keep listening", [123], [""], ["?!"]])
def test_invalid_keep_listening_catalog_is_rejected(phrase_file, value):
    data = json.loads(phrase_file.read_text(encoding="utf-8"))
    data["languages"]["en"]["keep_listening_phrases"] = value
    phrase_file.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="keep_listening_phrases"):
        load_voice_phrases(phrase_file)


@pytest.mark.parametrize("include_empty", [False, True])
def test_keep_listening_is_optional_in_existing_catalogs(phrase_file, include_empty):
    if include_empty:
        data = json.loads(phrase_file.read_text(encoding="utf-8"))
        data["languages"]["en"]["keep_listening_phrases"] = []
        phrase_file.write_text(json.dumps(data), encoding="utf-8")
    session = VoiceActivation("Simone", 10, Mock(), Mock(), phrases=load_voice_phrases(phrase_file))
    assert recognize(session, "Simone, keep listening").kind == "command"


def test_timeout_is_exact_and_restarts_after_processing_and_playback():
    now = [0.0]
    session = VoiceActivation("Simone", 10, Mock(), Mock(), clock=lambda: now[0])
    recognize(session, "Simone, plot a route")
    session.tick(busy=False)
    now[0] = 9.999
    session.tick(busy=False)
    assert session.active
    now[0] = 10.0
    session.tick(busy=False)
    assert session.state == "standby"
    assert session.consume_timeout()
    session.finish_control()

    recognize(session, "Simone, plot a route")
    session.tick(busy=True)
    now[0] = 100
    session.tick(busy=True, output_busy=True)
    assert session.active
    session.tick(busy=False)
    now[0] = 109.999
    session.tick(busy=False)
    assert session.active
    now[0] = 110
    session.tick(busy=False)
    assert not session.active


@pytest.mark.parametrize("expire_on_audio", [False, True])
def test_timeout_notification_is_one_shot_and_blocks_audio_until_completed(expire_on_audio):
    now = [0.0]
    session = VoiceActivation("Simone", 10, Mock(), Mock(), clock=lambda: now[0])
    recognize(session, "Simone, plot a route")
    session.tick(False)
    assert not session.consume_timeout()
    now[0] = 10
    if expire_on_audio:
        assert session.begin_audio() is None
    else:
        session.tick(False)
    assert session.state == "standby"
    assert session.consume_timeout()
    assert not session.consume_timeout()
    session.tick(False)
    assert session.begin_audio() is None
    session.finish_control()
    assert not session.consume_timeout()
    assert session.begin_audio() is not None


@pytest.mark.parametrize("control", ["Simone, reste en \u00e9coute", "Simone, that's all"])
def test_explicit_controls_do_not_signal_timeout(session, control):
    recognize(session, control)
    assert not session.consume_timeout()


@pytest.mark.parametrize("end", ["stop", "fail"])
def test_shutdown_and_errors_discard_pending_timeout(end):
    now = [0.0]
    session = VoiceActivation("Simone", 10, Mock(), Mock(), clock=lambda: now[0])
    recognize(session, "Simone, plot a route")
    session.tick(False)
    now[0] = 10
    session.tick(False)
    getattr(session, end)()
    assert not session.consume_timeout()


def test_speech_started_before_deadline_is_not_cut_off():
    now = [0.0]
    session = VoiceActivation("Simone", 10, Mock(), Mock(), clock=lambda: now[0])
    recognize(session, "Simone, plot a route")
    session.tick(False)
    now[0] = 9.99
    ticket = session.begin_audio()
    now[0] = 40
    session.tick(False)
    assert session.active
    result = session.recognize(ticket, lambda _: "a long followup")
    assert session.accepts(result)
    session.end_audio()
    session.tick(False)
    now[0] = 49.99
    session.tick(False)
    assert session.active
    now[0] = 50
    session.tick(False)
    assert not session.active


def test_stopped_or_failed_session_rejects_late_results(session):
    ticket = session.begin_audio()
    session.stop()
    assert session.recognize(ticket, lambda _: "Simone, plot a route") is None
    assert session.state == "disabled"
    session.fail()
    assert session.recognize(ticket, lambda _: "Simone, plot a route") is None


def test_standby_does_not_recognize_assistant_output(session):
    session.tick(False, output_busy=True)
    assert session.begin_audio() is None
    session.tick(False, output_busy=False)
    assert session.begin_audio() is not None


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), "ten", None, True])
def test_invalid_timeout_is_rejected(timeout):
    assert voice_config_error({"wake_word_timeout": timeout})


def test_invalid_name_is_rejected():
    assert voice_config_error({"wake_word_name": " ,! "})
    assert voice_config_error({"wake_word_name": "L\u00e9a", "wake_word_timeout": 0.1}) is None
