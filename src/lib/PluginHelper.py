from typing import Any, Callable
import openai
from openai.types.chat import ChatCompletionMessageParam

from .EDKeys import EDKeys
from .EventManager import EventManager, Projection
from .ActionManager import ActionManager
from .SystemDatabase import SystemDatabase
from .Config import Config
from .Event import Event
from .PromptGenerator import PromptGenerator
from .Assistant import Assistant

class PluginHelper():
    """Contains all built-inservices and managers that can be used by plugins"""

    _assistant: Assistant
    _prompt_generator: PromptGenerator
    _keys: EDKeys
    _vision_client: openai.OpenAI | None = None
    _llm_client: openai.OpenAI
    _llm_model_name: str
    _vision_model_name: str | None = None
    _event_manager: EventManager
    _action_manager: ActionManager
    _config: Config
    _system_db: SystemDatabase

    def __init__(self, prompt_generator: PromptGenerator, config: Config, action_manager: ActionManager, event_manager: EventManager, llm_client: openai.OpenAI,
                     llm_model_name: str, vision_client: openai.OpenAI | None, vision_model_name: str | None,
                     system_db: SystemDatabase, ed_keys: EDKeys, assistant: Assistant):
        self._prompt_generator = prompt_generator
        self._keys = ed_keys
        self._system_db = system_db
        self._vision_client = vision_client
        self._llm_client = llm_client
        self._llm_model_name = llm_model_name
        self._vision_model_name = vision_model_name
        self._event_manager = event_manager
        self._action_manager = action_manager
        self._config = config
        self._assistant = assistant
    
    # Plugin helper functions
    def get_plugin_settings(self, *key_paths: str) -> Any:
        """Get a plugin setting, from a number of keys forming a path"""
        cur_setting: dict[str, Any] = self._config.get('plugin_settings', {})
        
        # Recursively search for key paths
        for key_path in key_paths:
            cur_setting = cur_setting.get(key_path, {})
        
        return cur_setting

    def register_action(self, name, description, parameters, method: Callable[[dict, dict], str], action_type="ship", input_template: Callable[[dict, dict], str]|None=None):
        """Register an action"""
        self._action_manager.registerAction(name, description, parameters, method, action_type, input_template)

    def register_projection(self, projection: Projection):
        """Register a projection"""
        self._event_manager.register_projection(projection)
        
    def register_sideeffect(self, sideeffect: Callable[[Event, dict[str, Any]], None]):
        """Register a sideeffect"""
        self._event_manager.register_sideeffect(sideeffect)

    def put_incoming_event(self, event: Event):
        """Put an event into the incoming queue"""
        self._event_manager.incoming.put(event)
        
    def get_projection(self, projection_type: type) -> Projection[object] | None:
        """Get a projection by type"""
        return self._event_manager.get_projection(projection_type)

    def register_keybindings(self, keybindings: dict[str, dict[str, int | bool | list[Any]]]):
        """Register keybindings"""
        self._keys.keys.update(keybindings)

    def send_key(self, key_name: str):
        """Send a key"""
        self._keys.send(key_name)
        
    def register_prompt_event_handler(self, prompt_event_handler: Callable[[Event], list[ChatCompletionMessageParam]]):
        """Register a prompt generator callback, to respond to events"""
        self._prompt_generator.register_prompt_event_handler(prompt_event_handler)
        
    def register_status_generator(self, status_generator: Callable[[dict[str, dict]], list[tuple[str, Any]]]):
        """Register a status generator callback, for adding stuff to the models status context (Like ship info)."""
        self._prompt_generator.register_status_generator(status_generator)
        
    def register_should_reply_handler(self, should_reply_handler: Callable[[Event, dict[str, Any]], bool | None]):
        """Register a handler that will decide wether the assistant should reply to any given event. False means no reply, True means reply, None means no decision, leaving it to the assistant"""
        self._assistant.register_should_reply_handler(should_reply_handler)