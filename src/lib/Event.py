from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Literal

from .EventModels import AnyEvent

class Event:
    kind: Literal['game', 'user', 'assistant', 'assistant_completed', 'tool', 'status', 'projected']
    timestamp: str
    processed_at: float


@dataclass
class GameEvent(Event):
    content: AnyEvent
    historic: bool
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    kind: Literal['game'] = field(default='game')
    processed_at: float = field(default=0.0)

@dataclass
class StatusEvent(Event):
    status: Dict
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    kind: Literal['status'] = field(default='status')
    processed_at: float = field(default=0.0)

@dataclass
class ProjectedEvent(Event):
    content: Dict
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    kind: Literal['projected'] = field(default='projected')
    processed_at: float = field(default=0.0)

@dataclass
class ExternalEvent(Event):
    content: Dict
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    kind: Literal['external'] = field(default='external')
    processed_at: float = field(default=0.0)


@dataclass
class ConversationEvent(Event):
    content: str
    kind: Literal['user', 'assistant', 'assistant_completed']
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    processed_at: float = field(default=0.0)


@dataclass
class ToolEvent(Event):
    request: List[Dict]
    results: List[Dict]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    kind: Literal['tool'] = field(default='tool')
    processed_at: float = field(default=0.0)
