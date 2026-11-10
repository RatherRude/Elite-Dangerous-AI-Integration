from pathlib import Path
import json
import sys
from unittest.mock import MagicMock

import pytest
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.plugins.MistralPlugin import MistralLLMModel
from src.lib.Models import LLMError, LLMModel, LLMResponse, OpenAILLMModel, OpenAIResponsesLLMModel
from src.lib.Event import ConversationEvent, MemoryEvent
from src.lib.Logger import ModelUsageStats, PromptUsageStats
from src.lib.PromptGenerator import PromptGenerator


class ContentChunk:
    def __init__(self, data: dict):
        self.data = data

    def model_dump(self) -> dict:
        return self.data


class RawResponse:
    def __init__(self, value, retries_taken: int = 0):
        self.value = value
        self.retries_taken = retries_taken

    def parse(self):
        return self.value


def create_chat_completion(text: str = "Recovered") -> ChatCompletion:
    message = ChatCompletionMessage.model_construct(role="assistant", content=text)
    return ChatCompletion.model_construct(
        id="completion-retry",
        choices=[Choice.model_construct(index=0, message=message, finish_reason="stop")],
        created=0,
        model="test-model",
        object="chat.completion",
        usage=None,
    )


def test_chat_completion_reports_sdk_retry_attempts() -> None:
    model = OpenAILLMModel(
        base_url="https://api.mistral.ai/v1",
        api_key="test-key",
        model_name="mistral-test",
        temperature=1.0,
        provider_name="mistral",
    )
    model.client.chat.completions.with_raw_response.create = MagicMock(
        return_value=RawResponse(create_chat_completion(), retries_taken=2)
    )

    text, _, usage = model.generate([{"role": "user", "content": "Hello"}])

    assert text == "Recovered"
    assert usage.retry_attempts == 2
    assert model.client.max_retries == 4


def test_responses_reports_sdk_retry_attempts() -> None:
    model = OpenAIResponsesLLMModel(
        base_url="https://api.openai.com/v1",
        api_key="test-key",
        model_name="gpt-test",
        temperature=1.0,
        provider_name="openai",
    )
    response = MagicMock()
    response.error = None
    response.usage = None
    response.output_text = "Recovered"
    response.output = []
    model.client.responses.with_raw_response.create = MagicMock(
        return_value=RawResponse(response, retries_taken=1)
    )

    text, _, usage = model.generate([{"role": "user", "content": "Hello"}])

    assert text == "Recovered"
    assert usage.retry_attempts == 1
    assert model.client.max_retries == 4


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
    model.client.chat.completions.with_raw_response.create = MagicMock(
        return_value=RawResponse(completion)
    )

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
    model.client.chat.completions.with_raw_response.create = MagicMock(
        return_value=RawResponse(completion)
    )

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
    model.client.chat.completions.with_raw_response.create = MagicMock(
        return_value=RawResponse(completion)
    )
    tool_content = [
        ContentChunk({"type": "thinking", "thinking": [{"type": "text", "text": "secret"}]}),
        ContentChunk({"type": "text", "text": "Visible search result"}),
    ]

    model.generate([
        {"role": "assistant", "content": None, "tool_calls": []},
        {"role": "tool", "tool_call_id": "call-1", "content": tool_content},
    ])

    request_messages = model.client.chat.completions.with_raw_response.create.call_args.kwargs["messages"]
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
    model.client.chat.completions.with_raw_response.create = MagicMock(
        return_value=RawResponse(completion)
    )

    model.generate([
        {"role": "tool", "tool_call_id": "call-1", "content": {"systems": ["Sol"]}},
    ])

    request_messages = model.client.chat.completions.with_raw_response.create.call_args.kwargs["messages"]
    assert request_messages[0]["content"] == '{"systems": ["Sol"]}'


class LegacyLLMModel(LLMModel):
    """A plugin implementing only the original model API."""

    def generate(self, messages, tools=None, tool_choice=None):
        return "A: hi\nB: hello\nA: ready?", None, ModelUsageStats()


@pytest.mark.parametrize("text,expected", [
    ("A: hi\nB: hello\nA: ready?", [("A", "hi"), ("B", "hello"), ("A", "ready?")]),
    ("A: hi\nmore dialogue\nB: hello", [("A", "hi\nmore dialogue"), ("B", "hello")]),
    ("Unlabeled introduction\nA: hi", [(None, "Unlabeled introduction"), ("A", "hi")]),
    ("  A: hi\r\n\r\n B: hello  ", [("A", "hi"), ("B", "hello")]),
    ("A:\nhi\nB: hello", [("A", "hi"), ("B", "hello")]),
    ("Warning: shields offline\nUnknown: hello", [(None, "Warning: shields offline\nUnknown: hello")]),
    ("A: Warning: shields offline", [("A", "Warning: shields offline")]),
    ("  Plain text\nwith spacing  ", [(None, "  Plain text\nwith spacing  ")]),
    ("A:", [(None, "A:")]),
])
def test_default_character_parser(text, expected):
    model = LegacyLLMModel("legacy")

    responses = model.parse_character_responses(text, [{"name": "A"}, {"name": "B"}])

    assert [(response.character_name, response.text) for response in responses] == expected


def test_multi_character_fallback_supports_unchanged_legacy_plugins():
    model = LegacyLLMModel("legacy")
    model.generate = MagicMock(wraps=model.generate)
    prompt_generator = MagicMock()
    messages = [{"role": "user", "content": "hello"}]
    prompt_usage = PromptUsageStats(conversation_chars=5)
    prompt_generator.generate_prompt.return_value = messages, prompt_usage
    characters = [{"name": "A"}, {"name": "B"}]
    events = [ConversationEvent(kind="user", content="hello")]
    memories = [MemoryEvent(content="memory", metadata={}, embedding=[])]

    responses = model.generate_multi_character(
        prompt_generator=prompt_generator, characters=characters,
        events=events, memories=memories, projected_states={}, pending_events=events, tools=[],
    )
    # Generator creation itself neither formats prompts nor performs network calls.
    prompt_generator.generate_prompt.assert_not_called()
    model.generate.assert_not_called()
    responses = list(responses)

    prompt_generator.generate_prompt.assert_called_once_with(
        events=events, memories=memories, projected_states={}, pending_events=events,
        characters=characters, assistant_response_formatter=model.format_character_responses,
        response_format=model.character_response_format(characters),
    )
    model.generate.assert_called_once_with(messages=messages, tools=[])
    assert responses[:3] == [
        LLMResponse(character_name="A", text="hi"),
        LLMResponse(character_name="B", text="hello"),
        LLMResponse(character_name="A", text="ready?"),
    ]
    assert len(responses) == 4
    assert responses[-1].model_usage == ModelUsageStats()
    assert responses[-1].prompt_usage is prompt_usage


@pytest.mark.parametrize("text,tool_calls,expected_texts", [
    (None, None, ["..."]),
    (None, [{"id": "call_test"}], []),
    ("A: hi", [{"id": "call_test"}], ["hi"]),
])
def test_multi_character_fallback_preserves_tools_and_reports_usage_once(text, tool_calls, expected_texts):
    model = LegacyLLMModel("legacy")
    usage = ModelUsageStats(input_tokens=10, output_tokens=5)
    model.generate = MagicMock(return_value=(text, tool_calls, usage))
    prompt_generator = MagicMock()
    prompt_generator.generate_prompt.return_value = [], PromptUsageStats()

    responses = list(model.generate_multi_character(
        prompt_generator=prompt_generator, characters=[{"name": "A"}],
        events=[], memories=[], projected_states={}, pending_events=[],
        tools=[], tool_choice="auto",
    ))

    assert [response.text for response in responses if response.text] == expected_texts
    assert responses[-1].tool_calls == tool_calls
    assert [response.model_usage for response in responses if response.model_usage is not None] == [usage]
    assert model.generate.call_args.kwargs["tool_choice"] == "auto"


def test_multi_character_fallback_propagates_llm_errors():
    model = LegacyLLMModel("legacy")
    model.generate = MagicMock(side_effect=LLMError("Failed"))
    prompt_generator = MagicMock()
    prompt_generator.generate_prompt.return_value = [], PromptUsageStats()

    with pytest.raises(LLMError, match="Failed"):
        list(model.generate_multi_character(
            prompt_generator=prompt_generator, characters=[],
            events=[], memories=[], projected_states={}, pending_events=[],
        ))


def test_provider_can_customize_prompt_format_and_parser_without_replacing_generation():
    class JSONModel(LegacyLLMModel):
        def format_character_responses(self, responses):
            return json.dumps([{"speaker": response.character_name, "text": response.content} for response in responses])

        def character_response_format(self, characters):
            return 'Return a JSON array of objects with "speaker" and "text".'

        def parse_character_responses(self, text, characters):
            for part in json.loads(text):
                yield LLMResponse(character_name=part["speaker"], text=part["text"])

    generator = PromptGenerator.__new__(PromptGenerator)
    generator.commander_name = "Commander"
    generator.character_prompt = "Help {commander_name}."
    generator.important_game_events = []
    generator.disabled_game_events = []
    generator.registered_prompt_event_handlers = []
    generator.generate_status_message = MagicMock(return_value="Current status")
    characters = [{"name": "A", "character": "A's personality"}, {"name": "B", "character": "B's personality"}]
    events = [
        ConversationEvent(kind="assistant", character_name="A", content="hi"),
        ConversationEvent(kind="assistant", character_name="B", content="hello"),
    ]
    model = JSONModel("json-model")
    model.generate = MagicMock(return_value=('[{"speaker": "B", "text": "ready"}]', None, ModelUsageStats()))

    responses = list(model.generate_multi_character(
        prompt_generator=generator, characters=characters,
        events=events, memories=[], projected_states={}, pending_events=[],
    ))

    messages = model.generate.call_args.kwargs["messages"]
    assert "Return a JSON array" in messages[0]["content"]
    assert "Character name: dialogue" not in messages[0]["content"]
    assert "A's personality" in messages[0]["content"]
    assert "B's personality" in messages[0]["content"]
    assert messages[-1] == {
        "role": "assistant",
        "content": '[{"speaker": "A", "text": "hi"}, {"speaker": "B", "text": "hello"}]',
    }
    assert responses[0] == LLMResponse(character_name="B", text="ready")
