import openai

from .EDKeys import EDKeys
from .EventManager import EventManager
from .ActionManager import ActionManager
from .SystemDatabase import SystemDatabase
from .Config import Config

class PluginDependencies():

    keys: EDKeys
    vision_client: openai.OpenAI | None = None
    llm_client: openai.OpenAI
    llm_model_name: str
    vision_model_name: str | None = None
    event_manager: EventManager
    action_manager: ActionManager
    config: Config
    system_db: SystemDatabase

    def __init__(self, config: Config, action_manager: ActionManager, event_manager: EventManager, llm_client: openai.OpenAI,
                     llm_model_name: str, vision_client: openai.OpenAI | None, vision_model_name: str | None,
                     system_db: SystemDatabase, ed_keys: EDKeys):
        self.keys = ed_keys
        self.system_db = system_db
        self.vision_client = vision_client
        self.llm_client = llm_client
        self.llm_model_name = llm_model_name
        self.vision_model_name = vision_model_name
        self.event_manager = event_manager
        self.action_manager = action_manager
        self.config = config
