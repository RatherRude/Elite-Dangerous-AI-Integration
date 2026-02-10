from .EventManager import EventManager
from .EventManager import EventManager
from .SystemDatabase import SystemDatabase
from .projections.common import ProjectedStates, get_state_dict
from .projections.backpack import Backpack
from .projections.cargo import Cargo, CargoState
from .projections.colonisation_construction import ColonisationConstruction
from .projections.commander import Commander
from .projections.community_goal import CommunityGoal
from .projections.current_status import CurrentStatus, CurrentStatusState
from .projections.docking_events import DockingEvents
from .projections.engineer_progress import EngineerProgress
from .projections.event_counter import EventCounter
from .projections.loadout import Loadout
from .projections.market import Market
from .projections.module_info import ModuleInfo
from .projections.outfitting import Outfitting
from .projections.ship_locker import ShipLocker
from .projections.shipyard import Shipyard
from .projections.exobiology_scan import ExobiologyScan
from .projections.fleet_carriers import FleetCarriers
from .projections.friends import Friends
from .projections.fss_signals import FSSSignals
from .projections.idle import Idle
from .projections.in_combat import InCombat
from .projections.location import Location, LocationState
from .projections.materials import Materials
from .projections.missions import Missions, MissionsStateModel
from .projections.nav_info import NavInfo, NavInfoStateModel
from .projections.powerplay import Powerplay
from .projections.rank_progress import RankProgress
from .projections.reputation import Reputation
from .projections.ship_info import ShipInfo, ShipInfoStateModel
from .projections.squadron import Squadron
from .projections.statistics import Statistics
from .projections.stored_modules import StoredModules
from .projections.stored_ships import StoredShips
from .projections.suit_loadout import SuitLoadout
from .projections.target import Target, TargetStateModel
from .projections.wing import Wing


def registerProjections(
    event_manager: EventManager,
    system_db: SystemDatabase,
    idle_timeout: int,
):
    event_manager.register_projection(EventCounter())
    event_manager.register_projection(CurrentStatus())
    event_manager.register_projection(Location())
    event_manager.register_projection(Missions())
    event_manager.register_projection(EngineerProgress())
    event_manager.register_projection(RankProgress())
    event_manager.register_projection(CommunityGoal())
    event_manager.register_projection(Squadron())
    event_manager.register_projection(Reputation())
    event_manager.register_projection(Commander())
    event_manager.register_projection(Statistics())
    event_manager.register_projection(FleetCarriers())
    event_manager.register_projection(ShipInfo())
    event_manager.register_projection(Target())
    event_manager.register_projection(NavInfo(system_db))
    event_manager.register_projection(ExobiologyScan())
    event_manager.register_projection(Cargo())
    event_manager.register_projection(Backpack())
    event_manager.register_projection(SuitLoadout())
    event_manager.register_projection(Materials())
    event_manager.register_projection(Friends())
    event_manager.register_projection(Powerplay())
    event_manager.register_projection(ColonisationConstruction())
    event_manager.register_projection(DockingEvents())
    event_manager.register_projection(InCombat())
    event_manager.register_projection(Wing())
    event_manager.register_projection(FSSSignals())
    event_manager.register_projection(Idle(idle_timeout))
    event_manager.register_projection(StoredModules())
    event_manager.register_projection(StoredShips())

    event_manager.register_projection(ModuleInfo())
    event_manager.register_projection(ShipLocker())
    event_manager.register_projection(Loadout())
    event_manager.register_projection(Shipyard())
    event_manager.register_projection(Market())
    event_manager.register_projection(Outfitting())


# Type aliases for backward compatibility with existing imports
MissionsState = MissionsStateModel
ShipInfoState = ShipInfoStateModel
TargetState = TargetStateModel
LocationState = LocationState
CargoState = CargoState
NavInfoState = NavInfoStateModel
CurrentStatusState = CurrentStatusState
__all__ = [
    "registerProjections",
    "ProjectedStates",
    "get_state_dict",
    "MissionsState",
    "ShipInfoState",
    "TargetState",
    "LocationState",
    "CargoState",
    "NavInfoState",
    "CurrentStatusState",
]
