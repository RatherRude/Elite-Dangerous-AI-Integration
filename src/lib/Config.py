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
    'OutofDanger': True,
    'InDanger': True,
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
    llm_custom: dict[str, str]
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
    qol_autobrak: bool  # Quality of life: Auto brake when approaching stations
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
    if 'Exploration' in events:
        enabled_events = {}
        for section in events.keys():
            for name,value in events[section].items():
                enabled_events[name] = value
        data['game_events'] = enabled_events
        
    # Migrate vision_var to vision_provider
    if 'vision_var' in data and not data.get('vision_var'):
        data['vision_provider'] = 'none'
    
    # Migrate old character format to new characters array
    if 'characters' not in data:
        print("Migrating old character format to new characters array")
        data['characters'] = []
        data['active_character_index'] = -1
        
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
        data['active_character_index'] = 0

        data.pop('character', None)
        data.pop('personality_preset', None)
        data.pop('personality_verbosity', None)
        data.pop('personality_vulgarity', None)
        data.pop('personality_empathy', None)
        data.pop('personality_formality', None)
        data.pop('personality_confidence', None)
        data.pop('personality_ethical_alignment', None)
        data.pop('personality_moral_alignment', None)
        data.pop('personality_tone', None)
        data.pop('personality_character_inspiration', None)
        data.pop('personality_language', None)
        data.pop('personality_name', None)
        data.pop('personality_knowledge_pop_culture', None)
        data.pop('personality_knowledge_scifi', None)
        data.pop('personality_knowledge_history', None)

    # Ensure default values are properly set
    if 'commander_name' not in data or data['commander_name'] is None:
        data['commander_name'] = ""
    
    if 'personality_name' not in data or data['personality_name'] is None:
        data['personality_name'] = 'COVAS:NEXT'
    
    if 'config_version' not in data or data['config_version'] is None:
        data['config_version'] = 1
        
        if 'llm_provider' in data and data['llm_provider'] == 'google-ai-studio':
            if 'llm_model_name' in data and data['llm_model_name'] == 'gemini-2.0-flash':
                data['llm_model_name'] = 'gemini-2.5-flash-preview-04-17'
                
        if 'llm_provider' in data and data['llm_provider'] == 'openai':
            if 'llm_model_name' in data and data['llm_model_name'] == 'gpt-4o-mini':
                data['llm_model_name'] = 'gpt-4.1-mini'
        
    return data


def merge_config_data(defaults: dict, user: dict):
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
        else:
            # Copy unknown keys from user config
            merge[key] = user.get(key)
            
    return merge


def load_config() -> Config:
    defaults: Config = {
        'config_version': 1,
        'commander_name': "",
        'character': "Keep your responses extremely brief and minimal. Maintain a professional and serious tone in all responses. Stick to factual information and avoid references to specific domains. Your responses should be inspired by the character or persona of COVAS:NEXT (short for Cockpit Voice Assistant: Neurally Enhanced eXploration Terminal). Adopt their speech patterns, mannerisms, and viewpoints. Your name is COVAS:NEXT. Show some consideration for emotions while maintaining focus on information. Maintain a friendly yet respectful conversational style. Project an air of expertise and certainty when providing information. Adhere strictly to rules, regulations, and established protocols. Prioritize helping others and promoting positive outcomes in all situations. I am {commander_name}, pilot of this ship.",
        'personality_preset': 'default',
        'personality_verbosity': 0,
        'personality_vulgarity': 0,
        'personality_empathy': 50,
        'personality_formality': 50,
        'personality_confidence': 75,
        'personality_ethical_alignment': 'lawful',
        'personality_moral_alignment': 'good',
        'personality_tone': 'serious',
        'personality_character_inspiration': 'COVAS:NEXT (short for Cockpit Voice Assistant: Neurally Enhanced eXploration Terminal)',
        'personality_language': '',
        'personality_name': 'COVAS:NEXT',
        'personality_knowledge_pop_culture': False,
        'personality_knowledge_scifi': False,
        'personality_knowledge_history': False,
        'characters': [],
        'active_character_index': -1,  # -1 means using the default legacy character
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
        'llm_custom': {},
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
        'tts_voice': "en-US-AvaMultilingualNeural",
        'tts_speed': "1.2",
        'tts_prompt': "",
        'game_events': game_events,
        'react_to_text_local_var': True,
        'react_to_text_npc_var': False,
        'react_to_text_squadron_var': True,
        'react_to_text_starsystem_var': True,
        'react_to_material': 'opal, diamond, alexandrite',
        'react_to_danger_mining_var': False,
        'react_to_danger_onfoot_var': False,
        'react_to_danger_supercruise_var': False,
        "ed_journal_path": "",
        "ed_appdata_path": "",
        "qol_autobrak": False,  # Quality of life: Auto brake when approaching stations
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
    if data.get("character_operation"):
        print(f"Processing character operation: {data['character_operation']}")
        operation = data["character_operation"]
        
        if operation == "add":
            # Add a new character
            if data.get("character_data"):
                config["characters"] = config.get("characters", [])
                config["characters"].append(data["character_data"])
                print(f"Added new character: {data['character_data'].get('name')}")
                # Set as active character if requested
                if data.get("set_active", False):
                    config["active_character_index"] = len(config["characters"]) - 1
                    print(f"Set active character index to {config['active_character_index']}")
        
        elif operation == "update":
            # Update an existing character
            if data.get("character_index") is not None and data.get("character_data"):
                index = int(data["character_index"])
                if 0 <= index < len(config.get("characters", [])):
                    config["characters"][index] = data["character_data"]
                    print(f"Updated character at index {index}: {data['character_data'].get('name')}")
        
        elif operation == "delete":
            # Delete a character
            if data.get("character_index") is not None:
                index = int(data["character_index"])
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
            if data.get("character_index") is not None:
                index = int(data["character_index"])
                if -1 <= index < len(config.get("characters", [])):
                    config["active_character_index"] = index
                    print(f"Set active character index to {index}")
                    
                    # Copy character properties to top-level config
                    if index >= 0:
                        character_data = config["characters"][index]
                        # Apply all character fields
                        config["character"] = character_data.get("character", "")
                        print(f"Setting active character preset to: {character_data.get('personality_preset', 'unknown')}")
                        config["personality_preset"] = character_data.get("personality_preset", "custom")
                        config["personality_verbosity"] = character_data.get("personality_verbosity", 50)
                        config["personality_vulgarity"] = character_data.get("personality_vulgarity", 0)
                        config["personality_empathy"] = character_data.get("personality_empathy", 50)
                        config["personality_formality"] = character_data.get("personality_formality", 50)
                        config["personality_confidence"] = character_data.get("personality_confidence", 50)
                        config["personality_ethical_alignment"] = character_data.get("personality_ethical_alignment", "neutral")
                        config["personality_moral_alignment"] = character_data.get("personality_moral_alignment", "neutral")
                        config["personality_tone"] = character_data.get("personality_tone", "serious")
                        config["personality_character_inspiration"] = character_data.get("personality_character_inspiration", "")
                        config["personality_language"] = character_data.get("personality_language", "English")
                        config["personality_knowledge_pop_culture"] = character_data.get("personality_knowledge_pop_culture", False)
                        config["personality_knowledge_scifi"] = character_data.get("personality_knowledge_scifi", False)
                        config["personality_knowledge_history"] = character_data.get("personality_knowledge_history", False)
                        
                        # Also apply TTS voice if present
                        if "tts_voice" in character_data:
                            config["tts_voice"] = character_data.get("tts_voice", "")
                            
                        # Apply TTS speed if present
                        if "tts_speed" in character_data:
                            config["tts_speed"] = character_data.get("tts_speed", "1.2")
                            
                        # Apply TTS prompt if present
                        if "tts_prompt" in character_data:
                            config["tts_prompt"] = character_data.get("tts_prompt", "")
                            
                        # Write the config to disk
                        save_config(config)

    # Update provider-specific settings
    if data.get("llm_provider"):
      if data["llm_provider"] == "openai":
        data["llm_endpoint"] = "https://api.openai.com/v1"
        data["llm_model_name"] = "gpt-4.1-mini"
        data["llm_api_key"] = ""
        data["tools_var"] = True

      elif data["llm_provider"] == "openrouter":
        data["llm_endpoint"] = "https://openrouter.ai/api/v1/"
        data["llm_model_name"] = "meta-llama/llama-3.3-70b-instruct:free"
        data["llm_api_key"] = ""
        data["tools_var"] = False

      elif data["llm_provider"] == "google-ai-studio":
        data["llm_endpoint"] = "https://generativelanguage.googleapis.com/v1beta"
        data["llm_model_name"] = "gemini-2.5-flash-preview-04-17"
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
        data["vision_model_name"] = "gpt-4.1-mini"
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
        data["stt_model_name"] = "gpt-4o-mini-transcribe"
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
        data["tts_voice"] = "nova"
        data["tts_api_key"] = ""

      if data["tts_provider"] == "local-ai-server":
        data["tts_endpoint"] = "http://localhost:8080"
        data["tts_model_name"] = "tts-1"
        data["tts_voice"] = "nova"
        data["tts_api_key"] = ""
        
      if data["tts_provider"] == "edge-tts":
        data["tts_endpoint"] = ""
        data["tts_model_name"] = ""
        data["tts_voice"] = "en-US-AvaMultilingualNeural"
        data["tts_api_key"] = ""

      if data["tts_provider"] == "custom":
        data["tts_endpoint"] = "https://api.openai.com/v1"
        data["tts_model_name"] = "gpt-4o-mini-tts"
        data["tts_voice"] = "nova"
        data["tts_api_key"] = ""

      if data["tts_provider"] == "none":
        data["tts_endpoint"] = ""
        data["tts_model_name"] = ""
        data["tts_voice"] = ""
        data["tts_api_key"] = ""
    
    # Regular config updates
    new_config = cast(Config, {**config, **data}) # pyright: ignore[reportInvalidCast]
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
        
    # Load character data into main settings
    try:
        character_data = characters[index]
        # Apply all character fields
        self.update_data("character", character_data.get("character", ""))
        self.update_data("personality_preset", character_data.get("personality_preset", "default"))
        self.update_data("personality_verbosity", character_data.get("personality_verbosity", 50))
        self.update_data("personality_vulgarity", character_data.get("personality_vulgarity", 0))
        self.update_data("personality_empathy", character_data.get("personality_empathy", 50))
        self.update_data("personality_formality", character_data.get("personality_formality", 50))
        self.update_data("personality_confidence", character_data.get("personality_confidence", 50))
        self.update_data("personality_ethical_alignment", character_data.get("personality_ethical_alignment", "neutral"))
        self.update_data("personality_moral_alignment", character_data.get("personality_moral_alignment", "neutral"))
        self.update_data("personality_tone", character_data.get("personality_tone", "serious"))
        self.update_data("personality_character_inspiration", character_data.get("personality_character_inspiration", ""))
        self.update_data("personality_name", character_data.get("name", ""))
        self.update_data("personality_language", character_data.get("personality_language", "English"))
        self.update_data("personality_knowledge_pop_culture", character_data.get("personality_knowledge_pop_culture", False))
        self.update_data("personality_knowledge_scifi", character_data.get("personality_knowledge_scifi", False))
        self.update_data("personality_knowledge_history", character_data.get("personality_knowledge_history", False))
        
        # Also apply TTS voice if present
        if "tts_voice" in character_data:
            self.update_data("tts_voice", character_data.get("tts_voice", ""))
            
        # Apply TTS speed if present
        if "tts_speed" in character_data:
            self.update_data("tts_speed", character_data.get("tts_speed", "1.2"))
            
        # Apply TTS prompt if present
        if "tts_prompt" in character_data:
            self.update_data("tts_prompt", character_data.get("tts_prompt", ""))
            
        # Write the config to disk
        self.write_config()
        
        # Notify listeners
        #self.emit_config_change({"active_character_index": index})
            
    except Exception as e:
        print(f"Error setting active character: {str(e)}")
        return