# Plugin development for COVAS:NEXT

Wanna build a plugin, to expand on COVAS' features? This page will help you get started.

## Prerequisites

* **COVAS:NEXT Project**: Ensure you have the project running from source, as described in [CONTRIBUTING.md](./CONTRIBUTING.md).

## Plugin structure
Plugins are loaded from sub-folders of `./plugins`, up to one level deep.  
Create a new sub-folder for your plugin, and create a new Python script and a `manifest.json` file. Both of these are described below. 
You can create a git repository, and even include other assets or libraries in this subfolder.

### Folder structure:
* `/plugins`
    * `/YourPlugin`
        * `/manifest.json` <- The plugin manifest, which defines meta data and the entrypoint.
        * `/deps` <- Python dependencies.
        * `/YourPlugin.py` <- Contains class inplementing `PluginBase` base class.
        * `/requirements.txt` <- Only used when packaging additional Python dependencies. Not needed when distributing.
    * `/AnotherPlugin`

Create a new class implementing `PluginBase` like this:  
**All members have to be overriden in your implementation, even if you don't need them, and even if they're not listed here. Just use `pass` as a placeholder.**  
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

The registration functions (`register_actions`, `register_projections` and `register_sideeffects`, etc.) are where most of the magic happens.  
You can access most of the internal features you need from the `helper` object, such as the `send_key()`, various event handler registrations and more.

For further details, see the [HelloWorld example plugin](./plugins/HelloWorld) for more examples, or [Join our Discord](https://discord.gg/9c58jxVuAT).

## Python Dependencies
If your plugin needs additional 3rd party Python modules, then you need to package them along with your plugin.  
I suggest creating a `requirements.txt` for your plugin, and using `pip install -r requirements.txt --target=./deps` to install the packages to the `deps` subfolder.  
Only modules already used in COVAS:NEXT, and those placed inside the `deps` subfolder will be made available.  
**The `deps` sub-folder should be included when you distribute your plugin.**

## Plugin Lifecycle
Below is a list of plugin functions and when they are called.

| Function                                                                                                                                                                                   | Execution time                                                                                                                           |
|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------|
| `__init__`                                                                                                                                                                                 | The constructor is executed imediately upon loading the entrypoint file.                                                                 |
| `register_settings()`                                                                                                                                                                      | Settings are registered right after all plugins have been loaded.                                                                        |
| `register_actions()`<br>`register_projections()`<br>`register_sideeffects()`<br>`register_should_reply_handlers()`<br>`register_prompt_event_handlers()`<br>`register_status_generators()` | These functions are executed once the chat assistant is started.<br>The order in which these functions are called can not be guaranteed. |
| `on_chat_stop()`                                                                                                                                                                           | This function runs once the user stops the chat assistant. Use this for any cleanup between chat sessions.                               |
