from typing import Literal, TypedDict

class SettingBase(TypedDict):
    key: str
    label: str | None
    type: Literal['paragraph', 'text', 'textarea', 'toggle', 'number', 'select']
    readonly: bool
    placeholder: str | None


class SelectOption(TypedDict):
    key: str
    label: str
    value: object | str | int | float | bool
    disabled: bool

class SelectSetting(SettingBase):
    default_value: str | list[str] | None
    select_options: list[SelectOption] | None
    multi_select: bool

class TextSetting(SettingBase):
    default_value: str | None
    max_length: int | None
    min_length: int | None
    hidden: bool

class TextAreaSetting(SettingBase):
    default_value: str | None
    rows: int | float | None
    cols: int | float | None

class NumericalSetting(SettingBase):
    default_value: int | float | None
    min_value: int | float | None
    max_value: int | float | None
    step: int | float | None

class ToggleSetting(SettingBase):
    default_value: bool | None

class ParagraphSetting(SettingBase):
    content: str

class SettingsGrid(TypedDict):
    key: str
    label: str
    fields: list[TextSetting | TextAreaSetting | SelectSetting | NumericalSetting | ToggleSetting | ParagraphSetting]

class PluginSettings(TypedDict):
    key: str
    label: str
    icon: str
    grids: list[SettingsGrid]