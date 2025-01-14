from datetime import timedelta, datetime
import json
from functools import lru_cache
import traceback

import requests

from .Projections import LocationState, MissionsState, ShipInfoState

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

startupEvents = {
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
    #"SquadronStartup": "Commander {commanderName} is a member of a squadron.",
}
powerplayEvents = {
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
squadronEvents = {
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
}
tradeEvents = {
    "Trade": "Commander {commanderName} has performed a trade.",
    "AsteroidCracked": "Commander {commanderName} has cracked an asteroid.",
    "BuyTradeData": "Commander {commanderName} has bought trade data.",
    "CollectCargo": "Commander {commanderName} has collected cargo.",
    "EjectCargo": "Commander {commanderName} has ejected cargo.",
    "MarketBuy": "Commander {commanderName} has bought market goods.",
    "MarketSell": "Commander {commanderName} has sold market goods.",
    "MiningRefined": "Commander {commanderName} has refined a resource.",
}
stationServiceEvents = {
    "StationServices": "Commander {commanderName} has accessed station services.",
    "BuyAmmo": "Commander {commanderName} has bought ammunition.",
    "BuyDrones": "Commander {commanderName} has bought drones.",
    "CargoDepot": "Commander {commanderName} has completed a cargo depot operation.",
    "ClearImpound": "Commander {commanderName} has cleared an impound.",
    "CommunityGoal": "Commander {commanderName} has engaged in a community goal.",
    "CommunityGoalDiscard": "Commander {commanderName} has discarded a community goal.",
    "CommunityGoalJoin": "Commander {commanderName} has joined a community goal.",
    "CommunityGoalReward": "Commander {commanderName} has received a reward for a community goal.",
    "CrewAssign": "Commander {commanderName} has assigned a crew member.",
    "CrewFire": "Commander {commanderName} has fired a crew member.",
    "CrewHire": "Commander {commanderName} has hired a crew member.",
    "EngineerContribution": "Commander {commanderName} has made a contribution to an engineer.",
    "EngineerCraft": "Commander {commanderName} has crafted a blueprint at an engineer.",
    "EngineerLegacyConvert": "Commander {commanderName} has converted a legacy blueprint at an engineer.",
    "EngineerProgress": "Commander {commanderName} has progressed with an engineer.",
    "FetchRemoteModule": "Commander {commanderName} has fetched a remote module.",
    "Market": "Commander {commanderName} has interacted with a market.",
    "MassModuleStore": "Commander {commanderName} has mass stored modules.",
    "MaterialTrade": "Commander {commanderName} has conducted a material trade.",
    "MissionAbandoned": "Commander {commanderName} has abandoned a mission.",
    "MissionAccepted": "Commander {commanderName} has accepted a mission.",
    "MissionCompleted": "Commander {commanderName} has completed a mission.",
    "MissionFailed": "Commander {commanderName} has failed a mission.",
    "MissionRedirected": "Commander {commanderName}'s mission is now completed. Rewards are now available.",
    "ModuleBuy": "Commander {commanderName} has bought a module.",
    "ModuleRetrieve": "Commander {commanderName} has retrieved a module.",
    "ModuleSell": "Commander {commanderName} has sold a module.",
    "ModuleSellRemote": "Commander {commanderName} has sold a remote module.",
    "ModuleStore": "Commander {commanderName} has stored a module.",
    "ModuleSwap": "Commander {commanderName} has swapped modules.",
    "Outfitting": "Commander {commanderName} has visited an outfitting station.",
    "PayBounties": "Commander {commanderName} has paid bounties.",
    "PayFines": "Commander {commanderName} has paid fines.",
    "PayLegacyFines": "Commander {commanderName} has paid legacy fines.",
    "RedeemVoucher": "Commander {commanderName} has redeemed a voucher.",
    "RefuelAll": "Commander {commanderName} has refueled all.",
    "RefuelPartial": "Commander {commanderName} has partially refueled.",
    "Repair": "Commander {commanderName} has repaired.",
    "RepairAll": "Commander {commanderName} has repaired all.",
    "RestockVehicle": "Commander {commanderName} has restocked vehicle.",
    "ScientificResearch": "Commander {commanderName} has conducted scientific research.",
    "Shipyard": "Commander {commanderName} has visited a shipyard.",
    # "ShipyardNew": "Commander {commanderName} has acquired a new ship.",
    "ShipyardSell": "Commander {commanderName} has sold a ship.",
    "ShipyardSwap": "Commander {commanderName} has swapped ships.",
    "ShipyardTransfer": "Commander {commanderName} has transfersd a ship.",
    "ShipyardBuy": "Commander {commanderName} has bought a ship.",
    # "StoredShips": "Commander {commanderName} has stored ships.",
    # "StoredModules": "Commander {commanderName} has stored modules.",
    "TechnologyBroker": "Commander {commanderName} has accessed a technology broker.",
}
carrierEvents = {
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
odysseyEvents = {
    # 'Backpack': "Commander {commanderName} has interacted with their backpack.",
    'BackpackChange': "Commander {commanderName} has changed items in their backpack.",
    'BookDropship': "Commander {commanderName} has booked a dropship.",
    'BookTaxi': "Commander {commanderName} has booked a taxi.",
    'BuyMicroResources': "Commander {commanderName} has bought micro resources.",
    'BuySuit': "Commander {commanderName} has bought a suit.",
    'BuyWeapon': "Commander {commanderName} has bought a weapon.",
    'CancelDropship': "Commander {commanderName} has cancelled a dropship booking.",
    'CancelTaxi': "Commander {commanderName} has cancelled a taxi booking.",
    # 'CollectItems': "Commander {commanderName} has collected items.",
    'CreateSuitLoadout': "Commander {commanderName} has created a suit loadout.",
    'DeleteSuitLoadout': "Commander {commanderName} has deleted a suit loadout.",
    'Disembark': "Commander {commanderName} has disembarked.",
    'DropItems': "Commander {commanderName} has dropped items.",
    'DropShipDeploy': "Commander {commanderName} has deployed their dropship.",
    'Embark': "Commander {commanderName} has embarked.",
    'FCMaterials': "Commander {commanderName} has managed fleet carrier materials.",
    'LoadoutEquipModule': "Commander {commanderName} has equipped a module in suit loadout.",
    'LoadoutRemoveModule': "Commander {commanderName} has removed a module from suit loadout.",
    'RenameSuitLoadout': "Commander {commanderName} has renamed a suit loadout.",
    # 'ScanOrganic': "Commander {commanderName} has scanned organic life.",
    'SellMicroResources': "Commander {commanderName} has sold micro resources.",
    'SellOrganicData': "Commander {commanderName} has sold organic data.",
    'SellWeapon': "Commander {commanderName} has sold a weapon.",
    # 'ShipLocker': "Commander {commanderName} has accessed ship locker.",
    'SwitchSuitLoadout': "Commander {commanderName} has switched to suit loadout.",
    'TransferMicroResources': "Commander {commanderName} has transferred micro resources.",
    'TradeMicroResources': "Commander {commanderName} has traded micro resources.",
    'UpgradeSuit': "Commander {commanderName} has upgraded a suit.",
    'UpgradeWeapon': "Commander {commanderName} has upgraded a weapon.",
    'UseConsumable': "Commander {commanderName} has used a consumable."
}
combatEvents = {
    "Bounty": "Commander {commanderName} has eliminated a hostile.",
    "Died": "Commander {commanderName} has lost consciousness.",
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
    "SRVDestroyed": "Commander {commanderName}'s SRV was destroyed.",
    "UnderAttack": "Commander {commanderName} is under attack.",
}
travelEvents = {
    "ApproachBody": "Commander {commanderName} is entering an orbit.",
    "Docked": "Commander {commanderName} has docked with a station.",
    "DockingCanceled": "Commander {commanderName} has canceled the docking request.",
    # "DockingComplete": "Commander {commanderName} has docked with a station",
    "DockingDenied": "Commander {commanderName}'s request to dock with a station has been denied.",
    "DockingGranted": "Commander {commanderName}'s request to dock with a station has been granted.",
    "DockingRequested": "Commander {commanderName} has sent a request to dock with a station.",
    "DockingTimeout": "Commander {commanderName}'s request to dock with a station has timed out.",
    "FSDJump": "Commander {commanderName} has initiated a hyperjump to another system.",
    "FSDTarget": "Commander {commanderName} has selected a star system to jump to.",
    "LeaveBody": "Commander {commanderName} is exiting an orbit.",
    "Liftoff": "Commander {commanderName}'s ship has lifted off.",
    "Location": "Commander {commanderName} has changed location.",
    "StartJump": "Commander {commanderName} starts the hyperjump.",
    "SupercruiseEntry": "Commander {commanderName} has entered supercruise from normal space.",
    "SupercruiseExit": "Commander {commanderName} has exited supercruise and returned to normal space.",
    "Touchdown": "Commander {commanderName}'s ship has touched down on a planet surface.",
    "Undocked": "Commander {commanderName} has undocked from a station.",
    "NavRoute": "Commander {commanderName} has planned a new nav route.",
    "NavRouteClear": "Commander {commanderName} has cleared the nav route.",
}
otherEvents = {
    "AfmuRepairs": "Commander {commanderName} has conducted repairs.",
    "ApproachSettlement": "Commander {commanderName} is approaching settlement.",
    "ChangeCrewRole": "Commander {commanderName} has changed crew role.",
    "CockpitBreached": "Commander {commanderName} has experienced a cockpit breach.",
    "CommitCrime": "Commander {commanderName} has committed a crime.",
    "Continued": "Commander {commanderName} has continued.",
    "CrewLaunchFighter": "Commander {commanderName} has launched a fighter.",
    "CrewMemberJoins": "Commander {commanderName} has a new crew member.",
    "CrewMemberQuits": "Commander {commanderName} has lost a crew member.",
    "CrewMemberRoleChange": "Commander {commanderName} has changed a crew member's role.",
    "CrimeVictim": "Commander {commanderName} has been victimized.",
    "DatalinkScan": "Commander {commanderName} has scanned a datalink.",
    "DatalinkVoucher": "Commander {commanderName} has received a datalink voucher.",
    "DataScanned": "Commander {commanderName} has scanned data.",
    "DockFighter": "Commander {commanderName} has docked a fighter.",
    "DockSRV": "Commander {commanderName} has docked an SRV.",
    "EndCrewSession": "Commander {commanderName} has ended a crew session.",
    "FighterRebuilt": "Commander {commanderName} has rebuilt a fighter.",
    "FuelScoop": "Commander {commanderName} has scooped fuel.",
    "Friends": "The status of a friend of Commander {commanderName} has changed.",
    # "Music": "Commander {commanderName} has triggered music playback.",
    "JetConeBoost": "Commander {commanderName} has executed a jet cone boost.",
    "JetConeDamage": "Commander {commanderName} has received damage from a jet cone.",
    "JoinACrew": "Commander {commanderName} has joined a crew.",
    "KickCrewMember": "Commander {commanderName} has kicked a crew member.",
    "LaunchDrone": "Commander {commanderName} has launched a drone.",
    "LaunchFighter": "Commander {commanderName} has launched a fighter.",
    "LaunchSRV": "Commander {commanderName} has launched an SRV.",
    # "ModuleInfo": "Commander {commanderName} has received module info.",
    "NpcCrewPaidWage": "Commander {commanderName} has paid an NPC crew member.",
    "NpcCrewRank": "Commander {commanderName} has received NPC crew rank update.",
    "Promotion": "Commander {commanderName} has received a promotion.",
    # "ProspectedAsteroid": "Commander {commanderName} has prospected an asteroid. Only inform about the most interesting material.",
    "ProspectedAsteroid": "Commander {commanderName} has prospected an asteroid. Only inform about the most interesting material.",
    "QuitACrew": "Commander {commanderName} has quit a crew.",
    "RebootRepair": "Commander {commanderName} has initiated a reboot/repair.",
    "ReceiveText": "Commander {commanderName} has received a text message.",
    "RepairDrone": "Commander {commanderName} has repaired using a drone.",
    "ReservoirReplenished": "Commander {commanderName} has replenished reservoir.",
    "Resurrect": "Commander {commanderName} has resurrected.",
    "Scanned": "Commander {commanderName} has been scanned.",
    "SelfDestruct": "Commander {commanderName} has initiated self destruct.",
    "SendText": "Commander {commanderName} has sent a text message.",
    "Shutdown": "Commander {commanderName} has initiated a shutdown.",
    "Synthesis": "Commander {commanderName} has performed synthesis.",
    "SystemsShutdown": "Commander {commanderName}'s systems have been shut down forcefully.",
    "USSDrop": "Commander {commanderName} has encountered a USS drop.",
    "VehicleSwitch": "Commander {commanderName} has switched vehicle.",
    "WingAdd": "Commander {commanderName} has added to a wing.",
    "WingInvite": "Commander {commanderName} has received a wing invite.",
    "WingJoin": "Commander {commanderName} has joined a wing.",
    "WingLeave": "Commander {commanderName} has left a wing.",
    "CargoTransfer": "Commander {commanderName} has transferred cargo.",
    "SupercruiseDestinationDrop": "Commander {commanderName} has dropped out at a supercruise destination.",
}

projectedEvents = {
    'ScanOrganicTooClose': "Commander {commanderName} is now too close to take another sample. Distance must be increased.",
    'ScanOrganicFarEnough': "Commander {commanderName} is now far enough away to take another sample.",
    'ScanOrganicFirst': "Commander {commanderName} took the first of three biological samples. New sample distance acquired.",
    'ScanOrganicSecond': "Commander {commanderName} took the second of three biological samples.",
    'ScanOrganicThird': "Commander {commanderName} took the third and final biological samples.",
}

allGameEvents = {
    **startupEvents,
    **travelEvents,
    **combatEvents,
    **explorationEvents,
    **tradeEvents,
    **stationServiceEvents,
    **powerplayEvents,
    **squadronEvents,
    **carrierEvents,
    **odysseyEvents,
    **otherEvents,
    **projectedEvents,
}

externalEvents = {
    "SpanshTradePlanner": "The Spansh API has suggested a Trade Planner route for Commander {commanderName}.",
    "SpanshTradePlannerFailed": "The Spansh API has failed to retrieve a Trade Planner route for Commander {commanderName}.",
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

    def full_event_message(self, event: GameEvent|ProjectedEvent, is_important: bool):
        return {
            "role": "user",
            "content": f"({'IMPORTANT: ' if is_important else ''}{allGameEvents[event.content.get('event')].format(commanderName=self.commander_name)} Details: {json.dumps(event.content)})",
        }

    def simple_event_message(self, event: GameEvent|ProjectedEvent):
        return {
            "role": "user",
            "content": f"({allGameEvents[event.content.get('event')].format(commanderName=self.commander_name)})",
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
            "content": f"({externalEvents[event.content.get('event')].format(commanderName=self.commander_name)} Details: {json.dumps(event.content)})",
        }

    def tool_response_message(self, event: ToolEvent):
        return

    # fetch system info from EDSM
    @lru_cache(maxsize=1, typed=False)
    def get_system_info(self, system_name: str):
        url = "https://www.edsm.net/api-v1/system"
        params = {
            "systemName": system_name,
            "showInformation": 1,
            "showPrimaryStar": 1,
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()  # Raises an HTTPError for bad responses (4xx and 5xx)

            return response.text

        except Exception as e:
            log('error', e, traceback.format_exc())
            return "Currently no information on system available"

    # fetch station info from EDSM
    @lru_cache(maxsize=1, typed=False)
    def get_station_info(self, system_name: str, fleet_carrier=False):
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

    def generate_prompt(self, events: list[Event], projected_states: dict[str, dict], pending_events: list[Event]):
        # Collect the last 50 conversational pieces
        conversational_pieces: list = list()

        for event in events[::-1]:
            if len(conversational_pieces) >= 50:
                break

            is_pending = event in pending_events

            if isinstance(event, GameEvent) or isinstance(event, ProjectedEvent):
                if event.content.get('event') in allGameEvents:
                    if len(conversational_pieces) < 5 or is_pending:
                        is_important = is_pending and event.content.get('event') in self.important_game_events
                        conversational_pieces.append(self.full_event_message(event, is_important))
                    elif len(conversational_pieces) < 20:
                        conversational_pieces.append(self.simple_event_message(event))
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
        

        missions_info: MissionsState = projected_states.get('Missions', {}) # pyright: ignore[reportAssignmentType]
        
        if missions_info and 'Active' in missions_info:
            conversational_pieces.append(
                {
                    "role": "user",
                    "content": f"(Current missions: {json.dumps(missions_info)})",
                }
            )


        location_info: LocationState = projected_states.get('Location', {}) # pyright: ignore[reportAssignmentType]

        if "StarSystem" in location_info and location_info["StarSystem"] != "Unknown":
            conversational_pieces.append(
                {
                    "role": "user",
                    "content": f"(Current system: {self.get_system_info(location_info['StarSystem'])})",
                }
            )

            conversational_pieces.append(
                {
                    "role": "user",
                    "content": f"(Stations in current system: {self.get_station_info(location_info['StarSystem'])})",
                }
            )
        
        conversational_pieces.append(
            {"role": "user", "content": f"(Current location: {json.dumps(location_info)})"}
        )

        ship_info: ShipInfoState = projected_states.get('ShipInfo', {})  # pyright: ignore[reportAssignmentType]

        conversational_pieces.append(
            {"role": "user", "content": f"(Current ship: {json.dumps(ship_info)})"}
        )

        status = projected_states.get('CurrentStatus', {})
        flags = [key for key, value in status["flags"].items() if value]
        if status.get("flags2"):
            flags += [key for key, value in status["flags2"].items() if value]

        status_info = {
            "status": flags,
            "balance": status.get("Balance", None),
            "pips": status.get("Pips", None),
            "cargo": status.get("Cargo", None),
            "player_time": (datetime.now()).isoformat(),
            "elite_time": str(datetime.now().year + 1286) + (datetime.now()).isoformat()[4:],
        }

        current_status = projected_states.get("CurrentStatus")
        flags = current_status["flags"]
        flags2 = current_status["flags2"]

        active_mode = " "
        if flags:
            if flags["InMainShip"]:
                active_mode += "main ship"
            elif flags["InFighter"]:
                active_mode += "ship launched fighter"
            elif flags["InSRV"]:
                active_mode += "SRV"
        if flags2:
            if flags2["OnFoot"]:
                active_mode += "suit"

        conversational_pieces.append(
            {"role": "user", "content": f"(Current{active_mode} status: {json.dumps(status_info)})"}
        )
        conversational_pieces.append(
            {
                "role": "system",
                "content": "Let's roleplay in the universe of Elite: Dangerous. "
                + "I will provide game events in parentheses; do not create new ones. "
                + "Do not hallucinate any information that is not given to you. Do not use markdown in your responses. "
                + self.character_prompt.format(commander_name=self.commander_name),
            }
        )

        conversational_pieces.reverse()  # Restore the original order

        #log('debug', 'states', json.dumps(projected_states))
        log('debug', 'conversation', json.dumps(conversational_pieces))

        return conversational_pieces
