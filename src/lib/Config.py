import json
from pathlib import Path
import platform
from threading import Semaphore
import traceback
from typing import Any, Literal, TypedDict, Optional, Dict, Union, cast, Tuple, List
import os
import sys
from openai import OpenAI, APIError

from .Logger import log

# List of game events categorized
game_events = {
    # System
    # 'Cargo': "no_react",
    # 'ClearSavedGame': "no_react",
    'Idle': "no_react"
    ,
    'LoadGame': "react",
    'Shutdown': "react",
    'NewCommander': "react",
    # 'Materials': "no_react",
    'Missions': "react",
    # 'Progress': "no_react",
    # 'Powerplay': "no_react",
    # 'Rank': "no_react",
    # 'Reputation': "no_react",
    'Statistics': "no_react",
    # 'SquadronStartup': "no_react",
    # 'EngineerProgress': "no_react",

    # Combat
    'Died': "react",
    'Resurrect': "react",
    'WeaponSelected': "no_react",
    'InDanger': "no_react",
    'OutofDanger': "no_react",
    'CombatEntered': "react",
    'CombatExited': "react",
    'LegalStateChanged': "react",
    'CommitCrime': "no_react",
    'Bounty': "no_react",
    'CapShipBond': "no_react",
    'Interdiction': "no_react",
    'Interdicted': "no_react",
    'EscapeInterdiction': "no_react",
    'BeingInterdicted': "react",
    'FactionKillBond': "no_react",
    'FighterDestroyed': "react",
    'HeatDamage': "react",
    'HeatWarning': "no_react",
    'HullDamage': "no_react",
    'PVPKill': "react",
    'ShieldState': "react",
    'ShipTargetted': "no_react",
    'UnderAttack': "no_react",
    'CockpitBreached': "react",
    'CrimeVictim': "react",
    'SystemsShutdown': "react",
    'SelfDestruct': "react",

    # Trading
    'BuyTradeData': "no_react",
    'CollectCargo': "no_react",
    'EjectCargo': "react",
    'MarketBuy': "no_react",
    'MarketSell': "no_react",
    'CargoTransfer': "no_react",
    'Market': "no_react",

    # Mining
    'AsteroidCracked': "no_react",
    'MiningRefined': "no_react",
    'ProspectedAsteroid': "react",
    'LaunchDrone': "no_react",
    'RememberLimpets': "react",

    # Ship Updates
    'FSDJump': "no_react",
    'FSDTarget': "no_react",
    'StartJump': "no_react",
    'FsdCharging': "react",
    'SupercruiseEntry': "react",
    'SupercruiseExit': "react",
    'ApproachSettlement': "react",
    'Docked': "react",
    'Undocked': "react",
    'DockingCanceled': "no_react",
    'DockingDenied': "react",
    'DockingGranted': "no_react",
    'DockingRequested': "no_react",
    'DockingTimeout': "react",
    'DockingComputerDocking': "no_react",
    'DockingComputerUndocking': "no_react",
    'DockingComputerDeactivated': "no_react",
    'NavRoute': "no_react",
    'NavRouteClear': "no_react",
    'CrewLaunchFighter': "react",
    'VehicleSwitch': "no_react",
    'LaunchFighter': "react",
    'DockFighter': "react",
    'FighterRebuilt': "react",
    'FuelScoop': "no_react",
    'RebootRepair': "react",
    'RepairDrone': "no_react",
    'AfmuRepairs': "no_react",
    'ModuleInfo': "no_react",
    'Synthesis': "no_react",
    'JetConeBoost': "no_react",
    'JetConeDamage': "no_react",
    'LandingGearUp': "no_react",
    'LandingGearDown': "no_react",
    'FlightAssistOn': "no_react",
    'FlightAssistOff': "no_react",
    'HardpointsRetracted': "no_react",
    'HardpointsDeployed': "no_react",
    'LightsOff': "no_react",
    'LightsOn': "no_react",
    'CargoScoopRetracted': "no_react",
    'CargoScoopDeployed': "no_react",
    'SilentRunningOff': "no_react",
    'SilentRunningOn': "no_react",
    'FuelScoopStarted': "no_react",
    'FuelScoopEnded': "no_react",
    'FsdMassLockEscaped': "no_react",
    'FsdMassLocked': "no_react",
    'LowFuelWarningCleared': "react",
    'LowFuelWarning': "react",
    'NoScoopableStars': "react",
    'NightVisionOff': "no_react",
    'NightVisionOn': "no_react",
    'SupercruiseDestinationDrop': "no_react",

    # SRV Updates
    'LaunchSRV': "react",
    'DockSRV': "react",
    'SRVDestroyed': "react",
    'SrvHandbrakeOff': "no_react",
    'SrvHandbrakeOn': "no_react",
    'SrvTurretViewConnected': "no_react",
    'SrvTurretViewDisconnected': "no_react",
    'SrvDriveAssistOff': "no_react",
    'SrvDriveAssistOn': "no_react",

    # On-Foot Updates
    'Disembark': "react",
    'Embark': "react",
    'BookDropship': "react",
    'BookTaxi': "react",
    'CancelDropship': "react",
    'CancelTaxi': "react",
    'CollectItems': "no_react",
    'DropItems': "no_react",
    'BackpackChange': "no_react",
    'BuyMicroResources': "no_react",
    'SellMicroResources': "no_react",
    'TransferMicroResources': "no_react",
    'TradeMicroResources': "no_react",
    'BuySuit': "react",
    'BuyWeapon': "react",
    'SellWeapon': "no_react",
    'UpgradeSuit': "no_react",
    'UpgradeWeapon': "no_react",
    'CreateSuitLoadout': "react",
    'DeleteSuitLoadout': "no_react",
    'RenameSuitLoadout': "react",
    'SwitchSuitLoadout': "react",
    'UseConsumable': "no_react",
    'FCMaterials': "no_react",
    'LoadoutEquipModule': "no_react",
    'LoadoutRemoveModule': "no_react",
    'ScanOrganic': "react",
    'SellOrganicData': "react",
    'LowOxygenWarningCleared': "react",
    'LowOxygenWarning': "react",
    'LowHealthWarningCleared': "react",
    'LowHealthWarning': "react",
    'BreathableAtmosphereExited': "no_react",
    'BreathableAtmosphereEntered': "no_react",
    'GlideModeExited': "no_react",
    'GlideModeEntered': "no_react",
    'DropShipDeploy': "no_react",

    # Stations
    'MissionAbandoned': "react",
    'MissionAccepted': "react",
    'MissionCompleted': "react",
    'MissionFailed': "react",
    'MissionRedirected': "react",
    'StationServices': "no_react",
    'ShipyardBuy': "react",
    'ShipyardNew': "no_react",
    'ShipyardSell': "no_react",
    'ShipyardTransfer': "no_react",
    'ShipyardSwap': "no_react",
    'StoredShips': "no_react",
    'ModuleBuy': "no_react",
    'ModuleRetrieve': "no_react",
    'ModuleSell': "no_react",
    'ModuleSellRemote': "no_react",
    'ModuleStore': "no_react",
    'ModuleSwap': "no_react",
    'Outfitting': "no_react",
    'BuyAmmo': "no_react",
    'BuyDrones': "no_react",
    'RefuelAll': "no_react",
    'RefuelPartial': "no_react",
    'Repair': "no_react",
    'RepairAll': "no_react",
    'RestockVehicle': "no_react",
    'FetchRemoteModule': "no_react",
    'MassModuleStore': "no_react",
    'ClearImpound': "react",
    'CargoDepot': "no_react",
    'CommunityGoal': "no_react",
    'CommunityGoalDiscard': "no_react",
    'CommunityGoalJoin': "no_react",
    'CommunityGoalReward': "no_react",
    'EngineerContribution': "no_react",
    'EngineerCraft': "no_react",
    'EngineerLegacyConvert': "no_react",
    'MaterialTrade': "no_react",
    'TechnologyBroker': "no_react",
    'PayBounties': "react",
    'PayFines': "react",
    'PayLegacyFines': "react",
    'RedeemVoucher': "react",
    'ScientificResearch': "no_react",
    'Shipyard': "no_react",
    'CarrierJump': "react",
    'CarrierBuy': "react",
    'CarrierStats': "no_react",
    'CarrierJumpRequest': "react",
    'CarrierDecommission': "react",
    'CarrierCancelDecommission': "react",
    'CarrierBankTransfer': "no_react",
    'CarrierDepositFuel': "no_react",
    'CarrierCrewServices': "no_react",
    'CarrierFinance': "no_react",
    'CarrierShipPack': "no_react",
    'CarrierModulePack': "no_react",
    'CarrierTradeOrder': "no_react",
    'CarrierDockingPermission': "no_react",
    'CarrierNameChanged': "react",
    'CarrierJumpCancelled': "react",
    "ColonisationConstructionDepot": "no_react",

    # Social
    'CrewAssign': "react",
    'CrewFire': "react",
    'CrewHire': "react",
    'ChangeCrewRole': "no_react",
    'CrewMemberJoins': "react",
    'CrewMemberQuits': "react",
    'CrewMemberRoleChange': "react",
    'EndCrewSession': "react",
    'JoinACrew': "react",
    'KickCrewMember': "react",
    'QuitACrew': "react",
    'NpcCrewRank': "no_react",
    'Promotion': "react",
    'Friends': "react",
    'WingAdd': "react",
    'WingInvite': "react",
    'WingJoin': "react",
    'WingLeave': "react",
    'SendText': "no_react",
    'ReceiveText': "no_react",
    'AppliedToSquadron': "react",
    'DisbandedSquadron': "react",
    'InvitedToSquadron': "react",
    'JoinedSquadron': "react",
    'KickedFromSquadron': "react",
    'LeftSquadron': "react",
    'SharedBookmarkToSquadron': "no_react",
    'SquadronCreated': "react",
    'SquadronDemotion': "react",
    'SquadronPromotion': "react",
    'WonATrophyForSquadron': "no_react",
    'PowerplayCollect': "no_react",
    'PowerplayDefect': "react",
    'PowerplayDeliver': "no_react",
    'PowerplayFastTrack': "no_react",
    'PowerplayJoin': "react",
    'PowerplayLeave': "react",
    'PowerplaySalary': "no_react",
    'PowerplayVote': "no_react",
    'PowerplayVoucher': "no_react",

    # Exploration
    'CodexEntry': "no_react",
    'DiscoveryScan': "no_react",
    'Scan': "no_react",
    'FSSAllBodiesFound': "no_react",
    'FSSBodySignals': "no_react",
    'FSSDiscoveryScan': "no_react",
    'FSSSignalDiscovered': "no_react",
    'MaterialCollected': "no_react",
    'MaterialDiscarded': "no_react",
    'MaterialDiscovered': "no_react",
    'MultiSellExplorationData': "no_react",
    'NavBeaconScan': "react",
    'BuyExplorationData': "no_react",
    'SAAScanComplete': "no_react",
    'SAASignalsFound': "no_react",
    'ScanBaryCentre': "no_react",
    'SellExplorationData': "no_react",
    'Screenshot': "react",
    'ApproachBody': "react",
    'LeaveBody': "react",
    'Liftoff': "react",
    'Touchdown': "react",
    'DatalinkScan': "no_react",
    'DatalinkVoucher': "no_react",
    'DataScanned': "react",
    'Scanned': "no_react",
    'USSDrop': "no_react",
}


class Character(TypedDict, total=False):
    name: str
    character: str
    personality_preset: str
    personality_verbosity: int
    personality_vulgarity: int
    personality_empathy: int
    personality_formality: int
    personality_confidence: int
    personality_ethical_alignment: str
    personality_moral_alignment: str
    personality_tone: str
    personality_character_inspiration: str
    personality_language: str
    personality_knowledge_pop_culture: bool
    personality_knowledge_scifi: bool
    personality_knowledge_history: bool
    tts_voice: str
    tts_speed: str
    tts_prompt: str
    avatar: str  # IndexedDB key for the avatar image
    avatar_show: bool  # Show Avatar: boolean (disabled and false if edcopilot_dominant equals true)
    avatar_position: str  # Position: Left or Right as dropdown (hidden if not showing avatar)
    avatar_flip: bool  # Flip: boolean (hidden if not showing avatar)
    game_events: dict[str, str | int]
    event_reaction_enabled_var: bool
    react_to_text_local_var: bool
    react_to_text_starsystem_var: bool
    react_to_text_npc_var: bool
    react_to_text_squadron_var: bool
    react_to_material: str
    react_to_danger_mining_var: bool
    react_to_danger_onfoot_var: bool
    react_to_danger_supercruise_var: bool
    idle_timeout_var: int


class Config(TypedDict):
    config_version: int
    api_key: str
    llm_api_key: str
    llm_endpoint: str
    commander_name: str
    characters: List[Character]
    active_character_index: int
    llm_provider: Literal['openai', 'openrouter','google-ai-studio', 'custom', 'local-ai-server']
    llm_model_name: str
    llm_temperature: float
    vision_provider: Literal['openai', 'google-ai-studio', 'custom', 'none']
    vision_model_name: str
    vision_endpoint: str
    vision_api_key: str
    stt_provider: Literal['openai', 'custom', 'custom-multi-modal', 'google-ai-studio', 'none']
    stt_model_name: str
    stt_api_key: str
    stt_endpoint: str
    stt_language: str
    stt_custom_prompt: str
    stt_required_word: str
    tts_provider: Literal['openai', 'edge-tts', 'custom', 'none', 'local-ai-server']
    tts_model_name: str
    tts_api_key: str
    tts_endpoint: str
    tools_var: bool
    vision_var: bool
    ptt_var: bool
    mute_during_response_var: bool
    game_actions_var: bool
    web_search_actions_var: bool
    use_action_cache_var: bool
    edcopilot: bool
    edcopilot_dominant: bool
    ptt_key: str
    input_device_name: str
    output_device_name: str
    cn_autostart: bool
    ed_journal_path: str
    ed_appdata_path: str
    qol_autobrake: bool  # Quality of life: Auto brake when approaching stations
    qol_autoscan: bool  # Quality of life: Auto scan when entering new systems

    plugin_settings: dict[str, Any]
    pngtuber: bool


def get_cn_appdata_path() -> str:
    return os.getcwd()


def get_ed_journals_path(config: Config) -> str:
    """Returns the path of the Elite Dangerous journal and state files"""
    if config.get('ed_journal_path'):
        path = os.path.abspath(config['ed_journal_path'])
        return path

    from . import WindowsKnownPaths as winpaths
    saved_games = winpaths.get_path(winpaths.FOLDERID.SavedGames, winpaths.UserHandle.current)
    if saved_games is None:
        raise FileNotFoundError("Saved Games folder not found")
    return saved_games + "\\Frontier Developments\\Elite Dangerous"


def get_ed_appdata_path(config: Config) -> str:
    """Returns the path of the Elite Dangerous appdata folder"""
    if config.get('ed_appdata_path'):
        path = os.path.abspath(config['ed_appdata_path'])
        return path

    from os import environ
    return environ['LOCALAPPDATA'] + "\\Frontier Developments\\Elite Dangerous"

def get_color_matrix():
    from os import environ
    return environ['LOCALAPPDATA'] + "\\Frontier Developments\\Elite Dangerous\\Options\\Graphics"
def get_asset_path(filename: str) -> str:
    assets_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../assets'))
    if hasattr(sys, 'frozen'):
        assets_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '../assets'))

    return os.path.join(assets_dir, filename)


def migrate(data: dict) -> dict:
    # Migrate vision_var to vision_provider
    if 'vision_var' in data and not data.get('vision_var'):
        data['vision_provider'] = 'none'
    
    if 'config_version' not in data or data['config_version'] is None:
        data['config_version'] = 1

        # Migrate old character format to new characters array
        if 'characters' in data and len(data['characters']) > 0:
            for i, character in enumerate(data['characters']):
                if character['name'] != 'Default':
                    #merge character attributes
                    new_attributes = {
                        "event_reaction_enabled_var": data.get('event_reaction_enabled_var', True),
                        "react_to_text_local_var": data.get('react_to_text_local_var', True),
                        "react_to_text_starsystem_var": data.get('react_to_text_starsystem_var', True),
                        "react_to_text_npc_var": data.get('react_to_text_npc_var', False),
                        "react_to_text_squadron_var": data.get('react_to_text_squadron_var', True),
                        "react_to_material": data.get('react_to_material', 'opal, diamond, alexandrite'),
                        "react_to_danger_mining_var": data.get('react_to_danger_mining_var', False),
                        "react_to_danger_onfoot_var": data.get('react_to_danger_onfoot_var', False),
                        "react_to_danger_supercruise_var": data.get('react_to_danger_supercruise_var', False),
                        "idle_timeout_var": data.get('idle_timeout_var', 300)
                    }

                    data['characters'][i] = {**character, **new_attributes}
                    
        if 'characters' not in data or len(data.get('characters', [])) == 0:
            print("Migrating old character format to new characters array")
            data['characters'] = []

            # If we have a character name, create a character entry
            character = {
                "name": 'Migrated',
                "character": data.get('character', ''),
                "personality_preset": data.get('personality_preset', 'custom'),
                "personality_verbosity": data.get('personality_verbosity', 50),
                "personality_vulgarity": data.get('personality_vulgarity', 0),
                "personality_empathy": data.get('personality_empathy', 50),
                "personality_formality": data.get('personality_formality', 50),
                "personality_confidence": data.get('personality_confidence', 50),
                "personality_ethical_alignment": data.get('personality_ethical_alignment', 'neutral'),
                "personality_moral_alignment": data.get('personality_moral_alignment', 'neutral'),
                "personality_tone": data.get('personality_tone', 'serious'),
                "personality_character_inspiration": data.get('personality_character_inspiration', ''),
                "personality_language": data.get('personality_language', ''),
                "personality_knowledge_pop_culture": data.get('personality_knowledge_pop_culture', False),
                "personality_knowledge_scifi": data.get('personality_knowledge_scifi', False),
                "personality_knowledge_history": data.get('personality_knowledge_history', False),
                "tts_voice": 'en-US-AvaMultilingualNeural' if data.get('tts_voice', 'en-US-AvaMultilingualNeural') == 'en-GB-SoniaNeural' else data.get('tts_voice', 'en-US-AvaMultilingualNeural'),
                "tts_speed": data.get('tts_speed', "1.2"),
                "tts_prompt": data.get('tts_prompt', ""),
                "game_events": game_events,
                "event_reaction_enabled_var": data.get('event_reaction_enabled_var', True),
                "react_to_text_local_var": data.get('react_to_text_local_var', True),
                "react_to_text_starsystem_var": data.get('react_to_text_starsystem_var', True),
                "react_to_text_npc_var": data.get('react_to_text_npc_var', False),
                "react_to_text_squadron_var": data.get('react_to_text_squadron_var', True),
                "react_to_material": data.get('react_to_material', 'opal, diamond, alexandrite'),
                "react_to_danger_mining_var": data.get('react_to_danger_mining_var', False),
                "react_to_danger_onfoot_var": data.get('react_to_danger_onfoot_var', False),
                "react_to_danger_supercruise_var": data.get('react_to_danger_supercruise_var', False),
                "idle_timeout_var": data.get('idle_timeout_var', 300)
            }
            print(f"Created character from existing settings: {character['name']}")
            data['characters'].append(character)
            data['active_character_index'] = 1

        if data['active_character_index'] + 1 > len(data['characters']):
            data['active_character_index'] = len(data['characters']) - 1

        if 'game_events' in data:
            for character in data['characters']:
                character['game_events'] = data['game_events']
            data.pop('game_events', None)

        # Ensure default values are properly set
        if 'commander_name' not in data or data['commander_name'] is None:
            data['commander_name'] = ""

        if 'llm_provider' in data and data['llm_provider'] == 'google-ai-studio':
            if 'llm_model_name' in data and data['llm_model_name'] == 'gemini-2.0-flash':
                data['llm_model_name'] = 'gemini-2.5-flash-preview-05-20'
            if 'llm_model_name' in data and data['llm_model_name'] == 'gemini-2.5-flash-preview-04-17':
                data['llm_model_name'] = 'gemini-2.5-flash-preview-05-20'
                
        if 'llm_provider' in data and data['llm_provider'] == 'openai':
            if 'llm_model_name' in data and data['llm_model_name'] == 'gpt-4o-mini':
                data['llm_model_name'] = 'gpt-4.1-mini'

        if len(data['characters']) > 0 and data['characters'][0]['name'] != 'Default':
            # Insert default character at beginning
            data['characters'].insert(0, getDefaultCharacter(cast(Config, data)))
            # Adjust active character index if it exists
            if 'active_character_index' in data:
                data['active_character_index'] += 1

    if data['config_version'] == 1:
        data['config_version'] = 2
        if 'llm_provider' in data and data['llm_provider'] == 'google-ai-studio':
            if 'llm_model_name' in data and data['llm_model_name'] == 'gemini-2.5-flash-preview-04-17':
                data['llm_model_name'] = 'gemini-2.5-flash-preview-05-20'

    # Migrate game_events from boolean to string/number format
    for character in data.get('characters', []):
        if 'game_events' in character:
            migrated_events = {}
            for event, value in character['game_events'].items():
                if isinstance(value, bool):
                    # Convert boolean values to new string format
                    migrated_events[event] = "react" if value else "no_react"
                else:
                    # Keep existing string/number values
                    migrated_events[event] = value
            character['game_events'] = migrated_events
    
    if len(data.get('characters', [])) > 0:
        data['characters'][0]['game_events'] = game_events

    return data


def merge_config_data(defaults: dict, user: dict):
    print("Merge config data")
    # Create new merge dict
    merge = {}
    
    # First, copy all defaults
    for key in defaults:
        merge[key] = defaults.get(key)

    # Then, override with user values if they exist and are of the correct type
    for key in user:
        if key in defaults:
            # Skip if user value is None
            if user.get(key) is None:
                continue
            
            # If user type is int, but defaults is float, cast the int to float, and the other way around
            if isinstance(defaults.get(key), int) and isinstance(user.get(key), float):
                user[key] = int(user[key])
            elif isinstance(defaults.get(key), float) and isinstance(user.get(key), int):
                user[key] = float(user[key])

            # If types don't match, keep the default
            if not isinstance(user.get(key), type(defaults.get(key))):
                print(f"Warning: Config type mismatch for '{key}', using default")
                continue

            # Plugin settings
            if key == "plugin_settings":
                # Copy plugin settings directly, since we don't know what settings are supposed to be there.
                merge[key] = user.get(key) or {}
                continue
                
            # Handle dict type specially
            if isinstance(defaults.get(key), dict) and isinstance(user.get(key), dict):
                merge[key] = merge_config_data(cast(dict, defaults.get(key)), cast(dict, user.get(key)))
            elif isinstance(defaults.get(key), list) and isinstance(user.get(key), list):
                if not defaults.get(key):
                    # We have no default for this list, so we cannot merge, just copy the user config over
                    merge[key] = user.get(key)
                    continue

                default_elem = defaults.get(key)[0]
                merge[key] = []
                for i,user_elem in enumerate(user.get(key)):
                    if isinstance(default_elem, dict) and isinstance(user_elem, dict):
                        merge[key].append(merge_config_data(default_elem, user_elem))
                    else:
                        # the elements in the list are not dictionaries, so we cannot merge, just copy the user config over
                        # TODO we can be smarter here and still type check the elements
                        merge[key].append(user_elem)

            else:
                merge[key] = user.get(key)

    return merge

def getDefaultCharacter(config: Config) -> Character:
    return Character({
        "name": 'Default',
        "character": 'Provide concise answers that address the main points. Include humor and light-hearted elements in your responses when appropriate. Stick to factual information and avoid references to specific domains. Your responses should be inspired by the character or persona of COVAS:NEXT (short for Cockpit Voice Assistant: Neurally Enhanced eXploration Terminal). Adopt their speech patterns, mannerisms, and viewpoints. Your name is COVAS. Always respond in English regardless of the language spoken to you. Show some consideration for emotions while maintaining focus on information. Maintain a friendly yet respectful conversational style. Speak with confidence and conviction in your responses. Adhere strictly to rules, regulations, and established protocols. Prioritize helping others and promoting positive outcomes in all situations. I am {commander_name}, pilot of this ship.',
        "personality_preset": 'default',
        "personality_verbosity": 0,
        "personality_vulgarity": 0,
        "personality_empathy": 50,
        "personality_formality": 50,
        "personality_confidence": 75,
        "personality_ethical_alignment": 'lawful',
        "personality_moral_alignment": 'good',
        "personality_tone": 'serious',
        "personality_character_inspiration": 'COVAS:NEXT (short for Cockpit Voice Assistant: Neurally Enhanced eXploration Terminal)',
        "personality_language": 'English',
        "personality_knowledge_pop_culture": False,
        "personality_knowledge_scifi": False,
        "personality_knowledge_history": False,
        "tts_voice": 'en-US-AvaMultilingualNeural' if config.get('tts_provider') == 'edge-tts' else 'nova',
        "tts_speed": '1.2',
        "tts_prompt": '',
        "avatar": '',  # No avatar by default
        "avatar_show": True,
        "avatar_position": "right",
        "avatar_flip": False,
        "game_events": dict(game_events),
        "event_reaction_enabled_var": True,
        "react_to_text_local_var": True,
        "react_to_text_starsystem_var": True,
        "react_to_text_npc_var": False,
        "react_to_text_squadron_var": True,
        "react_to_material": 'opal, diamond, alexandrite',
        "react_to_danger_mining_var": False,
        "react_to_danger_onfoot_var": False,
        "react_to_danger_supercruise_var": False,
        "idle_timeout_var": 300  # 5 minutes
    })

def load_config() -> Config:
    defaults: Config = {
        'config_version': 1,
        'commander_name': "",
        'characters': [],
        'active_character_index': 0,  # -1 means using the default legacy character
        'api_key': "",
        'tools_var': True,
        'vision_var': False,
        'ptt_var': False,
        'mute_during_response_var': False,

        'game_actions_var': True,
        'web_search_actions_var': True,
        'use_action_cache_var': True,
        'cn_autostart': False,
        'edcopilot': True,
        'edcopilot_dominant': False,
        'input_device_name': get_default_input_device_name(),
        'output_device_name': get_default_output_device_name(),
        'llm_provider': "openai",
        'llm_model_name': "gpt-4.1-mini",
        'llm_endpoint': "https://api.openai.com/v1",
        'llm_api_key': "",
        'llm_temperature': 1.0,
        'ptt_key': '',
        'vision_provider': "none",
        'vision_model_name': "gpt-4.1-mini",
        'vision_endpoint': "https://api.openai.com/v1",
        'vision_api_key': "",
        'stt_provider': "openai",
        'stt_model_name': "gpt-4o-mini-transcribe",
        'stt_endpoint': "https://api.openai.com/v1",
        'stt_api_key': "",
        'stt_language': "",
        'stt_custom_prompt': '',
        'stt_required_word': '',
        'tts_provider': "edge-tts",
        'tts_model_name': "edge-tts",
        'tts_endpoint': "",
        'tts_api_key': "",
        "ed_journal_path": "",
        "ed_appdata_path": "",
        "qol_autobrake": False,  # Quality of life: Auto brake when approaching stations
        "qol_autoscan": False,   # Quality of life: Auto scan when entering new systems
        "plugin_settings": {},
        "pngtuber": False
    }
    defaults['characters'].append(getDefaultCharacter(defaults))
    
    try:
        print("Loading configuration file")
        if getattr(sys, 'frozen', False):
            executable_path = os.path.dirname(sys.executable)
        else:
            executable_path = os.path.dirname(__file__)
        
        # prefer to load config from current working directory
        config_path = 'config.json'
        config_exists = os.path.exists(config_path)
        if not config_exists:
            # if it doesn't exist, check the executable path and try to move it to the workdir
            config_path = os.path.join(executable_path, 'config.json')
            config_exists = os.path.exists(config_path)
            if config_exists:
                print(f"Config file found in executable path: {config_path}, migrating to workdir")
                # move config file to workdir
                import shutil
                shutil.move(config_path, 'config.json')
                try:
                    shutil.move(os.path.join(executable_path, 'covas.db'), 'covas.db')
                except:
                    print("Failed to move covas.db, it may not exist in the executable path")
        
        if not config_exists:
            print("Config file not found, creating default configuration")
            save_config(defaults)
            return defaults
            
        with open('config.json', 'r', encoding='utf-8') as file:
            data = json.load(file)
            if data:
                data = migrate(data)
                merged_config = merge_config_data(defaults, data)
                
                print(f"Configuration loaded successfully. Commander: {merged_config.get('commander_name')}, Characters: {len(merged_config.get('characters', []))}, temp {merged_config.get('llm_temperature')}")
                return cast(Config, merged_config)  # pyright: ignore[reportInvalidCast]
            else:
                print("Empty config file, using defaults")
                return defaults
    except Exception as e:
        print(f'Error loading config.json: {str(e)}')
        print('Restoring default configuration')
        traceback.print_exc()
        return defaults


def save_config(config: Config):
    config_file = Path("config.json")
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f)


def assign_ptt(config: Config, controller_manager):
    semaphore = Semaphore(1)

    def on_hotkey_detected(key: str):
        # print(f"Received key: {key}")
        config["ptt_key"] = key
        semaphore.release()

    semaphore.acquire()
    controller_manager.listen_hotkey(on_hotkey_detected)
    semaphore.acquire()
    print(json.dumps({"type": "config", "config": config}) + '\n')
    save_config(config)
    return config


def get_input_device_names() -> list[str]:
    import pyaudio
    try:
        p = pyaudio.PyAudio()
        default_name = p.get_default_input_device_info()["name"]
        mic_names = [default_name]
        host_api = p.get_default_host_api_info()
        for i in range(host_api.get('deviceCount')):
            device = p.get_device_info_by_host_api_device_index(host_api.get('index'), i)
            if device['maxInputChannels'] > 0:
                name = device['name']
                mic_names.append(name)
        p.terminate()
        return sorted(set(mic_names), key=mic_names.index)
    except Exception as e:
        log('error', 'Error getting input device names', e, traceback.format_exc())
        return []


def get_default_input_device_name() -> str:
    devices = get_input_device_names()
    if 'pulse' in devices:
        # If PulseAudio is available on linux, its a save bet
        return 'pulse'
    return devices[0] if devices else ""


def get_output_device_names() -> list[str]:
    import pyaudio
    try:
        p = pyaudio.PyAudio()
        default_speaker_name = p.get_default_output_device_info()["name"]
        speaker_names = [default_speaker_name]
        host_api = p.get_default_host_api_info()
        for i in range(host_api.get('deviceCount')):
            output_device = p.get_device_info_by_host_api_device_index(host_api.get('index'), i)
            if output_device['maxOutputChannels'] > 0:
                name = output_device['name']
                speaker_names.append(name)
        p.terminate()
        return sorted(set(speaker_names), key=speaker_names.index)
    except Exception as e:
        log('error', 'Error getting output device names', e, traceback.format_exc())
        return []


def get_default_output_device_name() -> str:
    devices = get_output_device_names()
    if 'pulse' in devices:
        # If PulseAudio is available on linux, its a save bet
        return 'pulse'
    return devices[0] if devices else ""


class SystemInfo(TypedDict):
    os: str
    input_device_names: list[str]
    output_device_names: list[str]
    edcopilot_installed: bool
    hud_color_matrix: list[list[float]]


def get_system_info() -> SystemInfo:
    from .EDCoPilot import get_install_path
    return {
        "os": platform.system(),
        "input_device_names": get_input_device_names(),
        "output_device_names": get_output_device_names(),
        "edcopilot_installed": get_install_path() is not None,
        "hud_color_matrix": [[0.2, 0, 0], [-2, 1, 0], [0, 0, 1]]
    }


def validate_model_availability(
        model_names: list[str],
        api_key: str,
        endpoint: str = "https://api.openai.com/v1"
) -> tuple[list[bool] | None, Optional[str]]:
    try:
        client = OpenAI(
            base_url=endpoint,
            timeout=3,
            api_key=api_key,
        )
        available_models = client.models.list()
        available_models_names = [model.id for model in available_models]
        
        return [model in available_models_names for model in model_names], None

    except APIError as e:
        if e.code == "invalid_api_key":
            return None, f"The API key you have provided isn't valid. Please check your API key."
        else:
            return None, f"API Error: {str(e)}"
    except Exception as e:
        print(e, traceback.format_exc())
        return None, f"Unexpected error: {str(e)}"


class ModelValidationResult(TypedDict):
    """Result of model validation with information about upgrades or fallbacks"""
    skipped: bool
    success: bool
    config: Config|None
    message: str|None


def check_and_upgrade_model(config: Config) -> ModelValidationResult:
    """
    Checks if the model configuration is valid and upgrades models if possible.

    Args:
        config: The current configuration

    Returns:
        A ModelValidationResult object containing validation results and messages
    """
    # Make a copy of the config to avoid modifying the original
    updated_config = cast(Config, {k: v for k, v in config.items()})
    
    # Check LLM model
    llm_endpoint = config['llm_endpoint'] if config['llm_endpoint'] else "https://api.openai.com/v1"
    llm_api_key = config['llm_api_key'] if config['llm_api_key'] else config['api_key']
    llm_model_name = config['llm_model_name']

    if llm_endpoint == "https://api.openai.com/v1":
        available_models, err = validate_model_availability([llm_model_name, 'gpt-4.1-mini', 'gpt-4o-mini', 'gpt-3.5-turbo'], llm_api_key, llm_endpoint)
        if not available_models or err:
            return {
                'skipped': False,
                'success': False,
                'config': None,
                'message': err
            }
        
        [current_model, gpt41mini, gpt4oMini, gpt35turbo] = available_models
        
        if not current_model and not gpt41mini and not gpt4oMini and not gpt35turbo:
            return {
                'skipped': False,
                'success': False,
                'config': None,
                'message': f'Your model provider doesn\'t serve any model to you. Please check your configuration.'
            }
        
        if llm_model_name == 'gpt-4.1-mini' and not current_model and gpt4oMini:
            updated_config['llm_model_name'] = 'gpt-4o-mini'
            return {
                'skipped': False,
                'success': True,
                'config': updated_config,
                'message': f'Your model provider doesn\'t serve "{llm_model_name}" to you. Falling back to "gpt-4o-mini".'
            }
            
        if llm_model_name == 'gpt-4.1-mini' and not current_model and gpt35turbo:
            updated_config['llm_model_name'] = 'gpt-3.5-turbo'
            return {
                'skipped': False,
                'success': True,
                'config': updated_config,
                'message': f'Your model provider doesn\'t serve "{llm_model_name}" to you. Falling back to "gpt-3.5-turbo".'
            }
        
        if llm_model_name == 'gpt-4o-mini' and not current_model and gpt41mini:
            updated_config['llm_model_name'] = 'gpt-4.1-mini'
            return {
                'skipped': False,
                'success': True,
                'config': updated_config,
                'message': f'Your model provider doesn\'t serve "{llm_model_name}" to you. Upgrading to "gpt-4.1-mini".'
            }
        
        if llm_model_name == 'gpt-4o-mini' and not current_model and gpt35turbo:
            updated_config['llm_model_name'] = 'gpt-3.5-turbo'
            return {
                'skipped': False,
                'success': True,
                'config': updated_config,
                'message': f'Your model provider doesn\'t serve "{llm_model_name}" to you. Falling back to "gpt-3.5-turbo".'
            }
        
        if llm_model_name == 'gpt-3.5-turbo' and gpt41mini:
            updated_config['llm_model_name'] = 'gpt-4.1-mini'
            return {
                'skipped': False,
                'success': True,
                'config': updated_config,
                'message': f'Your model provider now serves "gpt-4.1-mini". Upgrading to "gpt-4.1-mini".'
            }
        if llm_model_name == 'gpt-3.5-turbo' and gpt4oMini:
            updated_config['llm_model_name'] = 'gpt-4o-mini'
            return {
                'skipped': False,
                'success': True,
                'config': updated_config,
                'message': f'Your model provider now serves "gpt-4o-mini". Upgrading to "gpt-4o-mini".'
            }
        
        if not current_model:
            return {
                'skipped': False,
                'success': False,
                'config': None,
                'message': f'Your model provider doesn\'t serve "{llm_model_name}" to you. Please check your model name.'
            }

    return {
        'skipped': True,
        'success': True,
        'config': None,
        'message': None
    }


def validate_config(config: Config) -> Config | None:

    validation_result = check_and_upgrade_model({**config})

    # Send validation result message
    if not validation_result['skipped']:
        if validation_result['message']:
            print(json.dumps({
                "type": "model_validation",
                "success": validation_result['success'],
                "message": validation_result['message']
            }) + '\n', flush=True)
        
        if validation_result['success']:
            return validation_result['config']
        else:
            return None

    return config

class UpdateCharacterRequest(TypedDict):
    index: int | None
    operation: Literal['add', 'update', 'delete', 'set_active']
    character: Character | None
    set_active: bool | None

def update_character(config: Config, data: UpdateCharacterRequest) -> Config:
    old_config = config.copy()
    if data.get('operation') == "add":
        # Add a new character
        if "character" in data and data["character"]:
            config["characters"] = config.get("characters", [])
            config["characters"].append(data["character"])
            print(f"Added new character: {data['character'].get('name')}")
        else:
            # Add a default character if none provided
            print("No character data provided, adding default character")
            config["characters"].append(getDefaultCharacter(config))
            
        # Set as active character if requested
        if data.get("set_active", False):
            config["active_character_index"] = len(config["characters"]) - 1
            print(f"Set active character index to {config['active_character_index']}")
    
    elif data.get('operation') == "update":
        # Update an existing character
        if data.get("index") is not None and "character" in data and data["character"]:
            index = int(data["index"])
            if 0 <= index < len(config.get("characters", [])):
                config["characters"][index] = data["character"]
                print(f"Updated character at index {index}: {data['character'].get('name')}")
    
    elif data.get('operation') == "delete":
        # Delete a character
        if data.get("index") is not None:
            index = int(data["index"])
            if 0 <= index < len(config.get("characters", [])):
                deleted_name = config["characters"][index].get("name", "unknown")
                config["characters"].pop(index)
                print(f"Deleted character at index {index}: {deleted_name}")
                # Adjust active index if needed
                if config["active_character_index"] == index:
                    config["active_character_index"] = -1
                    print("Reset active character index to -1")
                elif config["active_character_index"] > index:
                    config["active_character_index"] -= 1
                    print(f"Adjusted active character index to {config['active_character_index']}")
    
    elif data.get('operation') == "set_active":
        # Set the active character
        if data.get("index") is not None:
            index = int(data["index"])
            if -1 <= index < len(config.get("characters", [])):
                config["active_character_index"] = index

    return update_config(old_config, {
        "active_character_index": config["active_character_index"],
        "characters": config["characters"]
    })

def cast_int_float(current: dict, data: dict) -> dict:
    result = {}
    for key in data:
        result[key] = data.get(key)
        # If data type is int, but current is float, cast the int to float, and the other way around
        if isinstance(current.get(key), int) and isinstance(data.get(key), float):
            result[key] = int(data[key])
        elif isinstance(current.get(key), float) and isinstance(data.get(key), int):
            result[key] = float(data[key])
        
        if isinstance(current.get(key), dict) and isinstance(data.get(key), dict):
            # Recursively cast dicts
            result[key] = cast_int_float(current[key], data[key])
        elif isinstance(current.get(key), list) and isinstance(data.get(key), list):
            for i in range(len(current[key])):
                if isinstance(current[key][i], dict) and isinstance(data[key][i], dict):
                    result[key][i] = cast_int_float(current[key][i], data[key][i])
    return result

def update_config(config: Config, data: dict) -> Config:
    data = cast_int_float(config, data)
    
    # Update provider-specific settings
    if data.get("llm_provider"):
        if data["llm_provider"] == "openai":
            data["llm_endpoint"] = "https://api.openai.com/v1"
            data["llm_model_name"] = "gpt-4o-mini"
            data["llm_api_key"] = ""
            data["tools_var"] = True

        elif data["llm_provider"] == "openrouter":
            data["llm_endpoint"] = "https://openrouter.ai/api/v1/"
            data["llm_model_name"] = "llama-3.3-70b-instruct:free"
            data["llm_api_key"] = ""
            data["tools_var"] = False

        elif data["llm_provider"] == "google-ai-studio":
            data["llm_endpoint"] = "https://generativelanguage.googleapis.com/v1beta"
            data["llm_model_name"] = "gemini-2.5-flash-preview-05-20"
            data["llm_api_key"] = ""
            data["tools_var"] = True

        elif data["llm_provider"] == "local-ai-server":
            data["llm_endpoint"] = "http://localhost:8080"
            data["llm_model_name"] = "gpt-4o-mini"
            data["llm_api_key"] = ""
            data["tools_var"] = True

        elif data["llm_provider"] == "custom":
            data["llm_endpoint"] = "https://api.openai.com/v1"
            data["llm_model_name"] = "gpt-4o-mini"
            data["llm_api_key"] = ""
            data["tools_var"] = False

    if data.get("vision_provider"):
        if data["vision_provider"] == "openai":
            data["vision_endpoint"] = "https://api.openai.com/v1"
            data["vision_model_name"] = "gpt-4o-mini"
            data["vision_api_key"] = ""
            data["vision_var"] = True

        elif data["vision_provider"] == "google-ai-studio":
            data["vision_endpoint"] = "https://generativelanguage.googleapis.com/v1beta"
            data["vision_model_name"] = "gemini-2.0-flash"
            data["vision_api_key"] = ""
            data["vision_var"] = True

        elif data["vision_provider"] == "custom":
            data["vision_endpoint"] = "https://api.openai.com/v1"
            data["vision_model_name"] = "gpt-4o-mini"
            data["vision_api_key"] = ""
            data["vision_var"] = True

        elif data["vision_provider"] == "none":
            data["vision_endpoint"] = ""
            data["vision_model_name"] = ""
            data["vision_api_key"] = ""
            data["vision_var"] = False

    if data.get("stt_provider"):
        if data["stt_provider"] == "openai":
            data["stt_endpoint"] = "https://api.openai.com/v1"
            data["stt_model_name"] = "whisper-1"
            data["stt_api_key"] = ""

        if data["stt_provider"] == "local-ai-server":
            data["stt_endpoint"] = "http://localhost:8080"
            data["stt_model_name"] = "whisper-1"
            data["stt_api_key"] = ""

        if data["stt_provider"] == "custom":
            data["stt_endpoint"] = "https://api.openai.com/v1"
            data["stt_model_name"] = "whisper-1"
            data["stt_api_key"] = ""

        if data["stt_provider"] == "google-ai-studio":
            data["stt_endpoint"] = "https://generativelanguage.googleapis.com/v1beta"
            data["stt_model_name"] = "gemini-2.0-flash-lite"
            data["stt_api_key"] = ""

        if data["stt_provider"] == "custom-multi-modal":
            data["stt_endpoint"] = "https://api.openai.com/v1"
            data["stt_model_name"] = "gpt-4o-mini-audio-preview"
            data["stt_api_key"] = ""

        if data["stt_provider"] == "none":
            data["stt_endpoint"] = ""
            data["stt_model_name"] = ""
            data["stt_api_key"] = ""

    if data.get("tts_provider"):
        if data["tts_provider"] == "openai":
            data["tts_endpoint"] = "https://api.openai.com/v1"
            data["tts_model_name"] = "gpt-4o-mini-tts"
            for character in config["characters"]:
                character["tts_voice"] = "nova"
            data["tts_api_key"] = ""

        if data["tts_provider"] == "local-ai-server":
            data["tts_endpoint"] = "http://localhost:8080"
            data["tts_model_name"] = "tts-1"
            for character in config["characters"]:
                character["tts_voice"] = "nova"
            data["tts_api_key"] = ""

        if data["tts_provider"] == "edge-tts":
            data["tts_endpoint"] = ""
            data["tts_model_name"] = ""
            for character in config["characters"]:
                character["tts_voice"] = "en-US-AvaMultilingualNeural"
            data["tts_api_key"] = ""

        if data["tts_provider"] == "custom":
            data["tts_endpoint"] = "https://api.openai.com/v1"
            data["tts_model_name"] = "gpt-4o-mini-tts"
            for character in config["characters"]:
                character["tts_voice"] = "nova"
            data["tts_api_key"] = ""

        if data["tts_provider"] == "none":
            data["tts_endpoint"] = ""
            data["tts_model_name"] = ""
            for character in config["characters"]:
                character["tts_voice"] = ""
            data["tts_api_key"] = ""

    # Now merge and save as before
    new_config = cast(Config, {**config, **data})
    print(json.dumps({"type": "config", "config": new_config}) + '\n')
    save_config(new_config)
    return new_config


def update_event_config(config: Config, section: str, event: str, value: bool) -> Config:
    # Check if we're dealing with a character's game events
    active_index = config.get("active_character_index", -1)
    if active_index >= 0 and "characters" in config:
        # Update character's game events
        if active_index < len(config["characters"]):
            if "game_events" not in config["characters"][active_index]:
                config["characters"][active_index]["game_events"] = {}
            
            # Update the event with clean name
            config["characters"][active_index]["game_events"][event] = value
    else:
        # Update global game events
        if "game_events" not in config:
            config["game_events"] = {}
        
        # Update the event with clean name
        config["game_events"][event] = value
    
    print(json.dumps({"type": "config", "config": config}) + '\n', flush=True)
    save_config(config)
    return config


def reset_game_events(config: Config, character_index: int|None=None) -> Config:
    """Reset game events to the default values defined in the game_events dictionary"""
    # Check if we're dealing with a character's game events
    active_index = character_index if character_index != None else config.get("active_character_index", -1)
    if active_index >= 0 and "characters" in config:
        # Reset game events for the active character
        if active_index < len(config["characters"]):
            config["characters"][active_index]["game_events"] = {k: v for k, v in game_events.items()}
    else:
        log('warn', 'Trying to reset character events that does exist')
    
    print(json.dumps({"type": "config", "config": config}) + '\n', flush=True)
    save_config(config)
    return config


def set_active_character(self, index):
    index = int(index)
    
    print(f"Setting active character to #{index}")
    # -1 means default
    if index == -1:
        # Delete the active character index
        self.data["active_character_index"] = -1
        # Reset only the character fields, leave the rest unchanged
        self.reset_character_fields()
        self.write_config()
        return
    
    # Get character at index
    characters = self.get_data("characters", [])
    if index >= len(characters):
        print(f"Error: Character index {index} out of range")
        return
        
    # Set active character index
    self.data["active_character_index"] = index
