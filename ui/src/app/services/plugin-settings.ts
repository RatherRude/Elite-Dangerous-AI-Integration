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
    fields: TextSetting[] | NumericalSetting[] | ToggleSetting[] | SelectSetting[];
}

export interface SettingBase {
    key: string;
    label: string;
    type: "paragraph" | "number" | "toggle" | "text" | "textarea" | "select";
    readonly: boolean | null;
    placeholder: string | null;

    // Paragraph
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

export interface SelectSetting extends SettingBase {
    default_value: string | string[] | null;
}

export interface SelectOption {
    key: string;
    label: string;
    value: object | string | number | boolean;
    disabled: boolean;
}

export interface PluginSettingsMessage extends BaseMessage {
    type: "plugin_settings_configs";
    plugin_settings_configs: PluginSettings[];
}
