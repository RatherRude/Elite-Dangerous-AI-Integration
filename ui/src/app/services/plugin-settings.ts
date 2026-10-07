import { type BaseMessage } from "./tauri.service";

export interface PluginSettings {
    key: string;
    label: string;
    icon: string;
    grids: SettingsGrid[];
}

export interface SettingsGrid {
    key: string;
    label: string;
    fields: SettingsElement[];
}

export type SettingsElement = TextSetting | TextAreaSetting | NumericalSetting | ToggleSetting | SelectSetting | ButtonSetting | ParagraphSetting | ErrorSetting | ConditionSetting;

export interface SettingCondition {
    key: string;
    operator: "eq" | "neq" | "gt" | "geq" | "lt" | "leq" | "in" | "not_in" | "contains" | "not_contains" | "is_set" | "is_unset";
    value?: unknown;
    default_show?: boolean;
}

export interface ConditionSetting {
    key: string;
    type: "condition";
    condition: SettingCondition;
    fields: SettingsElement[];
}

/** All actual fields, including hidden descendants; containers have no stored value. */
export function settingsFields(elements: SettingsElement[]): SettingBase[] {
    return elements.flatMap(element => element.type === "condition"
        ? settingsFields(element.fields) : [element]);
}

export function matchesSettingCondition(condition: SettingCondition, actual: unknown): boolean {
    const unset = actual === undefined || actual === null;
    if (condition.operator === "is_set") return !unset;
    if (condition.operator === "is_unset") return unset;
    if (actual === undefined || actual === null) return condition.default_show ?? false;
    const expected = condition.value;
    switch (condition.operator) {
        case "eq": return actual === expected;
        case "neq": return actual !== expected;
        case "gt": case "geq": case "lt": case "leq":
            if (typeof actual !== "number" || typeof expected !== "number"
                || !Number.isFinite(actual) || !Number.isFinite(expected)) return false;
            switch (condition.operator) {
                case "gt": return actual > expected;
                case "geq": return actual >= expected;
                case "lt": return actual < expected;
                case "leq": return actual <= expected;
            }
        case "in": case "not_in":
            if (!Array.isArray(expected)) return false;
            return condition.operator === "in" ? expected.includes(actual) : !expected.includes(actual);
        case "contains": case "not_contains": {
            if (!Array.isArray(actual) && !(typeof actual === "string" && typeof expected === "string")) return false;
            const contains = Array.isArray(actual) ? actual.includes(expected) : (actual as string).includes(expected as string);
            return condition.operator === "contains" ? contains : !contains;
        }
        default: return false;
    }
}

/** Voice conditions can reference global keys; character values win on collisions. */
export function voiceSettingsContext(
    pluginSettings: Record<string, any> | undefined,
    characterSettings: Record<string, any> | undefined,
): Record<string, any> {
    return { ...pluginSettings, ...characterSettings };
}

export interface SettingBase {
    key: string;
    label: string;
    type: "paragraph" | "number" | "toggle" | "text" | "textarea" | "select" | "button" | "error";
    readonly: boolean | null;
    placeholder: string | null;
    default_value?: any;

    // Paragraph & Error
    content: string;

    // Text & Textarea
    max_length: number | null;
    min_length: number | null;
    hidden: boolean | null;

    // Textarea
    rows: number | null;
    cols: number | null;

    // Numbers
    min_value: number | null;
    max_value: number | null;
    step: number | null;

    // Select
    select_options: SelectOption[];
    multi_select: boolean;
}

export interface TextSetting extends SettingBase {
    default_value: string | null;
}

export interface TextAreaSetting extends SettingBase {
    default_value: string | string[] | null;
}

export interface NumericalSetting extends SettingBase {
    default_value: number | null;
}

export interface ToggleSetting extends SettingBase {
    default_value: boolean | null;
}

export interface ButtonSetting extends SettingBase {}

export interface ParagraphSetting extends SettingBase {}

export interface ErrorSetting extends SettingBase {}

export interface SelectSetting extends SettingBase {
    default_value: string | string[] | null;
}

export interface SelectOption {
    key: string;
    label: string;
    value: object | string | number | boolean;
    disabled: boolean;
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
): Record<string, any> | undefined {
    const provider = providers.find(
        candidate => providerRef === `plugin:${candidate.plugin_guid}:${candidate.id}`,
    );
    if (!provider || provider.voice_settings_config === undefined) return undefined;

    const defaults = Object.fromEntries(
        provider.voice_settings_config
            .flatMap(grid => settingsFields(grid.fields))
            .filter(field => field.default_value !== undefined)
            .map(field => [field.key, field.default_value]),
    );
    const declaredKeys = new Set(
        provider.voice_settings_config.flatMap(grid => settingsFields(grid.fields)).map(field => field.key),
    );
    const stored = Object.fromEntries(
        Object.entries(voiceSettings?.[providerRef] ?? {})
            .filter(([key]) => declaredKeys.has(key)),
    );
    return { ...defaults, ...stored };
}

export function providerVoiceDisplayValue(
    providerRef: string,
    providers: ModelProviderDefinition[],
    voiceSettings: Record<string, Record<string, any>> | undefined,
    legacyFallback: string,
): string | undefined {
    const provider = providers.find(
        candidate => providerRef === `plugin:${candidate.plugin_guid}:${candidate.id}`,
    );
    if (!provider || provider.voice_settings_config === undefined) return legacyFallback || undefined;

    const voiceField = provider.voice_settings_config
        .flatMap(grid => settingsFields(grid.fields))
        .find(field => field.key === "voice");
    if (!voiceField) return undefined;

    const stored = voiceSettings?.[providerRef];
    const value = stored && Object.prototype.hasOwnProperty.call(stored, "voice")
        ? stored["voice"]
        : Object.prototype.hasOwnProperty.call(voiceField, "default_value")
            ? voiceField.default_value
            : legacyFallback;
    if (value === undefined || value === null || value === "") return undefined;

    if (voiceField.type === "select") {
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
    const modelField = provider?.settings_config.flatMap(grid => settingsFields(grid.fields))
        .find(field => field.label === "Model" || field.key === "model" || field.key.endsWith("_model"));
    const configured = provider && modelField ? pluginSettings[provider.plugin_guid]?.[modelField.key] : undefined;
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
