import datetime
import datetime
import json
import sys
import threading
from typing import Any, Literal, TypedDict


class BaseMessage(TypedDict):
    type: str

class ConversationMessage(TypedDict):
    type: Literal['conversation']
    kind: Literal['user', 'assistant', 'assistant_speaking', 'assistant_completed']
    content: str

class ConfigMessage(TypedDict):
    type: Literal['config']
    config: dict

class StatesMessage(TypedDict):
    type: Literal['states']
    states: dict

class EventMessage(TypedDict):
    type: Literal['event']
    event: Any

class UIMessage(TypedDict):
    type: Literal['ui']
    show: str

class GenUIMessage(TypedDict):
    type: Literal['genui']
    code: str

# Convert the message object to a dictionary with proper handling of nested objects
def serialize_object(obj: Any) -> Any:
    if hasattr(obj, '__dict__'):
        return {k: serialize_object(v) for k, v in obj.__dict__.items()}
    if isinstance(obj, list):
        return [serialize_object(item) for item in obj]
    if isinstance(obj, dict):
        return {k: serialize_object(v) for k, v in obj.items()}
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    return obj
    
_writer_lock = threading.Lock()


def _write_line(payload: dict, stream: Any | None = None) -> None:
    output = json.dumps(payload)
    target = stream or sys.stdout
    with _writer_lock:
        target.write(output + "\n")
        target.flush()


def send_message(message: dict, stream: Any | None = None) -> None:
    message_dict: dict[str, Any]
    serialized = serialize_object(message)
    if isinstance(serialized, dict):
        message_dict = serialized
    else:
        message_dict = {"type": "ui", "payload": serialized}

    if isinstance(message_dict, dict) and 'timestamp' not in message_dict:
        message_dict['timestamp'] = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    _write_line(message_dict, stream=stream)


def emit_message(message_type: str, stream: Any | None = None, **payload: Any) -> None:
    send_message({"type": message_type, **payload}, stream=stream)
