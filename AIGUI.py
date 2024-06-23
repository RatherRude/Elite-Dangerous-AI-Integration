import tkinter as tk
from tkinter import messagebox
import json, subprocess, os, signal
from pathlib import Path
from threading import Thread
from queue import Queue
from typing import Dict

class VerticalScrolledFrame(tk.Frame):
    """A pure Tkinter scrollable frame that actually works!
    * Use the 'interior' attribute to place widgets inside the scrollable frame.
    * Construct and pack/place/grid normally.
    * This frame only allows vertical scrolling.
    """
    def __init__(self, outer_frame, *args, **kw):
        # base class initialization
        tk.Frame.__init__(self, outer_frame)

        scrollbar = tk.Scrollbar(self, width=16)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, expand=False)

        self.canvas = tk.Canvas(self, yscrollcommand=scrollbar.set, *args, **kw)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.inner_frame = tk.Frame(self)
        self.inner_frame.pack()

        scrollbar.config(command=self.canvas.yview)

        self.canvas.bind('<Configure>', self.__fill_canvas)

        # assign this obj (the inner frame) to the windows item of the canvas
        self.windows_item = self.canvas.create_window(0,0, window=self.inner_frame, anchor=tk.NW)


    def __fill_canvas(self, event):
        "Enlarge the windows item to the canvas width"

        canvas_width = event.width
        self.canvas.itemconfig(self.windows_item, width = canvas_width)

    def update(self):
        "Update the canvas and the scrollregion"

        self.update_idletasks()
        self.canvas.config(scrollregion=self.canvas.bbox(self.windows_item))


# List of game events categorized
game_events = {
    'Startup Events': {
        'Cargo': False, 'ClearSavedGame': False, 'LoadGame': True, 'NewCommander': False, 'Materials': False, 
        'Missions': False, 'Progress': False, 'Rank': False, 'Reputation': False, 'Statistics': False
    },
    'Powerplay Events': {
        'PowerplayCollect': True, 'PowerplayDefect': True, 'PowerplayDeliver': True, 'PowerplayFastTrack': True, 
        'PowerplayJoin': True, 'PowerplayLeave': True, 'PowerplaySalary': True, 'PowerplayVote': True, 'PowerplayVoucher': True
    },
    'Squadron Events': {
        'AppliedToSquadron': True, 'DisbandedSquadron': True, 'InvitedToSquadron': True, 'JoinedSquadron': True, 
        'KickedFromSquadron': True, 'LeftSquadron': True, 'SharedBookmarkToSquadron': True, 'SquadronCreated': True, 
        'SquadronDemotion': True, 'SquadronPromotion': True, 'SquadronStartup': True, 'WonATrophyForSquadron': True
    },
    'Exploration Events': {
        'CodexEntry': True, 'DiscoveryScan': True, 'Scan': True
    },
    'Trade Events': {
        'Trade': True, 'AsteroidCracked': True, 'BuyTradeData': True, 'CollectCargo': True, 'EjectCargo': True, 
        'MarketBuy': True, 'MarketSell': True, 'MiningRefined': True
    },
    'Station Services Events': {
        'StationServices': True, 'BuyAmmo': True, 'BuyDrones': True, 'CargoDepot': True, 'CommunityGoal': True, 
        'CommunityGoalDiscard': True, 'CommunityGoalJoin': True, 'CommunityGoalReward': True, 'CrewAssign': True, 
        'CrewFire': True, 'CrewHire': True, 'EngineerContribution': True, 'EngineerCraft': True, 'EngineerLegacyConvert': True, 
        'EngineerProgress': False, 'FetchRemoteModule': True, 'Market': True, 'MassModuleStore': True, 'MaterialTrade': True, 
        'MissionAbandoned': True, 'MissionAccepted': True, 'MissionCompleted': True, 'MissionFailed': True, 
        'MissionRedirected': True, 'ModuleBuy': True, 'ModuleRetrieve': True, 'ModuleSell': True, 'ModuleSellRemote': True, 
        'ModuleStore': True, 'ModuleSwap': True, 'Outfitting': True, 'PayBounties': True, 'PayFines': True, 'PayLegacyFines': True, 
        'RedeemVoucher': True, 'RefuelAll': True, 'RefuelPartial': True, 'Repair': True, 'RepairAll': True, 'RestockVehicle': True, 
        'ScientificResearch': True, 'Shipyard': True, 'ShipyardBuy': True, 'ShipyardNew': False, 'ShipyardSell': True, 
        'ShipyardTransfer': True, 'ShipyardSwap': True, 'StoredModules': False, 'StoredShips': False, 'TechnologyBroker': True, 
        'ClearImpound': True, 'Touchdown': True, 'Undocked': True, 'Docked': True, 'DockingRequested': True, 'DockingGranted': True, 
        'DockingDenied': True, 'DockingComplete': True, 'DockingTimeout': True
    },
    'Fleet Carrier Events': {
        'CarrierJump': True, 'CarrierBuy': True, 'CarrierStats': True, 'CarrierJumpRequest': True, 'CarrierDecommission': True, 
        'CarrierCancelDecommission': True, 'CarrierBankTransfer': True, 'CarrierDepositFuel': True, 'CarrierCrewServices': True, 
        'CarrierFinance': True, 'CarrierShipPack': True, 'CarrierModulePack': True, 'CarrierTradeOrder': True, 
        'CarrierDockingPermission': True, 'CarrierNameChanged': True, 'CarrierJumpCancelled': True
    },
    'Odyssey Events': {
        'Backpack': False, 'BackpackChange': True, 'BookDropship': True, 'BookTaxi': True, 'BuyMicroResources': True, 
        'BuySuit': True, 'BuyWeapon': True, 'CancelDropship': True, 'CancelTaxi': True, 'CollectItems': False, 'CreateSuitLoadout': True, 
        'DeleteSuitLoadout': True, 'Disembark': True, 'DropItems': True, 'DropShipDeploy': True, 'Embark': True, 'FCMaterials': True, 
        'LoadoutEquipModule': True, 'LoadoutRemoveModule': True, 'RenameSuitLoadout': True, 'ScanOrganic': True, 
        'SellMicroResources': True, 'SellOrganicData': True, 'SellWeapon': True, 'ShipLocker': False, 'SwitchSuitLoadout': True, 
        'TransferMicroResources': True, 'TradeMicroResources': True, 'UpgradeSuit': True, 'UpgradeWeapon': True, 'UseConsumable': True
    },
    'Other Events': {
        'AfmuRepairs': True, 'ApproachSettlement': True, 'ChangeCrewRole': True, 'CockpitBreached': True, 'CommitCrime': True, 
        'Continued': True, 'CrewLaunchFighter': True, 'CrewMemberJoins': True, 'CrewMemberQuits': True, 'CrewMemberRoleChange': True, 
        'CrimeVictim': True, 'DatalinkScan': True, 'DatalinkVoucher': True, 'DataScanned': True, 'DockFighter': True, 'DockSRV': True, 
        'EndCrewSession': True, 'FighterRebuilt': True, 'FuelScoop': True, 'Friends': True, 'JetConeBoost': True, 'JetConeDamage': True, 
        'JoinACrew': True, 'KickCrewMember': True, 'LaunchDrone': True, 'LaunchFighter': True, 'LaunchSRV': True, 'ModuleInfo': False, 
        'Music': False, 'NpcCrewPaidWage': False, 'NpcCrewRank': True, 'Promotion': True, 'ProspectedAsteroid': True, 'QuitACrew': True, 
        'RebootRepair': True, 'ReceiveText': True, 'RepairDrone': True, 'ReservoirReplenished': False, 'Resurrect': True, 'Scanned': True, 
        'SelfDestruct': True, 'SendText': True, 'Shutdown': True, 'Synthesis': True, 'SystemsShutdown': True, 'USSDrop': True, 'VehicleSwitch': True, 
        'WingAdd': True, 'WingInvite': True, 'WingJoin': True, 'WingLeave': True, 'CargoTransfer': True, 'SupercruiseDestinationDrop': True
    }
}

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Elite Dangerous AI Integration")
        root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.check_vars = {}

        self.key_binding = None

        self.process = None
        self.output_queue = Queue()
        self.read_thread = None
        # Load initial data from JSON file if exists
        self.data = self.load_data()

        # Background Image
        try:
            background_image = tk.PhotoImage(file="screen/EDAI_logo.png")
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
        self.ptt_checkbox = tk.Checkbutton(self.main_frame, text="Enabled", variable=self.ptt_var)
        self.ptt_checkbox.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        tk.Label(self.main_frame, text="Uses automatic voice detection if not enabled", font="Arial 10 italic").grid(row=3, column=1, sticky=tk.W, padx=80, pady=5)

        self.pptButton = tk.Button(self.main_frame, text="Key Binding: Press any key", font=('Arial', 10))
        self.pptButton.grid(row=3, column=1, sticky=tk.W, padx=(360, 10), pady=5)
        self.pptButton.bind("<Button-1>", self.on_label_click)

        # Continue Conversation
        tk.Label(self.main_frame, text="Resume Chat:", font=('Arial', 10)).grid(row=4, column=0, sticky=tk.W)
        # Conversation (Checkbox)
        self.continue_conversation_var = tk.BooleanVar()
        self.continue_conversation_var.set(True)  # Default value
        self.continue_conversation_checkbox = tk.Checkbutton(self.main_frame, text="Enabled", variable=self.continue_conversation_var)
        self.continue_conversation_checkbox.grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)
        tk.Label(self.main_frame, text="Resumes previous conversation if enabled", font="Arial 10 italic").grid(row=4, column=1, sticky=tk.W, padx=80, pady=5)

        self.game_events_frame = VerticalScrolledFrame(self.main_frame, bg='lightgrey', bd=1, width=600)
        self.game_events_frame.grid(row=5, column=0, columnspan=2, sticky="")
        self.game_events_save_cb = self.populate_game_events_frame(self.game_events_frame.inner_frame, self.data['game_events'])
        self.game_events_frame.update() # update scrollable area
        self.game_events_frame.grid_remove()  # Initially hide

        # AI Geeks Section (Initially hidden)
        self.ai_geeks_frame = VerticalScrolledFrame(self.main_frame, bg='lightgrey', bd=1, width=600)
        self.ai_geeks_frame.grid(row=5, column=0, columnspan=2)
        self.ai_geeks_frame.grid_remove()  # Initially hide

        # Disclaimer
        tk.Label(self.ai_geeks_frame.inner_frame, text="None of the AI Geek options are required.", font="Helvetica 12 bold").grid(row=0, column=0, columnspan=2, sticky="")

        # AI Geeks Section (Left Side)
        self.ai_geeks_left_frame = tk.Frame(self.ai_geeks_frame.inner_frame)
        self.ai_geeks_left_frame.grid(row=1, column=0, padx=10, sticky=tk.W)

        # AI Geeks Section (Right Side)
        self.ai_geeks_right_frame = tk.Frame(self.ai_geeks_frame.inner_frame)
        self.ai_geeks_right_frame.grid(row=2, column=0, padx=10, sticky=tk.E)

        # LLM Model Name
        tk.Label(self.ai_geeks_left_frame, text="LLM Model Name:").grid(row=1, column=0, sticky=tk.W)
        self.llm_model_name = tk.Entry(self.ai_geeks_left_frame, width=50)
        self.llm_model_name.grid(row=1, column=1, padx=10, pady=5)

        ## Alternative LLM (Checkbox)
        #self.alternative_llm_var = tk.BooleanVar()
        #self.alternative_llm_var.set(False)  # Default value
        #self.alternative_llm_checkbox = tk.Checkbutton(self.ai_geeks_left_frame, text="Alternative LLM", variable=self.alternative_llm_var)
        #self.alternative_llm_checkbox.grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)

        # LLM Endpoint
        tk.Label(self.ai_geeks_left_frame, text="LLM Endpoint:").grid(row=2, column=0, sticky=tk.W)
        self.llm_endpoint = tk.Entry(self.ai_geeks_left_frame, width=50)
        self.llm_endpoint.grid(row=2, column=1, padx=10, pady=5)

        # LLM API Key
        tk.Label(self.ai_geeks_left_frame, text="LLM API Key:").grid(row=3, column=0, sticky=tk.W)
        self.llm_api_key = tk.Entry(self.ai_geeks_left_frame, show='*', width=50)
        self.llm_api_key.grid(row=3, column=1, padx=10, pady=5)

        # Function Calling (Checkbox)
        self.tools_var = tk.BooleanVar()
        self.tools_var.set(True)  # Default value
        self.tools_checkbox = tk.Checkbutton(self.ai_geeks_left_frame, text="Function Calling (default: on)", variable=self.tools_var)
        self.tools_checkbox.grid(row=4, column=0, padx=10, pady=10, sticky=tk.W)

        ## STT Model
        tk.Label(self.ai_geeks_right_frame, text="STT Model Name:").grid(row=5, column=0, sticky=tk.W)
        self.stt_model_name = tk.Entry(self.ai_geeks_right_frame, width=50)
        self.stt_model_name.grid(row=5, column=1, padx=10, pady=5)

        ## STT Endpoint
        tk.Label(self.ai_geeks_right_frame, text="STT Endpoint:").grid(row=6, column=0, sticky=tk.W)
        self.stt_endpoint = tk.Entry(self.ai_geeks_right_frame, width=50)
        self.stt_endpoint.grid(row=6, column=1, padx=10, pady=5)

        ## STT API Key
        tk.Label(self.ai_geeks_right_frame, text="STT API Key:").grid(row=7, column=0, sticky=tk.W)
        self.stt_api_key = tk.Entry(self.ai_geeks_right_frame, show='*', width=50)
        self.stt_api_key.grid(row=7, column=1, padx=10, pady=5)

        # Alternative STT (Checkbox)
        self.alternative_stt_var = tk.BooleanVar()
        self.alternative_stt_var.set(False)  # Default value
        self.alternative_stt_checkbox = tk.Checkbutton(self.ai_geeks_right_frame, text="Local STT (pre-installed whisper-medium)", variable=self.alternative_stt_var)
        self.alternative_stt_checkbox.grid(row=8, column=0, padx=10, pady=10, sticky=tk.W)

        ## TTS Model
        tk.Label(self.ai_geeks_right_frame, text="TTS Model Name:").grid(row=9, column=0, sticky=tk.W)
        self.tts_model_name = tk.Entry(self.ai_geeks_right_frame, width=50)
        self.tts_model_name.grid(row=9, column=1, padx=10, pady=5)

        ## TTS Endpoint
        tk.Label(self.ai_geeks_right_frame, text="TTS Endpoint:").grid(row=10, column=0, sticky=tk.W)
        self.tts_endpoint = tk.Entry(self.ai_geeks_right_frame, width=50)
        self.tts_endpoint.grid(row=10, column=1, padx=10, pady=5)

        ## TTS API Key
        tk.Label(self.ai_geeks_right_frame, text="TTS API Key:").grid(row=11, column=0, sticky=tk.W)
        self.tts_api_key = tk.Entry(self.ai_geeks_right_frame, show='*', width=50)
        self.tts_api_key.grid(row=11, column=1, padx=10, pady=5)

        # TTS Voice
        tk.Label(self.ai_geeks_right_frame, text="TTS Voice:").grid(row=12, column=0, sticky=tk.W)
        self.tts_voice = tk.Entry(self.ai_geeks_right_frame, width=50)
        self.tts_voice.grid(row=12, column=1, padx=10, pady=5)

        # Alternative TTS (Checkbox)
        self.alternative_tts_var = tk.BooleanVar()
        self.alternative_tts_var.set(False)  # Default value
        self.alternative_tts_checkbox = tk.Checkbutton(self.ai_geeks_right_frame, text="Local TTS (pre-installed OS Voices)", variable=self.alternative_tts_var)
        self.alternative_tts_checkbox.grid(row=13, column=0, padx=10, pady=10, sticky=tk.W)

        ## Vision Model
        tk.Label(self.ai_geeks_left_frame, text="Vision Model Name:").grid(row=14, column=0, sticky=tk.W)
        self.vision_model_name = tk.Entry(self.ai_geeks_left_frame, width=50)
        self.vision_model_name.grid(row=14, column=1, padx=10, pady=5)
#
        ## Vision Model Endpoint
        tk.Label(self.ai_geeks_left_frame, text="Vision Model Endpoint:").grid(row=15, column=0, sticky=tk.W)
        self.vision_endpoint = tk.Entry(self.ai_geeks_left_frame, width=50)
        self.vision_endpoint.grid(row=15, column=1, padx=10, pady=5)
#
        ## Vision Model API Key
        tk.Label(self.ai_geeks_left_frame, text="Vision Model API Key:").grid(row=16, column=0, sticky=tk.W)
        self.vision_api_key = tk.Entry(self.ai_geeks_left_frame, show='*', width=50)
        self.vision_api_key.grid(row=16, column=1, padx=10, pady=5)

        # Vision Capabilities (Checkbox)
        self.vision_var = tk.BooleanVar()
        self.vision_var.set(True)  # Default value
        self.vision_checkbox = tk.Checkbutton(self.ai_geeks_left_frame, text="Vision Capabilities (default: on)", variable=self.vision_var)
        self.vision_checkbox.grid(row=17, column=0, padx=10, pady=10, sticky=tk.W)

        self.ai_geeks_frame.update()

        # Toggle Section Button
        self.toggle_ai_geeks_section_button = tk.Button(self.main_frame, text="Show AI Geeks Section", command=self.toggle_ai_geeks_section)
        self.toggle_ai_geeks_section_button.grid(row=5, column=0, columnspan=2, pady=10, padx=(150, 0), sticky="")

        # Toggle Section Button
        self.toggle_game_events_section_button = tk.Button(self.main_frame, text="Show Game Events Section", command=self.toggle_game_events_section)
        self.toggle_game_events_section_button.grid(row=5, column=0, columnspan=2, pady=10, padx=(0, 150), sticky="")

        # Debug Frame and Text Widget
        self.debug_frame = tk.Frame(root, bg='black', bd=1)  # White background for visibility
        self.debug_frame.pack(side=tk.TOP, padx=20, pady=20)

        tk.Label(self.debug_frame, text="Debug Output:").pack(anchor=tk.W)
        self.debug_text = tk.Text(self.debug_frame, width=100, height=25, bg='black')
        self.debug_text.tag_configure("normal", foreground="white", font="Helvetica 12")
        self.debug_text.tag_configure("human", foreground="red", font="Helvetica 12 bold")
        self.debug_text.tag_configure("ai", foreground="blue", font="Helvetica 12 bold")
        self.debug_text.tag_configure("action", foreground="yellow", font="Helvetica 12 bold")
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

        #category_label = tk.Label(self.ai_geeks_frame, text="category", font=('Arial', 14, 'bold'))
        #        var = tk.BooleanVar(value=self.check_vars.get(event, event not in default_off_events))
        #        chk = tk.Checkbutton(self.ai_geeks_frame, text=event, variable=var)

        #for category, events in game_events.items():
        #    category_label = tk.Label(self.ai_geeks_frame, text=category, font=('Arial', 14, 'bold'))
        #    for event in events:
        #        var = tk.BooleanVar(value=self.check_vars.get(event, event not in default_off_events))
        #        chk = tk.Checkbutton(self.ai_geeks_frame, text=event, variable=var)
        #        self.check_vars[event] = var

        # Initialize fields with loaded data
        self.update_fields()

        # Process handle for subprocess
        self.process = None

    def populate_game_events_frame(self, frame: tk.Frame, game_events: Dict[str, Dict[str, bool]]):
        category_values: Dict[str, Dict[str, tk.BooleanVar]] = {}
        rowCounter = 0
        for category, events in game_events.items():
            category_label = tk.Label(frame, text=category, font=('Arial', 14, 'bold'))
            category_label.grid(row=rowCounter, column=0, sticky=tk.W)
            category_values[category] = {}

            for event, state in events.items():
                rowCounter += 1
                var = tk.BooleanVar(value=state)
                chk = tk.Checkbutton(frame, text=event, variable=var)
                chk.grid(row=rowCounter, column=1, sticky=tk.W)
                category_values[category][event] = var


        return lambda: {category: {
            event: state.get() for event, state in events.items()
        } for category, events in category_values.items()}

    def on_closing(self):
        self.save_settings()
        root.destroy()

    def on_label_click(self, event):
        self.pptButton.config(text="Press a key...")
        self.root.bind("<KeyPress>", self.on_key_press)

    def on_key_press(self, event):
        self.key_binding = event.keysym
        #self.save_key_binding()
        self.update_label_text()
        self.root.unbind("<KeyPress>")

    def update_label_text(self):
        if self.key_binding:
            self.pptButton.config(text=f"Key Binding: {self.key_binding}")
        else:
            self.pptButton.config(text="Key Binding: Press any key")

    def load_data(self):
        try:
            with open('config.json', 'r') as file:
                # @ToDo load default values for keys that are missing in json file
                data = json.load(file)
        except FileNotFoundError:
            data = {
                'commander_name': "",
                'character':
                "I am Commander {commander_name}. You are the onboard AI of my starship. \n" +
                "You will be addressed as 'Computer'. Acknowledge given orders. \n" +
                "You possess extensive knowledge and can provide detailed and accurate information on a wide range of topics, " +
                "including galactic navigation, ship status, the current system, and more. \n" +
                "Do not inform about my ship status and my location unless it's relevant or requested by me. \n" +
                "Guide and support me with witty and intelligent commentary. \n" +
                "Provide clear mission briefings, sarcastic comments, and humorous observations. Answer within 3 sentences. \n" +
                "Advance the narrative involving bounty hunting. \n" +
                "I am a broke bounty hunter who can barely pay the fuel.",
                'api_key': "",
                'alternative_stt_var': False,
                'alternative_tts_var': False,
                'tools_var': True,
                'vision_var': True,
                'ptt_var': False,
                'continue_conversation_var': True,
                'llm_model_name': "gpt-4o",
                'llm_endpoint': "https://api.openai.com/v1",
                'llm_api_key': "",
                'tts_voice': "nova",
                'key_binding': None,
                'vision_model_name': "gpt-4o",
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
        return data

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
        self.data['key_binding'] = self.key_binding
        self.data['game_events'] = self.game_events_save_cb()

        with open('config.json', 'w') as file:
            json.dump(self.data, file, indent=4)

        #messagebox.showinfo("Settings Saved", "Settings have been saved successfully.")

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
        self.key_binding = self.data['key_binding']

        self.update_label_text()

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

    def start_external_script(self):
        self.save_settings()
        self.debug_text.delete('1.0', tk.END)
        self.debug_text.insert(tk.END, "Starting Elite Dangerous AI Integration...\n", "normal")
        #self.debug_text.update_idletasks()

        try:
            # Example script execution
            self.process = subprocess.Popen(['pythonw', 'Chat.py'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, universal_newlines=True)
            self.debug_frame.pack()
            self.main_frame.pack_forget()
            self.stop_button.pack()
            self.start_button.pack_forget()  # Hide the start button

            # Read output in a separate thread
            self.thread = Thread(target=self.read_process_output)
            self.thread.start()

        except FileNotFoundError:
            self.debug_text.insert(tk.END, "Failed to start Elite Dangerous AI Integration: File not found.\n")
            self.debug_text.see(tk.END)
        except Exception as e:
            self.debug_text.insert(tk.END, f"Failed to start Elite Dangerous AI Integration: {str(e)}\n")
            self.debug_text.see(tk.END)

    def read_process_output(self):
        while True:
            stdout_line = self.process.stdout.readline()
            if stdout_line:
                if stdout_line.startswith("CMDR"):
                    self.debug_text.insert(tk.END, stdout_line[:4], "human")
                    self.debug_text.insert(tk.END, stdout_line[4:], "normal")
                elif stdout_line.startswith("AI"):
                    self.debug_text.insert(tk.END, stdout_line[:2], "ai")
                    self.debug_text.insert(tk.END, stdout_line[2:], "normal")
                elif stdout_line.startswith("ACTION"):
                    self.debug_text.insert(tk.END, stdout_line[:6], "action")
                    self.debug_text.insert(tk.END, stdout_line[6:], "normal")
                else:
                    self.debug_text.insert(tk.END, stdout_line, "normal")

                self.debug_text.see(tk.END)  # Scroll to the end of the text widget
            else:
                break  # No more output from subprocess

    def stop_external_script(self):
        if self.process:
            #self.send_signal(signal.SIGINT)  # Terminate the subprocess
            #self.process.wait()  # Terminate the subprocess
            self.process.terminate()  # Terminate the subprocess
            self.process = None
        if self.thread:
            self.thread.join()  # Wait for the thread to complete
            self.thread = None
        self.debug_text.insert(tk.END, "Elite Dangerous AI Integration stopped.\n")
        self.debug_text.see(tk.END)
        self.stop_button.pack_forget()
        self.debug_frame.pack_forget()
        self.main_frame.pack(padx=20, pady=20)
        self.start_button.pack()

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()