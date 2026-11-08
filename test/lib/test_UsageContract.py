from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from src.lib.Errors import AudioPipelineError, ModelError, ToolError, error_kind
from src.lib.ModelUsage import ModelUsageStats
from src.lib.Models import STTModel, TTSModel, LLMModel, OpenAITTSModel, LLMError, generate_with_usage


@pytest.mark.parametrize("status,kind", [(400, "invalid_arguments"), (401, "authentication"),
    (403, "permission_denied"), (404, "not_found"), (429, "rate_limit"), (503, "provider_unavailable")])
def test_error_kinds_use_structured_http_status(status, kind):
    response = httpx.Response(status, request=httpx.Request("POST", "https://example.invalid"))
    error = httpx.HTTPStatusError("message is not a label", request=response.request, response=response)
    assert error_kind(error) == kind
    assert ModelError("wrapped", error).kind == kind


def test_explicit_plugin_categories_are_preserved_without_using_exception_messages():
    assert ToolError("private message", kind="plugin-kind").kind == "plugin-kind"
    assert ToolError("private message").kind == "unknown"
    assert error_kind(TimeoutError("private message")) == "timeout"
    assert AudioPipelineError("private message", TimeoutError(), stage="resample").stage == "resample"


def test_transcription_legacy_bridge_attaches_identity_on_failure():
    class Provider(STTModel):
        def transcribe(self, audio):
            raise TimeoutError("private request")
    provider = Provider("actual-stt", "test")
    with pytest.raises(ModelError) as caught:
        provider.transcribe_with_usage(None)
    assert caught.value.kind == "timeout"
    assert caught.value.usage.model_name == "actual-stt"
    assert caught.value.usage.input_tokens is None


def test_synthesis_usage_is_request_local_and_survives_lazy_failure():
    closed = []
    class Provider(TTSModel):
        def synthesize(self, text, voice):
            try:
                yield b"pcm"
                raise ModelError("private", kind="rate_limit")
            finally:
                closed.append(voice)
    provider = Provider("actual-tts", "test")
    first = provider.synthesize_with_usage("hello", {"voice": "one"})
    second = provider.synthesize_with_usage("world", {"voice": "two"})
    assert first.usage is not second.usage
    assert first.usage.voice_name == "one"
    iterator = iter(first.audio_stream)
    assert next(iterator) == b"pcm"
    with pytest.raises(ModelError) as caught:
        next(iterator)
    assert caught.value.usage is first.usage
    assert caught.value.kind == "rate_limit"
    assert first.usage.response_ms is None
    assert closed == ["one"]


def test_synthesis_cancellation_closes_provider():
    closed = []
    class Provider(TTSModel):
        def synthesize(self, text, voice):
            try:
                yield b"one"
                yield b"two"
            finally:
                closed.append(True)
    stream = Provider("test").synthesize_with_usage("hi", {}).audio_stream
    next(stream)
    stream.close()
    assert closed == [True]


def test_provider_empty_audio_is_an_invalid_response():
    class Provider(TTSModel):
        def synthesize(self, text, voice):
            return iter(())
    result = Provider("test").synthesize_with_usage("hello", {})
    with pytest.raises(ModelError) as caught:
        list(result.audio_stream)
    assert caught.value.kind == "invalid_response"
    assert caught.value.usage is result.usage


def test_llm_handler_reports_success_using_returned_identity(monkeypatch):
    report = Mock()
    monkeypatch.setattr("src.lib.Logger.log_llm_usage", report)
    usage = ModelUsageStats(provider="actual", model_name="served-model")
    model = SimpleNamespace(generate=lambda **kw: ("text", None, usage))
    assert generate_with_usage(model, "assistant", None, messages=[]) == ("text", None, usage)
    assert report.call_args.args[1] is usage
    assert report.call_count == 1


def test_llm_handler_reports_failure_once_and_reraises(monkeypatch):
    report = Mock()
    monkeypatch.setattr("src.lib.Logger.log_llm_usage", report)
    class Provider(LLMModel):
        def generate(self, **kw):
            raise ModelError("private body", kind="authentication")
    with pytest.raises(ModelError):
        generate_with_usage(Provider("actual"), "assistant", None, messages=[])
    assert report.call_count == 1
    assert report.call_args.kwargs["status"] == "error"
    assert report.call_args.kwargs["error_kind"] == "authentication"
    assert report.call_args.args[1].model_name == "actual"


def test_legacy_stats_import_defaults_positional_arguments_and_accumulation():
    from src.lib.Logger import ModelUsageStats as LegacyStats
    assert LegacyStats is ModelUsageStats
    usage = LegacyStats()
    usage.input_tokens += 3
    usage.output_tokens += 2
    usage.total_tokens += 5
    usage.cached_tokens += 1
    usage.retry_attempts += 1
    assert (usage.input_tokens, usage.output_tokens, usage.total_tokens, usage.cached_tokens, usage.retry_attempts) == (3, 2, 5, 1, 1)
    positional = LegacyStats(1, 2, 3, 4, 5, "provider", "model", 6, 7, 8, 9)
    assert (positional.provider, positional.model_name, positional.response_ms, positional.time_to_first_token_ms,
            positional.output_chars, positional.retry_attempts) == ("provider", "model", 6, 7, 8, 9)
    assert ModelUsageStats.unknown().input_tokens is None


def test_legacy_generate_keeps_its_exception_type_and_does_not_require_base_init():
    class LegacyFailure(Exception):
        pass
    failure = LegacyFailure("original error")
    class Provider(LLMModel):
        def __init__(self):
            pass
        def generate(self, messages, tools=None, tool_choice=None):
            raise failure
    provider = Provider()
    with pytest.raises(LegacyFailure) as direct:
        provider.generate([])
    assert direct.value is failure
    with pytest.raises(ModelError) as observed:
        provider.generate_with_usage([])
    assert observed.value.original_error is failure
    assert observed.value.usage.model_name is None


def test_legacy_llm_missing_metadata_is_filled_only_in_additive_adapter():
    reported = ModelUsageStats(input_tokens=2)
    class Provider(LLMModel):
        def generate(self, messages, tools=None, tool_choice=None):
            return "text", tools, reported
    provider = Provider("legacy-model", "legacy-provider")
    assert provider.generate([])[2] is reported
    adapted = provider.generate_with_usage([])[2]
    assert (adapted.provider, adapted.model_name, adapted.input_tokens) == ("legacy-provider", "legacy-model", 2)
    assert reported.provider is None


def test_legacy_error_constructor_import_and_catching():
    cause = RuntimeError("cause")
    failure = LLMError("message", cause)
    assert failure.original_error is cause
    assert str(failure) == "message"
    assert type(failure).__name__ == "LLMError"
    with pytest.raises(LLMError):
        raise ModelError("typed failure", kind="timeout")


def test_legacy_voice_only_and_settings_synthesis_dispatch_remain_distinct():
    calls = []
    class Provider(TTSModel):
        def synthesize(self, text, voice):
            calls.append(("voice", text, voice))
            return [b"voice"]
        def synthesize_with_settings(self, text, settings):
            calls.append(("settings", text, settings))
            return [b"settings"]
    provider = Provider("legacy")
    assert list(provider.synthesize_voice_with_usage("hello", "nova").audio_stream) == [b"voice"]
    assert list(provider.synthesize_with_usage("hello", {"voice": "nova"}).audio_stream) == [b"settings"]
    assert calls == [("voice", "hello", "nova"), ("settings", "hello", {"voice": "nova"})]


def test_voice_only_dispatch_honors_explicit_new_usage_override():
    from src.lib.ModelUsage import SynthesisResult
    class Provider(TTSModel):
        def synthesize(self, text, voice):
            raise AssertionError("Legacy path must not bypass the provider's usage API")
        def synthesize_with_usage(self, text, settings):
            return SynthesisResult([b"new"], ModelUsageStats.unknown(model_name="resolved", voice_name=settings["voice"]))
    result = Provider("requested").synthesize_voice_with_usage("hello", "nova")
    assert list(result.audio_stream) == [b"new"]
    assert result.usage.model_name == "resolved"


def test_openai_subclass_synthesize_override_and_request_instructions_are_preserved():
    calls = []
    class LegacyProvider(OpenAITTSModel):
        def __init__(self):
            # No network client is needed for an overriding legacy provider.
            TTSModel.__init__(self, "legacy")
            self.voice_instructions = "default"
        def synthesize(self, text, voice):
            calls.append((text, voice, self.voice_instructions, self))
            yield (self.voice_instructions or "<none>").encode()
            yield (self.voice_instructions or "<none>").encode()
    provider = LegacyProvider()
    first = iter(provider.synthesize_with_usage("first", {"voice": "one", "instructions": "calm"}).audio_stream)
    second = iter(provider.synthesize_with_usage("second", {"voice": "two", "instructions": "excited"}).audio_stream)
    assert next(first) == b"calm"
    assert provider.voice_instructions == "default"
    assert next(second) == b"excited"
    assert next(first) == b"calm"
    assert next(second) == b"excited"
    first.close(); second.close()
    assert all(call[3] is provider for call in calls)
    assert list(provider.synthesize_voice_with_usage("direct", "nova").audio_stream) == [b"default", b"default"]
    assert list(provider.synthesize_with_usage("clear", {"voice": "nova"}).audio_stream) == [b"<none>", b"<none>"]
    assert provider.voice_instructions == "default"
