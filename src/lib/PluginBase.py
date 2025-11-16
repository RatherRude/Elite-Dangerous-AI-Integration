from abc import ABC, abstractmethod
import json
from typing import Any, cast


from .PluginSettingDefinitions import PluginSettings


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .PluginHelper import PluginHelper


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
    