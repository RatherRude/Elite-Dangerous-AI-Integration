import json
from os import listdir
import os
from os.path import getmtime, isfile, join
import platform
from time import sleep
import traceback
from typing import Any, Literal, final
from xml.etree.ElementTree import parse
import threading

from .Logger import log
from .UI import emit_message
from .Config import get_asset_path
from .directinput import PressKey, ReleaseKey

"""
Description:  Pulls the keybindings for specific controls from the ED Key Bindings file, this class also
  has method for sending a key to the display that has focus (so must have ED with focus)

Constraints:  This file will use the latest modified *.binds file
"""


@final
class EDKeys:
    def __init__(self, appdata_path: str, prefer_primary_bindings: bool = False):
        self.appdata_path = appdata_path
        self.prefer_primary_bindings = prefer_primary_bindings
        self.key_mod_delay = 0.010
        self.key_default_delay = 0.200
        self.key_repeat_delay = 0.100

        if platform.system() == "Windows":
            self.keymap: dict[str, int] = json.load(open(get_asset_path("keymap.json")))
        else:
            self.keymap: dict[str, int] = json.load(
                open(get_asset_path("keymap_pynput.json"))
            )

        self.required_keys = [
            "PrimaryFire",
            "SecondaryFire",
            "HyperSuperCombination",
            "Supercruise",
            "Hyperspace",
            "TargetNextRouteSystem",
            "SetSpeedZero",
            "SetSpeed25",
            "SetSpeed50",
            "SetSpeed75",
            "SetSpeed100",
            "SetSpeedMinus100",
            "SetSpeedMinus25",
            "SetSpeedMinus50",
            "SetSpeedMinus75",
            "DeployHeatSink",
            "DeployHardpointToggle",
            "IncreaseEnginesPower",
            "IncreaseWeaponsPower",
            "IncreaseSystemsPower",
            "ResetPowerDistribution",
            "GalaxyMapOpen",
            "SystemMapOpen",
            "CycleNextTarget",
            "CyclePreviousTarget",
            "CycleNextHostileTarget",
            "CyclePreviousHostileTarget",
            "TargetWingman0",
            "TargetWingman1",
            "TargetWingman2",
            "SelectTargetsTarget",
            "WingNavLock",
            "CycleNextSubsystem",
            "CycleFireGroupNext",
            "CycleFireGroupPrevious",
            "PlayerHUDModeToggle",
            "ShipSpotLightToggle",
            "EjectAllCargo",
            "LandingGearToggle",
            "UseShieldCell",
            "FireChaffLauncher",
            "NightVisionToggle",
            "RecallDismissShip",
            "SelectHighestThreat",
            "ToggleCargoScoop",
            "ChargeECM",
            "TriggerFieldNeutraliser",
            "CycleNextPanel",
            "CyclePreviousPanel",
            "FocusLeftPanel",
            "FocusRadarPanel",
            "UI_Up",
            "UI_Down",
            "UI_Left",
            "UI_Right",
            "UI_Select",
            "UI_Back",
            "CamZoomOut",
            "CamZoomIn",
            "UIFocus",
            "QuickCommsPanel",
            "QuickCommsPanel_Buggy",
            "QuickCommsPanel_Humanoid",
            "ToggleDriveAssist",
            "BuggyPrimaryFireButton",
            "BuggySecondaryFireButton",
            "AutoBreakBuggyButton",
            "HeadlightsBuggyButton",
            "ToggleBuggyTurretButton",
            "SelectTarget_Buggy",
            "IncreaseEnginesPower_Buggy",
            "IncreaseWeaponsPower_Buggy",
            "IncreaseSystemsPower_Buggy",
            "ResetPowerDistribution_Buggy",
            "ToggleCargoScoop_Buggy",
            "EjectAllCargo_Buggy",
            "RecallDismissShip",
            "GalaxyMapOpen_Buggy",
            "SystemMapOpen_Buggy",
            "OrderDefensiveBehaviour",
            "OrderAggressiveBehaviour",
            "OrderFocusTarget",
            "OrderHoldFire",
            "OrderHoldPosition",
            "OrderFollow",
            "OrderRequestDock",
            "HumanoidPrimaryInteractButton",
            "HumanoidSecondaryInteractButton",
            "HumanoidSelectPrimaryWeaponButton",
            "HumanoidSelectSecondaryWeaponButton",
            "HumanoidSelectUtilityWeaponButton",
            "HumanoidSwitchToRechargeTool",
            "HumanoidSwitchToCompAnalyser",
            "HumanoidSwitchToSuitTool",
            "HumanoidHideWeaponButton",
            "HumanoidSelectFragGrenade",
            "HumanoidSelectEMPGrenade",
            "HumanoidSelectShieldGrenade",
            "HumanoidToggleFlashlightButton",
            "HumanoidToggleNightVisionButton",
            "HumanoidToggleShieldsButton",
            "HumanoidClearAuthorityLevel",
            "HumanoidHealthPack",
            "HumanoidBattery",
            "GalaxyMapOpen_Humanoid",
            "SystemMapOpen_Humanoid",
            "HumanoidOpenAccessPanelButton",
        ]
        self.collision_candidates = ["CamTranslateRight", "CamTranslateForward"]

        self.latest_bindings_file = None
        self.latest_bindings_mtime = None
        self.missing_keys = []
        self.unsupported_keys = []
        self.latest_start_file = None
        self.latest_start_mtime = None
        self.latest_start_values: list[str] = []
        self.start_values_mismatch = False
        self.selected_start_profile = None
        self.start_profile_bindings_missing = False
        self.watch_thread = threading.Thread(target=self._watch_bindings_thread, daemon=True)
        self.watch_thread.start()

        self.keys = self.get_bindings()
        self.check_keybind_issues()
        log(
            "debug",
            "Keybindings file found, loaded bindings from",
            self.latest_bindings_file,
        )

    def check_keybind_issues(self):
        collisions = []
        self.missing_keys = []

        for key in self.required_keys:
            if not key in self.keys:
                self.missing_keys.append(key)
            else:
                binding = self.keys[key]
                for collision_candidate in self.collision_candidates:
                    candidate_bind = self.keys.get(collision_candidate, None)
                    if (
                        collision_candidate
                        and collision_candidate != key
                        and binding == candidate_bind
                    ):
                        collisions.append([key, collision_candidate])

        start_mismatch = None
        if self.start_values_mismatch:
            start_mismatch = {
                "file": self.latest_start_file,
                "values": self.latest_start_values
            }


    def get_bindings(self) -> dict[str, Any]:
        """Returns a dict struct with the direct input equivalent of the necessary elite keybindings"""
        direct_input_keys = {}
        unsupported_keys = set()
        latest_bindings, _ = self.get_latest_keybinds()
        if not latest_bindings:
            self.unsupported_keys = []
            return {}
        bindings_tree = parse(latest_bindings)
        bindings_root = bindings_tree.getroot()

        for item in bindings_root:
            key = None
            mods = []
            hold = None
            if len(item) < 2:
                continue
            # Check primary
            primary_binding_found = False
            if (
                item[0].tag == "Primary"
                and item[0].attrib["Device"].strip() == "Keyboard"
            ):
                key = item[0].attrib["Key"]
                for modifier in item[0]:
                    if modifier.tag == "Modifier":
                        mods.append(modifier.attrib["Key"])
                    elif modifier.tag == "Hold":
                        hold = True
                primary_binding_found = True
            # Check secondary (and prefer secondary)
            prefer_secondary = (
                not self.prefer_primary_bindings or not primary_binding_found
            )
            if (
                prefer_secondary
                and item[1].tag == "Secondary"
                and item[1].attrib["Device"].strip() == "Keyboard"
            ):
                key = item[1].attrib["Key"]
                mods = []
                hold = None
                for modifier in item[1]:
                    if modifier.tag == "Modifier":
                        mods.append(modifier.attrib["Key"])
                    elif modifier.tag == "Hold":
                        hold = True
            # Prepare final binding
            if len(item) > 2:
                if item[2].tag == "ToggleOn" and item[2].attrib.get("Value") == "0":
                    continue
            binding: None | dict[str, Any] = None
            try:
                if key is not None:
                    binding = {}
                    binding["key"] = self.keymap[key]
                    binding["mods"] = []
                    for mod in mods:
                        binding["mods"].append(self.keymap[mod])
                    if hold is not None:
                        binding["hold"] = True
            except KeyError:
                unsupported_keys.add(item.tag)
                print(
                    "Unrecognised key '"
                    + (json.dumps(binding) if binding else "?")
                    + "' for bind '"
                    + item.tag
                    + "'"
                )
            if binding is not None:
                direct_input_keys[item.tag] = binding

        self.unsupported_keys = sorted(unsupported_keys)
        if len(list(direct_input_keys.keys())) < 1:
            return {}
        else:
            return direct_input_keys

    def get_latest_keybinds(self):
        path_bindings = os.path.join(self.appdata_path + "/", "Options", "Bindings")
        try:
            list_of_bindings = [join(path_bindings, f) for f in listdir(path_bindings) if
                                isfile(join(path_bindings, f)) and f.endswith('.binds')]
        except FileNotFoundError:
            return None, None

        if not list_of_bindings:
            return None, None

        start_info = self.get_latest_start_profile(path_bindings)
        start_profile = start_info["profile_name"] if start_info else None

        self.selected_start_profile = start_profile
        self.start_profile_bindings_missing = False

        if start_profile:
            matching_bindings = []
            normalized_prefix = start_profile.lower()
            for binding_path in list_of_bindings:
                filename = os.path.basename(binding_path).lower()
                if filename.startswith(f"{normalized_prefix}.") and filename.endswith(".binds"):
                    matching_bindings.append(binding_path)

            if matching_bindings:
                latest_bindings = max(matching_bindings, key=getmtime)
            else:
                self.start_profile_bindings_missing = True
                latest_bindings = max(list_of_bindings, key=getmtime)
        else:
            latest_bindings = max(list_of_bindings, key=getmtime)

        return latest_bindings, getmtime(latest_bindings)

    def get_latest_start_profile(self, path_bindings: str):
        try:
            list_of_start_files = [join(path_bindings, f) for f in listdir(path_bindings) if
                                   isfile(join(path_bindings, f)) and f.endswith('.start')]
        except FileNotFoundError:
            self.latest_start_file = None
            self.latest_start_mtime = None
            self.latest_start_values = []
            self.start_values_mismatch = False
            return None

        if not list_of_start_files:
            self.latest_start_file = None
            self.latest_start_mtime = None
            self.latest_start_values = []
            self.start_values_mismatch = False
            return None

        latest_start = max(list_of_start_files, key=getmtime)
        latest_start_mtime = getmtime(latest_start)

        lines = []
        try:
            with open(latest_start, 'r', encoding='utf-8', errors='ignore') as file:
                lines = [line.strip() for line in file.readlines()]
        except OSError:
            self.latest_start_file = latest_start
            self.latest_start_mtime = latest_start_mtime
            self.latest_start_values = []
            self.start_values_mismatch = True
            return None

        first_four = lines[:4]
        all_same = len(first_four) == 4 and len(set(first_four)) == 1 and first_four[0] != ""

        self.latest_start_file = latest_start
        self.latest_start_mtime = latest_start_mtime
        self.latest_start_values = first_four
        self.start_values_mismatch = not all_same

        if all_same:
            return {
                "profile_name": first_four[0],
                "start_file": latest_start
            }

        return None

    def send_key(self, type: Literal['Up', 'Down'], key_name:str):
        key = self.keymap.get(key_name)
        if key is None:
            raise Exception(f"Unsupported key {key_name}.")
        if type == "Up":
            ReleaseKey(key)
        else:
            PressKey(key)

    def get_collisions(self, key_name: str) -> list[str]:
        key = self.keys.get(key_name)
        collisions = []
        for k, v in self.keys.items():
            if key == v:
                collisions.append(k)
        return collisions

    def send(self, key_name, hold=None, repeat=1, repeat_delay=None, state=None):
        log("debug", "Trying to send key", key_name)
        binding = self.keys.get(key_name)
        if binding is None:
            raise Exception(
                f"Unable to retrieve keybinding for {key_name}. Advise user to check game settings for keyboard bindings."
            )
        if not "key" in binding:
            raise Exception(f"Unsupported key {key_name}.")

        for i in range(repeat):
            if state is None or state == 1:
                for mod in binding["mods"]:
                    PressKey(mod)
                    sleep(self.key_mod_delay)

                PressKey(binding["key"])

            if state is None:
                if hold:
                    sleep(hold)
                else:
                    sleep(self.key_default_delay)

            if "hold" in binding:
                sleep(0.1)

            if state is None or state == 0:
                ReleaseKey(binding["key"])

                for mod in binding["mods"]:
                    sleep(self.key_mod_delay)
                    ReleaseKey(mod)

            if repeat_delay:
                sleep(repeat_delay)
            else:
                sleep(self.key_repeat_delay)

    def _watch_bindings_thread(self):
        """Thread that monitors for changes in the keybindings file"""
        backoff = 1
        while True:
            try:
                self._watch_bindings()
            except Exception as e:
                log(
                    "error",
                    "An error occurred when monitoring keybindings file",
                    e,
                    traceback.format_exc(),
                )
                sleep(backoff)
                log("info", "Attempting to restart keybindings monitor after failure")
                backoff *= 2

    def _watch_bindings(self):
        """Monitors the keybindings file for changes and reloads when necessary"""
        while True:
            previous_start_file = self.latest_start_file
            previous_start_mtime = self.latest_start_mtime
            latest_bindings, mtime = self.get_latest_keybinds()
            start_changed = (
                previous_start_file != self.latest_start_file
                or previous_start_mtime != self.latest_start_mtime
            )

            if latest_bindings != self.latest_bindings_file or mtime != self.latest_bindings_mtime or start_changed:
                self.latest_bindings_file = latest_bindings
                self.latest_bindings_mtime = mtime
                self.keys = self.get_bindings()
                self.check_keybind_issues()
                log(
                    "debug",
                    "Keybindings file changed, reloaded bindings from",
                    self.latest_bindings_file,
                )
            sleep(1)
