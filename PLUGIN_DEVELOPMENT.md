# Plugin development for CORVAS:NEXT

Wanna build a plugin, to expand on CORVAS' features? This page will help you get started.

## Prerequisites

*   **CORVAS:NEXT Project**: Ensure you have the project running from source, as described in [CONTRIBUTING.md](./CONTRIBUTING.md).

## Plugin structure
Plugins are loaded from `./plugins` and its sub-folders, up to one level deep.  
Create a new sub-folder for your plugin, and create a new Python script. Any class inheriting from `PluginBase` will be treated as a plugin.  
You can create a git repository, and even include other assets or libraries in this subfolder.

Create a new class implementing `PluginBase` like this:  
```python
# Main plugin class
# This is the class that will be loaded by the PluginManager.
class ExamplePlugin(PluginBase):

    # Plugin name
    plugin_name: str
    # Define the settings for this plugin. This is the settings that will be shown in the UI.
    settings_config: PluginSettings | None
    
    def __init__(self, plugin_name: str = "Example Plugin"): # This is the name that will be shown in the UI.
        super().__init__(plugin_name)

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
    def register_actions(self, deps: PluginDependencies):
        pass
    
    # Register projections
    @override
    def register_projections(self, deps: PluginDependencies):
        pass

    # Register sideeffects
    @override
    def register_sideeffects(self, deps: PluginDependencies):
        pass
```

The registration functions (`register_actions`, `register_projections` and `register_sideeffects`) are where most of the magic happens.  
You can access most of the services you need from the `deps` object, such as the `EventManager`, `ActionManager`, `Config` and more.

For further details, see [HelloWorld.py](./plugins/HelloWorld.py) for more examples, or [Join our Discord](https://discord.gg/9c58jxVuAT).