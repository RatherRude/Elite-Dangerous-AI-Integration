import json
from pathlib import Path
import sys

from openai.types.chat import ChatCompletionMessageFunctionToolCall

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.lib.actions import actions_web


class FakePromptGenerator:
    def generate_status_message(self, projected_states: dict) -> str:
        return "status"


class FakeLLMModel:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, messages: list, tools: list, tool_choice: str):
        self.calls += 1
        if self.calls == 1:
            return "", [ChatCompletionMessageFunctionToolCall(
                type="function",
                id="internal_call_1",
                function={
                    "name": "get_galnet_news",
                    "arguments": json.dumps({"query": "thargoids"}),
                },
            )], {}
        return "Final report", None, {}


class FailingLLMModel:
    def generate(self, messages: list, tools: list, tool_choice: str):
        raise RuntimeError("model unavailable")


def consume_generator(generator):
    values = []
    while True:
        try:
            values.append(next(generator))
        except StopIteration as stop:
            return values, stop.value


def test_web_search_agent_yields_internal_tool_processing_events(monkeypatch) -> None:
    monkeypatch.setattr(actions_web, "get_galnet_news", lambda args, projected_states: "news result")

    updates, final_result = consume_generator(actions_web.web_search_agent(
        {"query": "latest thargoid news"},
        {},
        prompt_generator=FakePromptGenerator(),
        llm_model=FakeLLMModel(),
        max_loops=3,
    ))

    assert updates == [
        {
            "status": "searching",
            "query": "latest thargoid news",
        },
        {
            "status": "started",
            "query": "latest thargoid news",
            "iteration": 1,
            "internal_tool_call_id": "internal_call_1",
            "internal_tool_name": "get_galnet_news",
            "arguments": {"query": "thargoids"},
        },
        {
            "status": "completed",
            "query": "latest thargoid news",
            "iteration": 1,
            "internal_tool_call_id": "internal_call_1",
            "internal_tool_name": "get_galnet_news",
            "result": "news result",
        },
    ]
    assert final_result == "Final report"


def test_web_search_agent_returns_actionable_loop_error() -> None:
    updates, final_result = consume_generator(actions_web.web_search_agent(
        {"query": "search for aluminum"},
        {},
        prompt_generator=FakePromptGenerator(),
        llm_model=FailingLLMModel(),
        max_loops=3,
    ))

    assert updates == [{"status": "searching", "query": "search for aluminum"}]
    assert final_result == (
        "Web search failed while requesting the search agent model response "
        "on iteration 1 for query 'search for aluminum'. RuntimeError: model unavailable"
    )
