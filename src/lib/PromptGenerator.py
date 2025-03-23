from datetime import timedelta, datetime
from functools import lru_cache
from typing import Any, cast

import yaml
import requests
import humanize

from lib.EventModels import DockedEvent, FSDJumpEvent, FSDTargetEvent, OutfittingEvent, ReceiveTextEvent, ShipTargetedEvent, StartJumpEvent, UnderAttackEvent

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


class PromptGenerator:
    def __init__(self, commander_name: str, character_prompt: str, important_game_events: list[str]):
        self.commander_name = commander_name
        self.character_prompt = character_prompt
        self.important_game_events = important_game_events

    # def time_since(self, timestamp):
    #     # Current time
    #     now = datetime.now()
    #
    #     # Time difference
    #     time_diff = now - timestamp
    #
    #     # Get the days, hours, and minutes
    #     days = time_diff.days
    #     hours = time_diff.seconds // 3600
    #     minutes = (time_diff.seconds % 3600) // 60
    #
    #     return days, hours, minutes
    def get_event_template(self, event: GameEvent):
        content: Any = event.content
        event_name = content.get('event')
        
        if event_name == 'ReceiveText':
            receive_text_event = cast(ReceiveTextEvent, content)
            return f'Message received from {receive_text_event.get('From_Localised',receive_text_event.get('From'))} on channel {receive_text_event.get('Channel')}: "{receive_text_event.get('Message_Localised', receive_text_event.get('Message'))}"'
        if event_name == 'StartJump':
            start_jump_event = cast(StartJumpEvent, content)
            return f"{self.commander_name} is starting a jump to {start_jump_event.get('StarSystem')}"
        if event_name == 'FSDJump':
            fsd_jump_event = cast(FSDJumpEvent, content)
            return f"{self.commander_name} is arriving at {fsd_jump_event.get('StarSystem')}"
        if event_name == 'FSDTarget':  # TODO is scoopable and should scoop?
            fsd_target_event = cast(FSDTargetEvent, content)
            return f"{self.commander_name} is targeting the next jump to go to {fsd_target_event.get('Name')}"
        if event_name == 'Docked':
            docked_event = cast(DockedEvent, content)
            return f"Now docked at {docked_event.get('StationType')} {docked_event.get('StationName')}"
        
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
            
        if event_name == 'Shipyard':
            return f"{self.commander_name} is accessing the stations shipyard."
        if event_name == 'Market':
            return f"{self.commander_name} is accessing the stations market."
        if event_name == 'Outfitting':
            return f"{self.commander_name} is accessing the stations outfitting."


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
            "content": f"({externalEvents[event.content.get('event')]} {event.content.get('text')})",
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
            ship_display.pop('CargoCapacity', None)

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
