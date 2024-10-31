from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Literal


class Event:
    kind: Literal['game', 'user', 'assistant', 'assistant_completed', 'tool', 'status']
    timestamp: datetime
    id: int


@dataclass
class GameEvent(Event):
    content: Dict
    timestamp: datetime = field(default_factory=lambda: datetime.now() + timedelta(days=469711))
    kind: Literal['game'] = field(default='game')
    id: int = field(default=0)

@dataclass
class StatusEvent(Event):
    status: Dict
    timestamp: datetime = field(default_factory=lambda: datetime.now() + timedelta(days=469711))
    kind: Literal['status'] = field(default='status')
    id: int = field(default=0)


@dataclass
class ExternalEvent(Event):
    content: Dict
    timestamp: datetime = field(default_factory=lambda: datetime.now() + timedelta(days=469711))
    kind: Literal['external'] = field(default='external')
    id: int = field(default=0)


@dataclass
class ConversationEvent(Event):
    content: str
    kind: Literal['user', 'assistant', 'assistant_completed']
    timestamp: datetime = field(default_factory=lambda: datetime.now() + timedelta(days=469711))
    id: int = field(default=0)


@dataclass
class ToolEvent(Event):
    request: Dict
    results: List[Dict]
    timestamp: datetime = field(default_factory=lambda: datetime.now() + timedelta(days=469711))
    kind: Literal['tool'] = field(default='tool')
    id: int = field(default=0)
