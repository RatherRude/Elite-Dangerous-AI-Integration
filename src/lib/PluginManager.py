import importlib
import json
import os

import sys
from typing import Any, Self, cast

from lib.Config import Config

from .PluginSettingDefinitions import PluginSettings
from .Logger import log

from .PluginBase import PluginBase, PluginManifest

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .PluginHelper import PluginHelper

class PluginManager:
    # Constructor
    def __init__(self, config: Config):
        self.plugin_list: dict[str, 'PluginBase'] = {}
        self.plugin_settings_configs: dict[str, PluginSettings] = {}
        self.PLUGIN_FOLDER: str = "plugins"
        self.PLUGIN_DEPENDENCIES_FOLDER: str = "deps"
        self.config = config

        # Add the plugin folder to sys.path
        # This allows us to import plugins as packages.
        plugin_folder = os.path.abspath(os.path.join('.', self.PLUGIN_FOLDER))
        log('debug', f"Plugins folder ({plugin_folder}) added to path.")
        sys.path.insert(0, plugin_folder)

    def load_plugin_module(self, manifest: 'PluginManifest', file_path: str) -> 'PluginBase':
        # Get the module name from file name
        module_name = os.path.splitext(os.path.basename(file_path))[0]
        
        # Add deps folder to sys.path, if it exists
        plugin_folder = os.path.abspath(os.path.dirname(file_path))
        plugin_name = os.path.basename(plugin_folder)
        dotted_module = f"{plugin_name}.{module_name}"

        # sys.path.insert(0, plugin_folder)
        deps_folder = os.path.join(plugin_folder, self.PLUGIN_DEPENDENCIES_FOLDER)
        if os.path.exists(deps_folder):
            log('debug', f"Adding {deps_folder} to sys.path")
            sys.path.insert(0, deps_folder)

        # Import module as package. This is better than the old way because it allows for relative imports.
        module = importlib.import_module(dotted_module)

        # Find a subclass of PluginBase
        from .PluginBase import PluginBase
        for attr in dir(module):
            obj = getattr(module, attr)
            if isinstance(obj, type) and issubclass(obj, PluginBase) and obj is not PluginBase:
                plugin = obj(manifest) # Instantiate and return
                plugin.settings = self.config.get('plugin_settings', {}).get(manifest.guid, {})
                return plugin

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
    
    def register_settings(self):
        """Register all settings for each plugin."""
        for module in self.plugin_list.values():
            log('debug', f"Registering Settings for {module.plugin_manifest.name}")
            if module.settings_config is not None:
                # Check if the settings config is already registered
                self.plugin_settings_configs[module.plugin_manifest.guid] = module.settings_config
        print(json.dumps({"type": "plugin_settings_configs", "plugin_settings_configs": self.plugin_settings_configs, "has_plugin_settings": (len(self.plugin_settings_configs) > 0)})+'\n', flush=True)

    def on_settings_changed(self, new_settings: Config):
        """
        Executed when the plugin settings are changed, and will call the on_settings_changed hook for each plugin.
        """
        for module in self.plugin_list.values():
            log('debug', f"Executing on_settings_changed hook for {module.plugin_manifest.name}")
            try:
                if module.plugin_manifest.guid in new_settings.get('plugin_settings', {}):
                    module.settings = new_settings.get('plugin_settings', {}).get(module.plugin_manifest.guid) or {}
            except Exception as e:
                log('error', f"Failed to execute on_settings_changed hook for {module.plugin_manifest.name}: {e}")
    
    def on_chat_start(self, helper: 'PluginHelper'):
        """
        Executed when the chat is started, and will call the on_chat_start hook for each plugin.
        """
        for module in self.plugin_list.values():
            log('debug', f"Executing on_chat_start hook for {module.plugin_manifest.name}")
            try:
                module.on_chat_start(helper)
            except Exception as e:
                log('error', f"Failed to execute on_chat_start hook for {module.plugin_manifest.name}: {e}")

    def on_chat_stop(self, helper: 'PluginHelper'):
        """
        Executed when the chat is stopped, and will call the on_chat_stop hook for each plugin.
        """
        for module in self.plugin_list.values():
            log('debug', f"Executing on_chat_stop hook for {module.plugin_manifest.name}")
            try:
                module.on_chat_stop(helper)
            except Exception as e:
                log('error', f"Failed to execute on_chat_stop hook for {module.plugin_manifest.name}: {e}")
