from datetime import timedelta, datetime
from functools import lru_cache
from typing import Any, Callable, cast, Dict, Union, List, Optional
import random

from openai.types.chat import ChatCompletionMessageParam
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
    WingJoinEvent, WingLeaveEvent, ColonisationConstructionDepotEvent
)

from .Projections import LocationState, MissionsState, ShipInfoState, NavInfo, TargetState, CurrentStatus, CargoState
from .SystemDatabase import SystemDatabase

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

# Add these new type definitions along with the other existing types
DockingCancelledEvent = dict
DockingTimeoutEvent = dict
LocationEvent = dict
NavRouteEvent = dict

class PromptGenerator:
    def __init__(self, commander_name: str, character_prompt: str, important_game_events: list[str], system_db: SystemDatabase):
        self.registered_prompt_event_handlers: list[Callable[[Event], list[ChatCompletionMessageParam]]] = []
        self.registered_status_generators: list[Callable[[dict[str, dict]], list[tuple[str, Any]]]] = []
        self.commander_name = commander_name
        self.character_prompt = character_prompt
        self.important_game_events = important_game_events
        self.system_db = system_db

    def get_event_template(self, event: Union[GameEvent, ProjectedEvent, ExternalEvent]):
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

        if event_name == "ColonisationConstructionDepot":
            return None

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
            return None

        if event_name == 'NavRoute':
            nav_route_event = cast(NavRouteEvent, content)
            if nav_route_event.get('Route'):
                route_count = len(nav_route_event.get('Route', [])) - 1  # jump count is 1 less than systems in route
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
        if event_name == 'Powerplay':
            return None
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

            system = screenshot_event.get('System') or 'current system'
            body = screenshot_event.get('Body') or ''
            body_text = f" near {body}" if body else ""

            location_text = ""
            if screenshot_event.get('Latitude') is not None and screenshot_event.get('Longitude') is not None and screenshot_event.get('Altitude') is not None:
                lat = screenshot_event.get('Latitude', 0)
                lon = screenshot_event.get('Longitude', 0)
                alt = screenshot_event.get('Altitude', 0)
                location_text = f" at coordinates {lat}, {lon}, altitude: {alt}m"

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

        if event_name == 'Loadout':
            return None

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
                
            return f"{self.commander_name} has boarded their {vehicle} {location}."
            
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
                
            return f"{self.commander_name} has {action} a {life_form} on planet {scan_event.get('Body', 'unknown body')}. {' The scan data can now be sold at the next station featuing a Vista Genomics.' if scan_type == 'Analyse' else ''}"
            
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
            return None
            
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

        # if event_name == 'Continued':
        #     continued_event = cast(Dict[str, Any], content)
        #     part = continued_event.get('Part', '?')
        #     return f"Journal file continued in part {part}."

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
            return None

        if event_name == 'NpcCrewPaidWage':
            wage_event = cast(Dict[str, Any], content)
            name = wage_event.get('NpcCrewName', 'An NPC crew member')
            amount = wage_event.get('Amount', 0)
            if amount == 0:
                return None
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

        if event_name == 'Cargo':
            return None
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

        if event_name == 'Bounty':
            bounty_event = cast(BountyEvent, content)
            rewards_text = ""
            if bounty_event.get('Rewards'):
                rewards = []
                for reward in bounty_event.get('Rewards', []):
                    rewards.append(f"{reward.get('Reward'):,} credits from {reward.get('Faction')}")
                rewards_text = f" ({', '.join(rewards)})"
            target = bounty_event.get('Target_Localised', bounty_event.get('Target', 'target'))
            return f"{self.commander_name} has collected a {bounty_event.get('TotalReward'):,} credit bounty for eliminating {target}{rewards_text}."

        if event_name == 'CapShipBond':
            cap_ship_bond_event = cast(Dict[str, Any], content)
            reward = cap_ship_bond_event.get('Reward', 0)
            victim_faction = cap_ship_bond_event.get('VictimFaction', 'enemy')
            awarding_faction = cap_ship_bond_event.get('AwardingFaction', 'allied')
            return f"{self.commander_name} has received a {reward:,} credit capital ship combat bond from {awarding_faction} for combat against {victim_faction}."

        if event_name == 'CargoDepot':
            cargo_depot_event = cast(Dict[str, Any], content)
            mission_id = cargo_depot_event.get('MissionID', 0)
            operation = cargo_depot_event.get('UpdateType', 'unknown')
            commodity = cargo_depot_event.get('CargoType', 'cargo')
            count = cargo_depot_event.get('Count', 0)
            total = cargo_depot_event.get('TotalCount', 0)
            return f"{self.commander_name} has {operation} {count} units of {commodity} for mission {mission_id} (Total: {total})."

        if event_name == 'CommunityGoal':
            cg_event = cast(Dict[str, Any], content)
            if cg_event.get('CurrentGoals'):
                goals = []
                for goal in cg_event.get('CurrentGoals', []):
                    goals.append(f"{goal.get('Title')} at {goal.get('System')}")
                return f"Community Goals available: {', '.join(goals)}."
            return f"No active Community Goals found."

        if event_name == 'CrimeVictim':
            crime_victim_event = cast(Dict[str, Any], content)
            offender = crime_victim_event.get('Offender', 'Unknown perpetrator')
            crime_type = crime_victim_event.get('CrimeType', 'unknown crime')
            return f"{self.commander_name} has been the victim of {crime_type} by {offender}."

        if event_name == 'Died':
            died_event = cast(DiedEvent, content)
            if died_event.get('KillerName'):
                return f"{self.commander_name} has been killed by {died_event.get('KillerName')} ({died_event.get('KillerShip', 'unknown ship')}, {died_event.get('KillerRank', 'unknown rank')})."
            return f"{self.commander_name} has been killed."

        if event_name == 'DockingCancelled':
            docking_cancelled_event = cast(DockingCancelledEvent, content)
            return f"{self.commander_name} has cancelled the docking request at {docking_cancelled_event.get('StationName')}."

        if event_name == 'EngineerContribution':
            engineer_contribution_event = cast(Dict[str, Any], content)
            engineer = engineer_contribution_event.get('Engineer', 'an engineer')
            type = engineer_contribution_event.get('Type', 'unknown')
            commodity = engineer_contribution_event.get('Commodity', engineer_contribution_event.get('Material', 'unknown'))
            quantity = engineer_contribution_event.get('Quantity', 0)
            total = engineer_contribution_event.get('TotalQuantity', 0)
            return f"{self.commander_name} has contributed {quantity} {commodity} ({type}) to {engineer}. Total: {total}."

        if event_name == 'EngineerLegacyConvert':
            legacy_convert_event = cast(Dict[str, Any], content)
            engineer = legacy_convert_event.get('Engineer', 'an engineer')
            return f"{self.commander_name} has converted legacy modifications with {engineer}."

        if event_name == 'FetchRemoteModule':
            fetch_module_event = cast(Dict[str, Any], content)
            module = fetch_module_event.get('StoredItem_Localised', fetch_module_event.get('StoredItem', 'a module'))
            cost = fetch_module_event.get('TransferCost', 0)
            time = fetch_module_event.get('TransferTime', 0)
            if time > 0:
                return f"{self.commander_name} has requested transfer of {module} for {cost:,} credits, arriving in {time} seconds."
            return f"{self.commander_name} has requested immediate transfer of {module} for {cost:,} credits."

        if event_name == 'FighterDestroyed':
            return f"{self.commander_name}'s fighter has been destroyed."

        if event_name == 'HeatDamage':
            return f"{self.commander_name}'s ship is taking heat damage!"

        if event_name == 'HeatWarning':
            return f"{self.commander_name}'s ship is overheating!"

        if event_name == 'HullDamage':
            hull_damage_event = cast(HullDamageEvent, content)
            health = hull_damage_event.get('Health', 0) * 100
            vehicle = "fighter" if hull_damage_event.get('Fighter') else "ship"
            return f"{self.commander_name}'s {vehicle} hull integrity at {health:.1f}%."

        if event_name == 'Interdicted':
            interdicted_event = cast(InterdictedEvent, content)
            if interdicted_event.get('IsThargoid'):
                interdictor = "a Thargoid"
            elif interdicted_event.get('Interdictor'):
                interdictor = interdicted_event.get('Interdictor_Localised', interdicted_event.get('Interdictor'))
            else:
                interdictor = "an unknown ship"
            
            outcome = "submitted to" if interdicted_event.get('Submitted') else "was forcibly interdicted by"
            return f"{self.commander_name} {outcome} {interdictor}."

        if event_name == 'Interdiction':
            interdiction_event = cast(Dict[str, Any], content)
            target = interdiction_event.get('Target', 'unknown ship')
            success = interdiction_event.get('Success', False)
            result = "successfully interdicted" if success else "failed to interdict"
            return f"{self.commander_name} has {result} {target}."

        if event_name == 'MassModuleStore':
            mass_store_event = cast(Dict[str, Any], content)
            ship = mass_store_event.get('Ship', 'current ship')
            items = mass_store_event.get('Items', [])
            count = len(items)
            return f"{self.commander_name} has stored {count} modules from their {ship}."

        if event_name == 'ModuleSellRemote':
            sell_remote_event = cast(Dict[str, Any], content)
            module = sell_remote_event.get('SellItem_Localised', sell_remote_event.get('SellItem', 'a module'))
            price = sell_remote_event.get('SellPrice', 0)
            return f"{self.commander_name} has sold {module} from storage for {price:,} credits."

        if event_name == 'Outfitting':
            outfitting_event = cast(OutfittingEvent, content)
            return f"{self.commander_name} is accessing outfitting services at {outfitting_event.get('StationName')} in {outfitting_event.get('StarSystem')}."

        if event_name == 'ScientificResearch':
            research_event = cast(Dict[str, Any], content)
            name = research_event.get('Name', 'unknown')
            category = research_event.get('Category', 'unknown category')
            count = research_event.get('Count', 0)
            return f"{self.commander_name} has contributed {count} {name} for scientific research in {category}."

        if event_name == 'ShieldState':
            shield_event = cast(Dict[str, Any], content)
            state = "online" if shield_event.get('ShieldsUp') else "offline"
            return f"{self.commander_name}'s shields are {state}."

        if event_name == 'ShipyardNew':
            new_ship_event = cast(Dict[str, Any], content)
            ship_type = new_ship_event.get('ShipType_Localised', new_ship_event.get('ShipType', 'a new ship'))
            return f"{self.commander_name} has purchased {ship_type}."

        if event_name == 'SRVDestroyed':
            srv_event = cast(SRVDestroyedEvent, content)
            srv_type = srv_event.get('SRVType_Localised', srv_event.get('SRVType', 'SRV'))
            return f"{self.commander_name}'s {srv_type} has been destroyed."

        if event_name == 'Statistics':
            # AI thinks wealth is credits when it's total assets so renaming it
            if "Bank_Account" in content and "Current_Wealth" in content["Bank_Account"]:
                content["Bank_Account"]["Total_Asset_Value"] = content["Bank_Account"].pop("Current_Wealth")

            return f"{self.commander_name}'s game statistics have been reported:\n{yaml.dump(content)}"

        if event_name == 'Trade':
            trade_event = cast(Dict[str, Any], content)
            commodity = trade_event.get('Type_Localised', trade_event.get('Type', 'goods'))
            count = trade_event.get('Count', 0)
            price_per_unit = trade_event.get('Price', 0)
            total_profit = trade_event.get('TotalProfit', 0)
            if trade_event.get('SellPrice'):
                return f"{self.commander_name} has sold {count} units of {commodity} at {price_per_unit:,} credits each (Total profit: {total_profit:,} credits)."
            else:
                return f"{self.commander_name} has purchased {count} units of {commodity} at {price_per_unit:,} credits each."

        if event_name == 'WeaponSelected':
            weapon_event = cast(Dict[str, Any], content)
            weapon = weapon_event.get('Weapon_Localised', weapon_event.get('Weapon', 'unknown weapon'))
            return f"{self.commander_name} has selected {weapon}."

        if event_name == 'ColonisationSystemClaim':
            claim_event = cast(Dict[str, Any], content)
            system = claim_event.get('StarSystem', '')
            return f"{self.commander_name} has claimed a system {system}."

        if event_name == 'ColonisationSystemClaimRelease':
            claim_event = cast(Dict[str, Any], content)
            system = claim_event.get('StarSystem', '')
            return f"{self.commander_name}'s claim on system {system} has been canceled."

        # Synthetic Events
        if event_name == 'ScanOrganicTooClose':
            return f"{self.commander_name} is now too close to take another sample. Distance must be increased."
        if event_name == 'ScanOrganicFarEnough':
            return f"{self.commander_name} is now far enough away to take another sample."
        if event_name == 'ScanOrganicFirst':
            scan_event = cast(Dict[str, Any], content)
            new_distance = scan_event.get('NewSampleDistance', 'unknown')
            return f"{self.commander_name} took the first of three biological samples. New sample distance acquired: {new_distance}"
        if event_name == 'ScanOrganicSecond':
            return f"{self.commander_name} took the second of three biological samples."
        if event_name == 'ScanOrganicThird':
            return f"{self.commander_name} took the third and final biological sample."
        if event_name == 'NoScoopableStars':
            return f"{self.commander_name}'s fuel is insufficient to reach the destination and there are not enough scoopable stars on the route. Alternative route required."
        if event_name == 'RememberLimpets':
            return f"{self.commander_name} has cargo capacity available to buy limpets. Remember to buy more."
        if event_name == 'CombatEntered':
            return f"{self.commander_name} is now in combat."
        if event_name == 'CombatExited':
            return f"{self.commander_name} is no longer in combat."
        # if event_name == 'ExternalDiscordNotification':
        #     twitch_event = cast(Dict[str, Any], content)
        #     return f"Twitch Alert! {twitch_event.get('text','')}",
        # "SpanshTradePlanner": "The Spansh API has suggested a Trade Planner route for Commander {commanderName}.",
        # "SpanshNeutronPlotter": "The Spansh API has suggested a Neutron Plotter router for Commander {commanderName}.",
        # "SpanshRoadToRiches": "The Spansh API has suggested a Road-to-Riches route for Commander {commanderName}.",
        if event_name == 'ExternalTwitchMessage':
            twitch_event = cast(Dict[str, Any], content)
            return f"Message received from {twitch_event.get('username','')} on Twitch Chat: {twitch_event.get('text','')}"
        if event_name == 'ExternalTwitchNotification':
            twitch_event = cast(Dict[str, Any], content)
            return f"{self.commander_name} has received a Discord notification."
        if event_name == 'Idle':
            return f"{self.commander_name} hasn't been responding for 5 minutes. Ponder about your current situation.",

        if event_name == "DockingComputerDocking":
            return f"{self.commander_name}'s ship has initiated automated docking computer"

        if event_name == "DockingComputerUndocking":
            # we know it's a station as we only trigger undocking event if we are inside a station
            return f"{self.commander_name}'s ship has initiated automated docking computer, we are leaving the station"

        if event_name == "DockingComputerDeactivated":
            return f"{self.commander_name}'s ship has deactivated the docking computer"

        log('debug', f'fallback for event', event_name, content)

        return f"Event: {event_name}\n{yaml.dump(content)}"

    def get_status_event_template(self, event: StatusEvent):
        status: Any = event.status
        event_name = status.get('event')

        # System events
        if event_name == 'Status':
            return None
        if event_name == 'LegalStateChanged':
            return f"Legal state is now {status['LegalState']}"
        if event_name == 'WeaponSelected':
            return f"Selected weapon {status['SelectedWeapon']}"

        if event_name == "SystemMapOpened":
            return "System map opened"
        if event_name == "SystemMapClosed":
            return "System map closed"
        if event_name == "GalaxyMapOpened":
            return "Galaxy map opened"
        if event_name == "GalaxyMapClosed":
            return "Galaxy map closed"
        if event_name == "SystemMapClosedGalaxyMapOpened":
            return "System map closed, Galaxy map opened"
        if event_name == "GalaxyMapClosedSystemMapOpened":
            return "Galaxy map closed, System map opened"
        if event_name == "HudSwitchedToCombatMode":
            return "Ship HUD is in combat mode"
        if event_name == "HudSwitchedToAnalysisMode":
            return "Ship HUD is in Analysis mode"
        if event_name == 'LandingGearUp':
            return 'Landing gear has been retracted'
        if event_name == 'LandingGearDown':
            return 'Landing gear has been deployed'
        if event_name == 'FlightAssistOn':
            return 'Flight stabilizer engaged, drift ending'
        if event_name == 'FlightAssistOff':
            return 'Flight stabilizer disengaged, drift starting'
        if event_name == 'HardpointsRetracted':
            return 'Hardpoints retracted'
        if event_name == 'HardpointsDeployed':
            return 'Hardpoints (Weapons/Scanners) deployed and ready'
        if event_name == 'SilentRunningOff':
            return 'Silent running mode deactivated, thermal signature normalized'
        if event_name == 'SilentRunningOn':
            return 'Silent running mode activated, suppressing thermal signature'
        if event_name == 'FuelScoopEnded':
            return 'Fuel collection complete, fuel scoop disengaged'
        if event_name == 'FuelScoopStarted':
            return 'Fuel scoop engaged, collecting stellar material'
        if event_name == 'LightsOff':
            return 'External lighting systems powered down'
        if event_name == 'LightsOn':
            return 'External lighting systems activated'
        if event_name == 'CargoScoopRetracted':
            return 'Cargo scoop retracted, collection systems offline'
        if event_name == 'CargoScoopDeployed':
            return 'Cargo scoop deployed, ready to collect materials'
        if event_name == 'FsdMassLockEscaped':
            return 'Frame Shift Drive mass lock released, hyperspace available'
        if event_name == 'FsdMassLocked':
            return 'Frame Shift Drive mass locked by nearby objects, hyperspace restricted'
        if event_name == 'GlideModeExited':
            return 'Glide mode disengaged, returned to normal flight'
        if event_name == 'GlideModeEntered':
            return 'Entered atmospheric glide mode, maintaining controlled descent'
        if event_name == 'LowFuelWarningCleared':
            return 'Fuel levels restored to acceptable levels'
        if event_name == 'LowFuelWarning':
            return 'Warning: Fuel reserves critically low, refueling recommended'
        if event_name == 'FsdCharging':
            return 'Frame Shift Drive charging, preparing for jump'
        if event_name == 'SrvHandbrakeOff':
            return 'SRV handbrake released, free to move'
        if event_name == 'SrvHandbrakeOn':
            return 'SRV handbrake engaged, vehicle secured'
        if event_name == 'SrvTurretViewDisconnected':
            return 'SRV turret view disconnected, returning to normal operation'
        if event_name == 'SrvTurretViewConnected':
            return 'SRV turret view connected, weapon systems accessible'
        if event_name == 'SrvDriveAssistOff':
            return 'SRV drive assist disabled, manual control active'
        if event_name == 'SrvDriveAssistOn':
            return 'SRV drive assist enabled, terrain compensation active'
        if event_name == 'LowOxygenWarningCleared':
            return 'Oxygen levels returned to normal parameters'
        if event_name == 'LowOxygenWarning':
            return 'Warning: Life support oxygen reserves critically low'
        if event_name == 'LowHealthWarningCleared':
            return 'Hull integrity stabilized, critical damage repaired'
        if event_name == 'LowHealthWarning':
            return 'Warning: Hull integrity critical, immediate repairs recommended'
        if event_name == 'BreathableAtmosphereExited':
            return 'Exited breathable atmosphere, life support systems active'
        if event_name == 'BreathableAtmosphereEntered':
            return 'Entered breathable atmosphere, external oxygen available'
        if event_name == 'OutofDanger':
            return 'No potential danger detected by scanners anymore. All clear.'
        if event_name == 'InDanger':
            return 'Potentially dangerous situation detected by scanners.'
        if event_name == 'NightVisionOff':
            return 'Night vision system deactivated'
        if event_name == 'NightVisionOn':
            return 'Night vision system activated'

        return None

    def event_message(self, event: Union[GameEvent, ProjectedEvent, ExternalEvent], timeoffset: str, is_important: bool):
        message = self.get_event_template(event)
        if message:
            return {
                "role": "user",
                "content": f"[{'IMPORTANT ' if is_important else ''}Game Event, {timeoffset}] {message}",
            }

        # Deliberately ignored events
        # log('info', f'ignored event', event)
        return None

    def status_messages(self, event: StatusEvent, timeoffset: str, is_important: bool):
        message = self.get_status_event_template(event)
        if message:
            return {
                "role": "user",
                "content": f"[{'IMPORTANT ' if is_important else ''}Game Event, {timeoffset}] {message}",
            }

        # Deliberately ignored events
        # log('info', f'ignored event', event)
        return None

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

    def tool_response_message(self, event: ToolEvent):
        return

    # Helper method to format station data into the desired structure
    def format_stations_data(self, stations_data) -> dict | str | list:
        """Format station data into the desired hierarchy regardless of source"""
        # If it's already a string or None, return as is
        if not stations_data or isinstance(stations_data, str):
            return stations_data or "No station data available"
            
        # Step 1: Process raw station data into a standard format
        station_data = []
        
        # Handle different possible input formats
        if isinstance(stations_data, list) and "stations" not in stations_data:
            # Direct list of stations from projections
            for station in stations_data:
                # Create a standardized station entry
                station_entry = self._create_standard_station_entry(station)
                station_data.append(station_entry)
                
        elif isinstance(stations_data, dict) and "stations" in stations_data:
            # Raw API response format from EDSM
            for station in stations_data["stations"]:
                if station.get("type") == "Fleet Carrier":
                    continue
                    
                # Create a standardized station entry
                station_entry = self._create_standard_station_entry(station, raw_format=True)
                station_data.append(station_entry)
        else:
            # Already processed data or unknown format
            if isinstance(stations_data, (dict, list)):
                return stations_data
            return "Unknown station data format"
            
        # If we have no stations after filtering
        if not station_data:
            return "No stations found in this system"
            
        # Step 2: Group by body and type
        result = {}
        
        # First collect orbit distances by body
        body_orbits = {}
        for station in station_data:
            body = station["body"]
            if body not in body_orbits and isinstance(station["orbit"], (int, float)):
                body_orbits[body] = station["orbit"]
        
        # Then group stations by body and type
        for station in station_data:
            body = station["body"]
            station_type = station["type"]
            
            # Format body label with orbit distance
            orbit_text = ""
            if body in body_orbits:
                orbit_text = f" ({body_orbits[body]}ls)"
            body_label = f"{body}{orbit_text}"
            
            # Initialize body section if needed
            if body_label not in result:
                result[body_label] = {}
            
            # Initialize station type section if needed
            if station_type not in result[body_label]:
                result[body_label][station_type] = []
            
            # Create clean station entry without redundant fields
            # station is {'body': 'In Orbit around Primary Star', 'orbit': 18.414, 'economy': 'Refinery/Extraction', 'services': ['market', 'shipyard', 'outfitting'], 'name': 'Dobrovolski Plant', 'type': 'Coriolis Starport', 'government': 'Empire Corporate', 'controllingFaction': 'East India Company'}
            clean_station = {
                "name": station["name"],
                "economy": station["economy"],
                "services": station["services"],
                "government": station["government"],
                "controllingFaction": station["controllingFaction"],
            }
            
            # Add to result structure
            result[body_label][station_type].append(clean_station)
        
        return result
        
    def _create_standard_station_entry(self, station, raw_format=False):
        """Create a standardized station entry from either projection or raw API data"""
        # Create a normalized station dict to work with
        normalized = {}
        
        # Handle body field
        if raw_format and "body" in station and "name" in station["body"]:
            normalized["body"] = station["body"]["name"]
        else:
            normalized["body"] = station.get("body", "In Orbit around Primary Star")
            
        # Handle orbit distance field
        if raw_format:
            orbit = station.get("distanceToArrival", "Unknown")
        else:
            orbit = station.get("orbit", "Unknown")
            
        if isinstance(orbit, (int, float)):
            normalized["orbit"] = round(float(orbit), 3)
        else:
            normalized["orbit"] = orbit
            
        # Handle economy fields - unified approach
        normalized["economy"] = station.get("economy", "None")
        # The secondEconomy field might have different structure based on source
        second_economy = station.get("secondEconomy")
        
        # Combine economy fields if both exist and aren't "None"
        if normalized["economy"] != "None" and second_economy and second_economy != "None":
            normalized["economy"] = f"{normalized['economy']}/{second_economy}"
            
        # Add reserve information if it exists
        reserve = station.get("reserve")
        if reserve and reserve != "None":
            normalized["economy"] = f"{normalized['economy']} ({reserve})"
            
        # Handle services field
        if raw_format:
            normalized["services"] = [
                service
                for service, has_service in {
                    "market": station.get("haveMarket", False),
                    "shipyard": station.get("haveShipyard", False),
                    "outfitting": station.get("haveOutfitting", False),
                }.items()
                if has_service
            ]
        else:
            normalized["services"] = station.get("services", [])
            
        # Add all other basic fields
        normalized["name"] = station.get("name", "Unknown")
        normalized["type"] = station.get("type", "Unknown")
        normalized["government"] = f"{station.get("allegiance", "")} {station.get("government", "None")}"
        
        # Handle controllingFaction which might have different structure
        if raw_format and isinstance(station.get("controllingFaction"), dict):
            normalized["controllingFaction"] = station["controllingFaction"].get("name", "Unknown")
        else:
            normalized["controllingFaction"] = station.get("controllingFaction", "Unknown")
            
        return normalized

    def generate_vehicle_status(self, current_status:dict, in_combat:dict):
        flags = [key for key, value in current_status["flags"].items() if value]
        if current_status.get("flags2"):
            flags += [key for key, value in current_status["flags2"].items() if value]

        if in_combat.get("InCombat", False):
            flags.append("InCombat")

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

        active_mode, vehicle_status = self.generate_vehicle_status(projected_states.get('CurrentStatus', {}), projected_states.get('InCombat', {}))
        status_entries.append((active_mode+" status", vehicle_status))


        guifocus = projected_states.get('CurrentStatus', {}).get('GuiFocus', '')
        if guifocus != "NoFocus":
            status_entries.append(("Current active window: ", guifocus))

        # Get ship and cargo info
        ship_info: ShipInfoState = projected_states.get('ShipInfo', {})  # pyright: ignore[reportAssignmentType]
        cargo_info: CargoState = projected_states.get('Cargo', {})  # pyright: ignore[reportAssignmentType]
        
        # Create a copy of ship_info so we don't modify the original
        ship_display = dict(ship_info)
        ship_display.pop('IsMiningShip', None)
        ship_display.pop('hasLimpets', None)

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

        if active_mode == 'Main ship':
            # Get the ship loadout information
            loadout_info = projected_states.get('Loadout', {})

            if loadout_info:
                # Create comprehensive ship loadout display focusing only on modules
                loadout_display = {}

                # Process modules - group by slot type for better organization
                if loadout_info.get('Modules'):
                    modules_by_category = {}

                    for module in loadout_info.get('Modules', []):
                        slot = module.get('Slot', 'Unknown')
                        item = module.get('Item', 'Unknown')

                        # Extract category from slot name
                        if slot.startswith('MediumHardpoint') or slot.startswith(
                                'SmallHardpoint') or slot.startswith('LargeHardpoint') or slot.startswith(
                                'HugeHardpoint') or slot.startswith('TinyHardpoint'):
                            category = "Weapons"
                        elif slot in ['Armour', 'PowerPlant', 'MainEngines', 'FrameShiftDrive', 'LifeSupport',
                                      'PowerDistributor', 'Radar', 'FuelTank']:
                            category = "Core Internals"
                        elif slot.startswith('Slot'):
                            category = "Optional Internals"
                        elif slot in ['ShipCockpit', 'CargoHatch', 'PlanetaryApproachSuite']:
                            category = "Essential Components"
                        elif slot in ['Bobble', 'ShipKitSpoiler', 'ShipKitBumper', 'ShipKitWings', 'WeaponColour',
                                      'EngineColour', 'VesselVoice', 'Decal1', 'Decal2', 'Decal3', 'NamePlate',
                                      'PaintJob']:
                            category = "Cosmetics"
                        else:
                            category = "Other"

                        # Create category if it doesn't exist
                        if category not in modules_by_category:
                            modules_by_category[category] = []

                        # Format module information
                        module_info = {
                            # "Slot": slot,
                            "Item": item
                        }

                        # Add simplified ammo information if available
                        if module.get('AmmoInHopper') is not None:
                            module_info["Max Ammo"] = module.get('AmmoInHopper')

                        # Add simplified engineering information if available
                        if module.get('Engineering'):
                            eng_info = module.get('Engineering', {})
                            engineering = {
                                "Blueprint": eng_info.get('BlueprintName', 'Unknown'),
                                "Level": eng_info.get('Level', 0),
                            }

                            # Add experimental effect if present
                            if eng_info.get('ExperimentalEffect_Localised'):
                                engineering["Experimental"] = eng_info.get('ExperimentalEffect_Localised')

                            module_info["Engineering"] = engineering

                        modules_by_category[category].append(module_info)

                    # Add modules to the loadout display
                    loadout_display = modules_by_category

                # Add the loadout information to status entries
                ship_display['Loadout'] = loadout_display

        status_entries.append(("Main Ship", ship_display))
        
        # Get location info
        location_info: LocationState = projected_states.get('Location', {})  # pyright: ignore[reportAssignmentType]
        
        # Process location info
        if location_info:
            system_name = location_info.get('StarSystem')
            system_info = None
            stations_info = None
            
            # Direct lookup from system database instead of SystemInfo projection
            if system_name:
                # Get system info from system database
                raw_system_info = self.system_db.get_system_info(system_name, async_fetch=True)
                if raw_system_info and not isinstance(raw_system_info, str):
                    system_info = self.format_system_info(raw_system_info)

                # Get stations from system database
                stations_data = self.system_db.get_stations(system_name)
                if stations_data:
                    stations_info = self.format_stations_data(stations_data)

            if location_info.get('Station'):
                if not location_info.get('Docked'):
                    location_info["Station"] = f"Outside {location_info['Station']}"

            altitude = projected_states.get('CurrentStatus', {}).get('Altitude') or None
            if altitude:
                location_info["Altitude"] = f"{altitude} km"

            status_entries.append(("Location", location_info))
            status_entries.append(("Local system", system_info))
            status_entries.append(("Stations in local system", stations_info))

        # Nav Route 
        if "NavInfo" in projected_states and projected_states["NavInfo"].get("NavRoute"):
            nav_route = projected_states["NavInfo"]["NavRoute"]
            
            # Enhance NavRoute with data from system database instead of SystemInfo projection
            enhanced_nav_route = []
            # Limit to first 20 systems
            systems_to_process = nav_route[:20]
            total_systems = len(nav_route)
            
            for system in systems_to_process:
                system_data = {**system}  # Create a copy of the original system data
                
                # Try to get additional info from system database
                system_name = system.get("StarSystem")
                if system_name:
                    raw_system_info = self.system_db.get_system_info(system_name, async_fetch=True)
                    if raw_system_info and not isinstance(raw_system_info, str):
                        # Use the formatter which now returns display-ready data
                        formatted_info = self.format_system_info(raw_system_info)
                        
                        # If we got valid formatted info, merge it with system_data
                        if isinstance(formatted_info, dict):
                            # Only add the keys we want for nav route display
                            for key in ["Government", "Population", "Unexplored", "Economy"]:
                                if key in formatted_info:
                                    system_data[key] = formatted_info[key]
                
                enhanced_nav_route.append(system_data)
            
            # We need to convert to a dict to add 'Jumps'
            enhanced_nav_route_dict = {"Systems": enhanced_nav_route, "Jumps": total_systems - 1}
            
            # Set appropriate title based on whether we're showing all systems or just the first 20
            nav_route_title = "Nav Route"
            if total_systems > 20:
                nav_route_title = "First 20 Systems of Nav Route"
            
            status_entries.append((nav_route_title, enhanced_nav_route_dict))

        # Target
        target_info: TargetState = projected_states.get('Target', {})  # pyright: ignore[reportAssignmentType]
        target_info.pop('EventID', None)
        if target_info.get('Ship', False):
            status_entries.append(("Weapons' target", target_info))

        # Market and station information
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
            # Create a nested structure from outfitting items with optimized leaf nodes
            nested_outfitting = {}

            # First pass: collect all items by their categories
            item_categories = {}

            for item in outfitting.get('Items', []):
                item_name = item.get('Name', '')
                if not item_name or '_' not in item_name:
                    continue

                parts = item_name.split('_')
                # Group items by their parent paths
                parent_path = '_'.join(parts[:-1])
                leaf = parts[-1]

                if parent_path not in item_categories:
                    item_categories[parent_path] = []
                item_categories[parent_path].append(leaf)

            # Second pass: build the optimized structure
            for path, leaves in item_categories.items():
                parts = path.split('_')
                current = nested_outfitting

                # Build the nested path
                for i in range(len(parts)):
                    part = parts[i]
                    if i < len(parts) - 1:
                        # Not the last part, ensure we have a dictionary
                        if part not in current:
                            current[part] = {}
                        if not isinstance(current[part], dict):
                            current[part] = {}
                        current = current[part]
                    else:
                        # Last part - add the optimized leaf
                        # Process the leaf nodes according to patterns
                        if any(leaf.startswith('class') for leaf in leaves):
                            # Extract class numbers and create a compact string
                            class_numbers = []
                            for leaf in leaves:
                                if leaf.startswith('class'):
                                    try:
                                        num = leaf.replace('class', '')
                                        class_numbers.append(num)
                                    except:
                                        class_numbers.append(leaf)
                            # Instead of using f-string, create a dictionary entry
                            current[part] = {"class": f"{','.join(sorted(class_numbers))}"}
                        elif any(leaf.startswith('size') for leaf in leaves):
                            # Extract size numbers
                            size_numbers = []
                            for leaf in leaves:
                                if leaf.startswith('size'):
                                    try:
                                        num = leaf.replace('size', '')
                                        size_numbers.append(num)
                                    except:
                                        size_numbers.append(leaf)
                            # Instead of using f-string, create a dictionary entry
                            current[part] = {"size": f"{','.join(sorted(size_numbers))}"}
                        else:
                            # Regular processing for other types - use a string directly
                            current[part] = f"{','.join(sorted(leaves))}"

            # Final pass: flatten the special dictionary entries to avoid quotes
            def flatten_special_entries(data):
                if not isinstance(data, dict):
                    return data

                result = {}
                for key, value in data.items():
                    if isinstance(value, dict) and len(value) == 1:
                        # Check if this is our special format with class or size
                        special_key = next(iter(value.keys()), None)
                        if special_key in ('class', 'size'):
                            # Flatten it to a direct string to avoid quotes
                            result[key] = f"{special_key} {value[special_key]}"
                        else:
                            # Regular nested dictionary
                            result[key] = flatten_special_entries(value)
                    else:
                        # Regular processing
                        result[key] = flatten_special_entries(value) if isinstance(value, dict) else value
                return result

            # Apply the flattening
            nested_outfitting = flatten_special_entries(nested_outfitting)

            status_entries.append(("Local outfitting information", nested_outfitting))
        if current_station and current_station == storedShips.get('StationName'):
            status_entries.append(("Local, stored ships", storedShips.get('ShipsHere', [])))
            
        # Missions
        missions_info: MissionsState = projected_states.get('Missions', {})  # pyright: ignore[reportAssignmentType]
        if missions_info and 'Active' in missions_info:
            status_entries.append(("Active missions", missions_info))

        # Add colonisation construction status if available
        colonisation_info = projected_states.get('ColonisationConstruction', {})
        if colonisation_info and colonisation_info.get('Location', 'Unknown') != 'Unknown':
            progress = colonisation_info.get('ConstructionProgress', 0.0)
            complete = colonisation_info.get('ConstructionComplete', False)
            failed = colonisation_info.get('ConstructionFailed', False)
            resources = colonisation_info.get('ResourcesRequired', [])
            starsystem = colonisation_info.get('StarSystem', 'Unknown')

            construction_status = {
                "Location": f"{starsystem}",
                "Progress": f"{progress:.1%}",
                "Status": "Complete" if complete else "Failed" if failed else "In Progress"
            }

            if resources:
                missing_resources = {}
                for resource in resources:
                    required = resource.get('RequiredAmount', 0)
                    provided = resource.get('ProvidedAmount', 0)
                    delta = required - provided

                    # Only include resources that still need more items
                    if delta > 0:
                        name = resource.get('Name_Localised', resource.get('Name', ''))
                        missing_resources[name] = delta

                # Only add missing resources if there are any
                if missing_resources:
                    construction_status["Missing Resources"] = missing_resources

            status_entries.append(("Colonisation Construction", construction_status))

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

        # Engineer status
        engineer_systems = {
            "Tod 'The Blaster' McQuinn": "Wolf 397",
            "Felicity Farseer": "Deciat",
            "Elvira Martuuk": "Khun",
            "Liz Ryder": "Eurybia",
            "The Dweller": "Wyrd",
            "Lei Cheung": "Laksak",
            "Selene Jean": "Kuk",
            "Hera Tani": "Kuwemaki",
            "Broo Tarquin": "Muang",
            "Marco Qwent": "Sirius",
            "Zacariah Nemo": "Yoru",
            "Didi Vatermann": "Leesti",
            "Colonel Bris Dekker": "Sol",
            "Juri Ishmaak": "Giryak",
            "Professor Palin": "Arque",
            "Bill Turner": "Alioth",
            "Lori Jameson": "Shinrarta Dezhra",
            "Ram Tah": "Meene",
            "Tiana Fortune": "Achenar",
            "The Sarge": "Beta-3 Tucani",
            "Etienne Dorn": "Los",
            "Marsha Hicks": "Tir",
            "Mel Brandon": "Luchtaine",
            "Petra Olmanova": "Asura",
            "Chloe Sedesi": "Shenve",
            "Domino Green": "Orishis",
            "Hero Ferrari": "Siris",
            "Jude Navarro": "Aurai",
            "Kit Fowler": "Capoya",
            "Oden Geiger": "Candiaei",
            "Terra Velasquez": "Shou Xing",
            "Uma Laszlo": "Xuane",
            "Wellington Beck": "Jolapa",
            "Yarden Bond": "Bayan",
            "Baltanos": "Deriso",
            "Eleanor Bresa": "Desy",
            "Rosa Dayette": "Kojeara",
            "Yi Shen": "Einheriar"
        }
        engineer_info = projected_states.get('EngineerProgress', {})

        # Process engineers that are either Unlocked or Invited
        if engineer_info and 'Engineers' in engineer_info:
            available_engineers = {}
            for engineer in engineer_info.get('Engineers', []):
                progress = engineer.get('Progress')
                if progress in ['Unlocked', 'Invited']:
                    engineer_name = engineer.get('Engineer')
                    if engineer_name in engineer_systems:
                        available_engineers[engineer_name] = engineer_systems[engineer_name]

            if available_engineers:
                status_entries.append(("Available Engineers", available_engineers))
        
        # Process plugin status messages
        for status_generator in self.registered_status_generators:
            try:
                status_entries += status_generator(projected_states)
            except Exception as e:
                log('error', f"Error executing status generator: {e}", traceback.format_exc())

        # Format and return the final status message
        return "\n\n".join(['# '+entry[0]+'\n' + yaml.dump(entry[1], sort_keys=False) for entry in status_entries])

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

            if isinstance(event, GameEvent) or isinstance(event, ProjectedEvent) or isinstance(event, ExternalEvent):
                if len(conversational_pieces) < 20 or is_pending:
                    is_important = is_pending and event.content.get('event') in self.important_game_events
                    message = self.event_message(event, time_offset, is_important)
                    if message:
                        conversational_pieces.append(message)

            if isinstance(event, StatusEvent):
                if (
                    len(conversational_pieces) < 20
                    and event.status.get("event") != "Status"
                ):
                    is_important = is_pending and event.status.get('event') in self.important_game_events
                    message = self.status_messages(event, time_offset, is_important)
                    if message:
                        conversational_pieces.append(message)

            if isinstance(event, ConversationEvent) and event.kind in ['user', 'assistant']:
                conversational_pieces.append(self.conversation_message(event))

            if isinstance(event, ToolEvent):
                conversational_pieces += self.tool_messages(event)

            for handler in self.registered_prompt_event_handlers:
                try:
                    conversational_pieces += handler(event)
                except Exception as e:
                    log('error', f"Error executing prompt event handler for {event}: {e}", traceback.format_exc())

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
                    "content": "The universe of Elite:Dangerous is your reality. Never mention it or refer to it as a game. "
                    + "Your purpose is to provide information, status updates, and execute tools as required. Only use tools you are given from me. "
                    + "You do not ask questions or initiate conversations. You respond only when addressed and in a single sentence. "
                    + "I will provide game events in parentheses; do not create new ones. Only react to game events marked with 'IMPORTANT:'.  "
                    + "Stay consistent with the lived experience. Do not hallucinate any information that is not given to you. "
                    + "Do not use markdown in your responses. "
                    # The character_prompt now contains all the generated settings
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
    
    def register_prompt_event_handler(self, prompt_event_handler: Callable[[Event], list[ChatCompletionMessageParam]]):
        self.registered_prompt_event_handlers.append(prompt_event_handler)
    
    def register_status_generator(self, status_generator: Callable[[dict[str, dict]], list[tuple [str, Any]]]):
        self.registered_status_generators.append(status_generator)

    def format_system_info(self, system_info: dict) -> dict:
        """
        Format system info into a structured template suitable for direct display
        Returns a dictionary that can be directly used in the UI or passed to display functions
        """
        if not system_info or isinstance(system_info, str):
            return system_info
            
        # Create a new dictionary for the formatted information - top level will be directly usable
        formatted = {}
        
        # Add the system name
        formatted["Name"] = system_info.get("name", "Unknown")

        # Mark as unexplored if applicable
        if "primaryStar" in system_info and not system_info["primaryStar"]:
            formatted["Unexplored"] = "true"
            return formatted
        
        # Process information section
        if "information" in system_info and system_info["information"]:
            info_data = system_info["information"]
            
            # Format government/security/allegiance for display
            government_parts = []
            if info_data.get("security") and info_data.get("security") != "None":
                government_parts.append(f"{info_data['security']} Security")
            if info_data.get("allegiance"):
                government_parts.append(info_data["allegiance"])
            if info_data.get("government"):
                government_parts.append(info_data["government"])

            if government_parts:
                formatted["Government"] = " ".join(government_parts)

            # Format economy information
            economy_parts = []
            if info_data.get("economy"):
                economy_parts.append(info_data["economy"])
            if info_data.get("secondEconomy"):
                economy_parts.append(info_data["secondEconomy"])

            if economy_parts:
                formatted["Economy"] = "/".join(economy_parts)
                if info_data.get("reserve"):
                    formatted["Economy"] += f" ({info_data['reserve']})"

            # Add faction information
            if info_data.get("faction"):
                faction_text = info_data["faction"]
                if info_data.get("factionState"):
                    faction_text += f" ({info_data['factionState']})"
                formatted["Faction"] = faction_text

            # Add population only if > 0
            population = info_data.get("population", 0)
            if population is not None and population > 0:
                formatted["Population"] = population
        
        # Process primary star
        if "primaryStar" in system_info and system_info["primaryStar"]:
            star_data = system_info["primaryStar"]
            formatted["Star"] = star_data.get("name", "Unknown")
            formatted["Star Type"] = star_data.get("type", "Unknown")
            formatted["Scoopable"] = star_data.get("isScoopable")

        # Include coordinates if available
        if "coords" in system_info:
            coords = system_info.get("coords", {})
            if coords and isinstance(coords, dict):
                formatted["Coordinates"] = f"X: {coords.get('x')}, Y: {coords.get('y')}, Z: {coords.get('z')}"

        return formatted
