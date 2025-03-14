from datetime import timedelta, datetime
from functools import lru_cache
from typing import Any, cast, Dict

import yaml
import requests
import humanize

from lib.EventModels import (
    ApproachBodyEvent, ApproachSettlementEvent, BookTaxiEvent, BountyEvent, BuyExplorationDataEvent, CodexEntryEvent, CommanderEvent, CommitCrimeEvent,
    CrewAssignEvent, CrewLaunchFighterEvent, CrewMemberJoinsEvent, CrewMemberQuitsEvent, CrewMemberRoleChangeEvent,
    DataScannedEvent, DatalinkScanEvent, DiedEvent, DisembarkEvent, DiscoveryScanEvent, DockedEvent, DockFighterEvent,
    DockingCancelledEvent, DockingDeniedEvent, DockingGrantedEvent, DockingRequestedEvent, DockingTimeoutEvent, DockSRVEvent, EjectCargoEvent, EmbarkEvent,
    EndCrewSessionEvent, FactionKillBondEvent, FighterDestroyedEvent, FighterRebuiltEvent, FriendsEvent,
    FSSAllBodiesFoundEvent, FSSBodySignalsEvent, FSSDiscoveryScanEvent, FSSSignalDiscoveredEvent, FSDJumpEvent, FSDTargetEvent, HullDamageEvent, InterdictedEvent,
    LaunchDroneEvent, LaunchFighterEvent, LaunchSRVEvent, LeaveBodyEvent, LiftoffEvent, LoadGameEvent, LocationEvent,
    MaterialCollectedEvent, MaterialDiscardedEvent, MaterialDiscoveredEvent, MissionAbandonedEvent, MissionAcceptedEvent, MissionCompletedEvent, MissionFailedEvent, MissionRedirectedEvent,
    MiningRefinedEvent, MissionsEvent, MultiSellExplorationDataEvent, NavBeaconScanEvent, OutfittingEvent, PayFinesEvent, PowerplayJoinEvent,
    PromotionEvent, ProspectedAsteroidEvent, ReceiveTextEvent, RebootRepairEvent, RedeemVoucherEvent, ResurrectEvent,
    SAASignalsFoundEvent, SAAScanCompleteEvent, ScanBaryCentreEvent, ScanEvent, ScreenshotEvent, SellExplorationDataEvent, SendTextEvent, ShieldStateEvent, ShipTargetedEvent, ShipyardBuyEvent,
    ShipyardSellEvent, ShipyardSwapEvent, ShipyardTransferEvent, SRVDestroyedEvent, StartJumpEvent,
    SupercruiseDestinationDropEvent, SupercruiseEntryEvent, SupercruiseExitEvent, SuitLoadoutEvent,
    SwitchSuitLoadoutEvent, TouchdownEvent, UnderAttackEvent, UndockedEvent, UseConsumableEvent, WingAddEvent,
    WingJoinEvent, WingLeaveEvent
)

from .Projections import LocationState, MissionsState, ShipInfoState, NavInfo, TargetState, CurrentStatus

from .EDJournal import *
from .Event import (
    GameEvent,
    Event,
    ConversationEvent,
    StatusEvent,
    ToolEvent,
    ExternalEvent,
    ProjectedEvent,
)
from .Logger import log

# Game events categorized according to Config.py structure
systemEvents = {
    # "Cargo": "Commander {commanderName} has updated their cargo inventory.",
    # "ClearSavedGame": "Commander {commanderName} has reset their game.",
    "LoadGame": "Commander {commanderName} has loaded the game.",
    "NewCommander": "Commander {commanderName} has started a new game.",
    # "Materials": "Commander {commanderName} has updated their materials inventory.",
    "Missions": "Commander {commanderName} has updated their missions.",
    # "Progress": "Commander {commanderName} has made progress in various activities.",
    # "Rank": "Commander {commanderName} has updated their ranks.",
    # "Reputation": "Commander {commanderName} has updated their reputation.",
    "Statistics": "Commander {commanderName} has updated their statistics.",
    "Shutdown": "Commander {commanderName} has initiated a shutdown.",
    # "SquadronStartup": "Commander {commanderName} is a member of a squadron.",
    # "EngineerProgress": "Commander {commanderName} has made progress with an engineer.",
}

combatEvents = {
    "Bounty": "Commander {commanderName} has eliminated a hostile.",
    "Died": "Commander {commanderName} has lost consciousness.",
    "Resurrect": "Commander {commanderName} has resurrected.",
    "WeaponSelected": "Commander {commanderName} has selected a weapon.",
    "OutofDanger": "Commander {commanderName} is no longer in danger.",
    "InDanger": "Commander {commanderName} is in danger.",
    "LegalStateChanged": "Commander {commanderName}'s legal state has changed.",
    "CommitCrime": "Commander {commanderName} has committed a crime.",
    "CapShipBond": "Commander {commanderName} has been rewarded for taking part in a capital ship combat.",
    "Interdiction": "Commander {commanderName} has attempted an interdiction.",
    "Interdicted": "Commander {commanderName} is being interdicted.",
    "EscapeInterdiction": "Commander {commanderName} has escaped the interdiction.",
    "FactionKillBond": "Commander {commanderName} has eliminated a hostile.",
    "FighterDestroyed": "A ship-launched fighter was destroyed.",
    "HeatDamage": "Commander {commanderName} is taking heat damage.",
    "HeatWarning": "Commander {commanderName}'s ship's heat has exceeded 100%.",
    "HullDamage": "Commander {commanderName} is taking hull damage.",
    "PVPKill": "Commander {commanderName} has eliminated another commander.",
    "ShieldState": "Commander {commanderName}'s shield state has changed.",
    "ShipTargetted": "Commander {commanderName} is targeting a ship.",
    "UnderAttack": "Commander {commanderName} is under attack.",
    "CockpitBreached": "Commander {commanderName} has experienced a cockpit breach.",
    "CrimeVictim": "Commander {commanderName} has been victimized.",
    "SystemsShutdown": "Commander {commanderName}'s systems have been shut down forcefully.",
    "SelfDestruct": "Commander {commanderName} has initiated self destruct.",
}

tradingEvents = {
    "Trade": "Commander {commanderName} has performed a trade.",
    "BuyTradeData": "Commander {commanderName} has bought trade data.",
    "CollectCargo": "Commander {commanderName} has collected cargo.",
    "EjectCargo": "Commander {commanderName} has ejected cargo.",
    "MarketBuy": "Commander {commanderName} has bought market goods.",
    "MarketSell": "Commander {commanderName} has sold market goods.",
    "CargoTransfer": "Commander {commanderName} has transferred cargo.",
    "Market": "Commander {commanderName} has interacted with a market.",
}

miningEvents = {
    "AsteroidCracked": "Commander {commanderName} has cracked an asteroid.",
    "MiningRefined": "Commander {commanderName} has refined a resource.",
    "ProspectedAsteroid": "Commander {commanderName} has prospected an asteroid. Only inform about the most interesting material.",
    "LaunchDrone": "Commander {commanderName} has launched a drone.",
}

shipUpdateEvents = {
    "FSDJump": "Commander {commanderName} has initiated a hyperjump to another system.",
    "FSDTarget": "Commander {commanderName} has selected a star system to jump to.",
    "StartJump": "Commander {commanderName} starts the hyperjump.",
    "SupercruiseEntry": "Commander {commanderName} has entered supercruise from normal space.",
    "SupercruiseExit": "Commander {commanderName} has exited supercruise and returned to normal space.",
    "ApproachSettlement": "Commander {commanderName} is approaching settlement.",
    "Docked": "Commander {commanderName} has docked with a station.",
    "Undocked": "Commander {commanderName} has undocked from a station.",
    "DockingCanceled": "Commander {commanderName} has canceled the docking request.",
    "DockingDenied": "Commander {commanderName}'s request to dock with a station has been denied.",
    "DockingGranted": "Commander {commanderName}'s request to dock with a station has been granted.",
    "DockingRequested": "Commander {commanderName} has sent a request to dock with a station.",
    "DockingTimeout": "Commander {commanderName}'s request to dock with a station has timed out.",
    "NavRoute": "Commander {commanderName} has planned a new nav route.",
    "NavRouteClear": "Commander {commanderName} has cleared the nav route.",
    "CrewLaunchFighter": "Commander {commanderName} has launched a fighter.",
    "VehicleSwitch": "Commander {commanderName} has switched vehicle.",
    "LaunchFighter": "Commander {commanderName} has launched a fighter.",
    "DockFighter": "Commander {commanderName} has docked a fighter.",
    "FighterRebuilt": "Commander {commanderName} has rebuilt a fighter.",
    "FuelScoop": "Commander {commanderName} has scooped fuel.",
    "RebootRepair": "Commander {commanderName} has initiated a reboot/repair.",
    "RepairDrone": "Commander {commanderName} has repaired using a drone.",
    "AfmuRepairs": "Commander {commanderName} has conducted repairs.",
    "ModuleInfo": "Commander {commanderName} has received module info.",
    "Synthesis": "Commander {commanderName} has performed synthesis.",
    "JetConeBoost": "Commander {commanderName} has executed a jet cone boost.",
    "JetConeDamage": "Commander {commanderName} has received damage from a jet cone.",
    "LandingGearUp": "Commander {commanderName} has raised the landing gear.",
    "LandingGearDown": "Commander {commanderName} has lowered the landing gear.",
    "FlightAssistOn": "Commander {commanderName} has turned flight assist on.",
    "FlightAssistOff": "Commander {commanderName} has turned flight assist off.",
    "HardpointsRetracted": "Commander {commanderName} has retracted hardpoints.",
    "HardpointsDeployed": "Commander {commanderName} has deployed hardpoints.",
    "LightsOff": "Commander {commanderName} has turned off the lights.",
    "LightsOn": "Commander {commanderName} has turned on the lights.",
    "CargoScoopRetracted": "Commander {commanderName} has retracted the cargo scoop.",
    "CargoScoopDeployed": "Commander {commanderName} has deployed the cargo scoop.",
    "SilentRunningOff": "Commander {commanderName} has turned off silent running.",
    "SilentRunningOn": "Commander {commanderName} has turned on silent running.",
    "FuelScoopStarted": "Commander {commanderName} has started scooping fuel.",
    "FuelScoopEnded": "Commander {commanderName} has stopped scooping fuel.",
    "FsdMassLockEscaped": "Commander {commanderName} has escaped mass lock.",
    "FsdMassLocked": "Commander {commanderName} is mass locked.",
    "LowFuelWarningCleared": "Commander {commanderName}'s low fuel warning has cleared.",
    "LowFuelWarning": "Commander {commanderName} is running low on fuel.",
    "NightVisionOff": "Commander {commanderName} has turned off night vision.",
    "NightVisionOn": "Commander {commanderName} has turned on night vision.",
    "SupercruiseDestinationDrop": "Commander {commanderName} has dropped out at a supercruise destination.",
}

srvUpdateEvents = {
    "LaunchSRV": "Commander {commanderName} has launched an SRV.",
    "DockSRV": "Commander {commanderName} has docked an SRV.",
    "SRVDestroyed": "Commander {commanderName}'s SRV was destroyed.",
    "SrvHandbrakeOff": "Commander {commanderName} has released the SRV handbrake.",
    "SrvHandbrakeOn": "Commander {commanderName} has applied the SRV handbrake.",
    "SrvTurretViewConnected": "Commander {commanderName} has connected to the SRV turret view.",
    "SrvTurretViewDisconnected": "Commander {commanderName} has disconnected from the SRV turret view.",
    "SrvDriveAssistOff": "Commander {commanderName} has turned off SRV drive assist.",
    "SrvDriveAssistOn": "Commander {commanderName} has turned on SRV drive assist.",
}

onFootUpdateEvents = {
    "Disembark": "Commander {commanderName} has disembarked.",
    "Embark": "Commander {commanderName} has embarked.",
    "BookDropship": "Commander {commanderName} has booked a dropship.",
    "BookTaxi": "Commander {commanderName} has booked a taxi.",
    "CancelDropship": "Commander {commanderName} has cancelled a dropship booking.",
    "CancelTaxi": "Commander {commanderName} has cancelled a taxi booking.",
    "CollectItems": "Commander {commanderName} has collected items.",
    "DropItems": "Commander {commanderName} has dropped items.",
    "BackpackChange": "Commander {commanderName} has changed items in their backpack.",
    "BuyMicroResources": "Commander {commanderName} has bought micro resources.",
    "SellMicroResources": "Commander {commanderName} has sold micro resources.",
    "TransferMicroResources": "Commander {commanderName} has transferred micro resources.",
    "TradeMicroResources": "Commander {commanderName} has traded micro resources.",
    "BuySuit": "Commander {commanderName} has bought a suit.",
    "BuyWeapon": "Commander {commanderName} has bought a weapon.",
    "SellWeapon": "Commander {commanderName} has sold a weapon.",
    "UpgradeSuit": "Commander {commanderName} has upgraded a suit.",
    "UpgradeWeapon": "Commander {commanderName} has upgraded a weapon.",
    "CreateSuitLoadout": "Commander {commanderName} has created a suit loadout.",
    "DeleteSuitLoadout": "Commander {commanderName} has deleted a suit loadout.",
    "RenameSuitLoadout": "Commander {commanderName} has renamed a suit loadout.",
    "SwitchSuitLoadout": "Commander {commanderName} has switched to suit loadout.",
    "UseConsumable": "Commander {commanderName} has used a consumable.",
    "FCMaterials": "Commander {commanderName} has managed fleet carrier materials.",
    "LoadoutEquipModule": "Commander {commanderName} has equipped a module in suit loadout.",
    "LoadoutRemoveModule": "Commander {commanderName} has removed a module from suit loadout.",
    "ScanOrganic": "Commander {commanderName} has scanned organic life.",
    "SellOrganicData": "Commander {commanderName} has sold organic data.",
    "LowOxygenWarningCleared": "Commander {commanderName}'s low oxygen warning has cleared.",
    "LowOxygenWarning": "Commander {commanderName} is running low on oxygen.",
    "LowHealthWarningCleared": "Commander {commanderName}'s low health warning has cleared.", 
    "LowHealthWarning": "Commander {commanderName}'s health is critically low.",
    "BreathableAtmosphereExited": "Commander {commanderName} has exited breathable atmosphere.",
    "BreathableAtmosphereEntered": "Commander {commanderName} has entered breathable atmosphere.",
    "GlideModeExited": "Commander {commanderName} has exited glide mode.",
    "GlideModeEntered": "Commander {commanderName} has entered glide mode.",
    "DropShipDeploy": "Commander {commanderName} has deployed their dropship.",
}

stationEvents = {
    "MissionAbandoned": "Commander {commanderName} has abandoned a mission.",
    "MissionAccepted": "Commander {commanderName} has accepted a mission.",
    "MissionCompleted": "Commander {commanderName} has completed a mission.",
    "MissionFailed": "Commander {commanderName} has failed a mission.",
    "MissionRedirected": "Commander {commanderName}'s mission is now completed. Rewards are now available.",
    "StationServices": "Commander {commanderName} has accessed station services.",
    "ShipyardBuy": "Commander {commanderName} has bought a ship.",
    "ShipyardNew": "Commander {commanderName} has acquired a new ship.",
    "ShipyardSell": "Commander {commanderName} has sold a ship.",
    "ShipyardTransfer": "Commander {commanderName} has transferred a ship.",
    "ShipyardSwap": "Commander {commanderName} has swapped ships.",
    "StoredShips": "Commander {commanderName} has stored ships.",
    "ModuleBuy": "Commander {commanderName} has bought a module.",
    "ModuleRetrieve": "Commander {commanderName} has retrieved a module.",
    "ModuleSell": "Commander {commanderName} has sold a module.",
    "ModuleSellRemote": "Commander {commanderName} has sold a remote module.",
    "ModuleStore": "Commander {commanderName} has stored a module.",
    "ModuleSwap": "Commander {commanderName} has swapped modules.",
    "Outfitting": "Commander {commanderName} has visited an outfitting station.",
    "BuyAmmo": "Commander {commanderName} has bought ammunition.",
    "BuyDrones": "Commander {commanderName} has bought drones.",
    "RefuelAll": "Commander {commanderName} has refueled all.",
    "RefuelPartial": "Commander {commanderName} has partially refueled.",
    "Repair": "Commander {commanderName} has repaired.",
    "RepairAll": "Commander {commanderName} has repaired all.",
    "RestockVehicle": "Commander {commanderName} has restocked vehicle.",
    "FetchRemoteModule": "Commander {commanderName} has fetched a remote module.",
    "MassModuleStore": "Commander {commanderName} has mass stored modules.",
    "ClearImpound": "Commander {commanderName} has cleared an impound.",
    "CargoDepot": "Commander {commanderName} has completed a cargo depot operation.",
    "CommunityGoal": "Commander {commanderName} has engaged in a community goal.",
    "CommunityGoalDiscard": "Commander {commanderName} has discarded a community goal.",
    "CommunityGoalJoin": "Commander {commanderName} has joined a community goal.",
    "CommunityGoalReward": "Commander {commanderName} has received a reward for a community goal.",
    "EngineerContribution": "Commander {commanderName} has made a contribution to an engineer.",
    "EngineerCraft": "Commander {commanderName} has crafted a blueprint at an engineer.",
    "EngineerLegacyConvert": "Commander {commanderName} has converted a legacy blueprint at an engineer.",
    "MaterialTrade": "Commander {commanderName} has conducted a material trade.",
    "TechnologyBroker": "Commander {commanderName} has accessed a technology broker.",
    "PayBounties": "Commander {commanderName} has paid bounties.",
    "PayFines": "Commander {commanderName} has paid fines.",
    "PayLegacyFines": "Commander {commanderName} has paid legacy fines.",
    "RedeemVoucher": "Commander {commanderName} has redeemed a voucher.",
    "ScientificResearch": "Commander {commanderName} has conducted scientific research.",
    "Shipyard": "Commander {commanderName} has visited a shipyard.",
    "StoredModules": "Commander {commanderName} has stored modules.",
    "CarrierJump": "Commander {commanderName} has performed a carrier jump.",
    "CarrierBuy": "Commander {commanderName} has purchased a carrier.",
    "CarrierStats": "Commander {commanderName} has updated carrier stats.",
    "CarrierJumpRequest": "Commander {commanderName} has requested a carrier jump.",
    "CarrierDecommission": "Commander {commanderName} has decommissioned a carrier.",
    "CarrierCancelDecommission": "Commander {commanderName} has canceled the decommission of a carrier.",
    "CarrierBankTransfer": "Commander {commanderName} has performed a bank transfer for carrier.",
    "CarrierDepositFuel": "Commander {commanderName} has deposited fuel to carrier.",
    "CarrierCrewServices": "Commander {commanderName} has performed crew services on carrier.",
    "CarrierFinance": "Commander {commanderName} has reviewed finance details for carrier.",
    "CarrierShipPack": "Commander {commanderName} has managed ship pack for carrier.",
    "CarrierModulePack": "Commander {commanderName} has managed module pack for carrier.",
    "CarrierTradeOrder": "Commander {commanderName} has placed a trade order on carrier.",
    "CarrierDockingPermission": "Commander {commanderName} has updated docking permissions for carrier.",
    "CarrierNameChanged": "Commander {commanderName} has changed the name of carrier.",
    "CarrierJumpCancelled": "Commander {commanderName} has canceled a jump request for carrier.",
}

socialEvents = {
    "CrewAssign": "Commander {commanderName} has assigned a crew member.",
    "CrewFire": "Commander {commanderName} has fired a crew member.",
    "CrewHire": "Commander {commanderName} has hired a crew member.",
    "ChangeCrewRole": "Commander {commanderName} has changed crew role.",
    "CrewMemberJoins": "Commander {commanderName} has a new crew member.",
    "CrewMemberQuits": "Commander {commanderName} has lost a crew member.",
    "CrewMemberRoleChange": "Commander {commanderName} has changed a crew member's role.",
    "EndCrewSession": "Commander {commanderName} has ended a crew session.",
    "JoinACrew": "Commander {commanderName} has joined a crew.",
    "KickCrewMember": "Commander {commanderName} has kicked a crew member.",
    "QuitACrew": "Commander {commanderName} has quit a crew.",
    "NpcCrewPaidWage": "Commander {commanderName} has paid an NPC crew member.",
    "NpcCrewRank": "Commander {commanderName} has received NPC crew rank update.",
    "Promotion": "Commander {commanderName} has received a promotion.",
    "Friends": "The status of a friend of Commander {commanderName} has changed.",
    "WingAdd": "Commander {commanderName} has added to a wing.",
    "WingInvite": "Commander {commanderName} has received a wing invite.",
    "WingJoin": "Commander {commanderName} has joined a wing.",
    "WingLeave": "Commander {commanderName} has left a wing.",
    "SendText": "Commander {commanderName} has sent a text message.",
    "ReceiveText": "Commander {commanderName} has received a text message.",
    "AppliedToSquadron": "Commander {commanderName} applied to a squadron.",
    "DisbandedSquadron": "Commander {commanderName} disbanded a squadron.",
    "InvitedToSquadron": "Commander {commanderName} was invited to a squadron.",
    "JoinedSquadron": "Commander {commanderName} joined a squadron.",
    "KickedFromSquadron": "Commander {commanderName} was kicked from a squadron.",
    "LeftSquadron": "Commander {commanderName} left a squadron.",
    "SharedBookmarkToSquadron": "Commander {commanderName} shared a bookmark with a squadron.",
    "SquadronCreated": "A squadron was created by commander {commanderName}.",
    "SquadronDemotion": "Commander {commanderName} was demoted in a squadron.",
    "SquadronPromotion": "Commander {commanderName} was promoted in a squadron.",
    "WonATrophyForSquadron": "Commander {commanderName} won a trophy for a squadron.",
    "PowerplayCollect": "Commander {commanderName} collected powerplay commodities.",
    "PowerplayDefect": "Commander {commanderName} defected from one power to another.",
    "PowerplayDeliver": "Commander {commanderName} delivered powerplay commodities.",
    "PowerplayFastTrack": "Commander {commanderName} fast-tracked powerplay allocation.",
    "PowerplayJoin": "Commander {commanderName} joined a power.",
    "PowerplayLeave": "Commander {commanderName} left a power.",
    "PowerplaySalary": "Commander {commanderName} received salary payment from a power.",
    "PowerplayVote": "Commander {commanderName} voted for system expansion.",
    "PowerplayVoucher": "Commander {commanderName} received payment for powerplay combat.",
}

explorationEvents = {
    "CodexEntry": "Commander {commanderName} has logged a Codex entry.",
    "DiscoveryScan": "Commander {commanderName} has performed a discovery scan.",
    "Scan": "Commander {commanderName} has conducted a scan.",
    "FSSAllBodiesFound": "Commander {commanderName} has identified all bodies in the system.",
    "FSSBodySignals": "Commander {commanderName} has completed a full spectrum scan of the systems, detecting signals.",
    "FSSDiscoveryScan": "Commander {commanderName} has performed a full system scan.",
    "FSSSignalDiscovered": "Commander {commanderName} has discovered a signal using the FSS scanner.",
    "MaterialCollected": "Commander {commanderName} has collected materials.",
    "MaterialDiscarded": "Commander {commanderName} has discarded materials.",
    "MaterialDiscovered": "Commander {commanderName} has discovered a new material.",
    "MultiSellExplorationData": "Commander {commanderName} has sold exploration data.",
    "NavBeaconScan": "Commander {commanderName} has scanned a navigation beacon.",
    "BuyExplorationData": "Commander {commanderName} has bought exploration data.",
    "SAAScanComplete": "Commander {commanderName} has completed a surface area analysis scan.",
    "SAASignalsFound": "Commander {commanderName} has found signals using the SAA scanner.",
    "ScanBaryCentre": "Commander {commanderName} has scanned a BaryCentre.",
    "SellExplorationData": "Commander {commanderName} has sold exploration data in Cartographics.",
    "Screenshot": "Commander {commanderName} has taken a screenshot.",
    "ApproachBody": "Commander {commanderName} is entering an orbit.",
    "LeaveBody": "Commander {commanderName} is exiting an orbit.",
    "Liftoff": "Commander {commanderName}'s ship has lifted off.",
    "Touchdown": "Commander {commanderName}'s ship has touched down on a planet surface.",
    "DatalinkScan": "Commander {commanderName} has scanned a datalink.",
    "DatalinkVoucher": "Commander {commanderName} has received a datalink voucher.",
    "DataScanned": "Commander {commanderName} has scanned data.",
    "Scanned": "Commander {commanderName} has been scanned.",
    "USSDrop": "Commander {commanderName} has encountered a USS drop.",
}

projectedEvents = {
    'ScanOrganicTooClose': "Commander {commanderName} is now too close to take another sample. Distance must be increased.",
    'ScanOrganicFarEnough': "Commander {commanderName} is now far enough away to take another sample.",
    'ScanOrganicFirst': "Commander {commanderName} took the first of three biological samples. New sample distance acquired.",
    'ScanOrganicSecond': "Commander {commanderName} took the second of three biological samples.",
    'ScanOrganicThird': "Commander {commanderName} took the third and final biological samples.",
}

allGameEvents = {
    **systemEvents,
    **combatEvents,
    **tradingEvents,
    **miningEvents,
    **shipUpdateEvents,
    **srvUpdateEvents,
    **onFootUpdateEvents,
    **stationEvents,
    **socialEvents,
    **explorationEvents,
    **projectedEvents,
}

externalEvents = {
    "SpanshTradePlanner": "The Spansh API has suggested a Trade Planner route for Commander {commanderName}.",
    "SpanshTradePlannerFailed": "The Spansh API has failed to retrieve a Trade Planner route for Commander {commanderName}.",
    "ExternalTwitchNotification": "[Twitch Alert]",
    "ExternalTwitchMessage": "[Twitch Message]",
    "ExternalDiscordNotification": "Commander {commanderName} has received a Discord notification.",
    # "SpanshNeutronPlotter": "The Spansh API has suggested a Neutron Plotter router for Commander {commanderName}.",
    # "SpanshRoadToRiches": "The Spansh API has suggested a Road-to-Riches route for Commander {commanderName}.",
}

# Add these new type definitions along with the other existing types
DockingCancelledEvent = dict
DockingTimeoutEvent = dict
LocationEvent = dict
NavRouteEvent = dict

class PromptGenerator:
    def __init__(self, commander_name: str, character_prompt: str, important_game_events: list[str]):
        self.commander_name = commander_name
        self.character_prompt = character_prompt
        self.important_game_events = important_game_events

    def get_event_template(self, event: GameEvent):
        content: Any = event.content
        event_name = content.get('event')
        
        # System events
        if event_name == 'LoadGame':
            load_game_event = cast(LoadGameEvent, content)
            return f"{self.commander_name} is logging into the game in {load_game_event.get('GameMode', 'unknown')} mode."
        if event_name == 'Shutdown':
            return f"{self.commander_name} is shutting down the game."
        if event_name == 'NewCommander':
            return f"{self.commander_name} is starting a new career as  {content.get('Name')}"
        if event_name == 'Missions':
            missions_event = cast(MissionsEvent, content)
            active_count = len(missions_event.get('Active', []))
            complete_count = len(missions_event.get('Complete', []))
            failed_count = len(missions_event.get('Failed', []))
            return f"{self.commander_name} has {active_count} active missions, {complete_count} completed, and {failed_count} failed."
        
        # Message events
        if event_name == 'ReceiveText':
            receive_text_event = cast(ReceiveTextEvent, content)
            return f'Message received from {receive_text_event.get("From_Localised", receive_text_event.get("From"))} on channel {receive_text_event.get("Channel")}: "{receive_text_event.get("Message_Localised", receive_text_event.get("Message"))}"'
        if event_name == 'SendText':
            send_text_event = cast(SendTextEvent, content)
            return f'{self.commander_name} sent a message to {send_text_event.get("To")}: "{send_text_event.get("Message")}"'
        
        # Jump events
        if event_name == 'StartJump':
            start_jump_event = cast(StartJumpEvent, content)
            if start_jump_event.get('JumpType') == 'Hyperspace':
                taxi_info = " (in a taxi)" if start_jump_event.get('Taxi') else ""
                return f"{self.commander_name} is charging FSD for hyperspace jump to {start_jump_event.get('StarSystem')} [{start_jump_event.get('StarClass')} class star]{taxi_info}."
            else:
                return f"{self.commander_name} is preparing to enter supercruise."
                
        if event_name == 'FSDJump':
            fsd_jump_event = cast(FSDJumpEvent, content)
            jump_details = []
            if fsd_jump_event.get('JumpDist'):
                jump_details.append(f"jump distance: {fsd_jump_event.get('JumpDist'):.2f} ly")
            if fsd_jump_event.get('FuelUsed'):
                jump_details.append(f"fuel used: {fsd_jump_event.get('FuelUsed'):.2f} tons")
            if fsd_jump_event.get('BoostUsed'):
                jump_details.append(f"FSD boost used")
            
            details_str = ", ".join(jump_details)
            details_str = f" ({details_str})" if details_str else ""
            
            population = f", population: {fsd_jump_event.get('Population'):,}" if fsd_jump_event.get('Population') else ""
            
            system_details = []
            if fsd_jump_event.get('SystemAllegiance'):
                system_details.append(f"allegiance: {fsd_jump_event.get('SystemAllegiance')}")
            if fsd_jump_event.get('SystemEconomy'):
                economy = fsd_jump_event.get('SystemEconomy_Localised', fsd_jump_event.get('SystemEconomy'))
                system_details.append(f"economy: {economy}")
            if fsd_jump_event.get('SystemGovernment'):
                government = fsd_jump_event.get('SystemGovernment_Localised', fsd_jump_event.get('SystemGovernment'))
                system_details.append(f"government: {government}")
            if fsd_jump_event.get('SystemSecurity'):
                security = fsd_jump_event.get('SystemSecurity_Localised', fsd_jump_event.get('SystemSecurity'))
                system_details.append(f"security: {security}")
            
            system_details_str = ", ".join(system_details)
            system_details_str = f" ({system_details_str})" if system_details_str else ""
            
            faction_info = ""
            if fsd_jump_event.get('SystemFaction'):
                faction_name = fsd_jump_event.get('SystemFaction', {}).get('Name', '')
                faction_state = fsd_jump_event.get('SystemFaction', {}).get('FactionState', '')
                if faction_name and faction_state:
                    faction_info = f" Controlling faction: {faction_name} ({faction_state})"
                elif faction_name:
                    faction_info = f" Controlling faction: {faction_name}"
            
            return f"{self.commander_name} has arrived at {fsd_jump_event.get('StarSystem')}{details_str}{system_details_str}{population}{faction_info}"
            
        if event_name == 'FSDTarget':
            fsd_target_event = cast(FSDTargetEvent, content)
            remaining = ""
            if fsd_target_event.get('RemainingJumpsInRoute') is not None:
                remaining = f" (Remaining jumps in route: {fsd_target_event.get('RemainingJumpsInRoute')})"
            return f"{self.commander_name} is targeting the next jump to {fsd_target_event.get('Name')} [{fsd_target_event.get('StarClass')} class star]{remaining}"
            
        if event_name == 'SupercruiseEntry':
            supercruise_entry_event = cast(SupercruiseEntryEvent, content)
            return f"{self.commander_name} has entered supercruise in the {supercruise_entry_event.get('StarSystem')} system."
            
        if event_name == 'SupercruiseExit':
            supercruise_exit_event = cast(SupercruiseExitEvent, content)
            body_type = f" ({supercruise_exit_event.get('BodyType')})" if supercruise_exit_event.get('BodyType') else ""
            return f"{self.commander_name} has dropped from supercruise near {supercruise_exit_event.get('Body')}{body_type}."
            
        if event_name == 'SupercruiseDestinationDrop':
            supercruise_destination_drop_event = cast(SupercruiseDestinationDropEvent, content)
            threat = ""
            if supercruise_destination_drop_event.get('Threat') is not None:
                threat_level = int(supercruise_destination_drop_event.get('Threat', 0))
                if threat_level > 2:
                    threat = f" WARNING: Threat level {threat_level}!"
                elif threat_level > 0:
                    threat = f" (Threat level: {threat_level})"
            
            destination = supercruise_destination_drop_event.get('Type_Localised', supercruise_destination_drop_event.get('Type'))
            return f"{self.commander_name} is dropping from supercruise at {destination}{threat}"
        
        # Station events
        if event_name == 'Docked':
            docked_event = cast(DockedEvent, content)
            
            station_services = []
            if docked_event.get('StationServices'):
                important_services = ['Shipyard', 'Outfitting', 'BlackMarket', 'Commodities', 'Refuel', 'Repair', 'Rearm']
                available_services = [service for service in important_services if service in docked_event.get('StationServices', [])]
                if available_services:
                    station_services.append(f"Services: {', '.join(available_services)}")
            
            station_economy = ""
            if docked_event.get('StationEconomy_Localised'):
                station_economy = f", Economy: {docked_event.get('StationEconomy_Localised')}"
            
            faction_info = ""
            if docked_event.get('StationFaction'):
                faction_name = docked_event.get('StationFaction', {}).get('Name', '')
                faction_state = docked_event.get('StationFaction', {}).get('FactionState', '')
                if faction_name and faction_state:
                    faction_info = f", Faction: {faction_name} ({faction_state})"
                elif faction_name:
                    faction_info = f", Faction: {faction_name}"
            
            status_info = ""
            if docked_event.get('Wanted'):
                status_info = " WARNING: You are wanted at this station!"
            elif docked_event.get('ActiveFine'):
                status_info = " You have active fines at this station."
            elif docked_event.get('CockpitBreach'):
                status_info = " WARNING: Your cockpit is breached!"
            
            service_str = f" {', '.join(station_services)}" if station_services else ""
            
            return f"Now docked at {docked_event.get('StationType')} {docked_event.get('StationName')} in {docked_event.get('StarSystem')}{station_economy}{faction_info}{service_str}{status_info}"
            
        if event_name == 'Undocked':
            undocked_event = cast(UndockedEvent, content)
            return f"{self.commander_name} has undocked from {undocked_event.get('StationName')}."
            
        if event_name == 'DockingDenied':
            docking_denied_event = cast(DockingDeniedEvent, content)
            reason_map = {
                'NoSpace': 'no landing pads available',
                'TooLarge': 'ship too large for available pads',
                'Hostile': 'station is hostile',
                'Offences': 'pilot has active offences',
                'Distance': 'ship is too far away',
                'ActiveFighter': 'active fighter deployed',
                'NoReason': 'no reason provided'
            }
            reason = reason_map.get(docking_denied_event.get('Reason'), docking_denied_event.get('Reason'))
            return f"Docking request denied at {docking_denied_event.get('StationName')}. Reason: {reason}"
            
        if event_name == 'DockingGranted':
            docking_granted_event = cast(DockingGrantedEvent, content)
            return f"Docking request granted at {docking_granted_event.get('StationName')} on landing pad {docking_granted_event.get('LandingPad')}"
            
        if event_name == 'DockingRequested':
            docking_requested_event = cast(DockingRequestedEvent, content)
            pads_info = ""
            if docking_requested_event.get('LandingPads'):
                pads = docking_requested_event.get('LandingPads', {})
                pads_details = []
                if 'Small' in pads:
                    pads_details.append(f"Small: {pads.get('Small')}")
                if 'Medium' in pads:
                    pads_details.append(f"Medium: {pads.get('Medium')}")
                if 'Large' in pads:
                    pads_details.append(f"Large: {pads.get('Large')}")
                if pads_details:
                    pads_info = f" (Available pads: {', '.join(pads_details)})"
            return f"{self.commander_name} has requested docking at {docking_requested_event.get('StationName')}{pads_info}."
            
        if event_name == 'DockingCancelled':
            docking_cancelled_event = cast(DockingCancelledEvent, content)
            return f"{self.commander_name} has cancelled the docking request at {docking_cancelled_event.get('StationName')}."
            
        if event_name == 'DockingTimeout':
            docking_timeout_event = cast(DockingTimeoutEvent, content)
            return f"{self.commander_name}'s docking request at {docking_timeout_event.get('StationName')} has timed out."
            
        # Planetary events
        if event_name == 'ApproachBody':
            approach_body_event = cast(ApproachBodyEvent, content)
            return f"{self.commander_name} is approaching {approach_body_event.get('Body')} and entering orbital cruise zone."
            
        if event_name == 'LeaveBody':
            leave_body_event = cast(LeaveBodyEvent, content)
            return f"{self.commander_name} is leaving the orbital cruise zone of {leave_body_event.get('Body')}."
            
        if event_name == 'Touchdown':
            touchdown_event = cast(TouchdownEvent, content)
            coordinates = ""
            if touchdown_event.get('Latitude') is not None and touchdown_event.get('Longitude') is not None:
                coordinates = f" at coordinates {touchdown_event.get('Latitude'):.4f}, {touchdown_event.get('Longitude'):.4f}"
            
            station_info = ""
            if touchdown_event.get('OnStation'):
                station_info = " on a planetary station"
            elif touchdown_event.get('NearestDestination'):
                dest = touchdown_event.get('NearestDestination_Localised', touchdown_event.get('NearestDestination'))
                station_info = f" near {dest}"
            
            if touchdown_event.get('PlayerControlled'):
                return f"{self.commander_name} has landed on {touchdown_event.get('Body')}{coordinates}{station_info}."
            else:
                return f"{self.commander_name}'s ship has auto-landed on {touchdown_event.get('Body')}{station_info}."
            
        if event_name == 'Liftoff':
            liftoff_event = cast(LiftoffEvent, content)
            coordinates = ""
            if liftoff_event.get('Latitude') is not None and liftoff_event.get('Longitude') is not None:
                coordinates = f" from coordinates {liftoff_event.get('Latitude'):.4f}, {liftoff_event.get('Longitude'):.4f}"
            
            station_info = ""
            if liftoff_event.get('OnStation'):
                station_info = " from a planetary station"
            elif liftoff_event.get('NearestDestination'):
                dest = liftoff_event.get('NearestDestination_Localised', liftoff_event.get('NearestDestination'))
                station_info = f" near {dest}"
            
            if liftoff_event.get('PlayerControlled'):
                return f"{self.commander_name} has lifted off from {liftoff_event.get('Body')}{coordinates}{station_info}."
            else:
                return f"{self.commander_name}'s ship has auto-lifted off from {liftoff_event.get('Body')}{station_info}."
                
        if event_name == 'Location':
            location_event = cast(LocationEvent, content)
            location_details = []
            
            if location_event.get('Docked'):
                station_type = f"{location_event.get('StationType')} " if location_event.get('StationType') else ""
                location_details.append(f"docked at {station_type}{location_event.get('StationName')}")
            elif location_event.get('BodyName'):
                if location_event.get('Latitude') is not None and location_event.get('Longitude') is not None:
                    location_details.append(f"on {location_event.get('BodyName')} at coordinates {location_event.get('Latitude'):.4f}, {location_event.get('Longitude'):.4f}")
                else:
                    location_details.append(f"near {location_event.get('BodyName')}")
                    if location_event.get('DistFromStarLS'):
                        location_details.append(f"{location_event.get('DistFromStarLS'):.2f} ls from main star")
            
            system_details = []
            if location_event.get('SystemAllegiance'):
                system_details.append(f"allegiance: {location_event.get('SystemAllegiance')}")
            if location_event.get('SystemEconomy'):
                economy = location_event.get('SystemEconomy_Localised', location_event.get('SystemEconomy'))
                system_details.append(f"economy: {economy}")
            if location_event.get('SystemGovernment'):
                government = location_event.get('SystemGovernment_Localised', location_event.get('SystemGovernment'))
                system_details.append(f"government: {government}")
            if location_event.get('SystemSecurity'):
                security = location_event.get('SystemSecurity_Localised', location_event.get('SystemSecurity'))
                system_details.append(f"security: {security}")
            
            population = f", population: {location_event.get('Population'):,}" if location_event.get('Population') else ""
            
            status_info = []
            if location_event.get('Wanted'):
                status_info.append("WANTED in this system")
            if location_event.get('Taxi'):
                status_info.append("in a taxi")
            elif location_event.get('Multicrew'):
                status_info.append("in multicrew session")
            elif location_event.get('InSRV'):
                status_info.append("in SRV")
            elif location_event.get('OnFoot'):
                status_info.append("on foot")
                
            location_str = f" {', '.join(location_details)}" if location_details else ""
            system_details_str = f" ({', '.join(system_details)})" if system_details else ""
            status_str = f" ({', '.join(status_info)})" if status_info else ""
            
            return f"{self.commander_name} is in the {location_event.get('StarSystem')} system{location_str}{system_details_str}{population}{status_str}."
            
        if event_name == 'NavRoute':
            nav_route_event = cast(NavRouteEvent, content)
            if nav_route_event.get('Route'):
                route_count = len(nav_route_event.get('Route', []))
                if route_count > 0:
                    start = nav_route_event.get('Route', [])[0].get('StarSystem', 'Unknown')
                    end = nav_route_event.get('Route', [])[-1].get('StarSystem', 'Unknown') 
                    return f"{self.commander_name} has plotted a {route_count}-jump route from {start} to {end}."
            return f"{self.commander_name} has plotted a new route."
            
        if event_name == 'NavRouteClear':
            return f"{self.commander_name} has cleared the current navigation route."
        
        # Mission events
        if event_name == 'MissionAccepted':
            mission_accepted_event = cast(MissionAcceptedEvent, content)
            return f"{self.commander_name} has accepted mission: {mission_accepted_event.get('LocalisedName')} from {mission_accepted_event.get('Faction')}."
        if event_name == 'MissionCompleted':
            mission_completed_event = cast(MissionCompletedEvent, content)
            if mission_completed_event.get('Reward'):
                return f"{self.commander_name} has completed mission: {mission_completed_event.get('LocalisedName')} for {mission_completed_event.get('Faction')}. Reward: {mission_completed_event.get('Reward'):,} credits."
            else:
                return f"{self.commander_name} has completed mission: {mission_completed_event.get('LocalisedName')} for {mission_completed_event.get('Faction')}."
        if event_name == 'MissionFailed':
            mission_failed_event = cast(MissionFailedEvent, content)
            return f"{self.commander_name} has failed mission: {mission_failed_event.get('LocalisedName')}."
        if event_name == 'MissionAbandoned':
            mission_abandoned_event = cast(MissionAbandonedEvent, content)
            return f"{self.commander_name} has abandoned mission: {mission_abandoned_event.get('LocalisedName')}."
        if event_name == 'MissionRedirected':
            mission_redirected_event = cast(MissionRedirectedEvent, content)
            return f"{self.commander_name}'s mission '{mission_redirected_event.get('LocalisedName')}' has been redirected to {mission_redirected_event.get('NewDestinationSystem')} - {mission_redirected_event.get('NewDestinationStation')}."
        
        # Financial events
        if event_name == 'RedeemVoucher':
            redeem_voucher_event = cast(RedeemVoucherEvent, content)
            return f"{self.commander_name} has redeemed a {redeem_voucher_event.get('Type')} voucher for {redeem_voucher_event.get('Amount'):,} credits."
        if event_name == 'PayFines':
            pay_fines_event = cast(PayFinesEvent, content)
            return f"{self.commander_name} has paid {pay_fines_event.get('Amount'):,} credits in fines."
        if event_name == 'PayLegacyFines':
            return f"{self.commander_name} has paid off legacy fines."
        if event_name == 'PayBounties':
            return f"{self.commander_name} has paid off their bounties."
        
        # Social events
        if event_name == 'CrewAssign':
            crew_assign_event = cast(CrewAssignEvent, content)
            return f"{self.commander_name} has assigned {crew_assign_event.get('Name')} to {crew_assign_event.get('Role')} role."
        if event_name == 'CrewHire':
            return f"{self.commander_name} has hired a new crew member."
        if event_name == 'CrewFire':
            return f"{self.commander_name} has fired a crew member."
        if event_name == 'CrewMemberJoins':
            crew_member_joins_event = cast(CrewMemberJoinsEvent, content)
            return f"{crew_member_joins_event.get('Crew')} has joined {self.commander_name}'s crew."
        if event_name == 'CrewMemberQuits':
            crew_member_quits_event = cast(CrewMemberQuitsEvent, content)
            return f"{crew_member_quits_event.get('Crew')} has left {self.commander_name}'s crew."
        if event_name == 'CrewMemberRoleChange':
            crew_member_role_change_event = cast(CrewMemberRoleChangeEvent, content)
            return f"{crew_member_role_change_event.get('Crew')} has changed role to {crew_member_role_change_event.get('Role')}."
        if event_name == 'EndCrewSession':
            end_crew_session_event = cast(EndCrewSessionEvent, content)
            return f"{self.commander_name} has ended their crew session."
        if event_name == 'JoinACrew':
            return f"{self.commander_name} has joined another commander's crew."
        if event_name == 'QuitACrew':
            return f"{self.commander_name} has left the crew they were part of."
        if event_name == 'KickCrewMember':
            return f"{self.commander_name} has kicked a member from their crew."
        if event_name == 'WingAdd':
            wing_add_event = cast(WingAddEvent, content)
            return f"{wing_add_event.get('Name')} has joined {self.commander_name}'s wing."
        if event_name == 'WingJoin':
            wing_join_event = cast(WingJoinEvent, content)
            return f"{self.commander_name} has joined a wing."
        if event_name == 'WingLeave':
            wing_leave_event = cast(WingLeaveEvent, content)
            return f"{self.commander_name} has left their wing."
        if event_name == 'WingInvite':
            return f"{self.commander_name} has invited someone to join their wing."
        if event_name == 'Friends':
            friends_event = cast(FriendsEvent, content)
            return f"Friend status update: {friends_event.get('Name')} is now {friends_event.get('Status')}."

        # Squadron events
        if event_name == 'AppliedToSquadron':
            return f"{self.commander_name} has applied to join a squadron."
        if event_name == 'DisbandedSquadron':
            return f"{self.commander_name} has disbanded their squadron."
        if event_name == 'InvitedToSquadron':
            return f"{self.commander_name} has been invited to join a squadron."
        if event_name == 'JoinedSquadron':
            return f"{self.commander_name} has joined a squadron."
        if event_name == 'KickedFromSquadron':
            return f"{self.commander_name} has been kicked from their squadron."
        if event_name == 'LeftSquadron':
            return f"{self.commander_name} has left their squadron."
        if event_name == 'SquadronCreated':
            return f"{self.commander_name} has created a new squadron."
        if event_name == 'SquadronDemotion':
            return f"{self.commander_name} has been demoted in their squadron."
        if event_name == 'SquadronPromotion':
            return f"{self.commander_name} has been promoted in their squadron."
        
        # Promotion events
        if event_name == 'Promotion':
            promotion_event = cast(PromotionEvent, content)
            ranks = []
            if promotion_event.get('Combat') is not None:
                ranks.append(f"Combat: {promotion_event.get('Combat')}")
            if promotion_event.get('Trade') is not None:
                ranks.append(f"Trade: {promotion_event.get('Trade')}")
            if promotion_event.get('Explore') is not None:
                ranks.append(f"Exploration: {promotion_event.get('Explore')}")
            if promotion_event.get('Soldier') is not None:
                ranks.append(f"Mercenary: {promotion_event.get('Soldier')}")
            if promotion_event.get('Exobiologist') is not None:
                ranks.append(f"Exobiologist: {promotion_event.get('Exobiologist')}")
            if promotion_event.get('Empire') is not None:
                ranks.append(f"Empire: {promotion_event.get('Empire')}")
            if promotion_event.get('Federation') is not None:
                ranks.append(f"Federation: {promotion_event.get('Federation')}")
            return f"{self.commander_name} has been promoted. New ranks: {', '.join(ranks)}"
        
        # Powerplay events
        if event_name == 'PowerplayJoin':
            powerplay_join_event = cast(PowerplayJoinEvent, content)
            return f"{self.commander_name} has pledged allegiance to {powerplay_join_event.get('Power')}."
        if event_name == 'PowerplayLeave':
            return f"{self.commander_name} has withdrawn their allegiance from their Power."
        if event_name == 'PowerplayDefect':
            return f"{self.commander_name} has defected to another Power."
        
        # Carrier events
        if event_name == 'CarrierJump':
            return f"{self.commander_name}'s fleet carrier has completed a jump."
        if event_name == 'CarrierJumpRequest':
            return f"{self.commander_name} has requested their fleet carrier to prepare for a jump."
        if event_name == 'CarrierBuy':
            return f"{self.commander_name} has purchased a fleet carrier."
        if event_name == 'CarrierDecommission':
            return f"{self.commander_name} has initiated the decommissioning process for their fleet carrier."
        if event_name == 'CarrierCancelDecommission':
            return f"{self.commander_name} has canceled the decommissioning process for their fleet carrier."
        if event_name == 'CarrierNameChanged':
            return f"{self.commander_name} has changed the name of their fleet carrier."
        if event_name == 'CarrierJumpCancelled':
            return f"{self.commander_name} has cancelled the pending jump of their fleet carrier."

        # Exploration events
        if event_name == 'CodexEntry':
            codex_entry_event = cast(CodexEntryEvent, content)
            codex_name = codex_entry_event.get('Name_Localised', codex_entry_event.get('Name', 'Unknown Discovery'))
            category = codex_entry_event.get('Category_Localised', codex_entry_event.get('Category', ''))
            system = codex_entry_event.get('System', '')
            is_new = ' - New discovery!' if codex_entry_event.get('IsNewEntry') else ''
            return f"{self.commander_name} has discovered a new codex entry: {codex_name} ({category}) in {system}{is_new}"
            
        if event_name == 'DiscoveryScan':
            discovery_scan_event = cast(DiscoveryScanEvent, content)
            bodies_count = discovery_scan_event.get('Bodies', 0)
            return f"{self.commander_name} performed a discovery scan and found {bodies_count} new astronomical bodies."
            
        if event_name == 'Scan':
            scan_event = cast(ScanEvent, content)
            body_name = scan_event.get('BodyName', 'Unknown body')
            body_type = None
            
            if scan_event.get('StarType'):
                star_type = scan_event.get('StarType', '')
                luminosity = scan_event.get('Luminosity', '')
                stellar_mass = scan_event.get('StellarMass', 0)
                body_type = f"star (Type: {star_type}, Mass: {stellar_mass} solar masses, Luminosity: {luminosity})"
            elif scan_event.get('PlanetClass'):
                planet_class = scan_event.get('PlanetClass', '')
                atmosphere = scan_event.get('Atmosphere', 'None')
                terraform_state = scan_event.get('TerraformState', 'Not terraformable')
                is_landable = 'Landable' if scan_event.get('Landable') else 'Not landable'
                body_type = f"{planet_class} ({terraform_state}, Atmosphere: {atmosphere}, {is_landable})"
            
            scan_type = scan_event.get('ScanType', 'Unknown scan')
            
            if body_type:
                return f"{self.commander_name} performed a {scan_type} scan of {body_name}: {body_type}."
            else:
                return f"{self.commander_name} performed a {scan_type} scan of {body_name}."
                
        if event_name == 'FSSAllBodiesFound':
            fss_all_bodies_event = cast(FSSAllBodiesFoundEvent, content)
            system_name = fss_all_bodies_event.get('SystemName', 'current system')
            body_count = fss_all_bodies_event.get('Count', 0)
            return f"{self.commander_name} has discovered all {body_count} bodies in the {system_name} system."
            
        if event_name == 'FSSDiscoveryScan':
            fss_discovery_scan_event = cast(FSSDiscoveryScanEvent, content)
            progress = fss_discovery_scan_event.get('Progress', 0) * 100
            body_count = fss_discovery_scan_event.get('BodyCount', 0)
            non_body_count = fss_discovery_scan_event.get('NonBodyCount', 0)
            return f"{self.commander_name} performed an FSS discovery scan. Progress: {progress:.1f}%, Bodies detected: {body_count}, Non-body signals: {non_body_count}."
            
        if event_name == 'FSSSignalDiscovered':
            fss_signal_event = cast(FSSSignalDiscoveredEvent, content)
            signal_type = fss_signal_event.get('SignalName_Localised', fss_signal_event.get('SignalName', 'Unknown signal'))
            return f"{self.commander_name} discovered a signal: {signal_type}."
            
        if event_name == 'FSSBodySignals':
            fss_body_signals_event = cast(FSSBodySignalsEvent, content)
            body_name = fss_body_signals_event.get('BodyName', 'a body')
            signal_count = sum(signal.get('Count', 0) for signal in fss_body_signals_event.get('Signals', []))
            return f"{self.commander_name} detected {signal_count} signals on {body_name}."
            
        if event_name == 'SAASignalsFound':
            saa_signals_event = cast(SAASignalsFoundEvent, content)
            body_name = saa_signals_event.get('BodyName', 'the current body')
            
            signals_info = []
            for signal in saa_signals_event.get('Signals', []):
                sig_type = signal.get('Type_Localised', signal.get('Type', 'Unknown'))
                count = signal.get('Count', 0)
                signals_info.append(f"{count} {sig_type}")
            
            if 'Genuses' in saa_signals_event:
                genus_info = []
                for genus in saa_signals_event.get('Genuses', []):
                    genus_name = genus.get('Genus_Localised', genus.get('Genus', 'Unknown species'))
                    genus_info.append(genus_name)
                
                if genus_info:
                    return f"{self.commander_name} scanned {body_name} and found: {', '.join(signals_info)}. Biological genuses detected: {', '.join(genus_info)}."
            
            if signals_info:
                return f"{self.commander_name} scanned {body_name} and found: {', '.join(signals_info)}."
            else:
                return f"{self.commander_name} scanned {body_name} but found no significant signals."
            
        if event_name == 'SAAScanComplete':
            saa_scan_complete_event = cast(SAAScanCompleteEvent, content)
            body_name = saa_scan_complete_event.get('BodyName', 'the current body')
            probes_used = saa_scan_complete_event.get('ProbesUsed', 0)
            efficiency_target = saa_scan_complete_event.get('EfficiencyTarget', 0)
            efficiency_text = f" (Efficiency target was {efficiency_target})" if efficiency_target else ""
            
            return f"{self.commander_name} has completed a full surface scan of {body_name} using {probes_used} probes{efficiency_text}."
            
        if event_name == 'ScanBaryCentre':
            scan_bary_event = cast(ScanBaryCentreEvent, content)
            system_name = scan_bary_event.get('StarSystem', 'current system')
            return f"{self.commander_name} has scanned the barycenter in the {system_name} system."
            
        if event_name == 'MaterialCollected':
            material_collected_event = cast(MaterialCollectedEvent, content)
            material_name = material_collected_event.get('Name_Localised', material_collected_event.get('Name', 'unknown material'))
            material_count = material_collected_event.get('Count', 1)
            material_category = material_collected_event.get('Category', '')
            
            return f"{self.commander_name} has collected {material_count} units of {material_name} ({material_category})."
            
        if event_name == 'MaterialDiscarded':
            material_discarded_event = cast(MaterialDiscardedEvent, content)
            material_name = material_discarded_event.get('Name_Localised', material_discarded_event.get('Name', 'unknown material'))
            material_count = material_discarded_event.get('Count', 1)
            
            return f"{self.commander_name} has discarded {material_count} units of {material_name}."
            
        if event_name == 'MaterialDiscovered':
            material_discovered_event = cast(MaterialDiscoveredEvent, content)
            material_name = material_discovered_event.get('Name_Localised', material_discovered_event.get('Name', 'unknown material'))
            category = material_discovered_event.get('Category', '')
            discovery_number = material_discovered_event.get('DiscoveryNumber', 0)
            
            return f"{self.commander_name} has discovered a new material: {material_name} ({category}). This is discovery #{discovery_number}."
            
        if event_name == 'BuyExplorationData':
            buy_exploration_data_event = cast(BuyExplorationDataEvent, content)
            system_name = buy_exploration_data_event.get('System', 'Unknown system')
            cost = buy_exploration_data_event.get('Cost', 0)
            
            return f"{self.commander_name} has purchased exploration data for the {system_name} system for {cost:,} credits."
            
        if event_name == 'SellExplorationData':
            sell_exploration_data_event = cast(SellExplorationDataEvent, content)
            systems = sell_exploration_data_event.get('Systems', [])
            systems_text = ', '.join(systems[:3])
            if len(systems) > 3:
                systems_text += f" and {len(systems) - 3} more"
                
            discovered_bodies = sell_exploration_data_event.get('Discovered', [])
            discovered_count = len(discovered_bodies)
            
            base_value = sell_exploration_data_event.get('BaseValue', 0)
            bonus = sell_exploration_data_event.get('Bonus', 0)
            total = sell_exploration_data_event.get('TotalEarnings', 0)
            
            return f"{self.commander_name} has sold exploration data for {systems_text} ({discovered_count} bodies) for {total:,} credits (base: {base_value:,}, bonus: {bonus:,})."
            
        if event_name == 'MultiSellExplorationData':
            multi_sell_event = cast(MultiSellExplorationDataEvent, content)
            discovered_systems = multi_sell_event.get('Discovered', [])
            system_count = len(discovered_systems)
            body_count = sum(system.get('NumBodies', 0) for system in discovered_systems)
            
            base_value = multi_sell_event.get('BaseValue', 0)
            bonus = multi_sell_event.get('Bonus', 0)
            total = multi_sell_event.get('TotalEarnings', 0)
            
            return f"{self.commander_name} has sold exploration data for {system_count} systems ({body_count} bodies) for {total:,} credits (base: {base_value:,}, bonus: {bonus:,})."
            
        if event_name == 'NavBeaconScan':
            nav_beacon_scan_event = cast(NavBeaconScanEvent, content)
            body_count = nav_beacon_scan_event.get('NumBodies', 0)
            
            return f"{self.commander_name} has scanned a navigation beacon, revealing data for {body_count} bodies in the system."
            
        if event_name == 'Screenshot':
            screenshot_event = cast(ScreenshotEvent, content)
            system = screenshot_event.get('System', 'current system')
            body = screenshot_event.get('Body', '')
            body_text = f" near {body}" if body else ""
            
            location_text = ""
            if screenshot_event.get('Latitude') is not None and screenshot_event.get('Longitude') is not None:
                lat = screenshot_event.get('Latitude')
                lon = screenshot_event.get('Longitude')
                alt = screenshot_event.get('Altitude')
                location_text = f" at coordinates {lat:.4f}, {lon:.4f}, altitude: {alt:.1f}m"
            
            return f"{self.commander_name} took a screenshot in {system}{body_text}{location_text}."

        # Station Services events
        if event_name == 'BuyAmmo':
            buy_ammo_event = cast(Dict[str, Any], content)
            return f"{self.commander_name} has purchased ammunition for {buy_ammo_event.get('Cost', 0):,} credits."
            
        if event_name == 'BuyDrones':
            buy_drones_event = cast(Dict[str, Any], content)
            drone_type = buy_drones_event.get('Type', 'drones')
            count = buy_drones_event.get('Count', 0)
            total_cost = buy_drones_event.get('TotalCost', 0)
            return f"{self.commander_name} has purchased {count} {drone_type} for {total_cost:,} credits."
            
        if event_name == 'SellDrones':
            sell_drones_event = cast(Dict[str, Any], content)
            count = sell_drones_event.get('Count', 0)
            sell_price = sell_drones_event.get('SellPrice', 0)
            total_sale = sell_drones_event.get('TotalSale', 0)
            return f"{self.commander_name} has sold {count} drones for {total_sale:,} credits (at {sell_price:,} each)."
            
        if event_name == 'CommunityGoalJoin':
            cg_join_event = cast(Dict[str, Any], content)
            name = cg_join_event.get('Name', 'a community goal')
            system = f" in {cg_join_event.get('System')}" if cg_join_event.get('System') else ""
            return f"{self.commander_name} has signed up for the community goal: {name}{system}."
            
        if event_name == 'CommunityGoalDiscard':
            cg_discard_event = cast(Dict[str, Any], content)
            name = cg_discard_event.get('Name', 'a community goal')
            system = f" in {cg_discard_event.get('System')}" if cg_discard_event.get('System') else ""
            return f"{self.commander_name} has opted out of the community goal: {name}{system}."
            
        if event_name == 'CommunityGoalReward':
            cg_reward_event = cast(Dict[str, Any], content)
            name = cg_reward_event.get('Name', 'a community goal')
            system = f" in {cg_reward_event.get('System')}" if cg_reward_event.get('System') else ""
            reward = cg_reward_event.get('Reward', 0)
            return f"{self.commander_name} has received a reward of {reward:,} credits for participation in community goal: {name}{system}."
            
        if event_name == 'RefuelAll':
            refuel_all_event = cast(Dict[str, Any], content)
            cost = refuel_all_event.get('Cost', 0)
            amount = refuel_all_event.get('Amount', 0)
            return f"{self.commander_name} has refueled the ship with {amount:.2f} tons of fuel for {cost:,} credits."
            
        if event_name == 'RefuelPartial':
            refuel_partial_event = cast(Dict[str, Any], content)
            cost = refuel_partial_event.get('Cost', 0)
            amount = refuel_partial_event.get('Amount', 0)
            return f"{self.commander_name} has partially refueled the ship with {amount:.2f} tons of fuel for {cost:,} credits."
            
        if event_name == 'Repair':
            repair_event = cast(Dict[str, Any], content)
            item = repair_event.get('Item', 'hull')
            cost = repair_event.get('Cost', 0)
            return f"{self.commander_name} has repaired the ship's {item} for {cost:,} credits."
            
        if event_name == 'RepairAll':
            repair_all_event = cast(Dict[str, Any], content)
            cost = repair_all_event.get('Cost', 0)
            return f"{self.commander_name} has repaired all ship damage for {cost:,} credits."
            
        if event_name == 'RestockVehicle':
            restock_vehicle_event = cast(Dict[str, Any], content)
            vehicle = restock_vehicle_event.get('Type', 'vehicle')
            cost = restock_vehicle_event.get('Cost', 0)
            count = restock_vehicle_event.get('Count', 1)
            return f"{self.commander_name} has restocked {count} {vehicle}(s) for {cost:,} credits."
            
        if event_name == 'ModuleBuy':
            module_buy_event = cast(Dict[str, Any], content)
            slot = module_buy_event.get('Slot', 'a slot')
            module = module_buy_event.get('BuyItem_Localised', module_buy_event.get('BuyItem', 'a module'))
            cost = module_buy_event.get('BuyPrice', 0)
            return f"{self.commander_name} has purchased a {module} for {slot} for {cost:,} credits."
            
        if event_name == 'ModuleSell':
            module_sell_event = cast(Dict[str, Any], content)
            slot = module_sell_event.get('Slot', 'a slot')
            module = module_sell_event.get('SellItem_Localised', module_sell_event.get('SellItem', 'a module'))
            price = module_sell_event.get('SellPrice', 0)
            return f"{self.commander_name} has sold a {module} from {slot} for {price:,} credits."
            
        if event_name == 'ModuleStore':
            module_store_event = cast(Dict[str, Any], content)
            slot = module_store_event.get('Slot', 'a slot')
            module = module_store_event.get('Module_Localised', module_store_event.get('Module', 'a module'))
            cost = module_store_event.get('Cost', 0)
            cost_text = f" for {cost:,} credits" if cost > 0 else ""
            return f"{self.commander_name} has stored a {module} from {slot}{cost_text}."
            
        if event_name == 'ModuleRetrieve':
            module_retrieve_event = cast(Dict[str, Any], content)
            slot = module_retrieve_event.get('Slot', 'a slot')
            module = module_retrieve_event.get('Module_Localised', module_retrieve_event.get('Module', 'a module'))
            cost = module_retrieve_event.get('Cost', 0)
            cost_text = f" for {cost:,} credits" if cost > 0 else ""
            return f"{self.commander_name} has retrieved a {module} to {slot}{cost_text}."
            
        if event_name == 'ModuleSwap':
            module_swap_event = cast(Dict[str, Any], content)
            from_slot = module_swap_event.get('FromSlot', 'a slot')
            to_slot = module_swap_event.get('ToSlot', 'another slot')
            from_module = module_swap_event.get('FromItem_Localised', module_swap_event.get('FromItem', 'a module'))
            to_module = module_swap_event.get('ToItem_Localised', module_swap_event.get('ToItem', 'another module'))
            return f"{self.commander_name} has swapped {from_module} in {from_slot} with {to_module} in {to_slot}."

        if event_name == 'ShipyardBuy':
            shipyard_buy_event = cast(Dict[str, Any], content)
            ship_type = shipyard_buy_event.get('ShipType_Localised', shipyard_buy_event.get('ShipType', 'a ship'))
            price = shipyard_buy_event.get('ShipPrice', 0)
            sold_ship = shipyard_buy_event.get('SellOldShip', '')
            sold_price = shipyard_buy_event.get('SellPrice', 0)
            
            if sold_ship:
                sold_ship_name = shipyard_buy_event.get('SellShipId', sold_ship)
                return f"{self.commander_name} has purchased a {ship_type} for {price:,} credits and traded in their {sold_ship_name} for {sold_price:,} credits."
            else:
                return f"{self.commander_name} has purchased a {ship_type} for {price:,} credits."
                
        if event_name == 'ShipyardSell':
            shipyard_sell_event = cast(Dict[str, Any], content)
            ship_type = shipyard_sell_event.get('ShipType_Localised', shipyard_sell_event.get('ShipType', 'a ship'))
            ship_id = shipyard_sell_event.get('SellShipId', '')
            price = shipyard_sell_event.get('ShipPrice', 0)
            return f"{self.commander_name} has sold their {ship_type} ({ship_id}) for {price:,} credits."
            
        if event_name == 'ShipyardTransfer':
            shipyard_transfer_event = cast(Dict[str, Any], content)
            ship_type = shipyard_transfer_event.get('ShipType_Localised', shipyard_transfer_event.get('ShipType', 'a ship'))
            ship_id = shipyard_transfer_event.get('ShipID', '')
            system = shipyard_transfer_event.get('System', 'another system')
            transfer_price = shipyard_transfer_event.get('TransferPrice', 0)
            transfer_time = shipyard_transfer_event.get('TransferTime', 0)
            
            if transfer_time > 0:
                time_str = f", arriving in {transfer_time} seconds"
            else:
                time_str = ", arriving immediately"
                
            return f"{self.commander_name} has requested a transfer of their {ship_type} ({ship_id}) from {system} for {transfer_price:,} credits{time_str}."
            
        if event_name == 'ShipyardSwap':
            shipyard_swap_event = cast(Dict[str, Any], content)
            ship_type = shipyard_swap_event.get('ShipType_Localised', shipyard_swap_event.get('ShipType', 'a ship'))
            ship_id = shipyard_swap_event.get('ShipID', '')
            store_old_ship = shipyard_swap_event.get('StoreOldShip', 0)
            store_ship_type = shipyard_swap_event.get('StoreShipType', '')
            
            if store_old_ship:
                return f"{self.commander_name} has swapped to their {ship_type} ({ship_id}) and stored their previous {store_ship_type}."
            else:
                return f"{self.commander_name} has swapped to their {ship_type} ({ship_id})."
                
        if event_name == 'MaterialTrade':
            material_trade_event = cast(Dict[str, Any], content)
            trader_type = material_trade_event.get('TraderType', 'material trader')
            paid_material = material_trade_event.get('Paid_Localised', material_trade_event.get('Paid', 'materials'))
            paid_quantity = material_trade_event.get('Paid_Quantity', 0)
            received_material = material_trade_event.get('Received_Localised', material_trade_event.get('Received', 'materials'))
            received_quantity = material_trade_event.get('Received_Quantity', 0)
            
            return f"{self.commander_name} has traded {paid_quantity} {paid_material} for {received_quantity} {received_material} at a {trader_type}."
            
        if event_name == 'EngineerProgress':
            engineer_progress_event = cast(Dict[str, Any], content)
            engineer = engineer_progress_event.get('Engineer', 'an engineer')
            progress = engineer_progress_event.get('Progress', '')
            rank = engineer_progress_event.get('Rank')
            
            if progress == 'Unlocked':
                return f"{self.commander_name} has unlocked {engineer}."
            elif progress == 'Invited':
                return f"{self.commander_name} has been invited to meet {engineer}."
            elif rank is not None:
                return f"{self.commander_name} has reached rank {rank} with {engineer}."
            else:
                return f"{self.commander_name} has made progress with {engineer}: {progress}."
                
        if event_name == 'EngineerCraft':
            engineer_craft_event = cast(Dict[str, Any], content)
            engineer = engineer_craft_event.get('Engineer', 'an engineer')
            blueprint = engineer_craft_event.get('Blueprint', 'a blueprint')
            level = engineer_craft_event.get('Level', 0)
            quality = engineer_craft_event.get('Quality', 0)
            
            return f"{self.commander_name} has crafted a level {level} {blueprint} modification with {engineer} (quality: {quality:.2f})."
            
        if event_name == 'EngineerApply':
            engineer_apply_event = cast(Dict[str, Any], content)
            engineer = engineer_apply_event.get('Engineer', 'an engineer')
            blueprint = engineer_apply_event.get('Blueprint', 'a blueprint')
            level = engineer_apply_event.get('Level', 0)
            
            return f"{self.commander_name} has applied a level {level} {blueprint} experimental effect with {engineer}."
            
        if event_name == 'PayBounties':
            pay_bounties_event = cast(Dict[str, Any], content)
            amount = pay_bounties_event.get('Amount', 0)
            faction = pay_bounties_event.get('Faction', 'a faction')
            
            return f"{self.commander_name} has paid off {amount:,} credits in bounties to {faction}."

        if event_name == 'ClearImpound':
            clear_impound_event = cast(Dict[str, Any], content)
            amount = clear_impound_event.get('Cost', 0)
            ship_type = clear_impound_event.get('ShipType_Localised', clear_impound_event.get('ShipType', 'a ship'))
            return f"{self.commander_name} has paid {amount:,} credits to reclaim their impounded {ship_type}."

        if event_name == 'SearchAndRescue':
            sar_event = cast(Dict[str, Any], content)
            item = sar_event.get('Name_Localised', sar_event.get('Name', 'items'))
            count = sar_event.get('Count', 0)
            reward = sar_event.get('Reward', 0)
            return f"{self.commander_name} has turned in {count} {item} for search and rescue, receiving a reward of {reward:,} credits."

        if event_name == 'SetUserShipName':
            set_ship_name_event = cast(Dict[str, Any], content)
            ship_type = set_ship_name_event.get('Ship_Localised', set_ship_name_event.get('Ship', 'a ship'))
            ship_name = set_ship_name_event.get('UserShipName', 'a name')
            ship_ident = set_ship_name_event.get('UserShipId', '')
            
            if ship_ident:
                return f"{self.commander_name} has renamed their {ship_type} to '{ship_name}' with ID '{ship_ident}'."
            else:
                return f"{self.commander_name} has renamed their {ship_type} to '{ship_name}'."

        # If we don't have a specific handler for this event
        return f"Event: {event_name} occurred."

    def full_event_message(self, event: GameEvent, timeoffset: str, is_important: bool):
        message = self.get_event_template(event)
        if message:
            return {
                "role": "user",
                "content": f"[{'IMPORTANT ' if is_important else ''}Game Event, {timeoffset}] {message}",
            }

        return {
            "role": "user",
            "content": f"[{'IMPORTANT ' if is_important else ''}Game Event, {timeoffset}] {allGameEvents[event.content.get('event')].format(commanderName=self.commander_name)}\n{yaml.dump(event.content)}",
        }

    def simple_event_message(self, event: GameEvent, timeoffset: str):
        return {
            "role": "user",
            "content": f"[Game Event, {timeoffset}] {allGameEvents[event.content.get('event')].format(commanderName=self.commander_name)}",
        }

    def full_projectedevent_message(self, event: ProjectedEvent, timeoffset: str, is_important: bool):
        return {
            "role": "user",
            "content": f"[{'IMPORTANT ' if is_important else ''}Game Event, {timeoffset}] {allGameEvents[event.content.get('event')].format(commanderName=self.commander_name)}\n{yaml.dump(event.content)}",
        }

    def simple_projectedevent_message(self, event: ProjectedEvent, timeoffset: str):
        return {
            "role": "user",
            "content": f"[Game Event, {timeoffset}] {allGameEvents[event.content.get('event')].format(commanderName=self.commander_name)}",
        }

    def status_messages(self, event: StatusEvent):
        if event.status.get('event'):
            return [{
                "role": "user",
                "content": f"(Status changed: {event.status.get('event')} Details: {json.dumps(event.status)})",
            }]
        return []

    def conversation_message(self, event: ConversationEvent):
        return {"role": event.kind, "content": event.content}

    def tool_messages(self, event: ToolEvent):
        responses = []
        for result in event.results:
            responses.append(result)
        responses.append(
            {"role": "assistant", "content": None, "tool_calls": event.request}
        )
        return responses

    def external_event_message(self, event: ExternalEvent):
        return {
            "role": "user",
            "content": f"({externalEvents[event.content.get('event')]})",
        }

    def tool_response_message(self, event: ToolEvent):
        return

    # fetch system info from EDSM
    @lru_cache(maxsize=1, typed=False)
    def get_system_info(self, system_name: str) -> dict:
        url = "https://www.edsm.net/api-v1/system"
        params = {
            "systemName": system_name,
            "showInformation": 1,
            "showPrimaryStar": 1,
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()  # Raises an HTTPError for bad responses (4xx and 5xx)

            return response.json()

        except Exception as e:
            log('error', e, traceback.format_exc())
            return "Currently no information on system available"

    # fetch station info from EDSM
    @lru_cache(maxsize=1, typed=False)
    def get_station_info(self, system_name: str, fleet_carrier=False) -> list:
        url = "https://www.edsm.net/api-system-v1/stations"
        params = {
            "systemName": system_name,
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()  # Raises an HTTPError for bad responses (4xx and 5xx)

            data = response.json()

            return [
                {
                    "name": station.get("name", "Unknown"),
                    "type": station.get("type", "Unknown"),
                    "orbit": station.get("distanceToArrival", "Unknown"),
                    "allegiance": station.get("allegiance", "None"),
                    "government": station.get("government", "None"),
                    "economy": station.get("economy", "None"),
                    "secondEconomy": station.get("secondEconomy", "None"),
                    "controllingFaction": station.get("controllingFaction", {}).get(
                        "name", "Unknown"
                    ),
                    "services": [
                        service
                        for service, has_service in {
                            "market": station.get("haveMarket", False),
                            "shipyard": station.get("haveShipyard", False),
                            "outfitting": station.get("haveOutfitting", False),
                        }.items()
                        if has_service
                    ],
                    **(
                        {"body": station["body"]["name"]}
                        if "body" in station and "name" in station["body"]
                        else {}
                    ),
                }
                for station in data["stations"]
                if station["type"] != "Fleet Carrier"
            ]

        except Exception as e:
            log("error", f"Error: {e}")
            return "Currently no information on system available"

    def generate_vehicle_status(self, current_status:dict):
        flags = [key for key, value in current_status["flags"].items() if value]
        if current_status.get("flags2"):
            flags += [key for key, value in current_status["flags2"].items() if value]

        status_info = {
            "status": flags,
            "balance": current_status.get("Balance", None),
            "pips": current_status.get("Pips", None),
            "cargo": current_status.get("Cargo", None),
            "player_time": (datetime.now()).isoformat(),
            "elite_time": str(datetime.now().year + 1286) + (datetime.now()).isoformat()[4:],
        }

        flags = current_status["flags"]
        flags2 = current_status["flags2"]

        active_mode = 'Unknown vehicle'
        if flags:
            if flags["InMainShip"]:
                active_mode = "Main ship"
            elif flags["InFighter"]:
                active_mode = "Ship launched fighter"
            elif flags["InSRV"]:
                active_mode = "SRV"
        if flags2:
            if flags2["OnFoot"]:
                active_mode = "Suit"

        return active_mode, status_info

    def generate_status_message(self, projected_states: dict[str, dict]):
        status_entries: list[tuple[str, Any]] = []

        active_mode, vehicle_status = self.generate_vehicle_status(projected_states.get('CurrentStatus', {}))
        status_entries.append((active_mode+" status", vehicle_status))

        ship_info: ShipInfoState = projected_states.get('ShipInfo', {})  # pyright: ignore[reportAssignmentType]
        status_entries.append(("Main Ship", ship_info))

        location_info: LocationState = projected_states.get('Location', {})  # pyright: ignore[reportAssignmentType]
        nav_info: NavInfo = projected_states.get('NavInfo', {})  # pyright: ignore[reportAssignmentType]

        if "StarSystem" in location_info and location_info["StarSystem"] != "Unknown":
            status_entries.append(("Local system", self.get_system_info(location_info['StarSystem'])))

            status_entries.append(("Stations in local system", self.get_station_info(location_info['StarSystem'])))

        status_entries.append(("Location", location_info))

        status_entries.append(("Navigation route", nav_info))

        missions_info: MissionsState = projected_states.get('Missions', {})  # pyright: ignore[reportAssignmentType]
        if missions_info and 'Active' in missions_info:
            status_entries.append(("Active missions", missions_info))


        target_info: TargetState = projected_states.get('Target', {})  # pyright: ignore[reportAssignmentType]
        target_info.pop('EventID', None)
        if target_info.get('Ship', False):
            status_entries.append(("Weapons' target", target_info))

        current_station = projected_states.get('Location', {}).get('Station')
        market = projected_states.get('Market', {})
        outfitting = projected_states.get('Outfitting', {})
        storedShips = projected_states.get('StoredShips', {})
        if current_station and current_station == market.get('StationName'):
            status_entries.append(("Local market information", {
                item.get('Name_Localised'): {
                    'Category': item.get('Category_Localised'),
                    'BuyPrice': item.get('BuyPrice'),
                    'MeanPrice': item.get('MeanPrice'),
                    'Stock': item.get('Stock'),
                } if item.get('Stock') > item.get('Demand') else {
                    'Category': item.get('Category_Localised'),
                    'SellPrice': item.get('SellPrice'),
                    'MeanPrice': item.get('MeanPrice'),
                    'Demand': item.get('Demand'),
                }
                for item in market.get('Items',[]) if item.get('Stock') or item.get('Demand')
            }))
        if current_station and current_station == outfitting.get('StationName'):
            status_entries.append(("Local outfitting information", [
                {"Name": item.get('Name'), "BuyPrice": item.get('BuyPrice')}
                for item in outfitting.get('Items', [])
            ]))
        if current_station and current_station == storedShips.get('StationName'):
            status_entries.append(("Local, stored ships", storedShips.get('ShipsHere', [])))

        return "\n\n".join(['# '+entry[0]+'\n' + yaml.dump(entry[1]) for entry in status_entries])

    def generate_prompt(self, events: list[Event], projected_states: dict[str, dict], pending_events: list[Event]):
        # Fine the most recent event
        last_event = events[-1]
        reference_time = datetime.fromisoformat(last_event.content.get('timestamp') if isinstance(last_event, GameEvent) else last_event.timestamp)
        if not reference_time.tzinfo:
            reference_time = reference_time.astimezone()

        # Collect the last 50 conversational pieces
        conversational_pieces: list = list()

        for event in events[::-1]:
            if len(conversational_pieces) >= 50:
                break

            is_pending = event in pending_events
            event_time = datetime.fromisoformat(
                event.content.get('timestamp') if isinstance(event, GameEvent) else event.timestamp)
            if not event_time.tzinfo:
                event_time = event_time.astimezone()

            time_offset = humanize.naturaltime(reference_time - event_time)

            if isinstance(event, GameEvent):
                if event.content.get('event') in allGameEvents:
                    if len(conversational_pieces) < 5 or is_pending:
                        is_important = is_pending and event.content.get('event') in self.important_game_events
                        conversational_pieces.append(self.full_event_message(event, time_offset, is_important))
                    elif len(conversational_pieces) < 20:
                        conversational_pieces.append(self.simple_event_message(event, time_offset))
                    else:
                        pass
                else: 
                    log('debug', "PromptGenerator ignoring event", event.content.get('event'))

            if isinstance(event, ProjectedEvent):
                if event.content.get('event') in allGameEvents:
                    if len(conversational_pieces) < 5 or is_pending:
                        is_important = is_pending and event.content.get('event') in self.important_game_events
                        conversational_pieces.append(self.full_projectedevent_message(event, time_offset, is_important))
                    elif len(conversational_pieces) < 20:
                        conversational_pieces.append(self.simple_projectedevent_message(event, time_offset))
                    else:
                        pass
                else:
                    log('debug', "PromptGenerator ignoring event", event.content.get('event'))
            
            if isinstance(event, StatusEvent):
                if (
                    len(conversational_pieces) < 20
                    and event.status.get("event") != "Status"
                ):
                    conversational_pieces += self.status_messages(event)

            if isinstance(event, ConversationEvent) and event.kind in ['user', 'assistant']:
                conversational_pieces.append(self.conversation_message(event))

            if isinstance(event, ToolEvent):
                conversational_pieces += self.tool_messages(event)

            if isinstance(event, ExternalEvent):
                if event.content.get('event') in externalEvents:
                    conversational_pieces.append(self.external_event_message(event))

        conversational_pieces.append(
            {
                "role": "user",
                "content": self.generate_status_message(projected_states),
            }
        )

        try:
            conversational_pieces.append(
                {
                    "role": "system",
                    "content": "This universe is your reality. "
                    + "You do not ask questions. You do not initiate conversations. You respond only when addressed. "
                    + "Your purpose is to provide information, status updates, and execute commands as required. Only respond in a single sentence. "
                    + "I will provide game events in parentheses; do not create new ones. Stay consistent with the lived experience. "
                    + "Do not hallucinate any information that is not given to you. Do not use markdown in your responses. "
                    + self.character_prompt.format(commander_name=self.commander_name),
                }
            )
        except Exception as e:
            log('error', e, traceback.format_exc())
            log('error', 'Invalid character prompt, please keep the {commander_name} placeholder in the prompt.')

        conversational_pieces.reverse()  # Restore the original order

        #log('debug', 'states', json.dumps(projected_states))
        log('debug', 'conversation', json.dumps(conversational_pieces))

        return conversational_pieces
