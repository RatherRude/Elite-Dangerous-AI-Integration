# Plugin development for COVAS:NEXT

Do you want to build a plugin, to expand on COVAS' features? This page will help you get started.

## Prerequisites

- **COVAS:NEXT Project**: Ensure you have the project running from source, as described in [CONTRIBUTING.md](./CONTRIBUTING.md).

# The easy way to get started

To quickly create a starting point, we suggest using [this cookiecutter template](http://github.com/MaverickMartyn/COVAS-NEXT-Plugin-Template).
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
# Main plugin class
# This is the class that will be loaded by the PluginManager.
class ExamplePlugin(PluginBase):
    def __init__(self, plugin_manifest: PluginManifest):
        super().__init__(plugin_manifest)

        # Define the plugin settings
        # This is the settings that will be shown in the UI for this plugin.
        self.settings_config: PluginSettings | None = PluginSettings(
            key="MediaPlayerPlugin",
            label="Example Plugin Settings",
            icon="wrench", # Uses Material Icons, like the built-in settings-tabs.
            grids=[
                SettingsGrid(
                    key="general",
                    label="General",
                    fields=[
                        ToggleSetting(
                            key="bool_setting",
                            label="Boolean Setting",
                            type="toggle",
                            readonly = False,
                            placeholder = None,
                            default_value = False
                        ),
                    ]
                ),
            ]
        )

    # The following overrides are optional. Remove them if you don't need them.

    @override
    def on_chat_start(self, helper: PluginHelper):
        """Called when chat starts - register all actions, projections, sideeffects, etc. here"""
        # Register actions
        # helper.register_action(...)

        # Register custom events
        # helper.register_event(...)

        # Register projections
        # helper.register_projection(...)

        # Register sideeffects
        # helper.register_sideeffect(...)

        # Register status generators
        # helper.register_status_generator(...)
        pass

    @override
    def on_chat_stop(self, helper: PluginHelper):
        """Called when chat stops - cleanup resources here"""
        pass
```

And a manifest file like this: (**The GUID must be unique. Generate a new one for your project**)

```json
{
  "guid": "babe1f36-bc38-4b62-8cda-80a7a68835f6",
  "name": "Hello World - Example Plugin",
  "version": "0.0.1",
  "author": "John Doe",
  "description": "A sample plugin",
  "entrypoint": "HelloWorld.py"
}
```

The `PluginBase` base class has the following methods that can be overridden:

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

The `PluginHelper` instance provides utilities for registering actions, projections, side effects, and more. You can access most of the internal features you need from the `helper` object, such as `send_key()`, various event handler registrations, and more.

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

- `helper.register_status_generator(status_generator: Callable[[dict[str, dict]], list[tuple[str, Any]]])`:  
   Register a status generator callback for adding information to the model's status context. The callable takes the current projected states and returns a list of (title, content) tuples.

### Input Simulation

- `helper.send_key(key_name: str, *args, **kwargs)`:  
   Send a key input to the game.

### Settings & Data

- `helper.get_plugin_setting(*key_paths: str) -> Any`:  
   Get a plugin setting using a series of keys forming a path.

- `helper.set_plugin_setting(*key_path: str, value: Any)`:  
   Set a plugin setting using a series of keys forming a path.

- `helper.get_plugin_data_path(plugin_manifest: PluginManifest) -> str`:  
   Get the absolute path to your plugin's data directory.

### A note on events

For events to work properly, you need to register your event classes in the constructor, like this:

```python
class HelloWorld(PluginBase):
    def __init__(self, plugin_manifest: PluginManifest):
        super().__init__(plugin_manifest, [MyValueChangedEvent]) # Provide a list of event classes here. This is used for deserializing stored events.
...
```

### Registering Custom Plugin Events

To handle custom plugin events, use the `helper.register_event()` method in `on_chat_start()`:

```python
def on_chat_start(self, helper: PluginHelper):
    helper.register_event(
        name="my_event",
        should_reply_check=lambda event: True,  # or your custom logic
        prompt_generator=lambda event: f"The new value is now {event.data['key']}"
    )
```

Then dispatch your custom event using:

```python
helper.dispatch_event(PluginEvent(
    plugin_event_name="my_event",
    data={"key": "value"}
))
```

**Note:** The `dispatch_event()` method validates that the event is of type `PluginEvent` and will raise a `ValueError` if it's not.

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
| `settings_config` | Settings are defined as a class property and registered right after all plugins have been loaded.                                                                                                                                      |
| `on_chat_start()` | This function is executed when the chat assistant is started.<br>**All registration should happen here:** register actions, projections, sideeffects, custom events, and status generators using the provided `PluginHelper` instance. |
| `on_chat_stop()`  | This function runs when the user stops the chat assistant. Use this for any cleanup between chat sessions.                                                                                                                             |
