from datetime import timedelta, datetime
from functools import lru_cache
from typing import Any, cast, Dict

import yaml
import requests
import humanize
import json

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

from .Projections import LocationState, MissionsState, ShipInfoState, NavInfo, TargetState, CurrentStatus, CargoState

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
                
        # if event_name == 'Location':
        #     location_event = cast(LocationEvent, content)
        #     location_details = []
        #
        #     if location_event.get('Docked'):
        #         station_type = f"{location_event.get('StationType')} " if location_event.get('StationType') else ""
        #         location_details.append(f"docked at {station_type}{location_event.get('StationName')}")
        #     elif location_event.get('BodyName'):
        #         if location_event.get('Latitude') is not None and location_event.get('Longitude') is not None:
        #             location_details.append(f"on {location_event.get('BodyName')} at coordinates {location_event.get('Latitude'):.4f}, {location_event.get('Longitude'):.4f}")
        #         else:
        #             location_details.append(f"near {location_event.get('BodyName')}")
        #             if location_event.get('DistFromStarLS'):
        #                 location_details.append(f"{location_event.get('DistFromStarLS'):.2f} ls from main star")
        #
        #     system_details = []
        #     if location_event.get('SystemAllegiance'):
        #         system_details.append(f"allegiance: {location_event.get('SystemAllegiance')}")
        #     if location_event.get('SystemEconomy'):
        #         economy = location_event.get('SystemEconomy_Localised', location_event.get('SystemEconomy'))
        #         system_details.append(f"economy: {economy}")
        #     if location_event.get('SystemGovernment'):
        #         government = location_event.get('SystemGovernment_Localised', location_event.get('SystemGovernment'))
        #         system_details.append(f"government: {government}")
        #     if location_event.get('SystemSecurity'):
        #         security = location_event.get('SystemSecurity_Localised', location_event.get('SystemSecurity'))
        #         system_details.append(f"security: {security}")
        #
        #     population = f", population: {location_event.get('Population'):,}" if location_event.get('Population') else ""
        #
        #     status_info = []
        #     if location_event.get('Wanted'):
        #         status_info.append("WANTED in this system")
        #     if location_event.get('Taxi'):
        #         status_info.append("in a taxi")
        #     elif location_event.get('Multicrew'):
        #         status_info.append("in multicrew session")
        #     elif location_event.get('InSRV'):
        #         status_info.append("in SRV")
        #     elif location_event.get('OnFoot'):
        #         status_info.append("on foot")
        #
        #     location_str = f" {', '.join(location_details)}" if location_details else ""
        #     system_details_str = f" ({', '.join(system_details)})" if system_details else ""
        #     status_str = f" ({', '.join(status_info)})" if status_info else ""
        #
        #     return f"{self.commander_name} is in the {location_event.get('StarSystem')} system{location_str}{system_details_str}{population}{status_str}."

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
            if content.get('SquadronName'):
                return f"{self.commander_name} has disbanded the squadron '{content.get('SquadronName')}'."
            else:
                return f"{self.commander_name} has disbanded their squadron."
        if event_name == 'InvitedToSquadron':
            if content.get('SquadronName'):
                return f"{self.commander_name} has been invited to join the squadron '{content.get('SquadronName')}'."
            else:
                return f"{self.commander_name} has been invited to join a squadron."
        if event_name == 'JoinedSquadron':
            if content.get('SquadronName'):
                return f"{self.commander_name} has joined the squadron '{content.get('SquadronName')}' with callsign {content.get('SquadronID', 'Unknown')}."
            else:
                return f"{self.commander_name} has joined a squadron."
        if event_name == 'KickedFromSquadron':
            if content.get('SquadronName'):
                return f"{self.commander_name} has been kicked from the squadron '{content.get('SquadronName')}'."
            else:
                return f"{self.commander_name} has been kicked from their squadron."
        if event_name == 'LeftSquadron':
            if content.get('SquadronName'):
                return f"{self.commander_name} has left the squadron '{content.get('SquadronName')}'."
            else:
                return f"{self.commander_name} has left their squadron."
        if event_name == 'SharedBookmarkToSquadron':
            bookmark_type = content.get('BookmarkType', 'Unknown')
            system_name = content.get('SystemName', 'Unknown system')
            if bookmark_type and system_name:
                return f"{self.commander_name} has shared a {bookmark_type} bookmark in {system_name} with their squadron."
            else:
                return f"{self.commander_name} has shared a bookmark with their squadron."
        if event_name == 'SquadronCreated':
            if content.get('SquadronName'):
                return f"{self.commander_name} has created a new squadron called '{content.get('SquadronName')}' with callsign {content.get('SquadronID', 'Unknown')}."
            else:
                return f"{self.commander_name} has created a new squadron."
        if event_name == 'SquadronDemotion':
            old_rank = content.get('OldRank', 'Unknown')
            new_rank = content.get('NewRank', 'Unknown')
            if content.get('SquadronName') and old_rank and new_rank:
                return f"{self.commander_name} has been demoted from {old_rank} to {new_rank} in the squadron '{content.get('SquadronName')}'."
            elif old_rank and new_rank:
                return f"{self.commander_name} has been demoted from {old_rank} to {new_rank} in their squadron."
            else:
                return f"{self.commander_name} has been demoted in their squadron."
        if event_name == 'SquadronPromotion':
            old_rank = content.get('OldRank', 'Unknown')
            new_rank = content.get('NewRank', 'Unknown')
            if content.get('SquadronName') and old_rank and new_rank:
                return f"{self.commander_name} has been promoted from {old_rank} to {new_rank} in the squadron '{content.get('SquadronName')}'."
            elif old_rank and new_rank:
                return f"{self.commander_name} has been promoted from {old_rank} to {new_rank} in their squadron."
            else:
                return f"{self.commander_name} has been promoted in their squadron."
        if event_name == 'WonATrophyForSquadron':
            if content.get('SquadronName') and content.get('TrophyName'):
                return f"{self.commander_name} has won a '{content.get('TrophyName')}' trophy for their squadron '{content.get('SquadronName')}'."
            elif content.get('TrophyName'):
                return f"{self.commander_name} has won a '{content.get('TrophyName')}' trophy for their squadron."
            else:
                return f"{self.commander_name} has won a trophy for their squadron."

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
            return f"{self.commander_name} has withdrawn their allegiance from {content.get('Power')}."
        if event_name == 'PowerplayDefect':
            return f"{self.commander_name} has defected from {content.get('FromPower')} to {content.get('ToPower')}."
        if event_name == 'PowerplayCollect':
            return f"{self.commander_name} has collected {content.get('Count')} units of {content.get('Type')} for {content.get('Power')}'s powerplay efforts."
        if event_name == 'PowerplayDeliver':
            return f"{self.commander_name} has delivered {content.get('Count')} units of {content.get('Type')} for {content.get('Power')}'s powerplay objectives."
        if event_name == 'PowerplayFastTrack':
            return f"{self.commander_name} has paid {content.get('Cost'):,} credits to fast-track allocation of powerplay commodities for {content.get('Power')}."
        if event_name == 'PowerplaySalary':
            return f"{self.commander_name} has received a salary payment of {content.get('Amount'):,} credits from {content.get('Power')}."
        if event_name == 'PowerplayVote':
            return f"{self.commander_name} has cast {content.get('Votes')} votes for {content.get('Power')}'s expansion into the {content.get('System')} system."
        if event_name == 'PowerplayVoucher':
            if content.get('Systems'):
                systems_list = ', '.join(content.get('Systems', []))
                return f"{self.commander_name} has received payment from {content.get('Power')} for combat operations in {systems_list}."
            else:
                return f"{self.commander_name} has received payment from {content.get('Power')} for powerplay combat operations."

        # Carrier events
        if event_name == 'CarrierJump':
            carrier_jump_event = cast(Dict[str, Any], content)
            star_system = carrier_jump_event.get('StarSystem', 'Unknown System')
            station_name = carrier_jump_event.get('StationName', 'Unknown Station')
            
            system_details = []
            if carrier_jump_event.get('SystemAllegiance'):
                system_details.append(f"allegiance: {carrier_jump_event.get('SystemAllegiance')}")
            if carrier_jump_event.get('SystemEconomy'):
                economy = carrier_jump_event.get('SystemEconomy_Localised', carrier_jump_event.get('SystemEconomy'))
                system_details.append(f"economy: {economy}")
            if carrier_jump_event.get('SystemGovernment'):
                government = carrier_jump_event.get('SystemGovernment_Localised', carrier_jump_event.get('SystemGovernment'))
                system_details.append(f"government: {government}")
            if carrier_jump_event.get('SystemSecurity'):
                security = carrier_jump_event.get('SystemSecurity_Localised', carrier_jump_event.get('SystemSecurity'))
                system_details.append(f"security: {security}")
            
            system_details_str = ", ".join(system_details)
            system_details_str = f" ({system_details_str})" if system_details_str else ""
            
            population = f", population: {carrier_jump_event.get('Population'):,}" if carrier_jump_event.get('Population') else ""
            
            body_info = ""
            if carrier_jump_event.get('Body'):
                body_type = f" ({carrier_jump_event.get('BodyType')})" if carrier_jump_event.get('BodyType') else ""
                body_info = f" near {carrier_jump_event.get('Body')}{body_type}"
            
            if 'Docked' in carrier_jump_event and carrier_jump_event.get('Docked'):
                return f"{self.commander_name} is docked at Fleet Carrier {station_name} which has jumped to the {star_system} system{body_info}{system_details_str}{population}."
            else:
                return f"Fleet Carrier {station_name} has jumped to the {star_system} system{body_info}{system_details_str}{population}."
            
        if event_name == 'CarrierBuy':
            carrier_buy_event = cast(Dict[str, Any], content)
            carrier_id = carrier_buy_event.get('CarrierID', 'Unknown ID')
            price = carrier_buy_event.get('Price', 0)
            location = carrier_buy_event.get('Location', 'an undisclosed location')
            variant = carrier_buy_event.get('Variant', 'Unknown Type')
            callsign = carrier_buy_event.get('Callsign', 'Unknown Callsign')
            return f"{self.commander_name} has purchased a Fleet Carrier with callsign {callsign} ({variant}) for {price:,} credits at {location}."
            
        if event_name == 'CarrierStats':
            carrier_stats_event = cast(Dict[str, Any], content)
            callsign = carrier_stats_event.get('Callsign', 'Unknown Callsign')
            carrier_name = carrier_stats_event.get('Name', callsign)
            balance = carrier_stats_event.get('Balance', 0)
            fuel = carrier_stats_event.get('Fuel', 0)
            reserve_percent = carrier_stats_event.get('ReservePercent', 0)
            services = carrier_stats_event.get('Services', [])
            
            service_str = ""
            if services:
                # Show just the first few services to avoid too long a message
                service_list = [s.get('Name', '') for s in services if s.get('Status') == 'Activated']
                if service_list:
                    service_str = f" Active services: {', '.join(service_list[:3])}"
                    if len(service_list) > 3:
                        service_str += f" and {len(service_list) - 3} more"
                
            return f"{self.commander_name}'s Fleet Carrier '{carrier_name}' ({callsign}) status update: {balance:,} credits balance, {fuel} tons of tritium, {reserve_percent}% reserve.{service_str}"
            
        if event_name == 'CarrierJumpRequest':
            carrier_jump_request_event = cast(Dict[str, Any], content)
            system_name = carrier_jump_request_event.get('SystemName', 'an unknown destination')
            
            body_info = ""
            if carrier_jump_request_event.get('Body'):
                body_info = f" near {carrier_jump_request_event.get('Body')}"
            
            departure_time = ""
            if carrier_jump_request_event.get('DepartureTime'):
                departure_time_str = carrier_jump_request_event.get('DepartureTime')
                try:
                    # Try to convert the time string to a more readable format
                    from datetime import datetime
                    dt = datetime.fromisoformat(departure_time_str.replace('Z', '+00:00'))
                    departure_time = f", departing at {dt.strftime('%H:%M:%S')}"
                except:
                    departure_time = f", departing at {departure_time_str}"
            
            return f"{self.commander_name} has requested their Fleet Carrier to jump to {system_name}{body_info}{departure_time}."
            
        if event_name == 'CarrierDecommission':
            carrier_decommission_event = cast(Dict[str, Any], content)
            refund = carrier_decommission_event.get('ScrapRefund', 0)
            
            scrap_time_info = ""
            if carrier_decommission_event.get('ScrapTime'):
                scrap_time = carrier_decommission_event.get('ScrapTime')
                if scrap_time is not None:
                    try:
                        # Try to convert the timestamp to a readable time
                        from datetime import datetime
                        dt = datetime.fromtimestamp(float(scrap_time))
                        scrap_time_info = f" The carrier will be decommissioned on {dt.strftime('%Y-%m-%d at %H:%M:%S')}."
                    except (ValueError, TypeError):
                        pass
                
            return f"{self.commander_name} has initiated the decommissioning process for their Fleet Carrier. Expected refund: {refund:,} credits.{scrap_time_info}"
            
        if event_name == 'CarrierCancelDecommission':
            return f"{self.commander_name} has cancelled the decommissioning process for their Fleet Carrier."
            
        if event_name == 'CarrierBankTransfer':
            carrier_bank_event = cast(Dict[str, Any], content)
            deposit = carrier_bank_event.get('Deposit', 0)
            withdraw = carrier_bank_event.get('Withdraw', 0)
            player_balance = carrier_bank_event.get('PlayerBalance', 0)
            carrier_balance = carrier_bank_event.get('CarrierBalance', 0)
            
            if deposit > 0:
                return f"{self.commander_name} has deposited {deposit:,} credits to their Fleet Carrier account. Carrier balance: {carrier_balance:,} credits. Commander's balance: {player_balance:,} credits."
            else:
                return f"{self.commander_name} has withdrawn {withdraw:,} credits from their Fleet Carrier account. Carrier balance: {carrier_balance:,} credits. Commander's balance: {player_balance:,} credits."
            
        if event_name == 'CarrierDepositFuel':
            carrier_fuel_event = cast(Dict[str, Any], content)
            amount = carrier_fuel_event.get('Amount', 0)
            total = carrier_fuel_event.get('Total', 0)
            return f"{self.commander_name} has deposited {amount} tons of tritium fuel to their Fleet Carrier. Total fuel: {total} tons."
            
        if event_name == 'CarrierCrewServices':
            carrier_crew_event = cast(Dict[str, Any], content)
            operation = carrier_crew_event.get('Operation', 'Unknown')
            crew_role = carrier_crew_event.get('CrewRole', 'Unknown')
            crew_name = carrier_crew_event.get('CrewName', 'a crew member')
            
            operation_str = str(operation).lower()
            if operation_str == 'activate':
                return f"{self.commander_name} has activated the {crew_role} service on their Fleet Carrier, hiring {crew_name}."
            elif operation_str == 'deactivate':
                return f"{self.commander_name} has deactivated the {crew_role} service on their Fleet Carrier, dismissing {crew_name}."
            elif operation_str == 'pause':
                return f"{self.commander_name} has temporarily paused the {crew_role} service on their Fleet Carrier, operated by {crew_name}."
            elif operation_str == 'resume':
                return f"{self.commander_name} has resumed the {crew_role} service on their Fleet Carrier, operated by {crew_name}."
            elif operation_str == 'replace':
                return f"{self.commander_name} has replaced the crew member for the {crew_role} service on their Fleet Carrier, hiring {crew_name}."
            else:
                return f"{self.commander_name} has made changes to the {crew_role} service on their Fleet Carrier, affecting {crew_name}."
            
        if event_name == 'CarrierFinance':
            carrier_finance_event = cast(Dict[str, Any], content)
            tax_rate = carrier_finance_event.get('TaxRate', 0)
            carrier_balance = carrier_finance_event.get('CarrierBalance', 0)
            reserve_balance = carrier_finance_event.get('ReserveBalance', 0)
            available_balance = carrier_finance_event.get('AvailableBalance', 0)
            reserve_percent = carrier_finance_event.get('ReservePercent', 0)
            
            return f"{self.commander_name} has updated their Fleet Carrier finances. Tax rate: {tax_rate}%, Available balance: {available_balance:,} credits, Reserve: {reserve_balance:,} credits ({reserve_percent}%), Total balance: {carrier_balance:,} credits."
            
        if event_name == 'CarrierShipPack':
            carrier_ship_pack_event = cast(Dict[str, Any], content)
            operation = carrier_ship_pack_event.get('Operation', 'Unknown')
            pack_theme = carrier_ship_pack_event.get('PackTheme', 'Unknown')
            pack_tier = carrier_ship_pack_event.get('PackTier', '')
            
            tier_str = f" Tier {pack_tier}" if pack_tier else ""
            
            operation_str = str(operation).lower()
            if operation_str == 'buypack':
                cost = carrier_ship_pack_event.get('Cost', 0)
                return f"{self.commander_name} has purchased the {pack_theme}{tier_str} ship pack for their Fleet Carrier for {cost:,} credits."
            elif operation_str == 'sellpack':
                refund = carrier_ship_pack_event.get('Refund', 0)
                return f"{self.commander_name} has sold the {pack_theme}{tier_str} ship pack from their Fleet Carrier for {refund:,} credits."
            elif operation_str == 'restockpack':
                cost = carrier_ship_pack_event.get('Cost', 0)
                return f"{self.commander_name} has restocked the {pack_theme}{tier_str} ship pack on their Fleet Carrier for {cost:,} credits."
            else:
                return f"{self.commander_name} has modified the {pack_theme}{tier_str} ship pack on their Fleet Carrier."
                
        if event_name == 'CarrierModulePack':
            carrier_module_pack_event = cast(Dict[str, Any], content)
            operation = carrier_module_pack_event.get('Operation', 'Unknown')
            pack_theme = carrier_module_pack_event.get('PackTheme', 'Unknown')
            pack_tier = carrier_module_pack_event.get('PackTier', '')
            
            tier_str = f" Tier {pack_tier}" if pack_tier else ""
            
            operation_str = str(operation).lower()
            if operation_str == 'buypack':
                cost = carrier_module_pack_event.get('Cost', 0)
                return f"{self.commander_name} has purchased the {pack_theme}{tier_str} module pack for their Fleet Carrier for {cost:,} credits."
            elif operation_str == 'sellpack':
                refund = carrier_module_pack_event.get('Refund', 0)
                return f"{self.commander_name} has sold the {pack_theme}{tier_str} module pack from their Fleet Carrier for {refund:,} credits."
            elif operation_str == 'restockpack':
                cost = carrier_module_pack_event.get('Cost', 0)
                return f"{self.commander_name} has restocked the {pack_theme}{tier_str} module pack on their Fleet Carrier for {cost:,} credits."
            else:
                return f"{self.commander_name} has modified the {pack_theme}{tier_str} module pack on their Fleet Carrier."
            
        if event_name == 'CarrierTradeOrder':
            carrier_trade_event = cast(Dict[str, Any], content)
            black_market = " on the black market" if carrier_trade_event.get('BlackMarket') else ""
            
            if 'CancelTrade' in carrier_trade_event and carrier_trade_event.get('CancelTrade'):
                commodity = carrier_trade_event.get('Commodity_Localised', carrier_trade_event.get('Commodity', 'commodities'))
                return f"{self.commander_name} has cancelled trade orders for {commodity}{black_market} on their Fleet Carrier."
            elif 'PurchaseOrder' in carrier_trade_event:
                commodity = carrier_trade_event.get('Commodity_Localised', carrier_trade_event.get('Commodity', 'commodities'))
                quantity = carrier_trade_event.get('PurchaseOrder', 0)
                price = carrier_trade_event.get('Price', 0)
                return f"{self.commander_name} has set up a buy order for {quantity} units of {commodity}{black_market} at {price:,} credits per unit on their Fleet Carrier."
            elif 'SaleOrder' in carrier_trade_event:
                commodity = carrier_trade_event.get('Commodity_Localised', carrier_trade_event.get('Commodity', 'commodities'))
                quantity = carrier_trade_event.get('SaleOrder', 0)
                price = carrier_trade_event.get('Price', 0)
                return f"{self.commander_name} has set up a sell order for {quantity} units of {commodity}{black_market} at {price:,} credits per unit on their Fleet Carrier."
            else:
                return f"{self.commander_name} has modified trade orders on their Fleet Carrier."
            
        if event_name == 'CarrierDockingPermission':
            carrier_docking_event = cast(Dict[str, Any], content)
            access = carrier_docking_event.get('DockingAccess', 'Unknown')
            allow_notorious = carrier_docking_event.get('AllowNotorious', False)
            
            access_map = {
                'all': 'all pilots',
                'none': 'no pilots',
                'friends': 'friends only',
                'squadron': 'squadron members only',
                'squadronfriends': 'squadron members and friends'
            }
            
            access_str = access_map.get(str(access).lower(), access)
            notorious_str = " including those with notorious status" if allow_notorious else ""
            
            return f"{self.commander_name} has updated their Fleet Carrier docking permissions to allow {access_str}{notorious_str}."
            
        if event_name == 'CarrierNameChanged':
            carrier_name_event = cast(Dict[str, Any], content)
            callsign = carrier_name_event.get('Callsign', 'Unknown Callsign')
            name = carrier_name_event.get('Name', 'Unknown Name')
            return f"{self.commander_name} has changed their Fleet Carrier's name to '{name}' (callsign: {callsign})."
            
        if event_name == 'CarrierJumpCancelled':
            return f"{self.commander_name} has cancelled the pending jump of their Fleet Carrier."
            
        if event_name == 'FCMaterials':
            fc_materials_event = cast(Dict[str, Any], content)
            carrier_name = fc_materials_event.get('CarrierName', 'their Fleet Carrier')
            return f"{self.commander_name} has accessed the materials bartender on {carrier_name}."

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
        # Trade events
        if event_name == 'AsteroidCracked':
            asteroid_cracked_event = cast(Dict[str, Any], content)
            body = asteroid_cracked_event.get('Body', 'an unknown body')
            return f"{self.commander_name} has cracked a motherlode asteroid near {body} for mining."
            
        if event_name == 'BuyTradeData':
            buy_trade_data_event = cast(Dict[str, Any], content)
            system = buy_trade_data_event.get('System', 'Unknown system')
            cost = buy_trade_data_event.get('Cost', 0)
            return f"{self.commander_name} has purchased trade data for the {system} system for {cost:,} credits."
            
        if event_name == 'CollectCargo':
            collect_cargo_event = cast(Dict[str, Any], content)
            cargo_type = collect_cargo_event.get('Type_Localised', collect_cargo_event.get('Type', 'unknown cargo'))
            stolen = " (stolen)" if collect_cargo_event.get('Stolen', False) else ""
            mission_related = " for a mission" if collect_cargo_event.get('MissionID') else ""
            return f"{self.commander_name} has collected {cargo_type}{stolen}{mission_related}."
            
        if event_name == 'EjectCargo':
            eject_cargo_event = cast(Dict[str, Any], content)
            cargo_type = eject_cargo_event.get('Type_Localised', eject_cargo_event.get('Type', 'unknown cargo'))
            count = eject_cargo_event.get('Count', 1)
            abandoned = "abandoned" if eject_cargo_event.get('Abandoned', False) else "ejected"
            mission_related = " from a mission" if eject_cargo_event.get('MissionID') else ""
            
            powerplay_info = ""
            if eject_cargo_event.get('PowerplayOrigin'):
                powerplay_info = f" (from {eject_cargo_event.get('PowerplayOrigin')})"
            
            return f"{self.commander_name} has {abandoned} {count} units of {cargo_type}{mission_related}{powerplay_info}."
            
        if event_name == 'MarketBuy':
            market_buy_event = cast(Dict[str, Any], content)
            item_type = market_buy_event.get('Type_Localised', market_buy_event.get('Type', 'unknown goods'))
            count = market_buy_event.get('Count', 0)
            buy_price = market_buy_event.get('BuyPrice', 0)
            total_cost = market_buy_event.get('TotalCost', 0)
            
            return f"{self.commander_name} has purchased {count} units of {item_type} for {buy_price:,} credits each (total: {total_cost:,} credits)."
            
        if event_name == 'MarketSell':
            market_sell_event = cast(Dict[str, Any], content)
            item_type = market_sell_event.get('Type_Localised', market_sell_event.get('Type', 'unknown goods'))
            count = market_sell_event.get('Count', 0)
            sell_price = market_sell_event.get('SellPrice', 0)
            total_sale = market_sell_event.get('TotalSale', 0)
            avg_price_paid = market_sell_event.get('AvgPricePaid', 0)
            
            special_flags = []
            if market_sell_event.get('IllegalGoods'):
                special_flags.append("illegal goods")
            if market_sell_event.get('StolenGoods'):
                special_flags.append("stolen goods")
            if market_sell_event.get('BlackMarket'):
                special_flags.append("using black market")
                
            special_info = f" ({', '.join(special_flags)})" if special_flags else ""
            profit_info = ""
            if avg_price_paid > 0:
                profit = total_sale - (avg_price_paid * count)
                profit_info = f", profit: {profit:,} credits"
            
            return f"{self.commander_name} has sold {count} units of {item_type} for {sell_price:,} credits each (total: {total_sale:,} credits{profit_info}){special_info}."
            
        if event_name == 'MiningRefined':
            mining_refined_event = cast(Dict[str, Any], content)
            material_type = mining_refined_event.get('Type_Localised', mining_refined_event.get('Type', 'unknown material'))
            
            return f"{self.commander_name} has refined mining fragments into 1 ton of {material_type}."

        # Odyssey events
        if event_name == 'Backpack':
            # This is primarily for the backpack.json file, but we'll report it in the journal too
            return f"{self.commander_name}'s backpack contents have been updated."
            
        if event_name == 'BackpackChange':
            backpack_event = cast(Dict[str, Any], content)
            if backpack_event.get('Added'):
                item_list = backpack_event.get('Added', [])
                item_names = [item.get('Name_Localised', item.get('Name', 'unknown item')) for item in item_list]
                if len(item_names) == 1:
                    return f"{self.commander_name} has added {item_names[0]} to their backpack."
                else:
                    return f"{self.commander_name} has added multiple items to their backpack: {', '.join(item_names)}."
            elif backpack_event.get('Removed'):
                item_list = backpack_event.get('Removed', [])
                item_names = [item.get('Name_Localised', item.get('Name', 'unknown item')) for item in item_list]
                if len(item_names) == 1:
                    return f"{self.commander_name} has removed {item_names[0]} from their backpack."
                else:
                    return f"{self.commander_name} has removed multiple items from their backpack: {', '.join(item_names)}."
            return f"{self.commander_name}'s backpack contents have changed."
            
        if event_name == 'BookDropship':
            return f"{self.commander_name} has booked a combat dropship."
            
        if event_name == 'BookTaxi':
            taxi_event = cast(Dict[str, Any], content)
            cost = taxi_event.get('Cost', 0)
            dest_sys = taxi_event.get('DestinationSystem', 'unknown system')
            dest_loc = taxi_event.get('DestinationLocation', 'unknown location')
            retreat = " to retreat from a combat zone" if taxi_event.get('Retreat') else ""
            return f"{self.commander_name} has booked a taxi to {dest_loc} in {dest_sys} for {cost:,} credits{retreat}."
            
        if event_name == 'BuyMicroResources':
            buy_event = cast(Dict[str, Any], content)
            if buy_event.get('MicroResources'):
                # New format with multiple items
                total_cost = buy_event.get('Price', 0)
                total_count = buy_event.get('TotalCount', 0)
                resources = buy_event.get('MicroResources', [])
                if len(resources) == 1:
                    item = resources[0]
                    item_name = item.get('Name_Localised', item.get('Name', 'unknown item'))
                    count = item.get('Count', 0)
                    return f"{self.commander_name} has purchased {count} units of {item_name} for {total_cost:,} credits."
                else:
                    return f"{self.commander_name} has purchased {total_count} units of various microresources for {total_cost:,} credits."
            else:
                # Old format with single item
                name = buy_event.get('Name_Localised', buy_event.get('Name', 'unknown item'))
                count = buy_event.get('Count', 0)
                price = buy_event.get('Price', 0)
                return f"{self.commander_name} has purchased {count} units of {name} for {price:,} credits."
                
        if event_name == 'BuySuit':
            suit_event = cast(Dict[str, Any], content)
            suit_name = suit_event.get('Name_Localised', suit_event.get('Name', 'unknown suit'))
            price = suit_event.get('Price', 0)
            return f"{self.commander_name} has purchased a {suit_name} for {price:,} credits."
            
        if event_name == 'BuyWeapon':
            weapon_event = cast(Dict[str, Any], content)
            weapon_name = weapon_event.get('Name_Localised', weapon_event.get('Name', 'unknown weapon'))
            price = weapon_event.get('Price', 0)
            return f"{self.commander_name} has purchased a {weapon_name} for {price:,} credits."
            
        if event_name == 'CancelDropship':
            return f"{self.commander_name} has cancelled their combat dropship journey."
            
        if event_name == 'CancelTaxi':
            taxi_event = cast(Dict[str, Any], content)
            refund = taxi_event.get('Refund', 0)
            return f"{self.commander_name} has cancelled their taxi journey and received a refund of {refund:,} credits."
            
        if event_name == 'CollectItems':
            collect_event = cast(Dict[str, Any], content)
            item_name = collect_event.get('Name_Localised', collect_event.get('Name', 'unknown item'))
            count = collect_event.get('Count', 1)
            stolen = " (stolen)" if collect_event.get('Stolen') else ""
            if count == 1:
                return f"{self.commander_name} has collected 1 {item_name}{stolen}."
            else:
                return f"{self.commander_name} has collected {count} {item_name}s{stolen}."
            
        if event_name == 'CreateSuitLoadout':
            loadout_event = cast(Dict[str, Any], content)
            loadout_name = loadout_event.get('LoadoutName', 'new loadout')
            suit_name = loadout_event.get('SuitName_Localised', loadout_event.get('SuitName', 'unknown suit'))
            return f"{self.commander_name} has created a new suit loadout named '{loadout_name}' for their {suit_name}."
            
        if event_name == 'DeleteSuitLoadout':
            loadout_event = cast(Dict[str, Any], content)
            loadout_name = loadout_event.get('LoadoutName', 'loadout')
            suit_name = loadout_event.get('SuitName_Localised', loadout_event.get('SuitName', 'unknown suit'))
            return f"{self.commander_name} has deleted the suit loadout named '{loadout_name}' for their {suit_name}."
            
        if event_name == 'Disembark':
            disembark_event = cast(Dict[str, Any], content)
            if disembark_event.get('SRV'):
                vehicle = "SRV"
            elif disembark_event.get('Taxi'):
                vehicle = "taxi"
            elif disembark_event.get('Multicrew'):
                vehicle = "another commander's vessel"
            else:
                vehicle = "ship"
            
            if disembark_event.get('OnStation'):
                location = f"at {disembark_event.get('StationName', 'a station')}"
            elif disembark_event.get('OnPlanet'):
                location = f"on {disembark_event.get('Body', 'a planet')}"
            else:
                location = ""
                
            return f"{self.commander_name} has disembarked from their {vehicle} {location}."
            
        if event_name == 'DropItems':
            drop_event = cast(Dict[str, Any], content)
            item_name = drop_event.get('Name_Localised', drop_event.get('Name', 'unknown item'))
            count = drop_event.get('Count', 1)
            if count == 1:
                return f"{self.commander_name} has dropped 1 {item_name}."
            else:
                return f"{self.commander_name} has dropped {count} {item_name}s."
            
        if event_name == 'DropShipDeploy':
            return f"{self.commander_name} has deployed from a dropship to a conflict zone."
            
        if event_name == 'Embark':
            embark_event = cast(Dict[str, Any], content)
            if embark_event.get('SRV'):
                vehicle = "SRV"
            elif embark_event.get('Taxi'):
                vehicle = "taxi"
            elif embark_event.get('Multicrew'):
                vehicle = "another commander's vessel"
            else:
                vehicle = "ship"
                
            if embark_event.get('OnStation'):
                location = f"at {embark_event.get('StationName', 'a station')}"
            elif embark_event.get('OnPlanet'):
                location = f"on {embark_event.get('Body', 'a planet')}"
            else:
                location = ""
                
            return f"{self.commander_name} has embarked into their {vehicle} {location}."
            
        if event_name == 'FCMaterials':
            fc_event = cast(Dict[str, Any], content)
            carrier_name = fc_event.get('CarrierName', 'a Fleet Carrier')
            return f"{self.commander_name} has accessed the materials bartender on {carrier_name}."
            
        if event_name == 'LoadoutEquipModule':
            equip_event = cast(Dict[str, Any], content)
            slot = equip_event.get('SlotName', 'a slot')
            module = equip_event.get('ModuleName_Localised', equip_event.get('ModuleName', 'an item'))
            loadout = equip_event.get('LoadoutName', 'loadout')
            suit = equip_event.get('SuitName_Localised', equip_event.get('SuitName', 'suit'))
            return f"{self.commander_name} has equipped {module} to {slot} on their {suit} loadout '{loadout}'."
            
        if event_name == 'LoadoutRemoveModule':
            remove_event = cast(Dict[str, Any], content)
            slot = remove_event.get('SlotName', 'a slot')
            module = remove_event.get('ModuleName_Localised', remove_event.get('ModuleName', 'an item'))
            loadout = remove_event.get('LoadoutName', 'loadout')
            suit = remove_event.get('SuitName_Localised', remove_event.get('SuitName', 'suit'))
            return f"{self.commander_name} has removed {module} from {slot} on their {suit} loadout '{loadout}'."
            
        if event_name == 'RenameSuitLoadout':
            rename_event = cast(Dict[str, Any], content)
            loadout = rename_event.get('LoadoutName', 'loadout')
            suit = rename_event.get('SuitName_Localised', rename_event.get('SuitName', 'suit'))
            return f"{self.commander_name} has renamed a loadout to '{loadout}' for their {suit}."
            
        if event_name == 'ScanOrganic':
            scan_event = cast(Dict[str, Any], content)
            scan_type = scan_event.get('ScanType', 'unknown')
            species = scan_event.get('Species_Localised', scan_event.get('Species', 'unknown species'))
            variant = scan_event.get('Variant_Localised', scan_event.get('Variant', ''))
            if variant and variant != species:
                life_form = f"{variant} ({species})"
            else:
                life_form = species
                
            if scan_type == 'Log':
                action = "logged"
            elif scan_type == 'Sample':
                action = "taken a sample from"
            elif scan_type == 'Analyse':
                action = "analyzed"
            else:
                action = "scanned"
                
            return f"{self.commander_name} has {action} a {life_form} on planet {scan_event.get('Body', 'unknown body')}."
            
        if event_name == 'SellMicroResources':
            sell_event = cast(Dict[str, Any], content)
            resources = sell_event.get('MicroResources', [])
            price = sell_event.get('Price', 0)
            
            if len(resources) == 1:
                item = resources[0]
                item_name = item.get('Name_Localised', item.get('Name', 'unknown item'))
                count = item.get('Count', 0)
                return f"{self.commander_name} has sold {count} units of {item_name} for {price:,} credits."
            else:
                item_names = [r.get('Name_Localised', r.get('Name', 'unknown item')) for r in resources]
                return f"{self.commander_name} has sold various microresources ({', '.join(item_names)}) for {price:,} credits."
                
        if event_name == 'SellOrganicData':
            data_event = cast(Dict[str, Any], content)
            biodata = data_event.get('BioData', [])
            total_value = sum(data.get('Value', 0) for data in biodata)
            total_bonus = sum(data.get('Bonus', 0) for data in biodata)
            
            if len(biodata) == 1:
                species = biodata[0].get('Species_Localised', biodata[0].get('Species', 'unknown species'))
                variant = biodata[0].get('Variant_Localised', biodata[0].get('Variant', ''))
                if variant and variant != species:
                    life_form = f"{variant} ({species})"
                else:
                    life_form = species
                    
                value = biodata[0].get('Value', 0)
                bonus = biodata[0].get('Bonus', 0)
                total = value + bonus
                return f"{self.commander_name} has sold organic data for {life_form} for {total:,} credits (base: {value:,}, bonus: {bonus:,})."
            else:
                total = total_value + total_bonus
                return f"{self.commander_name} has sold organic data for {len(biodata)} species for a total of {total:,} credits (base: {total_value:,}, bonus: {total_bonus:,})."
                
        if event_name == 'SellSuit':
            suit_event = cast(Dict[str, Any], content)
            suit_name = suit_event.get('Name_Localised', suit_event.get('Name', 'unknown suit'))
            price = suit_event.get('Price', 0)
            return f"{self.commander_name} has sold their {suit_name} for {price:,} credits."
            
        if event_name == 'SellWeapon':
            weapon_event = cast(Dict[str, Any], content)
            weapon_name = weapon_event.get('Name_Localised', weapon_event.get('Name', 'unknown weapon'))
            price = weapon_event.get('Price', 0)
            return f"{self.commander_name} has sold their {weapon_name} for {price:,} credits."
            
        if event_name == 'ShipLocker':
            # This is primarily for the ShipLocker.json file, but we'll report it in the journal too
            return f"{self.commander_name}'s ship locker inventory has been updated."
            
        if event_name == 'SuitLoadout':
            loadout_event = cast(Dict[str, Any], content)
            suit_name = loadout_event.get('SuitName_Localised', loadout_event.get('SuitName', 'unknown suit'))
            loadout_name = loadout_event.get('LoadoutName', 'loadout')
            return f"{self.commander_name} is using the '{loadout_name}' loadout for their {suit_name}."
            
        if event_name == 'SwitchSuitLoadout':
            loadout_event = cast(Dict[str, Any], content)
            suit_name = loadout_event.get('SuitName_Localised', loadout_event.get('SuitName', 'unknown suit'))
            loadout_name = loadout_event.get('LoadoutName', 'loadout')
            return f"{self.commander_name} has switched to the '{loadout_name}' loadout for their {suit_name}."
            
        if event_name == 'TransferMicroResources':
            transfer_event = cast(Dict[str, Any], content)
            transfers = transfer_event.get('Transfers', [])
            
            if len(transfers) == 1:
                item = transfers[0]
                item_name = item.get('Name_Localised', item.get('Name', 'unknown item'))
                count = item.get('Count', 0)
                direction = item.get('Direction', '')
                
                if direction == 'ToBackpack':
                    return f"{self.commander_name} has transferred {count} units of {item_name} from their ship locker to their backpack."
                else:
                    return f"{self.commander_name} has transferred {count} units of {item_name} from their backpack to their ship locker."
            else:
                to_backpack = any(t.get('Direction') == 'ToBackpack' for t in transfers)
                if to_backpack:
                    return f"{self.commander_name} has transferred multiple items from their ship locker to their backpack."
                else:
                    return f"{self.commander_name} has transferred multiple items from their backpack to their ship locker."
        
        if event_name == 'TradeMicroResources':
            trade_event = cast(Dict[str, Any], content)
            offered = trade_event.get('Offered', [])
            received = trade_event.get('Received_Localised', trade_event.get('Received', 'unknown resource'))
            count_received = trade_event.get('Count', 0)
            
            if len(offered) == 1:
                offered_name = offered[0].get('Name_Localised', offered[0].get('Name', 'unknown item'))
                offered_count = offered[0].get('Count', 0)
                return f"{self.commander_name} has traded {offered_count} units of {offered_name} for {count_received} units of {received}."
            else:
                offered_names = [o.get('Name_Localised', o.get('Name', 'unknown item')) for o in offered]
                return f"{self.commander_name} has traded multiple resources ({', '.join(offered_names)}) for {count_received} units of {received}."
        
        if event_name == 'UpgradeSuit':
            upgrade_event = cast(Dict[str, Any], content)
            suit_name = upgrade_event.get('Name_Localised', upgrade_event.get('Name', 'unknown suit'))
            class_level = upgrade_event.get('Class', 0)
            cost = upgrade_event.get('Cost', 0)
            resources = upgrade_event.get('Resources', [])
            resource_names = [r.get('Name_Localised', r.get('Name', 'unknown material')) for r in resources]
            
            if resource_names:
                material_info = f" using {', '.join(resource_names)}"
            else:
                material_info = ""
                
            return f"{self.commander_name} has upgraded their {suit_name} to class {class_level} for {cost:,} credits{material_info}."
        
        if event_name == 'UpgradeWeapon':
            upgrade_event = cast(Dict[str, Any], content)
            weapon_name = upgrade_event.get('Name_Localised', upgrade_event.get('Name', 'unknown weapon'))
            class_level = upgrade_event.get('Class', 0)
            cost = upgrade_event.get('Cost', 0)
            resources = upgrade_event.get('Resources', [])
            resource_names = [r.get('Name_Localised', r.get('Name', 'unknown material')) for r in resources]
            
            if resource_names:
                material_info = f" using {', '.join(resource_names)}"
            else:
                material_info = ""
                
            return f"{self.commander_name} has upgraded their {weapon_name} to class {class_level} for {cost:,} credits{material_info}."
        
        if event_name == 'UseConsumable':
            use_event = cast(Dict[str, Any], content)
            item_name = use_event.get('Name_Localised', use_event.get('Name', 'unknown consumable'))
            return f"{self.commander_name} has used a {item_name}."

        # Adding handlers for "Other Events" from the Journal documentation
        if event_name == 'AfmuRepairs':
            afmu_event = cast(Dict[str, Any], content)
            module = afmu_event.get('Module_Localised', afmu_event.get('Module', 'a module'))
            fully_repaired = "fully" if afmu_event.get('FullyRepaired') else "partially"
            health = afmu_event.get('Health', 0) * 100
            return f"{self.commander_name} has {fully_repaired} repaired {module} to {health:.1f}% health using the AFMU."

        if event_name == 'ApproachSettlement':
            approach_event = cast(Dict[str, Any], content)
            name = approach_event.get('Name', 'a settlement')
            body_name = approach_event.get('BodyName', '')
            body_details = f" on {body_name}" if body_name else ""
            return f"{self.commander_name} is approaching {name} settlement{body_details}."

        if event_name == 'ChangeCrewRole':
            crew_role_event = cast(Dict[str, Any], content)
            role = crew_role_event.get('Role', 'Unknown')
            telepresence = " via telepresence" if crew_role_event.get('Telepresence') else ""
            return f"{self.commander_name} has switched to {role} crew role{telepresence}."

        if event_name == 'CockpitBreached':
            return f"{self.commander_name}'s ship cockpit has been breached! Emergency oxygen engaged."

        if event_name == 'CommitCrime':
            crime_event = cast(Dict[str, Any], content)
            crime_type = crime_event.get('CrimeType', 'unknown crime')
            faction = crime_event.get('Faction', 'local authorities')

            details = ""
            if crime_event.get('Victim'):
                details += f" against {crime_event.get('Victim')}"

            punishment = ""
            if crime_event.get('Bounty'):
                punishment = f" A bounty of {crime_event.get('Bounty'):,} credits has been issued."
            elif crime_event.get('Fine'):
                punishment = f" A fine of {crime_event.get('Fine'):,} credits has been issued."

            return f"{self.commander_name} has committed a crime: {crime_type}{details} against {faction}.{punishment}"

        if event_name == 'Continued':
            continued_event = cast(Dict[str, Any], content)
            part = continued_event.get('Part', '?')
            return f"Journal file continued in part {part}."

        if event_name == 'CrewLaunchFighter':
            crew_launch_event = cast(Dict[str, Any], content)
            crew = crew_launch_event.get('Crew', 'A crew member')
            telepresence = " via telepresence" if crew_launch_event.get('Telepresence') else ""
            return f"{crew} has launched a fighter from {self.commander_name}'s ship{telepresence}."

        if event_name == 'DatalinkScan':
            datalink_event = cast(Dict[str, Any], content)
            message = datalink_event.get('Message', 'No message received')
            return f"{self.commander_name} has scanned a datalink and received: \"{message}\""

        if event_name == 'DatalinkVoucher':
            voucher_event = cast(Dict[str, Any], content)
            reward = voucher_event.get('Reward', 0)
            victim = voucher_event.get('VictimFaction', 'unknown faction')
            payee = voucher_event.get('PayeeFaction', 'unknown faction')
            return f"{self.commander_name} has received a datalink voucher worth {reward:,} credits from {payee} for data about {victim}."

        if event_name == 'DataScanned':
            data_scan_event = cast(Dict[str, Any], content)
            scan_type = data_scan_event.get('Type', 'unknown data')
            return f"{self.commander_name} has scanned a {scan_type}."

        if event_name == 'DockFighter':
            return f"{self.commander_name} has docked their fighter with the mothership."

        if event_name == 'DockSRV':
            srv_event = cast(Dict[str, Any], content)
            srv_type = srv_event.get('SRVType', 'SRV')
            return f"{self.commander_name} has docked their {srv_type} with the ship."

        if event_name == 'EndCrewSession':
            end_crew_event = cast(Dict[str, Any], content)
            reason = ""
            if end_crew_event.get('OnCrime'):
                reason = " due to criminal activity"
            telepresence = " telepresence" if end_crew_event.get('Telepresence') else ""
            return f"{self.commander_name} has ended the{telepresence} multicrew session{reason}."

        if event_name == 'FighterRebuilt':
            rebuild_event = cast(Dict[str, Any], content)
            loadout = rebuild_event.get('Loadout', 'a fighter')
            return f"{self.commander_name}'s {loadout} fighter has been rebuilt in the hangar."

        if event_name == 'FuelScoop':
            fuel_event = cast(Dict[str, Any], content)
            scooped = fuel_event.get('Scooped', 0)
            total = fuel_event.get('Total', 0)
            return f"{self.commander_name} has scooped {scooped:.2f} tons of fuel. Tank now contains {total:.2f} tons."

        if event_name == 'JetConeBoost':
            boost_event = cast(Dict[str, Any], content)
            boost = boost_event.get('BoostValue', 0)
            return f"{self.commander_name} has received a {boost:.1f}x FSD boost from a jet cone."

        if event_name == 'JetConeDamage':
            damage_event = cast(Dict[str, Any], content)
            module = damage_event.get('Module', 'a module')
            return f"{self.commander_name}'s ship has suffered damage to {module} while flying through a jet cone."

        if event_name == 'LaunchDrone':
            drone_event = cast(Dict[str, Any], content)
            drone_type = drone_event.get('Type', 'unknown drone')
            type_map = {
                'Prospector': 'a prospector drone',
                'Collection': 'a collector drone',
                'Hatchbreaker': 'a hatchbreaker drone',
                'Recon': 'a recon limpet',
                'Research': 'a research limpet',
                'Decontamination': 'a decontamination limpet',
                'Repair': 'a repair limpet',
                'Fuel': 'a fuel transfer limpet'
            }
            drone_name = type_map.get(drone_type, f"a {drone_type} drone")
            return f"{self.commander_name} has launched {drone_name}."

        if event_name == 'LaunchFighter':
            fighter_event = cast(Dict[str, Any], content)
            player_controlled = "player-controlled" if fighter_event.get('PlayerControlled') else "AI-controlled"
            loadout = fighter_event.get('Loadout', '')
            loadout_info = f" ({loadout})" if loadout else ""
            return f"{self.commander_name} has launched a {player_controlled} fighter{loadout_info}."

        if event_name == 'LaunchSRV':
            srv_event = cast(Dict[str, Any], content)
            srv_type = srv_event.get('SRVType', 'SRV')
            player_controlled = "player-controlled" if srv_event.get('PlayerControlled') else "AI-controlled"
            return f"{self.commander_name} has launched a {player_controlled} {srv_type}."

        if event_name == 'ModuleInfo':
            return f"{self.commander_name} has viewed their module information."

        if event_name == 'Music':
            music_event = cast(Dict[str, Any], content)
            track = music_event.get('MusicTrack', 'unknown track')
            return f"Music has changed to: {track}."

        if event_name == 'NpcCrewPaidWage':
            wage_event = cast(Dict[str, Any], content)
            name = wage_event.get('NpcCrewName', 'An NPC crew member')
            amount = wage_event.get('Amount', 0)
            return f"{self.commander_name} has paid {name} a wage of {amount:,} credits."

        if event_name == 'NpcCrewRank':
            rank_event = cast(Dict[str, Any], content)
            name = rank_event.get('NpcCrewName', 'An NPC crew member')
            rank = rank_event.get('RankCombat', 0)
            return f"{self.commander_name}'s crew member {name} has reached combat rank {rank}."

        if event_name == 'ProspectedAsteroid':
            prospect_event = cast(Dict[str, Any], content)
            content_level = prospect_event.get('Content', 'Unknown')
            remaining = prospect_event.get('Remaining', 100)

            materials_info = ""
            if prospect_event.get('Materials'):
                materials = []
                for material in prospect_event.get('Materials', []):
                    name = material.get('Name_Localised', material.get('Name', 'unknown material'))
                    proportion = material.get('Proportion', 0)
                    materials.append(f"{name} ({proportion:.1f}%)")
                materials_info = f" Contains: {', '.join(materials)}."

            motherlode = ""
            if prospect_event.get('MotherlodeMaterial'):
                motherlode = f" This is a motherlode asteroid with {prospect_event.get('MotherlodeMaterial')}!"

            return f"{self.commander_name} has prospected an asteroid with {content_level} mineral content. {remaining}% remaining.{materials_info}{motherlode}"

        if event_name == 'RebootRepair':
            repair_event = cast(Dict[str, Any], content)
            modules = repair_event.get('Modules', [])
            if modules:
                repaired = ", ".join(modules)
                return f"{self.commander_name} has performed an emergency reboot/repair. Repaired modules: {repaired}."
            else:
                return f"{self.commander_name} has performed an emergency reboot/repair."
                
        if event_name == 'RepairDrone':
            repair_drone_event = cast(Dict[str, Any], content)
            repairs = []
            if repair_drone_event.get('HullRepaired'):
                repairs.append(f"hull: {repair_drone_event.get('HullRepaired')}")
            if repair_drone_event.get('CockpitRepaired'):
                repairs.append(f"cockpit: {repair_drone_event.get('CockpitRepaired')}")
            if repair_drone_event.get('CorrosionRepaired'):
                repairs.append(f"corrosion: {repair_drone_event.get('CorrosionRepaired')}")
                
            if repairs:
                repair_details = ", ".join(repairs)
                return f"{self.commander_name}'s ship has been repaired by a repair drone. Repairs: {repair_details}."
            else:
                return f"{self.commander_name}'s ship has been repaired by a repair drone."
                
        if event_name == 'ReservoirReplenished':
            reservoir_event = cast(Dict[str, Any], content)
            main = reservoir_event.get('FuelMain', 0)
            reservoir = reservoir_event.get('FuelReservoir', 0)
            return f"{self.commander_name} has replenished their fuel reservoir. Main tank: {main:.2f} tons, Reservoir: {reservoir:.2f} tons."
            
        if event_name == 'Resurrect':
            resurrect_event = cast(Dict[str, Any], content)
            option = resurrect_event.get('Option', 'unknown')
            cost = resurrect_event.get('Cost', 0)
            bankrupt = " and declared bankruptcy" if resurrect_event.get('Bankrupt') else ""
            return f"{self.commander_name} has been resurrected (option: {option}) for {cost:,} credits{bankrupt}."
            
        if event_name == 'Scanned':
            scan_event = cast(Dict[str, Any], content)
            scan_type = scan_event.get('ScanType', 'Unknown')
            return f"{self.commander_name}'s ship has been scanned for {scan_type}."
            
        if event_name == 'SelfDestruct':
            return f"{self.commander_name} has initiated self-destruct sequence."
            
        if event_name == 'SendText':
            send_text_event = cast(SendTextEvent, content)
            return f'{self.commander_name} sent a message to {send_text_event.get("To")}: "{send_text_event.get("Message")}"'
            
        if event_name == 'Shutdown':
            return f"{self.commander_name} is shutting down the game."
            
        if event_name == 'Synthesis':
            synthesis_event = cast(Dict[str, Any], content)
            blueprint = synthesis_event.get('Name', 'unknown synthesis')
            
            materials_info = ""
            if synthesis_event.get('Materials'):
                materials = []
                for material in synthesis_event.get('Materials', []):
                    name = material.get('Name_Localised', material.get('Name', 'unknown material'))
                    count = material.get('Count', 0)
                    materials.append(f"{name} ({count})")
                materials_info = f" using {', '.join(materials)}"
            
            return f"{self.commander_name} has synthesized {blueprint}{materials_info}."
            
        if event_name == 'SystemsShutdown':
            return f"{self.commander_name}'s ship systems have shut down unexpectedly."
            
        if event_name == 'USSDrop':
            uss_event = cast(Dict[str, Any], content)
            uss_type = uss_event.get('USSType', 'Unknown')
            threat = uss_event.get('USSThreat', 0)
            
            threat_info = ""
            if threat > 0:
                threat_info = f" (Threat level: {threat})"
                
            return f"{self.commander_name} has dropped into an Unidentified Signal Source: {uss_type}{threat_info}."
            
        if event_name == 'VehicleSwitch':
            vehicle_event = cast(Dict[str, Any], content)
            to_vehicle = vehicle_event.get('To', 'Unknown')
            
            if to_vehicle == 'Mothership':
                return f"{self.commander_name} has switched control back to their main ship."
            elif to_vehicle == 'Fighter':
                return f"{self.commander_name} has switched control to their fighter."
            else:
                return f"{self.commander_name} has switched control to: {to_vehicle}."
                
        if event_name == 'WingAdd':
            wing_add_event = cast(WingAddEvent, content)
            return f"{wing_add_event.get('Name')} has joined {self.commander_name}'s wing."
            
        if event_name == 'WingInvite':
            wing_invite_event = cast(Dict[str, Any], content)
            name = wing_invite_event.get('Name', 'Another commander')
            return f"{self.commander_name} has been invited to join {name}'s wing."
            
        if event_name == 'WingJoin':
            wing_join_event = cast(WingJoinEvent, content)
            return f"{self.commander_name} has joined a wing."
            
        if event_name == 'WingLeave':
            wing_leave_event = cast(WingLeaveEvent, content)
            return f"{self.commander_name} has left their wing."
            
        if event_name == 'CargoTransfer':
            cargo_transfer_event = cast(Dict[str, Any], content)
            transfers = cargo_transfer_event.get('Transfers', [])
            
            if len(transfers) == 0:
                return f"{self.commander_name} has transferred cargo."
                
            if len(transfers) == 1:
                transfer = transfers[0]
                item_type = transfer.get('Type_Localised', transfer.get('Type', 'unknown item'))
                count = transfer.get('Count', 0)
                direction = transfer.get('Direction', '')
                
                if direction == 'tocarrier':
                    return f"{self.commander_name} has transferred {count} units of {item_type} to their fleet carrier."
                elif direction == 'toship':
                    return f"{self.commander_name} has transferred {count} units of {item_type} to their ship."
                elif direction == 'tosrv':
                    return f"{self.commander_name} has transferred {count} units of {item_type} to their SRV."
                elif direction == 'fromcarrier':
                    return f"{self.commander_name} has transferred {count} units of {item_type} from their fleet carrier."
                else:
                    return f"{self.commander_name} has transferred {count} units of {item_type}."
            else:
                to_carrier = any(t.get('Direction') == 'tocarrier' for t in transfers)
                to_ship = any(t.get('Direction') == 'toship' for t in transfers)
                to_srv = any(t.get('Direction') == 'tosrv' for t in transfers)
                
                if to_carrier:
                    return f"{self.commander_name} has transferred multiple cargo items to their fleet carrier."
                elif to_ship:
                    return f"{self.commander_name} has transferred multiple cargo items to their ship."
                elif to_srv:
                    return f"{self.commander_name} has transferred multiple cargo items to their SRV."
                else:
                    return f"{self.commander_name} has transferred multiple cargo items."
                    
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

        if event_name == 'SquadronStartup':
            if content.get('SquadronName'):
                return f"{self.commander_name} is a member of the squadron '{content.get('SquadronName')}' with callsign {content.get('SquadronID', 'Unknown')}."
            else:
                return f"{self.commander_name} is a member of a squadron."

        if event_name == 'EscapeInterdiction':
            escape_event = cast(Dict[str, Any], content)
            interdictor = escape_event.get('Interdictor', 'an unknown ship')
            is_player = escape_event.get('IsPlayer', False)
            is_thargoid = escape_event.get('IsThargoid', False)
            
            if is_thargoid:
                return f"{self.commander_name} has escaped interdiction from a Thargoid."
            elif is_player:
                return f"{self.commander_name} has escaped interdiction from Commander {interdictor}."
            else:
                return f"{self.commander_name} has escaped interdiction from {interdictor}."
            
        if event_name == 'FactionKillBond':
            faction_bond_event = cast(Dict[str, Any], content)
            reward = faction_bond_event.get('Reward', 0)
            awarding_faction = faction_bond_event.get('AwardingFaction', 'a faction')
            victim_faction = faction_bond_event.get('VictimFaction', 'enemy')
            return f"{self.commander_name} has received a {reward:,} credit combat bond for killing a {victim_faction} ship on behalf of {awarding_faction}."
            
        if event_name == 'PVPKill':
            pvp_kill_event = cast(Dict[str, Any], content)
            victim = pvp_kill_event.get('Victim', 'another commander')
            combat_rank = pvp_kill_event.get('CombatRank', -1)
            rank_names = ["Harmless", "Mostly Harmless", "Novice", "Competent", "Expert", "Master", "Dangerous", "Deadly", "Elite"]
            rank_text = f" (Combat Rank: {rank_names[combat_rank]})" if 0 <= combat_rank < len(rank_names) else ""
            return f"{self.commander_name} has defeated Commander {victim}{rank_text} in combat."

        # if event_name == 'Statistics':
        #     return f"{self.commander_name}'s game statistics have been updated."

        if event_name == 'ShipTargeted':
            ship_targeted_event = cast(ShipTargetedEvent, content)
            if ship_targeted_event.get('TargetLocked'):
                if ship_targeted_event.get('Subsystem_Localised'):
                    return f"Weapons now targeting {ship_targeted_event.get('LegalState', '')} pilot {ship_targeted_event.get('PilotName_Localised')}'s {ship_targeted_event.get('Subsystem_Localised')}"
                if ship_targeted_event.get('PilotName_Localised'):
                    return f"Weapons now targeting {ship_targeted_event.get('LegalState', '')} pilot {ship_targeted_event.get('PilotName_Localised')}'s {ship_targeted_event.get('Ship','ship').capitalize()}"
                else:
                    return f"Weapons now targeting the {ship_targeted_event.get('Ship','ship').capitalize()}"
            else:
                return f"Weapons' target lock lost."

        if event_name == 'UnderAttack':
            under_attack_event = cast(UnderAttackEvent, content)
            if under_attack_event.get('Target') == 'You':
                return f"{self.commander_name} is under attack."
            else:
                return f"{self.commander_name}'s {under_attack_event.get('Target')} is under attack."

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
            {"role": "assistant", "tool_calls": event.request}
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

        if active_mode == "Suit":
            status_info.pop('cargo', None)
            status_info.pop('pips', None)

        return active_mode, status_info

    def generate_status_message(self, projected_states: dict[str, dict]):
        status_entries: list[tuple[str, Any]] = []

        active_mode, vehicle_status = self.generate_vehicle_status(projected_states.get('CurrentStatus', {}))
        status_entries.append((active_mode+" status", vehicle_status))

        # Get ship and cargo info
        ship_info: ShipInfoState = projected_states.get('ShipInfo', {})  # pyright: ignore[reportAssignmentType]
        cargo_info: CargoState = projected_states.get('Cargo', {})  # pyright: ignore[reportAssignmentType]
        
        # Create a copy of ship_info so we don't modify the original
        ship_display = dict(ship_info)
        
        # Add cargo inventory in a more efficient format if available

        if cargo_info and cargo_info.get('Inventory'):
            formatted_inventory = []
            for item in cargo_info.get('Inventory', []):
                item_name = item.get('Name', 'Unknown')
                count = item.get('Count', 0)
                stolen = " (Stolen)" if item.get('Stolen', False) else ""
                formatted_inventory.append(f"{count} X {item_name}{stolen}")

            # Add the inventory to the ship display
            ship_display['CargoContents'] = formatted_inventory
        if active_mode == 'SRV':
            # ToDo: Recalculate CargoCapcity when undocking SRV (scarab = 4t; scorpion = 2t)
            ship_display.pop('CargoCapacity', None)

        if active_mode == 'Suit':
            backpack_info = projected_states.get('Backpack', {})
            suit_loadout = projected_states.get('SuitLoadout', {})
            
            # Create a comprehensive suit information display
            suit_display = {}
            backpack_summary = {}
            
            # Add suit details if available
            if suit_loadout:
                # Get basic suit info
                suit_display["Name"] = suit_loadout.get('SuitName_Localised', suit_loadout.get('SuitName', 'Unknown'))
                suit_display["Loadout"] = suit_loadout.get('LoadoutName', 'Unknown')
                
                # Format suit modifications in a readable way
                if suit_loadout.get('SuitMods', []):
                    suit_mods = []
                    for mod in suit_loadout.get('SuitMods', []):
                        # Convert snake_case to Title Case for better readability
                        readable_mod = ' '.join(word.capitalize() for word in mod.split('_'))
                        suit_mods.append(readable_mod)
                    suit_display["Modifications"] = suit_mods
                
                # Format equipped weapons
                if suit_loadout.get('Modules', []):
                    weapons = []
                    for module in suit_loadout.get('Modules', []):
                        weapon_info = {
                            "Name": module.get('ModuleName_Localised', module.get('ModuleName', 'Unknown')),
                            "Class": f"Class {module.get('Class', 0)}",
                            "Slot": module.get('SlotName', 'Unknown')
                        }
                        
                        # Format weapon modifications
                        if module.get('WeaponMods', []):
                            weapon_mods = []
                            for mod in module.get('WeaponMods', []):
                                # Convert snake_case to Title Case for better readability
                                readable_mod = ' '.join(word.capitalize() for word in mod.split('_'))
                                weapon_mods.append(readable_mod)
                            weapon_info["Modifications"] = weapon_mods
                            
                        weapons.append(weapon_info)
                    
                    suit_display["Weapons"] = weapons
            
            # Create a natural language description of backpack contents
            if backpack_info:
                category_display_names = {
                    'Items': 'Equipment',
                    'Components': 'Engineering Components',
                    'Consumables': 'Consumable Items',
                    'Data': 'Data Storage'
                }
                
                # Format all backpack items by category
                for category in ['Items', 'Components', 'Consumables', 'Data']:
                    if category in backpack_info and backpack_info[category]:
                        items_list = []
                        for item in backpack_info[category]:
                            item_name = item.get('Name_Localised', item.get('Name', 'Unknown'))
                            item_count = item.get('Count', 0)
                            items_list.append(f"{item_count}x {item_name}")
                        
                        if items_list:
                            # Use friendlier category names
                            friendly_name = category_display_names.get(category, category)
                            backpack_summary[friendly_name] = items_list
            
            # Add the comprehensive suit information to status entries
            if suit_display or backpack_summary:
                # Create the final display with suit info first, backpack last
                final_suit_display = {}
                
                # Add suit details if available
                if suit_display:
                    for key, value in suit_display.items():
                        final_suit_display[key] = value
                
                # Add backpack contents at the end
                if backpack_summary:
                    final_suit_display["Backpack"] = backpack_summary
                
                status_entries.append(("Suit Information", final_suit_display))
            # If we have no suit display but do have backpack info, fall back to old format
            elif backpack_summary:
                status_entries.append(("Suit Backpack Contents", backpack_summary))

        status_entries.append(("Main Ship", ship_display))

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

        # Add friends status (always include this entry)
        friends_info = projected_states.get('Friends', {})
        online_friends = friends_info.get('Online', [])
        
        
        # Always add the entry, with appropriate message based on online status
        if online_friends:
            status_entries.append(("Friends Status", {
                "Online Count": len(online_friends),
                "Online Friends": online_friends
            }))
        else:
            status_entries.append(("Friends Status", "No friends currently online"))

        # Format and return the final status message
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
                    if len(conversational_pieces) < 20 or is_pending:
                        is_important = is_pending and event.content.get('event') in self.important_game_events
                        conversational_pieces.append(self.full_event_message(event, time_offset, is_important))
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
