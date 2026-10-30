from abc import ABC, abstractmethod
import json
from typing import Any, ClassVar, cast


from .PluginSettingDefinitions import PluginSettings, ModelProviderDefinition
from .PluginUIDefinitions import PluginUIView


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .PluginHelper import PluginHelper
    from .PluginManager import PluginManager
    from .Models import LLMModel, STTModel, TTSModel, EmbeddingModel


class PluginManifest(object):
    guid: str = ""
    name: str = ""
    author: str = ""
    version: str = ""
    repository: str = ""
    description: str = ""
    entrypoint: str = ""

    def __init__(self, j: str) -> None:
        self.__dict__.update(cast(dict[str, str], json.loads(j)))


class PluginBase(ABC):
    """
    Base class for all plugins.
    """

    plugin_manifest: 'PluginManifest'
    """
    The manifest of the plugin.
    """

    settings_schema_version: ClassVar[int] = 0
    """Target version for this plugin's persisted settings schema."""
    
    settings_config: PluginSettings | None = None
    """
    Define the settings for this plugin. This is the settings that will be shown in the UI.
    """
    
    settings: dict[str, Any] = {}
    """
    The current settings for this plugin.
    """
    
    model_providers: list[ModelProviderDefinition] | None = None
    """
    Define model providers this plugin contributes. These appear in Advanced Settings
    provider dropdowns (LLM, VLM, STT, TTS, Embedding). Override create_model() to instantiate them.
    """
    
    @abstractmethod
    def __init__(self, plugin_manifest: 'PluginManifest'):
        """
        Initializes the plugin.

        Args:
            plugin_manifest (PluginManifest): The manifest of the plugin. This is used to get metadata about the plugin.
            event_classes (list[type[Event]] | None, optional): The event classes for this plugin. This is used for deserializing stored events.
        """

        self.plugin_manifest = plugin_manifest
        # Instance-level dict: the class annotation holds a mutable default
        # that would otherwise be shared by every plugin instance until the
        # manager assigns the persisted settings.
        self.settings: dict[str, Any] = {}
        # Set by the PluginManager when settings are registered; lets plugins
        # broadcast UI updates even in config state (before the runtime runs).
        self._manager: 'PluginManager | None' = None
        
    def on_chat_start(self, helper: 'PluginHelper'):
        """
        Executed when the chat is started
        """
        pass

    def on_chat_stop(self, helper: 'PluginHelper'):
        """
        Executed when the chat is stopped
        """
        pass

    def on_settings_button(self, key: str, value: str | None = None):
        """Handle a click on a button declared in this plugin's settings UI.

        Row actions of list fields pass an optional value (e.g. the new title
        of an inline-edited row)."""
        pass

    def on_settings_changed(self) -> None:
        """Called after persisted settings for this plugin have changed."""
        pass

    def on_ui_changed(self, key: str, value: Any, state: dict[str, Any]) -> None:
        """Handle an input edit in settings or a view.

        The default preserves automatic persistence for declared settings.
        Overrides may keep transient input or explicitly call update_setting().
        """
        if self._manager is None:
            raise RuntimeError('Plugin is not registered')
        if key in self._manager._setting_input_keys(self):
            if not self.update_setting(key, value):
                raise RuntimeError('common.actionError')

    def get_ui_state(self) -> dict[str, Any]:
        """Return a detached snapshot of all declared input values."""
        if self._manager is None:
            raise RuntimeError('Plugin is not registered')
        return self._manager._get_ui_state(self)

    def set_ui_value(self, key: str, value: Any) -> None:
        """Set a declared input without persisting it or invoking its callback."""
        if self._manager is None:
            raise RuntimeError('Plugin is not registered')
        self._manager._set_ui_value(self, key, value)

    def on_registered(self) -> None:
        pass

    def get_plugin_data_path(self) -> str:
        if self._manager is None:
            raise RuntimeError('Plugin is not registered')
        return self._manager._get_owned_data_path(self)

    def get_ui_views(self) -> list[PluginUIView]:
        return []

    def get_ui_settings(self) -> PluginSettings | None:
        return self.settings_config

    def get_ui_translations(self) -> dict[str, dict[str, Any]]:
        return {}

    def on_ui_action(self, action: str, payload: dict[str, Any]) -> Any:
        if action == 'settings_button':
            key = payload.get('key')
            value = payload.get('value')
            if not isinstance(key, str) or (value is not None and not isinstance(value, str)):
                raise ValueError('common.invalidAction')
            return self.on_settings_button(key) if value is None else self.on_settings_button(key, value)
        raise ValueError('common.invalidAction')

    def publish_ui(self) -> None:
        if self._manager is not None:
            self._manager.publish_plugin_ui(self)

    def publish_settings(self) -> None:
        """Deprecated alias for publish_ui()."""
        self.publish_ui()

    def update_setting(self, key: str, value: Any) -> bool:
        if self._manager is None:
            raise RuntimeError('Plugin settings are not registered')
        return self._manager._update_owned_setting(self, key, value)

    def get_app_config(self) -> dict[str, Any]:
        return self._manager._get_owned_app_config(self) if self._manager is not None else {}

    def migrate_settings(self, settings: dict[str, Any], from_version: int) -> None:
        """Migrate settings from one schema version to the next."""
        pass

    def create_model(self, provider_id: str, settings: dict[str, Any]) -> 'LLMModel | STTModel | TTSModel | EmbeddingModel':
        """
        Create a model instance for the given provider.
        
        Override this method to instantiate your plugin's model providers.
        Called by the application when a plugin provider is selected in settings.
        
        Args:
            provider_id: The `id` field from your ModelProviderDefinition
            settings: The plugin's full settings dict (from plugin_settings[guid])
            
        Returns:
            An instance of LLMModel, STTModel, TTSModel, or EmbeddingModel. VLM
            providers use the LLMModel interface.
            
        Raises:
            ValueError: If provider_id is not recognized
            NotImplementedError: If not overridden but model_providers is defined
        """
        raise NotImplementedError(
            f"Plugin {self.plugin_manifest.name} defines model_providers but does not implement create_model()"
        )
