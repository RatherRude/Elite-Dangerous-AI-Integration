from abc import ABC, abstractmethod
import json
from typing import Any, cast


from .PluginSettingDefinitions import PluginSettings, ModelProviderDefinition


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .PluginHelper import PluginHelper
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
    provider dropdowns (LLM, STT, TTS, Embedding). Override create_model() to instantiate them.
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

    def create_model(self, provider_id: str, settings: dict[str, Any]) -> 'LLMModel | STTModel | TTSModel | EmbeddingModel':
        """
        Create a model instance for the given provider.
        
        Override this method to instantiate your plugin's model providers.
        Called by the application when a plugin provider is selected in settings.
        
        Args:
            provider_id: The `id` field from your ModelProviderDefinition
            settings: The plugin's full settings dict (from plugin_settings[guid])
            
        Returns:
            An instance of LLMModel, STTModel, TTSModel, or EmbeddingModel
            
        Raises:
            ValueError: If provider_id is not recognized
            NotImplementedError: If not overridden but model_providers is defined
        """
        raise NotImplementedError(
            f"Plugin {self.plugin_manifest.name} defines model_providers but does not implement create_model()"
        )