from abc import ABC
import importlib
import importlib.util
import json
import os

import sys
from typing import Any, Callable, Literal, Self, TypedDict, cast, final

import openai

from .PluginBase import PluginBase
from .PluginHelper import PluginHelper, PluginManifest
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
        self.PLUGIN_DEPENDENCIES_FOLDER: str = "deps"

    def load_plugin_module(self, manifest: PluginManifest, file_path: str) -> PluginBase:
        # Get the module name from file name
        module_name = os.path.splitext(os.path.basename(file_path))[0]
        
        # Add deps folder to sys.path, if it exists
        plugin_folder = os.path.abspath(os.path.dirname(file_path))
        deps_folder = os.path.join(plugin_folder, self.PLUGIN_DEPENDENCIES_FOLDER)
        if os.path.exists(deps_folder):
            log('debug', f"Adding {deps_folder} to sys.path")
            sys.path.insert(0, deps_folder)

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
                return obj(manifest) # Instantiate and return

        raise TypeError("No valid PluginBase subclass found.")

    def load_plugins(self) -> Self:
        """Load all .py files in PLUGIN_FOLDER as plugins."""
        
        # Create PLUGIN_FOLDER if it doesn't exist
        if not os.path.exists(self.PLUGIN_FOLDER):
            os.makedirs(self.PLUGIN_FOLDER)

        for file in os.listdir(self.PLUGIN_FOLDER):
            try:
                # Check if the file is a folder
                subfolder_path = os.path.join(self.PLUGIN_FOLDER, file)
                if os.path.isdir(subfolder_path):
                    # Check if manifest.json exists
                    if not os.path.exists(os.path.join(subfolder_path, "manifest.json")):
                        continue

                    log('debug', f"Found manifest.json in {subfolder_path}")

                    # Load manifest.json
                    with open(os.path.join(subfolder_path, "manifest.json"), "r") as f:
                        json_str = f.read()
                        manifest = PluginManifest(json_str)

                    log('debug', f"Loaded manifest for {manifest.name}")
                    log('debug', f"Entry point: {manifest.entrypoint}")

                    # Check if the entrypoint is a .py file
                    if not manifest.entrypoint.endswith(".py"):
                        log('error', f"Plugin entrypoint {file} is not a .py file")
                        continue
                    
                    # Check if entrypoint file exists
                    entrypoint_path = os.path.join(subfolder_path, manifest.entrypoint)
                    if not os.path.exists(entrypoint_path):
                        log('error', f"Entrypoint file {entrypoint_path} does not exist")
                        continue

                    module_name = f"{manifest.guid}.{manifest.entrypoint[:-3]}"
                    module = self.load_plugin_module(manifest, entrypoint_path)
                    self.plugin_list[module_name] = module
            except Exception as e:
                log('error', f"Failed to load plugin {file}: {e}")
        return self

    def register_actions(self, helper: PluginHelper) -> None:
        """Register all actions for each plugin."""
        for module in self.plugin_list.values():
            log('debug', f"Registering Actions for {module.plugin_manifest.name}")
            try:
                module.register_actions(helper)
            except Exception as e:
                log('error', f"Failed to register actions for {module.plugin_manifest.name}: {e}")

    def register_projections(self, helper: PluginHelper):
        """Register all projections for each plugin."""
        for module in self.plugin_list.values():
            log('debug', f"Registering Projections for {module.plugin_manifest.name}")
            try:
                module.register_projections(helper)
            except Exception as e:
                log('error', f"Failed to register projections for {module.plugin_manifest.name}: {e}")
    
    def register_sideeffects(self, helper: PluginHelper):
        """Register all side effects for each plugin."""
        for module in self.plugin_list.values():
            log('debug', f"Registering Side-Effects for {module.plugin_manifest.name}")
            try:
                module.register_sideeffects(helper)
            except Exception as e:
                log('error', f"Failed to register side effects for {module.plugin_manifest.name}: {e}")
    
    def register_settings(self):
        """Register all settings for each plugin."""
        for module in self.plugin_list.values():
            log('debug', f"Registering Settings for {module.plugin_manifest.name}")
            if module.settings_config is not None:
                # Check if the settings config is already registered
                self.plugin_settings_configs.append(module.settings_config)
        print(json.dumps({"type": "plugin_settings_configs", "plugin_settings_configs": self.plugin_settings_configs, "has_plugin_settings": (len(self.plugin_settings_configs) > 0)})+'\n', flush=True)
    
    def register_prompt_event_handlers(self, helper: PluginHelper):
        """Register all prompt event handlers for each plugin. Used to add to the prompt in response to events."""
        for module in self.plugin_list.values():
            log('debug', f"Registering Prompt Generators for {module.plugin_manifest.name}")
            try:
                module.register_prompt_event_handlers(helper)
            except Exception as e:
                log('error', f"Failed to register prompt generators for {module.plugin_manifest.name}: {e}")
    
    def register_status_generators(self, helper: PluginHelper):
        """Register all status generators for each plugin. Used to add to the prompt context, much like ship info."""
        for module in self.plugin_list.values():
            log('debug', f"Registering status Generators for {module.plugin_manifest.name}")
            try:
                module.register_status_generators(helper)
            except Exception as e:
                log('error', f"Failed to register status generators for {module.plugin_manifest.name}: {e}")
    
    def on_chat_stop(self, helper: PluginHelper):
        """
        Executed when the chat is stopped, and will call the on_chat_stop hook for each plugin.
        """
        for module in self.plugin_list.values():
            log('debug', f"Executing on_chat_stop hook for {module.plugin_manifest.name}")
            try:
                module.on_chat_stop(helper)
            except Exception as e:
                log('error', f"Failed to execute on_chat_stop hook for {module.plugin_manifest.name}: {e}")

    def register_event_classes(self) -> list[type[Event]]:
        plugin_event_classes: list[type[Event]] = []
        for module in self.plugin_list.values():
            log('debug', f"Registering Event classes for {module.plugin_manifest.name}")
            if module.event_classes is not None:
                # Check if the settings config is already registered
                plugin_event_classes += module.event_classes
        return plugin_event_classes

    def register_should_reply_handlers(self, helper: PluginHelper):
        for module in self.plugin_list.values():
            log('debug', f"Registering should_reply handlers for {module.plugin_manifest.name}")
            try:
                module.register_should_reply_handlers(helper)
            except Exception as e:
                log('error', f"Failed to register should_reply handlers for {module.plugin_manifest.name}: {e}")
