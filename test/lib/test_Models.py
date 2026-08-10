from pathlib import Path
import sys
from unittest.mock import MagicMock

from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.plugins.MistralPlugin import MistralLLMModel


class ContentChunk:
    def __init__(self, data: dict):
        self.data = data

    def model_dump(self) -> dict:
        return self.data


def test_chat_completion_extracts_visible_text_from_structured_content() -> None:
    model = MistralLLMModel(
        base_url="https://api.mistral.ai/v1",
        api_key="test-key",
        model_name="mistral-medium-latest",
        temperature=1.0,
        provider_name="mistral",
    )
    message = ChatCompletionMessage.model_construct(
        role="assistant",
        content=[
            ContentChunk({"type": "thinking", "thinking": [{"type": "text", "text": "secret"}]}),
            ContentChunk({"type": "text", "text": "Final report"}),
            ContentChunk({"type": "text", "text": " with sources."}),
        ],
    )
    completion = ChatCompletion.model_construct(
        id="completion-1",
        choices=[Choice.model_construct(index=0, message=message, finish_reason="stop")],
        created=0,
        model="mistral-medium-latest",
        object="chat.completion",
        usage=None,
    )
    model.client.chat.completions.create = MagicMock(return_value=completion)

    text, tool_calls, usage = model.generate([{"role": "user", "content": "Search"}])

    assert text == "Final report with sources."
    assert tool_calls is None
    assert usage.output_chars == len(text)


def test_chat_completion_returns_none_for_thinking_only_content() -> None:
    model = MistralLLMModel(
        base_url="https://api.mistral.ai/v1",
        api_key="test-key",
        model_name="mistral-medium-latest",
        temperature=1.0,
        provider_name="mistral",
    )
    message = ChatCompletionMessage.model_construct(
        role="assistant",
        content=[ContentChunk({"type": "thinking", "thinking": []})],
    )
    completion = ChatCompletion.model_construct(
        id="completion-1",
        choices=[Choice.model_construct(index=0, message=message, finish_reason="stop")],
        created=0,
        model="mistral-medium-latest",
        object="chat.completion",
        usage=None,
    )
    model.client.chat.completions.create = MagicMock(return_value=completion)

    text, tool_calls, _ = model.generate([{"role": "user", "content": "Search"}])

    assert text is None
    assert tool_calls is None


def test_chat_completion_strips_thinking_chunks_from_tool_prompt() -> None:
    model = MistralLLMModel(
        base_url="https://api.mistral.ai/v1",
        api_key="test-key",
        model_name="mistral-small-latest",
        temperature=1.0,
        provider_name="mistral",
    )
    message = ChatCompletionMessage.model_construct(role="assistant", content="Acknowledged")
    completion = ChatCompletion.model_construct(
        id="completion-1",
        choices=[Choice.model_construct(index=0, message=message, finish_reason="stop")],
        created=0,
        model="mistral-small-latest",
        object="chat.completion",
        usage=None,
    )
    model.client.chat.completions.create = MagicMock(return_value=completion)
    tool_content = [
        ContentChunk({"type": "thinking", "thinking": [{"type": "text", "text": "secret"}]}),
        ContentChunk({"type": "text", "text": "Visible search result"}),
    ]

    model.generate([
        {"role": "assistant", "content": None, "tool_calls": []},
        {"role": "tool", "tool_call_id": "call-1", "content": tool_content},
    ])

    request_messages = model.client.chat.completions.create.call_args.kwargs["messages"]
    assert request_messages[1]["content"] == "Visible search result"
    assert request_messages[1]["tool_call_id"] == "call-1"
    assert "secret" not in request_messages[1]["content"]
    assert tool_content[0].data["type"] == "thinking"


def test_chat_completion_json_encodes_structured_tool_prompt() -> None:
    model = MistralLLMModel(
        base_url="https://api.mistral.ai/v1",
        api_key="test-key",
        model_name="mistral-small-latest",
        temperature=1.0,
        provider_name="mistral",
    )
    message = ChatCompletionMessage.model_construct(role="assistant", content="Acknowledged")
    completion = ChatCompletion.model_construct(
        id="completion-1",
        choices=[Choice.model_construct(index=0, message=message, finish_reason="stop")],
        created=0,
        model="mistral-small-latest",
        object="chat.completion",
        usage=None,
    )
    model.client.chat.completions.create = MagicMock(return_value=completion)

    model.generate([
        {"role": "tool", "tool_call_id": "call-1", "content": {"systems": ["Sol"]}},
    ])

    request_messages = model.client.chat.completions.create.call_args.kwargs["messages"]
    assert request_messages[0]["content"] == '{"systems": ["Sol"]}'
