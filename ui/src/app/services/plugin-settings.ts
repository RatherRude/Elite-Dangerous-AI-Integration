import { type BaseMessage } from "./tauri.service";
import { UIComponent, uiFields } from "./plugin-ui";
export type { SelectOption, ListRow, ListAction, GridHeaderAction,
    UIGrid as SettingsGrid, UICondition as SettingCondition, Condition as ConditionSetting } from "./plugin-ui";
import type { UIGrid as SettingsGrid } from "./plugin-ui";
export { uiFields as settingsFields, matchesUICondition as matchesSettingCondition } from "./plugin-ui";

export interface SettingsHeaderLink {
    text: string;
    label: string;
    url: string;
}

export interface PluginSettings {
    key: string;
    label: string;
    icon: string;
    grids: SettingsGrid[];
    tabs?: {key: string; label: string; grids: string[]}[];
    header_link?: SettingsHeaderLink;
}

// Deprecated names retained for existing consumers.
export type SettingBase = UIComponent;
export type TextSetting = UIComponent;
export type FilterSetting = UIComponent;
export type TextAreaSetting = UIComponent;
export type NumericalSetting = UIComponent;
export type ToggleSetting = UIComponent;
export type ButtonSetting = UIComponent;
export type ParagraphSetting = UIComponent;
export type NotificationSetting = UIComponent;
export type ErrorSetting = UIComponent;
export type ListSetting = UIComponent;
export type SelectSetting = UIComponent;
export type SettingsElement = UIComponent;

/** Voice conditions can reference global keys; character values win on collisions. */
export function voiceSettingsContext(
    pluginSettings: Record<string, any> | undefined,
    characterSettings: Record<string, any> | undefined,
): Record<string, any> {
    const setValues = (settings: Record<string, any> | undefined) => Object.fromEntries(
        Object.entries(settings ?? {}).filter(([, value]) => value !== undefined && value !== null),
    );
    return { ...setValues(pluginSettings), ...setValues(characterSettings) };
}

export interface PluginSettingsMap {
    [plugin_guid: string]: PluginSettings;
}

export interface PluginSettingsMessage extends BaseMessage {
    type: "plugin_settings_configs";
    plugin_settings_configs: PluginSettingsMap;
    has_plugin_settings: boolean;
}

export type ProviderSlot = "llm" | "agent_llm" | "vision" | "stt" | "tts" | "embedding";

export function filterProvidersForSlot(
    providers: ModelProviderDefinition[],
    slot: ProviderSlot,
): ModelProviderDefinition[] {
    return providers.filter(provider => !provider.slots || provider.slots.includes(slot));
}

export function providerVoiceSettingsValues(
    providerRef: string,
    providers: ModelProviderDefinition[],
    voiceSettings: Record<string, Record<string, any>> | undefined,
    pluginSettings?: Record<string, Record<string, any>>,
): Record<string, any> | undefined {
    const provider = providers.find(
        candidate => providerRef === `plugin:${candidate.plugin_guid}:${candidate.id}`,
    );
    if (!provider) return undefined;

    const defaults = Object.fromEntries(
        (provider.voice_settings_config ?? [])
            .flatMap(grid => uiFields([...grid.fields, ...(grid.content ?? [])]))
            .filter(field => field.default_value !== undefined)
            .map(field => [field.key, field.default_value]),
    );
    return {
        ...defaults,
        ...voiceSettingsContext(pluginSettings?.[provider.plugin_guid], voiceSettings?.[providerRef]),
    };
}

export function providerVoiceDisplayValue(
    providerRef: string,
    providers: ModelProviderDefinition[],
    voiceSettings: Record<string, Record<string, any>> | undefined,
    pluginSettings?: Record<string, Record<string, any>>,
): string | undefined {
    const provider = providers.find(
        candidate => providerRef === `plugin:${candidate.plugin_guid}:${candidate.id}`,
    );
    if (!provider) return undefined;

    const voiceField = provider.voice_settings_config?.flatMap(grid => uiFields([...grid.fields, ...(grid.content ?? [])]))
        .find(field => field.key === "voice");
    if (provider.voice_settings_config !== undefined && !voiceField) return undefined;

    const value = providerVoiceSettingsValues(providerRef, providers, voiceSettings, pluginSettings)?.["voice"];
    if (value === undefined || value === null || value === "") return undefined;

    if (voiceField?.type === "select") {
        const option = voiceField.select_options?.find(candidate => candidate.value === value);
        if (option) return option.label;
    }
    return String(value);
}

export function modelProviderLabel(
    providerRef: string | null | undefined,
    slot: ProviderSlot,
    providers: ModelProviderDefinition[],
): string {
    if (!providerRef) return "Not set";
    if (providerRef === "none") return "None";
    if (!providerRef.startsWith("plugin:")) return providerRef;

    const kind = slot === "agent_llm" ? "llm" : slot === "vision" ? "vlm" : slot;
    const provider = providers.find(p =>
        p.kind === kind &&
        (!p.slots || p.slots.includes(slot)) &&
        providerRef === `plugin:${p.plugin_guid}:${p.id}`
    );
    return provider?.label ?? "Plugin";
}

export function llmProviderSummary(
    providerRef: string | null | undefined,
    slot: "llm" | "agent_llm",
    providers: ModelProviderDefinition[],
    pluginSettings: Record<string, Record<string, unknown>>,
): string {
    const label = modelProviderLabel(providerRef, slot, providers);
    const provider = providers.find(p =>
        p.kind === "llm" &&
        (!p.slots || p.slots.includes(slot)) &&
        providerRef === `plugin:${p.plugin_guid}:${p.id}`
    );
    const modelField = provider?.settings_config.flatMap(grid => uiFields([...grid.fields, ...(grid.content ?? [])]))
        .find(field => field.label === "Model" || field.key === "model" || field.key?.endsWith("_model"));
    const configured = provider && modelField?.key ? pluginSettings[provider.plugin_guid]?.[modelField.key] : undefined;
    const model = typeof configured === "string" && configured.trim() ? configured.trim() : modelField?.default_value;
    return typeof model === "string" && model.trim() ? `${label} - ${model.trim()}` : label;
}

export interface ApiKeyDetection {
    patterns?: string[];
    priority?: number;
    setting_key?: string;
    provider_selections?: Record<string, string>;
}

export interface ModelProviderDefinition {
    kind: 'llm' | 'vlm' | 'stt' | 'tts' | 'embedding';
    id: string;
    label: string;
    settings_config: SettingsGrid[];
    plugin_guid: string;
    is_builtin: boolean;
    slots?: ProviderSlot[];
    api_key_detection?: ApiKeyDetection;
    voice_settings_config?: SettingsGrid[];
}

export interface PluginModelProvidersMessage extends BaseMessage {
    type: "plugin_model_providers";
    providers: ModelProviderDefinition[];
}
