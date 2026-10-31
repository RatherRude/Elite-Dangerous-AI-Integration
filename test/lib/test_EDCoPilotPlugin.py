from pathlib import Path
import sys
from unittest.mock import MagicMock

import pytest
from openai.types.chat import ChatCompletionMessageFunctionToolCall

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from lib.ActionManager import ActionManager
from lib.PluginHelper import PluginHelper
from plugins.EDCoPilotPlugin import EDCoPilotPlugin


@pytest.mark.parametrize("settings", [
    {},
    {"enabled": True},
    {"enabled": True, "actions": False},
    {"enabled": False, "actions": True},
])
def test_disabled_edcopilot_actions_are_not_offered_or_executed(settings):
    plugin = EDCoPilotPlugin.__new__(EDCoPilotPlugin)
    plugin.settings = {"enabled": True, "actions": True}
    plugin.edcopilot_open_panel = MagicMock(return_value="opened")
    manager = ActionManager()
    helper = PluginHelper.__new__(PluginHelper)
    helper._action_manager = manager
    plugin._register_actions(helper)
    assert len(manager.getToolsList("mainship", True, True, True)) == 2

    # PluginManager replaces settings dictionaries when the UI updates them.
    plugin.settings = settings

    assert manager.getToolsList("mainship", True, True, True) == []
    result = manager.runAction(ChatCompletionMessageFunctionToolCall(
        id="call_test", type="function",
        function={"name": "edcopilot_open_panel", "arguments": '{"panelName":"aboutedcopilot"}'},
    ), {})
    assert "disabled" in result["content"]
    plugin.edcopilot_open_panel.assert_not_called()

    plugin.settings = {"enabled": True, "actions": True}
    assert len(manager.getToolsList("mainship", True, True, True)) == 2
