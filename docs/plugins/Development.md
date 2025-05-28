# Plugin development for COVAS:NEXT

Do you want to build a plugin, to expand on COVAS' features? This page will help you get started.

## Prerequisites

* **COVAS:NEXT Project**: Ensure you have the project running from source, as described in [CONTRIBUTING.md](./CONTRIBUTING.md).

# The easy way to get started
To quickly create a starting point, we suggest using [this cookiecutter template](http://github.com/MaverickMartyn/COVAS-NEXT-Plugin-Template). 
Use the template to create a project in a sub-folder of the `plugins` folder.

## Plugin structure
Plugins are loaded from sub-folders of `./plugins`, up to one level deep.  
Create a new sub-folder for your plugin, and create a new Python script and a `manifest.json` file. Both of these are described below. 
You can create a git repository, and even include other assets or libraries in this subfolder.

### Folder structure:
* `/plugins`
    * `/YourPlugin` <- Main folder for your plugin. Contains source code and assets.
        * `/manifest.json` <- The plugin manifest, which defines meta data and the entrypoint.
        * `/deps` <- Python dependencies.
        * `/YourPlugin.py` <- Contains at least one class implementing the `PluginBase` base class.
        * `/requirements.txt` <- Only used when packaging additional Python dependencies. Not needed when distributing.
        * `__init__.py` <- This is optional and empty, but required to use relative imports´(like `from .PackageName import ClassName`).
    * `/AnotherPlugin`
* `plugin_data` <- For user data. These folders are created at runtime and are not part of your plugin source code.
    * `5b68272b-9949-4cad-b7c4-14da97a7f1c2` <- Plugin guid from metadata. This is your plugins data folder, which is used for persistent user data.
        * `YourPluginData.db` <- This means all data in this folder persists when updating and replacing the plugin.
    * `fc8a17ce-91ba-4dc7-819e-e65b02326244` <- Use `helper.get_plugin_data_path()` to get the path to your plugins dedicated data folder.

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

    # Register actions
    @override
    def register_actions(self, helper: PluginHelper):
        pass
    
    # Register projections
    @override
    def register_projections(self, helper: PluginHelper):
        pass

    # Register sideeffects
    @override
    def register_sideeffects(self, helper: PluginHelper):
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

The `PluginBase` base class has several functions that can be overridden to extend plugin functionality:

- `register_actions(self, helper: PluginHelper)`:  
    Override this method to register all tool actions for your plugin. Actions are commands or operations for the AI to execute at will. This method is called by the `PluginManager` after all plugins have been loaded and the assistant has started.

- `register_projections(self, helper: PluginHelper)`:  
    Use this method to register projections. Projections are used to store state information, which is updated in response to events, and potentially exposed to the assistant.

- `register_sideeffects(self, helper: PluginHelper)`:  
    Override to register side effects. Side effects are executed when any events occur, and are provided the projected state.

- `register_prompt_event_handlers(self, helper: PluginHelper)`:  
    Use this to register handlers that add to the prompt for the assistant based on events. These handlers help the assistant respond contextually to different situations. This adds to the token count.

- `register_status_generators(self, helper: PluginHelper)`:  
    Register status generators to add status information to the assistant's prompt. This can be used to add information to prompt/context, such as persistent memory. Keep in mind that this adds to the token count.

- `register_should_reply_handlers(self, helper: PluginHelper)`:  
    Override to register handlers that determine whether the assistant should reply to a given event. Return `True` to force a reply, `False` to suppress it, or `None` to leave the decision to the assistant.

- `on_plugin_helper_ready(self, helper: PluginHelper)`:  
    Called when the chat is started and the `PluginHelper` is ready. Use this for any additional setup that requires access to the helper or other managers.

- `on_chat_stop(self, helper: PluginHelper)`:  
    Called when the chat is stopped. Use this to perform any cleanup or finalization needed by your plugin.

Each of these methods receives a `PluginHelper` instance, which provides utilities for registering actions, projections, side effects, and more. Override only the methods relevant to your plugin's functionality.
The registration functions (`register_actions`, `register_projections` and `register_sideeffects`, etc.) are where most of the magic happens.  
You can access most of the internal features you need from the `helper` object, such as the `send_key()`, various event handler registrations and more.

### A note on events
For events to work properly, you need to register your event classes in the constructor, like this:
```python
class HelloWorld(PluginBase):
    def __init__(self, plugin_manifest: PluginManifest):
        super().__init__(plugin_manifest, [MyValueChangedEvent]) # Provide a list of event classes here. This is used for deserializing stored events.
...
```

For further details, see the [HelloWorld example plugin](./plugins/HelloWorld) for more examples, or [Join our Discord](https://discord.gg/9c58jxVuAT).

## Python Dependencies
If your plugin needs additional 3rd party Python modules, then you need to package them along with your plugin.  
I suggest creating a `requirements.txt` for your plugin, and using `pip install -r requirements.txt --target=./deps` to install the packages to the `deps` subfolder.  
Only modules already used in COVAS:NEXT, and those placed inside the `deps` subfolder will be made available.  
**The `deps` sub-folder should be included when you distribute your plugin.**

## Plugin Lifecycle
Below is a list of plugin functions and when they are called.  
Initialization is best done either in the cosntructor for stuff that should persist between chat sessions, and in the `on_plugin_helper_ready()` function for other stuff.  
Remember to clean up references etc. in `on_chat_stop()`.

| Function                                                                                                                                                                                   | Execution time                                                                                                                           |
|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------|
| `__init__`                                                                                                                                                                                 | The constructor is executed imediately upon loading the entrypoint file.                                                                 |
| `register_settings()`                                                                                                                                                                      | Settings are registered right after all plugins have been loaded.                                                                        |
| `register_actions()`<br>`register_projections()`<br>`register_sideeffects()`<br>`register_should_reply_handlers()`<br>`register_prompt_event_handlers()`<br>`register_status_generators()` | These functions are executed once the chat assistant is started.<br>The order in which these functions are called can not be guaranteed. |
| `on_plugin_helper_ready()`                                                                                                                                                                 | This function is executed as soon as the `PluginHelper` is ready, making it ideal for initialitation which requires the it.            |
| `on_chat_stop()`                                                                                                                                                                           | This function runs once the user stops the chat assistant. Use this for any cleanup between chat sessions.                               |