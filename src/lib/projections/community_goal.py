from datetime import datetime
from typing import Optional, cast

from typing_extensions import override
from pydantic import BaseModel, Field

from ..Event import Event, GameEvent
from ..EventManager import Projection
from ..EventModels import LoadGameEvent


def _as_int(value: object, default: int = 0) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _as_str(value: object, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _as_bool(value: object, default: bool = False) -> bool:
    return value if isinstance(value, bool) else default


class CommunityGoalTopTier(BaseModel):
    """Top tier reward for a community goal."""
    Name: str = Field(description="Name of the top tier reward")
    Bonus: str = Field(description="Bonus reward description")


class CommunityGoalItem(BaseModel):
    """An active community goal."""
    CGID: int = Field(description="Community goal unique identifier")
    Title: str = Field(description="Title of the community goal")
    SystemName: str = Field(description="Star system where the goal is located")
    MarketName: str = Field(description="Station/market name for the goal")
    Expiry: str = Field(description="Expiry timestamp in ISO format")
    IsComplete: bool = Field(description="Whether the goal has been completed")
    CurrentTotal: int = Field(description="Current total contributions")
    PlayerContribution: int = Field(description="Commander's contribution amount")
    NumContributors: int = Field(description="Total number of contributors")
    TopTier: Optional[CommunityGoalTopTier] = Field(default=None, description="Top tier reward info")
    TierReached: str = Field(description="Current tier reached")
    PlayerPercentileBand: int = Field(description="Commander's percentile band (top X%)")
    Bonus: int = Field(description="Bonus credits earned")
    TopRankSize: Optional[int] = Field(default=None, description="Size of top rank bracket")
    PlayerInTopRank: Optional[bool] = Field(default=None, description="Whether commander is in top rank")


class CommunityGoalStateModel(BaseModel):
    """Current community goals the commander is participating in."""
    event: Optional[str] = Field(default=None, description="Event type")
    timestamp: Optional[str] = Field(default=None, description="Last update timestamp")
    CurrentGoals: Optional[list[CommunityGoalItem]] = Field(default=None, description="List of active community goals")


class CommunityGoal(Projection[CommunityGoalStateModel]):
    StateModel = CommunityGoalStateModel

    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent) and event.content.get("event") == "CommunityGoal":
            payload = cast(dict[str, object], event.content)
            # Parse goals from event content
            raw_goals = cast(list[dict[str, object]], payload.get("CurrentGoals", []))
            goals = []
            for entry in raw_goals:
                g = cast(dict[str, object], entry)
                top_tier = None
                top_tier_payload = g.get("TopTier")
                if isinstance(top_tier_payload, dict):
                    top_tier = CommunityGoalTopTier(
                        Name=str(top_tier_payload.get("Name", "")),
                        Bonus=str(top_tier_payload.get("Bonus", "")),
                    )
                cgid = _as_int(g.get("CGID", 0))
                current_total = _as_int(g.get("CurrentTotal", 0))
                player_contribution = _as_int(g.get("PlayerContribution", 0))
                num_contributors = _as_int(g.get("NumContributors", 0))
                percentile = _as_int(g.get("PlayerPercentileBand", 0))
                bonus_value = _as_int(g.get("Bonus", 0))
                title = _as_str(g.get("Title", ""))
                system_name = _as_str(g.get("SystemName", ""))
                market_name = _as_str(g.get("MarketName", ""))
                expiry = _as_str(g.get("Expiry", ""))
                tier_reached = _as_str(g.get("TierReached", ""))
                is_complete = _as_bool(g.get("IsComplete", False))
                goals.append(
                    CommunityGoalItem(
                        CGID=cgid,
                        Title=title,
                        SystemName=system_name,
                        MarketName=market_name,
                        Expiry=expiry,
                        IsComplete=is_complete,
                        CurrentTotal=current_total,
                        PlayerContribution=player_contribution,
                        NumContributors=num_contributors,
                        TopTier=top_tier,
                        TierReached=tier_reached,
                        PlayerPercentileBand=percentile,
                        Bonus=bonus_value,
                        TopRankSize=cast(Optional[int], g.get("TopRankSize")),
                        PlayerInTopRank=cast(Optional[bool], g.get("PlayerInTopRank")),
                    )
                )
            goals = goals if goals else None

            self.state.event = cast(Optional[str], payload.get("event"))
            self.state.timestamp = cast(Optional[str], payload.get("timestamp"))
            self.state.CurrentGoals = goals

        elif isinstance(event, GameEvent) and event.content.get("event") == "LoadGame":
            payload = cast(LoadGameEvent, event.content)
            # Check for expired goals and remove them
            current_time = payload.get("timestamp", event.timestamp)
            current_dt = datetime.fromisoformat(current_time.replace("Z", "+00:00"))

            # Filter out expired goals
            active_goals = []
            current_goals = self.state.CurrentGoals or []
            for goal in current_goals:
                expiry_time = goal.Expiry or "1970-01-01T00:00:00Z"
                expiry_dt = datetime.fromisoformat(expiry_time.replace("Z", "+00:00"))

                # Keep goal if it hasn't expired yet
                if current_dt < expiry_dt:
                    active_goals.append(goal)

            # Update state with only non-expired goals
            self.state.CurrentGoals = active_goals if active_goals else None
