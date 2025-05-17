from typing import Literal, TypedDict

class SettingBase(TypedDict):
    key: str
    label: str | None
    type: Literal['paragraph', 'text', 'textarea', 'toggle', 'number', 'select']
    readonly: bool
    placeholder: str | None


class SelectOption(TypedDict):
    """Defines an option for a select setting."""
    key: str
    label: str
    value: object | str | int | float | bool
    disabled: bool

class SelectSetting(SettingBase):
    """Used to display a select input."""
    default_value: str | list[str] | None
    select_options: list[SelectOption] | None
    multi_select: bool

class TextSetting(SettingBase):
    """Used to display a text input."""
    default_value: str | None
    max_length: int | None
    min_length: int | None
    hidden: bool

class TextAreaSetting(SettingBase):
    """Used to display a textarea."""
    default_value: str | None
    rows: int | float | None
    cols: int | float | None

class NumericalSetting(SettingBase):
    """Used to display a numerical input."""
    default_value: int | float | None
    min_value: int | float | None
    max_value: int | float | None
    step: int | float | None

class ToggleSetting(SettingBase):
    """Used to display a toggle switch."""
    default_value: bool | None

class ParagraphSetting(SettingBase):
    """Used to display a paragraph of text. The label is used as the title."""
    content: str

class SettingsGrid(TypedDict):
    """Defines a grid of settings for a plugin."""
    key: str
    label: str
    fields: list[TextSetting | TextAreaSetting | SelectSetting | NumericalSetting | ToggleSetting | ParagraphSetting]

class PluginSettings(TypedDict):
    """Used to define the settings for a plugin."""
    key: str
    label: str
    icon: str
    grids: list[SettingsGrid]