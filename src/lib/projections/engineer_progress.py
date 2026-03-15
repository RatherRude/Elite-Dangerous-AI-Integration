from typing import Literal, Optional, cast

from typing_extensions import override
from pydantic import BaseModel, Field

from ..Event import Event, GameEvent
from ..EventModels import EngineerProgressEvent
from ..EventManager import Projection


ENGINEER_PROGRESS_LITERAL = Literal["Known", "Invited", "Acquainted", "Unlocked", "Barred"]


class EngineerState(BaseModel):
    """Progress status with an engineer."""
    Engineer: str = Field(description="Engineer name")
    EngineerID: int = Field(description="Unique engineer identifier")
    Progress: Optional[ENGINEER_PROGRESS_LITERAL] = Field(default=None, description="Relationship status: Known/Invited/Acquainted/Unlocked/Barred")
    Rank: Optional[int] = Field(default=None, description="Current rank with this engineer (1-5)")
    RankProgress: Optional[int] = Field(default=None, description="Progress percentage to next rank")


class EngineerProgressStateModel(BaseModel):
    """Commander's progress with all engineers."""
    event: str = "EngineerProgress"
    timestamp: str = Field(default="1970-01-01T00:00:00Z", description="Last update timestamp")
    Engineers: list[EngineerState] = Field(default_factory=list, description="List of engineer progress states")


class EngineerProgress(Projection[EngineerProgressStateModel]):
    StateModel = EngineerProgressStateModel

    @staticmethod
    def _normalize_progress(value: object) -> ENGINEER_PROGRESS_LITERAL | None:
        if isinstance(value, str) and value in {"Known", "Invited", "Acquainted", "Unlocked", "Barred"}:
            return cast(ENGINEER_PROGRESS_LITERAL, value)
        return None

    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent) and event.content.get("event") == "EngineerProgress":
            payload = cast(EngineerProgressEvent, event.content)
            # Handle startup form - save entire event
            if "Engineers" in payload:
                engineers: list[EngineerState] = []
                for e in payload.get("Engineers", []):
                    engineers.append(
                        EngineerState(
                            Engineer=e.get("Engineer", "Unknown") if isinstance(e.get("Engineer"), str) else "Unknown",
                            EngineerID=e.get("EngineerID", 0) if isinstance(e.get("EngineerID"), int) else 0,
                            Progress=self._normalize_progress(e.get("Progress")),
                            Rank=e.get("Rank") if isinstance(e.get("Rank"), int) else None,
                            RankProgress=e.get("RankProgress") if isinstance(e.get("RankProgress"), int) else None,
                        )
                    )
                event_name = payload.get("event", "EngineerProgress")
                timestamp = payload.get("timestamp", "1970-01-01T00:00:00Z")
                self.state.event = event_name if isinstance(event_name, str) else "EngineerProgress"
                self.state.timestamp = timestamp if isinstance(timestamp, str) else "1970-01-01T00:00:00Z"
                self.state.Engineers = engineers

            # Handle update form - single engineer update
            elif "Engineer" in payload and "EngineerID" in payload:
                engineer_id = payload.get("EngineerID", 0)
                if not isinstance(engineer_id, int):
                    engineer_id = 0

                # Find existing engineer or create new one
                existing_engineer = None
                for i, engineer in enumerate(self.state.Engineers):
                    if engineer.EngineerID == engineer_id:
                        existing_engineer = self.state.Engineers[i]
                        break

                if existing_engineer:
                    # Update existing engineer
                    if "Engineer" in payload:
                        engineer_name = payload.get("Engineer", "Unknown")
                        if isinstance(engineer_name, str):
                            existing_engineer.Engineer = engineer_name
                    if "Progress" in payload:
                        existing_engineer.Progress = self._normalize_progress(payload.get("Progress"))
                    if "Rank" in payload:
                        rank_value = payload.get("Rank")
                        if isinstance(rank_value, int):
                            existing_engineer.Rank = rank_value
                    if "RankProgress" in payload:
                        rank_progress = payload.get("RankProgress")
                        if isinstance(rank_progress, int):
                            existing_engineer.RankProgress = rank_progress
                else:
                    # Create new engineer entry
                    new_engineer = EngineerState(
                        Engineer=payload.get("Engineer", "Unknown") if isinstance(payload.get("Engineer"), str) else "Unknown",
                        EngineerID=engineer_id,
                        Progress=self._normalize_progress(payload.get("Progress")),
                        Rank=payload.get("Rank") if isinstance(payload.get("Rank"), int) else None,
                        RankProgress=payload.get("RankProgress") if isinstance(payload.get("RankProgress"), int) else None,
                    )
                    self.state.Engineers.append(new_engineer)
