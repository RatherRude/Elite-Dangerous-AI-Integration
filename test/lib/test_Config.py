import ast
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.lib.Config import (
    default_allowed_actions,
)


def test_action_defaults_match_registered_permissions() -> None:
    actions_source = (
        ROOT_DIR / "src" / "lib" / "actions" / "Actions.py"
    ).read_text(encoding="utf-8")
    registered_permissions = {
        keyword.value.value
        for node in ast.walk(ast.parse(actions_source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "registerAction"
        for keyword in node.keywords
        if keyword.arg == "permission"
        and isinstance(keyword.value, ast.Constant)
        and isinstance(keyword.value.value, str)
    }

    assert set(default_allowed_actions) == registered_permissions
