from typing import override

from typing import Optional
import openai

from lib.ScreenReader import ScreenReader
from lib.Logger import log
from lib.EDKeys import EDKeys
from lib.EventManager import EventManager
from lib.ActionManager import ActionManager
from lib.PluginBase import PluginBase

class MediaControlPlugin(PluginBase):
    def __init__(self, action_manager: ActionManager, event_manager: EventManager, llm_client: openai.OpenAI,
                     llm_model_name: str, vision_client: Optional[openai.OpenAI], vision_model_name: Optional[str],
                     ed_keys: EDKeys, plugin_name: str = "Hello World - Example Plugin"):
        super().__init__(action_manager, event_manager, llm_client, llm_model_name, vision_client, vision_model_name, ed_keys, plugin_name)

    # Actions
    def hello_world_action(self, args, projected_states) -> str:
        log('info', 'Hello World!')
        return "This is the result of the hello World action."
    
    @override
    def register_actions(self):
        log('info', f"Actions registered for {self.plugin_name}")

        # Register actions
        self.action_manager.registerAction('helloWorld', "Say hello to the world.", {
            "type": "object",
            "properties": {}
        }, self.hello_world_action, 'global')
        