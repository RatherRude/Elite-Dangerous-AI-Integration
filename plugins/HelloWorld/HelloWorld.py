from typing import Any, Callable, Literal, TypedDict, cast, final, override

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import openai
from openai.types.chat import ChatCompletionMessageParam

from lib.Config import Config
from lib.PluginHelper import PluginHelper, PluginManifest
from lib.PluginSettingDefinitions import PluginSettings, SettingsGrid, SelectOption, TextAreaSetting, TextSetting, SelectSetting, NumericalSetting, ToggleSetting, ParagraphSetting
from lib.ScreenReader import ScreenReader
from lib.Logger import log
from lib.EDKeys import EDKeys
from lib.EventManager import EventManager, Projection
from lib.ActionManager import ActionManager
from lib.PluginBase import PluginBase
from lib.SystemDatabase import SystemDatabase
from lib.Event import Event, StatusEvent

class HelloWorldState(TypedDict):
    event: str
    bool_value: bool

@dataclass
@final
class BoolValueUpdatedEvent(Event):
    new_bool_value: bool
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    kind: Literal['game', 'user', 'assistant', 'assistant_completed', 'tool', 'status', 'projected', 'external', 'archive'] = field(default='external')
    processed_at: float = field(default=0.0)

class CurrentHelloWorldState(Projection[HelloWorldState]):
    @override
    def get_default_state(self) -> HelloWorldState:
        return {
            'event': 'HelloWorldState',
            'bool_value': False
        }  # type: ignore

    @override
    def process(self, event: Event) -> None:
        if isinstance(event, BoolValueUpdatedEvent):
            self.state['bool_value'] = event.new_bool_value

# Main plugin class
# This is the class that will be loaded by the PluginManager.
class HelloWorld(PluginBase):
    def __init__(self, plugin_manifest: PluginManifest):
        super().__init__(plugin_manifest, event_classes=[BoolValueUpdatedEvent])

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
                        ToggleSetting(
                            key="bool_setting",
                            label="Boolean Setting",
                            type="toggle",
                            readonly = False,
                            placeholder = None,
                            default_value = False
                        ),
                        SelectSetting(
                            key="select_setting",
                            label="Select Setting",
                            type="select",
                            readonly = False,
                            placeholder = "Select an option",
                            default_value = "option_2",
                            select_options=[
                                SelectOption(key="option_1", label="Option 1", value="option_1", disabled=False),
                                SelectOption(key="option_2", label="Option 2", value="option_2", disabled=False),
                                SelectOption(key="option_3", label="Option 3", value="option_3", disabled=False),
                            ],
                            multi_select = False
                        ),
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
                ),
                SettingsGrid(
                    key="another_grid",
                    label="Another Grid",
                    fields=[
                        ToggleSetting(
                            key="second_bool_setting",
                            label="Boolean Setting with true default",
                            type="toggle",
                            readonly = False,
                            placeholder = None,
                            default_value = True,
                        ),
                        NumericalSetting(
                            key="number_setting",
                            label="A number goes in here",
                            type="number",
                            readonly = False,
                            placeholder = None, # Doesn't really work with number inputs.
                            default_value = None,
                            min_value = 0,
                            max_value = 100,
                            step = 0.2
                        ),
                        TextSetting(
                            key="text_setting",
                            label="This is a single-line text input",
                            type="text",
                            readonly = False,
                            placeholder = "This is a placeholder",
                            default_value = None,
                            max_length = None,
                            min_length = None,
                            hidden = False
                        ),
                        TextAreaSetting(
                            key="textarea_setting",
                            label="Multi-line Text Input",
                            type="textarea",
                            readonly = False,
                            placeholder = None,
                            default_value = "This is a multi-line plain-text field.\nThis is a second line.",
                            rows = None,
                            cols = None,
                        ),
                    ]
                ),
            ]
        )
    
    @override
    def register_actions(self, helper: PluginHelper):
        # Register actions
        helper.register_action('helloWorld', "Say hello to the world.", {
            "type": "object",
            "properties": {}
        }, lambda args, projected_states: self.hello_world_action(args, projected_states, helper), 'global')

        log('debug', f"Actions registered for {self.plugin_manifest.name}")
        
    @override
    def register_projections(self, helper: PluginHelper):
        # Register projections
        helper.register_projection(CurrentHelloWorldState())
        
        log('debug', f"Projections registered for {self.plugin_manifest.name}")

    @override
    def register_sideeffects(self, helper: PluginHelper):
        # Register side effects
        helper.register_sideeffect(self.hello_world_sideeffect)

        log('debug', f"Side effects registered for {self.plugin_manifest.name}")
        
    @override
    def register_prompt_event_handlers(self, helper: PluginHelper):
        # Register prompt generators
        helper.register_prompt_event_handler(self.bool_value_prompt_event_handler)
        
    @override
    def register_status_generators(self, helper: PluginHelper):
        # Register prompt generators
        helper.register_status_generator(self.bool_value_prompt_status_generator)

    @override
    def register_should_reply_handlers(self, helper: PluginHelper):
        helper.register_should_reply_handler(self.hw_should_reply_handler)
    
    @override
    def on_chat_stop(self, helper: PluginHelper):
        # Executed when the chat is stopped
        log('debug', f"Executed on_chat_stop hook for {self.plugin_manifest.name}")

    # Actions
    def hello_world_action(self, args, projected_states, helper: PluginHelper) -> str:
        log('info', 'Hello World!')

        # Toggle the boolean value
        # Use helper.get_projection to get the current projection state of a given type.
        projection: CurrentHelloWorldState | None = cast(CurrentHelloWorldState | None, helper.get_projection(CurrentHelloWorldState))
        if projection is not None:
            self.set_boolean(helper, projection.state['bool_value'])
            
        return "This is the result of the hello World action."

    # Functions
    def set_boolean(self, helper: PluginHelper, new_bool_value: bool):
        event = BoolValueUpdatedEvent(new_bool_value)
        helper.put_incoming_event(event) # Updates the boolean in the projection state

    def hello_world_sideeffect(self, event: Event, projected_states: dict[str, Any]):
        log('debug', f"Hello World side effect triggered by event: {event.__class__.__name__} event.")

    def bool_value_prompt_event_handler(self, event: Event) -> list[ChatCompletionMessageParam]:
        if isinstance(event, BoolValueUpdatedEvent):
            return [
                {
                    "role": "system",
                    "content": 'The boolean value is now {}.'.format(event.new_bool_value),
                }
            ]
        return []

    def bool_value_prompt_status_generator(self, projected_states: dict[str, dict]) -> list[tuple[str, Any]]:
        return [
            ('Current boolean value', projected_states['CurrentHelloWorldState']['bool_value'])
        ]

    def hw_should_reply_handler(self, event: Event, projected_states: dict[str, dict]) -> bool | None:
        if isinstance(event, BoolValueUpdatedEvent):
            return False # Never reply to BoolValueUpdatedEvents
        return None