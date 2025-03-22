# THIS FILE IS AUTO-GENERATED
# DO NOT EDIT
# USE BuildEventModels.py TO UPDATE

from typing import TypedDict, NotRequired, Literal, Any

# StoredModules: 47833307 characters, 1011 entries
class StoredModulesEventItemsItem(TypedDict):
    MarketID: NotRequired[int]
    TransferCost: NotRequired[int]
    EngineerModifications: NotRequired[str]
    Level: NotRequired[int]
    StorageSlot: int
    Name_Localised: str
    Quality: NotRequired[float]
    StarSystem: NotRequired[str]
    Name: str
    InTransit: NotRequired[bool]
    BuyPrice: int
    TransferTime: NotRequired[int]
    Hot: bool
class StoredModulesEvent(TypedDict):
    MarketID: int
    StationName: str
    StarSystem: str
    event: Literal["StoredModules"]
    timestamp: str
    Items: list[StoredModulesEventItemsItem]


# ShipLocker: 26227788 characters, 3537 entries
class ShipLockerEventConsumablesItem(TypedDict):
    Count: int
    OwnerID: Literal[0]
    Name_Localised: str
    Name: str
class ShipLockerEventComponentsItem(TypedDict):
    Count: int
    OwnerID: Literal[0]
    Name_Localised: NotRequired[str]
    Name: str
class ShipLockerEventDataItem(TypedDict):
    Count: int
    OwnerID: int
    Name_Localised: NotRequired[str]
    Name: str
class ShipLockerEventItemsItem(TypedDict):
    OwnerID: int
    MissionID: NotRequired[int]
    Name_Localised: NotRequired[str]
    Name: str
    Count: int
class ShipLockerEvent(TypedDict):
    Consumables: NotRequired[list[ShipLockerEventConsumablesItem]]
    Components: NotRequired[list[ShipLockerEventComponentsItem]]
    event: Literal["ShipLocker"]
    timestamp: str
    Data: NotRequired[list[ShipLockerEventDataItem]]
    Items: NotRequired[list[ShipLockerEventItemsItem]]


# Loadout: 5496403 characters, 433 entries
class LoadoutEventModulesItemEngineeringModifiersItem(TypedDict):
    LessIsGood: int
    OriginalValue: float
    Value: float
    Label: str
class LoadoutEventModulesItemEngineering(TypedDict):
    Level: int
    EngineerID: int
    Engineer: NotRequired[str]
    ExperimentalEffect: NotRequired[str]
    BlueprintID: int
    Quality: float
    Modifiers: list[LoadoutEventModulesItemEngineeringModifiersItem]
    ExperimentalEffect_Localised: NotRequired[str]
    BlueprintName: str
class LoadoutEventModulesItem(TypedDict):
    AmmoInHopper: NotRequired[int]
    AmmoInClip: NotRequired[int]
    Item: str
    Value: NotRequired[int]
    Health: float
    Engineering: NotRequired[LoadoutEventModulesItemEngineering]
    Slot: str
    On: bool
    Priority: int
class LoadoutEventFuelcapacity(TypedDict):
    Reserve: float
    Main: float
class LoadoutEvent(TypedDict):
    ShipName: str
    HullValue: NotRequired[int]
    HullHealth: float
    ShipIdent: str
    ModulesValue: NotRequired[int]
    CargoCapacity: int
    Modules: list[LoadoutEventModulesItem]
    FuelCapacity: LoadoutEventFuelcapacity
    MaxJumpRange: float
    Rebuy: int
    ShipID: int
    event: Literal["Loadout"]
    timestamp: str
    UnladenMass: float
    Ship: str
    Hot: NotRequired[bool]


# FSSSignalDiscovered: 3274822 characters, 16820 entries
class FSSSignalDiscoveredEvent(TypedDict):
    SignalType: str
    IsStation: NotRequired[bool]
    SignalName: str
    SystemAddress: int
    event: Literal["FSSSignalDiscovered"]
    timestamp: str
    SignalName_Localised: NotRequired[str]


# Materials: 1361155 characters, 163 entries
class MaterialsEventRawItem(TypedDict):
    Count: int
    Name: str
class MaterialsEventEncodedItem(TypedDict):
    Count: int
    Name_Localised: str
    Name: str
class MaterialsEventManufacturedItem(TypedDict):
    Count: int
    Name_Localised: str
    Name: str
class MaterialsEvent(TypedDict):
    Raw: list[MaterialsEventRawItem]
    Encoded: list[MaterialsEventEncodedItem]
    event: Literal["Materials"]
    Manufactured: list[MaterialsEventManufacturedItem]
    timestamp: str


# Scan: 1175962 characters, 1642 entries
class ScanEventAtmospherecompositionItem(TypedDict):
    Percent: float
    Name: str
class ScanEventMaterialsItem(TypedDict):
    Percent: float
    Name: str
class ScanEventParentsItem(TypedDict):
    Star: NotRequired[int]
    Null: NotRequired[int]
    Ring: NotRequired[int]
    Planet: NotRequired[int]
class ScanEventComposition(TypedDict):
    Ice: float
    Metal: float
    Rock: float
class ScanEventRingsItem(TypedDict):
    OuterRad: float
    InnerRad: float
    RingClass: str
    Name: str
    MassMT: Any
class ScanEvent(TypedDict):
    WasMapped: bool
    Periapsis: NotRequired[float]
    MassEM: NotRequired[float]
    WasDiscovered: bool
    timestamp: str
    OrbitalPeriod: NotRequired[float]
    DistanceFromArrivalLS: float
    OrbitalInclination: NotRequired[float]
    ReserveLevel: NotRequired[str]
    AtmosphereComposition: NotRequired[list[ScanEventAtmospherecompositionItem]]
    AscendingNode: NotRequired[float]
    Materials: NotRequired[list[ScanEventMaterialsItem]]
    ScanType: str
    StarType: NotRequired[str]
    SemiMajorAxis: NotRequired[float]
    AtmosphereType: NotRequired[str]
    Volcanism: NotRequired[str]
    AxialTilt: NotRequired[float]
    TerraformState: NotRequired[str]
    TidalLock: NotRequired[bool]
    MeanAnomaly: NotRequired[float]
    Eccentricity: NotRequired[float]
    Parents: NotRequired[list[ScanEventParentsItem]]
    Radius: NotRequired[float]
    SystemAddress: int
    Subclass: NotRequired[int]
    Landable: NotRequired[bool]
    event: Literal["Scan"]
    SurfaceGravity: NotRequired[float]
    Atmosphere: NotRequired[str]
    BodyName: str
    SurfaceTemperature: NotRequired[float]
    Age_MY: NotRequired[int]
    BodyID: int
    StellarMass: NotRequired[float]
    AbsoluteMagnitude: NotRequired[float]
    Luminosity: NotRequired[str]
    Composition: NotRequired[ScanEventComposition]
    Rings: NotRequired[list[ScanEventRingsItem]]
    PlanetClass: NotRequired[str]
    StarSystem: str
    RotationPeriod: NotRequired[float]
    SurfacePressure: NotRequired[float]


# FSDJump: 1080940 characters, 661 entries
class FSDJumpEventSystemfaction(TypedDict):
    FactionState: NotRequired[str]
    Name: str
class FSDJumpEventFactionsItemPendingstatesItem(TypedDict):
    State: str
    Trend: Literal[0]
class FSDJumpEventFactionsItemActivestatesItem(TypedDict):
    State: str
class FSDJumpEventFactionsItemRecoveringstatesItem(TypedDict):
    State: str
    Trend: Literal[0]
class FSDJumpEventFactionsItem(TypedDict):
    Influence: float
    Happiness: str
    PendingStates: NotRequired[list[FSDJumpEventFactionsItemPendingstatesItem]]
    ActiveStates: NotRequired[list[FSDJumpEventFactionsItemActivestatesItem]]
    Allegiance: str
    SquadronFaction: NotRequired[bool]
    Happiness_Localised: NotRequired[str]
    MyReputation: float
    Name: str
    FactionState: str
    RecoveringStates: NotRequired[list[FSDJumpEventFactionsItemRecoveringstatesItem]]
    Government: str
class FSDJumpEventThargoidwar(TypedDict):
    SuccessStateReached: bool
    EstimatedRemainingTime: NotRequired[str]
    CurrentState: str
    RemainingPorts: int
    NextStateFailure: str
    WarProgress: float
    NextStateSuccess: str
class FSDJumpEventConflictsItemFaction2(TypedDict):
    WonDays: int
    Stake: str
    Name: str
class FSDJumpEventConflictsItemFaction1(TypedDict):
    WonDays: int
    Stake: str
    Name: str
class FSDJumpEventConflictsItem(TypedDict):
    Status: str
    WarType: str
    Faction2: FSDJumpEventConflictsItemFaction2
    Faction1: FSDJumpEventConflictsItemFaction1
class FSDJumpEvent(TypedDict):
    SystemAllegiance: str
    SystemEconomy: str
    SystemFaction: NotRequired[FSDJumpEventSystemfaction]
    SystemSecurity: str
    StarPos: list[float]
    JumpDist: float
    timestamp: str
    FuelLevel: float
    PowerplayState: NotRequired[str]
    Factions: NotRequired[list[FSDJumpEventFactionsItem]]
    Multicrew: bool
    SystemEconomy_Localised: str
    Taxi: bool
    SystemSecondEconomy: str
    SystemSecurity_Localised: str
    Population: int
    BodyType: str
    SystemSecondEconomy_Localised: str
    BoostUsed: NotRequired[Literal[4]]
    Body: str
    Powers: NotRequired[list[str]]
    SystemAddress: int
    event: Literal["FSDJump"]
    SystemGovernment_Localised: str
    BodyID: int
    FuelUsed: float
    StarSystem: str
    ThargoidWar: NotRequired[FSDJumpEventThargoidwar]
    Conflicts: NotRequired[list[FSDJumpEventConflictsItem]]
    SystemGovernment: str


# Statistics: 819077 characters, 163 entries
class StatisticsEventPassengers(TypedDict):
    Passengers_Missions_VIP: int
    Passengers_Missions_Delivered: int
    Passengers_Missions_Disgruntled: NotRequired[Literal[70]]
    Passengers_Missions_Bulk: int
    Passengers_Missions_Accepted: int
    Passengers_Missions_Ejected: int
class StatisticsEventExploration(TypedDict):
    Systems_Visited: int
    Total_Hyperspace_Jumps: int
    Greatest_Distance_From_Start: float
    Spent_On_Shuttles: int
    OnFoot_Distance_Travelled: int
    Settlements_Visited: int
    Shuttle_Distance_Travelled: float
    Total_Hyperspace_Distance: int
    Highest_Payout: int
    Shuttle_Journeys: int
    Planets_Scanned_To_Level_2: int
    Planets_Scanned_To_Level_3: int
    First_Footfalls: Literal[0]
    Exploration_Profits: int
    Time_Played: int
    Planet_Footfalls: int
    Efficient_Scans: int
class StatisticsEventCrew(TypedDict):
    NpcCrew_Fired: int
    NpcCrew_Died: int
    NpcCrew_Hired: int
    NpcCrew_TotalWages: int
class StatisticsEventMulticrew(TypedDict):
    Multicrew_Gunner_Time_Total: int
    Multicrew_Fighter_Time_Total: Literal[0]
    Multicrew_Fines_Total: Literal[0]
    Multicrew_Time_Total: int
    Multicrew_Credits_Total: Literal[0]
class StatisticsEventExobiology(TypedDict):
    First_Logged: Literal[0]
    Organic_Data_Profits: int
    Organic_Variant_Encountered: int
    Organic_Species: int
    Organic_Genus: int
    Organic_Systems: int
    Organic_Data: int
    Organic_Planets: int
    Organic_Species_Encountered: int
    Organic_Genus_Encountered: int
    First_Logged_Profits: Literal[0]
class StatisticsEventTg_encounters(TypedDict):
    TG_ENCOUNTER_TOTAL_LAST_SYSTEM: str
    TG_ENCOUNTER_KILLED: NotRequired[int]
    TG_ENCOUNTER_TOTAL_LAST_TIMESTAMP: str
    TG_ENCOUNTER_TOTAL: int
    TG_ENCOUNTER_TOTAL_LAST_SHIP: str
class StatisticsEventCrafting(TypedDict):
    Recipes_Generated_Rank_4: int
    Suit_Mods_Applied: Literal[0]
    Recipes_Generated: int
    Weapon_Mods_Applied_Full: Literal[0]
    Weapons_Upgraded_Full: Literal[0]
    Suits_Upgraded_Full: Literal[0]
    Weapon_Mods_Applied: int
    Count_Of_Used_Engineers: int
    Recipes_Generated_Rank_2: int
    Weapons_Upgraded: int
    Suit_Mods_Applied_Full: Literal[0]
    Recipes_Generated_Rank_5: int
    Suits_Upgraded: Literal[0]
    Recipes_Generated_Rank_1: int
    Recipes_Generated_Rank_3: int
class StatisticsEventSmuggling(TypedDict):
    Resources_Smuggled: Literal[0]
    Black_Markets_Profits: Literal[0]
    Average_Profit: Literal[0]
    Highest_Single_Transaction: Literal[0]
    Black_Markets_Traded_With: Literal[0]
class StatisticsEventCrime(TypedDict):
    Sample_Stolen: int
    Data_Stolen: int
    Turrets_Overloaded: Literal[0]
    Total_Fines: int
    Total_Stolen: int
    Goods_Stolen: int
    Malware_Uploaded: Literal[0]
    Total_Bounties: int
    Highest_Bounty: Literal[1000]
    Turrets_Total: int
    Production_Sabotage: int
    Settlements_State_Shutdown: int
    Citizens_Murdered: int
    Notoriety: Literal[0]
    Total_Murders: int
    Production_Theft: int
    Turrets_Destroyed: int
    Omnipol_Murdered: int
    Value_Stolen_StateChange: int
    Bounties_Received: int
    Profiles_Cloned: int
    Guards_Murdered: int
    Fines: int
class StatisticsEventBank_account(TypedDict):
    Spent_On_Suit_Consumables: int
    Spent_On_Repairs: int
    Spent_On_Ammo_Consumables: int
    Spent_On_Outfitting: int
    Insurance_Claims: int
    Spent_On_Insurance: int
    Spent_On_Ships: int
    Current_Wealth: int
    Spent_On_Weapons: int
    Owned_Ship_Count: int
    Spent_On_Premium_Stock: int
    Weapons_Owned: int
    Suits_Owned: int
    Premium_Stock_Bought: int
    Spent_On_Suits: int
    Spent_On_Fuel: int
class StatisticsEventSearch_and_rescue(TypedDict):
    SearchRescue_Traded: int
    Settlements_State_FireOut: int
    SearchRescue_Count: int
    Salvage_Legal_Settlements: int
    Salvage_Illegal_Settlements: Literal[0]
    SearchRescue_Profit: int
    Maglocks_Opened: int
    Salvage_Illegal_POI: int
    Settlements_State_Reboot: int
    Salvage_Legal_POI: int
    Panels_Opened: int
class StatisticsEventTrading(TypedDict):
    Resources_Traded: int
    Market_Profits: int
    Goods_Sold: int
    Average_Profit: Any
    Highest_Single_Transaction: int
    Markets_Traded_With: int
    Assets_Sold: Literal[0]
    Data_Sold: int
class StatisticsEventCombat(TypedDict):
    Combat_Bond_Profits: int
    Bounties_Claimed: int
    ConflictZone_High_Wins: int
    OnFoot_Combat_Bonds_Profits: int
    Bounty_Hunting_Profit: int
    OnFoot_Combat_Bonds: int
    OnFoot_Vehicles_Destroyed: Literal[0]
    ConflictZone_Total: int
    ConflictZone_Medium: int
    ConflictZone_Medium_Wins: int
    Assassinations: int
    Highest_Single_Reward: int
    OnFoot_Skimmers_Killed: int
    ConflictZone_Low: int
    Settlement_Conquered: int
    Dropships_Cancelled: int
    Combat_Bonds: int
    Skimmers_Killed: int
    Settlement_Defended: int
    ConflictZone_High: int
    Dropships_Booked: int
    OnFoot_Scavs_Killed: int
    ConflictZone_Total_Wins: int
    ConflictZone_Low_Wins: int
    Dropships_Taken: int
    Assassination_Profits: int
    OnFoot_Ships_Destroyed: int
class StatisticsEventMaterial_trader_stats(TypedDict):
    Assets_Traded_Out: int
    Grade_4_Materials_Traded: int
    Grade_2_Materials_Traded: int
    Grade_3_Materials_Traded: int
    Materials_Traded: int
    Trades_Completed: int
    Assets_Traded_In: int
    Encoded_Materials_Traded: int
    Raw_Materials_Traded: int
    Grade_1_Materials_Traded: int
    Grade_5_Materials_Traded: int
class StatisticsEventMining(TypedDict):
    Mining_Profits: int
    Materials_Collected: int
    Quantity_Mined: int
class StatisticsEvent(TypedDict):
    Passengers: StatisticsEventPassengers
    Exploration: StatisticsEventExploration
    Crew: StatisticsEventCrew
    Multicrew: StatisticsEventMulticrew
    Exobiology: StatisticsEventExobiology
    TG_ENCOUNTERS: StatisticsEventTg_encounters
    Crafting: StatisticsEventCrafting
    Smuggling: StatisticsEventSmuggling
    event: Literal["Statistics"]
    timestamp: str
    Crime: StatisticsEventCrime
    Bank_Account: StatisticsEventBank_account
    Search_And_Rescue: StatisticsEventSearch_and_rescue
    Trading: StatisticsEventTrading
    Combat: StatisticsEventCombat
    Material_Trader_Stats: StatisticsEventMaterial_trader_stats
    Mining: StatisticsEventMining


# ReceiveText: 810441 characters, 3464 entries
class ReceiveTextEvent(TypedDict):
    Message: str
    event: Literal["ReceiveText"]
    From_Localised: NotRequired[str]
    timestamp: str
    Message_Localised: NotRequired[str]
    Channel: str
    From: str


# Music: 477180 characters, 5554 entries
class MusicEvent(TypedDict):
    MusicTrack: str
    event: Literal["Music"]
    timestamp: str


# EngineerProgress: 453658 characters, 176 entries
class EngineerProgressEventEngineersItem(TypedDict):
    EngineerID: int
    Engineer: str
    Progress: str
    Rank: NotRequired[int]
    RankProgress: NotRequired[int]
class EngineerProgressEvent(TypedDict):
    EngineerID: NotRequired[int]
    Engineer: NotRequired[str]
    Progress: NotRequired[str]
    Engineers: NotRequired[list[EngineerProgressEventEngineersItem]]
    event: Literal["EngineerProgress"]
    timestamp: str
    Rank: NotRequired[int]


# Location: 437896 characters, 169 entries
class LocationEventSystemfaction(TypedDict):
    FactionState: NotRequired[str]
    Name: str
class LocationEventFactionsItemPendingstatesItem(TypedDict):
    State: str
    Trend: Literal[0]
class LocationEventFactionsItemActivestatesItem(TypedDict):
    State: str
class LocationEventFactionsItemRecoveringstatesItem(TypedDict):
    State: str
    Trend: Literal[0]
class LocationEventFactionsItem(TypedDict):
    Influence: float
    Happiness: str
    PendingStates: NotRequired[list[LocationEventFactionsItemPendingstatesItem]]
    ActiveStates: NotRequired[list[LocationEventFactionsItemActivestatesItem]]
    Allegiance: str
    Happiness_Localised: str
    MyReputation: float
    Name: str
    FactionState: str
    RecoveringStates: NotRequired[list[LocationEventFactionsItemRecoveringstatesItem]]
    Government: str
class LocationEventStationeconomiesItem(TypedDict):
    Proportion: float
    Name_Localised: str
    Name: str
class LocationEventStationfaction(TypedDict):
    FactionState: NotRequired[str]
    Name: str
class LocationEventThargoidwar(TypedDict):
    SuccessStateReached: bool
    EstimatedRemainingTime: NotRequired[str]
    CurrentState: str
    RemainingPorts: int
    NextStateFailure: str
    WarProgress: float
    NextStateSuccess: Literal[""]
class LocationEventConflictsItemFaction2(TypedDict):
    WonDays: int
    Stake: str
    Name: str
class LocationEventConflictsItemFaction1(TypedDict):
    WonDays: int
    Stake: str
    Name: str
class LocationEventConflictsItem(TypedDict):
    Status: str
    WarType: str
    Faction2: LocationEventConflictsItemFaction2
    Faction1: LocationEventConflictsItemFaction1
class LocationEvent(TypedDict):
    MarketID: NotRequired[int]
    StationAllegiance: NotRequired[str]
    SystemAllegiance: str
    SystemEconomy: str
    DistFromStarLS: NotRequired[float]
    SystemFaction: NotRequired[LocationEventSystemfaction]
    SystemSecurity: str
    StarPos: list[float]
    Longitude: NotRequired[float]
    InSRV: NotRequired[bool]
    timestamp: str
    Factions: NotRequired[list[LocationEventFactionsItem]]
    PowerplayState: NotRequired[str]
    Multicrew: NotRequired[bool]
    SystemEconomy_Localised: str
    StationEconomy: NotRequired[str]
    StationGovernment_Localised: NotRequired[str]
    Taxi: NotRequired[bool]
    StationGovernment: NotRequired[str]
    StationName: NotRequired[str]
    SystemSecondEconomy: str
    StationType: NotRequired[str]
    Latitude: NotRequired[float]
    SystemSecurity_Localised: str
    Population: int
    BodyType: str
    SystemSecondEconomy_Localised: str
    Body: str
    Powers: NotRequired[list[str]]
    StationEconomies: NotRequired[list[LocationEventStationeconomiesItem]]
    Docked: bool
    SystemAddress: int
    event: Literal["Location"]
    StationServices: NotRequired[list[str]]
    OnFoot: NotRequired[bool]
    StationEconomy_Localised: NotRequired[str]
    SystemGovernment_Localised: str
    BodyID: int
    StationFaction: NotRequired[LocationEventStationfaction]
    StarSystem: str
    ThargoidWar: NotRequired[LocationEventThargoidwar]
    Conflicts: NotRequired[list[LocationEventConflictsItem]]
    SystemGovernment: str


# EngineerCraft: 423777 characters, 437 entries
class EngineerCraftEventIngredientsItem(TypedDict):
    Count: int
    Name_Localised: NotRequired[str]
    Name: str
class EngineerCraftEventModifiersItem(TypedDict):
    LessIsGood: int
    OriginalValue: float
    Value: float
    Label: str
class EngineerCraftEvent(TypedDict):
    Level: int
    Module: str
    EngineerID: int
    Ingredients: list[EngineerCraftEventIngredientsItem]
    Engineer: str
    ApplyExperimentalEffect: NotRequired[str]
    ExperimentalEffect: NotRequired[str]
    BlueprintID: int
    Quality: float
    Modifiers: list[EngineerCraftEventModifiersItem]
    event: Literal["EngineerCraft"]
    timestamp: str
    Slot: str
    ExperimentalEffect_Localised: NotRequired[str]
    BlueprintName: str


# UnderAttack: 382230 characters, 4777 entries
class UnderAttackEvent(TypedDict):
    Target: str
    event: Literal["UnderAttack"]
    timestamp: str


# StoredShips: 306416 characters, 184 entries
class StoredShipsEventShipshereItem(TypedDict):
    ShipType: str
    ShipID: int
    Value: int
    Name: NotRequired[str]
    ShipType_Localised: NotRequired[str]
    Hot: bool
class StoredShipsEventShipsremoteItem(TypedDict):
    TransferPrice: NotRequired[int]
    ShipMarketID: NotRequired[int]
    ShipType: str
    StarSystem: NotRequired[str]
    ShipID: int
    Value: int
    Name: str
    InTransit: NotRequired[bool]
    ShipType_Localised: NotRequired[str]
    TransferTime: NotRequired[int]
    Hot: bool
class StoredShipsEvent(TypedDict):
    MarketID: int
    StationName: str
    ShipsHere: list[StoredShipsEventShipshereItem]
    StarSystem: str
    event: Literal["StoredShips"]
    timestamp: str
    ShipsRemote: list[StoredShipsEventShipsremoteItem]


# Docked: 290226 characters, 268 entries
class DockedEventStationeconomiesItem(TypedDict):
    Proportion: float
    Name_Localised: str
    Name: str
class DockedEventStationfaction(TypedDict):
    FactionState: NotRequired[str]
    Name: str
class DockedEventLandingpads(TypedDict):
    Medium: int
    Small: int
    Large: int
class DockedEvent(TypedDict):
    MarketID: int
    StationAllegiance: NotRequired[str]
    DistFromStarLS: float
    timestamp: str
    Multicrew: bool
    StationEconomy: str
    Taxi: bool
    StationGovernment_Localised: str
    ActiveFine: NotRequired[bool]
    StationGovernment: str
    StationName: str
    StationType: str
    StationEconomies: list[DockedEventStationeconomiesItem]
    StationState: NotRequired[str]
    SystemAddress: int
    event: Literal["Docked"]
    StationServices: list[str]
    CockpitBreach: NotRequired[bool]
    StationEconomy_Localised: str
    StationFaction: DockedEventStationfaction
    StarSystem: str
    LandingPads: DockedEventLandingpads


# ShipTargeted: 228373 characters, 908 entries
class ShipTargetedEvent(TypedDict):
    TargetLocked: bool
    Subsystem: NotRequired[str]
    timestamp: str
    SquadronID: NotRequired[Literal["EDO1"]]
    HullHealth: NotRequired[float]
    Ship_Localised: NotRequired[str]
    Bounty: NotRequired[int]
    Ship: NotRequired[str]
    Faction: NotRequired[str]
    ShieldHealth: NotRequired[float]
    PilotName_Localised: NotRequired[str]
    ScanStage: NotRequired[int]
    Power: NotRequired[str]
    event: Literal["ShipTargeted"]
    Subsystem_Localised: NotRequired[str]
    SubsystemHealth: NotRequired[float]
    LegalStatus: NotRequired[str]
    PilotName: NotRequired[str]
    PilotRank: NotRequired[str]


# MissionCompleted: 198592 characters, 284 entries
class MissionCompletedEventFactioneffectsItemInfluenceItem(TypedDict):
    SystemAddress: int
    Influence: str
    Trend: str
class MissionCompletedEventFactioneffectsItemEffectsItem(TypedDict):
    Trend: str
    Effect_Localised: str
    Effect: str
class MissionCompletedEventFactioneffectsItem(TypedDict):
    Influence: list[MissionCompletedEventFactioneffectsItemInfluenceItem]
    Reputation: str
    ReputationTrend: str
    Effects: list[MissionCompletedEventFactioneffectsItemEffectsItem]
    Faction: str
class MissionCompletedEvent(TypedDict):
    Reward: NotRequired[int]
    MissionID: int
    Donated: NotRequired[int]
    LocalisedName: str
    FactionEffects: list[MissionCompletedEventFactioneffectsItem]
    DestinationStation: NotRequired[str]
    TargetFaction: NotRequired[str]
    TargetType_Localised: NotRequired[Literal["Known Pirate"]]
    Donation: NotRequired[str]
    TargetType: NotRequired[Literal["$MissionUtil_FactionTag_PirateLord;"]]
    DestinationSettlement: NotRequired[Literal["Mahto's Syntheticals"]]
    event: Literal["MissionCompleted"]
    timestamp: str
    Name: str
    Target: NotRequired[str]
    DestinationSystem: NotRequired[str]
    Faction: str


# StartJump: 151410 characters, 943 entries
class StartJumpEvent(TypedDict):
    Taxi: bool
    JumpType: str
    SystemAddress: NotRequired[int]
    StarSystem: NotRequired[str]
    event: Literal["StartJump"]
    StarClass: NotRequired[str]
    timestamp: str


# ProspectedAsteroid: 135208 characters, 342 entries
class ProspectedAsteroidEventMaterialsItem(TypedDict):
    Proportion: float
    Name_Localised: NotRequired[str]
    Name: str
class ProspectedAsteroidEvent(TypedDict):
    Content: str
    Materials: list[ProspectedAsteroidEventMaterialsItem]
    Content_Localised: str
    event: Literal["ProspectedAsteroid"]
    timestamp: str
    Remaining: float


# FSDTarget: 129833 characters, 787 entries
class FSDTargetEvent(TypedDict):
    RemainingJumpsInRoute: NotRequired[int]
    SystemAddress: int
    StarClass: str
    event: Literal["FSDTarget"]
    timestamp: str
    Name: str


# NpcCrewPaidWage: 118276 characters, 861 entries
class NpcCrewPaidWageEvent(TypedDict):
    NpcCrewId: int
    event: Literal["NpcCrewPaidWage"]
    timestamp: str
    Amount: int
    NpcCrewName: str


# ModuleRetrieve: 108733 characters, 306 entries
class ModuleRetrieveEvent(TypedDict):
    MarketID: int
    EngineerModifications: NotRequired[str]
    Level: NotRequired[int]
    RetrievedItem: str
    SwapOutItem: NotRequired[str]
    Quality: NotRequired[float]
    SwapOutItem_Localised: NotRequired[str]
    RetrievedItem_Localised: str
    event: Literal["ModuleRetrieve"]
    ShipID: int
    timestamp: str
    Ship: str
    Slot: str
    Hot: bool


# MaterialCollected: 102400 characters, 603 entries
class MaterialCollectedEvent(TypedDict):
    Category: str
    Name_Localised: NotRequired[str]
    event: Literal["MaterialCollected"]
    timestamp: str
    Name: str
    Count: int


# MissionAccepted: 100639 characters, 289 entries
class MissionAcceptedEvent(TypedDict):
    TargetType: NotRequired[Literal["$MissionUtil_FactionTag_PirateLord;"]]
    timestamp: str
    Influence: str
    MissionID: int
    Expiry: str
    Name: str
    Faction: str
    Reputation: str
    Reward: NotRequired[int]
    TargetFaction: NotRequired[str]
    event: Literal["MissionAccepted"]
    Target: NotRequired[str]
    Wing: bool
    LocalisedName: str
    DestinationStation: NotRequired[str]
    Donation: NotRequired[str]
    DestinationSettlement: NotRequired[Literal["Mahto's Syntheticals"]]
    DestinationSystem: NotRequired[str]
    TargetType_Localised: NotRequired[Literal["Known Pirate"]]


# SupercruiseExit: 95457 characters, 431 entries
class SupercruiseExitEvent(TypedDict):
    BodyType: str
    BodyID: int
    Taxi: bool
    Body: str
    SystemAddress: int
    StarSystem: str
    event: Literal["SupercruiseExit"]
    timestamp: str
    Multicrew: bool


# Cargo: 84284 characters, 866 entries
class CargoEventInventoryItem(TypedDict):
    Count: int
    Name_Localised: NotRequired[str]
    Stolen: Literal[0]
    Name: str
class CargoEvent(TypedDict):
    Vessel: str
    Inventory: NotRequired[list[CargoEventInventoryItem]]
    event: Literal["Cargo"]
    timestamp: str
    Count: int


# LaunchDrone: 76107 characters, 897 entries
class LaunchDroneEvent(TypedDict):
    event: Literal["LaunchDrone"]
    Type: str
    timestamp: str


# LoadGame: 69846 characters, 164 entries
class LoadGameEvent(TypedDict):
    GameMode: NotRequired[str]
    Commander: str
    FuelCapacity: NotRequired[float]
    FID: str
    ShipID: NotRequired[int]
    timestamp: str
    FuelLevel: NotRequired[float]
    Group: NotRequired[Literal["TREMENDOUSLYRUDE.TTV"]]
    build: str
    ShipIdent: NotRequired[str]
    Ship_Localised: NotRequired[str]
    StartDead: NotRequired[bool]
    Ship: NotRequired[str]
    gameversion: str
    Horizons: bool
    ShipName: NotRequired[str]
    Odyssey: bool
    language: Literal["English/UK"]
    event: Literal["LoadGame"]
    Loan: Literal[0]
    Credits: int
    StartLanded: NotRequired[bool]


# FetchRemoteModule: 61321 characters, 210 entries
class FetchRemoteModuleEvent(TypedDict):
    TransferCost: int
    StoredItem_Localised: str
    StorageSlot: int
    StoredItem: str
    event: Literal["FetchRemoteModule"]
    ShipID: int
    timestamp: str
    Ship: str
    TransferTime: int
    ServerId: int


# ApproachSettlement: 58863 characters, 74 entries
class ApproachSettlementEventStationeconomiesItem(TypedDict):
    Proportion: float
    Name_Localised: str
    Name: str
class ApproachSettlementEventStationfaction(TypedDict):
    FactionState: NotRequired[str]
    Name: str
class ApproachSettlementEvent(TypedDict):
    MarketID: NotRequired[int]
    StationEconomy: NotRequired[str]
    StationAllegiance: NotRequired[str]
    BodyID: int
    StationGovernment_Localised: NotRequired[str]
    StationGovernment: NotRequired[str]
    StationEconomies: NotRequired[list[ApproachSettlementEventStationeconomiesItem]]
    StationFaction: NotRequired[ApproachSettlementEventStationfaction]
    Longitude: float
    SystemAddress: int
    Name_Localised: NotRequired[str]
    event: Literal["ApproachSettlement"]
    StationServices: NotRequired[list[str]]
    timestamp: str
    Name: str
    Latitude: float
    BodyName: str
    StationEconomy_Localised: NotRequired[str]


# DockingRequested: 57972 characters, 278 entries
class DockingRequestedEventLandingpads(TypedDict):
    Medium: int
    Small: int
    Large: int
class DockingRequestedEvent(TypedDict):
    MarketID: int
    StationName: str
    StationType: str
    event: Literal["DockingRequested"]
    timestamp: str
    LandingPads: DockingRequestedEventLandingpads


# MaterialTrade: 53506 characters, 154 entries
class MaterialTradeEventReceived(TypedDict):
    Material_Localised: NotRequired[str]
    Category: str
    Material: str
    Quantity: int
class MaterialTradeEventPaid(TypedDict):
    Material_Localised: NotRequired[str]
    Category: str
    Material: str
    Quantity: int
class MaterialTradeEvent(TypedDict):
    MarketID: int
    event: Literal["MaterialTrade"]
    Received: MaterialTradeEventReceived
    timestamp: str
    Paid: MaterialTradeEventPaid
    TraderType: str


# Undocked: 49968 characters, 277 entries
class UndockedEvent(TypedDict):
    MarketID: int
    Taxi: bool
    StationName: str
    StationType: str
    event: Literal["Undocked"]
    timestamp: str
    Multicrew: bool


# SupercruiseDestinationDrop: 47457 characters, 309 entries
class SupercruiseDestinationDropEvent(TypedDict):
    MarketID: NotRequired[int]
    Type: str
    Type_Localised: NotRequired[str]
    event: Literal["SupercruiseDestinationDrop"]
    timestamp: str
    Threat: int


# Outfitting: 47363 characters, 320 entries
class OutfittingEvent(TypedDict):
    MarketID: int
    StationName: str
    StarSystem: str
    event: Literal["Outfitting"]
    timestamp: str


# SupercruiseEntry: 44829 characters, 277 entries
class SupercruiseEntryEvent(TypedDict):
    Taxi: bool
    SystemAddress: int
    StarSystem: str
    event: Literal["SupercruiseEntry"]
    timestamp: str
    Multicrew: bool


# DockingGranted: 44720 characters, 265 entries
class DockingGrantedEvent(TypedDict):
    MarketID: int
    StationName: str
    event: Literal["DockingGranted"]
    StationType: str
    timestamp: str
    LandingPad: int


# FuelScoop: 42941 characters, 429 entries
class FuelScoopEvent(TypedDict):
    Total: float
    event: Literal["FuelScoop"]
    Scooped: float
    timestamp: str


# Powerplay: 42158 characters, 288 entries
class PowerplayEvent(TypedDict):
    Merits: Literal[0]
    TimePledged: int
    Power: Literal["Aisling Duval"]
    event: Literal["Powerplay"]
    Rank: Literal[0]
    timestamp: str
    Votes: Literal[0]


# MultiSellExplorationData: 40568 characters, 16 entries
class MultiSellExplorationDataEventDiscoveredItem(TypedDict):
    NumBodies: int
    SystemName: str
class MultiSellExplorationDataEvent(TypedDict):
    Discovered: list[MultiSellExplorationDataEventDiscoveredItem]
    TotalEarnings: int
    Bonus: int
    event: Literal["MultiSellExplorationData"]
    timestamp: str
    BaseValue: int


# SuitLoadout: 36241 characters, 42 entries
class SuitLoadoutEventModulesItem(TypedDict):
    WeaponMods: list[str]
    SlotName: str
    Class: int
    SuitModuleID: int
    ModuleName_Localised: str
    ModuleName: str
class SuitLoadoutEvent(TypedDict):
    SuitMods: list[str]
    Modules: list[SuitLoadoutEventModulesItem]
    SuitName: str
    LoadoutName: str
    LoadoutID: int
    event: Literal["SuitLoadout"]
    SuitID: int
    timestamp: str
    SuitName_Localised: str


# ModuleBuy: 35471 characters, 115 entries
class ModuleBuyEvent(TypedDict):
    MarketID: int
    BuyItem_Localised: str
    StoredItem_Localised: NotRequired[str]
    StoredItem: NotRequired[str]
    BuyItem: str
    event: Literal["ModuleBuy"]
    ShipID: int
    timestamp: str
    SellItem: NotRequired[str]
    Ship: str
    SellPrice: NotRequired[int]
    Slot: str
    BuyPrice: int
    SellItem_Localised: NotRequired[str]


# ReservoirReplenished: 33643 characters, 289 entries
class ReservoirReplenishedEvent(TypedDict):
    FuelReservoir: float
    FuelMain: float
    event: Literal["ReservoirReplenished"]
    timestamp: str


# ScanBaryCentre: 32932 characters, 94 entries
class ScanBaryCentreEvent(TypedDict):
    BodyID: int
    MeanAnomaly: float
    Eccentricity: float
    AscendingNode: float
    Periapsis: float
    SystemAddress: int
    StarSystem: str
    SemiMajorAxis: float
    event: Literal["ScanBaryCentre"]
    timestamp: str
    OrbitalPeriod: float
    OrbitalInclination: float


# Progress: 29002 characters, 164 entries
class ProgressEvent(TypedDict):
    Trade: int
    Exobiologist: int
    Federation: int
    Soldier: int
    Empire: int
    event: Literal["Progress"]
    CQC: Literal[0]
    timestamp: str
    Explore: int
    Combat: int


# Rank: 27552 characters, 164 entries
class RankEvent(TypedDict):
    Trade: Literal[4]
    Exobiologist: Literal[0]
    Federation: int
    Soldier: int
    Empire: int
    event: Literal["Rank"]
    CQC: Literal[0]
    timestamp: str
    Explore: int
    Combat: int


# Shipyard: 26333 characters, 180 entries
class ShipyardEvent(TypedDict):
    MarketID: int
    StationName: str
    StarSystem: str
    event: Literal["Shipyard"]
    timestamp: str


# Fileheader: 26026 characters, 154 entries
class FileheaderEvent(TypedDict):
    build: str
    Odyssey: bool
    language: Literal["English/UK"]
    event: Literal["Fileheader"]
    timestamp: str
    gameversion: str
    part: Literal[1]


# MassModuleStore: 24796 characters, 18 entries
class MassModuleStoreEventItemsItem(TypedDict):
    EngineerModifications: NotRequired[str]
    Level: NotRequired[int]
    Name_Localised: str
    Quality: NotRequired[float]
    Name: str
    Slot: str
    Hot: bool
class MassModuleStoreEvent(TypedDict):
    MarketID: int
    ShipID: int
    event: Literal["MassModuleStore"]
    timestamp: str
    Ship: str
    Items: list[MassModuleStoreEventItemsItem]


# Reputation: 23280 characters, 164 entries
class ReputationEvent(TypedDict):
    Alliance: float
    Federation: float
    Independent: float
    Empire: float
    event: Literal["Reputation"]
    timestamp: str


# ModuleSellRemote: 22618 characters, 88 entries
class ModuleSellRemoteEvent(TypedDict):
    StorageSlot: int
    Ship: str
    event: Literal["ModuleSellRemote"]
    ShipID: int
    SellItem: str
    timestamp: str
    SellPrice: int
    SellItem_Localised: str
    ServerId: int


# FactionKillBond: 20910 characters, 84 entries
class FactionKillBondEvent(TypedDict):
    AwardingFaction_Localised: NotRequired[Literal["Pilots' Federation"]]
    Reward: int
    VictimFaction: str
    event: Literal["FactionKillBond"]
    timestamp: str
    AwardingFaction: str
    VictimFaction_Localised: NotRequired[Literal["Thargoids"]]


# ModuleStore: 20653 characters, 69 entries
class ModuleStoreEvent(TypedDict):
    MarketID: int
    EngineerModifications: NotRequired[str]
    Level: NotRequired[int]
    StoredItem_Localised: str
    StoredItem: str
    Quality: NotRequired[float]
    event: Literal["ModuleStore"]
    ShipID: int
    timestamp: str
    Ship: str
    Slot: str
    Hot: bool


# NavRoute: 20340 characters, 339 entries
class NavRouteEvent(TypedDict):
    event: Literal["NavRoute"]
    timestamp: str


# SquadronStartup: 19397 characters, 163 entries
class SquadronStartupEvent(TypedDict):
    CurrentRank: int
    event: Literal["SquadronStartup"]
    timestamp: str
    SquadronName: Literal["NIGHTFALL NAVY"]


# Missions: 19087 characters, 169 entries
class MissionsEventFailedItem(TypedDict):
    PassengerMission: bool
    MissionID: int
    Expires: Literal[0]
    Name: Literal["Mission_AltruismCredits_name"]
class MissionsEventActiveItem(TypedDict):
    PassengerMission: bool
    MissionID: int
    Expires: int
    Name: str
class MissionsEvent(TypedDict):
    Complete: list[Any]
    Failed: list[MissionsEventFailedItem]
    Active: list[MissionsEventActiveItem]
    event: Literal["Missions"]
    timestamp: str


# RefuelAll: 18570 characters, 198 entries
class RefuelAllEvent(TypedDict):
    event: Literal["RefuelAll"]
    Cost: int
    timestamp: str
    Amount: float


# Commander: 18348 characters, 164 entries
class CommanderEvent(TypedDict):
    event: Literal["Commander"]
    FID: str
    timestamp: str
    Name: str


# ShieldState: 18316 characters, 222 entries
class ShieldStateEvent(TypedDict):
    ShieldsUp: bool
    event: Literal["ShieldState"]
    timestamp: str


# ModuleSell: 18296 characters, 71 entries
class ModuleSellEvent(TypedDict):
    MarketID: int
    Ship: str
    event: Literal["ModuleSell"]
    ShipID: int
    SellItem: str
    timestamp: str
    SellPrice: int
    Slot: str
    SellItem_Localised: str


# NavRouteClear: 15795 characters, 243 entries
class NavRouteClearEvent(TypedDict):
    event: Literal["NavRouteClear"]
    timestamp: str


# ShipyardSwap: 15067 characters, 78 entries
class ShipyardSwapEvent(TypedDict):
    MarketID: int
    StoreOldShip: str
    ShipType: str
    ShipID: int
    event: Literal["ShipyardSwap"]
    timestamp: str
    StoreShipID: int
    ShipType_Localised: NotRequired[str]


# USSDrop: 14999 characters, 94 entries
class USSDropEvent(TypedDict):
    USSThreat: int
    USSType_Localised: str
    event: Literal["USSDrop"]
    USSType: str
    timestamp: str


# ModuleInfo: 14260 characters, 230 entries
class ModuleInfoEvent(TypedDict):
    event: Literal["ModuleInfo"]
    timestamp: str


# Scanned: 11280 characters, 141 entries
class ScannedEvent(TypedDict):
    ScanType: Literal["Cargo"]
    event: Literal["Scanned"]
    timestamp: str


# ModuleSwap: 10945 characters, 32 entries
class ModuleSwapEvent(TypedDict):
    MarketID: int
    ToItem: str
    FromSlot: str
    ToSlot: str
    ToItem_Localised: NotRequired[str]
    event: Literal["ModuleSwap"]
    FromItem: str
    timestamp: str
    ShipID: int
    Ship: str
    FromItem_Localised: str


# FSSDiscoveryScan: 10934 characters, 58 entries
class FSSDiscoveryScanEvent(TypedDict):
    BodyCount: int
    Progress: float
    SystemAddress: int
    event: Literal["FSSDiscoveryScan"]
    timestamp: str
    SystemName: str
    NonBodyCount: int


# ApproachBody: 10788 characters, 68 entries
class ApproachBodyEvent(TypedDict):
    BodyID: int
    Body: str
    SystemAddress: int
    StarSystem: str
    event: Literal["ApproachBody"]
    timestamp: str


# Embark: 10458 characters, 35 entries
class EmbarkEventCrewItem(TypedDict):
    Role: str
    Name: str
class EmbarkEvent(TypedDict):
    MarketID: NotRequired[int]
    BodyID: int
    Taxi: bool
    Body: str
    Crew: NotRequired[list[EmbarkEventCrewItem]]
    StationName: NotRequired[str]
    SRV: bool
    OnPlanet: bool
    ID: NotRequired[int]
    SystemAddress: int
    StarSystem: str
    event: Literal["Embark"]
    OnStation: bool
    timestamp: str
    StationType: NotRequired[str]
    Multicrew: bool


# Disembark: 10456 characters, 35 entries
class DisembarkEvent(TypedDict):
    MarketID: NotRequired[int]
    BodyID: int
    Taxi: bool
    Body: str
    StationName: NotRequired[str]
    SRV: bool
    OnPlanet: bool
    ID: NotRequired[int]
    SystemAddress: int
    StarSystem: str
    event: Literal["Disembark"]
    OnStation: bool
    timestamp: str
    StationType: NotRequired[str]
    Multicrew: bool


# MiningRefined: 9838 characters, 68 entries
class MiningRefinedEvent(TypedDict):
    Type_Localised: str
    event: Literal["MiningRefined"]
    Type: str
    timestamp: str


# CommitCrime: 9781 characters, 60 entries
class CommitCrimeEvent(TypedDict):
    CrimeType: str
    Fine: NotRequired[int]
    Bounty: NotRequired[int]
    Victim: NotRequired[str]
    event: Literal["CommitCrime"]
    timestamp: str
    Faction: str
    Victim_Localised: NotRequired[str]


# HullDamage: 9373 characters, 80 entries
class HullDamageEvent(TypedDict):
    PlayerPilot: bool
    event: Literal["HullDamage"]
    Health: float
    timestamp: str
    Fighter: NotRequired[bool]


# Backpack: 9116 characters, 42 entries
class BackpackEventConsumablesItem(TypedDict):
    Count: int
    OwnerID: Literal[0]
    Name_Localised: str
    Name: str
class BackpackEvent(TypedDict):
    Consumables: list[BackpackEventConsumablesItem]
    Components: list[Any]
    event: Literal["Backpack"]
    timestamp: str
    Data: list[Any]
    Items: list[Any]


# ShipyardTransfer: 8616 characters, 31 entries
class ShipyardTransferEvent(TypedDict):
    MarketID: int
    TransferPrice: int
    System: str
    ShipMarketID: int
    ShipType: str
    ShipID: int
    event: Literal["ShipyardTransfer"]
    timestamp: str
    Distance: float
    ShipType_Localised: NotRequired[str]
    TransferTime: int


# DatalinkScan: 8240 characters, 40 entries
class DatalinkScanEvent(TypedDict):
    Message: Literal["$DATAPOINT_GAMEPLAY_complete;"]
    event: Literal["DatalinkScan"]
    timestamp: str
    Message_Localised: Literal["Alert: All Data Point telemetry links established, Intel package created."]


# SAASignalsFound: 7984 characters, 22 entries
class SAASignalsFoundEventSignalsItem(TypedDict):
    Type_Localised: NotRequired[str]
    Type: str
    Count: int
class SAASignalsFoundEventGenusesItem(TypedDict):
    Genus_Localised: Literal["Brain Trees"]
    Genus: Literal["$Codex_Ent_Brancae_Name;"]
class SAASignalsFoundEvent(TypedDict):
    BodyID: int
    Signals: list[SAASignalsFoundEventSignalsItem]
    Genuses: list[SAASignalsFoundEventGenusesItem]
    SystemAddress: int
    event: Literal["SAASignalsFound"]
    timestamp: str
    BodyName: str


# FSSAllBodiesFound: 7228 characters, 48 entries
class FSSAllBodiesFoundEvent(TypedDict):
    SystemAddress: int
    event: Literal["FSSAllBodiesFound"]
    timestamp: str
    SystemName: str
    Count: int


# DockingDenied: 7122 characters, 41 entries
class DockingDeniedEvent(TypedDict):
    MarketID: int
    StationName: str
    event: Literal["DockingDenied"]
    StationType: str
    timestamp: str
    Reason: str


# Liftoff: 6823 characters, 19 entries
class LiftoffEvent(TypedDict):
    BodyID: int
    Taxi: bool
    Body: str
    OnPlanet: bool
    SystemAddress: int
    Longitude: float
    StarSystem: str
    NearestDestination: NotRequired[str]
    event: Literal["Liftoff"]
    OnStation: bool
    PlayerControlled: bool
    timestamp: str
    Latitude: float
    NearestDestination_Localised: NotRequired[str]
    Multicrew: bool


# Touchdown: 6777 characters, 19 entries
class TouchdownEvent(TypedDict):
    BodyID: int
    Taxi: bool
    Body: str
    OnPlanet: bool
    SystemAddress: int
    Longitude: float
    StarSystem: str
    NearestDestination: NotRequired[str]
    event: Literal["Touchdown"]
    OnStation: bool
    PlayerControlled: bool
    timestamp: str
    Latitude: float
    NearestDestination_Localised: NotRequired[str]
    Multicrew: bool


# ModuleBuyAndStore: 6420 characters, 26 entries
class ModuleBuyAndStoreEvent(TypedDict):
    MarketID: int
    BuyItem_Localised: str
    BuyItem: str
    event: Literal["ModuleBuyAndStore"]
    ShipID: int
    timestamp: str
    Ship: str
    BuyPrice: int


# HeatWarning: 6363 characters, 101 entries
class HeatWarningEvent(TypedDict):
    event: Literal["HeatWarning"]
    timestamp: str


# RepairAll: 6182 characters, 82 entries
class RepairAllEvent(TypedDict):
    event: Literal["RepairAll"]
    Cost: int
    timestamp: str


# Shutdown: 5340 characters, 89 entries
class ShutdownEvent(TypedDict):
    event: Literal["Shutdown"]
    timestamp: str


# BackpackChange: 5101 characters, 27 entries
class BackpackChangeEventAddedItem(TypedDict):
    OwnerID: int
    Type: str
    Name_Localised: NotRequired[str]
    Name: str
    Count: int
class BackpackChangeEventRemovedItem(TypedDict):
    OwnerID: Literal[0]
    Type: Literal["Consumable"]
    Name_Localised: str
    Name: str
    Count: Literal[1]
class BackpackChangeEvent(TypedDict):
    Added: NotRequired[list[BackpackChangeEventAddedItem]]
    event: Literal["BackpackChange"]
    Removed: NotRequired[list[BackpackChangeEventRemovedItem]]
    timestamp: str


# BuyAmmo: 5025 characters, 69 entries
class BuyAmmoEvent(TypedDict):
    event: Literal["BuyAmmo"]
    Cost: int
    timestamp: str


# LeaveBody: 5001 characters, 32 entries
class LeaveBodyEvent(TypedDict):
    BodyID: int
    Body: str
    SystemAddress: int
    StarSystem: str
    event: Literal["LeaveBody"]
    timestamp: str


# BuyDrones: 3832 characters, 30 entries
class BuyDronesEvent(TypedDict):
    Type: Literal["Drones"]
    event: Literal["BuyDrones"]
    TotalCost: int
    timestamp: str
    BuyPrice: int
    Count: int


# EjectCargo: 3668 characters, 25 entries
class EjectCargoEvent(TypedDict):
    Abandoned: bool
    Type: str
    Type_Localised: str
    event: Literal["EjectCargo"]
    timestamp: str
    Count: int


# LaunchSRV: 3104 characters, 16 entries
class LaunchSRVEvent(TypedDict):
    SRVType: Literal["combat_multicrew_srv_01"]
    SRVType_Localised: Literal["SRV Scorpion"]
    ID: int
    event: Literal["LaunchSRV"]
    timestamp: str
    PlayerControlled: bool
    Loadout: Literal["default"]


# Interdicted: 3090 characters, 19 entries
class InterdictedEvent(TypedDict):
    Interdictor: NotRequired[str]
    IsThargoid: NotRequired[bool]
    IsPlayer: bool
    event: Literal["Interdicted"]
    timestamp: str
    Interdictor_Localised: NotRequired[Literal["System Defence Force"]]
    Faction: NotRequired[str]
    Submitted: bool


# NavBeaconScan: 3044 characters, 27 entries
class NavBeaconScanEvent(TypedDict):
    SystemAddress: int
    NumBodies: int
    event: Literal["NavBeaconScan"]
    timestamp: str


# Bounty: 3039 characters, 9 entries
class BountyEventRewardsItem(TypedDict):
    Reward: int
    Faction: str
class BountyEvent(TypedDict):
    VictimFaction: str
    PilotName_Localised: str
    TotalReward: int
    PilotName: str
    event: Literal["Bounty"]
    timestamp: str
    Target: str
    Rewards: list[BountyEventRewardsItem]
    Target_Localised: NotRequired[str]


# Screenshot: 3003 characters, 14 entries
class ScreenshotEvent(TypedDict):
    Body: str
    Heading: NotRequired[Literal[0]]
    System: str
    Longitude: NotRequired[float]
    Filename: str
    Height: Literal[1080]
    event: Literal["Screenshot"]
    Latitude: NotRequired[float]
    timestamp: str
    Width: int


# CodexEntry: 2955 characters, 6 entries
class CodexEntryEvent(TypedDict):
    SubCategory_Localised: Literal["Stars"]
    Category: Literal["$Codex_Category_StellarBodies;"]
    Category_Localised: Literal["Astronomical Bodies"]
    BodyID: int
    IsNewEntry: bool
    SubCategory: Literal["$Codex_SubCategory_Stars;"]
    Region_Localised: str
    Region: str
    System: str
    Name_Localised: str
    SystemAddress: int
    EntryID: int
    event: Literal["CodexEntry"]
    timestamp: str
    Name: str


# RedeemVoucher: 2477 characters, 17 entries
class RedeemVoucherEventFactionsItem(TypedDict):
    Faction: str
    Amount: int
class RedeemVoucherEvent(TypedDict):
    Type: str
    event: Literal["RedeemVoucher"]
    timestamp: str
    Amount: int
    Factions: NotRequired[list[RedeemVoucherEventFactionsItem]]
    Faction: NotRequired[str]
    BrokerPercentage: NotRequired[float]


# TechnologyBroker: 2377 characters, 3 entries
class TechnologyBrokerEventMaterialsItem(TypedDict):
    Count: int
    Category: str
    Name_Localised: NotRequired[str]
    Name: str
class TechnologyBrokerEventItemsunlockedItem(TypedDict):
    Name_Localised: str
    Name: str
class TechnologyBrokerEventCommoditiesItem(TypedDict):
    Count: int
    Name_Localised: str
    Name: str
class TechnologyBrokerEvent(TypedDict):
    MarketID: Literal[3223343616]
    BrokerType: Literal["guardian"]
    Materials: list[TechnologyBrokerEventMaterialsItem]
    ItemsUnlocked: list[TechnologyBrokerEventItemsunlockedItem]
    event: Literal["TechnologyBroker"]
    timestamp: str
    Commodities: list[TechnologyBrokerEventCommoditiesItem]


# Repair: 2315 characters, 16 entries
class RepairEvent(TypedDict):
    Items: list[str]
    event: Literal["Repair"]
    Cost: int
    timestamp: str


# RestockVehicle: 2295 characters, 14 entries
class RestockVehicleEvent(TypedDict):
    Cost: int
    Type: str
    ID: NotRequired[int]
    Type_Localised: NotRequired[str]
    event: Literal["RestockVehicle"]
    timestamp: str
    Loadout: str
    Count: int


# RepairDrone: 2267 characters, 23 entries
class RepairDroneEvent(TypedDict):
    CockpitRepaired: NotRequired[float]
    CorrosionRepaired: NotRequired[float]
    event: Literal["RepairDrone"]
    timestamp: str
    HullRepaired: float


# RebootRepair: 2172 characters, 25 entries
class RebootRepairEvent(TypedDict):
    Modules: list[str]
    event: Literal["RebootRepair"]
    timestamp: str


# DockSRV: 2160 characters, 15 entries
class DockSRVEvent(TypedDict):
    SRVType: Literal["combat_multicrew_srv_01"]
    SRVType_Localised: Literal["SRV Scorpion"]
    ID: int
    event: Literal["DockSRV"]
    timestamp: str


# CrewMemberRoleChange: 2001 characters, 15 entries
class CrewMemberRoleChangeEvent(TypedDict):
    Crew: str
    Telepresence: bool
    event: Literal["CrewMemberRoleChange"]
    timestamp: str
    Role: str


# CollectCargo: 1920 characters, 13 entries
class CollectCargoEvent(TypedDict):
    Type: str
    Type_Localised: str
    event: Literal["CollectCargo"]
    timestamp: str
    Stolen: bool


# Market: 1846 characters, 10 entries
class MarketEvent(TypedDict):
    MarketID: int
    StationName: str
    StarSystem: str
    CarrierDockingAccess: NotRequired[Literal["all"]]
    StationType: str
    event: Literal["Market"]
    timestamp: str


# Synthesis: 1620 characters, 9 entries
class SynthesisEventMaterialsItem(TypedDict):
    Count: int
    Name: str
class SynthesisEvent(TypedDict):
    Materials: list[SynthesisEventMaterialsItem]
    event: Literal["Synthesis"]
    timestamp: str
    Name: str


# SwitchSuitLoadout: 1613 characters, 2 entries
class SwitchSuitLoadoutEventModulesItem(TypedDict):
    WeaponMods: list[str]
    SlotName: str
    Class: int
    SuitModuleID: int
    ModuleName_Localised: str
    ModuleName: str
class SwitchSuitLoadoutEvent(TypedDict):
    SuitMods: list[str]
    Modules: list[SwitchSuitLoadoutEventModulesItem]
    SuitName: str
    LoadoutName: str
    LoadoutID: int
    event: Literal["SwitchSuitLoadout"]
    SuitID: int
    timestamp: str
    SuitName_Localised: str


# MissionRedirected: 1342 characters, 4 entries
class MissionRedirectedEvent(TypedDict):
    MissionID: int
    LocalisedName: str
    NewDestinationStation: str
    OldDestinationSystem: str
    event: Literal["MissionRedirected"]
    OldDestinationStation: str
    timestamp: str
    Name: str
    NewDestinationSystem: str


# MaterialDiscovered: 1295 characters, 7 entries
class MaterialDiscoveredEvent(TypedDict):
    Category: str
    DiscoveryNumber: int
    Name_Localised: NotRequired[str]
    event: Literal["MaterialDiscovered"]
    timestamp: str
    Name: str


# Friends: 1217 characters, 12 entries
class FriendsEvent(TypedDict):
    Status: str
    event: Literal["Friends"]
    timestamp: str
    Name: str


# DataScanned: 1178 characters, 12 entries
class DataScannedEvent(TypedDict):
    Type_Localised: NotRequired[Literal["Ancient Codex"]]
    event: Literal["DataScanned"]
    Type: str
    timestamp: str


# BookTaxi: 1145 characters, 7 entries
class BookTaxiEvent(TypedDict):
    Cost: int
    event: Literal["BookTaxi"]
    timestamp: str
    DestinationSystem: str
    DestinationLocation: str


# CrewLaunchFighter: 1025 characters, 9 entries
class CrewLaunchFighterEvent(TypedDict):
    Crew: str
    event: Literal["CrewLaunchFighter"]
    timestamp: str
    Telepresence: bool


# LaunchFighter: 955 characters, 8 entries
class LaunchFighterEvent(TypedDict):
    ID: int
    event: Literal["LaunchFighter"]
    PlayerControlled: bool
    timestamp: str
    Loadout: Literal["one"]


# SendText: 949 characters, 6 entries
class SendTextEvent(TypedDict):
    Sent: bool
    To: str
    Message: str
    event: Literal["SendText"]
    timestamp: str


# SetUserShipName: 936 characters, 6 entries
class SetUserShipNameEvent(TypedDict):
    UserShipName: str
    UserShipId: str
    ShipID: int
    event: Literal["SetUserShipName"]
    timestamp: str
    Ship: str


# Resurrect: 921 characters, 8 entries
class ResurrectEvent(TypedDict):
    Cost: int
    Option: str
    Bankrupt: bool
    event: Literal["Resurrect"]
    timestamp: str


# WingAdd: 824 characters, 10 entries
class WingAddEvent(TypedDict):
    event: Literal["WingAdd"]
    timestamp: str
    Name: str


# SearchAndRescue: 751 characters, 4 entries
class SearchAndRescueEvent(TypedDict):
    MarketID: Literal[128819092]
    Reward: int
    Name_Localised: str
    event: Literal["SearchAndRescue"]
    timestamp: str
    Name: str
    Count: int


# Died: 744 characters, 8 entries
class DiedEvent(TypedDict):
    KillerShip: NotRequired[str]
    KillerName: NotRequired[Literal["Elvis Sims"]]
    event: Literal["Died"]
    timestamp: str
    KillerRank: NotRequired[str]


# SellMicroResources: 744 characters, 3 entries
class SellMicroResourcesEventMicroresourcesItem(TypedDict):
    Count: Literal[1]
    Category: Literal["Data"]
    Name_Localised: str
    Name: str
class SellMicroResourcesEvent(TypedDict):
    MarketID: Literal[128016640]
    Price: int
    TotalCount: Literal[1]
    event: Literal["SellMicroResources"]
    timestamp: str
    MicroResources: list[SellMicroResourcesEventMicroresourcesItem]


# WingJoin: 740 characters, 10 entries
class WingJoinEvent(TypedDict):
    Others: list[Any]
    event: Literal["WingJoin"]
    timestamp: str


# SystemsShutdown: 670 characters, 10 entries
class SystemsShutdownEvent(TypedDict):
    event: Literal["SystemsShutdown"]
    timestamp: str


# MarketSell: 645 characters, 3 entries
class MarketSellEvent(TypedDict):
    MarketID: int
    TotalSale: int
    Type: str
    Type_Localised: NotRequired[Literal["Low Temp. Diamonds"]]
    event: Literal["MarketSell"]
    timestamp: str
    SellPrice: int
    AvgPricePaid: Literal[0]
    Count: int


# CrewAssign: 635 characters, 5 entries
class CrewAssignEvent(TypedDict):
    CrewID: Literal[31464544]
    event: Literal["CrewAssign"]
    timestamp: str
    Name: Literal["George Roberson"]
    Role: Literal["Active"]


# MarketBuy: 627 characters, 3 entries
class MarketBuyEvent(TypedDict):
    MarketID: Literal[3701734400]
    Type: str
    Type_Localised: str
    event: Literal["MarketBuy"]
    timestamp: str
    TotalCost: int
    BuyPrice: int
    Count: int


# HeatDamage: 620 characters, 10 entries
class HeatDamageEvent(TypedDict):
    event: Literal["HeatDamage"]
    timestamp: str


# WingLeave: 610 characters, 10 entries
class WingLeaveEvent(TypedDict):
    event: Literal["WingLeave"]
    timestamp: str


# SAAScanComplete: 609 characters, 3 entries
class SAAScanCompleteEvent(TypedDict):
    BodyID: Literal[7]
    SystemAddress: Literal[40525700549504]
    ProbesUsed: Literal[1]
    event: Literal["SAAScanComplete"]
    timestamp: str
    EfficiencyTarget: Literal[0]
    BodyName: Literal["Col 285 Sector CC-K a38-2 1 B Ring"]


# ShipyardSell: 581 characters, 3 entries
class ShipyardSellEvent(TypedDict):
    MarketID: Literal[3230669312]
    System: NotRequired[Literal["Laksak"]]
    ShipMarketID: NotRequired[Literal[3230427392]]
    ShipType: str
    ShipPrice: int
    event: Literal["ShipyardSell"]
    timestamp: str
    SellShipID: int
    ShipType_Localised: NotRequired[str]


# PayFines: 570 characters, 4 entries
class PayFinesEvent(TypedDict):
    AllFines: bool
    event: Literal["PayFines"]
    ShipID: int
    timestamp: str
    Amount: int
    Faction: NotRequired[str]
    BrokerPercentage: NotRequired[float]


# UseConsumable: 568 characters, 4 entries
class UseConsumableEvent(TypedDict):
    Type: Literal["Consumable"]
    Name_Localised: Literal["Energy Cell"]
    event: Literal["UseConsumable"]
    timestamp: str
    Name: Literal["energycell"]


# Promotion: 534 characters, 7 entries
class PromotionEvent(TypedDict):
    Federation: NotRequired[int]
    Empire: NotRequired[int]
    event: Literal["Promotion"]
    timestamp: str
    Combat: NotRequired[Literal[5]]


# ShipyardRedeem: 532 characters, 3 entries
class ShipyardRedeemEvent(TypedDict):
    MarketID: int
    ShipType: str
    event: Literal["ShipyardRedeem"]
    timestamp: str
    BundleID: int
    ShipType_Localised: str


# EngineerContribution: 527 characters, 2 entries
class EngineerContributionEvent(TypedDict):
    Material_Localised: str
    Quantity: Literal[50]
    EngineerID: int
    Material: str
    Engineer: str
    Type: Literal["Materials"]
    event: Literal["EngineerContribution"]
    timestamp: str
    TotalQuantity: Literal[50]


# MissionAbandoned: 518 characters, 3 entries
class MissionAbandonedEvent(TypedDict):
    MissionID: int
    LocalisedName: str
    event: Literal["MissionAbandoned"]
    timestamp: str
    Name: str


# VehicleSwitch: 507 characters, 6 entries
class VehicleSwitchEvent(TypedDict):
    To: str
    event: Literal["VehicleSwitch"]
    timestamp: str


# FighterRebuilt: 470 characters, 5 entries
class FighterRebuiltEvent(TypedDict):
    Loadout: Literal["one"]
    event: Literal["FighterRebuilt"]
    ID: int
    timestamp: str


# FighterDestroyed: 468 characters, 6 entries
class FighterDestroyedEvent(TypedDict):
    ID: int
    event: Literal["FighterDestroyed"]
    timestamp: str


# DockingCancelled: 465 characters, 3 entries
class DockingCancelledEvent(TypedDict):
    MarketID: Literal[128829079]
    StationName: Literal["The Heart of Orion"]
    StationType: Literal["MegaShip"]
    event: Literal["DockingCancelled"]
    timestamp: str


# ShipyardBuy: 450 characters, 2 entries
class ShipyardBuyEvent(TypedDict):
    MarketID: int
    StoreOldShip: str
    ShipType: str
    ShipPrice: int
    event: Literal["ShipyardBuy"]
    timestamp: str
    StoreShipID: int
    ShipType_Localised: str


# ShipRedeemed: 436 characters, 3 entries
class ShipRedeemedEvent(TypedDict):
    ShipType: str
    event: Literal["ShipRedeemed"]
    timestamp: str
    ShipType_Localised: str
    NewShipID: int


# SellDrones: 388 characters, 3 entries
class SellDronesEvent(TypedDict):
    TotalSale: int
    Type: Literal["Drones"]
    event: Literal["SellDrones"]
    SellPrice: int
    timestamp: str
    Count: int


# MissionFailed: 359 characters, 2 entries
class MissionFailedEvent(TypedDict):
    MissionID: int
    LocalisedName: str
    event: Literal["MissionFailed"]
    timestamp: Literal["2024-09-16T19:27:27Z"]
    Name: Literal["Mission_AltruismCredits_name"]


# CrewMemberJoins: 337 characters, 3 entries
class CrewMemberJoinsEvent(TypedDict):
    Crew: str
    event: Literal["CrewMemberJoins"]
    timestamp: str
    Telepresence: bool


# CockpitBreached: 335 characters, 5 entries
class CockpitBreachedEvent(TypedDict):
    event: Literal["CockpitBreached"]
    timestamp: str


# PowerplaySalary: 327 characters, 3 entries
class PowerplaySalaryEvent(TypedDict):
    Power: Literal["Aisling Duval"]
    event: Literal["PowerplaySalary"]
    timestamp: str
    Amount: int


# EndCrewSession: 318 characters, 3 entries
class EndCrewSessionEvent(TypedDict):
    event: Literal["EndCrewSession"]
    OnCrime: bool
    timestamp: str
    Telepresence: bool


# ShipyardNew: 296 characters, 2 entries
class ShipyardNewEvent(TypedDict):
    ShipType: str
    event: Literal["ShipyardNew"]
    timestamp: str
    ShipType_Localised: str
    NewShipID: int


# DockFighter: 219 characters, 3 entries
class DockFighterEvent(TypedDict):
    ID: int
    event: Literal["DockFighter"]
    timestamp: str


# BuyMicroResources: 200 characters, 1 entries
class BuyMicroResourcesEvent(TypedDict):
    MarketID: Literal[128016640]
    Category: Literal["Consumable"]
    Price: Literal[1000]
    Name_Localised: Literal["Energy Cell"]
    event: Literal["BuyMicroResources"]
    timestamp: Literal["2024-07-22T19:14:03Z"]
    Name: Literal["energycell"]
    Count: Literal[1]


# SRVDestroyed: 149 characters, 1 entries
class SRVDestroyedEvent(TypedDict):
    SRVType: Literal["combat_multicrew_srv_01"]
    SRVType_Localised: Literal["SRV Scorpion"]
    ID: Literal[93]
    event: Literal["SRVDestroyed"]
    timestamp: Literal["2024-07-27T19:00:08Z"]


# DiscoveryScan: 111 characters, 1 entries
class DiscoveryScanEvent(TypedDict):
    SystemAddress: Literal[40525700549504]
    Bodies: Literal[1]
    event: Literal["DiscoveryScan"]
    timestamp: Literal["2024-07-28T14:59:08Z"]


# CrewMemberQuits: 108 characters, 1 entries
class CrewMemberQuitsEvent(TypedDict):
    Crew: Literal["Avigoku"]
    event: Literal["CrewMemberQuits"]
    timestamp: Literal["2024-07-07T17:43:00Z"]
    Telepresence: bool


# PowerplayJoin: 91 characters, 1 entries
class PowerplayJoinEvent(TypedDict):
    Power: Literal["Aisling Duval"]
    event: Literal["PowerplayJoin"]
    timestamp: Literal["2024-07-26T21:39:13Z"]


# JetConeBoost: 83 characters, 1 entries
class JetConeBoostEvent(TypedDict):
    event: Literal["JetConeBoost"]
    BoostValue: float
    timestamp: Literal["2024-08-02T21:14:32Z"]


# MaterialDiscarded: 744 characters, 3 entries
class MaterialDiscardedEvent(TypedDict):
    Category: str
    Name_Localised: NotRequired[str]
    Name: str
    Count: int
    event: Literal["MaterialDiscarded"]
    timestamp: str


# BuyExplorationData: 751 characters, 4 entries
class BuyExplorationDataEvent(TypedDict):
    System: str
    Cost: int
    event: Literal["BuyExplorationData"]
    timestamp: str


# SellExplorationData: 645 characters, 3 entries
class SellExplorationDataEvent(TypedDict):
    Systems: list[str]
    Discovered: list[str]
    BaseValue: int
    Bonus: int
    TotalEarnings: int
    event: Literal["SellExplorationData"]
    timestamp: str


# FSSBodySignals: 635 characters, 5 entries
class FSSBodySignalsEvent(TypedDict):
    BodyID: int
    BodyName: str
    SystemAddress: int
    Signals: list[Any]
    event: Literal["FSSBodySignals"]
    timestamp: str


# DockingTimeout: 570 characters, 4 entries
class DockingTimeoutEvent(TypedDict):
    StationName: str
    event: Literal["DockingTimeout"]
    timestamp: str


AnyEvent = StoredModulesEvent | ShipLockerEvent | LoadoutEvent | FSSSignalDiscoveredEvent | MaterialsEvent | ScanEvent | FSDJumpEvent | StatisticsEvent | ReceiveTextEvent | MusicEvent | EngineerProgressEvent | LocationEvent | EngineerCraftEvent | UnderAttackEvent | StoredShipsEvent | DockedEvent | ShipTargetedEvent | MissionCompletedEvent | StartJumpEvent | ProspectedAsteroidEvent | FSDTargetEvent | NpcCrewPaidWageEvent | ModuleRetrieveEvent | MaterialCollectedEvent | MissionAcceptedEvent | SupercruiseExitEvent | CargoEvent | LaunchDroneEvent | LoadGameEvent | FetchRemoteModuleEvent | ApproachSettlementEvent | DockingRequestedEvent | MaterialTradeEvent | UndockedEvent | SupercruiseDestinationDropEvent | OutfittingEvent | SupercruiseEntryEvent | DockingGrantedEvent | FuelScoopEvent | PowerplayEvent | MultiSellExplorationDataEvent | SuitLoadoutEvent | ModuleBuyEvent | ReservoirReplenishedEvent | ScanBaryCentreEvent | ProgressEvent | RankEvent | ShipyardEvent | FileheaderEvent | MassModuleStoreEvent | ReputationEvent | ModuleSellRemoteEvent | FactionKillBondEvent | ModuleStoreEvent | NavRouteEvent | SquadronStartupEvent | MissionsEvent | RefuelAllEvent | CommanderEvent | ShieldStateEvent | ModuleSellEvent | NavRouteClearEvent | ShipyardSwapEvent | USSDropEvent | ModuleInfoEvent | ScannedEvent | ModuleSwapEvent | FSSDiscoveryScanEvent | ApproachBodyEvent | EmbarkEvent | DisembarkEvent | MiningRefinedEvent | CommitCrimeEvent | HullDamageEvent | BackpackEvent | ShipyardTransferEvent | DatalinkScanEvent | SAASignalsFoundEvent | FSSAllBodiesFoundEvent | DockingDeniedEvent | LiftoffEvent | TouchdownEvent | ModuleBuyAndStoreEvent | HeatWarningEvent | RepairAllEvent | ShutdownEvent | BackpackChangeEvent | BuyAmmoEvent | LeaveBodyEvent | BuyDronesEvent | EjectCargoEvent | LaunchSRVEvent | InterdictedEvent | NavBeaconScanEvent | BountyEvent | ScreenshotEvent | CodexEntryEvent | RedeemVoucherEvent | TechnologyBrokerEvent | RepairEvent | RestockVehicleEvent | RepairDroneEvent | RebootRepairEvent | DockSRVEvent | CrewMemberRoleChangeEvent | CollectCargoEvent | MarketEvent | SynthesisEvent | SwitchSuitLoadoutEvent | MissionRedirectedEvent | MaterialDiscoveredEvent | FriendsEvent | DataScannedEvent | BookTaxiEvent | CrewLaunchFighterEvent | LaunchFighterEvent | SendTextEvent | SetUserShipNameEvent | ResurrectEvent | WingAddEvent | SearchAndRescueEvent | DiedEvent | SellMicroResourcesEvent | WingJoinEvent | SystemsShutdownEvent | MarketSellEvent | CrewAssignEvent | MarketBuyEvent | HeatDamageEvent | WingLeaveEvent | SAAScanCompleteEvent | ShipyardSellEvent | PayFinesEvent | UseConsumableEvent | PromotionEvent | ShipyardRedeemEvent | EngineerContributionEvent | MissionAbandonedEvent | VehicleSwitchEvent | FighterRebuiltEvent | FighterDestroyedEvent | DockingCancelledEvent | ShipyardBuyEvent | ShipRedeemedEvent | SellDronesEvent | MissionFailedEvent | CrewMemberJoinsEvent | CockpitBreachedEvent | PowerplaySalaryEvent | EndCrewSessionEvent | ShipyardNewEvent | DockFighterEvent | BuyMicroResourcesEvent | SRVDestroyedEvent | DiscoveryScanEvent | CrewMemberQuitsEvent | PowerplayJoinEvent | JetConeBoostEvent | MaterialDiscardedEvent | BuyExplorationDataEvent | SellExplorationDataEvent | FSSBodySignalsEvent | ScanBaryCentreEvent | DockingTimeoutEvent
