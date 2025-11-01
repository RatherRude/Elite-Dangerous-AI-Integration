from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Literal, TypedDict

from openai.types import embedding


class Event:
    kind: Literal['game', 'user', 'user_speaking', 'assistant', 'assistant_acting', 'assistant_completed', 'tool', 'status', 'projected', 'external', 'memory']
    timestamp: str
    processed_at: float
    memorized_at: float | None
    responded_at: float | None

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
    memorized_at: float | None = field(default=0.0)
    responded_at: float | None = field(default=0.0)

@dataclass
class StatusEvent(Event):
    status: Dict
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    kind: Literal['status'] = field(default='status')
    processed_at: float = field(default=0.0)
    memorized_at: float | None = field(default=0.0)
    responded_at: float | None = field(default=0.0)

@dataclass
class ProjectedEvent(Event):
    content: Dict
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    kind: Literal['projected'] = field(default='projected')
    processed_at: float = field(default=0.0)
    memorized_at: float | None = field(default=0.0)
    responded_at: float | None = field(default=0.0)

@dataclass
class ExternalEvent(Event):
    content: Dict
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    kind: Literal['external'] = field(default='external')
    processed_at: float = field(default=0.0)
    memorized_at: float | None = field(default=0.0)
    responded_at: float | None = field(default=0.0)


@dataclass
class ConversationEvent(Event):
    content: str
    kind: Literal['user_speaking', 'user', 'assistant', 'assistant_acting', 'assistant_completed']
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    processed_at: float = field(default=0.0)
    memorized_at: float | None = field(default=0.0)
    responded_at: float | None = field(default=0.0)


@dataclass
class ToolEvent(Event):
    request: List[Dict]
    results: List[Dict]
    text: List[str] | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    kind: Literal['tool'] = field(default='tool')
    processed_at: float = field(default=0.0)
    memorized_at: float | None = field(default=0.0)
    responded_at: float | None = field(default=0.0)


@dataclass
class MemoryEvent(Event):
    content: str
    metadata: dict
    embedding: list[float]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    kind: Literal['memory'] = field(default='memory')
    processed_at: float = field(default=0.0)
    memorized_at: float | None = field(default=0.0)
    responded_at: float | None = field(default=0.0)