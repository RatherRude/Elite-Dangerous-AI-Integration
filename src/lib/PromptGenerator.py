from datetime import timedelta, datetime
from functools import lru_cache
from typing import Any, cast

import yaml
import requests
import humanize

from lib.EventModels import (
    ApproachBodyEvent, ApproachSettlementEvent, BookTaxiEvent, BountyEvent, CommanderEvent, CommitCrimeEvent,
    CrewAssignEvent, CrewLaunchFighterEvent, CrewMemberJoinsEvent, CrewMemberQuitsEvent, CrewMemberRoleChangeEvent,
    DataScannedEvent, DatalinkScanEvent, DiedEvent, DisembarkEvent, DockedEvent, DockFighterEvent,
    DockingDeniedEvent, DockingGrantedEvent, DockingRequestedEvent, DockSRVEvent, EjectCargoEvent, EmbarkEvent,
    EndCrewSessionEvent, FactionKillBondEvent, FighterDestroyedEvent, FighterRebuiltEvent, FriendsEvent,
    FSSAllBodiesFoundEvent, FSSDiscoveryScanEvent, FSDJumpEvent, FSDTargetEvent, HullDamageEvent, InterdictedEvent,
    LaunchDroneEvent, LaunchFighterEvent, LaunchSRVEvent, LeaveBodyEvent, LiftoffEvent, LoadGameEvent,
    MissionAbandonedEvent, MissionAcceptedEvent, MissionCompletedEvent, MissionFailedEvent, MissionRedirectedEvent,
    MiningRefinedEvent, MissionsEvent, NavBeaconScanEvent, OutfittingEvent, PayFinesEvent, PowerplayJoinEvent,
    PromotionEvent, ProspectedAsteroidEvent, ReceiveTextEvent, RebootRepairEvent, RedeemVoucherEvent, ResurrectEvent,
    SAAScanCompleteEvent, ScreenshotEvent, SendTextEvent, ShieldStateEvent, ShipTargetedEvent, ShipyardBuyEvent,
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
            return f"{self.commander_name} is starting a jump to {start_jump_event.get('StarSystem')}"
        if event_name == 'FSDJump':
            fsd_jump_event = cast(FSDJumpEvent, content)
            return f"{self.commander_name} has arrived at {fsd_jump_event.get('StarSystem')}"
        if event_name == 'FSDTarget':
            fsd_target_event = cast(FSDTargetEvent, content)
            return f"{self.commander_name} is targeting the next jump to go to {fsd_target_event.get('Name')}"
        if event_name == 'SupercruiseEntry':
            supercruise_entry_event = cast(SupercruiseEntryEvent, content)
            return f"{self.commander_name} has entered supercruise in the {supercruise_entry_event.get('StarSystem')} system."
        if event_name == 'SupercruiseExit':
            supercruise_exit_event = cast(SupercruiseExitEvent, content)
            return f"{self.commander_name} has exited supercruise near {supercruise_exit_event.get('Body')}."
        if event_name == 'SupercruiseDestinationDrop':
            supercruise_destination_drop_event = cast(SupercruiseDestinationDropEvent, content)
            return f"{self.commander_name} is dropping from supercruise at {supercruise_destination_drop_event.get('Type_Localised', supercruise_destination_drop_event.get('Type'))}."
        
        # Station events
        if event_name == 'Docked':
            docked_event = cast(DockedEvent, content)
            return f"Now docked at {docked_event.get('StationType')} {docked_event.get('StationName')} in {docked_event.get('StarSystem')}"
        if event_name == 'Undocked':
            undocked_event = cast(UndockedEvent, content)
            return f"{self.commander_name} has undocked from {undocked_event.get('StationName')}."
        if event_name == 'DockingDenied':
            docking_denied_event = cast(DockingDeniedEvent, content)
            return f"Docking request denied at {docking_denied_event.get('StationName')}. Reason: {docking_denied_event.get('Reason')}"
        if event_name == 'DockingGranted':
            docking_granted_event = cast(DockingGrantedEvent, content)
            return f"Docking request granted at {docking_granted_event.get('StationName')} on landing pad {docking_granted_event.get('LandingPad')}"
        if event_name == 'DockingRequested':
            docking_requested_event = cast(DockingRequestedEvent, content)
            return f"{self.commander_name} has requested docking at {docking_requested_event.get('StationName')}."
        if event_name == 'DockingTimeout':
            return f"{self.commander_name}'s docking request has timed out."
        if event_name == 'ApproachSettlement':
            approach_settlement_event = cast(ApproachSettlementEvent, content)
            return f"{self.commander_name} is approaching settlement {approach_settlement_event.get('Name_Localised', approach_settlement_event.get('Name'))} on {approach_settlement_event.get('BodyName')}"
        
        # Shipyard and Outfitting events
        if event_name == 'Shipyard':
            return f"{self.commander_name} is accessing the station's shipyard."
        if event_name == 'Market':
            return f"{self.commander_name} is accessing the station's market."
        if event_name == 'Outfitting':
            outfitting_event = cast(OutfittingEvent, content)
            return f"{self.commander_name} is accessing outfitting services at {outfitting_event.get('StationName')}."
        if event_name == 'ShipyardBuy':
            shipyard_buy_event = cast(ShipyardBuyEvent, content)
            return f"{self.commander_name} has purchased a {shipyard_buy_event.get('ShipType_Localised', shipyard_buy_event.get('ShipType'))} for {shipyard_buy_event.get('ShipPrice')} credits."
        if event_name == 'ShipyardSell':
            shipyard_sell_event = cast(ShipyardSellEvent, content)
            return f"{self.commander_name} has sold a {shipyard_sell_event.get('ShipType_Localised', shipyard_sell_event.get('ShipType'))} for {shipyard_sell_event.get('ShipPrice')} credits."
        if event_name == 'ShipyardTransfer':
            shipyard_transfer_event = cast(ShipyardTransferEvent, content)
            return f"{self.commander_name} has requested a transfer of their {shipyard_transfer_event.get('ShipType_Localised', shipyard_transfer_event.get('ShipType'))} from {shipyard_transfer_event.get('System')}. Transfer time: {shipyard_transfer_event.get('TransferTime')} seconds."
        if event_name == 'ShipyardSwap':
            shipyard_swap_event = cast(ShipyardSwapEvent, content)
            return f"{self.commander_name} has swapped to a {shipyard_swap_event.get('ShipType_Localised', shipyard_swap_event.get('ShipType'))}."
        if event_name == 'ClearImpound':
            return f"{self.commander_name} has cleared an impounded asset."
        
        # Combat events
        if event_name == 'ShipTargeted':
            ship_targeted_event = cast(ShipTargetedEvent, content)
            if ship_targeted_event.get('TargetLocked'):
                if ship_targeted_event.get('ScanStage') == 3:  # Full scan completed
                    details = []
                    if ship_targeted_event.get('PilotName_Localised', ship_targeted_event.get('PilotName')):
                        details.append(f"pilot {ship_targeted_event.get('PilotName_Localised', ship_targeted_event.get('PilotName'))}")
                    if ship_targeted_event.get('PilotRank'):
                        details.append(f"rank {ship_targeted_event.get('PilotRank')}")
                    if ship_targeted_event.get('LegalStatus'):
                        details.append(f"status {ship_targeted_event.get('LegalStatus')}")
                    if ship_targeted_event.get('Faction'):
                        details.append(f"faction {ship_targeted_event.get('Faction')}")
                    if ship_targeted_event.get('Bounty'):
                        details.append(f"bounty {ship_targeted_event.get('Bounty')} credits")
                    
                    details_str = ", ".join(details)
                    
                    if ship_targeted_event.get('Subsystem_Localised'):
                        return f"Weapons locked on {ship_targeted_event.get('Ship_Localised', ship_targeted_event.get('Ship', 'ship')).capitalize()}'s {ship_targeted_event.get('Subsystem_Localised')}. Target details: {details_str}."
                    else:
                        return f"Weapons locked on {ship_targeted_event.get('Ship_Localised', ship_targeted_event.get('Ship', 'ship')).capitalize()}. Target details: {details_str}."
                else:
                    if ship_targeted_event.get('Subsystem_Localised'):
                        return f"Weapons targeting {ship_targeted_event.get('Ship_Localised', ship_targeted_event.get('Ship', 'ship')).capitalize()}'s {ship_targeted_event.get('Subsystem_Localised')}. Scan in progress."
                    else:
                        return f"Weapons targeting {ship_targeted_event.get('Ship_Localised', ship_targeted_event.get('Ship', 'ship')).capitalize()}. Scan in progress."
            else:
                return f"Target lock lost."
                
        if event_name == 'UnderAttack':
            under_attack_event = cast(UnderAttackEvent, content)
            if under_attack_event.get('Target') == 'You':
                if under_attack_event.get('Faction'):
                    return f"{self.commander_name} is under attack by {under_attack_event.get('Faction')}!"
                else:
                    return f"{self.commander_name} is under attack!"
            else:
                return f"{self.commander_name}'s {under_attack_event.get('Target')} is under attack."
                
        if event_name == 'Died':
            died_event = cast(DiedEvent, content)
            if died_event.get('KillerName') and died_event.get('KillerShip'):
                return f"{self.commander_name} was killed by {died_event.get('KillerName')} in a {died_event.get('KillerShip')}. Rebuy cost: {died_event.get('Insurance', 0):,} credits."
            elif died_event.get('Killers'):
                killers = [f"{killer.get('Name')} in a {killer.get('Ship')}" for killer in died_event.get('Killers', [])]
                return f"{self.commander_name} was killed by multiple attackers: {', '.join(killers)}. Rebuy cost: {died_event.get('Insurance', 0):,} credits."
            else:
                return f"{self.commander_name} has died. Rebuy cost: {died_event.get('Insurance', 0):,} credits."
                
        if event_name == 'Resurrect':
            resurrect_event = cast(ResurrectEvent, content)
            return f"{self.commander_name} has been resurrected with option: {resurrect_event.get('Option')}. Cost: {resurrect_event.get('Cost'):,} credits."
            
        if event_name == 'HeatDamage':
            return f"WARNING: {self.commander_name}'s ship is taking heat damage!"
            
        if event_name == 'HeatWarning':
            return f"CRITICAL WARNING: {self.commander_name}'s ship is overheating and sustaining damage!"
            
        if event_name == 'ShieldState':
            shield_state_event = cast(ShieldStateEvent, content)
            if shield_state_event.get('ShieldsUp'):
                return f"{self.commander_name}'s shields have been restored."
            else:
                return f"{self.commander_name}'s shields have collapsed!"
                
        if event_name == 'HullDamage':
            hull_damage_event = cast(HullDamageEvent, content)
            return f"WARNING: {self.commander_name}'s hull integrity is at {hull_damage_event.get('Health') * 100:.1f}%!"
            
        if event_name == 'SystemsShutdown':
            return f"EMERGENCY: {self.commander_name}'s ship systems are shutting down!"
            
        if event_name == 'CockpitBreached':
            return f"CRITICAL EMERGENCY: {self.commander_name}'s cockpit has been breached! Oxygen depleting rapidly!"
            
        if event_name == 'CommitCrime':
            commit_crime_event = cast(CommitCrimeEvent, content)
            if commit_crime_event.get('Fine'):
                return f"{self.commander_name} committed crime: {commit_crime_event.get('CrimeType')} against {commit_crime_event.get('Faction')}. Fine issued: {commit_crime_event.get('Fine'):,} credits."
            elif commit_crime_event.get('Bounty'):
                return f"{self.commander_name} committed crime: {commit_crime_event.get('CrimeType')} against {commit_crime_event.get('Faction')}. Bounty issued: {commit_crime_event.get('Bounty'):,} credits."
            else:
                return f"{self.commander_name} committed crime: {commit_crime_event.get('CrimeType')} against {commit_crime_event.get('Faction')}."
                
        if event_name == 'Interdiction':
            return f"{self.commander_name} has initiated an interdiction attempt."
            
        if event_name == 'Interdicted':
            interdicted_event = cast(InterdictedEvent, content)
            if interdicted_event.get('IsPlayer'):
                submit_status = "submitted to" if interdicted_event.get('Submitted') else "is fighting"
                return f"{self.commander_name} has been interdicted by CMDR {interdicted_event.get('Interdictor')} and {submit_status} the interdiction."
            else:
                submit_status = "submitted to" if interdicted_event.get('Submitted') else "is fighting"
                faction = f" ({interdicted_event.get('Faction')})" if interdicted_event.get('Faction') else ""
                return f"{self.commander_name} has been interdicted by {interdicted_event.get('Interdictor')}{faction} and {submit_status} the interdiction."
                
        if event_name == 'EscapeInterdiction':
            return f"{self.commander_name} has successfully escaped an interdiction attempt!"
            
        if event_name == 'Bounty':
            bounty_event = cast(BountyEvent, content)
            if bounty_event.get('Target'):
                faction = f" from {bounty_event.get('VictimFaction')}" if bounty_event.get('VictimFaction') else ""
                shared = " (shared)" if bounty_event.get('SharedWithOthers') else ""
                return f"{self.commander_name} has earned a bounty of {bounty_event.get('TotalReward'):,} credits{shared} for eliminating {bounty_event.get('Target_Localised', bounty_event.get('Target'))}{faction}."
            else:
                return f"{self.commander_name} has earned a bounty of {bounty_event.get('TotalReward'):,} credits."
                
        if event_name == 'CapShipBond':
            return f"{self.commander_name} has earned a capital ship combat bond worth {content.get('Reward'):,} credits from {content.get('AwardingFaction')}."
            
        if event_name == 'FactionKillBond':
            faction_kill_bond_event = cast(FactionKillBondEvent, content)
            return f"{self.commander_name} has earned a combat bond of {faction_kill_bond_event.get('Reward'):,} credits from {faction_kill_bond_event.get('AwardingFaction_Localised', faction_kill_bond_event.get('AwardingFaction'))} for eliminating a {faction_kill_bond_event.get('VictimFaction_Localised', faction_kill_bond_event.get('VictimFaction'))} target."
            
        if event_name == 'FighterDestroyed':
            fighter_destroyed_event = cast(FighterDestroyedEvent, content)
            if fighter_destroyed_event.get('ID'):
                return f"{self.commander_name}'s fighter {fighter_destroyed_event.get('ID')} has been destroyed in combat."
            else:
                return f"{self.commander_name}'s fighter has been destroyed in combat."
                
        if event_name == 'PVPKill':
            return f"{self.commander_name} has defeated CMDR {content.get('Victim')} in combat."
            
        if event_name == 'CrimeVictim':
            return f"{self.commander_name} has been the victim of a {content.get('CrimeType')} committed by {content.get('Offender')}."
            
        if event_name == 'SelfDestruct':
            return f"{self.commander_name} has initiated self-destruct sequence. Ship lost."
            
        if event_name == 'InDanger':
            return f"WARNING: {self.commander_name} is in danger!"
            
        if event_name == 'OutofDanger':
            return f"{self.commander_name} is no longer in danger."
            
        if event_name == 'LegalStateChanged':
            return f"{self.commander_name}'s legal status has changed to {content.get('LegalState')}."
        
        # Mining events
        if event_name == 'ProspectedAsteroid':
            prospected_asteroid_event = cast(ProspectedAsteroidEvent, content)
            return f"{self.commander_name} has prospected an asteroid containing {prospected_asteroid_event.get('Content_Localised', prospected_asteroid_event.get('Content'))}. Remaining: {prospected_asteroid_event.get('Remaining') * 100:.1f}%."
        if event_name == 'MiningRefined':
            mining_refined_event = cast(MiningRefinedEvent, content)
            return f"{self.commander_name} has refined 1 ton of {mining_refined_event.get('Type_Localised', mining_refined_event.get('Type'))}."
        if event_name == 'LaunchDrone':
            launch_drone_event = cast(LaunchDroneEvent, content)
            return f"{self.commander_name} has launched a {launch_drone_event.get('Type')} drone."
        if event_name == 'EjectCargo':
            eject_cargo_event = cast(EjectCargoEvent, content)
            abandoned = "abandoned" if eject_cargo_event.get('Abandoned') else "ejected"
            return f"{self.commander_name} has {abandoned} {eject_cargo_event.get('Count')} units of {eject_cargo_event.get('Type_Localised', eject_cargo_event.get('Type'))}."
        
        # SRV events
        if event_name == 'LaunchSRV':
            launch_srv_event = cast(LaunchSRVEvent, content)
            return f"{self.commander_name} has deployed their {launch_srv_event.get('SRVType_Localised', launch_srv_event.get('SRVType'))}."
        if event_name == 'DockSRV':
            dock_srv_event = cast(DockSRVEvent, content)
            return f"{self.commander_name} has recalled their {dock_srv_event.get('SRVType_Localised', dock_srv_event.get('SRVType'))}."
        if event_name == 'SRVDestroyed':
            srv_destroyed_event = cast(SRVDestroyedEvent, content)
            return f"{self.commander_name}'s {srv_destroyed_event.get('SRVType_Localised', srv_destroyed_event.get('SRVType'))} has been destroyed."
            
        # Fighter events
        if event_name == 'LaunchFighter':
            launch_fighter_event = cast(LaunchFighterEvent, content)
            return f"{self.commander_name} has launched a fighter with loadout {launch_fighter_event.get('Loadout')}."
        if event_name == 'DockFighter':
            dock_fighter_event = cast(DockFighterEvent, content)
            return f"{self.commander_name} has recalled their fighter."
        if event_name == 'FighterRebuilt':
            fighter_rebuilt_event = cast(FighterRebuiltEvent, content)
            return f"{self.commander_name}'s fighter has been rebuilt with loadout {fighter_rebuilt_event.get('Loadout')}."
        if event_name == 'CrewLaunchFighter':
            crew_launch_fighter_event = cast(CrewLaunchFighterEvent, content)
            return f"{self.commander_name}'s crew member {crew_launch_fighter_event.get('Crew')} has launched a fighter."
        
        # Ship status events
        if event_name == 'LowFuelWarning':
            return f"WARNING: {self.commander_name}'s ship is running low on fuel!"
        if event_name == 'LowFuelWarningCleared':
            return f"{self.commander_name}'s low fuel warning has been cleared."
        if event_name == 'RebootRepair':
            reboot_repair_event = cast(RebootRepairEvent, content)
            if reboot_repair_event.get('Modules'):
                modules = ", ".join(reboot_repair_event.get('Modules'))
                return f"{self.commander_name} has initiated a reboot/repair sequence. Repaired modules: {modules}."
            else:
                return f"{self.commander_name} has initiated a reboot/repair sequence."
        
        # On-foot events
        if event_name == 'Disembark':
            disembark_event = cast(DisembarkEvent, content)
            if disembark_event.get('OnStation'):
                return f"{self.commander_name} has disembarked at {disembark_event.get('StationName')}."
            else:
                return f"{self.commander_name} has disembarked on {disembark_event.get('Body')}."
        if event_name == 'Embark':
            embark_event = cast(EmbarkEvent, content)
            if embark_event.get('SRV'):
                return f"{self.commander_name} has boarded their SRV."
            elif embark_event.get('OnStation'):
                return f"{self.commander_name} has boarded their ship at {embark_event.get('StationName')}."
            else:
                return f"{self.commander_name} has boarded their ship on {embark_event.get('Body')}."
        if event_name == 'BookTaxi':
            book_taxi_event = cast(BookTaxiEvent, content)
            return f"{self.commander_name} has booked a taxi to {book_taxi_event.get('DestinationSystem')} - {book_taxi_event.get('DestinationLocation')} for {book_taxi_event.get('Cost')} credits."
        if event_name == 'CancelTaxi':
            return f"{self.commander_name} has cancelled their taxi booking."
        if event_name == 'BookDropship':
            return f"{self.commander_name} has booked a dropship."
        if event_name == 'CancelDropship':
            return f"{self.commander_name} has cancelled their dropship booking."
        if event_name == 'BuySuit':
            return f"{self.commander_name} has purchased a new suit."
        if event_name == 'BuyWeapon':
            return f"{self.commander_name} has purchased a new weapon."
        if event_name == 'SuitLoadout':
            suit_loadout_event = cast(SuitLoadoutEvent, content)
            return f"{self.commander_name} has equipped the {suit_loadout_event.get('SuitName_Localised', suit_loadout_event.get('SuitName'))} suit with loadout: {suit_loadout_event.get('LoadoutName')}."
        if event_name == 'SwitchSuitLoadout':
            switch_suit_loadout_event = cast(SwitchSuitLoadoutEvent, content)
            return f"{self.commander_name} has switched to the {switch_suit_loadout_event.get('SuitName_Localised', switch_suit_loadout_event.get('SuitName'))} suit with loadout: {switch_suit_loadout_event.get('LoadoutName')}."
        if event_name == 'CreateSuitLoadout':
            return f"{self.commander_name} has created a new suit loadout."
        if event_name == 'RenameSuitLoadout':
            return f"{self.commander_name} has renamed a suit loadout."
        if event_name == 'UseConsumable':
            use_consumable_event = cast(UseConsumableEvent, content)
            return f"{self.commander_name} has used a {use_consumable_event.get('Name_Localised', use_consumable_event.get('Name'))}."
        if event_name == 'SellOrganicData':
            return f"{self.commander_name} has sold organic scan data."
        if event_name == 'LowOxygenWarning':
            return f"WARNING: {self.commander_name} is running low on oxygen!"
        if event_name == 'LowOxygenWarningCleared':
            return f"{self.commander_name}'s low oxygen warning has been cleared."
        if event_name == 'LowHealthWarning':
            return f"WARNING: {self.commander_name}'s health is critically low!"
        if event_name == 'LowHealthWarningCleared':
            return f"{self.commander_name}'s low health warning has been cleared."
        
        # Planetary events
        if event_name == 'ApproachBody':
            approach_body_event = cast(ApproachBodyEvent, content)
            return f"{self.commander_name} is approaching {approach_body_event.get('Body')}."
        if event_name == 'LeaveBody':
            leave_body_event = cast(LeaveBodyEvent, content)
            return f"{self.commander_name} is leaving the vicinity of {leave_body_event.get('Body')}."
        if event_name == 'Touchdown':
            touchdown_event = cast(TouchdownEvent, content)
            if touchdown_event.get('PlayerControlled'):
                return f"{self.commander_name} has landed on {touchdown_event.get('Body')} at coordinates {touchdown_event.get('Latitude'):.4f}, {touchdown_event.get('Longitude'):.4f}."
            else:
                return f"{self.commander_name}'s ship has auto-landed on {touchdown_event.get('Body')}."
        if event_name == 'Liftoff':
            liftoff_event = cast(LiftoffEvent, content)
            if liftoff_event.get('PlayerControlled'):
                return f"{self.commander_name} has lifted off from {liftoff_event.get('Body')}."
            else:
                return f"{self.commander_name}'s ship has auto-lifted off from {liftoff_event.get('Body')}."
        
        # Exploration and scanning events
        if event_name == 'Screenshot':
            screenshot_event = cast(ScreenshotEvent, content)
            return f"{self.commander_name} took a screenshot of {screenshot_event.get('Body')} in the {screenshot_event.get('System')} system."
        if event_name == 'NavBeaconScan':
            nav_beacon_scan_event = cast(NavBeaconScanEvent, content)
            return f"{self.commander_name} has scanned the nav beacon, revealing {nav_beacon_scan_event.get('NumBodies')} bodies in the system."
        if event_name == 'SAAScanComplete':
            saa_scan_complete_event = cast(SAAScanCompleteEvent, content)
            return f"{self.commander_name} has completed surface mapping of {saa_scan_complete_event.get('BodyName')} using {saa_scan_complete_event.get('ProbesUsed')} probes."
        if event_name == 'FSSAllBodiesFound':
            fss_all_bodies_found_event = cast(FSSAllBodiesFoundEvent, content)
            return f"{self.commander_name} has discovered all {fss_all_bodies_found_event.get('Count')} bodies in the {fss_all_bodies_found_event.get('SystemName')} system."
        if event_name == 'FSSDiscoveryScan':
            fss_discovery_scan_event = cast(FSSDiscoveryScanEvent, content)
            return f"{self.commander_name} has performed a discovery scan in {fss_discovery_scan_event.get('SystemName')}. Progress: {fss_discovery_scan_event.get('Progress') * 100:.1f}%. Bodies detected: {fss_discovery_scan_event.get('BodyCount')}."
        if event_name == 'DataScanned':
            data_scanned_event = cast(DataScannedEvent, content)
            return f"{self.commander_name} has scanned a {data_scanned_event.get('Type_Localised', data_scanned_event.get('Type'))}."
        if event_name == 'DatalinkScan':
            datalink_scan_event = cast(DatalinkScanEvent, content)
            return f"{self.commander_name} has completed a datalink scan: {datalink_scan_event.get('Message_Localised', datalink_scan_event.get('Message'))}"
        
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
