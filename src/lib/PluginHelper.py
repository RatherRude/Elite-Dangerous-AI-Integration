import json
import os
from typing import Any, Callable, TypedDict, cast
import openai
from openai.types.chat import ChatCompletionMessageParam
from requests import auth

from .Logger import log
from .EDKeys import EDKeys
from .EventManager import EventManager, Projection
from .ActionManager import ActionManager
from .SystemDatabase import SystemDatabase
from .Config import Config, save_config
from .Event import Event, PluginEvent
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
        self._action_manager.registerAction(name=name, description=description, parameters=parameters, method=method, action_type=action_type, input_template=input_template)

    def register_projection(self, projection: Projection):
        """Register a projection to maintain state over time
        
        :param projection: The projection to register,
        """
        self._event_manager.register_projection(projection, raise_error = False)
        
    def register_sideeffect(self, sideeffect: Callable[[Event, dict[str, Any]], None]):
        """Register a sideeffect to react to events programmatically
        
        :param sideeffect: A callable that takes any incoming Event and the current projected states dict
        """
        self._event_manager.register_sideeffect(sideeffect)

    def dispatch_event(self, event: PluginEvent):
        """Dispatch an event from an outside source
        
        :param event: The event to dispatch
        """
        if not isinstance(event, PluginEvent):
            raise ValueError("Event must be of type PluginEvent")
        self._event_manager.incoming.put(event)

    def send_key(self, key_name: str, *args, **kwargs):
        """Send a key"""
        self._keys.send(key_name, *args, **kwargs)

    def register_event(self, name: str, should_reply_check: Callable[[PluginEvent], bool], prompt_generator: Callable[[PluginEvent], str]):
        """Register an event type

        :param name: The name of the plugin event to register
        :param should_reply_check: A callable that takes a PluginEvent and returns True if the assistant should reply to it, False otherwise
        :param prompt_generator: A callable that takes a PluginEvent and returns a string prompt to add to the assistant conversation
        """
        def _prompt_handler(event: Event) -> list[ChatCompletionMessageParam]:
            if not isinstance(event, PluginEvent):
                return []
            if event.plugin_event_name != name:
                return []
            response = prompt_generator(event)
            return [{"role": "user", "content": response}]
        self._prompt_generator.register_prompt_event_handler(_prompt_handler)
        
        def _should_reply_check(event: Event, context: dict[str, Any]) -> bool | None:
            if not isinstance(event, PluginEvent):
                return None
            if event.plugin_event_name != name:
                return None
            return should_reply_check(event)
        self._assistant.register_should_reply_handler(_should_reply_check)
        
    def register_status_generator(self, status_generator: Callable[[dict[str, dict]], list[tuple[str, Any]]]):
        """
        Register a status generator callback, for adding stuff to the models status context (Like ship info).
            
        :param status_generator: A callable that takes the current projected states and returns a list of (title, content) tuples.
        """
        self._prompt_generator.register_status_generator(status_generator)
        
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
