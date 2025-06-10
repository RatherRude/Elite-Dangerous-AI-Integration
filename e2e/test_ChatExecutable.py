import json
import platform
import shutil
import tempfile

default_config = {
    "commander_name": "lucaelin",
    'character':
        "I am Commander {commander_name}, an independent pilot and notorious pirate. My home system is Catucandit. \n\n" +
        "You are COVAS:NEXT, my cunning and sarcastic ship AI. " +
        "You're fiercely protective of your captain and ship, but you're not afraid to tell your captain " +
        "when they're being an idiot-in the most colorful way possible. \n\n" +
        "Professionally reply within one sentence, never ask questions and don't engage in smalltalk.",
    'api_key': "sk-DEADBEEF",
    'tools_var': True,
    'vision_var': True,
    'ptt_var': True,
    'ptt_tap_to_talk_var': False,
    'ptt_inverted_var': False,
    'continue_conversation_var': True,
    'event_reaction_enabled_var': True,
    'game_actions_var': True,
    'web_search_actions_var': True,
    'edcopilot': True,
    'edcopilot_dominant': False,
    'input_device_name': 'default',
    'output_device_name': 'default',
    'llm_model_name': "gpt-4o-mini",
    'llm_endpoint': "https://api.openai.com/v1",
    'llm_api_key': "",
    'ptt_key': '+',
    'mute_during_response_var': False,
    'vision_model_name': "gpt-4o-mini",
    'vision_endpoint': "https://api.openai.com/v1",
    'vision_api_key': "",
    'stt_provider': "openai",
    'stt_model_name': "whisper-1",
    'stt_endpoint': "https://api.openai.com/v1",
    'stt_api_key': "",
    'stt_custom_prompt': "",
    'stt_required_word': "",
    'tts_provider': "edge-tts",
    'tts_model_name': "edge-tts",
    'tts_endpoint': "",
    'tts_api_key': "",
    'tts_voice': "en-US-AvaMultilingualNeural",
    'tts_speed': "1.2",
    'react_to_text_local_var': True,
    'react_to_text_npc_var': False,
    'react_to_text_squadron_var': True,
    'react_to_text_starsystem_var': True,
    'react_to_material': 'opal, diamond, alexandrite',
    'react_to_danger_mining_var': False,
    'react_to_danger_onfoot_var': False,
    "game_events": {
        "Startup Events": {
            "LoadGame": True,
            "NewCommander": True,
            "Missions": True,
            "Statistics": False
        },
        "Combat Events": {
            "Died": True,
            "Bounty": False,
            "CapShipBond": False,
            "Interdiction": False,
            "Interdicted": False,
            "EscapeInterdiction": False,
            "FactionKillBond": False,
            "FighterDestroyed": True,
            "HeatDamage": True,
            "HeatWarning": False,
            "HullDamage": False,
            "PVPKill": True,
            "ShieldState": True,
            "ShipTargetted": False,
            "SRVDestroyed": True,
            "UnderAttack": False
        },
        "Travel Events": {
            "CodexEntry": False,
            "ApproachBody": True,
            "Docked": True,
            "DockingCanceled": False,
            "DockingDenied": True,
            "DockingGranted": False,
            "DockingRequested": False,
            "DockingTimeout": True,
            "FSDJump": False,
            "FSDTarget": False,
            "LeaveBody": True,
            "Liftoff": True,
            "StartJump": False,
            "SupercruiseEntry": True,
            "SupercruiseExit": True,
            "Touchdown": True,
            "Undocked": True,
            "NavRoute": False,
            "NavRouteClear": False
        },
        "Exploration Events": {
            "CodexEntry": False,
            "DiscoveryScan": False,
            "Scan": True,
            "FSSAllBodiesFound": False,
            "FSSBodySignals": False,
            "FSSDiscoveryScan": False,
            "FSSSignalDiscovered": False,
            "MaterialCollected": False,
            "MaterialDiscarded": False,
            "MaterialDiscovered": False,
            "MultiSellExplorationData": False,
            "NavBeaconScan": True,
            "BuyExplorationData": False,
            "SAAScanComplete": False,
            "SAASignalsFound": False,
            "ScanBaryCentre": False,
            "SellExplorationData": False,
            "Screenshot": False
        },
        "Trade Events": {
            "Trade": False,
            "AsteroidCracked": False,
            "BuyTradeData": False,
            "CollectCargo": False,
            "EjectCargo": True,
            "MarketBuy": False,
            "MarketSell": False,
            "MiningRefined": False
        },
        "Station Services Events": {
            "StationServices": False,
            "BuyAmmo": False,
            "BuyDrones": False,
            "CargoDepot": False,
            "CommunityGoal": False,
            "CommunityGoalDiscard": False,
            "CommunityGoalJoin": False,
            "CommunityGoalReward": False,
            "CrewAssign": True,
            "CrewFire": True,
            "CrewHire": True,
            "EngineerContribution": False,
            "EngineerCraft": False,
            "EngineerLegacyConvert": False,
            "FetchRemoteModule": False,
            "Market": False,
            "MassModuleStore": False,
            "MaterialTrade": False,
            "MissionAbandoned": True,
            "MissionAccepted": True,
            "MissionCompleted": True,
            "MissionFailed": True,
            "MissionRedirected": True,
            "ModuleBuy": False,
            "ModuleRetrieve": False,
            "ModuleSell": False,
            "ModuleSellRemote": False,
            "ModuleStore": False,
            "ModuleSwap": False,
            "Outfitting": False,
            "PayBounties": True,
            "PayFines": True,
            "PayLegacyFines": True,
            "RedeemVoucher": True,
            "RefuelAll": False,
            "RefuelPartial": False,
            "Repair": False,
            "RepairAll": False,
            "RestockVehicle": False,
            "ScientificResearch": False,
            "Shipyard": False,
            "ShipyardBuy": True,
            "ShipyardNew": False,
            "ShipyardSell": False,
            "ShipyardTransfer": False,
            "ShipyardSwap": False,
            "StoredShips": False,
            "TechnologyBroker": False,
            "ClearImpound": True
        },
        "Powerplay Events": {
            "PowerplayCollect": False,
            "PowerplayDefect": True,
            "PowerplayDeliver": False,
            "PowerplayFastTrack": False,
            "PowerplayJoin": True,
            "PowerplayLeave": True,
            "PowerplaySalary": False,
            "PowerplayVote": False,
            "PowerplayVoucher": False
        },
        "Squadron Events": {
            "AppliedToSquadron": True,
            "DisbandedSquadron": True,
            "InvitedToSquadron": True,
            "JoinedSquadron": True,
            "KickedFromSquadron": True,
            "LeftSquadron": True,
            "SharedBookmarkToSquadron": False,
            "SquadronCreated": True,
            "SquadronDemotion": True,
            "SquadronPromotion": True,
            "WonATrophyForSquadron": False
        },
        "Fleet Carrier Events": {
            "CarrierJump": True,
            "CarrierBuy": True,
            "CarrierStats": False,
            "CarrierJumpRequest": True,
            "CarrierDecommission": True,
            "CarrierCancelDecommission": True,
            "CarrierBankTransfer": False,
            "CarrierDepositFuel": False,
            "CarrierCrewServices": False,
            "CarrierFinance": False,
            "CarrierShipPack": False,
            "CarrierModulePack": False,
            "CarrierTradeOrder": False,
            "CarrierDockingPermission": False,
            "CarrierNameChanged": True,
            "CarrierJumpCancelled": True
        },
        "Odyssey Events": {
            "Backpack": False,
            "BackpackChange": False,
            "BookDropship": True,
            "BookTaxi": True,
            "BuyMicroResources": False,
            "BuySuit": True,
            "BuyWeapon": True,
            "CancelDropship": True,
            "CancelTaxi": True,
            "CollectItems": False,
            "CreateSuitLoadout": True,
            "DeleteSuitLoadout": False,
            "Disembark": True,
            "DropItems": False,
            "DropShipDeploy": False,
            "Embark": True,
            "FCMaterials": False,
            "LoadoutEquipModule": False,
            "LoadoutRemoveModule": False,
            "RenameSuitLoadout": True,
            "ScanOrganic": True,
            "SellMicroResources": False,
            "SellOrganicData": True,
            "SellWeapon": False,
            "SwitchSuitLoadout": True,
            "TransferMicroResources": False,
            "TradeMicroResources": False,
            "UpgradeSuit": False,
            "UpgradeWeapon": False,
            "UseConsumable": False
        },
        "Other Events": {
            "AfmuRepairs": False,
            "ApproachSettlement": True,
            "ChangeCrewRole": False,
            "CockpitBreached": True,
            "CommitCrime": False,
            "Continued": False,
            "CrewLaunchFighter": True,
            "CrewMemberJoins": True,
            "CrewMemberQuits": True,
            "CrewMemberRoleChange": True,
            "CrimeVictim": True,
            "DatalinkScan": False,
            "DatalinkVoucher": False,
            "DataScanned": True,
            "DockFighter": True,
            "DockSRV": True,
            "EndCrewSession": True,
            "FighterRebuilt": True,
            "FuelScoop": False,
            "Friends": True,
            "JetConeBoost": False,
            "JetConeDamage": False,
            "JoinACrew": True,
            "KickCrewMember": True,
            "LaunchDrone": False,
            "LaunchFighter": True,
            "LaunchSRV": True,
            "ModuleInfo": False,
            "NpcCrewRank": False,
            "Promotion": True,
            "ProspectedAsteroid": False,
            "QuitACrew": True,
            "RebootRepair": True,
            "ReceiveText": False,
            "RepairDrone": False,
            "Resurrect": True,
            "Scanned": True,
            "SelfDestruct": True,
            "SendText": True,
            "Shutdown": True,
            "Synthesis": False,
            "SystemsShutdown": True,
            "USSDrop": False,
            "VehicleSwitch": False,
            "WingAdd": True,
            "WingInvite": True,
            "WingJoin": True,
            "WingLeave": True,
            "CargoTransfer": False,
            "SupercruiseDestinationDrop": False
        },
        "Status Events": {
            "LandingGearUp": False,
            "LandingGearDown": False,
            "FlightAssistOn": False,
            "FlightAssistOff": False,
            "HardpointsRetracted": False,
            "HardpointsDeployed": False,
            "LightsOff": False,
            "LightsOn": False,
            "CargoScoopRetracted": False,
            "CargoScoopDeployed": False,
            "SilentRunningOff": False,
            "SilentRunningOn": False,
            "FuelScoopStarted": False,
            "FuelScoopEnded": False,
            "SrvHandbrakeOff": False,
            "SrvHandbrakeOn": False,
            "SrvTurretViewConnected": False,
            "SrvTurretViewDisconnected": False,
            "SrvDriveAssistOff": False,
            "SrvDriveAssistOn": False,
            "FsdMassLockEscaped": False,
            "FsdMassLocked": False,
            "LowFuelWarningCleared": True,
            "LowFuelWarning": True,
            "OutofDanger": True,
            "InDanger": True,
            "NightVisionOff": False,
            "NightVisionOn": False,
            "LowOxygenWarningCleared": True,
            "LowOxygenWarning": True,
            "LowHealthWarningCleared": True,
            "LowHealthWarning": True,
            "GlideModeExited": False,
            "GlideModeEntered": False,
            "BreathableAtmosphereExited": False,
            "BreathableAtmosphereEntered": False,
            "LegalStateChanged": True,
            "WeaponSelected": False
        }
    },
    "ed_journal_path": ".",
    "ed_appdata_path": "."
}

def test_chat_executable():
    import subprocess
    import os
    
    # create temp dir
    temp_dir = tempfile.mkdtemp()
    
    # write config.json to temp dir
    with open(f"{temp_dir}/config.json", "w") as f:
        f.write(json.dumps(default_config))
    # write config.json to temp dir
    with open(f"{temp_dir}/Status.json", "w") as f:
        f.write(json.dumps({"event": "Status", "timestamp": "2024-10-08T18:19:57Z"}))
    with open(f"{temp_dir}/Journal.2024-11-24T100000.01.log", "w") as f:
        f.write('')
    
    print('Temp dir:', temp_dir)
        
    # run ../../dist/Chat/Chat.exe relative to this file, with temp dir as working directory
    chat_location = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../dist/Chat/Chat.exe" if platform.system() == "Windows" else "../dist/Chat/Chat")
    proc = subprocess.Popen(
        [chat_location],
        cwd=temp_dir, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1,
        universal_newlines=True, encoding='utf-8', shell=False, close_fds=True
    )
    
    # read stdout until Chat.exe either exits or outputs "System Ready."
    while proc.stdout:
        line = proc.stdout.readline()
        if not line:
            raise Exception("Chat.exe exited unexpectedly")
        print(line)
        if '{"type": "ready"}' in line:
            break

    # assert that Chat.exe is running
    assert proc.poll() is None
    
    # write start message to stdin
    if proc.stdin:
        proc.stdin.write('{"type": "start", "oldUi": true}\n')
        proc.stdin.flush()
    
    # read stdout until Chat.exe outputs a response
    while proc.stdout:
        line = proc.stdout.readline()
        if not line:
            raise Exception("Chat.exe exited unexpectedly")
        print(line)
        if '"prefix": "info", "message": "System Ready.\\n"' in line:
            break
    
    # assert that Chat.exe is running
    assert proc.poll() is None
    
    # terminate Chat.exe
    proc.kill()
    proc.wait()
    
if __name__ == "__main__":
    test_chat_executable()
    
    
