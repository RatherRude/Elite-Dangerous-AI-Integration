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
from .directinput import (
    PressKey,
    PressMouseButton,
    ReleaseKey,
    ReleaseMouseButton,
    ScrollMouseWheel,
    resolve_layout_key_name,
    get_layout_key_character,
    load_keyboard_layout,
)

"""
Description:  Pulls the keybindings for specific controls from the ED Key Bindings file, this class also
  has method for sending a key to the display that has focus (so must have ED with focus)

Constraints:  This file will use the latest modified *.binds file
"""


class UnresolvedKeyError(KeyError):
    def __init__(self, key_name: str, role: str, reason: str):
        super().__init__(reason)
        self.key_name = key_name
        self.role = role


@final
class EDKeys:
    def __init__(self, appdata_path: str, prefer_primary_bindings: bool = False):
        self.appdata_path = appdata_path
        self.prefer_primary_bindings = prefer_primary_bindings
        self.key_mod_delay = 0.010
        self.key_default_delay = 0.200
        self.key_repeat_delay = 0.100
        self.mouse_button_map = {
            "Mouse_1": "left",
            "Mouse_2": "right",
            "Mouse_3": "middle",
            "Mouse_4": "x1",
            "Mouse_5": "x2",
        }
        self.mouse_wheel_map = {
            "Pos_Mouse_ZAxis": 1,
            "Neg_Mouse_ZAxis": -1,
        }

        if platform.system() == "Windows":
            self.keymap: dict[str, int | str] = json.load(open(get_asset_path("keymap.json")))
        elif platform.system() == "Darwin":
            self.keymap: dict[str, int | str] = json.load(
                open(get_asset_path("keymap_pynput_macos.json"))
            )
        else:
            self.keymap: dict[str, int | str] = json.load(
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
            "CyclePreviousSubsystem",
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
            "UpThrustButton",
            "UseBoostJuice",
        ]
        self.collision_candidates = ["CamTranslateRight", "CamTranslateForward"]

        self.latest_bindings_file = None
        self.keyboard_layout = None
        self.keyboard_layout_name: str | None = None
        self.latest_bindings_mtime = None
        self.missing_keys = []
        self.unsupported_keys = []
        self.unresolved_keys: list[dict[str, Any]] = []
        self.mapping_warnings: list[dict[str, Any]] = []
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

        emit_message(
            "keybinds",
            missing=self.missing_keys,
            collisions=collisions,
            unsupported=self.unsupported_keys,
            unresolved_keys=self.unresolved_keys,
            mapping_warnings=self.mapping_warnings,
            start_mismatch=self.start_values_mismatch,
            start_values=self.latest_start_values,
        )

    def get_bindings(self) -> dict[str, Any]:
        """Returns a dict struct with the direct input equivalent of the necessary elite keybindings"""
        direct_input_keys = {}
        unsupported_keys = set()
        unresolved_keys = []
        mapping_warnings = []
        latest_bindings, _ = self.get_latest_keybinds()
        if not latest_bindings:
            self.keyboard_layout = None
            self.keyboard_layout_name = None
            self.unsupported_keys = []
            self.unresolved_keys = []
            self.mapping_warnings = []
            return {}
        bindings_tree = parse(latest_bindings)
        bindings_root = bindings_tree.getroot()

        keyboard_layout = None
        self.keyboard_layout_name = (bindings_root.findtext("KeyboardLayout") or "en-US").strip() or "en-US"
        if platform.system() == "Windows":
            try:
                keyboard_layout = load_keyboard_layout(self.keyboard_layout_name)
            except ValueError as exc:
                log("error", "Unable to load game keyboard layout; using fixed keymap", exc)
        self.keyboard_layout = keyboard_layout

        for item in bindings_root:
            selected_binding = self._select_binding(item)
            if selected_binding is None:
                continue

            binding: None | dict[str, Any] = None
            binding_warnings = []
            try:
                binding = self._prepare_binding(selected_binding, binding_warnings)
            except KeyError as exc:
                unsupported_keys.add(item.tag)
                key_name = exc.key_name if isinstance(exc, UnresolvedKeyError) else selected_binding.attrib["Key"]
                unresolved_keys.append(self._binding_key_report(item.tag, selected_binding, {
                    "key": key_name,
                    "role": exc.role if isinstance(exc, UnresolvedKeyError) else "key",
                    "character": get_layout_key_character(key_name),
                    "reason": str(exc.args[0]),
                }))
                log("error", f"Unrecognised key for bind {item.tag!r}", exc)
            mapping_warnings.extend(
                self._binding_key_report(item.tag, selected_binding, warning)
                for warning in binding_warnings
            )
            if binding is not None:
                direct_input_keys[item.tag] = binding

        self.unsupported_keys = sorted(unsupported_keys)
        self.unresolved_keys = unresolved_keys
        self.mapping_warnings = mapping_warnings
        if len(list(direct_input_keys.keys())) < 1:
            return {}
        else:
            return direct_input_keys

    def _select_binding(self, item) -> Any | None:
        binding_elements = [
            binding
            for binding in item
            if binding.tag in ("Primary", "Secondary")
            and binding.attrib.get("Device", "").strip() in ("Keyboard", "Mouse")
            and binding.attrib.get("Key")
        ]

        if not binding_elements:
            return None

        keyboard_binding = self._select_preferred_binding(
            [
                binding
                for binding in binding_elements
                if binding.attrib.get("Device", "").strip() == "Keyboard"
            ]
        )
        if keyboard_binding is not None:
            return keyboard_binding

        return self._select_preferred_binding(
            [
                binding
                for binding in binding_elements
                if binding.attrib.get("Device", "").strip() == "Mouse"
            ]
        )

    def _select_preferred_binding(self, bindings: list[Any]) -> Any | None:
        if not bindings:
            return None

        preferred_order = (
            ["Primary", "Secondary"]
            if self.prefer_primary_bindings
            else ["Secondary", "Primary"]
        )
        for tag in preferred_order:
            for binding in bindings:
                if binding.tag == tag:
                    return binding

        return bindings[0]

    def _binding_key_report(self, action: str, selected_binding, issue: dict[str, Any]) -> dict[str, Any]:
        return {
            "action": action,
            "binding": selected_binding.tag,
            "layout": self.keyboard_layout_name,
            "platform": platform.system(),
            "modifiers": [mod.attrib.get("Key", "") for mod in selected_binding if mod.tag == "Modifier"],
            **issue,
        }

    def _prepare_binding(self, selected_binding, mapping_warnings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        key = selected_binding.attrib["Key"]
        device = selected_binding.attrib["Device"].strip()
        mods = []
        hold = None
        for modifier in selected_binding:
            if (
                modifier.tag == "Modifier"
                and modifier.attrib.get("Device", "").strip() == "Keyboard"
            ):
                mods.append(modifier.attrib["Key"])
            elif modifier.tag == "Hold":
                hold = True

        # Elite records physical keys and explicit modifiers, not text-entry chords.
        # Preserve modifier order and left/right identities exactly as saved.
        resolved_mods = [self._resolve_binding_key(mod, "modifier", mapping_warnings) for mod in mods]

        if device == "Keyboard":
            code = self._resolve_binding_key(key, "key", mapping_warnings)
            binding = {"key": code, "mods": resolved_mods}
        elif key in self.mouse_button_map:
            binding = {"mods": resolved_mods}
            binding["type"] = "mouse_button"
            binding["button"] = self.mouse_button_map[key]
        elif key in self.mouse_wheel_map:
            binding = {"mods": resolved_mods}
            binding["type"] = "mouse_wheel"
            binding["clicks"] = self.mouse_wheel_map[key]
        else:
            raise KeyError(key)

        if hold is not None:
            binding["hold"] = True

        return binding

    def _resolve_binding_key(self, key_name: str, role: str, mapping_warnings: list[dict[str, Any]] | None = None) -> int | str:
        character = get_layout_key_character(key_name)
        try:
            if self.keyboard_layout is not None and character is not None:
                resolved = resolve_layout_key_name(key_name, self.keyboard_layout)
                if resolved.shift_state and mapping_warnings is not None:
                    mapping_warnings.append({
                        "key": key_name,
                        "role": role,
                        "character": character,
                        "native_shift_state": resolved.shift_state,
                        "reason": (
                            f"Windows reports unexpected text-entry modifiers (mask {resolved.shift_state:#04x}) "
                            f"for {character!r}. Verify the key name and game layout. "
                            "Only the explicit .binds modifiers will be sent."
                        ),
                    })
                return resolved.scan_code
            if platform.system() != "Windows" and key_name not in self.keymap and character is not None:
                return character
            if key_name not in self.keymap:
                raise KeyError(f"Unknown key name {key_name!r}; no native mapping is available.")
            return self.keymap[key_name]
        except (KeyError, ValueError) as exc:
            raise UnresolvedKeyError(key_name, role, str(exc.args[0])) from exc

    def get_latest_keybinds(self):
        path_bindings = os.path.join(self.appdata_path + "/", "Options", "Bindings")
        try:
            list_of_bindings = [
                join(path_bindings, f)
                for f in listdir(path_bindings)
                if isfile(join(path_bindings, f)) and f.endswith(".binds")
            ]
        except FileNotFoundError as e:
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
                f"Unable to retrieve keybinding for {key_name}. Advise user to check game settings for keyboard or mouse bindings."
            )
        if "key" not in binding and "type" not in binding:
            raise Exception(f"Unsupported key {key_name}.")

        for i in range(repeat):
            if state is None or state == 1:
                for mod in binding["mods"]:
                    PressKey(mod)
                    sleep(self.key_mod_delay)

                self._press_binding(binding)

            if state is None:
                if hold:
                    sleep(hold)
                else:
                    sleep(self.key_default_delay)

            if "hold" in binding:
                sleep(0.1)

            if state is None or state == 0:
                self._release_binding(binding)

                for mod in binding["mods"]:
                    sleep(self.key_mod_delay)
                    ReleaseKey(mod)

            if repeat_delay:
                sleep(repeat_delay)
            else:
                sleep(self.key_repeat_delay)

    def _press_binding(self, binding: dict[str, Any]) -> None:
        if "key" in binding:
            PressKey(binding["key"])
        elif binding.get("type") == "mouse_button":
            PressMouseButton(binding["button"])
        elif binding.get("type") == "mouse_wheel":
            ScrollMouseWheel(binding["clicks"])

    def _release_binding(self, binding: dict[str, Any]) -> None:
        if "key" in binding:
            ReleaseKey(binding["key"])
        elif binding.get("type") == "mouse_button":
            ReleaseMouseButton(binding["button"])

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
