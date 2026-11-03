from typing import Any, Literal, NotRequired, TypedDict
from .PluginUIDefinitions import (
    UIComponent, UINode, InputBase, SelectOption, Select, TextInput, Filter,
    TextArea, NumberInput, Toggle, Button, Paragraph, Notification, Error, List, ListAction, ListRow,
    UICondition, Condition, UIGrid, GridHeaderAction, ui_fields,
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
SettingField = UIComponent
SettingsField = UIComponent
SettingsElement = UIComponent
SettingCondition = UICondition
ConditionSetting = Condition
SettingsGrid = UIGrid
settings_fields = ui_fields

class SettingsHeaderLink(TypedDict):
    text: str
    label: str
    url: str

def resolve_voice_settings(
    grids: list[SettingsGrid], plugin_settings: dict[str, Any], character_settings: dict[str, Any],
) -> dict[str, Any]:
    """Merge voice defaults, plugin globals, and character overrides, in that order."""
    defaults = {
        field['key']: field['default_value']
        for grid in grids for field in ui_fields(grid['fields'] + grid.get('content', []))
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
