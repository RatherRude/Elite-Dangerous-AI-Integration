import { Injectable } from "@angular/core";
import { BehaviorSubject, filter, Observable } from "rxjs";
import { type BaseMessage, TauriService } from "./tauri.service";

export interface ConfigMessage extends BaseMessage {
    type: "config";
    config: Config;
}

export interface InputDeviceNamesMessage extends BaseMessage {
    type: "input_device_names";
    device_names: string[];
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
    react_to_text_local_var: boolean;
    react_to_text_starsystem_var: boolean;
    react_to_text_npc_var: boolean;
    react_to_text_squadron_var: boolean;
    react_to_material: string;
    react_to_danger_mining_var: boolean;
    react_to_danger_onfoot_var: boolean;
    edcopilot: boolean;
    edcopilot_dominant: boolean;
    tts_voice: string;
    tts_speed: string;
    ptt_key: string;
    input_device_name: string;
    game_events: { [key: string]: { [key: string]: boolean } };
    ed_journal_path: string;
    ed_appdata_path: string;
}

@Injectable({
    providedIn: "root",
})
export class ConfigService {
    private configSubject = new BehaviorSubject<Config | null>(null);
    public config$ = this.configSubject.asObservable();

    private inputDeviceNamesSubject = new BehaviorSubject<string[]>([]);
    public inputDeviceNames$ = this.inputDeviceNamesSubject.asObservable();

    constructor(private tauriService: TauriService) {
        // Subscribe to config messages from the TauriService
        this.tauriService.output$.pipe(
            filter((
                message,
            ): message is ConfigMessage | InputDeviceNamesMessage =>
                message.type === "config" ||
                message.type === "input_device_names"
            ),
        ).subscribe((configMessage) => {
            if (configMessage.type === "config") {
                this.configSubject.next(configMessage.config);
            } else if (configMessage.type === "input_device_names") {
                this.inputDeviceNamesSubject.next(configMessage.device_names);
            }
        });
    }

    public async updateConfig(partialConfig: Partial<Config>): Promise<void> {
        const currentConfig = this.getCurrentConfig();
        if (!currentConfig) {
            throw new Error("Cannot update config before it is initialized");
        }

        // Merge the partial config with the current config
        const newConfig: Config = {
            ...currentConfig,
            ...partialConfig,
        };

        // Update UI state immediately (this makes the ui really laggy somehow)
        //this.configSubject.next(newConfig);

        const message: ConfigMessage = {
            type: "config",
            timestamp: new Date().toISOString(),
            config: newConfig,
        };

        // Send update to backend
        await this.tauriService.send_message(message);
    }

    public async updateEventConfig(
        section: string,
        event: string,
        enabled: boolean,
    ): Promise<void> {
        const currentConfig = this.getCurrentConfig();
        if (!currentConfig) {
            throw new Error("Cannot update config before it is initialized");
        }

        const newConfig = {
            game_events: {
                ...currentConfig.game_events,
                [section]: {
                    ...currentConfig.game_events[section],
                    [event]: enabled,
                },
            },
        };

        return this.updateConfig(newConfig);
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
