import { Injectable } from "@angular/core";
import { BehaviorSubject, filter, Observable } from "rxjs";
import { BaseCommand, type BaseMessage, TauriService } from "./tauri.service";
import { PluginSettings, PluginSettingsMessage } from "./plugin-settings";
import { ScreenInfo } from "../models/screen-info";

export interface ConfigMessage extends BaseMessage {
    type: "config";
    config: Config;
}
export interface SecretsMessage extends BaseMessage {
    type: "secrets";
    secrets: Secrets;
}
export interface RunningConfigMessage extends BaseMessage {
    type: 'running_config';
    config: Config;
}
export interface ChangeConfigMessage extends BaseCommand {
    type: "change_config";
    config: Partial<Config>;
}

export interface ChangeEventConfigMessage extends BaseCommand {
    type: "change_event_config";
    section: string;
    event: string;
    value: any;
}

export interface ModelValidationMessage extends BaseMessage {
    type: "model_validation";
    success: boolean;
    message: string;
}

export interface StartMessage extends BaseMessage {
    type: "start";
}

export interface SystemInfo {
    os: string;
    input_device_names: string[];
    output_device_names: string[];
    edcopilot_installed: boolean;
}

export interface SystemInfoMessage extends BaseMessage {
    type: "system";
    system: SystemInfo;
}

export interface ProviderSecrets {
    openai?: string | null;
    openrouter?: string | null;
    google_ai_studio?: string | null;
    custom?: string | null;
    custom_multi_modal?: string | null;
    local_ai_server?: string | null;
}

export interface Secrets {
    llm: ProviderSecrets;
    stt: ProviderSecrets;
    tts: ProviderSecrets;
    vision: ProviderSecrets;
}

export interface Config {
    commander_name: string;
    // Stored characters
    characters: unknown[];
    active_character_index: number;
    // Other config settings
    llm_provider:
        | "openai"
        | "openrouter"
        | "google-ai-studio"
        | "custom"
        | "local-ai-server";
    llm_model_name: string;
    llm_endpoint: string;
    llm_temperature: number;
    vision_provider: "openai" | "google-ai-studio" | "custom" | "none";
    vision_model_name: string;
    vision_endpoint: string;
    stt_provider:
        | "openai"
        | "custom"
        | "custom-multi-modal"
        | "google-ai-studio"
        | "none"
        | "local-ai-server";
    stt_model_name: string;
    stt_endpoint: string;
    stt_language: string;
    stt_custom_prompt: string;
    stt_required_word: string;
    tts_provider: "openai" | "edge-tts" | "custom" | "none" | "local-ai-server";
    tts_model_name: string;
    tts_endpoint: string;
    tools_var: boolean;
    vision_var: boolean;
    ptt_var: "voice_activation" | "push_to_talk" | "push_to_mute" | "toggle";
    ptt_inverted_var: boolean;
    mute_during_response_var: boolean;
    game_actions_var: boolean;
    web_search_actions_var: boolean;
    ui_actions_var: boolean;
    use_action_cache_var: boolean;
    edcopilot: boolean;
    edcopilot_dominant: boolean;
    ptt_key: string;
    input_device_name: string;
    output_device_name: string;
    cn_autostart: boolean;
    ed_journal_path: string;
    ed_appdata_path: string;
    reset_game_events?: boolean; // Flag to request resetting game events to defaults
    qol_autobrake: boolean; // Quality of life: Auto brake when approaching stations
    qol_autoscan: boolean; // Quality of life: Auto scan when entering new systems
    
    // Overlay settings
    overlay_show_avatar: boolean;
    overlay_show_chat: boolean;
    overlay_position: "left" | "right";
    overlay_screen_id: number;

    plugin_settings: { [key: string]: any };
}

@Injectable({
    providedIn: "root",
})
export class ConfigService {
    private configSubject = new BehaviorSubject<Config | null>(null);
    public config$ = this.configSubject.asObservable();

    private secretsSubject = new BehaviorSubject<Secrets | null>(null);
    public secrets$ = this.secretsSubject.asObservable();

    private systemSubject = new BehaviorSubject<SystemInfo | null>(null);
    public system$ = this.systemSubject.asObservable();
    public systemInfo: SystemInfo | null = null;

    // Screens are managed separately from SystemInfo
    private screensSubject = new BehaviorSubject<ScreenInfo[] | null>(null);
    public screens$ = this.screensSubject.asObservable();

    private validationSubject = new BehaviorSubject<
        ModelValidationMessage | null
    >(null);
    public validation$ = this.validationSubject.asObservable();

    private plugin_settings_message_subject = new BehaviorSubject<
        PluginSettingsMessage | null
    >(null);
    public plugin_settings_message$ = this.plugin_settings_message_subject
        .asObservable();

    constructor(private tauriService: TauriService) {
        // Subscribe to config messages from the TauriService
        this.tauriService.output$.pipe(
            filter((
                message,
            ): message is
                | ConfigMessage
                | RunningConfigMessage
                | SystemInfoMessage
                | ModelValidationMessage
                | PluginSettingsMessage
                | StartMessage =>
                message.type === "config" ||
                message.type === "running_config" ||
                message.type === "system" ||
                message.type === "model_validation" ||
                message.type === "plugin_settings_configs" ||
                message.type === "start"
            ),
        ).subscribe((message: ConfigMessage | SecretsMessage | RunningConfigMessage | SystemInfoMessage | ModelValidationMessage | PluginSettingsMessage | StartMessage) => {
            if (message.type === "config") {
                this.configSubject.next(message.config);
            } else if (message.type === "secrets") {
                this.secretsSubject.next(message.secrets);
            } else if (message.type === "running_config") {
                this.configSubject.next(message.config);
            } else if (message.type === "system") {
                // Do not mutate SystemInfo with screen data
                this.systemSubject.next(message.system);
                this.systemInfo = message.system;
                // Load screens separately
                this.loadScreens();
            } else if (message.type === "model_validation") {
                this.validationSubject.next(message);
            } else if (message.type === "plugin_settings_configs") {
                this.plugin_settings_message_subject.next(message);
            } else if (message.type === "start") {
                this.validationSubject.next(null);
            }
        });
    }

    private async loadScreens(): Promise<void> {
        try {
            const screens = await this.tauriService.getAvailableScreens();
            this.screensSubject.next(screens ?? []);
        } catch (error) {
            console.error('Failed to get screen information:', error);
            this.screensSubject.next([]);
        }
    }

    public async changeConfig(partialConfig: Partial<Config>): Promise<void> {
        const currentConfig = this.getCurrentConfig();
        if (!currentConfig) {
            throw new Error("Cannot update config before it is initialized");
        }

        const message: ChangeConfigMessage = {
            type: "change_config",
            timestamp: new Date().toISOString(),
            config: partialConfig,
        };

        // Send update to backend
        await this.tauriService.send_command(message);
    }

    public async changeEventConfig(
        section: string,
        event: string,
        enabled: boolean,
    ): Promise<void> {
        const currentConfig = this.getCurrentConfig();
        if (!currentConfig) {
            throw new Error("Cannot update config before it is initialized");
        }

        const message: ChangeEventConfigMessage = {
            type: "change_event_config",
            timestamp: new Date().toISOString(),
            section,
            event,
            value: enabled,
        };

        await this.tauriService.send_command(message);
    }

    public async setPluginSetting(key: string, value: any): Promise<void> {
        const currentConfig = this.getCurrentConfig();
        if (!currentConfig) {
            throw new Error("Cannot update config before it is initialized");
        }

        const updatedPluginSettings = {
            ...currentConfig.plugin_settings,
            [key]: value,
        };

        const message: ChangeConfigMessage = {
            type: "change_config",
            timestamp: new Date().toISOString(),
            config: { plugin_settings: updatedPluginSettings },
        };

        await this.tauriService.send_command(message);
    }

    public getPluginSetting(key: string): any | null {
        const currentConfig = this.getCurrentConfig();
        return currentConfig?.plugin_settings?.[key] ?? null;
    }

    public getCurrentConfig(): Config | null {
        return this.configSubject.getValue();
    }

    public async assignPTT(): Promise<void> {
        const message = {
            type: "assign_ptt",
            timestamp: new Date().toISOString(),
            index: 0,
        };
        await this.tauriService.send_command(message);
    }

    public async clearHistory(): Promise<void> {
        const message: BaseCommand = {
            type: "clear_history",
            timestamp: new Date().toISOString(),
        };

        try {
            await this.tauriService.send_command(message);
        } catch (error) {
            console.error("Error sending clear history request:", error);
        }
    }
}
