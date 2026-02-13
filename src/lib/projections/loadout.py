from distro.distro import TypedDict
from lib.EventModels import LoadoutEventModulesItemEngineering
from typing import cast

from typing_extensions import override

from ..Event import Event, GameEvent
from ..EventManager import Projection
from pydantic import BaseModel, Field

from ..EventModels import LoadoutEvent


class LoadoutModifierA(BaseModel):
    LessIsGood: int
    OriginalValue: float
    Value: float
    Label: str

class LoadoutModifierB(BaseModel):
    ValueStr: str
    ValueStr_Localised: str
    Label: str


class LoadoutEngineering(BaseModel):
    Level: int
    EngineerID: int
    Engineer: str | None = None
    ExperimentalEffect: str | None = None
    BlueprintID: int
    Quality: float
    Modifiers: list[LoadoutModifierA | LoadoutModifierB] = Field(default_factory=list)
    ExperimentalEffect_Localised: str | None = None
    BlueprintName: str


class LoadoutModule(BaseModel):
    AmmoInHopper: int | None = None
    AmmoInClip: int | None = None
    Item: str
    Value: int | None = None
    Health: float
    Engineering: LoadoutEngineering | None = None
    Slot: str
    On: bool
    Priority: int


class LoadoutFuelCapacity(BaseModel):
    Reserve: float | None = None
    Main: float | None = None


class LoadoutState(BaseModel):
    ShipName: str | None = None
    HullValue: int | None = None
    HullHealth: float | None = None
    ShipIdent: str | None = None
    ModulesValue: int | None = None
    CargoCapacity: int | None = None
    Modules: list[LoadoutModule] = Field(default_factory=list)
    FuelCapacity: LoadoutFuelCapacity | None = None
    MaxJumpRange: float | None = None
    Rebuy: int | None = None
    ShipID: int | None = None
    event: str | None = None
    timestamp: str | None = None
    UnladenMass: float | None = None
    Ship: str | None = None
    Hot: bool | None = None


class Loadout(Projection[LoadoutState]):
    StateModel = LoadoutState

    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent) and event.content.get("event") == "Loadout":
            payload = cast(LoadoutEvent, event.content)
            self.state.ShipName = payload.get("ShipName")
            self.state.HullValue = payload.get("HullValue")
            self.state.HullHealth = payload.get("HullHealth")
            self.state.ShipIdent = payload.get("ShipIdent")
            self.state.ModulesValue = payload.get("ModulesValue")
            self.state.CargoCapacity = payload.get("CargoCapacity")
            self.state.Modules = []
            for module in payload.get("Modules", []):
                engineering = module.get("Engineering")
                if isinstance(engineering, dict):
                    modifiers: list[LoadoutModifierA | LoadoutModifierB] = []
                    for mod in engineering.get("Modifiers", []):
                        if "LessIsGood" in mod:
                            modifiers.append(LoadoutModifierA(**mod))
                        elif "ValueStr" in mod:
                            modifiers.append(LoadoutModifierB(**mod))
                    engineering_data = {**engineering, "Modifiers": modifiers}
                    engineering_model = LoadoutEngineering(**engineering_data)
                else:
                    engineering_model = None
                self.state.Modules.append(
                    LoadoutModule(
                        AmmoInHopper=module.get("AmmoInHopper"),
                        AmmoInClip=module.get("AmmoInClip"),
                        Item=module.get("Item", ""),
                        Value=module.get("Value"),
                        Health=module.get("Health", 0.0),
                        Engineering=engineering_model,
                        Slot=module.get("Slot", ""),
                        On=module.get("On", False),
                        Priority=module.get("Priority", 0),
                    )
                )
            fuel_capacity = payload.get("FuelCapacity")
            self.state.FuelCapacity = LoadoutFuelCapacity(**fuel_capacity) if isinstance(fuel_capacity, dict) else None
            self.state.MaxJumpRange = payload.get("MaxJumpRange")
            self.state.Rebuy = payload.get("Rebuy")
            self.state.ShipID = payload.get("ShipID")
            self.state.event = payload.get("event")
            self.state.timestamp = payload.get("timestamp")
            self.state.UnladenMass = payload.get("UnladenMass")
            self.state.Ship = payload.get("Ship")
            self.state.Hot = payload.get("Hot")
