from abc import ABC, abstractmethod

import openai

from .EDKeys import EDKeys
from .EventManager import EventManager
from .ActionManager import ActionManager

class PluginBase(ABC):

    keys: EDKeys
    vision_client: openai.OpenAI | None = None
    llm_client: openai.OpenAI
    llm_model_name: str
    vision_model_name: str | None = None
    event_manager: EventManager
    action_manager: ActionManager
    plugin_name: str

    @abstractmethod
    def __init__(self, action_manager: ActionManager, event_manager: EventManager, llm_client: openai.OpenAI,
                     llm_model_name: str, vision_client: openai.OpenAI | None, vision_model_name: str | None,
                     ed_keys: EDKeys, plugin_name: str = "PluginBase"):
        self.keys = ed_keys
        self.vision_client = vision_client
        self.llm_client = llm_client
        self.llm_model_name = llm_model_name
        self.vision_model_name = vision_model_name
        self.event_manager = event_manager
        self.action_manager = action_manager
        self.plugin_name = plugin_name

    @abstractmethod
    def register_actions(self):
        pass