from typing import cast

from typing_extensions import override
from pydantic import BaseModel, Field

from ..Event import Event, GameEvent
from ..EventModels import ProgressEvent, RankEvent
from ..EventManager import Projection


class RankProgressEntry(BaseModel):
    """Rank and progress for a single category."""
    Rank: int = Field(default=0, description="Rank value")
    RankName: str = Field(default="Unknown", description="Human-readable rank name")
    Progress: int = Field(default=0, description="Progress to next rank (0-100)")


class RankProgressStateModel(BaseModel):
    """Commander rank and progress per category."""
    Combat: RankProgressEntry = Field(default_factory=RankProgressEntry, description="Combat rank/progress")
    Trade: RankProgressEntry = Field(default_factory=RankProgressEntry, description="Trade rank/progress")
    Explore: RankProgressEntry = Field(default_factory=RankProgressEntry, description="Exploration rank/progress")
    Empire: RankProgressEntry = Field(default_factory=RankProgressEntry, description="Empire rank/progress")
    Federation: RankProgressEntry = Field(default_factory=RankProgressEntry, description="Federation rank/progress")
    CQC: RankProgressEntry = Field(default_factory=RankProgressEntry, description="CQC rank/progress")
    Soldier: RankProgressEntry = Field(default_factory=RankProgressEntry, description="Soldier rank/progress")
    Exobiologist: RankProgressEntry = Field(default_factory=RankProgressEntry, description="Exobiologist rank/progress")
    Timestamp: str = Field(default="1970-01-01T00:00:00Z", description="Timestamp of last rank/progress event")


class RankProgress(Projection[RankProgressStateModel]):
    StateModel = RankProgressStateModel

    _category_keys = [
        "Combat",
        "Trade",
        "Explore",
        "Empire",
        "Federation",
        "CQC",
        "Soldier",
        "Exobiologist",
    ]
    _rank_names: dict[str, list[str]] = {
        "Combat": [
            "Harmless",
            "Mostly Harmless",
            "Novice",
            "Competent",
            "Expert",
            "Master",
            "Dangerous",
            "Deadly",
            "Elite",
            "Elite I",
            "Elite II",
            "Elite III",
            "Elite IV",
            "Elite V",
        ],
        "Trade": [
            "Penniless",
            "Mostly Pennliess",
            "Peddler",
            "Dealer",
            "Merchant",
            "Broker",
            "Entrepreneur",
            "Tycoon",
            "Elite",
            "Elite I",
            "Elite II",
            "Elite III",
            "Elite IV",
            "Elite V",
        ],
        "Explore": [
            "Aimless",
            "Mostly Aimless",
            "Scout",
            "Surveyor",
            "Explorer",
            "Pathfinder",
            "Ranger",
            "Pioneer",
            "Elite",
            "Elite I",
            "Elite II",
            "Elite III",
            "Elite IV",
            "Elite V",
        ],
        "Federation": [
            "None",
            "Recruit",
            "Cadet",
            "Midshipman",
            "Petty Officer",
            "Chief Petty Officer",
            "Warrant Officer",
            "Ensign",
            "Lieutenant",
            "Lt. Commander",
            "Post Commander",
            "Post Captain",
            "Rear Admiral",
            "Vice Admiral",
            "Admiral",
        ],
        "Empire": [
            "None",
            "Outsider",
            "Serf",
            "Master",
            "Squire",
            "Knight",
            "Lord",
            "Baron",
            "Viscount",
            "Count",
            "Earl",
            "Marquis",
            "Duke",
            "Prince",
            "King",
        ],
        "CQC": [
            "Helpless",
            "Mostly Helpless",
            "Amateur",
            "Semi Professional",
            "Professional",
            "Champion",
            "Hero",
            "Legend",
            "Elite",
            "Elite I",
            "Elite II",
            "Elite III",
            "Elite IV",
            "Elite V",
        ],
        "Soldier": [
            "Defenceless",
            "Mostly Defenceless",
            "Rookie",
            "Soldier",
            "Gunslinger",
            "Warrior",
            "Gladiator",
            "Deadeye",
            "Elite",
            "Elite I",
            "Elite II",
            "Elite III",
            "Elite IV",
            "Elite V",
        ],
        "Exobiologist": [
            "Directionless",
            "Mostly Directionless",
            "Compiler",
            "Collector",
            "Cataloguer",
            "Taxonomist",
            "Ecologist",
            "Geneticist",
            "Elite",
            "Elite I",
            "Elite II",
            "Elite III",
            "Elite IV",
            "Elite V",
        ],
    }

    def _rank_name_for(self, category: str, rank_value: int) -> str:
        names = self._rank_names.get(category, [])
        if 0 <= rank_value < len(names):
            return names[rank_value]
        return "Unknown"

    @override
    def process(self, event: Event) -> None:
        if not isinstance(event, GameEvent):
            return

        event_name = event.content.get("event")
        if event_name == "Rank":
            payload = cast(RankEvent, event.content)
            for key in self._category_keys:
                if key in payload:
                    rank_value = payload.get(key, 0)
                    if not isinstance(rank_value, int):
                        rank_value = 0
                    category = getattr(self.state, key)
                    category.Rank = rank_value
                    category.RankName = self._rank_name_for(key, rank_value)
            if "timestamp" in payload:
                self.state.Timestamp = payload["timestamp"]

        if event_name == "Progress":
            payload = cast(ProgressEvent, event.content)
            for key in self._category_keys:
                if key in payload:
                    progress_value = payload.get(key, 0)
                    if not isinstance(progress_value, int):
                        progress_value = 0
                    getattr(self.state, key).Progress = progress_value
            if "timestamp" in payload:
                self.state.Timestamp = payload["timestamp"]

        if event_name == "Promotion":
            for key in self._category_keys:
                if key in event.content:
                    category = getattr(self.state, key)
                    rank_value = event.content.get(key, 0)
                    if not isinstance(rank_value, int):
                        rank_value = 0
                    category.Rank = rank_value
                    category.RankName = self._rank_name_for(key, rank_value)
                    category.Progress = 0
            if "timestamp" in event.content:
                self.state.Timestamp = event.content["timestamp"]
