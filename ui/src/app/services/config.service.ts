import { Injectable } from "@angular/core";
import { BehaviorSubject, filter, Observable } from "rxjs";
import { type BaseMessage, TauriService } from "./tauri.service";
import { SystemInfo, Character, Config } from "../types/models";

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

export interface CharacterOperationMessage extends BaseMessage {
    type: "change_config";
    config: {
        character_operation: "add" | "update" | "delete" | "set_active";
        character_index?: number;
        character_data?: Character;
        set_active?: boolean;
    };
}

export interface ModelValidationMessage extends BaseMessage {
    type: "model_validation";
    success: boolean;
    message: string;
}

export interface StartMessage extends BaseMessage {
    type: "start";
}

export interface SystemInfoMessage extends BaseMessage {
    type: "system";
    system: SystemInfo;
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
                | ModelValidationMessage
                | StartMessage =>
                message.type === "config" ||
                message.type === "system" ||
                message.type === "model_validation" ||
                message.type === "start"
            ),
        ).subscribe((message) => {
            if (message.type === "config") {
                this.configSubject.next(message.config);
            } else if (message.type === "system") {
                this.systemSubject.next(message.system);
            } else if (message.type === "model_validation") {
                this.validationSubject.next(message);
            } else if (message.type === "start") {
                this.validationSubject.next(null);
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

    public async addCharacter(character: Character, setActive: boolean = false): Promise<void> {
        const message: CharacterOperationMessage = {
            type: "change_config",
            timestamp: new Date().toISOString(),
            config: {
                character_operation: "add",
                character_data: character,
                set_active: setActive
            }
        };
        
        await this.tauriService.send_message(message);
    }
    
    public async updateCharacter(index: number, character: Character): Promise<void> {
        const message: CharacterOperationMessage = {
            type: "change_config",
            timestamp: new Date().toISOString(),
            config: {
                character_operation: "update",
                character_index: index,
                character_data: character
            }
        };
        
        await this.tauriService.send_message(message);
    }
    
    public async deleteCharacter(index: number): Promise<void> {
        const message: CharacterOperationMessage = {
            type: "change_config",
            timestamp: new Date().toISOString(),
            config: {
                character_operation: "delete",
                character_index: index
            }
        };
        
        await this.tauriService.send_message(message);
    }
    
    public async setActiveCharacter(index: number): Promise<void> {
        const message: CharacterOperationMessage = {
            type: "change_config",
            timestamp: new Date().toISOString(),
            config: {
                character_operation: "set_active",
                character_index: index
            }
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

    public async resetGameEvents(): Promise<void> {
        const message: ChangeConfigMessage = {
            type: "change_config",
            timestamp: new Date().toISOString(),
            config: {
                reset_game_events: true
            }
        };

        try {
            await this.tauriService.send_message(message);
        } catch (error) {
            console.error('Error sending reset game events request:', error);
        }
    }
}
