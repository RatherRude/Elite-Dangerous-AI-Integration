import datetime
import json
from typing import Any, Literal, TypedDict


class BaseMessage(TypedDict):
    type: str

class ConversationMessage(TypedDict):
    type: Literal['conversation']
    kind: Literal['user', 'assistant', 'assistant_completed']
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

# Convert the message object to a dictionary with proper handling of nested objects
def serialize_object(obj) -> dict|list|str:
    if hasattr(obj, '__dict__'):
        return {k: serialize_object(v) for k, v in obj.__dict__.items()}
    elif isinstance(obj, list):
        return [serialize_object(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: serialize_object(v) for k, v in obj.items()}
    elif isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    else:
        return obj
    
def send_message(message: dict):
    message_dict = serialize_object(message)
    
    # Ensure timestamp is present
    if 'timestamp' not in message_dict:
        message_dict['timestamp'] = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    print(json.dumps(message_dict))