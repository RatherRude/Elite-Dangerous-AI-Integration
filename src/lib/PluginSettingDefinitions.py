from typing import Literal, NotRequired, TypedDict
from .PluginUIDefinitions import UINode

class SettingBase(TypedDict):
    key: str
    label: str | None
    type: Literal['paragraph', 'text', 'textarea', 'toggle', 'number', 'select', 'button', 'list', 'filter', 'error']
    readonly: bool
    placeholder: str | None
    params: NotRequired[dict[str, str | int | float]]


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

class FilterSetting(SettingBase):
    """Used to display a compact live-filter input."""
    default_value: NotRequired[str | None]
    max_length: NotRequired[int | None]
    min_length: NotRequired[int | None]
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

class ButtonSetting(SettingBase):
    """Used to display a button that invokes the plugin's settings-button hook."""
    icon: NotRequired[str]

class ParagraphSetting(SettingBase):
    """Used to display a paragraph of text. The label is used as the title."""
    content: str

class ErrorSetting(SettingBase):
    """Used to display an error message."""
    content: str

class ListAction(TypedDict):
    """Defines an action button rendered on every row of a list field.

    Clicking it invokes the plugin's settings-button hook with the key
    ``<action>:<row key>``. With ``inline_edit`` the row title becomes an
    editable input and the edited value is passed as the hook value.
    """
    action: str
    icon: NotRequired[str]
    label: NotRequired[str]
    danger: NotRequired[bool]
    inline_edit: NotRequired[bool]

class ListRow(TypedDict):
    """Defines one row of a list field. Rows sharing the same group value are
    rendered under a common group header."""
    key: str
    title: str
    title_key: NotRequired[str]
    suffix: NotRequired[str]
    meta: NotRequired[str]
    params: NotRequired[dict[str, str | int | float]]
    group: NotRequired[str]
    pending: NotRequired[bool]
    tone: NotRequired[str]
    details: NotRequired[list[UINode]]

class ListSetting(SettingBase):
    """Used to display a list of rows, each carrying optional actions."""
    items: list[ListRow]
    row_actions: NotRequired[list[ListAction]]
    count_labels: NotRequired[dict[str, str]]

class GridHeaderAction(TypedDict):
    """Defines an action button rendered next to a grid header."""
    key: str
    icon: NotRequired[str]
    label: NotRequired[str]

SettingField = TextSetting | TextAreaSetting | SelectSetting | NumericalSetting | ToggleSetting | ButtonSetting | ParagraphSetting | ErrorSetting | ListSetting | FilterSetting


class SettingsGrid(TypedDict):
    """Defines a grid of settings for a plugin."""
    key: str
    label: str
    fields: list[SettingField]
    content: NotRequired[list[UINode]]
    collapsible: NotRequired[bool]
    default_collapsed: NotRequired[bool]
    header_action: NotRequired[GridHeaderAction]

class SettingsHeaderLink(TypedDict):
    text: str
    label: str
    url: str


class PluginSettings(TypedDict):
    """Used to define the settings for a plugin."""
    key: str
    label: str
    icon: str
    grids: list[SettingsGrid]
    tabs: NotRequired[list['SettingsTab']]
    header_link: NotRequired[SettingsHeaderLink]


class SettingsTab(TypedDict):
    key: str
    label: str
    grids: list[str]


class ApiKeyDetection(TypedDict, total=False):
    """Optional API-key format detection and recommended provider selections."""
    patterns: list[str]
    priority: int
    setting_key: str
    provider_selections: dict[str, str]


class ModelProviderDefinition(TypedDict):
    """
    Defines a model provider that a plugin can contribute.
    
    Plugins can provide LLM, VLM, STT, TTS, or Embedding model implementations
    that appear in the Advanced Settings provider dropdowns.
    """
    kind: Literal['llm', 'vlm', 'stt', 'tts', 'embedding']
    """The type of model this provider creates."""
    
    id: str
    """Unique identifier for this provider within the plugin."""
    
    label: str
    """Human-readable name shown in the UI dropdown."""
    
    settings_config: list[SettingsGrid]
    """
    Settings fields specific to this provider, rendered inline in Advanced Settings
    when this provider is selected. Values are stored in the plugin's settings namespace.
    """

    slots: NotRequired[list[Literal['llm', 'agent_llm', 'vision', 'stt', 'tts', 'embedding']]]
    """Application slots where this provider is available. Omitted preserves kind-based behavior."""

    api_key_detection: NotRequired[ApiKeyDetection]
    """Optional API-key detection metadata used by the settings UI."""

    voice_settings_config: NotRequired[list[SettingsGrid]]
    """Optional character-scoped voice settings for TTS providers."""
