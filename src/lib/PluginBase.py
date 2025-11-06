from abc import ABC, abstractmethod
import json
from typing import Any, cast


from .PluginSettingDefinitions import PluginSettings
from .Event import Event
from .Config import Config


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

    @abstractmethod
    def __init__(self, plugin_manifest: 'PluginManifest'):
        """
        Initializes the plugin.

        Args:
            plugin_manifest (PluginManifest): The manifest of the plugin. This is used to get metadata about the plugin.
            event_classes (list[type[Event]] | None, optional): The event classes for this plugin. This is used for deserializing stored events.
        """

        self.plugin_manifest = plugin_manifest
        
    def on_settings_changed(self, plugin_settings: dict[str, Any], global_settings: Config):
        """
        Executed when the plugin settings are changed.

        Args:
            new_settings (dict[str, Any]): The new settings.
        """
    
    def on_chat_start(self, helper: 'PluginHelper'):
        """
        Executed when the chat is started
        """

    def on_chat_stop(self, helper: 'PluginHelper'):
        """
        Executed when the chat is stopped
        """

        pass
    