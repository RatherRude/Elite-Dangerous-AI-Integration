from typing import Literal, NotRequired, TypedDict
from .PluginUIDefinitions import (
    UIComponent, UINode, InputBase, SelectOption, Select, TextInput, Filter,
    TextArea, NumberInput, Toggle, Button, Paragraph, Error, List, ListAction, ListRow,
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
ErrorSetting = Error
ListSetting = List
FilterSetting = Filter

class GridHeaderAction(TypedDict):
    """Defines an action button rendered next to a grid header."""
    key: str
    icon: NotRequired[str]
    label: NotRequired[str]

SettingField = UIComponent


class SettingsGrid(TypedDict):
    """Defines a grid of settings for a plugin."""
    key: str
    label: str
    fields: list[SettingField]
    content: NotRequired[list[UIComponent]]
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
