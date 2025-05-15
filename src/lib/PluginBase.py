from abc import ABC, abstractmethod

from .PluginHelper import PluginHelper
from .PluginSettingDefinitions import PluginSettings
from .Event import Event

class PluginBase(ABC):
    """
    Base class for all plugins.
    """

    plugin_name: str
    """
    The name of the plugin.
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
    def __init__(self, plugin_name: str = "PluginBase", event_classes: list[type[Event]] | None = None):
        """
        Initializes the plugin.

        Args:
            plugin_name (str, optional): The name of the plugin. Defaults to "PluginBase".
        """

        self.plugin_name = plugin_name
        self.event_classes = event_classes

    # Register actions
    @abstractmethod
    def register_actions(self, helper: PluginHelper):
        """
        Registers all actions for this plugin.

        This is called by the PluginManager once all plugins have been loaded and the assistant has been started. The PluginManager
        will then register all actions, projections and side effects with the respective managers.

        Args:
            helper (PluginHelper): The helper class that can be used to register actions, projections, side effects and more.
        """

        pass
    
    # Register projections
    @abstractmethod
    def register_projections(self, helper: PluginHelper):
        """
        Registers all projections for this plugin.

        This is called by the PluginManager once all plugins have been loaded and the assistant has been started. The PluginManager
        will then register all actions, projections and side effects with the respective managers.

        Args:
            helper (PluginHelper): The helper class that can be used to register actions, projections, side effects and more.
        """
        pass

    # Register sideeffects
    @abstractmethod
    def register_sideeffects(self, helper: PluginHelper):
        """
        Registers all side effects for this plugin.

        This is called by the PluginManager once all plugins have been loaded and the assistant has been started. The PluginManager
        will then register all actions, projections and side effects with the respective managers.

        Args:
            helper (PluginHelper): The helper class that can be used to register actions, projections, side effects and more.
        """
        pass
    @abstractmethod
    def register_prompt_generators(self, helper: PluginHelper):
        """
        Registers all prompt generators for this plugin.

        This is called by the PluginManager once all plugins have been loaded and the assistant has been started. The PluginManager
        will then register all actions, projections and side effects with the respective managers.

        Prompt generators are used to generate prompts for the assistant, based on events.

        Args:
            helper (PluginHelper): The helper class that can be used to register actions, projections, side effects and more.
        """

        pass
    
    @abstractmethod
    def on_chat_stop(self, helper: PluginHelper):
        """
        Executed when the chat is stopped
        """

        pass
    