from abc import ABC, abstractmethod
from typing import Any

from .PluginHelper import PluginHelper, PluginManifest
from .PluginSettingDefinitions import PluginSettings
from .Event import Event

class PluginBase(ABC):
    """
    Base class for all plugins.
    """

    plugin_manifest: PluginManifest
    """
    The manifest of the plugin.
    """
    
    settings_config: PluginSettings | None = None
    """
    Define the settings for this plugin. This is the settings that will be shown in the UI.
    """

    event_classes: list[type[Event]] | None = None
    """
    Define the events for this plugin. This is used for deserializing stored events.
    """

    @abstractmethod
    def __init__(self, plugin_manifest: PluginManifest, event_classes: list[type[Event]] | None = None):
        """
        Initializes the plugin.

        Args:
            plugin_manifest (PluginManifest): The manifest of the plugin. This is used to get metadata about the plugin.
            event_classes (list[type[Event]] | None, optional): The event classes for this plugin. This is used for deserializing stored events.
        """

        self.plugin_manifest = plugin_manifest
        self.event_classes = event_classes
    
    def on_chat_start(self, helper: PluginHelper):
        """
        Executed when the chat is started
        """

    def on_chat_stop(self, helper: PluginHelper):
        """
        Executed when the chat is stopped
        """

        pass
    