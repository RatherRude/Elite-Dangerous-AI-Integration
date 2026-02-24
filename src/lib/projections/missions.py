from typing import Literal, Optional, cast

from typing_extensions import override
from pydantic import BaseModel, Field

from ..Event import Event, GameEvent
from ..EventModels import MissionAcceptedEvent, MissionRedirectedEvent, MissionsEvent
from ..EventManager import Projection


class MissionState(BaseModel):
    """An active mission the commander has accepted."""
    Faction: str = Field(description="The faction that issued the mission")
    Name: str = Field(description="Internal mission name/identifier")
    LocalisedName: str = Field(description="Human-readable mission name")
    Expiry: str = Field(description="Mission expiry timestamp in ISO format")
    Wing: bool = Field(description="Whether this is a wing mission")
    Influence: str = Field(description="Influence effect on completion (None/Low/Med/High)")
    Reputation: str = Field(description="Reputation effect on completion (None/Low/Med/High)")
    MissionID: int = Field(description="Unique mission identifier")
    OriginStation: Optional[str] = Field(default=None, description="Station where mission was accepted")
    Commodity: Optional[str] = Field(default=None, description="Commodity to deliver (for delivery missions)")
    Count: Optional[int] = Field(default=None, description="Amount to deliver/collect")
    Target: Optional[str] = Field(default=None, description="Target name (for assassination missions)")
    TargetType: Optional[str] = Field(default=None, description="Target type")
    TargetFaction: Optional[str] = Field(default=None, description="Target faction")
    DestinationSystem: Optional[str] = Field(default=None, description="Destination star system")
    DestinationSettlement: Optional[str] = Field(default=None, description="Destination settlement")
    DestinationStation: Optional[str] = Field(default=None, description="Destination station")
    PassengerCount: Optional[int] = Field(default=None, description="Number of passengers (for passenger missions)")
    PassengerVIPs: Optional[bool] = Field(default=None, description="Whether passengers are VIPs")
    PassengerWanted: Optional[bool] = Field(default=None, description="Whether passengers are wanted")
    PassengerType: Optional[str] = Field(default=None, description="Type of passengers")
    Donation: Optional[int] = Field(default=None, description="Donation amount for donation missions")
    Reward: Optional[int] = Field(default=None, description="Credit reward on completion")


class UnknownMissionState(BaseModel):
    """A mission that was loaded from save but details are unknown."""
    MissionID: int = Field(description="Unique mission identifier")
    Name: str = Field(description="Mission name")


class MissionsStateModel(BaseModel):
    """Current mission state of the commander."""
    Active: list[MissionState] = Field(default_factory=list, description="List of active missions with full details")
    Unknown: Optional[list[UnknownMissionState]] = Field(default=None, description="Missions loaded from save with limited details")


class Missions(Projection[MissionsStateModel]):
    StateModel = MissionsStateModel

    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent) and event.content.get("event") == "Missions":
            payload = cast(MissionsEvent, event.content)
            active_ids = [mission["MissionID"] for mission in payload.get("Active", [])]
            known_ids = [mission.MissionID for mission in self.state.Active]
            self.state.Active = [mission for mission in self.state.Active if mission.MissionID in active_ids]
            unknown_missions = [
                UnknownMissionState(MissionID=m["MissionID"], Name=m.get("Name", "Unknown"))
                for m in payload.get("Active", [])
                if m["MissionID"] not in known_ids
            ]
            self.state.Unknown = unknown_missions if unknown_missions else None

        if isinstance(event, GameEvent) and event.content.get("event") == "MissionAccepted":
            payload = cast(MissionAcceptedEvent, event.content)
            donation = payload.get("Donation")
            if not isinstance(donation, int):
                donation = None
            reward = payload.get("Reward")
            if not isinstance(reward, int):
                reward = None
            count_value = payload.get("Count")
            if not isinstance(count_value, int):
                count_value = None
            passenger_count = payload.get("PassengerCount")
            if not isinstance(passenger_count, int):
                passenger_count = None
            faction = payload.get("Faction", "Unknown")
            name = payload.get("Name", "Unknown")
            localized_name = payload.get("LocalisedName", "Unknown")
            expiry = payload.get("Expiry", "1970-01-01T00:00:00Z")
            wing = payload.get("Wing", False)
            influence = payload.get("Influence", "Unknown")
            reputation = payload.get("Reputation", "Unknown")
            mission_id = payload.get("MissionID", 0)
            commodity = payload.get("Commodity")
            target = payload.get("Target")
            target_faction = payload.get("TargetFaction")
            destination_system = payload.get("DestinationSystem")
            destination_settlement = payload.get("DestinationSettlement")
            destination_station = payload.get("DestinationStation")
            passenger_vips = payload.get("PassengerVIPs")
            passenger_wanted = payload.get("PassengerWanted")
            passenger_type = payload.get("PassengerType")
            mission = MissionState(
                Faction=faction if isinstance(faction, str) else "Unknown",
                Name=name if isinstance(name, str) else "Unknown",
                LocalisedName=localized_name if isinstance(localized_name, str) else "Unknown",
                Expiry=expiry if isinstance(expiry, str) else "1970-01-01T00:00:00Z",
                Wing=wing if isinstance(wing, bool) else False,
                Influence=influence if isinstance(influence, str) else "Unknown",
                Reputation=reputation if isinstance(reputation, str) else "Unknown",
                MissionID=mission_id if isinstance(mission_id, int) else 0,
                Donation=donation,
                Reward=reward,
                Commodity=commodity if isinstance(commodity, str) else None,
                Count=count_value,
                Target=target if isinstance(target, str) else None,
                TargetFaction=target_faction if isinstance(target_faction, str) else None,
                DestinationSystem=destination_system if isinstance(destination_system, str) else None,
                DestinationSettlement=destination_settlement if isinstance(destination_settlement, str) else None,
                DestinationStation=destination_station if isinstance(destination_station, str) else None,
                PassengerCount=passenger_count,
                PassengerVIPs=passenger_vips if isinstance(passenger_vips, bool) else None,
                PassengerWanted=passenger_wanted if isinstance(passenger_wanted, bool) else None,
                PassengerType=passenger_type if isinstance(passenger_type, str) else None,
            )
            self.state.Active.append(mission)

        if isinstance(event, GameEvent) and event.content.get("event") == "MissionCompleted":
            mission_id = event.content.get("MissionID", 0)
            self.state.Active = [mission for mission in self.state.Active if mission.MissionID != mission_id]
            if self.state.Unknown:
                self.state.Unknown = [mission for mission in self.state.Unknown if mission.MissionID != mission_id]
                if not self.state.Unknown:
                    self.state.Unknown = None

        if isinstance(event, GameEvent) and event.content.get("event") == "MissionRedirected":
            payload = cast(MissionRedirectedEvent, event.content)
            mission_id = payload.get("MissionID", 0)
            if not isinstance(mission_id, int):
                mission_id = 0
            existing_mission = next((mission for mission in self.state.Active if mission.MissionID == mission_id), None)
            new_destination_system = payload.get("NewDestinationSystem", None)
            new_destination_station = payload.get("NewDestinationStation", None)
            new_destination_settlement = payload.get("NewDestinationSettlement", None)
            if not isinstance(new_destination_system, str):
                new_destination_system = None
            if not isinstance(new_destination_station, str):
                new_destination_station = None
            if not isinstance(new_destination_settlement, str):
                new_destination_settlement = None

            if existing_mission:
                if new_destination_system:
                    existing_mission.DestinationSystem = new_destination_system
                if new_destination_station:
                    existing_mission.DestinationStation = new_destination_station
                    if existing_mission.DestinationStation == existing_mission.OriginStation:
                        existing_mission.Name += " (Collect Reward)"
                if new_destination_settlement:
                    existing_mission.DestinationSettlement = new_destination_settlement

                self.state.Active = [mission for mission in self.state.Active if mission.MissionID != mission_id]
                self.state.Active.append(existing_mission)

        # If we Undock with a new mission, we probably accepted it at the station we undocked from
        if isinstance(event, GameEvent) and event.content.get("event") == "Undocked":
            for mission in self.state.Active:
                if mission.OriginStation is None:
                    station_name = event.content.get("StationName", "Unknown")
                    if isinstance(station_name, str):
                        mission.OriginStation = station_name
        # If we Dock with a new mission, we probably accepted it somewhere in space, so we don't know the exact origin
        if isinstance(event, GameEvent) and event.content.get("event") == "Docked":
            for mission in self.state.Active:
                if mission.OriginStation is None:
                    mission.OriginStation = "Unknown"

        if isinstance(event, GameEvent) and event.content.get("event") == "MissionAbandoned":
            mission_id = event.content.get("MissionID", 0)
            self.state.Active = [mission for mission in self.state.Active if mission.MissionID != mission_id]
            if self.state.Unknown:
                self.state.Unknown = [mission for mission in self.state.Unknown if mission.MissionID != mission_id]
                if not self.state.Unknown:
                    self.state.Unknown = None

        if isinstance(event, GameEvent) and event.content.get("event") == "MissionFailed":
            mission_id = event.content.get("MissionID", 0)
            self.state.Active = [mission for mission in self.state.Active if mission.MissionID != mission_id]
            if self.state.Unknown:
                self.state.Unknown = [mission for mission in self.state.Unknown if mission.MissionID != mission_id]
                if not self.state.Unknown:
                    self.state.Unknown = None
