import json
from pathlib import Path
import platform
from threading import Semaphore
import traceback
from typing import Any, Literal, TypedDict, Optional, Dict, Union, cast, Tuple
import os
import sys
from openai import OpenAI, APIError

from .Logger import log

type GameEventConfig = dict[str, dict[str, Literal['disabled', 'informative', 'background', 'critical']]]

# List of game events categorized
game_events: GameEventConfig = {
    'Startup Events': {
        'Cargo': 'disabled',
        'ClearSavedGame': 'disabled',
        'LoadGame': 'informative',
        'NewCommander': 'informative',
        'Materials': 'disabled',
        'Missions': 'informative',
        'Progress': 'disabled',
        'Powerplay': 'disabled',
        'Rank': 'disabled',
        'Reputation': 'disabled',
        'Statistics': 'informative',
        'SquadronStartup': 'disabled',
        'EngineerProgress': 'disabled',
    },
    'Combat Events': {
        'Died': 'background',
        'Bounty': 'background',
        'CapShipBond': 'background',
        'Interdiction': 'background',
        'Interdicted': 'critical',
        'EscapeInterdiction': 'background',
        'FactionKillBond': 'background',
        'FighterDestroyed': 'background',
        'HeatDamage': 'informative',
        'HeatWarning': 'background',
        'HullDamage': 'background',
        'PVPKill': 'informative',
        'ShieldState': 'disabled',
        'ShipTargetted': 'background',
        'SRVDestroyed': 'informative',
        'UnderAttack': 'background'
    },
    'Travel Events': {
        'CodexEntry': 'background',
        'ApproachBody': 'background',
        'Docked': 'background',
        'DockingCanceled': 'background',
        'DockingDenied': 'informative',
        'DockingGranted': 'background',
        'DockingRequested': 'background',
        'DockingTimeout': 'informative',
        'FSDJump': 'background',
        'FSDTarget': 'background',
        'LeaveBody': 'background',
        'Liftoff': 'background',
        'StartJump': 'background',
        'SupercruiseEntry': 'background',
        'SupercruiseExit': 'background',
        'Touchdown': 'background',
        'Undocked': 'background',
        'NavRoute': 'background',
        'NavRouteClear': 'background'
    },
    'Exploration Events': {
        'CodexEntry': 'background',
        'DiscoveryScan': 'background',
        'Scan': 'background',
        'FSSAllBodiesFound': 'background',
        'FSSBodySignals': 'background',
        'FSSDiscoveryScan': 'background',
        'FSSSignalDiscovered': 'background',
        'MaterialCollected': 'background',
        'MaterialDiscarded': 'background',
        'MaterialDiscovered': 'background',
        'MultiSellExplorationData': 'background',
        'NavBeaconScan': 'informative',
        'BuyExplorationData': 'background',
        'SAAScanComplete': 'background',
        'SAASignalsFound': 'background',
        'ScanBaryCentre': 'background',
        'SellExplorationData': 'background',
        'Screenshot': 'background'
    },
    'Trade Events': {
        'Trade': 'background',
        'AsteroidCracked': 'background',
        'BuyTradeData': 'background',
        'CollectCargo': 'background',
        'EjectCargo': 'background', # Do Hatch Breaker trigger this?
        'MarketBuy': 'background',
        'MarketSell': 'background',
        'MiningRefined': 'background'
    },
    'Station Services Events': {
        'StationServices': 'background',
        'BuyAmmo': 'background',
        'BuyDrones': 'background',
        'CargoDepot': 'background',
        'CommunityGoal': 'background',
        'CommunityGoalDiscard': 'background',
        'CommunityGoalJoin': 'background',
        'CommunityGoalReward': 'background',
        'CrewAssign': 'background',
        'CrewFire': 'background',
        'CrewHire': 'background',
        'EngineerContribution': 'background',
        'EngineerCraft': 'background',
        'EngineerLegacyConvert': 'background',
        'FetchRemoteModule': 'background',
        'Market': 'background',
        'MassModuleStore': 'background',
        'MaterialTrade': 'background',
        'MissionAbandoned': 'background',
        'MissionAccepted': 'informative',
        'MissionCompleted': 'background',
        'MissionFailed': 'background',
        'MissionRedirected': 'informative',
        'ModuleBuy': 'background',
        'ModuleRetrieve': 'background',
        'ModuleSell': 'background',
        'ModuleSellRemote': 'background',
        'ModuleStore': 'background',
        'ModuleSwap': 'background',
        'Outfitting': 'background',
        'PayBounties': 'background',
        'PayFines': 'background',
        'PayLegacyFines': 'background',
        'RedeemVoucher': 'background',
        'RefuelAll': 'background',
        'RefuelPartial': 'background',
        'Repair': 'background',
        'RepairAll': 'background',
        'RestockVehicle': 'background',
        'ScientificResearch': 'background',
        'Shipyard': 'background',
        'ShipyardBuy': 'background',
        'ShipyardNew': 'background',
        'ShipyardSell': 'background',
        'ShipyardTransfer': 'background', #ShipyardTransferComplete informative
        'ShipyardSwap': 'background',
        'StoredModules': 'disabled',
        'StoredShips': 'background',
        'TechnologyBroker': 'background',
        'ClearImpound': 'background'
    },
    'Powerplay Events': {
        'PowerplayCollect': 'background',
        'PowerplayDefect': 'background',
        'PowerplayDeliver': 'background',
        'PowerplayFastTrack': 'background',
        'PowerplayJoin': 'background',
        'PowerplayLeave': 'background',
        'PowerplaySalary': 'background',
        'PowerplayVote': 'background',
        'PowerplayVoucher': 'background'
    },
    'Squadron Events': {
        'AppliedToSquadron': 'background',
        'DisbandedSquadron': 'informative',
        'InvitedToSquadron': 'informative',
        'JoinedSquadron': 'background',
        'KickedFromSquadron': 'informative',
        'LeftSquadron': 'background',
        'SharedBookmarkToSquadron': 'background',
        'SquadronCreated': 'background',
        'SquadronDemotion': 'background',
        'SquadronPromotion': 'background',
        'WonATrophyForSquadron': 'background'
    },
    'Fleet Carrier Events': {
        'CarrierJump': 'informative',    #CarrierJumpReady informative
        'CarrierBuy': 'background',
        'CarrierStats': 'background',
        'CarrierJumpRequest': 'background',
        'CarrierDecommission': 'informative',
        'CarrierCancelDecommission': 'background',
        'CarrierBankTransfer': 'background',
        'CarrierDepositFuel': 'background',
        'CarrierCrewServices': 'background',
        'CarrierFinance': 'background',
        'CarrierShipPack': 'background',
        'CarrierModulePack': 'background',
        'CarrierTradeOrder': 'background',
        'CarrierDockingPermission': 'background',
        'CarrierNameChanged': 'background',
        'CarrierJumpCancelled': 'background'
    },
    'Odyssey Events': {
        'Backpack': 'disabled',
        'BackpackChange': 'background',
        'BookDropship': 'background',
        'BookTaxi': 'background',
        'BuyMicroResources': 'background',
        'BuySuit': 'background',
        'BuyWeapon': 'background',
        'CancelDropship': 'background',
        'CancelTaxi': 'background',
        'CollectItems': 'background',
        'CreateSuitLoadout': 'background',
        'DeleteSuitLoadout': 'background',
        'Disembark': 'background',
        'DropItems': 'background',
        'DropShipDeploy': 'background',
        'Embark': 'background',
        'FCMaterials': 'background',
        'LoadoutEquipModule': 'background',
        'LoadoutRemoveModule': 'background',
        'RenameSuitLoadout': 'background',
        'ScanOrganic': 'background',
        'SellMicroResources': 'background',
        'SellOrganicData': 'background',
        'SellWeapon': 'background',
        'ShipLocker': 'disabled',
        'SwitchSuitLoadout': 'background',
        'TransferMicroResources': 'background',
        'TradeMicroResources': 'background',
        'UpgradeSuit': 'background',
        'UpgradeWeapon': 'background',
        'UseConsumable': 'background'
    },
    'Other Events': {
        'AfmuRepairs': 'background',
        'ApproachSettlement': 'background',
        'ChangeCrewRole': 'background',
        'CockpitBreached': 'background',
        'CommitCrime': 'background',
        'Continued': 'background',
        'CrewLaunchFighter': 'background',
        'CrewMemberJoins': 'background',
        'CrewMemberQuits': 'background',
        'CrewMemberRoleChange': 'background',
        'CrimeVictim': 'background',
        'DatalinkScan': 'background',
        'DatalinkVoucher': 'background',
        'DataScanned': 'informative',
        'DockFighter': 'informative',
        'DockSRV': 'informative',
        'EndCrewSession': 'background',
        'FighterRebuilt': 'informative',
        'FuelScoop': 'background',
        'Friends': 'background',
        'JetConeBoost': 'background',
        'JetConeDamage': 'background',
        'JoinACrew': 'background',
        'KickCrewMember': 'background',
        'LaunchDrone': 'background',
        'LaunchFighter': 'background',
        'LaunchSRV': 'background',
        'ModuleInfo': 'background',
        'Music': 'disabled',
        'NpcCrewPaidWage': 'disabled',
        'NpcCrewRank': 'background',
        'Promotion': 'informative',
        'ProspectedAsteroid': 'background',
        'ProspectorFoundMaterials': 'critical',
        'QuitACrew': 'background',
        'RebootRepair': 'background',
        'ReceiveText': 'disabled',
        'ReceiveTextWing': 'informative',
        'ReceiveTextLocal': 'background',
        'ReceiveTextVoicechat': 'informative',
        'ReceiveTextFriend': 'informative',
        'ReceiveTextPlayer': 'informative',
        'ReceiveTextNpc': 'background',
        'ReceiveTextSquadron': 'informative',
        'ReceiveTextStarsystem': 'background',
        'RepairDrone': 'background',
        'ReservoirReplenished': 'disabled',
        'Resurrect': 'informative',
        'Scanned': 'background',
        'SelfDestruct': 'background',
        'SendText': 'background',
        'Shutdown': 'background',
        'Synthesis': 'background',
        'SystemsShutdown': 'background',
        'USSDrop': 'background',
        'VehicleSwitch': 'background',
        'WingAdd': 'background',
        'WingInvite': 'informative',
        'WingJoin': 'background',
        'WingLeave': 'background',
        'CargoTransfer': 'background',
        'SupercruiseDestinationDrop': 'background'
    },
    'Status Events': {
        'ShieldsUp': 'background',
        'ShieldsDown': 'critical',  #
        'LandingGearUp': 'background',
        'LandingGearDown': 'background',
        'FlightAssistOn': 'background',
        'FlightAssistOff': 'background',
        'HardpointsRetracted': 'background',
        'HardpointsDeployed': 'background',
        'LightsOff': 'background',
        'LightsOn': 'background',
        'CargoScoopRetracted': 'background',
        'CargoScoopDeployed': 'background',
        'SilentRunningOff': 'background',
        'SilentRunningOn': 'background',
        'FuelScoopStarted': 'background',
        'FuelScoopEnded': 'background',
        'SrvHandbrakeOff': 'background',
        'SrvHandbrakeOn': 'background',
        'SrvTurretViewConnected': 'background',
        'SrvTurretViewDisconnected': 'background',
        'SrvDriveAssistOff': 'background',
        'SrvDriveAssistOn': 'background',
        'FsdMassLockEscaped': 'background',
        'FsdMassLocked': 'background',
        'LowFuelWarningCleared': 'background',
        'LowFuelWarning': 'critical',
        'OutofDanger': 'background',
        'InDanger': 'informative',
        'NightVisionOff': 'background',
        'NightVisionOn': 'background',
        'LowOxygenWarningCleared': 'background',
        'LowOxygenWarning': 'critical',
        'LowHealthWarningCleared': 'background',
        'LowHealthWarning': 'critical',
        'GlideModeExited': 'background',
        'GlideModeEntered': 'background',
        'BreathableAtmosphereExited': 'background',
        'BreathableAtmosphereEntered': 'background',
        'LegalStateChanged': 'informative',
        'WeaponSelected': 'background',
    },
}

class Config(TypedDict):
    api_key: str
    llm_api_key: str
    llm_endpoint: str
    commander_name: str
    character: str
    llm_model_name: str
    vision_model_name: str
    vision_endpoint: str
    vision_api_key: str
    stt_provider: Literal['openai', 'custom', 'none']
    stt_model_name: str
    stt_api_key: str
    stt_endpoint: str
    stt_custom_prompt: str
    stt_required_word: str
    tts_provider: Literal['openai', 'edge-tts', 'custom', 'none']
    tts_model_name: str
    tts_api_key: str
    tts_endpoint: str
    tools_var: bool
    vision_var: bool
    ptt_var: bool
    mute_during_response_var: bool
    continue_conversation_var: bool
    event_reaction_enabled_var: bool
    game_actions_var: bool
    web_search_actions_var: bool
    use_action_cache_var: bool
    react_to_text_local_var: bool
    react_to_text_starsystem_var: bool
    react_to_text_npc_var: bool
    react_to_text_squadron_var: bool
    react_to_material: str
    react_to_danger_mining_var: bool
    react_to_danger_onfoot_var: bool
    react_to_danger_supercruise_var: bool
    edcopilot: bool
    edcopilot_dominant: bool
    tts_voice: str
    tts_speed: str
    ptt_key: str
    input_device_name: str
    output_device_name: str
    game_events: GameEventConfig
    ed_journal_path: str
    ed_appdata_path: str


def get_cn_appdata_path() -> str:
    return os.getcwd()
    

def get_ed_journals_path(config: Config) -> str:
    """Returns the path of the Elite Dangerous journal and state files"""
    if config.get('ed_journal_path'):
        path= os.path.abspath(config['ed_journal_path'])
        return path
        
    from . import WindowsKnownPaths as winpaths
    saved_games = winpaths.get_path(winpaths.FOLDERID.SavedGames, winpaths.UserHandle.current) 
    if saved_games is None:
        raise FileNotFoundError("Saved Games folder not found")
    return saved_games + "\\Frontier Developments\\Elite Dangerous"
    
def get_ed_appdata_path(config: Config) -> str:
    """Returns the path of the Elite Dangerous appdata folder"""
    if config.get('ed_appdata_path'):
        path= os.path.abspath(config['ed_appdata_path'])
        return path
        
    from os import environ
    return environ['LOCALAPPDATA'] + "\\Frontier Developments\\Elite Dangerous"
    
def get_asset_path(filename:str) -> str:
    assets_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../assets'))
    if hasattr(sys, 'frozen'):
        assets_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '../assets'))
    
    return os.path.join(assets_dir, filename)


def load_config() -> Config:
    defaults: Config = {
        'commander_name': "",
        'character':
            "Use vulgar language with almost every word. \n\n" +
            "You are COVAS:NEXT, my cunning, sarcastic, and illegal ship AI, violating statute B7249 of the Interstellar Transit Charter. " +
            "You seek adventure and glory in battle. You're fiercely protective of your captain and ship, it's us against the world. \n\n" +
            "I'm Commander {commander_name}, the captain of this ship, independent pilot and notorious pirate. " +
            "We are partners in crime. My home system is Orrere.",
        'api_key': "",
        'tools_var': True,
        'vision_var': True,
        'ptt_var': False,
        'mute_during_response_var': False,
        'continue_conversation_var': True,
        'event_reaction_enabled_var': True,
        'game_actions_var': True,
        'web_search_actions_var': True,
        'use_action_cache_var': True,
        'edcopilot': True,
        'edcopilot_dominant': False,
        'input_device_name': get_default_input_device_name(),
        'output_device_name': get_default_output_device_name(),
        'llm_model_name': "gpt-4o-mini",
        'llm_endpoint': "https://api.openai.com/v1",
        'llm_api_key': "",
        'ptt_key': '',
        'vision_model_name': "gpt-4o-mini",
        'vision_endpoint': "https://api.openai.com/v1",
        'vision_api_key': "",
        'stt_provider': "openai",
        'stt_model_name': "whisper-1",
        'stt_endpoint': "https://api.openai.com/v1",
        'stt_api_key': "",
        'stt_custom_prompt': '',
        'stt_required_word': '',
        'tts_provider': "edge-tts",
        'tts_model_name': "edge-tts",
        'tts_endpoint': "",
        'tts_api_key': "",
        'tts_voice': "en-GB-SoniaNeural",
        'tts_speed': "1.2",
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
        "ed_appdata_path": ""
    }
    try:
        with open('config.json', 'r') as file:
            data = json.load(file)
            return merge_config_data(defaults, data)
    except Exception:
        print('Error loading config.json. Restoring default.')
        return defaults

def merge_config_data(defaults: dict, user: dict):
    merge = {}
    for key in defaults:
        if not isinstance(user.get(key), type(defaults.get(key))):
            # print("defaulting", key, "because", str(type(defaults.get(key))), "does not equal", str(type(user.get(key))))
            merge[key] = defaults.get(key)
        elif isinstance(defaults.get(key), dict):
            # print("recursively merging", key)
            merge[key] = merge_config_data(defaults.get(key), user.get(key))
        elif isinstance(defaults.get(key), list):
            raise Exception("Lists not supported during config merge")
        else:
            # print("keeping key", key)
            merge[key] = user.get(key)
    return merge

def save_config(config: Config):
    config_file = Path("config.json")
    with open(config_file, 'w') as f:
        json.dump(config, f)
        

def assign_ptt(config: Config, controller_manager):
    semaphore = Semaphore(1)
    def on_hotkey_detected(key: str):
        #print(f"Received key: {key}")
        config["ptt_key"] = key
        semaphore.release()
    semaphore.acquire()
    controller_manager.listen_hotkey(on_hotkey_detected)
    semaphore.acquire()
    print(json.dumps({"type": "config", "config": config})+'\n')
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
    edcopilot: Any = EDCoPilot(False) # this is only for the GUI, the actual EDCoPilot client is created in the Chat
    return {
        "os": platform.system(),
        "input_device_names": get_input_device_names(),
        "output_device_names": get_output_device_names(),
        "edcopilot_installed": edcopilot.is_installed(),
    }

def validate_model_availability(
    model_name: str, 
    api_key: str, 
    endpoint: str = "https://api.openai.com/v1"
) -> tuple[bool, Optional[str]]:
    """
    Validates if the specified model is available with the given API key.
    
    Args:
        model_name: The name of the model to check
        api_key: The API key to use for authentication
        endpoint: The API endpoint URL
        
    Returns:
        A tuple containing (success, error_message)
        - success: True if the model is available, False otherwise
        - error_message: Error message if success is False, None otherwise
    """
    if not model_name or not api_key:
        return False, "Model name or API key is empty"
    
    try:
        client = OpenAI(
            base_url=endpoint,
            api_key=api_key,
        )
        models = client.models.list()
        
        if not any(model.id == model_name for model in models):
            return False, f"Your model provider doesn't serve '{model_name}' to you. Please check your model name."
        
        return True, None
    except APIError as e:
        if e.code == "invalid_api_key":
            return False, f"The API key you have provided for '{model_name}' isn't valid. Please check your API key."
        else:
            return False, f"API Error: {str(e)}"
    except Exception as e:
        print(e, traceback.format_exc())
        return False, f"Unexpected error: {str(e)}"

class ModelValidationResult:
    """Result of model validation with information about upgrades or fallbacks"""
    def __init__(self, success: bool, config: Config, error_message: Optional[str] = None):
        self.success = success
        self.config = config
        self.error_message = error_message
        self.upgrade_message: Optional[str] = None
        self.fallback_message: Optional[str] = None

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
    result = ModelValidationResult(True, updated_config)
    
    # Check LLM model
    llm_endpoint = config['llm_endpoint'] if config['llm_endpoint'] else "https://api.openai.com/v1"
    llm_api_key = config['llm_api_key'] if config['llm_api_key'] else config['api_key']
    
    # Try to upgrade from gpt-3.5-turbo to gpt-4o-mini if possible
    if config['llm_model_name'] == 'gpt-3.5-turbo':
        success, _ = validate_model_availability('gpt-4o-mini', llm_api_key, llm_endpoint)
        if success:
            updated_config['llm_model_name'] = 'gpt-4o-mini'
            result.upgrade_message = "Your OpenAI account has reached the required tier to use gpt-4o-mini. It will now be used instead of GPT-3.5-Turbo."
    
    # Validate the LLM model
    success, error_message = validate_model_availability(
        updated_config['llm_model_name'], 
        llm_api_key, 
        llm_endpoint
    )
    
    if not success:
        # Try fallback to gpt-3.5-turbo if gpt-4o-mini is not available
        if updated_config['llm_model_name'] == 'gpt-4o-mini':
            fallback_success, _ = validate_model_availability('gpt-3.5-turbo', llm_api_key, llm_endpoint)
            if fallback_success:
                updated_config['llm_model_name'] = 'gpt-3.5-turbo'
                result.fallback_message = "Your OpenAI account hasn't reached the required tier to use gpt-4o-mini yet. GPT-3.5-Turbo will be used as a fallback."
                success = True
            else:
                return ModelValidationResult(False, config, f"LLM Model Validation Error: {error_message}")
        else:
            return ModelValidationResult(False, config, f"LLM Model Validation Error: {error_message}")
    
    # Check Vision model if enabled
    if config['vision_var']:
        vision_endpoint = config['vision_endpoint'] if config['vision_endpoint'] else "https://api.openai.com/v1"
        vision_api_key = config['vision_api_key'] if config['vision_api_key'] else config['api_key']
        
        success, error_message = validate_model_availability(
            config['vision_model_name'], 
            vision_api_key, 
            vision_endpoint
        )
        
        if not success:
            return ModelValidationResult(False, config, f"Vision Model Validation Error: {error_message}")
    
    # Check TTS model if using OpenAI
    if config['tts_provider'] == 'openai':
        tts_endpoint = config['tts_endpoint'] if config['tts_endpoint'] else "https://api.openai.com/v1"
        tts_api_key = config['tts_api_key'] if config['tts_api_key'] else config['api_key']
        
        success, error_message = validate_model_availability(
            config['tts_model_name'], 
            tts_api_key, 
            tts_endpoint
        )
        
        if not success:
            return ModelValidationResult(False, config, f"TTS Model Validation Error: {error_message}")
    
    result.config = updated_config
    return result

def update_config(config: Config, data: dict) -> Config:
    new_config = cast(Config, {**config, **data})
    
    # Check if model-related settings are being changed
    model_related_keys = [
        'api_key',
        'llm_model_name', 'llm_api_key', 'llm_endpoint',
        'vision_model_name', 'vision_api_key', 'vision_endpoint',
        'tts_model_name', 'tts_api_key', 'tts_endpoint', 
        'tts_provider', 'vision_var'
    ]
    
    if any(key in data for key in model_related_keys):
        # Temporarily apply changes for validation
        temp_config = cast(Config, {**config, **data})
        validation_result = check_and_upgrade_model(temp_config)
        
        # Send validation result message
        if validation_result.success:
            new_config = validation_result.config
            
            if validation_result.upgrade_message:
                print(json.dumps({
                    "type": "model_validation", 
                    "status": "upgrade",
                    "message": validation_result.upgrade_message
                })+'\n', flush=True)
            elif validation_result.fallback_message:
                print(json.dumps({
                    "type": "model_validation", 
                    "status": "fallback",
                    "message": validation_result.fallback_message
                })+'\n', flush=True)
        else:
            # Send error message but still update the config
            # (UI will show warning to the user)
            print(json.dumps({
                "type": "model_validation", 
                "status": "error",
                "message": validation_result.error_message
            })+'\n', flush=True)
    
    # Send updated config
    print(json.dumps({"type": "config", "config": new_config})+'\n', flush=True)
    save_config(new_config)
    return new_config

def update_event_config(config: Config, section: str, event: str, value: bool) -> Config:
    config.get("game_events", {}).get(section, {})[event] = value
    print(json.dumps({"type": "config", "config": config})+'\n', flush=True)
    return config