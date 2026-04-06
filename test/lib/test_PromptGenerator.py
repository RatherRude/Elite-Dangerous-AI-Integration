import sys
import sqlite3
from pathlib import Path
import types
from unittest.mock import MagicMock

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

humanize_stub = types.ModuleType("humanize")
humanize_stub.naturaltime = lambda _delta: "less than a minute ago"
sys.modules.setdefault("humanize", humanize_stub)

sqlite_vec_stub = types.ModuleType("sqlite_vec")
sqlite_vec_stub.load = lambda _conn: None
sys.modules.setdefault("sqlean", sqlite3)
sys.modules.setdefault("sqlite_vec", sqlite_vec_stub)

pythonjsonlogger_stub = types.ModuleType("pythonjsonlogger")
pythonjsonlogger_json_stub = types.ModuleType("pythonjsonlogger.json")


class _JsonFormatter:
    def __init__(self, *args, **kwargs):
        pass


pythonjsonlogger_json_stub.JsonFormatter = _JsonFormatter
pythonjsonlogger_stub.json = pythonjsonlogger_json_stub
sys.modules.setdefault("pythonjsonlogger", pythonjsonlogger_stub)
sys.modules.setdefault("pythonjsonlogger.json", pythonjsonlogger_json_stub)

opentelemetry_stub = types.ModuleType("opentelemetry")
trace_stub = types.ModuleType("opentelemetry.trace")
trace_stub.get_tracer = lambda _name: MagicMock()
trace_stub.set_tracer_provider = lambda _provider: None

sdk_trace_stub = types.ModuleType("opentelemetry.sdk.trace")
sdk_trace_stub.TracerProvider = MagicMock
sdk_trace_export_stub = types.ModuleType("opentelemetry.sdk.trace.export")
sdk_trace_export_stub.BatchSpanProcessor = MagicMock

sdk_resources_stub = types.ModuleType("opentelemetry.sdk.resources")


class _Resource:
    @staticmethod
    def create(*args, **kwargs):
        return MagicMock()


sdk_resources_stub.Resource = _Resource
sdk_resources_stub.SERVICE_NAME = "service.name"
sdk_resources_stub.SERVICE_INSTANCE_ID = "service.instance.id"
sdk_resources_stub.SERVICE_NAMESPACE = "service.namespace"

trace_exporter_stub = types.ModuleType("opentelemetry.exporter.otlp.proto.http.trace_exporter")
trace_exporter_stub.OTLPSpanExporter = MagicMock

logs_api_stub = types.ModuleType("opentelemetry._logs")
logs_api_stub.set_logger_provider = lambda _provider: None

sdk_logs_stub = types.ModuleType("opentelemetry.sdk._logs")
sdk_logs_stub.LoggerProvider = MagicMock
sdk_logs_stub.LoggingHandler = MagicMock

sdk_logs_export_stub = types.ModuleType("opentelemetry.sdk._logs.export")
sdk_logs_export_stub.BatchLogRecordProcessor = MagicMock

log_exporter_stub = types.ModuleType("opentelemetry.exporter.otlp.proto.http._log_exporter")
log_exporter_stub.OTLPLogExporter = MagicMock

openai_instrumentation_stub = types.ModuleType("opentelemetry.instrumentation.openai")
openai_instrumentation_stub.OpenAIInstrumentor = MagicMock

opentelemetry_stub.trace = trace_stub
sys.modules.setdefault("opentelemetry", opentelemetry_stub)
sys.modules.setdefault("opentelemetry.trace", trace_stub)
sys.modules.setdefault("opentelemetry.sdk.trace", sdk_trace_stub)
sys.modules.setdefault("opentelemetry.sdk.trace.export", sdk_trace_export_stub)
sys.modules.setdefault("opentelemetry.sdk.resources", sdk_resources_stub)
sys.modules.setdefault("opentelemetry.exporter.otlp.proto.http.trace_exporter", trace_exporter_stub)
sys.modules.setdefault("opentelemetry._logs", logs_api_stub)
sys.modules.setdefault("opentelemetry.sdk._logs", sdk_logs_stub)
sys.modules.setdefault("opentelemetry.sdk._logs.export", sdk_logs_export_stub)
sys.modules.setdefault("opentelemetry.exporter.otlp.proto.http._log_exporter", log_exporter_stub)
sys.modules.setdefault("opentelemetry.instrumentation.openai", openai_instrumentation_stub)

from src.lib.PromptGenerator import PromptGenerator


def make_prompt_generator(monkeypatch, active_characters=None):
    monkeypatch.setattr("src.lib.PromptGenerator.QuestDatabase", MagicMock(return_value=MagicMock()))
    return PromptGenerator(
        commander_name="Rude",
        character_prompt="I am {commander_name}'s main ship voice.",
        important_game_events=[],
        system_db=MagicMock(),
        active_characters=active_characters,
    )


def test_get_character_prompt_block_uses_main_prompt_with_one_active_character(monkeypatch):
    generator = make_prompt_generator(
        monkeypatch,
        active_characters=[
            {
                "speaker_id": "character_0",
                "name": "COVAS",
                "is_primary": True,
                "character_prompt": "I am {commander_name}'s main ship voice.",
            },
        ],
    )

    prompt_block = generator.get_character_prompt_block()

    assert prompt_block == "Your character prompt is: I am Rude's main ship voice."
    assert "Crew roster:" not in prompt_block


def test_get_character_prompt_block_uses_multicrew_roster_when_multiple_active_characters(monkeypatch):
    generator = make_prompt_generator(
        monkeypatch,
        active_characters=[
            {
                "speaker_id": "character_0",
                "name": "COVAS",
                "is_primary": True,
                "character_prompt": "I am {commander_name}'s main ship voice.",
            },
            {
                "speaker_id": "character_2",
                "name": "Nyx",
                "is_primary": False,
                "character_prompt": "I am the gunner covering {commander_name}.",
            },
        ],
    )

    prompt_block = generator.get_character_prompt_block()

    assert "Your character prompt is:" not in prompt_block
    assert "Multicrew is active" in prompt_block
    assert "Responses without using the crewTalk tool are always spoken by the primary ship voice." in prompt_block
    assert "Never write character names in brackets or labels to simulate a different speaker in plain text; use the crewTalk tool instead." in prompt_block
    assert "Crew roster by speaker_id for crewTalk:" in prompt_block
    assert "character_0 -> COVAS (primary): I am Rude's main ship voice." in prompt_block
    assert "character_2 -> Nyx (active): I am the gunner covering Rude." in prompt_block


def test_generate_status_message_includes_main_ship_loadout_hull_health(monkeypatch):
    generator = make_prompt_generator(monkeypatch)

    projected_states = {
        "CurrentStatus": {
            "flags": {
                "InMainShip": True,
                "InFighter": False,
                "InSRV": False,
            },
            "flags2": {
                "OnFoot": False,
            },
            "Balance": 1000,
            "Pips": [4, 2, 0],
            "Cargo": 0,
        },
        "InCombat": {
            "InCombat": False,
        },
        "ShipInfo": {
            "Ship": "CobraMkIII",
        },
        "Cargo": {},
        "Loadout": {
            "HullHealth": 0.75,
            "Modules": [],
        },
    }

    status_message = generator.generate_status_message(projected_states)

    assert "# Main Ship" in status_message
    assert "Loadout:" in status_message
    assert "ShipHealth:" in status_message
    assert "HullHealth: 0.75" in status_message
