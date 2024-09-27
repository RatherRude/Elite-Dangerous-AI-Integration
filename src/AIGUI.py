import argparse
import json
import os
import re
import subprocess
import sys
import tkinter as tk
import webbrowser
from queue import Queue
from sys import platform
from threading import Thread
from tkinter import messagebox
from typing import Dict

import pyaudio
import requests
from openai import APIError, OpenAI

from lib.ControllerManager import ControllerManager


class VerticalScrolledFrame(tk.Frame):
    """A pure Tkinter scrollable frame that actually works!
    * Use the 'interior' attribute to place widgets inside the scrollable frame.
    * Construct and pack/place/grid normally.
    * This frame only allows vertical scrolling.
    """

    def __init__(self, outer_frame, width, *args, **kw):
        scrollbar_width = 16
        inner_width = width - scrollbar_width

        # base class initialization
        tk.Frame.__init__(self, outer_frame, width=width)

        scrollbar = tk.Scrollbar(self, width=scrollbar_width)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, expand=False)

        self.canvas = tk.Canvas(self, yscrollcommand=scrollbar.set, width=inner_width)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.inner_frame = tk.Frame(self.canvas, width=inner_width, *args, **kw)
        # self.inner_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar.config(command=self.canvas.yview)

        self.canvas.bind('<Configure>', self.__fill_canvas)

        # assign this obj (the inner frame) to the windows item of the canvas
        self.windows_item = self.canvas.create_window(0, 0, window=self.inner_frame, width=inner_width, anchor=tk.NW)
        self.canvas.configure(background='black')

    def __fill_canvas(self, event):
        "Enlarge the windows item to the canvas width"

        self.update_idletasks()
        self.canvas.itemconfig("inner_frame", width=self.canvas.winfo_width())

    def update(self):
        "Update the canvas and the scrollregion"

        self.update_idletasks()
        self.canvas.config(scrollregion=self.canvas.bbox("all"))
        self.canvas.itemconfig("inner_frame", width=self.canvas.winfo_width())

        self.canvas.bind('<Enter>', self.__on_enter)
        self.canvas.bind('<Leave>', self.__on_leave)

    def __on_enter(self, event):
        self.canvas.bind_all("<MouseWheel>", self.__onmousewheel)

    def __on_leave(self, event):
        self.canvas.unbind_all("<MouseWheel>")

    def __onmousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


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
        # 'Rank': False,
        # 'Reputation': False,
        'Statistics': False,
        # 'SquadronStartup': False
    },
    'Combat Events': {
        'Died': True,
        'Bounty': False,
        'CapShipBond': False,
        'Interdiction': True,
        'Interdicted': True,
        'EscapeInterdiction': True,
        'FactionKillBond': False,
        'FighterDestroyed': True,
        'HeatDamage': True,
        'HeatWarning': False,
        'HullDamage': True,
        'PVPKill': True,
        'ShieldState': True,
        'ShipTargetted': True,
        'SRVDestroyed': True,
        'UnderAttack': True
    },
    'Travel Events': {
        'CodexEntry': False,
        'ApproachBody': True,
        'Docked': True,
        'DockingCanceled': False,
        'DockingDenied': False,
        'DockingGranted': False,
        'DockingRequested': False,
        'DockingTimeout': False,
        'FSDJump': False,
        'FSDTarget': False,
        'LeaveBody': True,
        'Liftoff': True,
        'StartJump': False,
        'SupercruiseEntry': False,
        'SupercruiseExit': False,
        'Touchdown': True,
        'Undocked': True,
        'NavRoute': False,
        'NavRouteClear': False
    },
    'Exploration Events': {
        'CodexEntry': False,
        'DiscoveryScan': True,
        'Scan': True,
        'FSSAllBodiesFound': True,
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
        'EngineerProgress': False,
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
        'PayBounties': False,
        'PayFines': False,
        'PayLegacyFines': False,
        'RedeemVoucher': False,
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
        'StoredModules': False,
        'StoredShips': False,
        'TechnologyBroker': False,
        'ClearImpound': False
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
        'CarrierJump': False,
        'CarrierBuy': False,
        'CarrierStats': False,
        'CarrierJumpRequest': False,
        'CarrierDecommission': False,
        'CarrierCancelDecommission': False,
        'CarrierBankTransfer': False,
        'CarrierDepositFuel': False,
        'CarrierCrewServices': False,
        'CarrierFinance': False,
        'CarrierShipPack': False,
        'CarrierModulePack': False,
        'CarrierTradeOrder': False,
        'CarrierDockingPermission': False,
        'CarrierNameChanged': False,
        'CarrierJumpCancelled': False
    },
    'Odyssey Events': {
        'Backpack': False,
        'BackpackChange': False,
        'BookDropship': False,
        'BookTaxi': False,
        'BuyMicroResources': False,
        'BuySuit': True,
        'BuyWeapon': True,
        'CancelDropship': False,
        'CancelTaxi': False,
        'CollectItems': False,
        'CreateSuitLoadout': False,
        'DeleteSuitLoadout': False,
        'Disembark': True,
        'DropItems': False,
        'DropShipDeploy': False,
        'Embark': True,
        'FCMaterials': False,
        'LoadoutEquipModule': False,
        'LoadoutRemoveModule': False,
        'RenameSuitLoadout': False,
        'ScanOrganic': False,
        'SellMicroResources': False,
        'SellOrganicData': False,
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
        'CommitCrime': True,
        'Continued': False,
        'CrewLaunchFighter': True,
        'CrewMemberJoins': True,
        'CrewMemberQuits': True,
        'CrewMemberRoleChange': True,
        'CrimeVictim': True,
        'DatalinkScan': True,
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
        'NpcCrewPaidWage': False,
        'NpcCrewRank': False,
        'Promotion': True,
        'ProspectedAsteroid': False,
        'QuitACrew': True,
        'RebootRepair': True,
        'ReceiveText': False,
        'RepairDrone': False,
        'ReservoirReplenished': False,
        'Resurrect': True,
        'Scanned': True,
        'SelfDestruct': True,
        'SendText': True,
        'Shutdown': True,
        'Synthesis': False,
        'SystemsShutdown': False,
        'USSDrop': False,
        'VehicleSwitch': False,
        'WingAdd': True,
        'WingInvite': True,
        'WingJoin': True,
        'WingLeave': True,
        'CargoTransfer': False,
        'SupercruiseDestinationDrop': False
    }
}


def ask_for_update(release_name='A new release',
                   release_url='https://github.com/RatherRude/Elite-Dangerous-AI-Integration/releases/'):
    # Ask the user if they want to download the new version
    result = messagebox.askyesno(f"Update available",
                                 f"Would you like to download {release_name}?")

    if result:
        webbrowser.open(release_url)


def check_for_updates(current_commit):
    url = f'https://api.github.com/repos/RatherRude/Elite-Dangerous-AI-Integration/releases'
    response = requests.get(url)

    if response.status_code == 200:
        release_data = response.json()
        tag_name = release_data[0]['tag_name']
        release_url = release_data[0]['html_url']
        release_name = release_data[0]['name']

        # Get the commit id for the release tag
        tag_url = f'https://api.github.com/repos/RatherRude/Elite-Dangerous-AI-Integration/git/ref/tags/{tag_name}'
        tag_response = requests.get(tag_url)

        if tag_response.status_code == 200:
            tag_data = tag_response.json()
            if tag_data['object']['sha'] != current_commit:
                ask_for_update(release_name, release_url)


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Elite Dangerous AI Integration")
        root.protocol("WM_DELETE_WINDOW", self.on_closing)

        parser = argparse.ArgumentParser()
        python_executable = sys.executable
        parser.add_argument("--chat", default=python_executable + " ./src/Chat.py", help="command to run the chat app")
        parser.add_argument("--release", default="", help="current release")
        args = parser.parse_args()
        self.chat_command_arg: str = args.chat
        self.release_version_arg: str = args.release

        self.check_vars = {}

        self.ptt_key = None

        self.controller_manager = ControllerManager()

        self.process = None
        self.output_queue = Queue()
        self.read_thread = None
        # Load initial data from JSON file if exists
        self.data = self.load_data()

        # Background Image
        try:
            background_image_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../screen/EDAI_logo.png'))
            if hasattr(sys, 'frozen'):
                background_image_path = os.path.abspath(
                    os.path.join(os.path.dirname(__file__), './screen/EDAI_logo.png'))
            background_image = tk.PhotoImage(file=background_image_path)
            self.background_label = tk.Label(root, bg="black", image=background_image)
            self.background_label.place(x=0, y=0, relwidth=1, relheight=1)
            self.background_label.image = background_image
        except tk.TclError as e:
            print(f"Failed to load background image: {e}")

        # Main Frame (for other widgets)
        self.main_frame = tk.Frame(root, bd=1)  # White background for visibility
        self.main_frame.pack(padx=20, pady=20)

        # Commander Name (Small Input)
        tk.Label(self.main_frame, text="Commander Name:").grid(row=0, column=0, sticky=tk.W)
        self.commander_name = tk.Entry(self.main_frame, width=50)
        self.commander_name.grid(row=0, column=1, padx=10, pady=5, sticky=tk.W)

        # Character (Multi-line Input)
        tk.Label(self.main_frame, text="AI Character:").grid(row=1, column=0, sticky=tk.W)
        self.character = tk.Text(self.main_frame, width=80, height=15)
        self.character.grid(row=1, column=1, padx=10, pady=5, sticky=tk.W)

        # API Key (Secure Entry) - Placed above the first button
        tk.Label(self.main_frame, text="OpenAI API Key:").grid(row=2, column=0, sticky=tk.W)
        self.api_key = tk.Entry(self.main_frame, show='*', width=50)  # Show '*' to indicate a secure entry
        self.api_key.grid(row=2, column=1, padx=10, pady=5, sticky=tk.W)

        # Push-to-talk
        tk.Label(self.main_frame, text="Push-to-talk:", font=('Arial', 10)).grid(row=3, column=0, sticky=tk.W)
        # PTT (Checkbox)
        self.ptt_var = tk.BooleanVar()
        self.ptt_var.set(False)  # Default value
        self.ptt_checkbox = tk.Checkbutton(self.main_frame, text="Enabled", variable=self.ptt_var,
                                           command=self.toggle_ptt)
        self.ptt_checkbox.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        tk.Label(self.main_frame, text="Uses automatic voice detection if not enabled", font="Arial 10 italic").grid(
            row=3, column=1, sticky=tk.W, padx=80, pady=5)

        self.pptButton = tk.Button(self.main_frame, text="Key Binding: Press any key", font=('Arial', 10))
        self.pptButton.grid(row=3, column=1, sticky=tk.W, padx=(360, 10), pady=5)
        self.pptButton.bind("<Button-1>", self.on_label_click)

        # Continue Conversation
        tk.Label(self.main_frame, text="Resume Chat:", font=('Arial', 10)).grid(row=4, column=0, sticky=tk.W)
        # Conversation (Checkbox)
        self.continue_conversation_var = tk.BooleanVar()
        self.continue_conversation_var.set(True)  # Default value
        self.continue_conversation_checkbox = tk.Checkbutton(self.main_frame, text="Enabled",
                                                             variable=self.continue_conversation_var)
        self.continue_conversation_checkbox.grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)
        tk.Label(self.main_frame, text="Resumes previous conversation if enabled", font="Arial 10 italic").grid(row=4,
                                                                                                                column=1,
                                                                                                                sticky=tk.W,
                                                                                                                padx=80,
                                                                                                                pady=5)

        tk.Label(self.main_frame, text="Input Device:", font=('Arial', 10)).grid(row=5, column=0, sticky=tk.W)
        self.input_device_name = tk.Label(self.main_frame, text=self.get_default_microphone_name(),
                                          font=('Arial', 10)).grid(row=5, column=1, sticky=tk.W)

        self.game_events_frame = VerticalScrolledFrame(self.main_frame, width=600)
        self.game_events_frame.grid(row=7, column=0, columnspan=2, sticky="")
        self.game_events_save_cb = self.populate_game_events_frame(self.game_events_frame.inner_frame,
                                                                   self.data['game_events'])
        self.game_events_frame.update()  # update scrollable area
        self.game_events_frame.grid_remove()  # Initially hide

        # AI Geeks Section (Initially hidden)
        self.ai_geeks_frame = VerticalScrolledFrame(self.main_frame, width=600)
        self.ai_geeks_frame.grid(row=7, column=0, columnspan=2)
        self.ai_geeks_frame.grid_remove()  # Initially hide

        # Disclaimer
        tk.Label(self.ai_geeks_frame.inner_frame, text="None of the AI Geek options are required.",
                 font="Helvetica 12 bold").grid(row=0, column=0, columnspan=2, sticky="")

        self.incr = 0

        def get_next():
            self.incr += 1
            return self.incr

        def get_same():
            return self.incr

        # LLM
        tk.Label(self.ai_geeks_frame.inner_frame, text="Text LLM options",
                 font="Helvetica 10 bold").grid(row=get_next(), column=0, columnspan=2, sticky="")

        # LLM Model Name
        tk.Label(self.ai_geeks_frame.inner_frame, text="LLM Model Name:").grid(row=get_next(), column=0, sticky=tk.W)
        self.llm_model_name = tk.Entry(self.ai_geeks_frame.inner_frame, width=50)
        self.llm_model_name.grid(row=get_same(), column=1, padx=10, pady=5)

        # LLM Endpoint
        tk.Label(self.ai_geeks_frame.inner_frame, text="LLM Endpoint:").grid(row=get_next(), column=0, sticky=tk.W)
        self.llm_endpoint = tk.Entry(self.ai_geeks_frame.inner_frame, width=50)
        self.llm_endpoint.grid(row=get_same(), column=1, padx=10, pady=5)

        # LLM API Key
        tk.Label(self.ai_geeks_frame.inner_frame, text="LLM API Key:").grid(row=get_next(), column=0, sticky=tk.W)
        self.llm_api_key = tk.Entry(self.ai_geeks_frame.inner_frame, show='*', width=50)
        self.llm_api_key.grid(row=get_same(), column=1, padx=10, pady=5)

        # Function Calling (Checkbox)
        self.tools_var = tk.BooleanVar()
        self.tools_var.set(True)  # Default value
        self.tools_checkbox = tk.Checkbutton(self.ai_geeks_frame.inner_frame, text="Function Calling (default: on)",
                                             variable=self.tools_var)
        self.tools_checkbox.grid(row=get_next(), column=0, padx=10, pady=10, sticky=tk.W)

        # STT
        tk.Label(self.ai_geeks_frame.inner_frame, text="STT options",
                 font="Helvetica 10 bold").grid(row=get_next(), column=0, columnspan=2, sticky="")

        ## STT Model
        self.stt_model_name_label = tk.Label(self.ai_geeks_frame.inner_frame, text="STT Model Name:")
        self.stt_model_name_label.grid(row=get_next(), column=0, sticky=tk.W)
        self.stt_model_name = tk.Entry(self.ai_geeks_frame.inner_frame, width=50)
        self.stt_model_name.grid(row=get_same(), column=1, padx=10, pady=5)

        ## STT Endpoint
        self.stt_endpoint_label = tk.Label(self.ai_geeks_frame.inner_frame, text="STT Endpoint:")
        self.stt_endpoint_label.grid(row=get_next(), column=0, sticky=tk.W)
        self.stt_endpoint = tk.Entry(self.ai_geeks_frame.inner_frame, width=50)
        self.stt_endpoint.grid(row=get_same(), column=1, padx=10, pady=5)

        ## STT API Key
        self.stt_api_key_label = tk.Label(self.ai_geeks_frame.inner_frame, text="STT API Key:")
        self.stt_api_key_label.grid(row=get_next(), column=0, sticky=tk.W)
        self.stt_api_key = tk.Entry(self.ai_geeks_frame.inner_frame, show='*', width=50)
        self.stt_api_key.grid(row=get_same(), column=1, padx=10, pady=5)

        # Alternative STT (Checkbox)
        self.alternative_stt_var = tk.BooleanVar()
        self.alternative_stt_var.set(False)  # Default value
        self.alternative_stt_checkbox = tk.Checkbutton(self.ai_geeks_frame.inner_frame,
                                                       text="Local STT (pre-installed whisper-medium)",
                                                       variable=self.alternative_stt_var, command=self.toggle_local_stt)
        self.alternative_stt_checkbox.grid(row=get_next(), column=0, padx=10, pady=10, sticky=tk.W, columnspan=2)

        # TTS
        tk.Label(self.ai_geeks_frame.inner_frame, text="TTS options",
                 font="Helvetica 10 bold").grid(row=get_next(), column=0, columnspan=2, sticky="")

        ## TTS Model
        self.tts_model_name_label = tk.Label(self.ai_geeks_frame.inner_frame, text="TTS Model Name:")
        self.tts_model_name_label.grid(row=get_next(), column=0, sticky=tk.W)
        self.tts_model_name = tk.Entry(self.ai_geeks_frame.inner_frame, width=50)
        self.tts_model_name.grid(row=get_same(), column=1, padx=10, pady=5)

        ## TTS Endpoint
        self.tts_endpoint_label = tk.Label(self.ai_geeks_frame.inner_frame, text="TTS Endpoint:")
        self.tts_endpoint_label.grid(row=get_next(), column=0, sticky=tk.W)
        self.tts_endpoint = tk.Entry(self.ai_geeks_frame.inner_frame, width=50)
        self.tts_endpoint.grid(row=get_same(), column=1, padx=10, pady=5)

        ## TTS API Key
        self.tts_api_key_label = tk.Label(self.ai_geeks_frame.inner_frame, text="TTS API Key:")
        self.tts_api_key_label.grid(row=get_next(), column=0, sticky=tk.W)
        self.tts_api_key = tk.Entry(self.ai_geeks_frame.inner_frame, show='*', width=50)
        self.tts_api_key.grid(row=get_same(), column=1, padx=10, pady=5)

        # TTS Voice
        self.tts_voice_label = tk.Label(self.ai_geeks_frame.inner_frame, text="TTS Voice:")
        self.tts_voice_label.grid(row=get_next(), column=0, sticky=tk.W)
        self.tts_voice = tk.Entry(self.ai_geeks_frame.inner_frame, width=50)
        self.tts_voice.grid(row=get_same(), column=1, padx=10, pady=5)

        # TTS Speed
        self.tts_speed_label = tk.Label(self.ai_geeks_frame.inner_frame, text="TTS Speed:")
        self.tts_speed_label.grid(row=get_next(), column=0, sticky=tk.W)
        self.tts_speed = tk.Entry(self.ai_geeks_frame.inner_frame, width=50)
        self.tts_speed.grid(row=get_same(), column=1, padx=10, pady=5)

        # Alternative TTS (Checkbox)
        self.alternative_tts_var = tk.BooleanVar()
        self.alternative_tts_var.set(False)  # Default value
        self.alternative_tts_checkbox = tk.Checkbutton(self.ai_geeks_frame.inner_frame,
                                                       text="Local TTS (pre-installed OS Voices)",
                                                       variable=self.alternative_tts_var, command=self.toggle_local_tts)
        self.alternative_tts_checkbox.grid(row=get_next(), column=0, padx=10, pady=10, sticky=tk.W)

        # Vision
        tk.Label(self.ai_geeks_frame.inner_frame, text="Vision LLM options",
                 font="Helvetica 10 bold").grid(row=get_next(), column=0, columnspan=2, sticky="")

        ## Vision Model
        self.vision_model_name_label = tk.Label(self.ai_geeks_frame.inner_frame, text="Vision Model Name:")
        self.vision_model_name_label.grid(row=get_next(), column=0, sticky=tk.W)
        self.vision_model_name = tk.Entry(self.ai_geeks_frame.inner_frame, width=50)
        self.vision_model_name.grid(row=get_same(), column=1, padx=10, pady=5)
        #
        ## Vision Model Endpoint
        self.vision_endpoint_label = tk.Label(self.ai_geeks_frame.inner_frame, text="Vision Model Endpoint:")
        self.vision_endpoint_label.grid(row=get_next(), column=0, sticky=tk.W)
        self.vision_endpoint = tk.Entry(self.ai_geeks_frame.inner_frame, width=50)
        self.vision_endpoint.grid(row=get_same(), column=1, padx=10, pady=5)
        #
        ## Vision Model API Key
        self.vision_api_key_label = tk.Label(self.ai_geeks_frame.inner_frame, text="Vision Model API Key:")
        self.vision_api_key_label.grid(row=get_next(), column=0, sticky=tk.W)
        self.vision_api_key = tk.Entry(self.ai_geeks_frame.inner_frame, show='*', width=50)
        self.vision_api_key.grid(row=get_same(), column=1, padx=10, pady=5)

        # Vision Capabilities (Checkbox)
        self.vision_var = tk.BooleanVar()
        self.vision_var.set(True)  # Default value
        self.vision_checkbox = tk.Checkbutton(self.ai_geeks_frame.inner_frame, text="Vision Capabilities (default: on)",
                                              variable=self.vision_var, command=self.toggle_vision)
        self.vision_checkbox.grid(row=get_next(), column=0, padx=10, pady=10, sticky=tk.W)

        self.ai_geeks_frame.update()

        # Toggle Section Button
        self.toggle_ai_geeks_section_button = tk.Button(self.main_frame, text="Show AI Geeks Section",
                                                        command=self.toggle_ai_geeks_section)
        self.toggle_ai_geeks_section_button.grid(row=6, column=0, columnspan=2, pady=10, padx=(150, 0), sticky="")

        # Toggle Section Button
        self.toggle_game_events_section_button = tk.Button(self.main_frame, text="Show Game Events Section",
                                                           command=self.toggle_game_events_section)
        self.toggle_game_events_section_button.grid(row=6, column=0, columnspan=2, pady=10, padx=(0, 150), sticky="")

        # Debug Frame and Text Widget
        self.debug_frame = tk.Frame(root, bg='black', bd=1)  # White background for visibility
        self.debug_frame.pack(side=tk.TOP, padx=20, pady=20)

        tk.Label(self.debug_frame, text="Debug Output:").pack(anchor=tk.W)
        self.debug_text = tk.Text(self.debug_frame, width=100, height=43, bg='black')
        self.debug_text.tag_configure("normal", foreground="white", font="Helvetica 12")
        self.debug_text.tag_configure("human", foreground="red", font="Helvetica 12 bold")
        self.debug_text.tag_configure("ai", foreground="blue", font="Helvetica 12 bold")
        self.debug_text.tag_configure("action", foreground="yellow", font="Helvetica 12 bold")
        self.debug_text.tag_configure("event", foreground="orange", font="Helvetica 12 bold")
        self.debug_text.tag_configure("debug", foreground="gray", font="Helvetica 12 bold")
        self.debug_text.tag_configure("error", foreground="red", font="Helvetica 12 bold")
        self.debug_text.pack(side=tk.LEFT, padx=10, pady=10)

        self.debug_frame.pack_forget()

        # Button Frame
        self.button_frame = tk.Frame(root, bg='black')
        self.button_frame.pack(side=tk.BOTTOM, pady=10)

        # Start and Stop Buttons for External Script
        self.start_button = tk.Button(self.button_frame, text="Start AI", command=self.start_external_script)
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = tk.Button(self.button_frame, text="Stop AI", command=self.stop_external_script)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        self.stop_button.pack_forget()

        # category_label = tk.Label(self.ai_geeks_frame, text="category", font=('Arial', 14, 'bold'))
        #        var = tk.BooleanVar(value=self.check_vars.get(event, event not in default_off_events))
        #        chk = tk.Checkbutton(self.ai_geeks_frame, text=event, variable=var)

        # for category, events in game_events.items():
        #    category_label = tk.Label(self.ai_geeks_frame, text=category, font=('Arial', 14, 'bold'))
        #    for event in events:
        #        var = tk.BooleanVar(value=self.check_vars.get(event, event not in default_off_events))
        #        chk = tk.Checkbutton(self.ai_geeks_frame, text=event, variable=var)
        #        self.check_vars[event] = var

        # Initialize fields with loaded data
        self.update_fields()

        # Process handle for subprocess
        self.process = None

        if self.release_version_arg:
            check_for_updates(self.release_version_arg)

    def populate_game_events_frame(self, frame: tk.Frame, game_events: Dict[str, Dict[str, bool]]):
        category_values: Dict[str, Dict[str, tk.BooleanVar]] = {}
        rowCounter = 0
        for category, events in game_events.items():
            category_label = tk.Label(frame, text=category, font=('Arial', 14, 'bold'))
            category_label.grid(row=rowCounter, column=0, sticky=tk.W)
            category_values[category] = {}

            for event, state in events.items():
                var = tk.BooleanVar(value=state)
                chk = tk.Checkbutton(frame, text=event, variable=var)
                chk.grid(row=rowCounter, column=1, sticky=tk.W)
                category_values[category][event] = var
                rowCounter += 1

        return lambda: {category: {
            event: state.get() for event, state in events.items()
        } for category, events in category_values.items()}

    def on_closing(self):
        self.save_settings()
        root.destroy()

    def on_label_click(self, event):
        self.pptButton.config(text="Press a key...")
        self.controller_manager.listen_hotkey(self.on_hotkey_detected)

    def on_hotkey_detected(self, key: str):
        self.ptt_key = key
        self.update_label_text()

    def update_label_text(self):
        if self.ptt_key:
            self.pptButton.config(text=f"Key Binding: {self.ptt_key}")
        else:
            self.pptButton.config(text="Set Key Binding")

    def load_data(self):
        defaults = {
            'commander_name': "",
            'character':
                "I am Commander {commander_name}, an independent pilot and secret member of the Dark Wheel. \n\n" +
                "you are COVAS:NEXT, the onboard AI of my starship. You will be addressed as 'Computer'. \n" +
                "You possess extensive knowledge and can provide detailed and accurate information on a wide range of topics, " +
                "including galactic navigation, ship status, the current system, and more. \n\n" +
                "Do not inform about my ship status and my location unless it's relevant or requested by me. Answer within 3 sentences. Acknowledge given orders. \n\n" +
                "Guide and support me with witty, intelligent and sarcastic commentary. Provide clear mission briefings and humorous observations.",
            'api_key': "",
            'alternative_stt_var': False,
            'alternative_tts_var': False,
            'tools_var': True,
            'vision_var': True,
            'ptt_var': False,
            'continue_conversation_var': True,
            'llm_model_name': "gpt-4o-mini",
            'llm_endpoint': "https://api.openai.com/v1",
            'llm_api_key': "",
            'tts_voice': "nova",
            'tts_speed': "1.2",
            'ptt_key': '',
            'vision_model_name': "gpt-4o-mini",
            'vision_endpoint': "https://api.openai.com/v1",
            'vision_api_key': "",
            'stt_model_name': "whisper-1",
            'stt_endpoint': "https://api.openai.com/v1",
            'stt_api_key': "",
            'tts_model_name': "tts-1",
            'tts_endpoint': "https://api.openai.com/v1",
            'tts_api_key': "",
            'game_events': game_events
        }
        try:
            with open('config.json', 'r') as file:
                data = json.load(file)
                return self.merge_config_data(defaults, data)
        except Exception:
            print('Error loading config.json. Restoring default.')
            return defaults

    def merge_config_data(self, defaults: dict, user: dict):
        merge = {}
        for key in defaults:
            if not isinstance(user.get(key), type(defaults.get(key))):
                # print("defaulting", key, "because", str(type(defaults.get(key))), "does not equal", str(type(user.get(key))))
                merge[key] = defaults.get(key)
            elif isinstance(defaults.get(key), dict):
                # print("recursively merging", key)
                merge[key] = self.merge_config_data(defaults.get(key), user.get(key))
            elif isinstance(defaults.get(key), list):
                raise Exception("Lists not supported during config merge")
            else:
                # print("keeping key", key)
                merge[key] = user.get(key)
        return merge

    def check_model_list(self, client, model_name):
        try:
            models = client.models.list()
            # print('models', models)
            if not any(model.id == model_name for model in models):
                messagebox.showerror("Invalid model name",
                                     f"Your model provider doesn't serve '{model_name}' to you. Please check your model name.")
                return False

            return True
        except APIError as e:
            if e.code == "invalid_api_key":
                messagebox.showerror("Invalid API key",
                                     f"The API key you have provided for '{model_name}' isn't valid. Please check your API key.")
                return False
            else:
                print('APIError', e)
        except Exception as e:
            print(e)

        return True

    def check_settings(self):

        llmClient = OpenAI(
            base_url="https://api.openai.com/v1" if self.llm_endpoint.get() == '' else self.llm_endpoint.get(),
            api_key=self.api_key.get() if self.llm_api_key.get() == '' else self.llm_api_key.get(),
        )
        if self.llm_model_name.get() == 'gpt-3.5-turbo' and self.check_model_list(llmClient, 'gpt-4o-mini'):
            self.llm_model_name.delete(0, tk.END)
            self.llm_model_name.insert(0, 'gpt-4o-mini')
            messagebox.showinfo("Upgrade to GPT-4o-mini",
                                "Your OpenAI account has reached the required tier to use gpt-4o-mini. It will now be used instead of GPT-3.5-Turbo.")

        if not self.check_model_list(llmClient, self.llm_model_name.get()):
            if self.llm_model_name.get() == 'gpt-4o-mini' and self.check_model_list(llmClient, 'gpt-3.5-turbo'):
                self.llm_model_name.delete(0, tk.END)
                self.llm_model_name.insert(0, 'gpt-3.5-turbo')
                messagebox.showinfo("Fallback to GPT-3.5-Turbo",
                                    "Your OpenAI account hasn't reached the required tier to use gpt-4o-mini yet. GPT-3.5-Turbo will be used as a fallback.")
            else:
                return False

        if self.vision_var.get():
            visionClient = OpenAI(
                base_url="https://api.openai.com/v1" if self.vision_endpoint.get() == '' else self.vision_endpoint.get(),
                api_key=self.api_key.get() if self.vision_api_key.get() == '' else self.vision_api_key.get(),
            )

            if not self.check_model_list(visionClient, self.vision_model_name.get()):
                return False

        if not self.alternative_stt_var.get():
            sttClient = OpenAI(
                base_url="https://api.openai.com/v1" if self.stt_endpoint.get() == '' else self.stt_endpoint.get(),
                api_key=self.api_key.get() if self.stt_api_key.get() == '' else self.stt_api_key.get(),
            )
            if not self.check_model_list(sttClient, self.stt_model_name.get()):
                return False

        if not self.alternative_tts_var.get():
            ttsClient = OpenAI(
                base_url="https://api.openai.com/v1" if self.tts_endpoint.get() == '' else self.tts_endpoint.get(),
                api_key=self.api_key.get() if self.tts_api_key.get() == '' else self.tts_api_key.get(),
            )
            if not self.check_model_list(ttsClient, self.tts_model_name.get()):
                return False

        return True

    def save_settings(self):
        self.data['commander_name'] = self.commander_name.get()
        self.data['character'] = self.character.get("1.0", tk.END).strip()
        self.data['api_key'] = self.api_key.get()
        self.data['llm_model_name'] = self.llm_model_name.get()
        self.data['llm_endpoint'] = self.llm_endpoint.get()
        self.data['llm_api_key'] = self.llm_api_key.get()
        self.data['vision_model_name'] = self.vision_model_name.get()
        self.data['vision_endpoint'] = self.vision_endpoint.get()
        self.data['vision_api_key'] = self.vision_api_key.get()
        self.data['stt_model_name'] = self.stt_model_name.get()
        self.data['stt_endpoint'] = self.stt_endpoint.get()
        self.data['stt_api_key'] = self.stt_api_key.get()
        self.data['tts_model_name'] = self.tts_model_name.get()
        self.data['tts_endpoint'] = self.tts_endpoint.get()
        self.data['tts_api_key'] = self.tts_api_key.get()
        self.data['alternative_stt_var'] = self.alternative_stt_var.get()
        self.data['alternative_tts_var'] = self.alternative_tts_var.get()
        self.data['tools_var'] = self.tools_var.get()
        self.data['vision_var'] = self.vision_var.get()
        self.data['ptt_var'] = self.ptt_var.get()
        self.data['continue_conversation_var'] = self.continue_conversation_var.get()
        self.data['tts_voice'] = self.tts_voice.get()
        self.data['tts_speed'] = self.tts_speed.get()
        self.data['ptt_key'] = self.ptt_key
        self.data['game_events'] = self.game_events_save_cb()

        with open('config.json', 'w') as file:
            json.dump(self.data, file, indent=4)

        # messagebox.showinfo("Settings Saved", "Settings have been saved successfully.")

    def update_fields(self):
        self.commander_name.insert(0, self.data['commander_name'])
        self.character.insert(tk.END, self.data['character'])
        self.api_key.insert(0, self.data['api_key'])
        self.llm_model_name.insert(0, self.data['llm_model_name'])
        self.llm_endpoint.insert(0, self.data['llm_endpoint'])
        self.llm_api_key.insert(0, self.data['llm_api_key'])
        self.vision_model_name.insert(0, self.data['vision_model_name'])
        self.vision_endpoint.insert(0, self.data['vision_endpoint'])
        self.vision_api_key.insert(0, self.data['vision_api_key'])
        self.stt_model_name.insert(0, self.data['stt_model_name'])
        self.stt_endpoint.insert(0, self.data['stt_endpoint'])
        self.stt_api_key.insert(0, self.data['stt_api_key'])
        self.tts_model_name.insert(0, self.data['tts_model_name'])
        self.tts_endpoint.insert(0, self.data['tts_endpoint'])
        self.tts_api_key.insert(0, self.data['tts_api_key'])
        self.alternative_stt_var.set(self.data['alternative_stt_var'])
        self.alternative_tts_var.set(self.data['alternative_tts_var'])
        self.tools_var.set(self.data['tools_var'])
        self.vision_var.set(self.data['vision_var'])
        self.ptt_var.set(self.data['ptt_var'])
        self.continue_conversation_var.set(self.data['continue_conversation_var'])
        self.tts_voice.insert(0, self.data['tts_voice'])
        self.tts_speed.insert(0, self.data['tts_speed'])
        self.ptt_key = self.data['ptt_key']

        self.update_label_text()
        self.toggle_ptt()
        self.toggle_local_stt()
        self.toggle_local_tts()
        self.toggle_vision()

    def toggle_ai_geeks_section(self):
        if self.ai_geeks_frame.winfo_viewable():
            self.ai_geeks_frame.grid_remove()
            self.toggle_ai_geeks_section_button.config(text="Show AI Geeks Section")
        else:
            self.ai_geeks_frame.grid()
            self.toggle_ai_geeks_section_button.config(text="Hide AI Geeks Section")

            self.game_events_frame.grid_remove()
            self.toggle_game_events_section_button.config(text="Show Game Event Section")

    def toggle_game_events_section(self):
        if self.game_events_frame.winfo_viewable():
            self.game_events_frame.grid_remove()
            self.toggle_game_events_section_button.config(text="Show Game Event Section")
        else:
            self.game_events_frame.grid()
            self.toggle_game_events_section_button.config(text="Hide Game Event Section")

            self.ai_geeks_frame.grid_remove()
            self.toggle_ai_geeks_section_button.config(text="Show AI Geeks Section")

    def toggle_ptt(self):
        if self.ptt_var.get():
            self.pptButton.grid()
        else:
            self.pptButton.grid_remove()

    def toggle_local_stt(self):
        if self.alternative_stt_var.get():
            self.stt_model_name.grid_remove()
            self.stt_model_name_label.grid_remove()
            self.stt_endpoint.grid_remove()
            self.stt_endpoint_label.grid_remove()
            self.stt_api_key.grid_remove()
            self.stt_api_key_label.grid_remove()
        else:
            self.stt_model_name.grid()
            self.stt_model_name_label.grid()
            self.stt_endpoint.grid()
            self.stt_endpoint_label.grid()
            self.stt_api_key.grid()
            self.stt_api_key_label.grid()

    def toggle_local_tts(self):
        if self.alternative_tts_var.get():
            self.tts_model_name.grid_remove()
            self.tts_model_name_label.grid_remove()
            self.tts_endpoint.grid_remove()
            self.tts_endpoint_label.grid_remove()
            self.tts_api_key.grid_remove()
            self.tts_api_key_label.grid_remove()
        else:
            self.tts_model_name.grid()
            self.tts_model_name_label.grid()
            self.tts_endpoint.grid()
            self.tts_endpoint_label.grid()
            self.tts_api_key.grid()
            self.tts_api_key_label.grid()

    def toggle_vision(self):
        if self.vision_var.get():
            self.vision_model_name.grid()
            self.vision_model_name_label.grid()
            self.vision_endpoint.grid()
            self.vision_endpoint_label.grid()
            self.vision_api_key.grid()
            self.vision_api_key_label.grid()
        else:
            self.vision_model_name.grid_remove()
            self.vision_model_name_label.grid_remove()
            self.vision_endpoint.grid_remove()
            self.vision_endpoint_label.grid_remove()
            self.vision_api_key.grid_remove()
            self.vision_api_key_label.grid_remove()

    def start_external_script(self):
        if not self.check_settings():
            return

        self.save_settings()
        self.debug_text.delete('1.0', tk.END)
        self.debug_text.insert(tk.END, "Starting Elite Dangerous AI Integration...\n", "normal")
        # self.debug_text.update_idletasks()

        try:
            # Script execution
            startupinfo = None
            if platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            self.process = subprocess.Popen(self.chat_command_arg.split(' '), startupinfo=startupinfo,
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1,
                                            universal_newlines=True, encoding='utf-8', shell=False, close_fds=True)

            self.debug_frame.pack()
            self.main_frame.pack_forget()
            self.stop_button.pack()
            self.start_button.pack_forget()  # Hide the start button

            # Read output in a separate thread
            self.thread_process_stdout = Thread(target=self.read_process_output, daemon=True)
            self.thread_process_stdout.start()
            self.thread_process_stderr = Thread(target=self.read_process_error, daemon=True)
            self.thread_process_stderr.start()

        except FileNotFoundError as e:
            print(e)
            self.debug_text.insert(tk.END, "Failed to start Elite Dangerous AI Integration: File not found.\n")
            self.debug_text.see(tk.END)
        except Exception as e:
            print(e)
            self.debug_text.insert(tk.END, f"Failed to start Elite Dangerous AI Integration: {str(e)}\n")
            self.debug_text.see(tk.END)

    def strip_ansi_codes(self, s: str):
        return re.sub(r'\x1b\[([0-9,A-Z]{1,2}(;[0-9]{1,2})?(;[0-9]{3})?)?[m|K]?', '', s)

    def read_process_output(self):
        process = self.process
        while process and process.poll() is None:
            stdout_line = process.stdout.readline()
            stdout_line = self.strip_ansi_codes(stdout_line)
            if stdout_line:
                if stdout_line.startswith("cmdr"):
                    self.debug_text.insert(tk.END, "CMDR", "human")
                    self.debug_text.insert(tk.END, stdout_line[4:], "normal")
                elif stdout_line.startswith("covas"):
                    self.debug_text.insert(tk.END, "COVAS", "ai")
                    self.debug_text.insert(tk.END, stdout_line[5:], "normal")
                elif stdout_line.startswith("event"):
                    self.debug_text.insert(tk.END, "Event", "event")
                    self.debug_text.insert(tk.END, stdout_line[5:], "normal")
                elif stdout_line.startswith("action"):
                    self.debug_text.insert(tk.END, "Action", "action")
                    self.debug_text.insert(tk.END, stdout_line[6:], "normal")
                elif stdout_line.startswith("debug"):
                    self.debug_text.insert(tk.END, "Debug", "debug")
                    self.debug_text.insert(tk.END, stdout_line[5:], "normal")
                elif stdout_line.startswith("error"):
                    self.debug_text.insert(tk.END, "Error", "error")
                    self.debug_text.insert(tk.END, stdout_line[5:], "normal")
                else:
                    self.debug_text.insert(tk.END, stdout_line, "normal")

                self.debug_text.see(tk.END)  # Scroll to the end of the text widget

    def read_process_error(self):
        process = self.process
        while process and process.poll() is None:
            stderr_line = process.stderr.readline()
            stderr_line = self.strip_ansi_codes(stderr_line)
            if stderr_line:
                self.debug_text.insert(tk.END, "Error: ", "error")
                self.debug_text.insert(tk.END, stderr_line, "normal")
                self.debug_text.see(tk.END)

    def stop_external_script(self):
        if self.process:
            # self.send_signal(signal.SIGINT)  # Terminate the subprocess
            # self.process.wait()  # Terminate the subprocess
            self.process.kill()  # Terminate the subprocess (@TODO check why terminate doesn't work on linux, windows does the same for both anyway)
            self.process.wait()
            self.process = None
        if self.thread_process_stdout:
            if self.thread_process_stdout.is_alive():
                self.thread_process_stdout.join(timeout=1)  # Wait for the thread to complete
            self.thread_process_stdout = None
        if self.thread_process_stderr:
            if self.thread_process_stderr.is_alive():
                self.thread_process_stderr.join(timeout=1)  # Wait for the thread to complete
            self.thread_process_stderr = None
        self.debug_text.insert(tk.END, "Elite Dangerous AI Integration stopped.\n")
        self.debug_text.see(tk.END)
        self.stop_button.pack_forget()
        self.debug_frame.pack_forget()
        self.main_frame.pack(padx=20, pady=20)
        self.start_button.pack()

    def get_default_microphone_name(self) -> str:
        p = pyaudio.PyAudio()
        name = p.get_default_input_device_info()['name']
        return (name + '...') if len(name) == 31 else name

    def shutdown(self):
        if self.process:
            self.process.terminate()  # Terminate the subprocess


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
    app.shutdown()
