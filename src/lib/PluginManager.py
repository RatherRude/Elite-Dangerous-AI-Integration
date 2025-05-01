import importlib
import importlib.util
import os

from typing import Self

import openai

from lib.PluginBase import PluginBase
from .ScreenReader import ScreenReader
from .Logger import log
from .EDKeys import EDKeys
from .EventManager import EventManager
from .ActionManager import ActionManager

class PluginManager:
    def load_plugin(self, file_path: str, action_manager: ActionManager, event_manager: EventManager, llm_client: openai.OpenAI,
                     llm_model_name: str, vision_client: openai.OpenAI | None, vision_model_name: str | None,
                     ed_keys: EDKeys) -> PluginBase:
        # Get the module name from file name
        module_name = os.path.splitext(os.path.basename(file_path))[0]

        # Load module from file
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load spec for {file_path}")
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Find a subclass of PluginBase
        for attr in dir(module):
            obj = getattr(module, attr)
            if isinstance(obj, type) and issubclass(obj, PluginBase) and obj is not PluginBase:
                return obj(action_manager, event_manager, llm_client, llm_model_name, vision_client, vision_model_name, ed_keys)  # Instantiate and return

        raise TypeError("No valid PluginBase subclass found.")

    PLUGIN_FOLDER: str = "plugins"
    plugin_list: dict[str, PluginBase]  = {}

    def load_plugins(self, action_manager: ActionManager, event_manager: EventManager, llm_client: openai.OpenAI,
                     llm_model_name: str, vision_client: openai.OpenAI | None, vision_model_name: str | None,
                     ed_keys: EDKeys) -> Self:
        """Load all .py files in PLUGIN_FOLDER as plugins."""
        for file in os.listdir(self.PLUGIN_FOLDER):
            if file.endswith(".py"):
                module_name = file[:-3]
                module = self.load_plugin(os.path.join(self.PLUGIN_FOLDER, file), action_manager, event_manager, llm_client, llm_model_name, vision_client, vision_model_name, ed_keys)
                self.plugin_list[module_name] = module
        return self

    def register_actions(self):
        for module in self.plugin_list.values():
            log('info', f"Registering Actions for {module.plugin_name}")
            module.register_actions()