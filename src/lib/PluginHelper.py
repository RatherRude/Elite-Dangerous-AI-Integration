import json
import os
from typing import Any, Callable, TypedDict, cast
import openai
from openai.types.chat import ChatCompletionMessageParam
from requests import auth

from .EDKeys import EDKeys
from .EventManager import EventManager, Projection
from .ActionManager import ActionManager
from .SystemDatabase import SystemDatabase
from .Config import Config, save_config
from .Event import Event
from .PromptGenerator import PromptGenerator
from .Assistant import Assistant

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
    PLUGIN_DATA_PATH: str = "plugin_data"

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
    def get_plugin_setting(self, *key_paths: str) -> Any:
        """Get a plugin setting, from a number of keys forming a path"""
        cur_setting: dict[str, Any] | None = self._config.get('plugin_settings', None)
        
        # Recursively search for key paths
        for key_path in key_paths:
            cur_setting = (cur_setting or {}).get(key_path, None)
        
        return cur_setting

    def set_plugin_setting(self, *key_path: str, value: Any) -> None:
        """Set a plugin setting using a series of keys forming a path"""
        if not key_path:
            raise ValueError("At least one key must be provided")

        # Ensure plugin_settings exists
        if 'plugin_settings' not in self._config:
            self._config['plugin_settings'] = {}

        cur_setting = self._config['plugin_settings']

        # Traverse or create intermediate dictionaries
        for key in key_path[:-1]:
            if key not in cur_setting or not isinstance(cur_setting[key], dict):
                cur_setting[key] = {}
            cur_setting = cur_setting[key]

        # Set the final value
        cur_setting[key_path[-1]] = value
        save_config(self._config)

    def get_plugin_data_path(self, plugin_manifest: PluginManifest) -> str:
        """Get a plugin data path, from the plugin data folder"""
        plugin_data_path = os.path.abspath(os.path.join(self.PLUGIN_DATA_PATH, plugin_manifest.guid))
        if not os.path.exists(plugin_data_path):
            os.makedirs(plugin_data_path, exist_ok=True)
        return plugin_data_path

    def register_action(self, name, description, parameters, method: Callable[[dict, dict], str], action_type="ship", input_template: Callable[[dict, dict], str]|None=None):
        """Register an action"""
        self._action_manager.registerAction(name, description, parameters, method, action_type, input_template)

    def register_projection(self, projection: Projection):
        """Register a projection"""
        self._event_manager.register_projection(projection, raise_error = False)
        
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

    def wait_for_condition(self, projection_name: str, condition_fn, timeout=None):
        """Block until `condition_fn` is satisfied by the current or future
        state of the specified projection.

        :param projection_name: Name/identifier of the projection to watch.
        :param condition_fn: A callable that takes a dict (the current projection state)
                             and returns True/False.
        :param timeout: Optional timeout (seconds).
        :return: The state dict that satisfied the condition.
        :raises TimeoutError: If the condition isn't met within `timeout`.
        """
        return self._event_manager.wait_for_condition(projection_name, condition_fn, timeout)
