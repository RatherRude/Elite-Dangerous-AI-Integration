from typing import Any, Iterator, Literal, NotRequired, TypeAlias, TypedDict
from .PluginUIDefinitions import (
    UIComponent, UINode, InputBase, SelectOption, Select, TextInput, Filter,
    TextArea, NumberInput, Toggle, Button, Paragraph, Notification, Error, List, ListAction, ListRow,
)

# Deprecated compatibility aliases; use PluginUIDefinitions for new components.
SettingBase = InputBase
SelectSetting = Select
TextSetting = TextInput
TextAreaSetting = TextArea
NumericalSetting = NumberInput
ToggleSetting = Toggle
ButtonSetting = Button
ParagraphSetting = Paragraph
NotificationSetting = Notification
ErrorSetting = Error
ListSetting = List
FilterSetting = Filter

class GridHeaderAction(TypedDict):
    """Defines an action button rendered next to a grid header."""
    key: str
    icon: NotRequired[str]
    label: NotRequired[str]

SettingField = UIComponent

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

SettingsField: TypeAlias = UIComponent
SettingsElement: TypeAlias = SettingsField | ConditionSetting

class SettingsGrid(TypedDict):
    """Defines a grid of settings for a plugin."""
    key: str
    label: str
    fields: list[SettingsElement]
    content: NotRequired[list[UIComponent]]
    collapsible: NotRequired[bool]
    default_collapsed: NotRequired[bool]
    header_action: NotRequired[GridHeaderAction]

class SettingsHeaderLink(TypedDict):
    text: str
    label: str
    url: str

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
    return {
        **defaults,
        **{key: value for key, value in plugin_settings.items() if value is not None},
        **{key: value for key, value in character_settings.items() if value is not None},
    }

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
    """Character voice settings use merged plugin globals with character values taking precedence.
    Use unique logical setting keys across the global and character schemas.
    """
