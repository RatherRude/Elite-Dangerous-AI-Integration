from abc import ABC, abstractmethod

from .PluginDependencies import PluginDependencies
from .PluginSettingDefinitions import PluginSettings

class PluginBase(ABC):
    """
    Base class for all plugins.
    """

    # Plugin name
    plugin_name: str
    # Define the settings for this plugin. This is the settings that will be shown in the UI.
    settings_config: PluginSettings | None = None

    @abstractmethod
    def __init__(self, plugin_name: str = "PluginBase"):
        """
        Initializes the plugin.

        Args:
            plugin_name (str, optional): The name of the plugin. Defaults to "PluginBase".
        """

        self.plugin_name = plugin_name

    # Register actions
    @abstractmethod
    def register_actions(self, deps: PluginDependencies):
        """
        Registers all actions for this plugin.

        This is called by the PluginManager once all plugins have been loaded and the assistant has been started. The PluginManager
        will then register all actions, projections and side effects with the respective managers.

        Args:
            deps (PluginDependencies): The dependencies object containing all services and managers
                that can be used by plugins.
        """

        pass
    
    # Register projections
    @abstractmethod
    def register_projections(self, deps: PluginDependencies):
        """
        Registers all projections for this plugin.

        This is called by the PluginManager once all plugins have been loaded and the assistant has been started. The PluginManager
        will then register all actions, projections and side effects with the respective managers.

        Args:
            deps (PluginDependencies): The dependencies object containing all services and managers
                that can be used by plugins.
        """
        pass

    # Register sideeffects
    @abstractmethod
    def register_sideeffects(self, deps: PluginDependencies):
        """
        Registers all side effects for this plugin.

        This is called by the PluginManager once all plugins have been loaded and the assistant has been started. The PluginManager
        will then register all actions, projections and side effects with the respective managers.

        Args:
            deps (PluginDependencies): The dependencies object containing all services and managers
                that can be used by plugins.
        """
        pass
    