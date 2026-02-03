from typing import cast

from typing_extensions import override
from pydantic import BaseModel, Field

from ..Event import Event, GameEvent
from ..EventManager import Projection
from ..EventModels import SuitLoadoutEvent


class SuitWeaponModule(BaseModel):
    """A weapon or tool equipped in the suit loadout."""
    SlotName: str = Field(description="Equipment slot name")
    SuitModuleID: int = Field(description="Module unique identifier")
    ModuleName: str = Field(description="Module internal name")
    ModuleName_Localised: str = Field(description="Human-readable module name")
    Class: int = Field(description="Module class/grade (1-5)")
    WeaponMods: list[str] = Field(default_factory=list, description="Applied weapon modifications")


class SuitLoadoutStateModel(BaseModel):
    """Commander's current on-foot suit loadout."""
    SuitID: int = Field(default=0, description="Suit unique identifier")
    SuitName: str = Field(default="Unknown", description="Suit internal name")
    SuitName_Localised: str = Field(default="Unknown", description="Human-readable suit name")
    SuitMods: list[str] = Field(default_factory=list, description="Applied suit modifications")
    LoadoutID: int = Field(default=0, description="Loadout unique identifier")
    LoadoutName: str = Field(default="Unknown", description="Custom loadout name")
    Modules: list[SuitWeaponModule] = Field(default_factory=list, description="Equipped weapons and tools")


class SuitLoadout(Projection[SuitLoadoutStateModel]):
    StateModel = SuitLoadoutStateModel

    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent) and event.content.get("event") == "SuitLoadout":
            payload = cast(SuitLoadoutEvent, event.content)
            # Update the entire state with the new loadout information
            self.state.SuitID = payload.get("SuitID", 0)
            self.state.SuitName = payload.get("SuitName", "Unknown")
            self.state.SuitName_Localised = payload.get("SuitName_Localised", "Unknown")
            self.state.SuitMods = payload.get("SuitMods", [])
            self.state.LoadoutID = payload.get("LoadoutID", 0)
            self.state.LoadoutName = payload.get("LoadoutName", "Unknown")

            # Process weapon modules with proper SuitWeaponModule instantiation
            self.state.Modules = [
                SuitWeaponModule(
                    SlotName=module.get("SlotName", "Unknown"),
                    SuitModuleID=module.get("SuitModuleID", 0),
                    ModuleName=module.get("ModuleName", "Unknown"),
                    ModuleName_Localised=module.get("ModuleName_Localised", "Unknown"),
                    Class=module.get("Class", 0),
                    WeaponMods=module.get("WeaponMods", []),
                )
                for module in payload.get("Modules", [])
            ]
