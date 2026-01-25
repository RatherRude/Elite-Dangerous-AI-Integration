import json
import re
import traceback
from datetime import datetime, timezone, timedelta
from typing import Literal, Optional, cast

from typing_extensions import override
from pydantic import BaseModel, Field

from ..Config import get_asset_path
from ..Event import Event, GameEvent, ProjectedEvent, StatusEvent
from ..EventManager import Projection
from ..Logger import log
from ..StatusParser import Status
from ..EventModels import (
    CargoEvent,
    DockFighterEvent,
    FighterDestroyedEvent,
    FighterRebuiltEvent,
    JetConeBoostEvent,
    LaunchFighterEvent,
    LoadoutEvent,
    SetUserShipNameEvent,
    SynthesisEvent,
    VehicleSwitchEvent,
)


with open(get_asset_path("ship_sizes.json"), encoding="utf-8") as handle:
    ship_sizes: dict[str, Literal["S", "M", "L", "Unknown"]] = json.load(handle)

with open(get_asset_path("fsd_stats.json"), encoding="utf-8") as handle:
    fsd_stats_payload = json.load(handle)

FSD_STATS = fsd_stats_payload.get("fsd_stats", {})
FSD_OVERCHARGE_STATS = fsd_stats_payload.get("fsd_overcharge_stats", {})
FSD_MKii = fsd_stats_payload.get("fsd_mkii", {})
FSD_GUARDIAN_BOOSTER = fsd_stats_payload.get("fsd_guardian_booster", {})
RATING_BY_CLASSNUM = {int(key): value for key, value in fsd_stats_payload.get("rating_by_classnum", {}).items()}


FIGHTER_STATUS_LITERAL = Literal["Ready", "Launched", "BeingRebuilt", "Abandoned"]


class FighterState(BaseModel):
    """State of a ship-launched fighter."""
    Status: FIGHTER_STATUS_LITERAL = Field(description="Current fighter status")
    ID: Optional[int] = Field(default=None, description="Fighter identifier when launched")
    Pilot: Optional[str] = Field(default=None, description="Who is piloting: Commander, NPC Crew, or No pilot")
    RebuiltAt: Optional[str] = Field(default=None, description="Timestamp when fighter will be rebuilt")


LANDING_PAD_SIZE_LITERAL = Literal["S", "M", "L", "Unknown"]


class ShipInfoStateModel(BaseModel):
    """Current ship information and capabilities."""
    Name: str = Field(default="Unknown", description="Custom ship name")
    Type: str = Field(default="Unknown", description="Ship type identifier")
    ShipIdent: str = Field(default="Unknown", description="Ship identification code")
    UnladenMass: float = Field(default=0, description="Ship mass without cargo or fuel (tons)")
    Cargo: float = Field(default=0, description="Current cargo weight (tons)")
    CargoCapacity: float = Field(default=0, description="Maximum cargo capacity (tons)")
    ShipCargo: float = Field(default=0, description="Ship cargo (not SRV) weight (tons)")
    FuelMain: float = Field(default=0, description="Current main fuel tank level (tons)")
    FuelMainCapacity: float = Field(default=0, description="Main fuel tank capacity (tons)")
    FuelReservoir: float = Field(default=0, description="Current reservoir fuel level (tons)")
    FuelReservoirCapacity: float = Field(default=0, description="Reservoir fuel capacity (tons)")
    FSDSynthesis: float = Field(default=0, description="FSD synthesis boost multiplier (0.25/0.5/1.0)")
    ReportedMaximumJumpRange: float = Field(default=0, description="Maximum jump range reported by game (ly)")
    DriveOptimalMass: float = Field(default=0, description="FSD optimal mass parameter")
    DriveLinearConst: float = Field(default=0, description="FSD linear constant")
    DrivePowerConst: float = Field(default=0, description="FSD power constant")
    GuardianfsdBooster: float = Field(default=0, description="Guardian FSD booster bonus (ly)")
    DriveMaxFuel: float = Field(default=0, description="Maximum fuel per jump (tons)")
    JetConeBoost: float = Field(default=1, description="Jet cone/neutron star boost multiplier")
    MinimumJumpRange: float = Field(default=0, description="Minimum jump range with full cargo (ly)")
    CurrentJumpRange: float = Field(default=0, description="Current jump range with current load (ly)")
    MaximumJumpRange: float = Field(default=0, description="Maximum jump range empty (ly)")
    LandingPadSize: LANDING_PAD_SIZE_LITERAL = "Unknown"
    IsMiningShip: bool = Field(default=False, description="Whether ship has mining equipment")
    hasLimpets: bool = Field(default=False, description="Whether ship has limpet controllers")
    hasDockingComputer: bool = Field(default=False, description="Whether ship has docking computer")
    Fighters: list[FighterState] = Field(default_factory=list, description="Ship-launched fighters status")


class ShipInfo(Projection[ShipInfoStateModel]):
    StateModel = ShipInfoStateModel

    @override
    def process(self, event: Event) -> list[ProjectedEvent]:
        projected_events: list[ProjectedEvent] = []

        if isinstance(event, StatusEvent) and event.status.get("event") == "Status":
            status = cast(Status, event.status)
            cargo_value = status.get("Cargo")
            if cargo_value is not None:
                self.state.Cargo = float(cargo_value)

            fuel = status.get("Fuel")
            if fuel:
                self.state.FuelMain = float(fuel.get("FuelMain") or 0)
                self.state.FuelReservoir = float(fuel.get("FuelReservoir") or 0)

        if isinstance(event, GameEvent) and event.content.get("event") == "Loadout":
            payload = cast(LoadoutEvent, event.content)
            if "ShipName" in payload:
                self.state.Name = payload.get("ShipName") or "Unknown"
            if "Ship" in payload:
                self.state.Type = payload.get("Ship") or "Unknown"
            if "ShipIdent" in payload:
                self.state.ShipIdent = payload.get("ShipIdent") or "Unknown"
            if "UnladenMass" in payload:
                self.state.UnladenMass = payload.get("UnladenMass") or 0.0
            if "CargoCapacity" in payload:
                self.state.CargoCapacity = payload.get("CargoCapacity") or 0
            if "FuelCapacity" in payload:
                self.state.FuelMainCapacity = payload["FuelCapacity"].get("Main") or 0
                self.state.FuelReservoirCapacity = payload["FuelCapacity"].get("Reserve") or 0

            if "MaxJumpRange" in payload:
                self.state.ReportedMaximumJumpRange = payload.get("MaxJumpRange") or 0

            if "Modules" in payload:
                modules = payload.get("Modules", [])
                has_refinery = any(module["Item"].startswith("int_refinery") for module in modules)
                if has_refinery:
                    self.state.IsMiningShip = True
                else:
                    self.state.IsMiningShip = False

                has_limpets = any(
                    module.get("Item", "").startswith("int_dronecontrol")
                    or module.get("Item", "").startswith("int_multidronecontrol_")
                    for module in modules
                )
                if has_limpets:
                    self.state.hasLimpets = True
                else:
                    self.state.hasLimpets = False

                has_docking_computer = any(
                    module.get("Item", "").startswith("int_dockingcomputer")
                    for module in modules
                )
                if has_docking_computer:
                    self.state.hasDockingComputer = True
                else:
                    self.state.hasDockingComputer = False

                # Check for fighter bay modules
                fighter_count = 0
                for module in modules:
                    module_item = module.get("Item", "")
                    if module_item == "int_fighterbay_size5_class1":
                        fighter_count = 1
                        break
                    elif module_item in ["int_fighterbay_size6_class1", "int_fighterbay_size7_class1"]:
                        fighter_count = 2
                        break

                if fighter_count > 0:
                    # Initialize fighters in Ready state without IDs
                    self.state.Fighters = [FighterState(Status="Ready") for _ in range(fighter_count)]
                else:
                    self.state.Fighters = []

                # Check for FSD Engine
                for module in modules:
                    module_slot = module.get("Slot", "")
                    if module_slot != "FrameShiftDrive":
                        continue

                    module_item = module.get("Item") or ""
                    over = "hyperdrive_overcharge" in module_item
                    mkii = "overchargebooster_mkii" in module_item
                    module_size_match = re.search(r"size(\d)", module_item)
                    module_class_match = re.search(r"class(\d)", module_item)
                    module_size = int(module_size_match.group(1)) if module_size_match else None
                    module_rating = RATING_BY_CLASSNUM.get(int(module_class_match.group(1))) if module_class_match else None

                    engineering_optimal_mass_override = None
                    engineering_max_fuel_override = None

                    for modifier in module.get("Engineering", {}).get("Modifiers", []) or []:
                        if modifier.get("Label") in ("FSDOptimalMass", "fsdoptimalmass"):
                            engineering_optimal_mass_override = float(modifier.get("Value"))

                        if modifier.get("Label") in ("MaxFuelPerJump", "maxfuelperjump"):
                            engineering_max_fuel_override = float(modifier.get("Value"))
                    if mkii is True:
                        all_module_stats = FSD_MKii
                    else:
                        all_module_stats = FSD_OVERCHARGE_STATS if over else FSD_STATS

                    module_stat: dict = all_module_stats.get(f"{module_size}{module_rating}", {})
                    self.state.DriveOptimalMass = (
                        engineering_optimal_mass_override
                        if engineering_optimal_mass_override is not None
                        else module_stat.get("opt_mass", 0.00)
                    )
                    self.state.DriveMaxFuel = (
                        engineering_max_fuel_override
                        if engineering_max_fuel_override is not None
                        else module_stat.get("max_fuel", 0.00)
                    )
                    self.state.DriveLinearConst = module_stat.get("linear_const", 0.0)
                    self.state.DrivePowerConst = module_stat.get("power_const", 0.0)

                    log("debug", "mkii?: ", mkii, " Fsd type again :", module_item)

                # Check for GuardianfsdBooster
                self.state.GuardianfsdBooster = 0
                for module in modules:
                    module_item = module.get("Item")
                    if "int_guardianfsdbooster" in (module_item or "").lower():
                        module_size_match = re.search(r"size(\d+)", module_item)
                        module_size = int(module_size_match.group(1)) if module_size_match else 0
                        guardian_booster_stats = FSD_GUARDIAN_BOOSTER.get(f"{module_size}H")

                        self.state.GuardianfsdBooster = guardian_booster_stats.get("jump_boost", 0.0)

        if isinstance(event, GameEvent) and event.content.get("event") == "JetConeBoost":
            payload = cast(JetConeBoostEvent, event.content)
            fsd_star_boost = payload.get("BoostValue", 1)
            self.state.JetConeBoost = fsd_star_boost

        if isinstance(event, GameEvent) and event.content.get("event") == "Synthesis":
            payload = cast(SynthesisEvent, event.content)
            fsd_inject_boost_name = payload.get("Name", "")

            if fsd_inject_boost_name == "FSD Basic":
                self.state.FSDSynthesis = 0.25

            elif fsd_inject_boost_name == "FSD Standard":
                self.state.FSDSynthesis = 0.5

            elif fsd_inject_boost_name == "FSD Premium":
                self.state.FSDSynthesis = 1

        if isinstance(event, GameEvent) and event.content.get("event") == "FSDJump":
            self.state.JetConeBoost = 1
            self.state.FSDSynthesis = 0

        if isinstance(event, GameEvent) and event.content.get("event") == "Cargo":
            payload = cast(CargoEvent, event.content)
            self.state.Cargo = payload.get("Count") or 0
            if payload.get("Vessel") == "Ship":
                self.state.ShipCargo = payload.get("Count") or 0

        if isinstance(event, GameEvent) and event.content.get("event") in ["RefuelAll", "RepairAll", "BuyAmmo"]:
            if self.state.hasLimpets and self.state.Cargo < self.state.CargoCapacity:
                projected_events.append(ProjectedEvent(content={"event": "RememberLimpets"}))

        if isinstance(event, GameEvent) and event.content.get("event") == "SetUserShipName":
            payload = cast(SetUserShipNameEvent, event.content)
            if "UserShipName" in payload:
                self.state.Name = payload.get("UserShipName") or "Unknown"
            if "UserShipId" in payload:
                self.state.ShipIdent = payload.get("UserShipId") or "Unknown"

        if isinstance(event, GameEvent) and event.content.get("event") == "LaunchFighter":
            payload = cast(LaunchFighterEvent, event.content)
            fighter_id = payload.get("ID")
            player_controlled = payload.get("PlayerControlled", False)

            if fighter_id is not None:
                # Determine pilot based on PlayerControlled flag
                pilot = "Commander" if player_controlled else "NPC Crew"

                # Find existing fighter with this ID or a ready fighter without ID
                fighter_found = False
                for fighter in self.state.Fighters:
                    if fighter.ID == fighter_id:
                        # Fighter with this ID already exists
                        fighter.Status = "Launched"
                        fighter.Pilot = pilot
                        fighter_found = True
                        break

                if not fighter_found:
                    # Find a ready fighter without ID
                    for fighter in self.state.Fighters:
                        if fighter.Status == "Ready" and fighter.ID is None:
                            fighter.ID = fighter_id
                            fighter.Status = "Launched"
                            fighter.Pilot = pilot
                            break

        if isinstance(event, GameEvent) and event.content.get("event") == "DockFighter":
            payload = cast(DockFighterEvent, event.content)
            fighter_id = payload.get("ID")

            # Find fighter by ID and set to ready, clear ID
            for fighter in self.state.Fighters:
                if fighter.ID == fighter_id:
                    fighter.Status = "Ready"
                    fighter.ID = None
                    fighter.Pilot = None
                    break

        if isinstance(event, GameEvent) and event.content.get("event") == "FighterDestroyed":
            payload = cast(FighterDestroyedEvent, event.content)
            fighter_id = payload.get("ID")

            # Calculate rebuild completion time (80 seconds from now)
            current_time = datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
            rebuild_time = current_time + timedelta(seconds=90)
            rebuild_timestamp = rebuild_time.isoformat().replace("+00:00", "Z")

            # Find fighter by ID and set to being rebuilt
            for fighter in self.state.Fighters:
                if fighter.ID == fighter_id:
                    fighter.Status = "BeingRebuilt"
                    fighter.RebuiltAt = rebuild_timestamp
                    fighter.Pilot = None
                    break

        if isinstance(event, GameEvent) and event.content.get("event") == "FighterRebuilt":
            payload = cast(FighterRebuiltEvent, event.content)
            fighter_id = payload.get("ID")

            # Find fighter by ID and set to ready, clear ID
            for fighter in self.state.Fighters:
                if fighter.ID == fighter_id:
                    fighter.Status = "Ready"
                    fighter.ID = None
                    fighter.Pilot = None
                    fighter.RebuiltAt = None
                    break

        if isinstance(event, GameEvent) and event.content.get("event") == "VehicleSwitch":
            payload = cast(VehicleSwitchEvent, event.content)
            vehicle_to = payload.get("To", "")

            if vehicle_to == "Mothership":
                # Commander switched back to mothership, fighter becomes abandoned
                for fighter in self.state.Fighters:
                    if fighter.Pilot == "Commander" and fighter.Status == "Launched":
                        fighter.Status = "Abandoned"
                        fighter.Pilot = "No pilot"
                        break

            elif vehicle_to == "Fighter":
                # Commander switched to fighter, set fighter back to launched
                for fighter in self.state.Fighters:
                    if fighter.Status == "Abandoned" and fighter.Pilot == "No pilot":
                        fighter.Status = "Launched"
                        fighter.Pilot = "Commander"
                        break

        if self.state.Type != "Unknown":
            self.state.LandingPadSize = ship_sizes.get(self.state.Type, "Unknown")

        # Recalculate jump ranges on weight, module or modifier changes
        if isinstance(event, StatusEvent) and event.status.get("event") == "Status":
            try:
                min_jr, cur_jr, max_jr = self.calculate_jump_range()
                self.state.MinimumJumpRange = min_jr
                self.state.CurrentJumpRange = cur_jr
                self.state.MaximumJumpRange = max_jr
            except Exception as e:
                log("error", "Error calculating jump ranges:", e, traceback.format_exc())

        return projected_events

    def calculate_jump_range(self) -> tuple[float, float, float]:
        unladen_mass = self.state.UnladenMass
        cargo_capacity = self.state.CargoCapacity
        fuel_capacity = self.state.FuelMainCapacity
        maximum_jump_range = self.state.ReportedMaximumJumpRange
        drive_power_const = self.state.DrivePowerConst
        drive_optimal_mass = self.state.DriveOptimalMass
        drive_linear_const = self.state.DriveLinearConst
        drive_max_fuel = self.state.DriveMaxFuel
        fsd_star_boost = self.state.JetConeBoost
        fsd_boost = self.state.GuardianfsdBooster
        fsd_inject = self.state.FSDSynthesis

        if not (unladen_mass > 0 and fuel_capacity > 0 and maximum_jump_range > 0 and drive_max_fuel):
            return 0, 0, 0

        current_cargo = self.state.ShipCargo
        current_fuel = self.state.FuelMain
        current_fuel_reservoir = self.state.FuelReservoir

        minimal_mass = unladen_mass + drive_max_fuel
        current_mass = unladen_mass + current_cargo + current_fuel + current_fuel_reservoir
        maximal_mass = unladen_mass + cargo_capacity + fuel_capacity

        base = lambda M, F: (drive_optimal_mass / M) * ((10**3 * F) / drive_linear_const) ** (1 / drive_power_const)
        min_ly = (base(maximal_mass, drive_max_fuel) + fsd_boost) * (fsd_star_boost + fsd_inject)
        cur_ly = (base(current_mass, min(drive_max_fuel, current_fuel)) + fsd_boost) * (fsd_star_boost + fsd_inject)
        max_ly = (base(minimal_mass, drive_max_fuel) + fsd_boost) * (fsd_star_boost + fsd_inject)

        return min_ly, cur_ly, max_ly
