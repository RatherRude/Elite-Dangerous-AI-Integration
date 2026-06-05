from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.lib.actions import actions_genui


class FakeGenUIManager:
    def generate(self, instruction: str | None, projected_states: dict, undo: bool = False):
        yield {"status": "generating", "instruction": instruction}
        yield {
            "status": "started",
            "instruction": instruction,
            "internal_tool_call_id": "internal_call_1",
            "internal_tool_name": "read",
        }
        return "UI updated successfully."


def consume_generator(generator):
    values = []
    while True:
        try:
            values.append(next(generator))
        except StopIteration as stop:
            return values, stop.value


def test_generate_ui_action_yields_processing_events(monkeypatch) -> None:
    monkeypatch.setattr(actions_genui, "_genui_manager", FakeGenUIManager())

    updates, final_result = consume_generator(actions_genui._generate_ui_action(
        {"instruction": "show cargo"},
        {},
    ))

    assert updates == [
        {"status": "generating", "instruction": "show cargo"},
        {
            "status": "started",
            "instruction": "show cargo",
            "internal_tool_call_id": "internal_call_1",
            "internal_tool_name": "read",
        },
    ]
    assert final_result == "UI updated successfully."
