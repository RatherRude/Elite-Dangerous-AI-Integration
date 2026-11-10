from pathlib import Path
import json
import sys
from unittest.mock import MagicMock

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.lib.Event import ConversationEvent, GameEvent, ToolEvent
from src.lib.PromptGenerator import PromptGenerator


@pytest.fixture
def generator():
    generator = PromptGenerator.__new__(PromptGenerator)
    generator.commander_name = "Commander"
    generator.character_prompt = "Help {commander_name}."
    generator.important_game_events = []
    generator.disabled_game_events = []
    generator.registered_prompt_event_handlers = []
    generator.generate_status_message = MagicMock(return_value="Current status")
    generator.event_message = MagicMock(return_value={"role": "user", "content": "Game event"})
    return generator


def test_named_utterances_reassemble_in_order_across_lifecycle_events(generator):
    events = [
        ConversationEvent(kind="user", content="hello"),
        ConversationEvent(kind="assistant_speaking", content=""),
        ConversationEvent(kind="assistant", character_name="A", content="hi"),
        ConversationEvent(kind="assistant_completed", content=""),
        ConversationEvent(kind="assistant_speaking", content=""),
        ConversationEvent(kind="assistant", character_name="B", content="hello"),
        ConversationEvent(kind="assistant", character_name="A", content="ready?"),
    ]

    prompt, _ = generator.generate_prompt(events, {}, [], [])

    assert prompt[1:] == [
        {"role": "user", "content": "Current status"},
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "A: hi\nB: hello\nA: ready?"},
    ]
    assert "Character name: dialogue" in prompt[0]["content"]


@pytest.mark.parametrize("boundary", [
    ConversationEvent(kind="user", content="next request"),
    GameEvent(content={"event": "FSDJump", "timestamp": "2026-11-10T00:00:00+00:00"}, historic=False),
    ToolEvent(
        request=[{"id": "call_test", "type": "function", "function": {"name": "test", "arguments": "{}"}}],
        results=[{"role": "tool", "tool_call_id": "call_test", "content": "done"}],
    ),
])
def test_visible_messages_and_tool_calls_break_assistant_groups(generator, boundary):
    events = [
        ConversationEvent(kind="assistant", character_name="A", content="hi"),
        boundary,
        ConversationEvent(kind="assistant", character_name="B", content="hello"),
    ]

    prompt, _ = generator.generate_prompt(events, {}, [], [])

    assert [message for message in prompt if message["role"] == "assistant" and "tool_calls" not in message] == [
        {"role": "assistant", "content": "A: hi"},
        {"role": "assistant", "content": "B: hello"},
    ]
    if isinstance(boundary, ToolEvent):
        assert prompt[3:5] == [
            {"role": "assistant", "tool_calls": boundary.request},
            boundary.results[0],
        ]


def test_legacy_messages_remain_unprefixed(generator):
    events = [
        ConversationEvent(kind="user", content="hello"),
        ConversationEvent(kind="assistant", content="Plain reply"),
        ConversationEvent(kind="assistant", character_name="A", content="hi"),
    ]

    prompt, _ = generator.generate_prompt(events, {}, [], [])

    assert prompt[-1] == {"role": "assistant", "content": "Plain reply\nA: hi"}


def test_legacy_history_does_not_request_character_format(generator):
    prompt, _ = generator.generate_prompt([
        ConversationEvent(kind="assistant", content="Plain reply"),
    ], {}, [], [])

    assert prompt[-1] == {"role": "assistant", "content": "Plain reply"}
    assert "Character name: dialogue" not in prompt[0]["content"]


def test_custom_formatter_receives_complete_chronological_groups(generator):
    first = ConversationEvent(kind="assistant", character_name="A", content="hi")
    second = ConversationEvent(kind="assistant", character_name="B", content="hello")
    third = ConversationEvent(kind="assistant", character_name="A", content="ready?")
    formatter = MagicMock(side_effect=lambda events: json.dumps([event.content for event in events]))
    events = [first, second, ConversationEvent(kind="user", content="next"), third]

    prompt, usage = generator.generate_prompt(events, {}, [], [], assistant_response_formatter=formatter)

    assert [args.args[0] for args in formatter.call_args_list] == [[first, second], [third]]
    assert [message["content"] for message in prompt if message["role"] == "assistant"] == [
        '["hi", "hello"]', '["ready?"]',
    ]
    assert usage.conversation_chars == sum(len(json.dumps(message)) for message in prompt[2:])


def test_empty_history_still_builds_character_prompt(generator):
    prompt, _ = generator.generate_prompt(
        [], {}, [], [], characters=[{"name": "A", "character": "Help {commander_name}."}],
        response_format="Return JSON dialogue.",
    )

    assert prompt[1:] == [{"role": "user", "content": "Current status"}]
    assert "A: Help Commander." in prompt[0]["content"]
    assert "Return JSON dialogue." in prompt[0]["content"]
    assert "Character name: dialogue" not in prompt[0]["content"]
