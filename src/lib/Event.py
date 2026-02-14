from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Generic, Literal, TypedDict, TypeVar


EventKind = Literal[
    'game',
    'user',
    'user_speaking',
    'assistant',
    'assistant_acting',
    'assistant_completed',
    'play_sound',
    'tool',
    'status',
    'projected',
    'external',
    'quest',
    'memory',
    'plugin',
]

ConversationEventKind = Literal[
    'user_speaking',
    'user',
    'assistant',
    'assistant_acting',
    'assistant_completed',
    'play_sound',
]


KindT = TypeVar('KindT', bound=str)


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(kw_only=True)
class Event(Generic[KindT]):
    """Base type shared by all persisted events."""

    kind: KindT
    timestamp: str = field(default_factory=_utc_timestamp)
    processed_at: float = 0.0
    memorized_at: float | None = 0.0
    responded_at: float | None = 0.0


class GameEventContent(TypedDict):
    event: str
    timestamp: str


@dataclass(kw_only=True)
class GameEvent(Event[Literal['game']]):
    content: GameEventContent
    historic: bool
    kind: Literal['game'] = 'game'


@dataclass(kw_only=True)
class StatusEvent(Event[Literal['status']]):
    status: dict[str, object]
    kind: Literal['status'] = 'status'


@dataclass(kw_only=True)
class ProjectedEvent(Event[Literal['projected']]):
    content: dict[str, object]
    kind: Literal['projected'] = 'projected'


@dataclass(kw_only=True)
class ExternalEvent(Event[Literal['external']]):
    content: dict[str, object]
    kind: Literal['external'] = 'external'


@dataclass(kw_only=True)
class QuestEvent(Event[Literal['quest']]):
    content: dict[str, object]
    kind: Literal['quest'] = 'quest'


@dataclass(kw_only=True)
class PluginEvent(Event[Literal['plugin']]):
    plugin_event_content: Any
    plugin_event_name: str
    kind: Literal['plugin'] = 'plugin'


@dataclass(kw_only=True)
class ConversationEvent(Event[ConversationEventKind]):
    content: str
    reasons: list[str] | None = None
    kind: ConversationEventKind


@dataclass(kw_only=True)
class ToolEvent(Event[Literal['tool']]):
    request: list[dict[str, object]]
    results: list[dict[str, object]]
    text: list[str] | None = None
    kind: Literal['tool'] = 'tool'


@dataclass(kw_only=True)
class MemoryEvent(Event[Literal['memory']]):
    content: str
    metadata: dict[str, object]
    embedding: list[float]
    kind: Literal['memory'] = 'memory'


EventLike = (
    GameEvent
    | StatusEvent
    | ProjectedEvent
    | ExternalEvent
    | QuestEvent
    | PluginEvent
    | ConversationEvent
    | ToolEvent
    | MemoryEvent
)

EventClasses: list[type[Event]] = [
    GameEvent,
    ConversationEvent,
    ToolEvent,
    StatusEvent,
    ProjectedEvent,
    ExternalEvent,
    QuestEvent,
    MemoryEvent,
    PluginEvent,
]