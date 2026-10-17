import json
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from lib.PluginBase import PluginBase, PluginManifest
from lib.PluginHelper import PluginHelper
from lib.PluginManager import PluginManager


class DetectorPlugin(PluginBase):
    def __init__(self, guid: str) -> None:
        super().__init__(PluginManifest(json.dumps({"guid": guid, "name": "Test detector"})))
        self.detector = Mock(return_value="fr")
        self.fail_start = False
        self.fail_stop = False

    def on_chat_start(self, helper: PluginHelper) -> None:
        helper.register_language_detector(self.detector)
        if self.fail_start:
            raise RuntimeError("Startup failed")

    def on_chat_stop(self, helper: PluginHelper) -> None:
        if self.fail_stop:
            raise RuntimeError("Shutdown failed")


@pytest.fixture
def runtime(monkeypatch):
    manager = PluginManager({"plugin_settings": {}})
    plugin = DetectorPlugin("first")
    manager.plugin_list["first"] = manager._initialize_plugin_settings(plugin)
    helper = PluginHelper(manager, Mock(), {}, Mock(), Mock(), Mock(), None, Mock(), Mock(), Mock())
    monkeypatch.setattr(manager, "publish_plugin_ui", Mock())
    monkeypatch.setattr(manager, "publish_plugin_settings", Mock())
    return manager, plugin, helper


def test_no_plugin_is_a_supported_configuration(runtime):
    manager, _, _ = runtime
    assert not manager.has_language_detector
    assert manager.detect_language("accepted voice input") is None


def test_detector_is_registered_for_each_run_and_cleared_on_stop(runtime):
    manager, plugin, helper = runtime
    manager.on_chat_start(helper)
    assert manager.has_language_detector
    assert manager.detect_language("Bonjour") == "fr"
    plugin.detector.assert_called_once_with("Bonjour")
    manager.on_chat_stop(helper)
    assert not manager.has_language_detector
    assert manager.detect_language("Bonjour") is None
    manager.on_chat_start(helper)
    assert manager.detect_language("Bonjour") == "fr"


def test_failed_plugin_start_cannot_leave_a_detector_registered(runtime):
    manager, plugin, helper = runtime
    plugin.fail_start = True
    manager.on_chat_start(helper)
    assert not manager.has_language_detector


def test_failed_plugin_stop_still_clears_detector(runtime):
    manager, plugin, helper = runtime
    manager.on_chat_start(helper)
    plugin.fail_stop = True
    manager.on_chat_stop(helper)
    assert not manager.has_language_detector


def test_unbound_helper_and_unregistered_owners_are_rejected(runtime):
    manager, _, helper = runtime
    with pytest.raises(RuntimeError, match="bound"):
        helper.register_language_detector(lambda _: "fr")
    with pytest.raises(ValueError, match="registered"):
        manager.register_language_detector("unknown", lambda _: "fr")


def test_registration_is_owned_and_competing_plugins_cannot_replace_it(runtime):
    manager, plugin, helper = runtime
    other = DetectorPlugin("second")
    namespace = manager._register_plugin(other)
    bound = helper._for_plugin(namespace)
    manager.on_chat_start(helper)
    with pytest.raises(ValueError, match="owner"):
        bound._plugin_manager.register_language_detector("first", lambda _: "en")
    with pytest.raises(ValueError, match="one language detector"):
        bound.register_language_detector(lambda _: "en")
    assert manager.detect_language("Bonjour") == "fr"
    plugin.detector.assert_called_once()


def test_detector_must_be_callable(runtime):
    manager, _, _ = runtime
    with pytest.raises(ValueError, match="callable"):
        manager.register_language_detector("first", None)


@pytest.mark.parametrize("value", ["FR", "fra", "French", "fr-FR", "", 123, False, {}])
def test_invalid_plugin_results_are_explicit_errors(runtime, value):
    manager, plugin, helper = runtime
    plugin.detector.return_value = value
    manager.on_chat_start(helper)
    with pytest.raises(ValueError, match="two-letter language code or None"):
        manager.detect_language("accepted voice input")


def test_ambiguous_detection_is_not_an_error(runtime):
    manager, plugin, helper = runtime
    plugin.detector.return_value = None
    manager.on_chat_start(helper)
    assert manager.detect_language("Sol") is None


def test_detector_errors_are_not_silently_converted_to_success(runtime):
    manager, plugin, helper = runtime
    plugin.detector.side_effect = RuntimeError("Detector unavailable")
    manager.on_chat_start(helper)
    with pytest.raises(RuntimeError, match="Detector unavailable"):
        manager.detect_language("accepted voice input")
