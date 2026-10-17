import traceback
import importlib
import json
import os
import re
from copy import deepcopy

import sys
from typing import Any, Callable, Self, TypeGuard

from lib.Config import Config, save_config

from .PluginSettingDefinitions import PluginSettings, ModelProviderDefinition, ParagraphSetting, SettingsGrid, ErrorSetting
from .Logger import log
from .UI import emit_message

from .PluginBase import PluginBase, PluginManifest
from .PluginNamespace import PluginNamespace
from .PluginUIDefinitions import UIComponent, view_target
from .Models import LLMModel, STTModel, TTSModel, EmbeddingModel

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .PluginHelper import PluginHelper


class PluginModelProvider(ModelProviderDefinition):
    """Extended provider definition that includes the plugin's guid for routing."""
    plugin_guid: str
    is_builtin: bool


class PluginManager:
    # Constructor
    def __init__(self, config: Config) -> None:
        self.plugin_list: dict[str, 'PluginBase'] = {}
        self.plugin_settings_configs: dict[str, PluginSettings] = {}
        self.plugin_model_providers: list[PluginModelProvider] = []
        self.builtin_plugin_guids: set[str] = set()
        self.failed_plugins: list[dict] = []
        self.settings_migrated = False
        self.PLUGIN_FOLDER: str = "plugins"
        self.PLUGIN_DEPENDENCIES_FOLDER: str = "deps"
        self.config = config
        self.plugin_ui: dict[str, dict[str, Any]] = {}
        self.ui_action_manager = None
        self._namespaces: dict[PluginBase, PluginNamespace] = {}
        self._owners: dict[str, PluginBase] = {}
        self._ui_values: dict[PluginBase, dict[str, Any]] = {}
        self._language_detector: tuple[str, Callable[[str], str | None]] | None = None

        # Add the plugin folder to sys.path
        # This allows us to import plugins as packages.
        plugin_folder = os.path.abspath(os.path.join('.', self.PLUGIN_FOLDER))
        log('debug', f"Plugins folder ({plugin_folder}) added to path.")
        sys.path.insert(0, plugin_folder)

    def _register_plugin(self, plugin: PluginBase, guid: str | None = None) -> PluginNamespace:
        if plugin in self._namespaces:
            return self._namespaces[plugin]
        namespace = PluginNamespace(guid if guid is not None else plugin.plugin_manifest.guid)
        if namespace.guid in self._owners:
            raise ValueError(f'Duplicate plugin GUID: {namespace.guid}')
        self._namespaces[plugin] = namespace
        self._owners[namespace.guid] = plugin
        self._ui_values[plugin] = {}
        plugin._manager = self
        try:
            plugin.on_registered()
        except Exception:
            self._namespaces.pop(plugin)
            self._owners.pop(namespace.guid)
            self._ui_values.pop(plugin)
            plugin._manager = None
            raise
        return namespace

    def _get_owned_data_path(self, plugin: PluginBase) -> str:
        from .PluginHelper import PluginHelper
        path = os.path.abspath(os.path.join(PluginHelper.PLUGIN_DATA_PATH, self._namespaces[plugin].guid))
        os.makedirs(path, exist_ok=True)
        return path

    def _settings_presentation(self, plugin: PluginBase) -> PluginSettings | None:
        namespace = self._namespaces[plugin]
        settings = plugin.get_ui_settings()
        if settings is not None:
            settings = namespace.presentation(settings)
            settings['key'] = namespace.guid
        return settings

    def _get_owned_app_config(self, plugin: PluginBase) -> dict[str, Any]:
        guid = self._namespaces[plugin].guid
        config = deepcopy(self.config)
        config['plugin_settings'] = {guid: config.get('plugin_settings', {}).get(guid, {})}
        return dict(config)

    def _initialize_plugin_settings(self, plugin: PluginBase, guid: str | None = None) -> PluginBase:
        """Load and migrate one plugin's settings without changing its public API."""
        guid = self._register_plugin(plugin, guid).guid
        stored = self.config.get('plugin_settings', {}).get(guid, {})
        plugin.settings = deepcopy(stored) if isinstance(stored, dict) else {}
        previous_settings = deepcopy(plugin.settings)
        try:
            settings_version = max(0, int(plugin.settings.get('settings_version', 0)))
        except (TypeError, ValueError):
            settings_version = 0
        target_version = max(0, int(plugin.settings_schema_version))
        while settings_version < target_version:
            plugin.migrate_settings(plugin.settings, settings_version)
            settings_version += 1
            plugin.settings['settings_version'] = settings_version
        if plugin.settings != previous_settings:
            self.config.setdefault('plugin_settings', {})[guid] = deepcopy(plugin.settings)
            self.settings_migrated = True
        return plugin

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
                guid = manifest.guid
                return self._initialize_plugin_settings(obj(manifest), guid)

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
        self.builtin_plugin_guids.add(edcopilot_guid)
        self.plugin_list[edcopilot_guid] = self._initialize_plugin_settings(EDCoPilotPlugin(PluginManifest(json.dumps({
            "guid": edcopilot_guid,
            "name": "EDCoPilot Plugin",
            "author": "Elite Dangerous AI Integration",
            "version": "1.0.0",
            "repository": ""
        }))))

        from plugins.MistralPlugin import MISTRAL_PLUGIN_GUID, MistralPlugin
        self.builtin_plugin_guids.add(MISTRAL_PLUGIN_GUID)
        self.plugin_list[MISTRAL_PLUGIN_GUID] = self._initialize_plugin_settings(MistralPlugin(PluginManifest(json.dumps({
            "guid": MISTRAL_PLUGIN_GUID,
            "name": "Mistral Plugin",
            "author": "Elite Dangerous AI Integration",
            "version": "1.0.0",
            "repository": ""
        }))))

        from plugins.EdgeTTSPlugin import EDGE_TTS_PLUGIN_GUID, EdgeTTSPlugin
        from plugins.GoogleAIStudioPlugin import GOOGLE_AI_STUDIO_PLUGIN_GUID, GoogleAIStudioPlugin
        from plugins.OpenAICompatiblePlugin import OPENAI_COMPATIBLE_PLUGIN_GUID, OpenAICompatiblePlugin
        from plugins.OpenAIPlugin import OPENAI_PLUGIN_GUID, OpenAIPlugin
        from plugins.OpenRouterPlugin import OPENROUTER_PLUGIN_GUID, OpenRouterPlugin

        bundled_providers = [
            (EDGE_TTS_PLUGIN_GUID, "Edge TTS Plugin", EdgeTTSPlugin),
            (GOOGLE_AI_STUDIO_PLUGIN_GUID, "Google AI Studio Plugin", GoogleAIStudioPlugin),
            (OPENAI_COMPATIBLE_PLUGIN_GUID, "OpenAI-compatible Plugin", OpenAICompatiblePlugin),
            (OPENAI_PLUGIN_GUID, "OpenAI Plugin", OpenAIPlugin),
            (OPENROUTER_PLUGIN_GUID, "OpenRouter Plugin", OpenRouterPlugin),
        ]
        for guid, name, plugin_type in bundled_providers:
            self.builtin_plugin_guids.add(guid)
            manifest = PluginManifest(json.dumps({
                "guid": guid,
                "name": name,
                "author": "COVAS:NEXT",
                "version": "1.0.0",
                "repository": "",
            }))
            self.plugin_list[guid] = self._initialize_plugin_settings(plugin_type(manifest))
    
    def register_settings(self):
        """Register all settings and model providers for each plugin."""
        self.plugin_model_providers = []
        self.plugin_ui = {}
        
        for module in self.plugin_list.values():
            log('debug', f"Registering Settings for {module.plugin_manifest.name}")
            namespace = self._register_plugin(module)

            # Register plugin settings config
            try:
                settings = self._settings_presentation(module)
                if settings is not None:
                    self.plugin_settings_configs[namespace.guid] = settings
                self.publish_plugin_ui(module, broadcast=False)
            except Exception as e:
                log('error', f"Failed to read settings_config for {module.plugin_manifest.name}: {e}")
            
            # Register model providers
            try:
                if module.model_providers is not None:
                    for provider in module.model_providers:
                        plugin_provider = PluginModelProvider(**{
                            **namespace.presentation(provider),
                            'plugin_guid': namespace.guid,
                            'is_builtin': namespace.guid in self.builtin_plugin_guids,
                        })
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
            if guid in self._owners:
                guid = f'failed_{file}'
            
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

        if self.settings_migrated:
            emit_message("config", config=self.config)
            save_config(self.config)
            self.settings_migrated = False

        # Broadcast settings configs to UI
        self.broadcast_plugin_ui()

    def publish_plugin_settings(self, plugin: PluginBase) -> None:
        self.publish_plugin_ui(plugin)

    def publish_plugin_ui(self, plugin: PluginBase, *, broadcast: bool = True) -> None:
        namespace = self._namespaces[plugin]
        guid = namespace.guid
        views = namespace.presentation(plugin.get_ui_views())
        ids = [view['id'] for view in views]
        if len(ids) != len(set(ids)) or any(not view_id or ':' in view_id for view_id in ids):
            raise ValueError('Plugin UI view IDs must be unique, nonempty and contain no colon')
        settings = self._settings_presentation(plugin)
        if settings is None:
            self.plugin_settings_configs.pop(guid, None)
        else:
            self.plugin_settings_configs[guid] = settings
        self.plugin_ui[guid] = {
            'views': views,
            'translations': namespace.translations(plugin.get_ui_translations()),
            'state': self._get_ui_state(plugin),
        }
        for provider in self.plugin_model_providers:
            if provider['plugin_guid'] == guid:
                definition = next((item for item in plugin.model_providers or [] if item['id'] == provider['id']), None)
                if definition is not None:
                    provider.update(namespace.presentation(definition))
        if broadcast:
            self.broadcast_plugin_ui()

    def _input_fields(self, value: Any) -> dict[str, dict[str, Any]]:
        fields: dict[str, dict[str, Any]] = {}
        if isinstance(value, list):
            for item in value:
                fields.update(self._input_fields(item))
        elif isinstance(value, dict):
            if value.get('type') in {'text', 'textarea', 'toggle', 'number', 'select', 'filter'} and 'text' not in value:
                key = value.get('key')
                if not isinstance(key, str) or not key:
                    raise ValueError('Plugin UI inputs must have nonempty keys')
                fields[key] = value
            for key in ('grids', 'fields', 'content', 'sections', 'children', 'items', 'details'):
                child = value.get(key)
                if isinstance(child, (list, dict)):
                    fields.update(self._input_fields(child))
        return fields

    def _setting_inputs(self, plugin: PluginBase) -> dict[str, dict[str, Any]]:
        fields = self._input_fields(plugin.get_ui_settings())
        for provider in plugin.model_providers or []:
            fields.update(self._input_fields(provider.get('settings_config', [])))
        return fields

    def _setting_input_keys(self, plugin: PluginBase) -> set[str]:
        return set(self._setting_inputs(plugin))

    def _get_ui_state(self, plugin: PluginBase) -> dict[str, Any]:
        settings = self._setting_inputs(plugin)
        fields = {**settings, **self._input_fields(plugin.get_ui_views())}
        state = {key: field.get('default_value') for key, field in fields.items()}
        state.update({key: value for key, value in plugin.settings.items() if key in fields})
        state.update({key: value for key, value in self._ui_values[plugin].items() if key in fields})
        return deepcopy(state)

    def _on_ui_changed(self, plugin: PluginBase, payload: dict[str, Any]) -> None:
        key = payload.get('key')
        fields = {**self._setting_inputs(plugin), **self._input_fields(plugin.get_ui_views())}
        if not isinstance(key, str) or key not in fields or 'value' not in payload or fields[key].get('readonly'):
            raise ValueError('common.invalidAction')
        value = deepcopy(payload['value'])
        values = self._ui_values[plugin]
        previous = deepcopy(values)
        values[key] = value
        try:
            plugin.on_ui_changed(key, deepcopy(value), self._get_ui_state(plugin))
        except Exception:
            self._ui_values[plugin] = previous
            raise

    def broadcast_plugin_ui(self) -> None:
        emit_message('plugin_ui', plugins=self.plugin_ui)
        emit_message('plugin_settings_configs', plugin_settings_configs=self.plugin_settings_configs,
                     has_plugin_settings=bool(self.plugin_settings_configs))
        emit_message('plugin_model_providers', providers=self.plugin_model_providers)
        if self.ui_action_manager is not None:
            from .actions.actions_ui import configure_plugin_ui
            configure_plugin_ui(self, self.ui_action_manager)

    def get_ui_targets(self, mode: str = 'running') -> dict[str, dict[str, Any]]:
        return {
            view_target(guid, view['id']): view
            for guid, contribution in self.plugin_ui.items()
            for view in contribution['views']
            if mode in view.get('modes', ['running'])
        }

    def on_ui_action(self, plugin_guid: str, action: str, payload: dict[str, Any], request_id: str) -> None:
        plugin = self._owners.get(plugin_guid)
        try:
            if plugin is None:
                raise ValueError('common.pluginUnavailable')
            if action == 'ui_changed':
                result = self._on_ui_changed(plugin, payload)
            else:
                result = plugin.on_ui_action(action, payload)
            self._refresh_plugin_setting_contents(plugin)
            plugin.publish_ui()
            emit_message('plugin_ui_result', request_id=request_id, plugin_guid=plugin_guid, success=True, result=result)
        except Exception as error:
            log('error', f'Plugin UI action {action} failed: {error}')
            try:
                error_text = self._namespaces[plugin].translation_key(str(error)) if plugin is not None else str(error)
            except ValueError:
                error_text = 'common.invalidAction'
            emit_message('plugin_ui_result', request_id=request_id, plugin_guid=plugin_guid, success=False, error=error_text)

    def on_settings_changed(self, new_config: Config):
        """
        Executed when the plugin settings are changed, and will call the on_settings_changed hook for each plugin.
        """
        self.config = new_config
        for module in self.plugin_list.values():
            log('debug', f"Executing on_settings_changed hook for {module.plugin_manifest.name}")
            try:
                guid = self._namespaces[module].guid
                previous_settings = module.settings
                module.settings = deepcopy(new_config.get('plugin_settings', {}).get(guid) or {})
                missing = object()
                for key in self._get_ui_state(module):
                    if previous_settings.get(key, missing) != module.settings.get(key, missing):
                        self._ui_values[module].pop(key, None)
                module.on_settings_changed()
            except Exception as e:
                log('error', f"Failed to execute on_settings_changed hook for {module.plugin_manifest.name}: {e}")
        # Emit after the hooks so field mutations made inside them (e.g. live
        # list filtering) are included in the published snapshot.
        self.republish_settings()

    def update_plugin_setting(self, plugin_guid: str, key: str, value: Any) -> bool:
        """Persist one plugin setting and notify the UI and owning plugin."""
        plugin = self._owners.get(plugin_guid)
        if plugin is None:
            log('warn', f"Ignoring setting update for unknown plugin {plugin_guid}")
            return False

        return self._update_owned_setting(plugin, key, value)

    def _update_owned_setting(self, plugin: PluginBase, key: str, value: Any) -> bool:
        plugin_guid = self._namespaces[plugin].guid
        if not isinstance(key, str) or not key:
            raise ValueError('Plugin setting keys must be nonempty strings')
        plugin_settings = self.config.setdefault('plugin_settings', {})
        settings = plugin_settings.setdefault(plugin_guid, {})
        settings[key] = deepcopy(value)
        plugin.settings = deepcopy(settings)
        self._ui_values[plugin].pop(key, None)

        save_config(self.config)
        emit_message("config", config=self.config)
        settings_config = plugin.settings_config
        if settings_config is not None:
            for grid in settings_config.get("grids", []):
                for field in grid.get("fields", []):
                    if self._is_status_field(field) and field.get("key") == key:
                        field["content"] = str(value)

        try:
            plugin.on_settings_changed()
        except Exception as e:
            log('error', f"Failed to execute on_settings_changed hook for {plugin.plugin_manifest.name}: {e}")
            return False

        self.publish_plugin_ui(plugin)
        return True

    def republish_settings(self) -> None:
        """Compatibility entry point publishing all current plugin UI.

        Safe to call from background threads: emit_message serializes writes.
        Used by plugins whose state changes outside the config-update paths."""
        for plugin in self.plugin_list.values():
            self.publish_plugin_ui(plugin, broadcast=False)
        self.broadcast_plugin_ui()

    def on_settings_button(self, plugin_guid: str, key: str, value: str | None = None):
        """Route a plugin settings button click to its owning plugin."""
        plugin = self._owners.get(plugin_guid)
        if plugin is None:
            log('warn', f"Ignoring settings button click for unknown plugin {plugin_guid}")
            return
        try:
            if value is None:
                plugin.on_settings_button(key)
            else:
                plugin.on_settings_button(key, value)
            self._refresh_plugin_setting_contents(plugin)
            self.publish_plugin_ui(plugin)
        except Exception as e:
            log('error', f"Plugin settings button '{key}' raised an exception: {e}")

    @staticmethod
    def _is_status_field(field: UIComponent) -> TypeGuard[ParagraphSetting | ErrorSetting]:
        return field.get('type') in {'paragraph', 'error'}

    def _refresh_plugin_setting_contents(self, plugin: PluginBase) -> None:
        """Reflect plugin-owned paragraph values after a settings action."""
        settings_config = plugin.settings_config
        if settings_config is None:
            return
        for grid in settings_config.get("grids", []):
            for field in grid.get("fields", []):
                if self._is_status_field(field):
                    setting_key = field.get("key")
                    if setting_key in plugin.settings:
                        field["content"] = str(plugin.settings[setting_key])

    def on_chat_start(self, helper: 'PluginHelper'):
        """
        Executed when the chat is started, and will call the on_chat_start hook for each plugin.
        """
        self._language_detector = None
        for module in self.plugin_list.values():
            log('debug', f"Executing on_chat_start hook for {module.plugin_manifest.name}")
            try:
                module.on_chat_start(helper._for_plugin(self._namespaces[module]))
                self.publish_plugin_ui(module)
            except Exception as e:
                if self._language_detector is not None and self._language_detector[0] == self._namespaces[module].guid:
                    self._language_detector = None
                log('error', f"Failed to execute on_chat_start hook for {module.plugin_manifest.name}: {e}")

    def on_chat_stop(self, helper: 'PluginHelper'):
        """
        Executed when the chat is stopped, and will call the on_chat_stop hook for each plugin.
        """
        for module in self.plugin_list.values():
            log('debug', f"Executing on_chat_stop hook for {module.plugin_manifest.name}")
            try:
                module.on_chat_stop(helper._for_plugin(self._namespaces[module]))
                self.publish_plugin_ui(module)
            except Exception as e:
                log('error', f"Failed to execute on_chat_stop hook for {module.plugin_manifest.name}: {e}")
        self._language_detector = None

    def register_language_detector(
        self, plugin_guid: str, detector: Callable[[str], str | None],
    ) -> None:
        if plugin_guid not in self._owners:
            raise ValueError("Language detectors must belong to a registered plugin.")
        if not callable(detector):
            raise ValueError("A language detector must be callable.")
        if self._language_detector is not None and self._language_detector[0] != plugin_guid:
            raise ValueError("Only one language detector plugin can be active.")
        self._language_detector = (plugin_guid, detector)

    @property
    def has_language_detector(self) -> bool:
        return self._language_detector is not None

    def detect_language(self, text: str) -> str | None:
        registered = self._language_detector
        if registered is None:
            return None
        language = registered[1](text)
        if language is not None and (
            not isinstance(language, str) or not re.fullmatch(r"[a-z]{2}", language)
        ):
            raise ValueError(f"Language detector '{registered[0]}' must return a lowercase "
                             "two-letter language code or None.")
        return language

    def create_plugin_model(self, plugin_guid: str, provider_id: str, expected_kind: str) -> LLMModel | STTModel | TTSModel | EmbeddingModel | None:
        """
        Create a model instance from a plugin provider.
        
        Args:
            plugin_guid: The GUID of the plugin providing the model
            provider_id: The provider's id within the plugin
            expected_kind: The expected model type ('llm', 'vlm', 'stt', 'tts', 'embedding')
            
        Returns:
            The model instance, or None if creation failed
        """
        provider = self.get_plugin_provider(plugin_guid, provider_id)
        if provider is None:
            log('error', f"Plugin provider '{plugin_guid}:{provider_id}' is not registered")
            return None
        if provider['kind'] != expected_kind:
            log('error', f"Plugin provider '{plugin_guid}:{provider_id}' has kind {provider['kind']}, expected {expected_kind}")
            return None

        # Find the plugin
        plugin = self._owners.get(plugin_guid)
        
        if plugin is None:
            log('error', f"Plugin with guid '{plugin_guid}' not found")
            return None
        
        # Get plugin settings
        settings = self.config.get('plugin_settings', {}).get(plugin_guid, {})
        
        # Call the plugin's create_model method
        try:
            model = plugin.create_model(provider_id, deepcopy(settings))
        except Exception as e:
            log('error', f"Plugin {plugin.plugin_manifest.name} failed to create model '{provider_id}': {e}")
            return None
        
        # Validate the returned model type
        expected_types = {
            'llm': LLMModel,
            'vlm': LLMModel,
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
