from abc import ABC, abstractmethod

from .PluginDependencies import PluginDependencies
from .PluginSettingDefinitions import PluginSettings

class PluginBase(ABC):

    # Plugin name
    plugin_name: str
    # Define the settings for this plugin. This is the settings that will be shown in the UI.
    settings_config: PluginSettings | None = None

    @abstractmethod
    def __init__(self, plugin_name: str = "PluginBase"):
        self.plugin_name = plugin_name

    # Register actions
    @abstractmethod
    def register_actions(self, deps: PluginDependencies):
        pass
    
    # Register projections
    @abstractmethod
    def register_projections(self, deps: PluginDependencies):
        pass

    # Register sideeffects
    @abstractmethod
    def register_sideeffects(self, deps: PluginDependencies):
        pass
    