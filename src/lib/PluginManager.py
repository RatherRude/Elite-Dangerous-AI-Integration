from abc import ABC
import importlib
import importlib.util
import json
import os

import sys
from typing import Any, Callable, Literal, Self, TypedDict, cast, final

import openai

from .PluginBase import PluginBase
from .PluginHelper import PluginHelper
from .PluginSettingDefinitions import PluginSettings
from .ScreenReader import ScreenReader
from .Logger import log
from .EDKeys import EDKeys
from .Config import Config
from .EventManager import EventManager
from .ActionManager import ActionManager
from .SystemDatabase import SystemDatabase
from .Event import Event

class PluginManager:
    # Constructor
    def __init__(self):
        self.plugin_list: dict[str, PluginBase] = {}
        self.plugin_settings_configs: list[PluginSettings] = []
        self.PLUGIN_FOLDER: str = "plugins"

    def load_plugin_module(self, file_path: str) -> PluginBase:
        # Get the module name from file name
        module_name = os.path.splitext(os.path.basename(file_path))[0]

        # Load module from file
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load spec for {file_path}")
        
        module = importlib.util.module_from_spec(spec)
        module.__file__ = os.path.abspath(file_path) # Set the __file__ attribute to the file path, since otherwise inspect will fail to find the source code later.
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # Find a subclass of PluginBase
        for attr in dir(module):
            obj = getattr(module, attr)
            if isinstance(obj, type) and issubclass(obj, PluginBase) and obj is not PluginBase:
                return obj() # Instantiate and return

        raise TypeError("No valid PluginBase subclass found.")

    def load_plugins(self) -> Self:
        """Load all .py files in PLUGIN_FOLDER as plugins."""
        for file in os.listdir(self.PLUGIN_FOLDER):
            try:
                # Check if the file is a folder
                abs_subfolder_path =os.path.join(self.PLUGIN_FOLDER, file)
                if os.path.isdir(abs_subfolder_path):
                    for file in os.listdir(abs_subfolder_path):
                        # Check if the file is a .py file
                        if file.endswith(".py"):
                            module_name = abs_subfolder_path[:-3]
                            module = self.load_plugin_module(os.path.join(abs_subfolder_path, file))
                            self.plugin_list[module_name] = module
                else:
                    # Check if the file is a .py file
                    if file.endswith(".py"):
                        module_name = file[:-3]
                        module = self.load_plugin_module(os.path.join(self.PLUGIN_FOLDER, file))
                        self.plugin_list[module_name] = module
            except Exception as e:
                log('error', f"Failed to load plugin {file}: {e}")
        return self

    def register_actions(self, deps: PluginHelper) -> None:
        """Register all actions for each plugin."""
        for module in self.plugin_list.values():
            log('info', f"Registering Actions for {module.plugin_name}")
            try:
                module.register_actions(deps)
            except Exception as e:
                log('error', f"Failed to register actions for {module.plugin_name}: {e}")

    def register_projections(self, deps: PluginHelper):
        """Register all projections for each plugin."""
        for module in self.plugin_list.values():
            log('info', f"Registering Projections for {module.plugin_name}")
            try:
                module.register_projections(deps)
            except Exception as e:
                log('error', f"Failed to register projections for {module.plugin_name}: {e}")
    
    def register_sideeffects(self, deps: PluginHelper):
        """Register all side effects for each plugin."""
        for module in self.plugin_list.values():
            log('info', f"Registering Side-Effects for {module.plugin_name}")
            try:
                module.register_sideeffects(deps)
            except Exception as e:
                log('error', f"Failed to register side effects for {module.plugin_name}: {e}")
    
    def register_settings(self):
        """Register all settings for each plugin."""
        for module in self.plugin_list.values():
            log('info', f"Registering Settings for {module.plugin_name}")
            if module.settings_config is not None:
                # Check if the settings config is already registered
                self.plugin_settings_configs.append(module.settings_config)
        print(json.dumps({"type": "plugin_settings_configs", "plugin_settings_configs": self.plugin_settings_configs})+'\n', flush=True)

    
    def register_prompt_generators(self, deps: PluginHelper):
        """Register all promp generators for each plugin."""
        for module in self.plugin_list.values():
            log('info', f"Registering Prompt Generators for {module.plugin_name}")
            try:
                module.register_prompt_generators(deps)
            except Exception as e:
                log('error', f"Failed to register prompt generators for {module.plugin_name}: {e}")
    
    def on_chat_stop(self, helper: PluginHelper):
        """
        Executed when the chat is stopped, and will call the on_chat_stop hook for each plugin.
        """
        for module in self.plugin_list.values():
            log('info', f"Executing on_chat_stop hook for {module.plugin_name}")
            try:
                module.on_chat_stop(helper)
            except Exception as e:
                log('error', f"Failed to execute on_chat_stop hook for {module.plugin_name}: {e}")

    def register_event_classes(self) -> list[type[Event]]:
        plugin_event_classes: list[type[Event]] = []
        for module in self.plugin_list.values():
            log('info', f"Registering Event classes for {module.plugin_name}")
            if module.event_classes is not None:
                # Check if the settings config is already registered
                plugin_event_classes += module.event_classes
        return plugin_event_classes
