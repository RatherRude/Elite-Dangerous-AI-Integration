import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from lib.PluginBase import PluginBase, PluginManifest
from lib.PluginManager import PluginManager


class _SettingsPlugin(PluginBase):
    def __init__(self, manifest: PluginManifest):
        super().__init__(manifest)
        self.hook_calls = 0
        self.settings_config = {
            "key": manifest.guid,
            "label": "Test",
            "grids": [
                {
                    "key": "status",
                    "fields": [
                        {
                            "key": "status",
                            "type": "paragraph",
                            "content": "initial",
                        }
                    ],
                }
            ],
        }

    def on_settings_changed(self) -> None:
        self.hook_calls += 1


def _manager() -> tuple[PluginManager, _SettingsPlugin]:
    manifest = PluginManifest(
        '{"guid":"settings-test-guid","name":"Settings Test","version":"1.0.0"}'
    )
    plugin = _SettingsPlugin(manifest)
    manager = PluginManager({"plugin_settings": {}})
    manager.plugin_list[manifest.guid] = plugin
    manager.register_settings()
    return manager, plugin


def test_update_plugin_setting_persists_updates_ui_and_calls_hook(monkeypatch):
    manager, plugin = _manager()
    emitted: list[tuple[str, dict]] = []
    saved: list[dict] = []
    monkeypatch.setattr(
        "lib.PluginManager.emit_message",
        lambda event, **payload: emitted.append((event, payload)),
    )
    monkeypatch.setattr(
        "lib.PluginManager.save_config",
        lambda config: saved.append(config),
    )

    assert manager.update_plugin_setting(plugin.plugin_manifest.guid, "status", "ready")

    assert manager.config["plugin_settings"][plugin.plugin_manifest.guid]["status"] == "ready"
    assert plugin.settings["status"] == "ready"
    assert plugin.hook_calls == 1
    assert saved == [manager.config]
    assert manager.plugin_settings_configs[plugin.plugin_manifest.guid]["grids"][0]["fields"][0]["content"] == "ready"
    assert {event for event, _payload in emitted} == {"config", "plugin_ui", "plugin_settings_configs", "plugin_model_providers"}


def test_update_plugin_setting_rejects_unknown_plugin():
    manager, _plugin = _manager()

    assert not manager.update_plugin_setting("missing-guid", "status", "ignored")
    assert manager.config["plugin_settings"] == {}


def test_settings_button_refreshes_plugin_paragraph_values(monkeypatch):
    manager, plugin = _manager()
    emitted: list[str] = []
    monkeypatch.setattr(
        "lib.PluginManager.emit_message",
        lambda event, **_payload: emitted.append(event),
    )

    def click(_key: str, _value: str | None = None) -> None:
        plugin.settings["status"] = "clicked"

    plugin.on_settings_button = click
    manager.on_settings_button(plugin.plugin_manifest.guid, "refresh")

    assert (
        manager.plugin_settings_configs[plugin.plugin_manifest.guid]["grids"][0]["fields"][0]["content"]
        == "clicked"
    )
    assert emitted == ["plugin_ui", "plugin_settings_configs", "plugin_model_providers"]


@pytest.mark.parametrize('placement', ['fields', 'content'])
@pytest.mark.parametrize('container_type', ['condition', 'section', 'summary', 'details'])
def test_legacy_status_refresh_reaches_shared_containers(monkeypatch, placement, container_type):
    manager, plugin = _manager()
    monkeypatch.setattr("lib.PluginManager.emit_message", lambda *_args, **_payload: None)
    monkeypatch.setattr("lib.PluginManager.save_config", lambda _config: None)
    grid = plugin.settings_config['grids'][0]
    status = grid['fields'][0]
    if container_type == 'condition':
        container = {
            'key': 'hidden', 'type': 'condition',
            'condition': {'key': 'enabled', 'operator': 'eq', 'value': True},
            'fields': [status],
        }
    elif container_type == 'section':
        container = {'type': 'section', 'children': [status]}
    else:
        container = {'type': 'list', 'items': [{'key': 'row', 'title': 'Row', container_type: [status]}]}
    grid['fields'] = []
    grid[placement] = [container]

    assert manager.update_plugin_setting(plugin.plugin_manifest.guid, 'status', 'ready')
    assert status['content'] == 'ready'

    def click(_key):
        plugin.settings['status'] = 'clicked'

    plugin.on_settings_button = click
    manager.on_settings_button(plugin.plugin_manifest.guid, 'refresh')
    assert status['content'] == 'clicked'
