from pathlib import Path
from queue import Queue
import sys
from unittest.mock import MagicMock

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.lib.Event import ConversationEvent
from src.lib.EventManager import EventManager


def test_add_conversation_event_keeps_character_name():
    manager = EventManager.__new__(EventManager)
    manager.incoming = Queue()
    manager.short_term_memory = MagicMock()

    manager.add_conversation_event("assistant", "hi", processed_at=12.0, reasons=["user"], character_name="A")

    event = manager.incoming.get_nowait()
    assert isinstance(event, ConversationEvent)
    assert event.kind == "assistant"
    assert event.character_name == "A"
    assert event.content == "hi"
    assert event.reasons == ["user"]
    manager.short_term_memory.replied_before.assert_called_once_with(12.0)
