# Plugin development for COVAS:NEXT

Wanna build a plugin, to expand on COVAS' features? This page will help you get started.

## Prerequisites

* **COVAS:NEXT Project**: Ensure you have the project running from source, as described in [CONTRIBUTING.md](./CONTRIBUTING.md).

## Plugin structure
Plugins are loaded from `./plugins` and its sub-folders, up to one level deep.  
Create a new sub-folder for your plugin, and create a new Python script. Any class inheriting from `PluginBase` will be treated as a plugin.  
You can create a git repository, and even include other assets or libraries in this subfolder.

### Folder structure:
* `/plugins`
    * `/YourPlugin`
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
    def __init__(self): # This is the name that will be shown in the UI.
        super().__init__(plugin_name = "Example Plugin")

        # Define the plugin settings
        # This is the settings that will be shown in the UI for this plugin.
        self.settings_config = PluginSettings(
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

The registration functions (`register_actions`, `register_projections` and `register_sideeffects`, etc.) are where most of the magic happens.  
You can access most of the internal features you need from the `helper` object, such as the `send_key()`, various event handler registrations and more.

For further details, see [HelloWorld.py](./plugins/HelloWorld.py) for more examples, or [Join our Discord](https://discord.gg/9c58jxVuAT).

## Python Dependencies
If your plugin needs additional 3rd party Python modules, then you need to package them along with your plugin.  
I suggest creating a `requirements.txt` for your plugin, and using `pip install -r requirements.txt --target=./deps` to install the packages to the `deps` subfolder.  
Only modules already used in COVAS:NEXT, and those placed inside the `deps` subfolder will be made available.  
**The `deps` sub-folder should be included when you distribute your plugin.**

## Plugin Lifecycle
The lifecycle of plugins will be described here soon<sup>tm</sup>.
