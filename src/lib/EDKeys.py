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
from .Config import get_asset_path
from .directinput import PressKey, ReleaseKey

"""
Description:  Pulls the keybindings for specific controls from the ED Key Bindings file, this class also
  has method for sending a key to the display that has focus (so must have ED with focus)

Constraints:  This file will use the latest modified *.binds file
"""

@final
class EDKeys:

    def __init__(self, appdata_path: str):
        self.appdata_path = appdata_path
        self.key_mod_delay = 0.010
        self.key_default_delay = 0.200
        self.key_repeat_delay = 0.100
        
        if platform.system() == 'Windows':
            self.keymap: dict[str, int] = json.load(open(get_asset_path('keymap.json')))
        else:
            self.keymap: dict[str, int] = json.load(open(get_asset_path('keymap_pynput.json')))
        
        self.keys_to_obtain = [
            'PrimaryFire',
            'SecondaryFire',
            'HyperSuperCombination',
            'Supercruise',
            'Hyperspace',
            'TargetNextRouteSystem',
            'SetSpeedZero',
            'SetSpeed25',
            'SetSpeed50',
            'SetSpeed75',
            'SetSpeed100',
            'SetSpeedMinus100',
            'SetSpeedMinus25',
            'SetSpeedMinus50',
            'SetSpeedMinus75',
            'DeployHeatSink',
            'DeployHardpointToggle',
            'IncreaseEnginesPower',
            'IncreaseWeaponsPower',
            'IncreaseSystemsPower',
            'ResetPowerDistribution',
            'GalaxyMapOpen',
            'CamYawLeft',
            'SystemMapOpen',
            'CycleNextTarget',
            'CyclePreviousTarget',
            'CycleNextSubsystem',
            'CycleFireGroupNext',
            'CycleFireGroupPrevious',
            'PlayerHUDModeToggle',
            'ShipSpotLightToggle',
            'EjectAllCargo',
            'LandingGearToggle',
            'UseShieldCell',
            'FireChaffLauncher',
            'NightVisionToggle',
            'RecallDismissShip',
            'SelectHighestThreat',
            'ToggleCargoScoop',
            'ChargeECM',
            'CycleNextPanel',
            'CyclePreviousPanel',
            'FocusLeftPanel',
            'UI_Up',
            'UI_Down',
            'UI_Left',
            'UI_Right',
            'UI_Select',
            'UI_Back',
            'CamTranslateForward',
            'CamTranslateRight',
            'CamZoomOut',
            'UIFocus',
            'QuickCommsPanel',
            'QuickCommsPanel_Buggy',
            'QuickCommsPanel_Humanoid',
            'ToggleDriveAssist',
            'VerticalThrustersButton',
            'BuggyPrimaryFireButton',
            'BuggySecondaryFireButton',
            'AutoBreakBuggyButton',
            'HeadlightsBuggyButton',
            'ToggleBuggyTurretButton',
            'SelectTarget_Buggy',
            'IncreaseEnginesPower_Buggy',
            'IncreaseWeaponsPower_Buggy',
            'IncreaseSystemsPower_Buggy',
            'ResetPowerDistribution_Buggy',
            'ToggleCargoScoop_Buggy',
            'EjectAllCargo_Buggy',
            'RecallDismissShip',
            'GalaxyMapOpen_Buggy',
            'SystemMapOpen_Buggy',
            'OrderDefensiveBehaviour',
            'OrderAggressiveBehaviour',
            'OrderFocusTarget',
            'OrderHoldFire',
            'OrderHoldPosition',
            'OrderFollow',
            'OrderRequestDock',
            'HumanoidPrimaryInteractButton',
            'HumanoidSecondaryInteractButton',
            'HumanoidSelectPrimaryWeaponButton',
            'HumanoidSelectSecondaryWeaponButton',
            'HumanoidSelectUtilityWeaponButton',
            'HumanoidSwitchToRechargeTool',
            'HumanoidSwitchToCompAnalyser',
            'HumanoidSwitchToSuitTool',
            'HumanoidHideWeaponButton',
            'HumanoidSelectFragGrenade',
            'HumanoidSelectEMPGrenade',
            'HumanoidSelectShieldGrenade',
            'HumanoidToggleFlashlightButton',
            'HumanoidToggleNightVisionButton',
            'HumanoidToggleShieldsButton',
            'HumanoidClearAuthorityLevel',
            'HumanoidHealthPack',
            'HumanoidBattery',
            'GalaxyMapOpen_Humanoid',
            'SystemMapOpen_Humanoid',
            'HumanoidOpenAccessPanelButton',
        ]
        
        self.latest_bindings_file = None
        self.latest_bindings_mtime = None
        self.watch_thread = threading.Thread(target=self._watch_bindings_thread, daemon=True)
        self.watch_thread.start()
        
        self.keys = self.get_bindings()
        log('debug', 'Keybindings file found, loaded bindings from', self.latest_bindings_file)
        
        self.missing_keys = []
        # dump config to log
        for key in self.keys_to_obtain:
            if not key in self.keys:
                self.missing_keys.append(key)

    def get_bindings(self) -> dict[str, Any]:
        """Returns a dict struct with the direct input equivalent of the necessary elite keybindings"""
        direct_input_keys = {}
        latest_bindings, _ = self.get_latest_keybinds()
        if not latest_bindings:
            return {}
        bindings_tree = parse(latest_bindings)
        bindings_root = bindings_tree.getroot()

        for item in bindings_root:
            if item.tag in self.keys_to_obtain:
                key = None
                mods = []
                hold = None
                # Check primary
                if item[0].attrib['Device'].strip() == "Keyboard":
                    key = item[0].attrib['Key']
                    for modifier in item[0]:
                        if modifier.tag == "Modifier":
                            mods.append(modifier.attrib['Key'])
                        elif modifier.tag == "Hold":
                            hold = True
                # Check secondary (and prefer secondary)
                if item[1].attrib['Device'].strip() == "Keyboard":
                    key = item[1].attrib['Key']
                    mods = []
                    hold = None
                    for modifier in item[1]:
                        if modifier.tag == "Modifier":
                            mods.append(modifier.attrib['Key'])
                        elif modifier.tag == "Hold":
                            hold = True
                # Prepare final binding
                binding: None | dict[str, Any] = None
                try:
                    if key is not None:
                        binding = {}
                        binding['key'] = self.keymap[key]
                        binding['mods'] = []
                        for mod in mods:
                            binding['mods'].append(self.keymap[mod])
                        if hold is not None:
                            binding['hold'] = True
                except KeyError:
                    print("Unrecognised key '" + (json.dumps(binding) if binding else '?')  + "' for bind '" + item.tag + "'")
                if binding is not None:
                    direct_input_keys[item.tag] = binding

        if len(list(direct_input_keys.keys())) < 1:
            return {}
        else:
            return direct_input_keys

    def get_latest_keybinds(self):
        path_bindings = os.path.join(self.appdata_path+'/', "Options", "Bindings")
        try:
            list_of_bindings = [join(path_bindings, f) for f in listdir(path_bindings) if
                                isfile(join(path_bindings, f)) and f.endswith('.binds')]
        except FileNotFoundError as e:
            return None, None

        if not list_of_bindings:
            return None, None
        latest_bindings = max(list_of_bindings, key=getmtime)
        return latest_bindings, getmtime(latest_bindings)

    def send_key(self, type: Literal['Up', 'Down'], key_name:str):
        key = self.keymap.get(key_name)
        if key is None:
            raise Exception(f"Unsupported key {key_name}.")
        if type == 'Up':
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
        log('debug', 'Trying to send key', key_name)
        binding = self.keys.get(key_name)
        if binding is None:
            raise Exception(
                f"Unable to retrieve keybinding for {key_name}. Advise user to check game settings for keyboard bindings.")
        if not binding['key']:
            raise Exception(f"Unsupported key {key_name}.")

        for i in range(repeat):

            if state is None or state == 1:
                for mod in binding['mods']:
                    PressKey(mod)
                    sleep(self.key_mod_delay)

                PressKey(binding['key'])

            if state is None:
                if hold:
                    sleep(hold)
                else:
                    sleep(self.key_default_delay)

            if 'hold' in binding:
                sleep(0.1)

            if state is None or state == 0:
                ReleaseKey(binding['key'])

                for mod in binding['mods']:
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
                log('error', 'An error occurred when monitoring keybindings file', e, traceback.format_exc())
                sleep(backoff)
                log('info', 'Attempting to restart keybindings monitor after failure')
                backoff *= 2

    def _watch_bindings(self):
        """Monitors the keybindings file for changes and reloads when necessary"""
        while True:
            latest_bindings, mtime = self.get_latest_keybinds()
            if latest_bindings != self.latest_bindings_file or mtime != self.latest_bindings_mtime:
                self.latest_bindings_file = latest_bindings
                self.latest_bindings_mtime = mtime
                self.keys = self.get_bindings()
                log('debug', 'Keybindings file changed, reloaded bindings from', self.latest_bindings_file)
                # Update missing keys list
                self.missing_keys = []
                for key in self.keys_to_obtain:
                    if not key in self.keys:
                        self.missing_keys.append(key)
            sleep(1)
