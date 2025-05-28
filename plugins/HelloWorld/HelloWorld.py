from typing import override

from lib.PluginHelper import PluginHelper, PluginManifest
from lib.PluginSettingDefinitions import PluginSettings, SettingsGrid, SelectOption, SelectSetting, ParagraphSetting
from lib.Logger import log
from lib.PluginBase import PluginBase

# Main plugin class
# This is the class that will be loaded by the PluginManager.
class HelloWorld(PluginBase):
    def __init__(self, plugin_manifest: PluginManifest):
        super().__init__(plugin_manifest)

        # Define the plugin settings
        # This is the settings that will be shown in the UI for this plugin.
        self.settings_config: PluginSettings | None = PluginSettings(
            key="HelloWorldPlugin",
            label="Hello World Plugin",
            icon="waving_hand", # Uses Material Icons, like the built-in settings-tabs.
            grids=[
                SettingsGrid(
                    key="general",
                    label="General",
                    fields=[
                        ParagraphSetting(
                            key="info_box",
                            label="Information Box",
                            readonly = False,
                            placeholder = None,
                            type="paragraph",
                            content="This is just a text block.\nIt is not a setting."
                        ),
                        SelectSetting(
                            key="multiselect_setting",
                            label="Multi-Select Setting",
                            type="select",
                            readonly = False,
                            placeholder = "Select an option",
                            default_value = ["option_2", "option_3"],
                            multi_select = True,
                            select_options=[
                                SelectOption(key="option_1", label="Option 1", value="option_1", disabled=False),
                                SelectOption(key="option_2", label="Option 2", value="option_2", disabled=False),
                                SelectOption(key="option_3", label="Option 3", value="option_3", disabled=False),
                            ]
                        ),
                    ]
                )
            ]
        )
    
    @override
    def register_actions(self, helper: PluginHelper):
        # Register actions
        helper.register_action('self_test_helloWorld', "Self Test: Say hello to the world.", {
            "type": "object",
            "properties": {}
        }, lambda args, projected_states: self.hello_world_action(args, projected_states, helper), 'global')

    # Actions
    def hello_world_action(self, args, projected_states, helper: PluginHelper) -> str:
        log('info', 'Hello World!')
        return "'Hello World!' successfully writted to the log."
