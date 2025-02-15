from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Literal, TypedDict


class Event:
    kind: Literal['game', 'user', 'assistant', 'assistant_completed', 'tool', 'status', 'projected']
    timestamp: str
    processed_at: float

class GameEventContent(TypedDict):
    event: str
    timestamp: str

@dataclass
class GameEvent(Event):
    content: GameEventContent
    historic: bool
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    kind: Literal['game'] = field(default='game')
    processed_at: float = field(default=0.0)

@dataclass
class StatusEvent(Event):
    status: Dict
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    kind: Literal['status'] = field(default='status')
    processed_at: float = field(default=0.0)

@dataclass
class ProjectedEvent(Event):
    content: Dict
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    kind: Literal['projected'] = field(default='projected')
    processed_at: float = field(default=0.0)

@dataclass
class ExternalEvent(Event):
    content: Dict
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    kind: Literal['external'] = field(default='external')
    processed_at: float = field(default=0.0)


@dataclass
class ConversationEvent(Event):
    content: str
    kind: Literal['user', 'assistant', 'assistant_completed']
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    processed_at: float = field(default=0.0)


@dataclass
class ToolEvent(Event):
    request: List[Dict]
    results: List[Dict]
    text: List[str] | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    kind: Literal['tool'] = field(default='tool')
    processed_at: float = field(default=0.0)
