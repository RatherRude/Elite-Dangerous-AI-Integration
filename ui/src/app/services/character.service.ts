import { Injectable } from "@angular/core";
import { BehaviorSubject, filter, map, Observable } from "rxjs";
import { BaseCommand, BaseMessage, TauriService } from "./tauri.service";
import { Config, ConfigService } from "./config.service.js";

export interface ConfigWithCharacters extends Config {
    characters: Character[];
    active_character_index: number;
}

export interface Character {
    name: string;
    character: string;
    personality_preset: string;
    personality_verbosity: number;
    personality_vulgarity: number;
    personality_empathy: number;
    personality_formality: number;
    personality_confidence: number;
    personality_ethical_alignment: string;
    personality_moral_alignment: string;
    personality_tone: string;
    personality_character_inspiration: string;
    personality_language: string;
    personality_knowledge_pop_culture: boolean;
    personality_knowledge_scifi: boolean;
    personality_knowledge_history: boolean;
    tts_voice: string;
    tts_speed: string;
    tts_prompt: string;

    

    // Event reaction properties
    event_reaction_enabled_var: boolean;
    react_to_text_local_var: boolean;
    react_to_text_starsystem_var: boolean;
    react_to_text_npc_var: boolean;
    react_to_text_squadron_var: boolean;
    react_to_material: string;
    idle_timeout_var: number;
    react_to_danger_mining_var: boolean;
    react_to_danger_onfoot_var: boolean;
    react_to_danger_supercruise_var: boolean;
    game_events: { [key: string]: boolean };
}


export interface CharacterOperationMessage extends BaseCommand {
    type: "change_character";
    operation: "add" | "update" | "delete" | "set_active";
    index?: number;
    character?: Character;
    set_active?: boolean;
}

@Injectable({
    providedIn: "root",
})
export class CharacterService {
    private characterSubject = new BehaviorSubject<Character | null>(null);
    public character$ = this.characterSubject.asObservable();
    private activeCharacterIndex: number | null = null;

    private characterListSubject = new BehaviorSubject<Character[]>([]);
    public characterList$ = this.characterListSubject.asObservable();

    constructor(
        private tauriService: TauriService,
        private configService: ConfigService,
    ) {
        // Subscribe to states messages from the TauriService
        this.configService.config$.pipe().subscribe(
            (config: Config | null) => {
                if (!config) return;
                this.activeCharacterIndex = config.active_character_index;

                this.characterSubject.next(
                    (config as ConfigWithCharacters)
                        .characters[config.active_character_index],
                );

                // Update the character list
                this.characterListSubject.next(
                    (config as ConfigWithCharacters).characters,
                );
            },
        );
    }

    public getCharacterProperty<T extends keyof Character>(propName: T, defaultValue: Character[T]): Character[T] {
        const character = this.characterSubject.getValue();
        const value = character?.[propName] ?? defaultValue;
        return value;
    }
    public async setCharacterProperty<T extends keyof Character>(
        propName: T,
        value: Character[T],
    ): Promise<void> {
        const character = this.characterSubject.getValue();
        if (!character) return;
        character[propName] = value;
        this.characterSubject.next(character);
        // Update the active character in the config
        await this.updateCharacter(
            this.activeCharacterIndex ?? 0,
            character,
        );
    }

    public getCharacterEventProperty<T extends keyof Character["game_events"]>(
        eventName: T,
        defaultValue: Character["game_events"][T],
    ): Character["game_events"][T] {
        const character = this.characterSubject.getValue();
        if (!character) return defaultValue;
        return character.game_events[eventName] ?? defaultValue;
    }

    public async setCharacterEventProperty<T extends keyof Character["game_events"]>(
        eventName: T,
        value: Character["game_events"][T],
    ): Promise<void> {
        const character = this.characterSubject.getValue();
        if (!character) return;
        character.game_events[eventName] = value;
        this.characterSubject.next(character);
        // Update the active character in the config
        await this.updateCharacter(
            this.activeCharacterIndex ?? 0,
            character,
        );
    }

    public async addCharacter(
        character: Character,
        setActive: boolean = false,
    ): Promise<void> {
        const message: CharacterOperationMessage = {
            type: "change_character",
            timestamp: new Date().toISOString(),
            operation: "add",
            character: character,
            set_active: setActive,
        };

        await this.tauriService.send_command(message);
    }

    public async updateCharacter(
        index: number,
        character: Character,
    ): Promise<void> {
        const message: CharacterOperationMessage = {
            type: "change_character",
            timestamp: new Date().toISOString(),
            operation: "update",
            index: index,
            character: character,
        };

        await this.tauriService.send_command(message);
    }

    public async deleteCharacter(index: number): Promise<void> {
        const message: CharacterOperationMessage = {
            type: "change_character",
            timestamp: new Date().toISOString(),
            operation: "delete",
            index: index,
        };

        await this.tauriService.send_command(message);
        await this.setActiveCharacter(0);
    }

    public async setActiveCharacter(index: number): Promise<void> {
        const message: CharacterOperationMessage = {
            type: "change_character",
            timestamp: new Date().toISOString(),
            operation: "set_active",
            index: index,
        };

        await this.tauriService.send_command(message);
    }

    public async resetGameEvents(character_index: number): Promise<void> {
        return this.configService.resetGameEvents(character_index);
    }
}
