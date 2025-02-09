# THIS FILE IS AUTO-GENERATED
# DO NOT EDIT
# USE BuildEventModels.py TO UPDATE

from typing import TypedDict

# TODO Projection
# StoredModules: 358151524 characters, 9699 entries
class StoredModulesEvent(TypedDict):
    timestamp: str
    event: str
    MarketID: int
    StationName: str
    StarSystem: str
    Items: list

# TODO Projection
# ShipLocker: 184333691 characters, 25060 entries
class ShipLockerEvent(TypedDict):
    timestamp: str
    event: str
    Items: list
    Components: list
    Consumables: list
    Data: list

# TODO Projection
# Loadout: 64124055 characters, 5402 entries
class LoadoutEvent(TypedDict):
    timestamp: str
    event: str
    Ship: str
    ShipID: int
    ShipName: str
    ShipIdent: str
    HullValue: int
    ModulesValue: int
    HullHealth: float
    UnladenMass: float
    CargoCapacity: int
    MaxJumpRange: float
    FuelCapacity: dict
    Rebuy: int
    Modules: list

# TODO Projection
# FSSSignalDiscovered: 27828863 characters, 156267 entries
class FSSSignalDiscoveredEvent(TypedDict):
    timestamp: str
    event: str
    SystemAddress: int
    SignalName: str
    IsStation: bool


# ReceiveText: 13190349 characters, 62955 entries
class ReceiveTextEvent(TypedDict):
    timestamp: str
    event: str
    From: str
    Message: str
    Message_Localised: str
    Channel: str

# TODO Projection
# Scan: 12632340 characters, 17232 entries
class ScanEvent(TypedDict):
    timestamp: str
    event: str
    ScanType: str
    BodyName: str
    BodyID: int
    Parents: list
    StarSystem: str
    SystemAddress: int
    DistanceFromArrivalLS: float
    StarType: str
    Subclass: int
    StellarMass: float
    Radius: float
    AbsoluteMagnitude: float
    Age_MY: int
    SurfaceTemperature: float
    Luminosity: str
    SemiMajorAxis: float
    Eccentricity: float
    OrbitalInclination: float
    Periapsis: float
    OrbitalPeriod: float
    RotationPeriod: float
    AxialTilt: float
    Rings: list
    WasDiscovered: bool
    WasMapped: bool

# TODO Projection
# Materials: 12442264 characters, 1651 entries
class MaterialsEvent(TypedDict):
    timestamp: str
    event: str
    Raw: list
    Manufactured: list
    Encoded: list

# custom template added
# FSDJump: 11257065 characters, 6423 entries
class FSDJumpEvent(TypedDict):
    timestamp: str
    event: str
    StarSystem: str
    SystemAddress: int
    StarPos: list
    SystemAllegiance: str
    SystemEconomy: str
    SystemEconomy_Localised: str
    SystemSecondEconomy: str
    SystemSecondEconomy_Localised: str
    SystemGovernment: str
    SystemGovernment_Localised: str
    SystemSecurity: str
    SystemSecurity_Localised: str
    Population: int
    Body: str
    BodyID: int
    BodyType: str
    JumpDist: float
    FuelUsed: float
    FuelLevel: float

# we have projection
# ShipTargeted: 7069718 characters, 26333 entries
class ShipTargetedEvent(TypedDict):
    timestamp: str
    event: str
    TargetLocked: bool
    Ship: str
    ScanStage: int

# TODO projection?
# Statistics: 7046457 characters, 1633 entries
class StatisticsEvent(TypedDict):
    timestamp: str
    event: str
    Bank_Account: dict
    Combat: dict
    Crime: dict
    Smuggling: dict
    Trading: dict
    Mining: dict
    Exploration: dict
    Passengers: dict
    Search_And_Rescue: dict
    Crafting: dict
    Crew: dict
    Multicrew: dict
    Material_Trader_Stats: dict

# ignore
# Music: 5554889 characters, 64624 entries
class MusicEvent(TypedDict):
    timestamp: str
    event: str
    MusicTrack: str

# ignore
# Location: 5201273 characters, 1916 entries
class LocationEvent(TypedDict):
    timestamp: str
    event: str
    Docked: bool
    StationName: str
    StationType: str
    MarketID: int
    StationFaction: dict
    StationGovernment: str
    StationGovernment_Localised: str
    StationAllegiance: str
    StationServices: list
    StationEconomy: str
    StationEconomy_Localised: str
    StationEconomies: list
    StarSystem: str
    SystemAddress: int
    StarPos: list
    SystemAllegiance: str
    SystemEconomy: str
    SystemEconomy_Localised: str
    SystemSecondEconomy: str
    SystemSecondEconomy_Localised: str
    SystemGovernment: str
    SystemGovernment_Localised: str
    SystemSecurity: str
    SystemSecurity_Localised: str
    Population: int
    Body: str
    BodyID: int
    BodyType: str
    Factions: list
    SystemFaction: dict
    Conflicts: list

# custom template added
# UnderAttack: 4947327 characters, 61772 entries
class UnderAttackEvent(TypedDict):
    timestamp: str
    event: str
    Target: str

# ignore
# StoredShips: 4389295 characters, 2248 entries
class StoredShipsEvent(TypedDict):
    timestamp: str
    event: str
    StationName: str
    MarketID: int
    StarSystem: str
    ShipsHere: list
    ShipsRemote: list

# template added
# Docked: 3674298 characters, 3737 entries
class DockedEvent(TypedDict):
    timestamp: str
    event: str
    StationName: str
    StationType: str
    StarSystem: str
    SystemAddress: int
    MarketID: int
    StationFaction: dict
    StationGovernment: str
    StationGovernment_Localised: str
    StationAllegiance: str
    StationServices: list
    StationEconomy: str
    StationEconomy_Localised: str
    StationEconomies: list
    DistFromStarLS: float


# EngineerProgress: 3528712 characters, 1838 entries
class EngineerProgressEvent(TypedDict):
    timestamp: str
    event: str
    Engineers: list


# EngineerCraft: 2939181 characters, 3229 entries
class EngineerCraftEvent(TypedDict):
    timestamp: str
    event: str
    Slot: str
    Module: str
    Ingredients: list
    Engineer: str
    EngineerID: int
    BlueprintID: int
    BlueprintName: str
    Level: int
    Quality: float
    Modifiers: list


# CarrierStats: 1650480 characters, 886 entries
class CarrierStatsEvent(TypedDict):
    timestamp: str
    event: str
    CarrierID: int
    Callsign: str
    Name: str
    DockingAccess: str
    AllowNotorious: bool
    FuelLevel: int
    JumpRangeCurr: float
    JumpRangeMax: float
    PendingDecommission: bool
    SpaceUsage: dict
    Finance: dict
    Crew: list
    ShipPacks: list
    ModulePacks: list


# SuitLoadout: 1543809 characters, 1980 entries
class SuitLoadoutEvent(TypedDict):
    timestamp: str
    event: str
    SuitID: int
    SuitName: str
    SuitName_Localised: str
    SuitMods: list
    LoadoutID: int
    LoadoutName: str
    Modules: list


# MaterialCollected: 1424830 characters, 8433 entries
class MaterialCollectedEvent(TypedDict):
    timestamp: str
    event: str
    Category: str
    Name: str
    Count: int


# StartJump: 1305862 characters, 8772 entries
class StartJumpEvent(TypedDict):
    timestamp: str
    event: str
    JumpType: str
    StarSystem: str
    SystemAddress: int
    StarClass: str


# NpcCrewPaidWage: 1187865 characters, 8613 entries
class NpcCrewPaidWageEvent(TypedDict):
    timestamp: str
    event: str
    NpcCrewName: str
    NpcCrewId: int
    Amount: int


# FSDTarget: 1176298 characters, 7229 entries
class FSDTargetEvent(TypedDict):
    timestamp: str
    event: str
    Name: str
    SystemAddress: int
    StarClass: str
    RemainingJumpsInRoute: int


# BackpackChange: 1132837 characters, 6254 entries
class BackpackChangeEvent(TypedDict):
    timestamp: str
    event: str
    Removed: list


# MissionCompleted: 1057076 characters, 1482 entries
class MissionCompletedEvent(TypedDict):
    timestamp: str
    event: str
    Faction: str
    Name: str
    MissionID: int
    Donation: str
    Donated: int
    FactionEffects: list


# ModuleRetrieve: 1015383 characters, 2824 entries
class ModuleRetrieveEvent(TypedDict):
    timestamp: str
    event: str
    MarketID: int
    Slot: str
    RetrievedItem: str
    RetrievedItem_Localised: str
    Ship: str
    ShipID: int
    Hot: bool
    SwapOutItem: str
    SwapOutItem_Localised: str


# CollectItems: 964319 characters, 5415 entries
class CollectItemsEvent(TypedDict):
    timestamp: str
    event: str
    Name: str
    Name_Localised: str
    Type: str
    OwnerID: int
    Count: int
    Stolen: bool


# SupercruiseExit: 927824 characters, 4460 entries
class SupercruiseExitEvent(TypedDict):
    timestamp: str
    event: str
    StarSystem: str
    SystemAddress: int
    Body: str
    BodyID: int
    BodyType: str


# Cargo: 798931 characters, 8083 entries
class CargoEvent(TypedDict):
    timestamp: str
    event: str
    Vessel: str
    Count: int
    Inventory: list


# FactionKillBond: 701770 characters, 3783 entries
class FactionKillBondEvent(TypedDict):
    timestamp: str
    event: str
    Reward: int
    AwardingFaction: str
    VictimFaction: str


# MissionAccepted: 694708 characters, 1584 entries
class MissionAcceptedEvent(TypedDict):
    timestamp: str
    event: str
    Faction: str
    Name: str
    LocalisedName: str
    Donation: str
    Expiry: str
    Wing: bool
    Influence: str
    Reputation: str
    MissionID: int


# ApproachSettlement: 689742 characters, 2096 entries
class ApproachSettlementEvent(TypedDict):
    timestamp: str
    event: str
    Name: str
    MarketID: int
    SystemAddress: int
    BodyID: int
    BodyName: str
    Latitude: float
    Longitude: float


# LoadGame: 675166 characters, 1655 entries
class LoadGameEvent(TypedDict):
    timestamp: str
    event: str
    FID: str
    Commander: str
    Horizons: bool
    Ship: str
    Ship_Localised: str
    ShipID: int
    ShipName: str
    ShipIdent: str
    FuelLevel: float
    FuelCapacity: float
    GameMode: str
    Group: str
    Credits: int
    Loan: int


# ModuleBuy: 611726 characters, 1927 entries
class ModuleBuyEvent(TypedDict):
    timestamp: str
    event: str
    Slot: str
    BuyItem: str
    BuyItem_Localised: str
    MarketID: int
    BuyPrice: int
    Ship: str
    ShipID: int


# Backpack: 596280 characters, 1867 entries
class BackpackEvent(TypedDict):
    timestamp: str
    event: str
    Items: list
    Components: list
    Consumables: list
    Data: list


# DockingRequested: 580811 characters, 3096 entries
class DockingRequestedEvent(TypedDict):
    timestamp: str
    event: str
    MarketID: int
    StationName: str
    StationType: str


# Undocked: 534879 characters, 3185 entries
class UndockedEvent(TypedDict):
    timestamp: str
    event: str
    StationName: str
    StationType: str
    MarketID: int


# FetchRemoteModule: 530291 characters, 1819 entries
class FetchRemoteModuleEvent(TypedDict):
    timestamp: str
    event: str
    StorageSlot: int
    StoredItem: str
    StoredItem_Localised: str
    ServerId: int
    TransferCost: int
    TransferTime: int
    Ship: str
    ShipID: int


# Outfitting: 493378 characters, 3433 entries
class OutfittingEvent(TypedDict):
    timestamp: str
    event: str
    MarketID: int
    StationName: str
    StarSystem: str


# DockingGranted: 462524 characters, 2751 entries
class DockingGrantedEvent(TypedDict):
    timestamp: str
    event: str
    LandingPad: int
    MarketID: int
    StationName: str
    StationType: str


# SupercruiseEntry: 455391 characters, 3057 entries
class SupercruiseEntryEvent(TypedDict):
    timestamp: str
    event: str
    StarSystem: str
    SystemAddress: int


# Embark: 444749 characters, 1523 entries
class EmbarkEvent(TypedDict):
    timestamp: str
    event: str
    SRV: bool
    Taxi: bool
    Multicrew: bool
    StarSystem: str
    SystemAddress: int
    Body: str
    BodyID: int
    OnStation: bool
    OnPlanet: bool
    StationName: str
    StationType: str
    MarketID: int


# Disembark: 438499 characters, 1523 entries
class DisembarkEvent(TypedDict):
    timestamp: str
    event: str
    SRV: bool
    Taxi: bool
    Multicrew: bool
    ID: int
    StarSystem: str
    SystemAddress: int
    Body: str
    BodyID: int
    OnStation: bool
    OnPlanet: bool
    StationName: str
    StationType: str
    MarketID: int


# LaunchDrone: 411542 characters, 4849 entries
class LaunchDroneEvent(TypedDict):
    timestamp: str
    event: str
    Type: str


# FuelScoop: 409906 characters, 4056 entries
class FuelScoopEvent(TypedDict):
    timestamp: str
    event: str
    Scooped: float
    Total: float


# Powerplay: 381865 characters, 2611 entries
class PowerplayEvent(TypedDict):
    timestamp: str
    event: str
    Power: str
    Rank: int
    Merits: int
    Votes: int
    TimePledged: int


# ProspectedAsteroid: 337333 characters, 880 entries
class ProspectedAsteroidEvent(TypedDict):
    timestamp: str
    event: str
    Materials: list
    Content: str
    Content_Localised: str
    Remaining: float


# Shipyard: 304535 characters, 2151 entries
class ShipyardEvent(TypedDict):
    timestamp: str
    event: str
    MarketID: int
    StationName: str
    StarSystem: str


# Missions: 284744 characters, 1913 entries
class MissionsEvent(TypedDict):
    timestamp: str
    event: str
    Active: list
    Failed: list
    Complete: list


# Progress: 277480 characters, 1656 entries
class ProgressEvent(TypedDict):
    timestamp: str
    event: str
    Combat: int
    Trade: int
    Explore: int
    Empire: int
    Federation: int
    CQC: int


# Bounty: 273679 characters, 1017 entries
class BountyEvent(TypedDict):
    timestamp: str
    event: str
    Rewards: list
    Target: str
    TotalReward: int
    VictimFaction: str


# ShieldState: 272210 characters, 3300 entries
class ShieldStateEvent(TypedDict):
    timestamp: str
    event: str
    ShieldsUp: bool


# CollectCargo: 268340 characters, 1841 entries
class CollectCargoEvent(TypedDict):
    timestamp: str
    event: str
    Type: str
    Type_Localised: str
    Stolen: bool


# CommitCrime: 266229 characters, 1567 entries
class CommitCrimeEvent(TypedDict):
    timestamp: str
    event: str
    CrimeType: str
    Faction: str
    Victim: str
    Victim_Localised: str
    Bounty: int


# Rank: 262443 characters, 1656 entries
class RankEvent(TypedDict):
    timestamp: str
    event: str
    Combat: int
    Trade: int
    Explore: int
    Empire: int
    Federation: int
    CQC: int


# MassModuleStore: 248803 characters, 197 entries
class MassModuleStoreEvent(TypedDict):
    timestamp: str
    event: str
    MarketID: int
    Ship: str
    ShipID: int
    Items: list


# ScanBaryCentre: 241861 characters, 686 entries
class ScanBaryCentreEvent(TypedDict):
    timestamp: str
    event: str
    StarSystem: str
    SystemAddress: int
    BodyID: int
    SemiMajorAxis: float
    Eccentricity: float
    OrbitalInclination: float
    Periapsis: float
    OrbitalPeriod: float
    AscendingNode: float
    MeanAnomaly: float


# ReservoirReplenished: 237356 characters, 2041 entries
class ReservoirReplenishedEvent(TypedDict):
    timestamp: str
    event: str
    FuelMain: float
    FuelReservoir: float


# CommunityGoal: 227106 characters, 453 entries
class CommunityGoalEvent(TypedDict):
    timestamp: str
    event: str
    CurrentGoals: list


# FSSDiscoveryScan: 226434 characters, 1185 entries
class FSSDiscoveryScanEvent(TypedDict):
    timestamp: str
    event: str
    Progress: float
    BodyCount: int
    NonBodyCount: int
    SystemName: str
    SystemAddress: int


# MaterialTrade: 225550 characters, 634 entries
class MaterialTradeEvent(TypedDict):
    timestamp: str
    event: str
    MarketID: int
    TraderType: str
    Paid: dict
    Received: dict


# ModuleStore: 219723 characters, 745 entries
class ModuleStoreEvent(TypedDict):
    timestamp: str
    event: str
    MarketID: int
    Slot: str
    StoredItem: str
    StoredItem_Localised: str
    Ship: str
    ShipID: int
    Hot: bool


# Reputation: 215504 characters, 1656 entries
class ReputationEvent(TypedDict):
    timestamp: str
    event: str
    Empire: float
    Federation: float


# SendText: 197492 characters, 1348 entries
class SendTextEvent(TypedDict):
    timestamp: str
    event: str
    To: str
    Message: str
    Sent: bool


# ShipyardSwap: 195192 characters, 983 entries
class ShipyardSwapEvent(TypedDict):
    timestamp: str
    event: str
    ShipType: str
    ShipType_Localised: str
    ShipID: int
    StoreOldShip: str
    StoreShipID: int
    MarketID: int


# Touchdown: 194013 characters, 589 entries
class TouchdownEvent(TypedDict):
    timestamp: str
    event: str
    PlayerControlled: bool
    Latitude: float
    Longitude: float
    NearestDestination: str


# Fileheader: 188794 characters, 1109 entries
class FileheaderEvent(TypedDict):
    timestamp: str
    event: str
    part: int
    language: str
    gameversion: str
    build: str


# RefuelAll: 187964 characters, 2009 entries
class RefuelAllEvent(TypedDict):
    timestamp: str
    event: str
    Cost: int
    Amount: float


# Scanned: 177036 characters, 2213 entries
class ScannedEvent(TypedDict):
    timestamp: str
    event: str
    ScanType: str


# ModuleSellRemote: 175316 characters, 682 entries
class ModuleSellRemoteEvent(TypedDict):
    timestamp: str
    event: str
    StorageSlot: int
    SellItem: str
    SellItem_Localised: str
    ServerId: int
    SellPrice: int
    Ship: str
    ShipID: int


# Commander: 174956 characters, 1655 entries
class CommanderEvent(TypedDict):
    timestamp: str
    event: str
    FID: str
    Name: str


# Liftoff: 170018 characters, 498 entries
class LiftoffEvent(TypedDict):
    timestamp: str
    event: str
    PlayerControlled: bool
    NearestDestination: str


# CodexEntry: 166213 characters, 300 entries
class CodexEntryEvent(TypedDict):
    timestamp: str
    event: str
    EntryID: int
    Name: str
    Name_Localised: str
    SubCategory: str
    SubCategory_Localised: str
    Category: str
    Category_Localised: str
    Region: str
    Region_Localised: str
    System: str
    SystemAddress: int
    IsNewEntry: bool


# SwitchSuitLoadout: 165785 characters, 212 entries
class SwitchSuitLoadoutEvent(TypedDict):
    timestamp: str
    event: str
    SuitID: int
    SuitName: str
    SuitName_Localised: str
    SuitMods: list
    LoadoutID: int
    LoadoutName: str
    Modules: list


# HullDamage: 165229 characters, 1397 entries
class HullDamageEvent(TypedDict):
    timestamp: str
    event: str
    Health: float
    PlayerPilot: bool
    Fighter: bool


# ModuleInfo: 161758 characters, 2609 entries
class ModuleInfoEvent(TypedDict):
    timestamp: str
    event: str


# ApproachBody: 161140 characters, 1008 entries
class ApproachBodyEvent(TypedDict):
    timestamp: str
    event: str
    StarSystem: str
    SystemAddress: int
    Body: str
    BodyID: int


# CarrierJump: 156954 characters, 67 entries
class CarrierJumpEvent(TypedDict):
    timestamp: str
    event: str
    Docked: bool
    StationName: str
    StationType: str
    MarketID: int
    StationFaction: dict
    StationGovernment: str
    StationGovernment_Localised: str
    StationServices: list
    StationEconomy: str
    StationEconomy_Localised: str
    StationEconomies: list
    StarSystem: str
    SystemAddress: int
    StarPos: list
    SystemAllegiance: str
    SystemEconomy: str
    SystemEconomy_Localised: str
    SystemSecondEconomy: str
    SystemSecondEconomy_Localised: str
    SystemGovernment: str
    SystemGovernment_Localised: str
    SystemSecurity: str
    SystemSecurity_Localised: str
    Population: int
    Body: str
    BodyID: int
    BodyType: str
    Powers: list
    PowerplayState: str
    Factions: list
    SystemFaction: dict
    Conflicts: list


# NavRoute: 147660 characters, 2461 entries
class NavRouteEvent(TypedDict):
    timestamp: str
    event: str


# SAASignalsFound: 138424 characters, 438 entries
class SAASignalsFoundEvent(TypedDict):
    timestamp: str
    event: str
    BodyName: str
    SystemAddress: int
    BodyID: int
    Signals: list


# MissionRedirected: 136752 characters, 457 entries
class MissionRedirectedEvent(TypedDict):
    timestamp: str
    event: str
    MissionID: int
    Name: str
    NewDestinationStation: str
    NewDestinationSystem: str
    OldDestinationStation: str
    OldDestinationSystem: str


# ShipLockerMaterials: 130671 characters, 43 entries
class ShipLockerMaterialsEvent(TypedDict):
    timestamp: str
    event: str
    Items: list
    Components: list
    Consumables: list
    Data: list


# SupercruiseDestinationDrop: 120677 characters, 805 entries
class SupercruiseDestinationDropEvent(TypedDict):
    timestamp: str
    event: str
    Type: str
    Threat: int


# MiningRefined: 116913 characters, 915 entries
class MiningRefinedEvent(TypedDict):
    timestamp: str
    event: str
    Type: str
    Type_Localised: str


# MultiSellExplorationData: 115193 characters, 66 entries
class MultiSellExplorationDataEvent(TypedDict):
    timestamp: str
    event: str
    Discovered: list
    BaseValue: int
    Bonus: int
    TotalEarnings: int


# EjectCargo: 113708 characters, 804 entries
class EjectCargoEvent(TypedDict):
    timestamp: str
    event: str
    Type: str
    Type_Localised: str
    Count: int
    Abandoned: bool


# DockingDenied: 108701 characters, 623 entries
class DockingDeniedEvent(TypedDict):
    timestamp: str
    event: str
    Reason: str
    MarketID: int
    StationName: str
    StationType: str


# ShipyardTransfer: 107147 characters, 391 entries
class ShipyardTransferEvent(TypedDict):
    timestamp: str
    event: str
    ShipType: str
    ShipType_Localised: str
    ShipID: int
    System: str
    ShipMarketID: int
    Distance: float
    TransferPrice: int
    TransferTime: int
    MarketID: int


# ModuleSell: 106979 characters, 419 entries
class ModuleSellEvent(TypedDict):
    timestamp: str
    event: str
    MarketID: int
    Slot: str
    SellItem: str
    SellItem_Localised: str
    SellPrice: int
    Ship: str
    ShipID: int


# Friends: 100677 characters, 987 entries
class FriendsEvent(TypedDict):
    timestamp: str
    event: str
    Status: str
    Name: str


# FSSAllBodiesFound: 99067 characters, 660 entries
class FSSAllBodiesFoundEvent(TypedDict):
    timestamp: str
    event: str
    SystemName: str
    SystemAddress: int
    Count: int


# LeaveBody: 92115 characters, 586 entries
class LeaveBodyEvent(TypedDict):
    timestamp: str
    event: str
    StarSystem: str
    SystemAddress: int
    Body: str
    BodyID: int


# TransferMicroResources: 89226 characters, 96 entries
class TransferMicroResourcesEvent(TypedDict):
    timestamp: str
    event: str
    Transfers: list


# HeatWarning: 82656 characters, 1312 entries
class HeatWarningEvent(TypedDict):
    timestamp: str
    event: str


# Market: 81331 characters, 449 entries
class MarketEvent(TypedDict):
    timestamp: str
    event: str
    MarketID: int
    StationName: str
    StationType: str
    StarSystem: str


# ModuleSwap: 77556 characters, 232 entries
class ModuleSwapEvent(TypedDict):
    timestamp: str
    event: str
    MarketID: int
    FromSlot: str
    ToSlot: str
    FromItem: str
    FromItem_Localised: str
    ToItem: str
    ToItem_Localised: str
    Ship: str
    ShipID: int


# UseConsumable: 71471 characters, 508 entries
class UseConsumableEvent(TypedDict):
    timestamp: str
    event: str
    Name: str
    Name_Localised: str
    Type: str


# SquadronStartup: 71043 characters, 597 entries
class SquadronStartupEvent(TypedDict):
    timestamp: str
    event: str
    SquadronName: str
    CurrentRank: int


# NavRouteClear: 68705 characters, 1057 entries
class NavRouteClearEvent(TypedDict):
    timestamp: str
    event: str


# BookTaxi: 56878 characters, 380 entries
class BookTaxiEvent(TypedDict):
    timestamp: str
    event: str
    Cost: int
    DestinationSystem: str
    DestinationLocation: str


# RestockVehicle: 55648 characters, 359 entries
class RestockVehicleEvent(TypedDict):
    timestamp: str
    event: str
    Type: str
    Loadout: str
    Cost: int
    Count: int


# RepairAll: 52308 characters, 694 entries
class RepairAllEvent(TypedDict):
    timestamp: str
    event: str
    Cost: int


# DatalinkScan: 51706 characters, 251 entries
class DatalinkScanEvent(TypedDict):
    timestamp: str
    event: str
    Message: str
    Message_Localised: str


# BuyAmmo: 50677 characters, 697 entries
class BuyAmmoEvent(TypedDict):
    timestamp: str
    event: str
    Cost: int


# Shutdown: 49440 characters, 824 entries
class ShutdownEvent(TypedDict):
    timestamp: str
    event: str


# USSDrop: 47983 characters, 302 entries
class USSDropEvent(TypedDict):
    timestamp: str
    event: str
    USSType: str
    USSType_Localised: str
    USSThreat: int


# LaunchSRV: 47725 characters, 290 entries
class LaunchSRVEvent(TypedDict):
    timestamp: str
    event: str
    Loadout: str
    ID: int
    PlayerControlled: bool


# MaterialDiscovered: 46510 characters, 258 entries
class MaterialDiscoveredEvent(TypedDict):
    timestamp: str
    event: str
    Category: str
    Name: str
    DiscoveryNumber: int


# LaunchFighter: 43314 characters, 361 entries
class LaunchFighterEvent(TypedDict):
    timestamp: str
    event: str
    Loadout: str
    ID: int
    PlayerControlled: bool


# WingAdd: 42144 characters, 508 entries
class WingAddEvent(TypedDict):
    timestamp: str
    event: str
    Name: str


# Interdicted: 41349 characters, 258 entries
class InterdictedEvent(TypedDict):
    timestamp: str
    event: str
    Submitted: bool
    Interdictor: str
    IsPlayer: bool
    Faction: str


# LoadoutEquipModule: 39134 characters, 93 entries
class LoadoutEquipModuleEvent(TypedDict):
    timestamp: str
    event: str
    LoadoutName: str
    SuitID: int
    SuitName: str
    SuitName_Localised: str
    LoadoutID: int
    SlotName: str
    ModuleName: str
    ModuleName_Localised: str
    Class: int
    WeaponMods: list
    SuitModuleID: int


# CarrierJumpRequest: 37822 characters, 195 entries
class CarrierJumpRequestEvent(TypedDict):
    timestamp: str
    event: str
    CarrierID: int
    SystemName: str
    Body: str
    SystemAddress: int
    BodyID: int


# Synthesis: 34899 characters, 149 entries
class SynthesisEvent(TypedDict):
    timestamp: str
    event: str
    Name: str
    Materials: list


# BuyDrones: 34049 characters, 267 entries
class BuyDronesEvent(TypedDict):
    timestamp: str
    event: str
    Type: str
    Count: int
    BuyPrice: int
    TotalCost: int


# MarketSell: 33897 characters, 175 entries
class MarketSellEvent(TypedDict):
    timestamp: str
    event: str
    MarketID: int
    Type: str
    Type_Localised: str
    Count: int
    SellPrice: int
    TotalSale: int
    AvgPricePaid: int


# RedeemVoucher: 31655 characters, 207 entries
class RedeemVoucherEvent(TypedDict):
    timestamp: str
    event: str
    Type: str
    Amount: int
    Faction: str
    BrokerPercentage: float


# MarketBuy: 30994 characters, 174 entries
class MarketBuyEvent(TypedDict):
    timestamp: str
    event: str
    MarketID: int
    Type: str
    Type_Localised: str
    Count: int
    BuyPrice: int
    TotalCost: int


# ScanOrganic: 30430 characters, 85 entries
class ScanOrganicEvent(TypedDict):
    timestamp: str
    event: str
    ScanType: str
    Genus: str
    Genus_Localised: str
    Species: str
    Species_Localised: str
    SystemAddress: int
    Body: int


# CarrierTradeOrder: 28296 characters, 135 entries
class CarrierTradeOrderEvent(TypedDict):
    timestamp: str
    event: str
    CarrierID: int
    BlackMarket: bool
    Commodity: str
    PurchaseOrder: int
    Price: int


# DockSRV: 25888 characters, 230 entries
class DockSRVEvent(TypedDict):
    timestamp: str
    event: str
    ID: int


# DropshipDeploy: 24657 characters, 123 entries
class DropshipDeployEvent(TypedDict):
    timestamp: str
    event: str
    StarSystem: str
    SystemAddress: int
    Body: str
    BodyID: int
    OnStation: bool
    OnPlanet: bool


# SAAScanComplete: 24635 characters, 133 entries
class SAAScanCompleteEvent(TypedDict):
    timestamp: str
    event: str
    BodyName: str
    SystemAddress: int
    BodyID: int
    ProbesUsed: int
    EfficiencyTarget: int


# WingJoin: 24613 characters, 307 entries
class WingJoinEvent(TypedDict):
    timestamp: str
    event: str
    Others: list


# TechnologyBroker: 23696 characters, 26 entries
class TechnologyBrokerEvent(TypedDict):
    timestamp: str
    event: str
    BrokerType: str
    MarketID: int
    ItemsUnlocked: list
    Commodities: list
    Materials: list


# NavBeaconScan: 22232 characters, 196 entries
class NavBeaconScanEvent(TypedDict):
    timestamp: str
    event: str
    SystemAddress: int
    NumBodies: int


# CrimeVictim: 22036 characters, 168 entries
class CrimeVictimEvent(TypedDict):
    timestamp: str
    event: str
    Offender: str
    CrimeType: str
    Bounty: int


# CrewMemberRoleChange: 20789 characters, 180 entries
class CrewMemberRoleChangeEvent(TypedDict):
    timestamp: str
    event: str
    Crew: str
    Role: str


# TradeMicroResources: 20135 characters, 33 entries
class TradeMicroResourcesEvent(TypedDict):
    timestamp: str
    event: str
    Offered: list
    TotalCount: int
    Received: str
    Received_Localised: str
    Count: int
    Category: str
    MarketID: int


# VehicleSwitch: 19224 characters, 237 entries
class VehicleSwitchEvent(TypedDict):
    timestamp: str
    event: str
    To: str


# CreateSuitLoadout: 19133 characters, 26 entries
class CreateSuitLoadoutEvent(TypedDict):
    timestamp: str
    event: str
    SuitID: int
    SuitName: str
    SuitName_Localised: str
    SuitMods: list
    LoadoutID: int
    LoadoutName: str
    Modules: list


# ModuleBuyAndStore: 18998 characters, 77 entries
class ModuleBuyAndStoreEvent(TypedDict):
    timestamp: str
    event: str
    BuyItem: str
    BuyItem_Localised: str
    MarketID: int
    BuyPrice: int
    Ship: str
    ShipID: int


# FighterDestroyed: 18899 characters, 242 entries
class FighterDestroyedEvent(TypedDict):
    timestamp: str
    event: str
    ID: int


# Resurrect: 17898 characters, 156 entries
class ResurrectEvent(TypedDict):
    timestamp: str
    event: str
    Option: str
    Cost: int
    Bankrupt: bool


# WingLeave: 17568 characters, 288 entries
class WingLeaveEvent(TypedDict):
    timestamp: str
    event: str


# FighterRebuilt: 17557 characters, 186 entries
class FighterRebuiltEvent(TypedDict):
    timestamp: str
    event: str
    Loadout: str
    ID: int


# Died: 16176 characters, 142 entries
class DiedEvent(TypedDict):
    timestamp: str
    event: str


# CrewLaunchFighter: 15495 characters, 146 entries
class CrewLaunchFighterEvent(TypedDict):
    timestamp: str
    event: str
    Crew: str


# Repair: 15413 characters, 125 entries
class RepairEvent(TypedDict):
    timestamp: str
    event: str
    Item: str
    Cost: int


# CarrierCrewServices: 15353 characters, 89 entries
class CarrierCrewServicesEvent(TypedDict):
    timestamp: str
    event: str
    CarrierID: int
    CrewRole: str
    Operation: str
    CrewName: str


# ShipyardBuy: 14649 characters, 72 entries
class ShipyardBuyEvent(TypedDict):
    timestamp: str
    event: str
    ShipType: str
    ShipType_Localised: str
    ShipPrice: int
    StoreOldShip: str
    StoreShipID: int
    MarketID: int


# Screenshot: 14596 characters, 74 entries
class ScreenshotEvent(TypedDict):
    timestamp: str
    event: str
    Filename: str
    Width: int
    Height: int
    System: str
    Body: str


# RepairDrone: 13475 characters, 141 entries
class RepairDroneEvent(TypedDict):
    timestamp: str
    event: str
    HullRepaired: float
    CorrosionRepaired: float


# CargoDepot: 13305 characters, 42 entries
class CargoDepotEvent(TypedDict):
    timestamp: str
    event: str
    MissionID: int
    UpdateType: str
    CargoType: str
    Count: int
    StartMarketID: int
    EndMarketID: int
    ItemsCollected: int
    ItemsDelivered: int
    TotalItemsToDeliver: int
    Progress: float


# HeatDamage: 12586 characters, 203 entries
class HeatDamageEvent(TypedDict):
    timestamp: str
    event: str


# DataScanned: 12070 characters, 104 entries
class DataScannedEvent(TypedDict):
    timestamp: str
    event: str
    Type: str
    Type_Localised: str


# BookDropship: 11712 characters, 73 entries
class BookDropshipEvent(TypedDict):
    timestamp: str
    event: str
    Cost: int
    DestinationSystem: str
    DestinationLocation: str


# RebootRepair: 11596 characters, 106 entries
class RebootRepairEvent(TypedDict):
    timestamp: str
    event: str
    Modules: list


# CrewAssign: 11545 characters, 91 entries
class CrewAssignEvent(TypedDict):
    timestamp: str
    event: str
    Name: str
    CrewID: int
    Role: str


# BuyWeapon: 10665 characters, 50 entries
class BuyWeaponEvent(TypedDict):
    timestamp: str
    event: str
    Name: str
    Name_Localised: str
    Class: int
    Price: int
    SuitModuleID: int
    WeaponMods: list


# SearchAndRescue: 10533 characters, 57 entries
class SearchAndRescueEvent(TypedDict):
    timestamp: str
    event: str
    MarketID: int
    Name: str
    Name_Localised: str
    Count: int
    Reward: int


# PayFines: 10318 characters, 76 entries
class PayFinesEvent(TypedDict):
    timestamp: str
    event: str
    Amount: int
    AllFines: bool
    ShipID: int


# SetUserShipName: 9488 characters, 60 entries
class SetUserShipNameEvent(TypedDict):
    timestamp: str
    event: str
    Ship: str
    ShipID: int
    UserShipName: str
    UserShipId: str


# SellMicroResources: 9387 characters, 23 entries
class SellMicroResourcesEvent(TypedDict):
    timestamp: str
    event: str
    TotalCount: int
    MicroResources: list
    Price: int
    MarketID: int


# ShipyardSell: 9383 characters, 47 entries
class ShipyardSellEvent(TypedDict):
    timestamp: str
    event: str
    ShipType: str
    ShipType_Localised: str
    SellShipID: int
    ShipPrice: int
    MarketID: int


# DropItems: 9284 characters, 56 entries
class DropItemsEvent(TypedDict):
    timestamp: str
    event: str
    Name: str
    Name_Localised: str
    Type: str
    OwnerID: int
    Count: int


# DockFighter: 8984 characters, 123 entries
class DockFighterEvent(TypedDict):
    timestamp: str
    event: str
    ID: int


# ShipyardNew: 8980 characters, 71 entries
class ShipyardNewEvent(TypedDict):
    timestamp: str
    event: str
    ShipType: str
    ShipType_Localised: str
    NewShipID: int


# SystemsShutdown: 8442 characters, 126 entries
class SystemsShutdownEvent(TypedDict):
    timestamp: str
    event: str


# EscapeInterdiction: 8293 characters, 66 entries
class EscapeInterdictionEvent(TypedDict):
    timestamp: str
    event: str
    Interdictor: str
    IsPlayer: bool


# MissionFailed: 8079 characters, 56 entries
class MissionFailedEvent(TypedDict):
    timestamp: str
    event: str
    Name: str
    MissionID: int


# BuyMicroResources: 7838 characters, 38 entries
class BuyMicroResourcesEvent(TypedDict):
    timestamp: str
    event: str
    Name: str
    Name_Localised: str
    Category: str
    Count: int
    Price: int
    MarketID: int


# BackPack: 6780 characters, 113 entries
class BackPackEvent(TypedDict):
    timestamp: str
    event: str


# DockingCancelled: 6423 characters, 41 entries
class DockingCancelledEvent(TypedDict):
    timestamp: str
    event: str
    MarketID: int
    StationName: str
    StationType: str


# EngineerContribution: 6334 characters, 27 entries
class EngineerContributionEvent(TypedDict):
    timestamp: str
    event: str
    Engineer: str
    EngineerID: int
    Type: str
    Commodity: str
    Commodity_Localised: str
    Quantity: int
    TotalQuantity: int


# SRVDestroyed: 6171 characters, 48 entries
class SRVDestroyedEvent(TypedDict):
    timestamp: str
    event: str
    ID: int


# Passengers: 6144 characters, 11 entries
class PassengersEvent(TypedDict):
    timestamp: str
    event: str
    Manifest: list


# MissionAbandoned: 5297 characters, 34 entries
class MissionAbandonedEvent(TypedDict):
    timestamp: str
    event: str
    Name: str
    MissionID: int


# PayBounties: 5099 characters, 30 entries
class PayBountiesEvent(TypedDict):
    timestamp: str
    event: str
    Amount: int
    Faction: str
    Faction_Localised: str
    ShipID: int
    BrokerPercentage: float


# SellWeapon: 4516 characters, 21 entries
class SellWeaponEvent(TypedDict):
    timestamp: str
    event: str
    Name: str
    Name_Localised: str
    Class: int
    WeaponMods: list
    Price: int
    SuitModuleID: int


# SellExplorationData: 4419 characters, 25 entries
class SellExplorationDataEvent(TypedDict):
    timestamp: str
    event: str
    Systems: list
    Discovered: list
    BaseValue: int
    Bonus: int
    TotalEarnings: int


# BuySuit: 4390 characters, 22 entries
class BuySuitEvent(TypedDict):
    timestamp: str
    event: str
    Name: str
    Name_Localised: str
    Price: int
    SuitID: int
    SuitMods: list


# WingInvite: 4352 characters, 51 entries
class WingInviteEvent(TypedDict):
    timestamp: str
    event: str
    Name: str


# Promotion: 4147 characters, 55 entries
class PromotionEvent(TypedDict):
    timestamp: str
    event: str
    Combat: int


# CarrierModulePack: 3645 characters, 20 entries
class CarrierModulePackEvent(TypedDict):
    timestamp: str
    event: str
    CarrierID: int
    Operation: str
    PackTheme: str
    PackTier: int
    Cost: int


# CrewHire: 3509 characters, 20 entries
class CrewHireEvent(TypedDict):
    timestamp: str
    event: str
    Name: str
    CrewID: int
    Faction: str
    Cost: int
    CombatRank: int


# EndCrewSession: 3500 characters, 38 entries
class EndCrewSessionEvent(TypedDict):
    timestamp: str
    event: str
    OnCrime: bool


# UpgradeWeapon: 3020 characters, 8 entries
class UpgradeWeaponEvent(TypedDict):
    timestamp: str
    event: str
    Name: str
    Name_Localised: str
    Class: int
    SuitModuleID: int
    Cost: int


# CrewMemberJoins: 2993 characters, 32 entries
class CrewMemberJoinsEvent(TypedDict):
    timestamp: str
    event: str
    Crew: str


# CarrierFinance: 2940 characters, 14 entries
class CarrierFinanceEvent(TypedDict):
    timestamp: str
    event: str
    CarrierID: int
    TaxRate: int
    CarrierBalance: int
    ReserveBalance: int
    AvailableBalance: int
    ReservePercent: int


# UpgradeSuit: 2899 characters, 5 entries
class UpgradeSuitEvent(TypedDict):
    timestamp: str
    event: str
    Name: str
    Name_Localised: str
    SuitID: int
    Class: int
    Cost: int
    Resources: list


# CarrierJumpCancelled: 2813 characters, 29 entries
class CarrierJumpCancelledEvent(TypedDict):
    timestamp: str
    event: str
    CarrierID: int


# CancelTaxi: 2781 characters, 36 entries
class CancelTaxiEvent(TypedDict):
    timestamp: str
    event: str
    Refund: int


# CarrierDepositFuel: 2723 characters, 22 entries
class CarrierDepositFuelEvent(TypedDict):
    timestamp: str
    event: str
    CarrierID: int
    Amount: int
    Total: int


# SellDrones: 2712 characters, 21 entries
class SellDronesEvent(TypedDict):
    timestamp: str
    event: str
    Type: str
    Count: int
    SellPrice: int
    TotalSale: int


# CrewMemberQuits: 2559 characters, 28 entries
class CrewMemberQuitsEvent(TypedDict):
    timestamp: str
    event: str
    Crew: str


# NpcCrewRank: 2318 characters, 17 entries
class NpcCrewRankEvent(TypedDict):
    timestamp: str
    event: str
    NpcCrewName: str
    NpcCrewId: int
    RankCombat: int


# DeleteSuitLoadout: 2302 characters, 10 entries
class DeleteSuitLoadoutEvent(TypedDict):
    timestamp: str
    event: str
    SuitID: int
    SuitName: str
    SuitName_Localised: str
    LoadoutID: int
    LoadoutName: str


# SellSuit: 2090 characters, 11 entries
class SellSuitEvent(TypedDict):
    timestamp: str
    event: str
    SuitID: int
    SuitMods: list
    Name: str
    Name_Localised: str
    Price: int


# DatalinkVoucher: 1954 characters, 14 entries
class DatalinkVoucherEvent(TypedDict):
    timestamp: str
    event: str
    Reward: int
    VictimFaction: str
    PayeeFaction: str


# CrewFire: 1905 characters, 18 entries
class CrewFireEvent(TypedDict):
    timestamp: str
    event: str
    Name: str
    CrewID: int


# RenameSuitLoadout: 1631 characters, 7 entries
class RenameSuitLoadoutEvent(TypedDict):
    timestamp: str
    event: str
    SuitID: int
    SuitName: str
    SuitName_Localised: str
    LoadoutID: int
    LoadoutName: str


# CarrierDockingPermission: 1520 characters, 10 entries
class CarrierDockingPermissionEvent(TypedDict):
    timestamp: str
    event: str
    CarrierID: int
    DockingAccess: str
    AllowNotorious: bool


# AfmuRepairs: 1486 characters, 8 entries
class AfmuRepairsEvent(TypedDict):
    timestamp: str
    event: str
    Module: str
    Module_Localised: str
    FullyRepaired: bool
    Health: float


# CockpitBreached: 1474 characters, 22 entries
class CockpitBreachedEvent(TypedDict):
    timestamp: str
    event: str


# CarrierBankTransfer: 1412 characters, 8 entries
class CarrierBankTransferEvent(TypedDict):
    timestamp: str
    event: str
    CarrierID: int
    Deposit: int
    PlayerBalance: int
    CarrierBalance: int


# CargoTransfer: 1255 characters, 7 entries
class CargoTransferEvent(TypedDict):
    timestamp: str
    event: str
    Transfers: list


# LoadoutRemoveModule: 1225 characters, 3 entries
class LoadoutRemoveModuleEvent(TypedDict):
    timestamp: str
    event: str
    LoadoutName: str
    SuitID: int
    SuitName: str
    SuitName_Localised: str
    LoadoutID: int
    SlotName: str
    ModuleName: str
    ModuleName_Localised: str
    SuitModuleID: int


# RefuelPartial: 968 characters, 10 entries
class RefuelPartialEvent(TypedDict):
    timestamp: str
    event: str
    Cost: int
    Amount: float


# SelfDestruct: 960 characters, 15 entries
class SelfDestructEvent(TypedDict):
    timestamp: str
    event: str


# BuyExplorationData: 949 characters, 9 entries
class BuyExplorationDataEvent(TypedDict):
    timestamp: str
    event: str
    System: str
    Cost: int


# CancelDropship: 948 characters, 12 entries
class CancelDropshipEvent(TypedDict):
    timestamp: str
    event: str
    Refund: int


# JetConeBoost: 913 characters, 11 entries
class JetConeBoostEvent(TypedDict):
    timestamp: str
    event: str
    BoostValue: float


# PowerplaySalary: 873 characters, 8 entries
class PowerplaySalaryEvent(TypedDict):
    timestamp: str
    event: str
    Power: str
    Amount: int


# ShipyardRedeem: 845 characters, 5 entries
class ShipyardRedeemEvent(TypedDict):
    timestamp: str
    event: str
    ShipType: str
    ShipType_Localised: str
    BundleID: int
    MarketID: int


# BackPackMaterials: 786 characters, 6 entries
class BackPackMaterialsEvent(TypedDict):
    timestamp: str
    event: str
    Items: list
    Components: list
    Consumables: list
    Data: list


# ShipRedeemed: 685 characters, 5 entries
class ShipRedeemedEvent(TypedDict):
    timestamp: str
    event: str
    ShipType: str
    ShipType_Localised: str
    NewShipID: int


# PowerplayJoin: 452 characters, 5 entries
class PowerplayJoinEvent(TypedDict):
    timestamp: str
    event: str
    Power: str


# NewCommander: 393 characters, 3 entries
class NewCommanderEvent(TypedDict):
    timestamp: str
    event: str
    FID: str
    Name: str
    Package: str


# ClearImpound: 384 characters, 2 entries
class ClearImpoundEvent(TypedDict):
    timestamp: str
    event: str
    ShipType: str
    ShipType_Localised: str
    ShipID: int
    ShipMarketID: int
    MarketID: int


# Resupply: 360 characters, 6 entries
class ResupplyEvent(TypedDict):
    timestamp: str
    event: str


# FSSBodySignals: 336 characters, 1 entries
class FSSBodySignalsEvent(TypedDict):
    timestamp: str
    event: str
    BodyName: str
    BodyID: int
    SystemAddress: int
    Signals: list


# ChangeCrewRole: 334 characters, 4 entries
class ChangeCrewRoleEvent(TypedDict):
    timestamp: str
    event: str
    Role: str


# SellOrganicData: 300 characters, 1 entries
class SellOrganicDataEvent(TypedDict):
    timestamp: str
    event: str
    MarketID: int
    BioData: list


# PVPKill: 299 characters, 3 entries
class PVPKillEvent(TypedDict):
    timestamp: str
    event: str
    Victim: str
    CombatRank: int


# RequestPowerMicroResources: 255 characters, 1 entries
class RequestPowerMicroResourcesEvent(TypedDict):
    timestamp: str
    event: str
    TotalCount: int
    MicroResources: list
    MarketID: int


# CarrierBuy: 244 characters, 1 entries
class CarrierBuyEvent(TypedDict):
    timestamp: str
    event: str
    CarrierID: int
    BoughtAtMarket: int
    Location: str
    SystemAddress: int
    Price: int
    Variant: str
    Callsign: str


# AppliedToSquadron: 206 characters, 2 entries
class AppliedToSquadronEvent(TypedDict):
    timestamp: str
    event: str
    SquadronName: str


# JoinACrew: 174 characters, 2 entries
class JoinACrewEvent(TypedDict):
    timestamp: str
    event: str
    Captain: str


# QuitACrew: 174 characters, 2 entries
class QuitACrewEvent(TypedDict):
    timestamp: str
    event: str
    Captain: str


# CommunityGoalJoin: 161 characters, 1 entries
class CommunityGoalJoinEvent(TypedDict):
    timestamp: str
    event: str
    CGID: int
    Name: str
    System: str


# DiscoveryScan: 111 characters, 1 entries
class DiscoveryScanEvent(TypedDict):
    timestamp: str
    event: str
    SystemAddress: int
    Bodies: int


# AsteroidCracked: 96 characters, 1 entries
class AsteroidCrackedEvent(TypedDict):
    timestamp: str
    event: str
    Body: str


# PowerplayLeave: 92 characters, 1 entries
class PowerplayLeaveEvent(TypedDict):
    timestamp: str
    event: str
    Power: str


AnyEvent = StoredModulesEvent | ShipLockerEvent | LoadoutEvent | FSSSignalDiscoveredEvent | ReceiveTextEvent | ScanEvent | MaterialsEvent | FSDJumpEvent | ShipTargetedEvent | StatisticsEvent | MusicEvent | LocationEvent | UnderAttackEvent | StoredShipsEvent | DockedEvent | EngineerProgressEvent | EngineerCraftEvent | CarrierStatsEvent | SuitLoadoutEvent | MaterialCollectedEvent | StartJumpEvent | NpcCrewPaidWageEvent | FSDTargetEvent | BackpackChangeEvent | MissionCompletedEvent | ModuleRetrieveEvent | CollectItemsEvent | SupercruiseExitEvent | CargoEvent | FactionKillBondEvent | MissionAcceptedEvent | ApproachSettlementEvent | LoadGameEvent | ModuleBuyEvent | BackpackEvent | DockingRequestedEvent | UndockedEvent | FetchRemoteModuleEvent | OutfittingEvent | DockingGrantedEvent | SupercruiseEntryEvent | EmbarkEvent | DisembarkEvent | LaunchDroneEvent | FuelScoopEvent | PowerplayEvent | ProspectedAsteroidEvent | ShipyardEvent | MissionsEvent | ProgressEvent | BountyEvent | ShieldStateEvent | CollectCargoEvent | CommitCrimeEvent | RankEvent | MassModuleStoreEvent | ScanBaryCentreEvent | ReservoirReplenishedEvent | CommunityGoalEvent | FSSDiscoveryScanEvent | MaterialTradeEvent | ModuleStoreEvent | ReputationEvent | SendTextEvent | ShipyardSwapEvent | TouchdownEvent | FileheaderEvent | RefuelAllEvent | ScannedEvent | ModuleSellRemoteEvent | CommanderEvent | LiftoffEvent | CodexEntryEvent | SwitchSuitLoadoutEvent | HullDamageEvent | ModuleInfoEvent | ApproachBodyEvent | CarrierJumpEvent | NavRouteEvent | SAASignalsFoundEvent | MissionRedirectedEvent | ShipLockerMaterialsEvent | SupercruiseDestinationDropEvent | MiningRefinedEvent | MultiSellExplorationDataEvent | EjectCargoEvent | DockingDeniedEvent | ShipyardTransferEvent | ModuleSellEvent | FriendsEvent | FSSAllBodiesFoundEvent | LeaveBodyEvent | TransferMicroResourcesEvent | HeatWarningEvent | MarketEvent | ModuleSwapEvent | UseConsumableEvent | SquadronStartupEvent | NavRouteClearEvent | BookTaxiEvent | RestockVehicleEvent | RepairAllEvent | DatalinkScanEvent | BuyAmmoEvent | ShutdownEvent | USSDropEvent | LaunchSRVEvent | MaterialDiscoveredEvent | LaunchFighterEvent | WingAddEvent | InterdictedEvent | LoadoutEquipModuleEvent | CarrierJumpRequestEvent | SynthesisEvent | BuyDronesEvent | MarketSellEvent | RedeemVoucherEvent | MarketBuyEvent | ScanOrganicEvent | CarrierTradeOrderEvent | DockSRVEvent | DropshipDeployEvent | SAAScanCompleteEvent | WingJoinEvent | TechnologyBrokerEvent | NavBeaconScanEvent | CrimeVictimEvent | CrewMemberRoleChangeEvent | TradeMicroResourcesEvent | VehicleSwitchEvent | CreateSuitLoadoutEvent | ModuleBuyAndStoreEvent | FighterDestroyedEvent | ResurrectEvent | WingLeaveEvent | FighterRebuiltEvent | DiedEvent | CrewLaunchFighterEvent | RepairEvent | CarrierCrewServicesEvent | ShipyardBuyEvent | ScreenshotEvent | RepairDroneEvent | CargoDepotEvent | HeatDamageEvent | DataScannedEvent | BookDropshipEvent | RebootRepairEvent | CrewAssignEvent | BuyWeaponEvent | SearchAndRescueEvent | PayFinesEvent | SetUserShipNameEvent | SellMicroResourcesEvent | ShipyardSellEvent | DropItemsEvent | DockFighterEvent | ShipyardNewEvent | SystemsShutdownEvent | EscapeInterdictionEvent | MissionFailedEvent | BuyMicroResourcesEvent | BackPackEvent | DockingCancelledEvent | EngineerContributionEvent | SRVDestroyedEvent | PassengersEvent | MissionAbandonedEvent | PayBountiesEvent | SellWeaponEvent | SellExplorationDataEvent | BuySuitEvent | WingInviteEvent | PromotionEvent | CarrierModulePackEvent | CrewHireEvent | EndCrewSessionEvent | UpgradeWeaponEvent | CrewMemberJoinsEvent | CarrierFinanceEvent | UpgradeSuitEvent | CarrierJumpCancelledEvent | CancelTaxiEvent | CarrierDepositFuelEvent | SellDronesEvent | CrewMemberQuitsEvent | NpcCrewRankEvent | DeleteSuitLoadoutEvent | SellSuitEvent | DatalinkVoucherEvent | CrewFireEvent | RenameSuitLoadoutEvent | CarrierDockingPermissionEvent | AfmuRepairsEvent | CockpitBreachedEvent | CarrierBankTransferEvent | CargoTransferEvent | LoadoutRemoveModuleEvent | RefuelPartialEvent | SelfDestructEvent | BuyExplorationDataEvent | CancelDropshipEvent | JetConeBoostEvent | PowerplaySalaryEvent | ShipyardRedeemEvent | BackPackMaterialsEvent | ShipRedeemedEvent | PowerplayJoinEvent | NewCommanderEvent | ClearImpoundEvent | ResupplyEvent | FSSBodySignalsEvent | ChangeCrewRoleEvent | SellOrganicDataEvent | PVPKillEvent | RequestPowerMicroResourcesEvent | CarrierBuyEvent | AppliedToSquadronEvent | JoinACrewEvent | QuitACrewEvent | CommunityGoalJoinEvent | DiscoveryScanEvent | AsteroidCrackedEvent | PowerplayLeaveEvent
