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
    # 'Cargo': False,
    # 'ClearSavedGame': False,
    'LoadGame': True,
    'Shutdown': True,
    'NewCommander': True,
    # 'Materials': False,
    'Missions': True,
    # 'Progress': False,
    # 'Powerplay': False,
    # 'Rank': False,
    # 'Reputation': False,
    'Statistics': False,
    # 'SquadronStartup': False
    # 'EngineerProgress': False,

    # Combat
    'Died': True,
    'Resurrect': True,
    'WeaponSelected': False,
    'InDanger': False,
    'OutofDanger': False,
    'CombatEntered': True,
    'CombatExited': True,
    'LegalStateChanged': True,
    'CommitCrime': False,
    'Bounty': False,
    'CapShipBond': False,
    'Interdiction': False,
    'Interdicted': False,
    'EscapeInterdiction': False,
    'FactionKillBond': False,
    'FighterDestroyed': True,
    'HeatDamage': True,
    'HeatWarning': False,
    'HullDamage': False,
    'PVPKill': True,
    'ShieldState': True,
    'ShipTargetted': False,
    'UnderAttack': False,
    'CockpitBreached': True,
    'CrimeVictim': True,
    'SystemsShutdown': True,
    'SelfDestruct': True,

    # Trading
    'Trade': False,
    'BuyTradeData': False,
    'CollectCargo': False,
    'EjectCargo': True,
    'MarketBuy': False,
    'MarketSell': False,
    'CargoTransfer': False,
    'Market': False,

    # Mining
    'AsteroidCracked': False,
    'MiningRefined': False,
    'ProspectedAsteroid': True,
    'LaunchDrone': False,

    # Ship Updates
    'FSDJump': False,
    'FSDTarget': False,
    'StartJump': False,
    'FsdCharging': True,
    'SupercruiseEntry': True,
    'SupercruiseExit': True,
    'ApproachSettlement': True,
    'Docked': True,
    'Undocked': True,
    'DockingCanceled': False,
    'DockingDenied': True,
    'DockingGranted': False,
    'DockingRequested': False,
    'DockingTimeout': True,
    'NavRoute': False,
    'NavRouteClear': False,
    'CrewLaunchFighter': True,
    'VehicleSwitch': False,
    'LaunchFighter': True,
    'DockFighter': True,
    'FighterRebuilt': True,
    'FuelScoop': False,
    'RebootRepair': True,
    'RepairDrone': False,
    'AfmuRepairs': False,
    'ModuleInfo': False,
    'Synthesis': False,
    'JetConeBoost': False,
    'JetConeDamage': False,
    'LandingGearUp': False,
    'LandingGearDown': False,
    'FlightAssistOn': False,
    'FlightAssistOff': False,
    'HardpointsRetracted': False,
    'HardpointsDeployed': False,
    'LightsOff': False,
    'LightsOn': False,
    'CargoScoopRetracted': False,
    'CargoScoopDeployed': False,
    'SilentRunningOff': False,
    'SilentRunningOn': False,
    'FuelScoopStarted': False,
    'FuelScoopEnded': False,
    'FsdMassLockEscaped': False,
    'FsdMassLocked': False,
    'LowFuelWarningCleared': True,
    'LowFuelWarning': True,
    'NoScoopableStars': True,
    'NightVisionOff': False,
    'NightVisionOn': False,
    'SupercruiseDestinationDrop': False,

    # SRV Updates
    'LaunchSRV': True,
    'DockSRV': True,
    'SRVDestroyed': True,
    'SrvHandbrakeOff': False,
    'SrvHandbrakeOn': False,
    'SrvTurretViewConnected': False,
    'SrvTurretViewDisconnected': False,
    'SrvDriveAssistOff': False,
    'SrvDriveAssistOn': False,

    # On-Foot Updates
    'Disembark': True,
    'Embark': True,
    'BookDropship': True,
    'BookTaxi': True,
    'CancelDropship': True,
    'CancelTaxi': True,
    'CollectItems': False,
    'DropItems': False,
    'BackpackChange': False,
    'BuyMicroResources': False,
    'SellMicroResources': False,
    'TransferMicroResources': False,
    'TradeMicroResources': False,
    'BuySuit': True,
    'BuyWeapon': True,
    'SellWeapon': False,
    'UpgradeSuit': False,
    'UpgradeWeapon': False,
    'CreateSuitLoadout': True,
    'DeleteSuitLoadout': False,
    'RenameSuitLoadout': True,
    'SwitchSuitLoadout': True,
    'UseConsumable': False,
    'FCMaterials': False,
    'LoadoutEquipModule': False,
    'LoadoutRemoveModule': False,
    'ScanOrganic': True,
    'SellOrganicData': True,
    'LowOxygenWarningCleared': True,
    'LowOxygenWarning': True,
    'LowHealthWarningCleared': True,
    'LowHealthWarning': True,
    'BreathableAtmosphereExited': False,
    'BreathableAtmosphereEntered': False,
    'GlideModeExited': False,
    'GlideModeEntered': False,
    'DropShipDeploy': False,

    # Stations
    'MissionAbandoned': True,
    'MissionAccepted': True,
    'MissionCompleted': True,
    'MissionFailed': True,
    'MissionRedirected': True,
    'StationServices': False,
    'ShipyardBuy': True,
    'ShipyardNew': False,
    'ShipyardSell': False,
    'ShipyardTransfer': False,
    'ShipyardSwap': False,
    'StoredShips': False,
    'ModuleBuy': False,
    'ModuleRetrieve': False,
    'ModuleSell': False,
    'ModuleSellRemote': False,
    'ModuleStore': False,
    'ModuleSwap': False,
    'Outfitting': False,
    'BuyAmmo': False,
    'BuyDrones': False,
    'RefuelAll': False,
    'RefuelPartial': False,
    'Repair': False,
    'RepairAll': False,
    'RestockVehicle': False,
    'FetchRemoteModule': False,
    'MassModuleStore': False,
    'ClearImpound': True,
    'CargoDepot': False,
    'CommunityGoal': False,
    'CommunityGoalDiscard': False,
    'CommunityGoalJoin': False,
    'CommunityGoalReward': False,
    'EngineerContribution': False,
    'EngineerCraft': False,
    'EngineerLegacyConvert': False,
    'MaterialTrade': False,
    'TechnologyBroker': False,
    'PayBounties': True,
    'PayFines': True,
    'PayLegacyFines': True,
    'RedeemVoucher': True,
    'ScientificResearch': False,
    'Shipyard': False,
    'CarrierJump': True,
    'CarrierBuy': True,
    'CarrierStats': False,
    'CarrierJumpRequest': True,
    'CarrierDecommission': True,
    'CarrierCancelDecommission': True,
    'CarrierBankTransfer': False,
    'CarrierDepositFuel': False,
    'CarrierCrewServices': False,
    'CarrierFinance': False,
    'CarrierShipPack': False,
    'CarrierModulePack': False,
    'CarrierTradeOrder': False,
    'CarrierDockingPermission': False,
    'CarrierNameChanged': True,
    'CarrierJumpCancelled': True,
    "ColonisationConstructionDepot": False,

    # Social
    'CrewAssign': True,
    'CrewFire': True,
    'CrewHire': True,
    'ChangeCrewRole': False,
    'CrewMemberJoins': True,
    'CrewMemberQuits': True,
    'CrewMemberRoleChange': True,
    'EndCrewSession': True,
    'JoinACrew': True,
    'KickCrewMember': True,
    'QuitACrew': True,
    'NpcCrewRank': False,
    'Promotion': True,
    'Friends': True,
    'WingAdd': True,
    'WingInvite': True,
    'WingJoin': True,
    'WingLeave': True,
    'SendText': False,
    'ReceiveText': False,
    'AppliedToSquadron': True,
    'DisbandedSquadron': True,
    'InvitedToSquadron': True,
    'JoinedSquadron': True,
    'KickedFromSquadron': True,
    'LeftSquadron': True,
    'SharedBookmarkToSquadron': False,
    'SquadronCreated': True,
    'SquadronDemotion': True,
    'SquadronPromotion': True,
    'WonATrophyForSquadron': False,
    'PowerplayCollect': False,
    'PowerplayDefect': True,
    'PowerplayDeliver': False,
    'PowerplayFastTrack': False,
    'PowerplayJoin': True,
    'PowerplayLeave': True,
    'PowerplaySalary': False,
    'PowerplayVote': False,
    'PowerplayVoucher': False,

    # Exploration
    'CodexEntry': False,
    'DiscoveryScan': False,
    'Scan': False,
    'FSSAllBodiesFound': False,
    'FSSBodySignals': False,
    'FSSDiscoveryScan': False,
    'FSSSignalDiscovered': False,
    'MaterialCollected': False,
    'MaterialDiscarded': False,
    'MaterialDiscovered': False,
    'MultiSellExplorationData': False,
    'NavBeaconScan': True,
    'BuyExplorationData': False,
    'SAAScanComplete': False,
    'SAASignalsFound': False,
    'ScanBaryCentre': False,
    'SellExplorationData': False,
    'Screenshot': True,
    'ApproachBody': True,
    'LeaveBody': True,
    'Liftoff': True,
    'Touchdown': True,
    'DatalinkScan': False,
    'DatalinkVoucher': False,
    'DataScanned': True,
    'Scanned': False,
    'USSDrop': False,
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
    game_events: dict[str, bool]
    event_reaction_enabled_var: bool
    react_to_text_local_var: bool
    react_to_text_starsystem_var: bool
    react_to_text_npc_var: bool
    react_to_text_squadron_var: bool
    react_to_material: str
    react_to_danger_mining_var: bool
    react_to_danger_onfoot_var: bool
    react_to_danger_supercruise_var: bool


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
    vision_provider: Literal['openai', 'google-ai-studio', 'custom', 'none']
    vision_model_name: str
    vision_endpoint: str
    vision_api_key: str
    stt_provider: Literal['openai', 'custom', 'custom-multi-modal', 'google-ai-studio', 'none']
    stt_model_name: str
    stt_api_key: str
    stt_endpoint: str
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
    continue_conversation_var: bool
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


def get_asset_path(filename: str) -> str:
    assets_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../assets'))
    if hasattr(sys, 'frozen'):
        assets_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '../assets'))

    return os.path.join(assets_dir, filename)


def migrate(data: dict) -> dict:
    events = data.get('game_events', {})

    
    if 'config_version' not in data or data['config_version'] is None:

        data['config_version'] = 1

        if 'Exploration' in events:
            enabled_events = {}
            for section in events.keys():
                for name, value in events[section].items():
                    enabled_events[name] = value
            data['game_events'] = enabled_events

        # Migrate vision_var to vision_provider
        if 'vision_var' in data and not data.get('vision_var'):
            data['vision_provider'] = 'none'

        # Migrate old character format to new characters array
        if 'characters' not in data:
            print("Migrating old character format to new characters array")
            data['characters'] = []

            # Add default character before migrated character
            data['characters'].append({
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
                "tts_voice": 'en-US-AvaMultilingualNeural',
                "tts_speed": '1.2',
                "tts_prompt": '',
                "game_events": game_events,
                "event_reaction_enabled_var": True,
                "react_to_text_local_var": True,
                "react_to_text_starsystem_var": True,
                "react_to_text_npc_var": False,
                "react_to_text_squadron_var": True,
                "react_to_material": 'opal, diamond, alexandrite',
                "react_to_danger_mining_var": False,
                "react_to_danger_onfoot_var": False,
                "react_to_danger_supercruise_var": False
            })

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
                "tts_voice": data.get('tts_voice', 'en-US-AvaMultilingualNeural'),
                "tts_speed": data.get('tts_speed', "1.2"),
                "tts_prompt": data.get('tts_prompt', ""),
                "game_events": game_events,
                "event_reaction_enabled_var": True,
                "react_to_text_local_var": True,
                "react_to_text_starsystem_var": True,
                "react_to_text_npc_var": False,
                "react_to_text_squadron_var": True,
                "react_to_material": 'opal, diamond, alexandrite',
                "react_to_danger_mining_var": False,
                "react_to_danger_onfoot_var": False,
                "react_to_danger_supercruise_var": False
            }
            print(f"Created character from existing settings: {character['name']}")
            data['characters'].append(character)
            data['active_character_index'] = 1
        else:
            if len(data['characters']) > 0:
                # Check if first character is not the default
                if data['characters'][0]['name'] != 'Default':
                    # Insert default character at beginning
                    data['characters'].insert(0, {
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
                        "tts_voice": 'en-US-AvaMultilingualNeural',
                        "tts_speed": '1.2',
                        "tts_prompt": '',
                        "game_events": game_events,
                        "event_reaction_enabled_var": True,
                        "react_to_text_local_var": True,
                        "react_to_text_starsystem_var": True,
                        "react_to_text_npc_var": False,
                        "react_to_text_squadron_var": True,
                        "react_to_material": 'opal, diamond, alexandrite',
                        "react_to_danger_mining_var": False,
                        "react_to_danger_onfoot_var": False,
                        "react_to_danger_supercruise_var": False
                    })
                    # Adjust active character index if it exists
                    if 'active_character_index' in data:
                        data['active_character_index'] += 1

        if 'game_events' in data:
            for character in data['characters']:
                character['game_events'] = data['game_events']
            data.pop('game_events', None)

        # Ensure default values are properly set
        if 'commander_name' not in data or data['commander_name'] is None:
            data['commander_name'] = ""

        if 'llm_provider' in data and data['llm_provider'] == 'google-ai-studio':
            if 'llm_model_name' in data and data['llm_model_name'] == 'gemini-2.0-flash':
                data['llm_model_name'] = 'gemini-2.5-flash-preview-04-17'
                
        if 'llm_provider' in data and data['llm_provider'] == 'openai':
            if 'llm_model_name' in data and data['llm_model_name'] == 'gpt-4o-mini':
                data['llm_model_name'] = 'gpt-4.1-mini'
        
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
                
            # If types don't match, keep the default
            if not isinstance(user.get(key), type(defaults.get(key))):
                print(f"Warning: Config type mismatch for '{key}', using default")
                continue
                
            # Handle dict type specially
            if isinstance(defaults.get(key), dict) and isinstance(user.get(key), dict):
                merge[key] = merge_config_data(defaults.get(key), user.get(key))
            # Skip list type (not supported in merge)
            elif isinstance(defaults.get(key), list):
                # Just copy the user list directly
                merge[key] = user.get(key)
            else:
                merge[key] = user.get(key)

    return merge


def load_config() -> Config:
    defaults: Config = {
        'config_version': 1,
        'commander_name': "",
        'characters': [
            {
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
                "tts_voice": 'en-US-AvaMultilingualNeural',
                "tts_speed": '1.2',
                "tts_prompt": '',
                "game_events": game_events,
                "event_reaction_enabled_var": True,
                "react_to_text_local_var": True,
                "react_to_text_starsystem_var": True,
                "react_to_text_npc_var": False,
                "react_to_text_squadron_var": True,
                "react_to_material": 'opal, diamond, alexandrite',
                "react_to_danger_mining_var": False,
                "react_to_danger_onfoot_var": False,
                "react_to_danger_supercruise_var": False
            }
        ],
        'active_character_index': 0,  # -1 means using the default legacy character
        'api_key': "",
        'tools_var': True,
        'vision_var': False,
        'ptt_var': False,
        'mute_during_response_var': False,
        'continue_conversation_var': True,
        'event_reaction_enabled_var': True,
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
        'ptt_key': '',
        'vision_provider': "none",
        'vision_model_name': "gpt-4.1-mini",
        'vision_endpoint': "https://api.openai.com/v1",
        'vision_api_key': "",
        'stt_provider': "openai",
        'stt_model_name': "gpt-4o-mini-transcribe",
        'stt_endpoint': "https://api.openai.com/v1",
        'stt_api_key': "",
        'stt_custom_prompt': '',
        'stt_required_word': '',
        'tts_provider': "edge-tts",
        'tts_model_name': "edge-tts",
        'tts_endpoint': "",
        'tts_api_key': "",
        "ed_journal_path": "",
        "ed_appdata_path": "",
        "qol_autobrake": False,  # Quality of life: Auto brake when approaching stations
        "qol_autoscan": False   # Quality of life: Auto scan when entering new systems
    }
    try:
        print("Loading configuration file")
        config_exists = os.path.exists('config.json')
        
        if not config_exists:
            print("Config file not found, creating default configuration")
            save_config(defaults)
            return defaults
            
        with open('config.json', 'r', encoding='utf-8') as file:
            data = json.load(file)
            if data:
                data = migrate(data)
                merged_config = merge_config_data(defaults, data)
                print(f"Configuration loaded successfully. Commander: {merged_config.get('commander_name')}, Characters: {len(merged_config.get('characters', []))}")
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
    return devices[0] if devices else ""


class SystemInfo(TypedDict):
    os: str
    input_device_names: list[str]
    output_device_names: list[str]
    edcopilot_installed: bool


def get_system_info() -> SystemInfo:
    from .EDCoPilot import EDCoPilot
    edcopilot: Any = EDCoPilot(False)  # this is only for the GUI, the actual EDCoPilot client is created in the Chat
    return {
        "os": platform.system(),
        "input_device_names": get_input_device_names(),
        "output_device_names": get_output_device_names(),
        "edcopilot_installed": edcopilot.is_installed(),
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


def update_config(config: Config, data: dict) -> Config:
    # Check if we need to reset game events
    if data.get("reset_game_events", False):
        config = reset_game_events(config)
        # Remove the reset_game_events flag from data to avoid confusion
        if "reset_game_events" in data:
            del data["reset_game_events"]
    
    # Handle character management operations
    if data.get("operation"):
        print(f"Processing character operation: {data['operation']}")
        operation = data["operation"]
        
        if operation == "add":
            # Add a new character
            if data.get("character"):
                config["characters"] = config.get("characters", [])
                config["characters"].append(data["character"])
                print(f"Added new character: {data['character'].get('name')}")
                # Set as active character if requested
                if data.get("set_active", False):
                    config["active_character_index"] = len(config["characters"]) - 1
                    print(f"Set active character index to {config['active_character_index']}")
        
        elif operation == "update":
            # Update an existing character
            if data.get("index") is not None and data.get("character"):
                index = int(data["index"])
                if 0 <= index < len(config.get("characters", [])):
                    config["characters"][index] = data["character"]
                    print(f"Updated character at index {index}: {data['character'].get('name')}")
        
        elif operation == "delete":
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
        
        elif operation == "set_active":
            # Set the active character
            if data.get("index") is not None:
                index = int(data["index"])
                if -1 <= index < len(config.get("characters", [])):
                    config["active_character_index"] = index

                    # Write the config to disk
                    save_config(config)

    # Remove temporary operation fields so they are NOT persisted
    for key in ["operation", "index", "character", "set_active"]:
        if key in data:
            data.pop(key)
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


def reset_game_events(config: Config) -> Config:
    """Reset game events to the default values defined in the game_events dictionary"""
    # Check if we're dealing with a character's game events
    active_index = config.get("active_character_index", -1)
    if active_index >= 0 and "characters" in config:
        # Reset game events for the active character
        if active_index < len(config["characters"]):
            config["characters"][active_index]["game_events"] = {k: v for k, v in game_events.items()}
    else:
        # Reset global game events
        config["game_events"] = {k: v for k, v in game_events.items()}
    
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
