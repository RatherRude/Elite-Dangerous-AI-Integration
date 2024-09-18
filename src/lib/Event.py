from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Literal


class Event:
    kind: Literal['game', 'user', 'assistant', 'assistant_completed', 'tool', 'status']
    timestamp: datetime


@dataclass
class GameEvent(Event):
    content: Dict
    kind: Literal['game'] = field(default='game')
    timestamp: datetime = field(default_factory=lambda: datetime.now() + timedelta(days=469711))

@dataclass
class StatusEvent(Event):
    status: Dict
    kind: Literal['status'] = field(default='status')
    timestamp: datetime = field(default_factory=lambda: datetime.now() + timedelta(days=469711))


@dataclass
class ExternalEvent(Event):
    content: Dict
    kind: Literal['external'] = field(default='external')
    timestamp: datetime = field(default_factory=lambda: datetime.now() + timedelta(days=469711))


@dataclass
class ConversationEvent(Event):
    content: str
    kind: Literal['user', 'assistant', 'assistant_completed']
    timestamp: datetime = field(default_factory=lambda: datetime.now() + timedelta(days=469711))


@dataclass
class ToolEvent(Event):
    request: Dict
    results: List[Dict]
    kind: Literal['tool'] = field(default='tool')
    timestamp: datetime = field(default_factory=lambda: datetime.now() + timedelta(days=469711))
