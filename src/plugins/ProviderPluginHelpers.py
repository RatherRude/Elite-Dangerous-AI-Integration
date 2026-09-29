from typing import Any, List, Optional

from lib.Logger import ModelUsageStats
from lib.Models import OpenAILLMModel


def text_field(
    key: str,
    label: str,
    default_value: str,
    *,
    hidden: bool = False,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "type": "text",
        "readonly": False,
        "placeholder": None,
        "default_value": default_value,
        "max_length": None,
        "min_length": None,
        "hidden": hidden,
    }


def textarea_field(key: str, label: str, default_value: str, rows: int = 4) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "type": "textarea",
        "readonly": False,
        "placeholder": None,
        "default_value": default_value,
        "rows": rows,
        "cols": None,
    }


def number_field(
    key: str,
    label: str,
    default_value: float,
    minimum: float,
    maximum: float,
    step: float,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "type": "number",
        "readonly": False,
        "placeholder": None,
        "default_value": default_value,
        "min_value": minimum,
        "max_value": maximum,
        "step": step,
    }


def toggle_field(key: str, label: str, default_value: bool) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "type": "toggle",
        "readonly": False,
        "placeholder": None,
        "default_value": default_value,
    }


def select_field(
    key: str,
    label: str,
    default_value: str,
    options: list[str],
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "type": "select",
        "readonly": False,
        "placeholder": None,
        "default_value": default_value,
        "select_options": [
            {"key": option, "label": option.replace("_", " ").title(), "value": option, "disabled": False}
            for option in options
        ],
        "multi_select": False,
    }


def paragraph(content: str) -> dict[str, Any]:
    return {
        "key": "info",
        "label": None,
        "type": "paragraph",
        "readonly": True,
        "placeholder": None,
        "content": content,
    }


def api_key(settings: dict[str, Any], prefix: str, shared_key: str = "api_key") -> str:
    return str(settings.get(f"{prefix}_api_key") or settings.get(shared_key) or "-")


def string_setting(settings: dict[str, Any], key: str, default: str) -> str:
    return str(settings.get(key) or default)


def float_setting(settings: dict[str, Any], key: str, default: float) -> float:
    try:
        value = settings.get(key, default)
        return default if value is None or value == "" else float(value)
    except (TypeError, ValueError):
        return default


def bool_setting(settings: dict[str, Any], key: str, default: bool) -> bool:
    value = settings.get(key, default)
    return value if isinstance(value, bool) else default


class ToolToggleOpenAILLMModel(OpenAILLMModel):
    def __init__(self, *args: Any, tools_enabled: bool = True, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.tools_enabled = tools_enabled

    def generate(
        self,
        messages: List[dict],
        tools: Optional[List[dict]] = None,
        tool_choice: Optional[Any] = None,
    ) -> tuple[str | None, List[Any] | None, ModelUsageStats]:
        return super().generate(
            messages,
            tools if self.tools_enabled else None,
            tool_choice if self.tools_enabled else None,
        )
