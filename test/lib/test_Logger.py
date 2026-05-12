import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import sqlean as sqlite3
import sqlite_vec

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.lib.Logger import ModelUsageStats, PromptUsageStats, log_llm_usage
from src.lib.Logger import AudioUsageStats, LatencyUsageStats, TextUsageStats, log_stt_usage, log_tts_usage
from src.lib.Logger import CacheUsageStats, log_action_cache_usage
from src.lib.Database import ModelUsageStore, set_connection_for_testing
from src.lib.Models import OpenAIResponsesLLMModel, _get_reasoning_tokens


@pytest.fixture
def mock_connection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "test_logger.db"

    monkeypatch.setattr("src.lib.Database.get_db_path", lambda: str(db_path))

    conn = sqlite3.connect(str(db_path))
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.execute("DROP TABLE IF EXISTS model_usage_v1")
    conn.commit()
    set_connection_for_testing(conn)

    try:
        yield conn
    finally:
        conn.close()


def test_log_llm_usage_includes_provider_model_and_reasoning_tokens(
    capsys, mock_connection
) -> None:
    _ = mock_connection
    usage = ModelUsageStats(
        input_tokens=120,
        output_tokens=45,
        total_tokens=165,
        cached_tokens=10,
        reasoning_tokens=7,
        provider="openai",
        model_name="gpt-5",
        response_ms=842,
        output_chars=17,
    )

    log_llm_usage("assistant", usage, PromptUsageStats(system_chars=20))

    output_lines = [
        line for line in capsys.readouterr().out.splitlines() if line.strip()
    ]
    message = next(
        json.loads(line)
        for line in reversed(output_lines)
        if json.loads(line).get("type") == "llm_usage"
    )
    assert message["type"] == "llm_usage"
    assert message["provider"] == "openai"
    assert message["model_name"] == "gpt-5"
    assert message["schema_version"] == 2
    assert message["model_usage"]["reasoning_tokens"] == 7
    assert message["model_usage"]["provider"] == "openai"
    assert message["model_usage"]["model_name"] == "gpt-5"
    assert message["prompt_usage"]["total_prompt_chars"] == 20
    assert message["latency_usage"]["response_ms"] == 842
    assert message["text_usage"]["output_chars"] == 17

    rows, total = ModelUsageStore().get_history(usage_kind="llm")
    assert total == 1
    assert len(rows) == 1
    assert rows[0]["payload"]["context"] == "assistant"
    assert rows[0]["payload"]["provider"] == "openai"
    assert rows[0]["payload"]["model_usage"]["reasoning_tokens"] == 7
    assert rows[0]["payload"]["prompt_usage"]["total_prompt_chars"] == 20
    assert rows[0]["payload"]["latency_usage"]["response_ms"] == 842
    assert rows[0]["payload"]["text_usage"]["output_chars"] == 17


def test_log_stt_and_tts_usage_persist_new_metric_groups(
    capsys, mock_connection
) -> None:
    _ = mock_connection

    log_stt_usage(
        "speech",
        provider="openai",
        model_name="gpt-4o-mini-transcribe",
        latency_usage=LatencyUsageStats(response_ms=321),
        audio_usage=AudioUsageStats(input_audio_duration_ms=2500),
        text_usage=TextUsageStats(output_chars=42),
    )
    log_tts_usage(
        "assistant",
        provider="edge-tts",
        model_name="edge-tts",
        latency_usage=LatencyUsageStats(response_ms=555, time_to_first_byte_ms=120),
        audio_usage=AudioUsageStats(output_audio_duration_ms=4200),
        text_usage=TextUsageStats(input_chars=88),
    )

    output_lines = [
        json.loads(line)
        for line in capsys.readouterr().out.splitlines()
        if line.strip()
    ]
    usage_messages = [
        line for line in output_lines if line.get("type") in {"stt_usage", "tts_usage"}
    ]

    assert len(usage_messages) == 2
    assert usage_messages[0]["audio_usage"]["input_audio_duration_ms"] == 2500
    assert usage_messages[0]["text_usage"]["output_chars"] == 42
    assert usage_messages[1]["latency_usage"]["time_to_first_byte_ms"] == 120
    assert usage_messages[1]["audio_usage"]["output_audio_duration_ms"] == 4200
    assert usage_messages[1]["text_usage"]["input_chars"] == 88

    rows, total = ModelUsageStore().get_history(limit=10)
    assert total == 2
    assert rows[0]["usage_kind"] == "tts"
    assert rows[0]["payload"]["latency_usage"]["time_to_first_byte_ms"] == 120
    assert rows[1]["usage_kind"] == "stt"
    assert rows[1]["payload"]["audio_usage"]["input_audio_duration_ms"] == 2500


def test_log_action_cache_usage_persists_saved_llm_calls(
    capsys, mock_connection
) -> None:
    _ = mock_connection

    log_action_cache_usage(
        "assistant",
        provider="openai",
        model_name="gpt-5",
        cache_usage=CacheUsageStats(llm_calls_saved=1),
    )

    output_lines = [
        json.loads(line)
        for line in capsys.readouterr().out.splitlines()
        if line.strip()
    ]
    message = next(
        line for line in reversed(output_lines) if line.get("type") == "action_cache_usage"
    )

    assert message["context"] == "assistant"
    assert message["cache_usage"]["llm_calls_saved"] == 1

    rows, total = ModelUsageStore().get_history(usage_kind="llm")
    assert total == 1
    assert rows[0]["payload"]["type"] == "action_cache_usage"
    assert rows[0]["payload"]["cache_usage"]["llm_calls_saved"] == 1


def test_openai_responses_model_usage_captures_reasoning_tokens(
    monkeypatch, mock_connection
) -> None:
    _ = mock_connection
    response = SimpleNamespace(
        usage=SimpleNamespace(
            input_tokens=10,
            output_tokens=6,
            total_tokens=16,
            input_tokens_details=SimpleNamespace(cached_tokens=2),
            output_tokens_details=SimpleNamespace(reasoning_tokens=4),
        ),
        output_text="ok",
        output=[],
        error=None,
    )
    client = SimpleNamespace(
        responses=SimpleNamespace(create=MagicMock(return_value=response)),
        models=SimpleNamespace(list=MagicMock(return_value=[])),
    )

    monkeypatch.setattr("src.lib.Models.OpenAI", lambda **kwargs: client)

    model = OpenAIResponsesLLMModel(
        base_url="https://api.openai.com/v1",
        api_key="test-key",
        model_name="gpt-5",
        temperature=1.0,
        provider_name="openai",
    )

    text, tool_calls, usage = model.generate(
        [
            {"role": "user", "content": "Hello"},
        ]
    )

    assert text == "ok"
    assert tool_calls is None
    assert usage.input_tokens == 10
    assert usage.output_tokens == 6
    assert usage.total_tokens == 16
    assert usage.cached_tokens == 2
    assert usage.reasoning_tokens == 4
    assert usage.provider == "openai"
    assert usage.model_name == "gpt-5"
    assert usage.response_ms is not None
    assert usage.output_chars == 2


def test_get_reasoning_tokens_falls_back_to_usage_totals() -> None:
    usage = SimpleNamespace(
        prompt_tokens=100,
        completion_tokens=40,
        total_tokens=155,
        completion_tokens_details=None,
        output_tokens_details=None,
    )

    assert _get_reasoning_tokens(usage) == 15


def test_get_reasoning_tokens_falls_back_to_response_usage_totals() -> None:
    usage = SimpleNamespace(
        input_tokens=1276,
        output_tokens=55,
        total_tokens=1437,
        completion_tokens_details=None,
        output_tokens_details=None,
    )

    assert _get_reasoning_tokens(usage) == 106
