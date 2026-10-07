from typing import Any, Iterator, Literal, NotRequired, TypeAlias, TypedDict

class SettingBase(TypedDict):
    key: str
    label: str | None
    type: Literal['paragraph', 'text', 'textarea', 'toggle', 'number', 'select', 'button', 'error']
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

class ButtonSetting(SettingBase):
    """Used to display a button that invokes the plugin's settings-button hook."""
    pass

class ParagraphSetting(SettingBase):
    """Used to display a paragraph of text. The label is used as the title."""
    content: str

class ErrorSetting(SettingBase):
    """Used to display an error message."""
    content: str

class SettingCondition(TypedDict):
    """Compare a key in the current namespace, or use default_show when unset."""
    key: str
    operator: Literal['eq', 'neq', 'gt', 'geq', 'lt', 'leq', 'in', 'not_in', 'contains', 'not_contains', 'is_set', 'is_unset']
    value: NotRequired[object]
    default_show: NotRequired[bool]

class ConditionSetting(TypedDict):
    """Show nested fields when the condition matches; hidden values are preserved."""
    key: str
    type: Literal['condition']
    condition: SettingCondition
    fields: list['SettingsElement']

SettingsField: TypeAlias = TextSetting | TextAreaSetting | SelectSetting | NumericalSetting | ToggleSetting | ButtonSetting | ParagraphSetting | ErrorSetting
SettingsElement: TypeAlias = SettingsField | ConditionSetting

class SettingsGrid(TypedDict):
    """Defines a grid of settings for a plugin."""
    key: str
    label: str
    fields: list[SettingsElement]

def settings_fields(elements: list[SettingsElement]) -> Iterator[SettingsField]:
    """Include hidden descendants when resolving defaults and persisted values."""
    for element in elements:
        if element['type'] == 'condition':
            yield from settings_fields(element['fields'])
        else:
            yield element


def resolve_voice_settings(
    grids: list[SettingsGrid], plugin_settings: dict[str, Any], character_settings: dict[str, Any],
) -> dict[str, Any]:
    """Merge voice defaults, plugin globals, and character overrides, in that order."""
    defaults = {
        field['key']: field['default_value']
        for grid in grids for field in settings_fields(grid['fields'])
        if 'default_value' in field
    }
    return {**defaults, **plugin_settings, **character_settings}

class PluginSettings(TypedDict):
    """Used to define the settings for a plugin."""
    key: str
    label: str
    icon: str
    grids: list[SettingsGrid]


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
    """Character voice settings use merged plugin globals with character values taking precedence.
    Use unique logical setting keys across the global and character schemas.
    """
