from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Literal, Callable

class Event:
    kind: Literal['game', 'user', 'assistant', 'assistant_completed', 'tool']
    timestamp: datetime

@dataclass
class GameEvent(Event):
    content: Dict
    kind: Literal['game'] = field(default='game')
    timestamp: datetime = field(default_factory=lambda: datetime.now())

@dataclass
class ExternalEvent(Event):
    content: Dict
    kind: Literal['external'] = field(default='external')
    timestamp: datetime = field(default_factory=lambda: datetime.now())

@dataclass
class ConversationEvent(Event):
    content: str
    kind: Literal['user', 'assistant', 'assistant_completed']
    timestamp: datetime = field(default_factory=lambda: datetime.now())

@dataclass
class ToolEvent(Event):
    request: Dict
    results: List[Dict]
    kind: Literal['tool'] = field(default='tool')
    timestamp: datetime = field(default_factory=lambda: datetime.now())
