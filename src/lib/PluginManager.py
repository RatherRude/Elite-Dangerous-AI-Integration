import traceback
import importlib
import json
import os

import sys
from typing import Self

from lib.Config import Config

from .PluginSettingDefinitions import PluginSettings, ModelProviderDefinition, ParagraphSetting, SettingsGrid, ErrorSetting
from .Logger import log
from .UI import emit_message

from .PluginBase import PluginBase, PluginManifest
from .Models import LLMModel, STTModel, TTSModel, EmbeddingModel

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .PluginHelper import PluginHelper


class PluginModelProvider(ModelProviderDefinition):
    """Extended provider definition that includes the plugin's guid for routing."""
    plugin_guid: str


class PluginManager:
    # Constructor
    def __init__(self, config: Config):
        self.plugin_list: dict[str, 'PluginBase'] = {}
        self.plugin_settings_configs: dict[str, PluginSettings] = {}
        self.plugin_model_providers: list[PluginModelProvider] = []
        self.failed_plugins: list[dict] = []
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
        
        self.load_default_plugins()
        self.failed_plugins = []
        
        # Create PLUGIN_FOLDER if it doesn't exist
        # Create PLUGIN_FOLDER if it doesn't exist
        if not os.path.exists(self.PLUGIN_FOLDER):
            os.makedirs(self.PLUGIN_FOLDER)
        for file in os.listdir(self.PLUGIN_FOLDER):
            manifest = None
            try:
                # Check if the file is a folder
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
                log('error', f"Failed to load plugin {file}:", e, traceback.format_exc())
                self.failed_plugins.append({
                    "file": file,
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "manifest": manifest
                })
        return self
    
    def load_default_plugins(self):
        """Load default built-in plugins."""

        log('debug', f"Loading built-in plugins")
        
        # EDCoPilot Plugin
        from plugins.EDCoPilotPlugin import EDCoPilotPlugin
        edcopilot_guid = 'ec3eee66-8c4c-4ede-be36-b8612b14a5c0'
        self.plugin_list[edcopilot_guid] = EDCoPilotPlugin(PluginManifest(json.dumps({
            "guid": edcopilot_guid,
            "name": "EDCoPilot Plugin",
            "author": "Elite Dangerous AI Integration",
            "version": "1.0.0",
            "repository": ""
        })))
    
    def register_settings(self):
        """Register all settings and model providers for each plugin."""
        self.plugin_model_providers = []
        
        for module in self.plugin_list.values():
            log('debug', f"Registering Settings for {module.plugin_manifest.name}")
            
            # Register plugin settings config
            try:
                if module.settings_config is not None:
                    self.plugin_settings_configs[module.plugin_manifest.guid] = module.settings_config
            except Exception as e:
                log('error', f"Failed to read settings_config for {module.plugin_manifest.name}: {e}")
            
            # Register model providers
            try:
                if module.model_providers is not None:
                    for provider in module.model_providers:
                        plugin_provider: PluginModelProvider = {
                            **provider,
                            'plugin_guid': module.plugin_manifest.guid
                        }
                        self.plugin_model_providers.append(plugin_provider)
                        log('debug', f"Registered {provider['kind']} provider '{provider['id']}' from {module.plugin_manifest.name}")
            except Exception as e:
                log('error', f"Failed to read model_providers for {module.plugin_manifest.name}: {e}")
        
        # Add failed plugins to settings
        for failed in self.failed_plugins:
            manifest = failed.get("manifest")
            file = failed.get("file")
            error = failed.get("error")
            tb = failed.get("traceback")
            
            if manifest:
                guid = manifest.guid
                name = manifest.name
            else:
                guid = f"failed_{file}"
                name = f"Failed Plugin: {file}"
            
            # Create error settings page
            error_settings: PluginSettings = {
                "key": guid,
                "label": name,
                "icon": "alert-circle",
                "grids": [
                    {
                        "key": "error_info",
                        "label": "Plugin Load Error",
                        "fields": [
                            {
                                "key": "error_msg",
                                "label": "Error Message",
                                "type": "error",
                                "content": f"This plugin failed to load.\n\nError: {error}\n\nTraceback:\n{tb}",
                                "readonly": True,
                                "placeholder": None
                            }
                        ]
                    }
                ]
            }
            self.plugin_settings_configs[guid] = error_settings

        # Broadcast settings configs to UI
        emit_message(
            "plugin_settings_configs",
            plugin_settings_configs=self.plugin_settings_configs,
            has_plugin_settings=(len(self.plugin_settings_configs) > 0),
        )
        
        # Broadcast model providers to UI
        emit_message("plugin_model_providers", providers=self.plugin_model_providers)

    def on_settings_changed(self, new_config: Config):
        """
        Executed when the plugin settings are changed, and will call the on_settings_changed hook for each plugin.
        """
        self.config = new_config
        for module in self.plugin_list.values():
            log('debug', f"Executing on_settings_changed hook for {module.plugin_manifest.name}")
            try:
                if module.plugin_manifest.guid in new_config.get('plugin_settings', {}):
                    module.settings = new_config.get('plugin_settings', {}).get(module.plugin_manifest.guid) or {}
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

    def create_plugin_model(self, plugin_guid: str, provider_id: str, expected_kind: str) -> LLMModel | STTModel | TTSModel | EmbeddingModel | None:
        """
        Create a model instance from a plugin provider.
        
        Args:
            plugin_guid: The GUID of the plugin providing the model
            provider_id: The provider's id within the plugin
            expected_kind: The expected model type ('llm', 'stt', 'tts', 'embedding')
            
        Returns:
            The model instance, or None if creation failed
        """
        # Find the plugin
        plugin: PluginBase | None = None
        for p in self.plugin_list.values():
            if p.plugin_manifest.guid == plugin_guid:
                plugin = p
                break
        
        if plugin is None:
            log('error', f"Plugin with guid '{plugin_guid}' not found")
            return None
        
        # Get plugin settings
        settings = self.config.get('plugin_settings', {}).get(plugin_guid, {})
        
        # Call the plugin's create_model method
        try:
            model = plugin.create_model(provider_id, settings)
        except Exception as e:
            log('error', f"Plugin {plugin.plugin_manifest.name} failed to create model '{provider_id}': {e}")
            return None
        
        # Validate the returned model type
        expected_types = {
            'llm': LLMModel,
            'stt': STTModel,
            'tts': TTSModel,
            'embedding': EmbeddingModel
        }
        expected_type = expected_types.get(expected_kind)
        if expected_type and not isinstance(model, expected_type):
            log('error', f"Plugin {plugin.plugin_manifest.name} returned wrong model type for '{provider_id}': expected {expected_kind}, got {type(model).__name__}")
            return None
        
        log('info', f"Created {expected_kind} model '{provider_id}' from plugin {plugin.plugin_manifest.name}")
        return model

    def get_plugin_provider(self, plugin_guid: str, provider_id: str) -> PluginModelProvider | None:
        """
        Get a plugin model provider definition by guid and id.
        
        Args:
            plugin_guid: The GUID of the plugin
            provider_id: The provider's id within the plugin
            
        Returns:
            The provider definition, or None if not found
        """
        for provider in self.plugin_model_providers:
            if provider['plugin_guid'] == plugin_guid and provider['id'] == provider_id:
                return provider
        return None
