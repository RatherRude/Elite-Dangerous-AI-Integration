import os
from typing import Any, Callable

from .Models import LLMModel, STTModel, TTSModel, EmbeddingModel
from .Logger import log
from .EDKeys import EDKeys
from .EventManager import EventManager, Projection as _Projection
from .ActionManager import ActionManager
from .SystemDatabase import SystemDatabase
from .Config import Config, save_config
from .Event import Event, PluginEvent as _PluginEvent
from .PromptGenerator import PromptGenerator
from .Assistant import Assistant

# reexport Projection and PluginEvent for plugins
Projection = _Projection
PluginEvent = _PluginEvent

# reexport Model base classes for plugins to extend
LLMModel = LLMModel
STTModel = STTModel
TTSModel = TTSModel
EmbeddingModel = EmbeddingModel

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .PluginManager import PluginManager
    from .PluginBase import PluginManifest

class PluginHelper():
    """Contains all built-inservices and managers that can be used by plugins"""

    _plugin_manager: 'PluginManager'
    _assistant: Assistant
    _prompt_generator: PromptGenerator
    _keys: EDKeys
    _vision_model: LLMModel | None = None
    _llm_model: LLMModel
    _vision_model_name: str | None = None
    _event_manager: EventManager
    _action_manager: ActionManager
    _config: Config
    _system_db: SystemDatabase
    PLUGIN_DATA_PATH: str = "plugin_data"

    def __init__(self, plugin_manager: 'PluginManager', prompt_generator: PromptGenerator, config: Config, action_manager: ActionManager, event_manager: EventManager, llm_model: LLMModel, vision_model: LLMModel | None,
                     system_db: SystemDatabase, ed_keys: EDKeys, assistant: Assistant):
        self._plugin_manager = plugin_manager
        self._prompt_generator = prompt_generator
        self._keys = ed_keys
        self._system_db = system_db
        self._vision_model = vision_model
        self._llm_model = llm_model
        self._event_manager = event_manager
        self._action_manager = action_manager
        self._config = config
        self._assistant = assistant

    def get_plugin_data_path(self, plugin_manifest: 'PluginManifest') -> str:
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
        def _sideeffect_wrapper(event: Event, context: dict[str, Any]):
            try:
                sideeffect(event, context)
            except Exception as e:
                log('error', f"Plugin sideeffect raised an exception: {e}")
        self._event_manager.register_sideeffect(_sideeffect_wrapper)

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
        def _prompt_handler(event: Event) -> str| None:
            if not isinstance(event, PluginEvent):
                return None
            if event.plugin_event_name != name:
                return None
            try:
                response = prompt_generator(event)
            except Exception as e:
                log('error', f"Plugin prompt_generator raised an exception: {e}")
                return None
            return response
        self._prompt_generator.register_prompt_event_handler(_prompt_handler)
        
        def _should_reply_check(event: Event, context: dict[str, Any]) -> bool | None:
            if not isinstance(event, PluginEvent):
                return None
            if event.plugin_event_name != name:
                return None
            try:
                return should_reply_check(event)
            except Exception as e:
                log('error', f"Plugin should_reply_check raised an exception: {e}")
                return False
        self._assistant.register_should_reply_handler(_should_reply_check)
        
    def register_status_generator(self, status_generator: Callable[[dict[str, dict]], list[tuple[str, Any]]]):
        """
        Register a status generator callback, for adding stuff to the models status context (Like ship info).
            
        :param status_generator: A callable that takes the current projected states and returns a list of (title, content) tuples.
        """
        def _status_generator_wrapper(states: dict[str, dict]) -> list[tuple[str, Any]]:
            try:
                return status_generator(states)
            except Exception as e:
                log('error', f"Plugin status_generator raised an exception: {e}")
                return []
        self._prompt_generator.register_status_generator(_status_generator_wrapper)

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
        def _condition_fn_wrapper(state: dict) -> bool:
            try:
                return condition_fn(state)
            except Exception as e:
                log('error', f"Plugin wait_for_condition condition_fn raised an exception: {e}")
                return False
        return self._event_manager.wait_for_condition(projection_name, _condition_fn_wrapper, timeout)
