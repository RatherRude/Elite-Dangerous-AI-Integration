# Plugin development for COVAS:NEXT

Do you want to build a plugin, to expand on COVAS' features? This page will help you get started.

For plugin-provided views, translations, UI actions, and event-driven updates,
see [Plugin UI and Runtime Integration](ui-integration.md). It documents the
generic framework available in this checkout, with a complete working example.

## Prerequisites

- **COVAS:NEXT Project**: Ensure you have the project running from source, as described in [CONTRIBUTING.md](https://github.com/RatherRude/Elite-Dangerous-AI-Integration/blob/main/CONTRIBUTING.md).

# The easy way to get started

To quickly create a starting point, we suggest using [this cookiecutter template](http://github.com/COVAS-Labs/COVAS-NEXT-Plugin-Template).
Use the template to create a project in a sub-folder of the `plugins` folder.

## Plugin structure

Plugins are loaded from sub-folders of `./plugins`, up to one level deep.  
Create a new sub-folder for your plugin, and create a new Python script and a `manifest.json` file. Both of these are described below.
You can create a git repository, and even include other assets or libraries in this subfolder.

### Folder structure:

- `/plugins`
  - `/YourPlugin` <- Main folder for your plugin. Contains source code and assets.
    - `/manifest.json` <- The plugin manifest, which defines meta data and the entrypoint.
    - `/deps` <- Python dependencies.
    - `/YourPlugin.py` <- Contains at least one class implementing the `PluginBase` base class.
    - `/requirements.txt` <- Only used when packaging additional Python dependencies. Not needed when distributing.
    - `__init__.py` <- This is optional and empty, but required to use relative imports´(like `from .PackageName import ClassName`).
  - `/AnotherPlugin`
- `plugin_data` <- For user data. These folders are created at runtime and are not part of your plugin source code.
  - `5b68272b-9949-4cad-b7c4-14da97a7f1c2` <- Plugin guid from metadata. This is your plugins data folder, which is used for persistent user data.
    - `YourPluginData.db` <- This means all data in this folder persists when updating and replacing the plugin.
  - `fc8a17ce-91ba-4dc7-819e-e65b02326244` <- Use `helper.get_plugin_data_path()` to get the path to your plugins dedicated data folder.

Create a new class implementing `PluginBase` like this:

```python
from lib.PluginBase import PluginBase, PluginManifest
from lib.PluginHelper import PluginHelper
from lib.PluginSettingDefinitions import PluginSettings, SettingsGrid
from lib.PluginUIDefinitions import Toggle


class ExamplePlugin(PluginBase):
    def __init__(self, plugin_manifest: PluginManifest):
        super().__init__(plugin_manifest)
        self.settings_config = PluginSettings(
            key="settings", label="@title", icon="settings",
            grids=[SettingsGrid(
                key="general", label="@general",
                fields=[Toggle(
                    key="my_bool_setting", label="@enabled", type="toggle",
                    readonly=False, placeholder=None, default_value=False,
                )],
            )],
        )

    def get_ui_translations(self):
        return {
            "en": {"title": "Example plugin", "general": "General", "enabled": "Enabled"},
            "fr": {"title": "Plugin d’exemple", "general": "Général", "enabled": "Activé"},
        }

    def on_chat_start(self, helper: PluginHelper):
        # Register actions, events, projections, side effects, and status generators here.
        self.enabled = self.settings.get("my_bool_setting", False)

    def on_chat_stop(self, helper: PluginHelper):
        # Clean up runtime resources here.
        pass
```

And a manifest file like this: (**The GUID must be unique. Generate a new one for your project**)

```json
{
  "guid": "babe1f36-bc38-4b62-8cda-80a7a68835f6",
  "name": "Example Plugin",
  "version": "0.0.1",
  "author": "John Doe",
  "description": "A sample plugin",
  "entrypoint": "YourPlugin.py"
}
```

## Updating plugin settings from Python

For derived view/status data, update plugin-owned state and publish it without
persisting a configuration change:

```python
self.publish_ui()
```

`get_ui_views()` and `get_ui_settings()` return the latest presentation. See the
[UI guide](ui-integration.md#lifecycle-and-public-hooks) for their lifecycle.
`publish_ui()` refreshes both contexts, including dynamic options, text and
progress indicators. `publish_settings()` remains a deprecated alias.
The shared typed components from `lib.PluginUIDefinitions` work in settings
`fields` and view `content`. Historical names such as `ToggleSetting` and
`TextSetting` remain exact aliases at their original import path.

The public API for a persisted setting is bound to the registered plugin:

```python
self.update_setting("status", "@importCompleted")
```

The manager persists the value in `config.json`, emits the normal `config` message,
and calls the plugin's optional `on_settings_changed()` hook. The hook is also called
when settings are changed from the UI. Plugins should keep durable application data
in their dedicated `plugin_data/<guid>` directory rather than in plugin settings.
Setting keys are flat local keys, not configuration paths. The core selects the
owner from its registration registry and stores the value unchanged; local
translation references are qualified only when exporting presentation. For
example, `@importCompleted` becomes `plugin.<registered-guid>.importCompleted`
in a status paragraph. Normal plugin input edits use the shared
`on_ui_changed(key, value, state)` callback in both settings and views. Its default
implementation persists declared settings and calls `on_settings_changed()`,
preserving existing plugins. Override it to keep search/filter input transient
or explicitly persist selected preferences with `update_setting()`. The state
snapshot includes all current inputs; buttons can read it with `get_ui_state()`.
The historical configuration transport remains supported; UI publication
must not be used as a substitute for saving a setting or plugin database change.

The `PluginBase` base class has the following methods that can be overridden:

- `on_registered(self)`:
   Called once after the core assigns the plugin's namespace. Use
   `self.get_plugin_data_path()` here for configuration-state data initialization.

- `on_chat_start(self, helper: PluginHelper)`:  
   Called when the chat is started. This is where you should register all plugin functionality:

  - Register actions with `helper.register_action()`
  - Register custom events with `helper.register_event()`
  - Register projections with `helper.register_projection()`
  - Register sideeffects with `helper.register_sideeffect()`
  - Register status generators with `helper.register_status_generator()`
  - Perform any additional setup that requires the `PluginHelper`

- `on_chat_stop(self, helper: PluginHelper)`:  
   Called when the chat is stopped. Use this to perform any cleanup or finalization needed by your plugin.

- `on_settings_button(self, key: str, value: str | None = None)`:
    Called for settings buttons, grid header actions, and list row actions.
    Row actions use `<action>:<row-key>`; inline edits pass the edited value.
- `on_settings_changed(self)`:
    Called after configuration changes; refresh derived content as needed.
- `on_ui_changed(self, key, value, state)`:
    Called for an input edit in settings or views, with a detached snapshot of
    current inputs. Delegate to `super()` to retain default settings persistence.
- `get_ui_views()`, `get_ui_settings()`, `get_ui_translations()`, and `on_ui_action(action, payload)`:
    Optional generic UI contributions and structured interactions. See the
    [UI guide](ui-integration.md) for types and examples.

Use the public `PluginHelper` methods below for runtime integration. In particular,
use `get_current_state()` instead of reaching into `_event_manager`, and the
`PluginBase` publication hooks instead of mutating manager registries.

## Conditional settings

Use `ConditionSetting` to show nested fields only when another setting matches a
comparison. It works in plugin `settings_config`, model-provider `settings_config`,
and character-scoped `voice_settings_config`. Conditions can contain other conditions.

```python
from lib.PluginBase import PluginBase
from lib.PluginSettingDefinitions import (
    PluginSettings, SettingsGrid, ToggleSetting, NumericalSetting,
    ParagraphSetting, ConditionSetting,
)


class ExamplePlugin(PluginBase):
    settings_config = PluginSettings(
        key="example",
        label="Example Plugin",
        icon="settings",
        grids=[SettingsGrid(
            key="general",
            label="General",
            fields=[
                ToggleSetting(
                    key="enable_advanced", label="Enable advanced settings",
                    type="toggle", default_value=False,
                ),
                ConditionSetting(
                    key="advanced_options",
                    type="condition",
                    condition={
                        "key": "enable_advanced", "operator": "eq",
                        "value": True, "default_show": False,
                    },
                    fields=[
                        NumericalSetting(
                            key="temperature", label="Temperature", type="number",
                            default_value=0.7, min_value=0, max_value=2, step=0.1,
                        ),
                        ConditionSetting(
                            key="high_temperature_notice",
                            type="condition",
                            condition={
                                "key": "temperature", "operator": "geq",
                                "value": 1.5, "default_show": False,
                            },
                            fields=[ParagraphSetting(
                                key="temperature_notice", label="High temperature",
                                type="paragraph",
                                content="Responses may be less predictable.",
                            )],
                        ),
                    ],
                ),
            ],
        )],
    )

    def on_chat_start(self, helper):
        advanced = self.settings.get("enable_advanced", False)
        temperature = self.settings.get("temperature", 0.7) if advanced else 0.7
        # Use temperature in your plugin.
```

The container's `key` identifies the UI element; `condition.key` is the flat key
to read from the current settings namespace (the owning plugin, or the current
character/provider for voice settings, merged with its owning plugin's global
settings). `condition.default_show` is the visibility
result when that key is unset (missing or null), and defaults to `False`. It is
not an input to the comparison, and input defaults are not used for condition
evaluation. Saved values, including `False`, `0`, and an empty string, are compared
normally. Keep element keys unique within each list of fields.

Use `condition={"key": "custom_mode", "operator": "is_unset"}` to show help
until a value is saved. `is_set` and `is_unset` evaluate presence directly, so
`default_show` does not affect these two operators. `False`, `0`, and `""` all
count as set.

| Operator | Comparison |
| --- | --- |
| `eq`, `neq` | Strict equality / inequality (no string-to-number conversion) |
| `gt`, `geq` | Greater than / greater than or equal |
| `lt`, `leq` | Less than / less than or equal |
| `in`, `not_in` | Setting value is / is not in the list supplied as `value` |
| `contains`, `not_contains` | A list setting contains / does not contain `value`, or a string setting contains / does not contain a string substring |
| `is_set`, `is_unset` | Whether the key has a non-null value / is missing or null; `value` is not required |

For example, show fields in either of two modes with
`condition={"key": "mode", "operator": "in", "value": ["custom", "expert"], "default_show": False}`.
Equality and list membership compare primitive values by type and value; objects
are not compared structurally. Numeric comparisons require finite numbers.
Invalid operand types for numeric or containment comparisons hide the fields,
including for `not_in` and `not_contains`.

Visibility updates as settings change. Hidden values are preserved and nested
inputs still store their own flat keys; no value is stored for the condition
container. Conditions control UI visibility only: plugin code should decide
whether to use the hidden values, as the example does above. Nested buttons still
call `on_settings_button` with their own key.

## Model Providers

### Configuration migration ownership

`Config.py` handles the one-time conversion of old built-in provider selectors and
top-level settings into `plugin:<guid>:<provider-id>` references and flat
`plugin_settings[guid]` dictionaries. It leaves each plugin's `settings_version`
unchanged (or absent for newly migrated settings). It does not import plugins or
apply their current model defaults.

After that handoff, each plugin owns its migrations independently:

```python
class ExamplePlugin(PluginBase):
    settings_schema_version = 2

    def migrate_settings(self, settings, from_version):
        if from_version == 0:
            # Upgrade the initial settings copied from the old built-in provider.
            settings.setdefault("new_option", False)
        elif from_version == 1:
            # Upgrade this plugin's next schema without repeating earlier changes.
            if "old_option" in settings:
                settings.setdefault("renamed_option", settings.pop("old_option"))
```

`PluginManager` treats an absent version as `0`, runs migrations in order, and
stores the resulting `settings_version`. This happens at startup and when importing
an older backup while the application is running. Already-current schemas are not
migrated again, and versions newer than the installed plugin are preserved.
The application `config_version` does not need to change for a plugin-only update.

The bundled OpenAI, Google AI Studio, and OpenRouter plugins also preserve imported
per-role API-key overrides. Legacy non-empty role keys take precedence over the
old global key. If a backup uses different keys for different roles, those effective
credentials remain in use until the shared API-key setting is changed; a new shared
key then takes precedence for all roles. Existing explicit plugin values take
precedence over values copied by the legacy handoff.

Plugins can register model providers by assigning `self.model_providers` in their constructor. Each provider definition requires `kind`, `id`, `label`, and `settings_config`. The optional `slots` field limits where a provider appears; omitting it preserves the existing kind-based behavior.

```python
from typing import Any
from lib.PluginSettingDefinitions import ModelProviderDefinition

self.model_providers = [ModelProviderDefinition(
    kind="llm", id="llm", label="Example LLM", settings_config=[],
)]

def create_model(self, provider_id: str, settings: dict[str, Any]):
    if provider_id == "llm":
        return ExampleLLM(settings)
    raise ValueError(f"Unknown provider: {provider_id}")
```

Provider references use `plugin:<plugin-guid>:<provider-id>`. `create_model` receives the same provider ID and the plugin's flat `plugin_settings[plugin_guid]` dictionary. The existing `LLMModel`, `STTModel`, `TTSModel`, and `EmbeddingModel` interfaces remain the model contracts; in particular, LLM implementations receive `generate(messages, tools, tool_choice)`. Optional provider metadata such as `slots` and `api_key_detection` is not required for existing plugins.

TTS providers may optionally add `voice_settings_config`, using the same `SettingsGrid` format as provider settings. These values are stored per character and provider rather than in the plugin's global settings. Use `voice` as the primary field key when the provider has one; its label and field type may represent a named voice, a description, or a reference-audio path. Providers without a voice concept may omit that field, while an explicit empty list declares that the provider has no character-level voice controls. Omitting `voice_settings_config` entirely retains the legacy `synthesize(text, voice)` behavior.

### Voice settings namespace and conditions

Voice inputs and conditions read a merged settings namespace: the owning plugin's
global configuration, overlaid with the current character's provider-specific
configuration. **Character settings take precedence on matching keys**, including
explicit `False`, `0`, empty strings, and null values. Editing a voice input writes
only to the character configuration.

Keep logical setting keys unique across a plugin's global settings and character
voice settings, as well as across its providers: grids and condition containers do
not introduce a storage namespace. For example, use `tts_model` globally and
`voice` / `instructions` per character. Do not give unrelated global and character
inputs the same key. Alternative, mutually exclusive representations of the same
setting may share its key deliberately.

A character condition can therefore reference a global model selection:

```python
ConditionSetting(
    key="tts_style_options",
    type="condition",
    condition={
        "key": "tts_model",
        "operator": "in",
        "value": ["model-with-style", "another-model-with-style"],
        "default_show": True,  # Whether the provider's unsaved default supports style
    },
    fields=[TextAreaSetting(
        key="instructions", label="Voice style", type="textarea", default_value="",
    )],
)
```

At synthesis time, `synthesize_with_settings` receives the same merged namespace,
with declared voice defaults supplying values absent from both saved configurations.
Nested defaults are included even while their fields are hidden. A condition's
`default_show` still applies when its referenced key is unset; input defaults are
not substituted into UI condition comparisons.

```python
from lib.PluginSettingDefinitions import ModelProviderDefinition, SettingsGrid, TextSetting

self.model_providers = [ModelProviderDefinition(
    kind="tts", id="tts", label="Example TTS", settings_config=[],
    voice_settings_config=[SettingsGrid(
        key="voice",
        label="Voice",
        fields=[TextSetting(
            key="voice", label="Reference audio path", type="text",
            readonly=False, placeholder=None, default_value="",
            max_length=None, min_length=None,
        )],
    )],
)]
```

Existing implementations only need `synthesize(text, voice)`. Providers that require additional character voice fields may override `synthesize_with_settings(text, settings)`; its default implementation forwards `settings["voice"]` to `synthesize`.

## PluginHelper Methods

The `PluginHelper` class provides several methods for interacting with the COVAS:NEXT system:

### Event Management

- `helper.register_event(name: str, should_reply_check: Callable[[PluginEvent], bool], prompt_generator: Callable[[PluginEvent], str])`:  
   Register a custom plugin event type. This is the preferred way to handle custom events from your plugin.
  - `name`: The name of the plugin event to register
  - `should_reply_check`: A callable that takes a PluginEvent and returns True if the assistant should reply to it, False otherwise
  - `prompt_generator`: A callable that takes a PluginEvent and returns a string prompt to add to the assistant conversation
- `helper.dispatch_event(event: PluginEvent)`:  
   Dispatch an event from an outside source. The event must be of type `PluginEvent`.

### State Management

- `helper.get_current_state()`:
    Return `(processed_events, projected_states)`. Projection values may be
    Pydantic models; treat shared state as read-only. Use the initial snapshot to
    populate a runtime view before receiving new events.

- `helper.register_projection(projection: Projection)`:  
   Register a projection to maintain state over time. Projections are used to track and update state in response to events.

- `helper.register_sideeffect(sideeffect: Callable[[Event, dict[str, Any]], None])`:  
   Register a sideeffect to react to events programmatically. The callable receives any incoming Event and the current projected states dict.

- `helper.wait_for_condition(projection_name: str, condition_fn, timeout=None)`:  
   Block until a condition is satisfied by the current or future state of a specified projection. Returns the state dict that satisfied the condition. Raises `TimeoutError` if the condition isn't met within the timeout period.
  ```python
  # Example usage:
  state = helper.wait_for_condition(
      "MyProjection",
      lambda state: state.get("ready") == True,
      timeout=5.0
  )
  ```

### Action & Status

- `helper.register_action(name, description, parameters, method, action_type="ship", input_template=None)`:
    Register an action that the AI can execute.
    `parameters` is a Pydantic model class. The callback receives the validated
    model and projection states; its returned string is consumed by the assistant.
    UI action callbacks are separate and may return JSON-serializable results.

- `helper.register_status_generator(status_generator: Callable[[dict[str, dict]], list[tuple[str, Any]]])`:  
   Register a status generator callback for adding information to the model's status context. The callable takes the current projected states and returns a list of (title, content) tuples.

### Input Simulation

- `helper.send_key(key_name: str, *args, **kwargs)`:  
   Send a key input to the game.

### Data & Assets

- `helper.get_plugin_data_path() -> str`:
   Get the absolute path to the registered plugin's data directory. The same
   directory is available before Run through `self.get_plugin_data_path()`.
   The legacy manifest argument is accepted only when it matches the owner.

### A note on events

The current base constructor accepts only the manifest:

```python
class HelloWorld(PluginBase):
    def __init__(self, plugin_manifest: PluginManifest):
        super().__init__(plugin_manifest)
```

Use `PluginEvent` for custom payloads and register its handling during Run. Live
events can update a view through `publish_ui()`. Historic `GameEvent`s update
projections but are skipped by the normal side-effect dispatch; use current
projection state to seed a runtime UI rather than expecting callback replay.

### Registering Custom Plugin Events

To handle custom plugin events, use the `helper.register_event()` method in `on_chat_start()`:

```python
def on_chat_start(self, helper: PluginHelper):
    helper.register_event(
        name="value_changed",
        should_reply_check=lambda event: True,  # or your custom logic
        prompt_generator=lambda event: f"The new value is now {event.plugin_event_content['key']}"
    )
```

Then dispatch your custom event using:

```python
from lib.Event import PluginEvent

helper.dispatch_event(PluginEvent(
    plugin_event_name="value_changed",
    plugin_event_content={"key": "value"}
))
```

**Note:** The `dispatch_event()` method validates that the event is of type `PluginEvent` and will raise a `ValueError` if it's not.

The manager supplies a separate bound helper to each plugin. Registration and
dispatch qualify the local event name with the registered namespace; event
callbacks receive the local name. Identical local names in different plugins do
not collide. Plugins must not prefix event names with their manifest GUID.

For further details or questions, [Join our Discord](https://discord.gg/9c58jxVuAT).

## Python Dependencies

If your plugin needs additional 3rd party Python modules, then you need to package them along with your plugin.  
I suggest creating a `requirements.txt` for your plugin, and using `pip install -r requirements.txt --target=./deps` to install the packages to the `deps` subfolder.  
Only modules already used in COVAS:NEXT, and those placed inside the `deps` subfolder will be made available.  
**The `deps` sub-folder should be included when you distribute your plugin.**

## Plugin Lifecycle

Below is a list of plugin functions and when they are called.  
Initialization is best done either in the constructor for stuff that should persist between chat sessions, or in the `on_chat_start()` function for registration and setup that requires the `PluginHelper`.  
Remember to clean up references etc. in `on_chat_stop()`.

| Function          | Execution time                                                                                                                                                                                                                         |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `__init__`        | The constructor is executed immediately upon loading the entrypoint file. Use this for initialization that doesn't require the `PluginHelper`.                                                                                         |
| `on_registered()` | Called once with a core-owned namespace and data path, before UI contributions are read. |
| `settings_config` | Settings may be defined on the instance; the default `get_ui_settings()` exports them during registration/publication. |
| `settings` | An instance dictionary populated from persisted configuration after construction and refreshed when configuration changes. |
| `on_chat_start()` | This function is executed when the chat assistant is started.<br>**All registration should happen here:** register actions, projections, sideeffects, custom events, and status generators using the provided `PluginHelper` instance. |
| `on_chat_stop()`  | This function runs when the user stops the chat assistant. Use this for any cleanup between chat sessions.                                                                                                                             |
| `get_ui_views()` / `get_ui_translations()` | Read at registration and UI publication; usable before Run without a runtime helper. |
| `get_ui_settings()` | Read when registering or republishing the exported settings schema. |
| `on_ui_action()` | Called for a GUID-routed UI command in configuration or runtime. |
| `publish_ui()` / `publish_settings()` | Explicitly publish changed presentation after events or background work; no configuration persistence. |
