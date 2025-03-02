import { Injectable } from "@angular/core";
import { BehaviorSubject, filter, Observable } from "rxjs";
import { type BaseMessage, TauriService } from "./tauri.service";

export interface ConfigMessage extends BaseMessage {
    type: "config";
    config: Config;
}
export interface ChangeConfigMessage extends BaseMessage {
    type: "change_config";
    config: Partial<Config>;
}

export interface ChangeEventConfigMessage extends BaseMessage {
    type: "change_event_config";
    section: string;
    event: string;
    value: any;
}

export interface ModelValidationMessage extends BaseMessage {
    type: "model_validation";
    status: "upgrade" | "fallback" | "error";
    message: string;
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

export interface Config {
    api_key: string;
    llm_api_key: string;
    llm_endpoint: string;
    commander_name: string;
    character: string;
    llm_model_name: string;
    vision_model_name: string;
    vision_endpoint: string;
    vision_api_key: string;
    stt_provider: "openai" | "custom" | "none";
    stt_model_name: string;
    stt_api_key: string;
    stt_endpoint: string;
    stt_custom_prompt: string;
    stt_required_word: string;
    tts_provider: "openai" | "edge-tts" | "custom" | "none";
    tts_model_name: string;
    tts_api_key: string;
    tts_endpoint: string;
    tools_var: boolean;
    vision_var: boolean;
    ptt_var: boolean;
    mute_during_response_var: boolean;
    continue_conversation_var: boolean;
    event_reaction_enabled_var: boolean;
    game_actions_var: boolean;
    web_search_actions_var: boolean;
    use_action_cache_var: boolean;
    react_to_text_local_var: boolean;
    react_to_text_starsystem_var: boolean;
    react_to_text_npc_var: boolean;
    react_to_text_squadron_var: boolean;
    react_to_material: string;
    react_to_danger_mining_var: boolean;
    react_to_danger_onfoot_var: boolean;
    react_to_danger_supercruise_var: boolean;
    edcopilot: boolean;
    edcopilot_dominant: boolean;
    tts_voice: string;
    tts_speed: string;
    ptt_key: string;
    input_device_name: string;
    output_device_name: string;
    game_events: { [key: string]: { [key: string]: 'critical' | 'informative' | 'background' | 'disabled' } };
    ed_journal_path: string;
    ed_appdata_path: string;
}

@Injectable({
    providedIn: "root",
})
export class ConfigService {
    private configSubject = new BehaviorSubject<Config | null>(null);
    public config$ = this.configSubject.asObservable();

    private systemSubject = new BehaviorSubject<SystemInfo | null>(null);
    public system$ = this.systemSubject.asObservable();

    private validationSubject = new BehaviorSubject<
        ModelValidationMessage | null
    >(null);
    public validation$ = this.validationSubject.asObservable();

    constructor(private tauriService: TauriService) {
        // Subscribe to config messages from the TauriService
        this.tauriService.output$.pipe(
            filter((
                message,
            ): message is
                | ConfigMessage
                | SystemInfoMessage
                | ModelValidationMessage =>
                message.type === "config" ||
                message.type === "system" ||
                message.type === "model_validation"
            ),
        ).subscribe((message) => {
            if (message.type === "config") {
                this.configSubject.next(message.config);
            } else if (message.type === "system") {
                this.systemSubject.next(message.system);
            } else if (message.type === "model_validation") {
                this.validationSubject.next(message);
            }
        });
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
        await this.tauriService.send_message(message);
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

        await this.tauriService.send_message(message);
    }

    public getCurrentConfig(): Config | null {
        return this.configSubject.getValue();
    }

    public async assignPTT(): Promise<void> {
        const message = {
            type: "assign_ptt",
            timestamp: new Date().toISOString(),
        };
        await this.tauriService.send_message(message);
    }
}
