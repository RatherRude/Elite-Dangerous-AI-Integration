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

    # Register actions
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
    def register_sideeffects(self, helper: PluginHelper):
        """
        Registers all side effects for this plugin.

        This is called by the PluginManager once all plugins have been loaded and the assistant has been started. The PluginManager
        will then register all actions, projections and side effects with the respective managers.

        Args:
            helper (PluginHelper): The helper class that can be used to register actions, projections, side effects and more.
        """
        pass

    def register_prompt_event_handlers(self, helper: PluginHelper):
        """
        Registers all prompt event handlers for this plugin.

        This is called by the PluginManager once all plugins have been loaded and the assistant has been started. The PluginManager
        will then register all actions, projections and side effects with the respective managers.

        Prompt event hanlderts are used to generate prompts for the assistant, based on events.

        Args:
            helper (PluginHelper): The helper class that can be used to register actions, projections, side effects and more.
        """

        pass
    
    def register_status_generators(self, helper: PluginHelper):
        """
        Registers all prompt status generators for this plugin.

        This is called by the PluginManager once all plugins have been loaded and the assistant has been started. The PluginManager
        will then register all actions, projections and side effects with the respective managers.

        Status generators are used to add status information to the assistant prompt.

        Args:
            helper (PluginHelper): The helper class that can be used to register actions, projections, side effects and more.
        """

        pass
    
    def register_should_reply_handlers(self, helper: PluginHelper):
        """
        Registers handlers that will decide wether the assistant should reply to any given event.
        False means no reply, True means reply, None means no decision, leaving it to the assistant
        """

        pass
    
    def on_plugin_helper_ready(self, helper: PluginHelper):
        """
        Executed when the chat is started and the PluginHelper is ready. At this point, all managers are ready, although not all actions and such are registered yet.
        This is a good time to do any additional setup that requires the PluginHelper.
        """

        pass

    def on_chat_stop(self, helper: PluginHelper):
        """
        Executed when the chat is stopped
        """

        pass
    