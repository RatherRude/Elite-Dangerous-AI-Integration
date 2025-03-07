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

# List of game events categorized
game_events = {
    'Startup Events': {
        # 'Cargo': False,
        # 'ClearSavedGame': False,
        'LoadGame': True,
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
    },
    'Combat Events': {
        'Died': True,
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
        'SRVDestroyed': True,
        'UnderAttack': False
    },
    'Travel Events': {
        'CodexEntry': False,
        'ApproachBody': True,
        'Docked': True,
        'DockingCanceled': False,
        'DockingDenied': True,
        'DockingGranted': False,
        'DockingRequested': False,
        'DockingTimeout': True,
        'FSDJump': True,
        'FSDTarget': False,
        'LeaveBody': True,
        'Liftoff': True,
        'StartJump': False,
        'SupercruiseEntry': True,
        'SupercruiseExit': True,
        'Touchdown': True,
        'Undocked': True,
        'NavRoute': False,
        'NavRouteClear': False
    },
    'Exploration Events': {
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
        'Screenshot': False
    },
    'Trade Events': {
        'Trade': False,
        'AsteroidCracked': False,
        'BuyTradeData': False,
        'CollectCargo': False,
        'EjectCargo': True,
        'MarketBuy': False,
        'MarketSell': False,
        'MiningRefined': False
    },
    'Station Services Events': {
        'StationServices': False,
        'BuyAmmo': False,
        'BuyDrones': False,
        'CargoDepot': False,
        'CommunityGoal': False,
        'CommunityGoalDiscard': False,
        'CommunityGoalJoin': False,
        'CommunityGoalReward': False,
        'CrewAssign': True,
        'CrewFire': True,
        'CrewHire': True,
        'EngineerContribution': False,
        'EngineerCraft': False,
        'EngineerLegacyConvert': False,
        'FetchRemoteModule': False,
        'Market': False,
        'MassModuleStore': False,
        'MaterialTrade': False,
        'MissionAbandoned': True,
        'MissionAccepted': True,
        'MissionCompleted': True,
        'MissionFailed': True,
        'MissionRedirected': True,
        'ModuleBuy': False,
        'ModuleRetrieve': False,
        'ModuleSell': False,
        'ModuleSellRemote': False,
        'ModuleStore': False,
        'ModuleSwap': False,
        'Outfitting': False,
        'PayBounties': True,
        'PayFines': True,
        'PayLegacyFines': True,
        'RedeemVoucher': True,
        'RefuelAll': False,
        'RefuelPartial': False,
        'Repair': False,
        'RepairAll': False,
        'RestockVehicle': False,
        'ScientificResearch': False,
        'Shipyard': False,
        'ShipyardBuy': True,
        'ShipyardNew': False,
        'ShipyardSell': False,
        'ShipyardTransfer': False,
        'ShipyardSwap': False,
        # 'StoredModules': False,
        'StoredShips': False,
        'TechnologyBroker': False,
        'ClearImpound': True
    },
    'Powerplay Events': {
        'PowerplayCollect': False,
        'PowerplayDefect': True,
        'PowerplayDeliver': False,
        'PowerplayFastTrack': False,
        'PowerplayJoin': True,
        'PowerplayLeave': True,
        'PowerplaySalary': False,
        'PowerplayVote': False,
        'PowerplayVoucher': False
    },
    'Squadron Events': {
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
        'WonATrophyForSquadron': False
    },
    'Fleet Carrier Events': {
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
        'CarrierJumpCancelled': True
    },
    'Odyssey Events': {
        # 'Backpack': False,
        'BackpackChange': False,
        'BookDropship': True,
        'BookTaxi': True,
        'BuyMicroResources': False,
        'BuySuit': True,
        'BuyWeapon': True,
        'CancelDropship': True,
        'CancelTaxi': True,
        'CollectItems': False,
        'CreateSuitLoadout': True,
        'DeleteSuitLoadout': False,
        'Disembark': True,
        'DropItems': False,
        'DropShipDeploy': False,
        'Embark': True,
        'FCMaterials': False,
        'LoadoutEquipModule': False,
        'LoadoutRemoveModule': False,
        'RenameSuitLoadout': True,
        'ScanOrganic': False,
        'SellMicroResources': False,
        'SellOrganicData': True,
        'SellWeapon': False,
        # 'ShipLocker': False,
        'SwitchSuitLoadout': True,
        'TransferMicroResources': False,
        'TradeMicroResources': False,
        'UpgradeSuit': False,
        'UpgradeWeapon': False,
        'UseConsumable': False
    },
    'Other Events': {
        'AfmuRepairs': False,
        'ApproachSettlement': True,
        'ChangeCrewRole': False,
        'CockpitBreached': True,
        'CommitCrime': False,
        'Continued': False,
        'CrewLaunchFighter': True,
        'CrewMemberJoins': True,
        'CrewMemberQuits': True,
        'CrewMemberRoleChange': True,
        'CrimeVictim': True,
        'DatalinkScan': False,
        'DatalinkVoucher': False,
        'DataScanned': True,
        'DockFighter': True,
        'DockSRV': True,
        'EndCrewSession': True,
        'FighterRebuilt': True,
        'FuelScoop': False,
        'Friends': True,
        'JetConeBoost': False,
        'JetConeDamage': False,
        'JoinACrew': True,
        'KickCrewMember': True,
        'LaunchDrone': False,
        'LaunchFighter': True,
        'LaunchSRV': True,
        'ModuleInfo': False,
        # 'Music': False,
        # 'NpcCrewPaidWage': False,
        'NpcCrewRank': False,
        'Promotion': True,
        'ProspectedAsteroid': True,
        'QuitACrew': True,
        'RebootRepair': True,
        'ReceiveText': False,
        'RepairDrone': False,
        # 'ReservoirReplenished': False,
        'Resurrect': True,
        'Scanned': False,
        'SelfDestruct': True,
        'SendText': False,
        'Shutdown': True,
        'Synthesis': False,
        'SystemsShutdown': True,
        'USSDrop': False,
        'VehicleSwitch': False,
        'WingAdd': True,
        'WingInvite': True,
        'WingJoin': True,
        'WingLeave': True,
        'CargoTransfer': False,
        'SupercruiseDestinationDrop': False
    },
    'Status Events': {
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
        'SrvHandbrakeOff': False,
        'SrvHandbrakeOn': False,
        'SrvTurretViewConnected': False,
        'SrvTurretViewDisconnected': False,
        'SrvDriveAssistOff': False,
        'SrvDriveAssistOn': False,
        'FsdMassLockEscaped': False,
        'FsdMassLocked': False,
        'LowFuelWarningCleared': True,
        'LowFuelWarning': True,
        'OutofDanger': True,
        'InDanger': True,
        'NightVisionOff': False,
        'NightVisionOn': False,
        'LowOxygenWarningCleared': True,
        'LowOxygenWarning': True,
        'LowHealthWarningCleared': True,
        'LowHealthWarning': True,
        'GlideModeExited': False,
        'GlideModeEntered': False,
        'BreathableAtmosphereExited': False,
        'BreathableAtmosphereEntered': False,
        'LegalStateChanged': True,
        'WeaponSelected': False,
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
    game_events: dict[str, dict[str, bool]]
    ed_journal_path: str
    ed_appdata_path: str


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
        available_models, err = validate_model_availability([llm_model_name, 'gpt-4o-mini', 'gpt-3.5-turbo'], llm_api_key, llm_endpoint)
        if not available_models or err:
            return {
                'skipped': False,
                'success': False,
                'config': None,
                'message': err
            }
        
        [current_model, main_model, fallback_model] = available_models
        
        if not current_model and not main_model and not fallback_model:
            return {
                'skipped': False,
                'success': False,
                'config': None,
                'message': f'Your model provider doesn\'t serve any model to you. Please check your model name.'
            }
        
        if llm_model_name == 'gpt-4o-mini' and not main_model and fallback_model:
            updated_config['llm_model_name'] = 'gpt-3.5-turbo'
            return {
                'skipped': False,
                'success': True,
                'config': updated_config,
                'message': f'Your model provider doesn\'t serve "{llm_model_name}" to you. Falling back to "gpt-3.5-turbo".'
            }
        
        if llm_model_name == 'gpt-3.5-turbo' and main_model:
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
    new_config = cast(Config, {**config, **data}) # pyright: ignore[reportInvalidCast]
    save_config(new_config)
    return new_config


def update_event_config(config: Config, section: str, event: str, value: bool) -> Config:
    config.get("game_events", {}).get(section, {})[event] = value
    print(json.dumps({"type": "config", "config": config}) + '\n', flush=True)
    save_config(config)
    return config