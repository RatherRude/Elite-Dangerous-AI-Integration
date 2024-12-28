import json
from os import listdir
import os
from os.path import getmtime, isfile, join
from time import sleep
from typing import Any, final
from xml.etree.ElementTree import parse

from lib.Config import get_asset_path

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
        self.keys_to_obtain = [
            'PrimaryFire',
            'SecondaryFire',
            'HyperSuperCombination',
            'SetSpeedZero',
            'SetSpeed50',
            'SetSpeed100',
            'DeployHeatSink',
            'DeployHardpointToggle',
            'IncreaseEnginesPower',
            'IncreaseWeaponsPower',
            'IncreaseSystemsPower',
            'GalaxyMapOpen',
            'SystemMapOpen',
            'CycleNextTarget',
            'CycleFireGroupNext',
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
            'FocusLeftPanel',
            'UI_Up',
            'UI_Left',
            'UI_Right',
            'UI_Select',
            'UI_Back',
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
        self.keys = self.get_bindings()
        
        self.keymap: dict[str, int] = json.load(open(get_asset_path('keymap.json')))

        self.missing_keys = []
        # dump config to log
        for key in self.keys_to_obtain:
            if not key in self.keys:
                self.missing_keys.append(key)

    def get_bindings(self) -> dict[str, Any]:
        """Returns a dict struct with the direct input equivalent of the necessary elite keybindings"""
        direct_input_keys = {}
        latest_bindings = self.get_latest_keybinds()
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

    # Note:  this routine will grab the *.binds file which is the latest modified
    def get_latest_keybinds(self):
        path_bindings = os.path.join(self.appdata_path+'/', "Options", "Bindings")
        try:
            list_of_bindings = [join(path_bindings, f) for f in listdir(path_bindings) if
                                isfile(join(path_bindings, f)) and f.endswith('.binds')]
        except FileNotFoundError as e:
            return None

        if not list_of_bindings:
            return None
        latest_bindings = max(list_of_bindings, key=getmtime)
        return latest_bindings

    def send_key(self, type, key):
        if type == 'Up':
            ReleaseKey(key)
        else:
            PressKey(key)

    def send(self, key_name, hold=None, repeat=1, repeat_delay=None, state=None):
        key = self.keys.get(key_name)
        if key is None:
            # logger.warning('SEND=NONE !!!!!!!!')
            raise Exception(
                f"Unable to retrieve keybinding for {key_name}. Advise user to check game settings for keyboard bindings.")

        for i in range(repeat):

            if state is None or state == 1:
                for mod in key['mods']:
                    PressKey(mod)
                    sleep(self.key_mod_delay)

                PressKey(key['key'])

            if state is None:
                if hold:
                    sleep(hold)
                else:
                    sleep(self.key_default_delay)

            if 'hold' in key:
                sleep(0.1)

            if state is None or state == 0:
                ReleaseKey(key['key'])

                for mod in key['mods']:
                    sleep(self.key_mod_delay)
                    ReleaseKey(mod)

            if repeat_delay:
                sleep(repeat_delay)
            else:
                sleep(self.key_repeat_delay)
