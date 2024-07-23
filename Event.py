from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Literal, Callable

class Event:
    kind: Literal['game', 'user', 'assistant', 'assistant_completed', 'tool']
    timestamp: datetime

@dataclass
class GameEvent(Event):
    content: Dict
    kind = 'game'
    timestamp = datetime.now()

@dataclass
class ConversationEvent(Event):
    content: str
    kind: Literal['user', 'assistant', 'assistant_completed']
    timestamp = datetime.now()

@dataclass
class ToolEvent(Event):
    request: Dict
    results: List[Dict]
    kind: Literal['tool'] = 'tool'
    timestamp = datetime.now()
