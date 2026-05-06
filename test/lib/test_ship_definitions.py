import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def test_lynx_highliner_has_medium_pad_size():
    ship_sizes = json.loads((ROOT / "src" / "assets" / "ship_sizes.json").read_text())

    assert ship_sizes["mediumtransport01"] == "M"


def test_lynx_highliner_is_known_ship_name():
    from lib.actions.data import known_ships

    assert "Lynx Highliner" in known_ships
    assert "Panther Clipper MkII" in known_ships
    assert "Python" in known_ships
