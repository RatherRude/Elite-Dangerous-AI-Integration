import { Injectable } from "@angular/core";
import { BehaviorSubject, filter, Subject } from "rxjs";
import { BaseCommand, BaseMessage, TauriService } from "./tauri.service";

export interface QuestCatalog {
    version: string;
    actors?: QuestActor[];
    quests: QuestDefinition[];
}

export interface QuestActor {
    id: string;
    name: string;
    name_color: string;
    voice: string;
    avatar_url: string;
    prompt: string;
}

export interface QuestDefinition {
    id: string;
    title: string;
    description: string;
    active?: boolean;
    initial_stage_id?: string;
    stages: QuestStage[];
    fallback_stage?: QuestFallbackStage;
}

export interface QuestStage {
    id: string;
    description: string;
    instructions: string;
    plan?: QuestPlanStep[];
}

export interface QuestFallbackStage {
    description: string;
    instructions: string;
    plan?: QuestPlanStep[];
}

export interface QuestPlanStep {
    conditions: QuestCondition[];
    actions: QuestAction[];
}

export interface QuestCondition {
    source: "event";
    path: string;
    operator: "equals" | "==";
    value: string | number | boolean | null;
}

export interface QuestAction {
    action: "log" | "advance_stage" | "set_active" | "play_sound" | "npc_message";
    message?: string;
    target_stage_id?: string;
    quest_id?: string;
    active?: boolean;
    file_name?: string;
    transcription?: string;
    actor_id?: string | null;
}

export interface QuestAudioImportResult {
    canceled: boolean;
    fileName?: string;
    copied?: boolean;
    reused?: boolean;
    destinationPath?: string;
}

export interface GetQuestCatalogMessage extends BaseCommand {
    type: "get_quest_catalog";
}

export interface SaveQuestCatalogMessage extends BaseCommand {
    type: "save_quest_catalog";
    data: QuestCatalog;
}

export interface ResetQuestProgressMessage extends BaseCommand {
    type: "reset_quest_progress";
}

export interface QuestCatalogMessage extends BaseMessage {
    type: "quest_catalog";
    data: QuestCatalog;
    raw: string;
    error?: string;
    path?: string;
}

export interface QuestCatalogSavedMessage extends BaseMessage {
    type: "quest_catalog_saved";
    success: boolean;
    message?: string;
    data?: QuestCatalog;
    raw?: string;
}

@Injectable({
    providedIn: "root",
})
export class QuestsService {
    private catalogSubject = new BehaviorSubject<QuestCatalog | null>(null);
    public catalog$ = this.catalogSubject.asObservable();
    private rawYamlSubject = new BehaviorSubject<string>("");
    public rawYaml$ = this.rawYamlSubject.asObservable();
    private catalogPathSubject = new BehaviorSubject<string | null>(null);
    public catalogPath$ = this.catalogPathSubject.asObservable();
    private loadErrorSubject = new BehaviorSubject<string | null>(null);
    public loadError$ = this.loadErrorSubject.asObservable();
    private loadPendingSubject = new BehaviorSubject<boolean>(false);
    public loadPending$ = this.loadPendingSubject.asObservable();
    private lastLoadedAtSubject = new BehaviorSubject<string | null>(null);
    public lastLoadedAt$ = this.lastLoadedAtSubject.asObservable();
    private saveResultSubject = new Subject<QuestCatalogSavedMessage>();
    public saveResult$ = this.saveResultSubject.asObservable();

    constructor(private tauriService: TauriService) {
        this.tauriService.output$
            .pipe(
                filter(
                    (
                        message,
                    ): message is
                        | QuestCatalogMessage
                        | QuestCatalogSavedMessage =>
                        message.type === "quest_catalog" ||
                        message.type === "quest_catalog_saved",
                ),
            )
            .subscribe((message) => {
                if (message.type === "quest_catalog") {
                    this.loadPendingSubject.next(false);
                    this.lastLoadedAtSubject.next(new Date().toISOString());
                    this.loadErrorSubject.next(message.error || null);
                    this.catalogPathSubject.next(message.path || null);
                    if (message.data) {
                        this.catalogSubject.next(message.data);
                        this.rawYamlSubject.next(message.raw || "");
                    } else if (message.raw) {
                        this.rawYamlSubject.next(message.raw);
                    }
                } else if (message.type === "quest_catalog_saved") {
                    if (message.data) {
                        this.catalogSubject.next(message.data);
                    }
                    if (message.raw) {
                        this.rawYamlSubject.next(message.raw);
                    }
                    this.saveResultSubject.next(message);
                }
            });
    }

    public loadCatalog(): void {
        this.loadPendingSubject.next(true);
        const command: GetQuestCatalogMessage = {
            type: "get_quest_catalog",
            timestamp: new Date().toISOString(),
        };
        this.tauriService.send_command(command);
    }

    public saveCatalog(catalog: QuestCatalog): void {
        const command: SaveQuestCatalogMessage = {
            type: "save_quest_catalog",
            timestamp: new Date().toISOString(),
            data: catalog,
        };
        this.tauriService.send_command(command);
    }

    public resetQuestProgress(): void {
        const command: ResetQuestProgressMessage = {
            type: "reset_quest_progress",
            timestamp: new Date().toISOString(),
        };
        this.tauriService.send_command(command);
    }

    public async importQuestAudioFile(
        catalogPath: string | null,
    ): Promise<QuestAudioImportResult> {
        if (!catalogPath) {
            throw new Error("Quest catalog path is not available.");
        }
        if (!window.electronAPI?.invoke) {
            throw new Error("Electron API is not available.");
        }
        let result: unknown;
        try {
            result = await window.electronAPI.invoke("select_quest_audio_file", {
                catalogPath,
            });
        } catch (error: unknown) {
            const message = error instanceof Error ? error.message : String(error);
            if (message.includes("No handler registered for 'select_quest_audio_file'")) {
                throw new Error(
                    "Audio picker backend is not loaded. Restart the desktop app to pick files.",
                );
            }
            throw error;
        }
        if (!result || typeof result !== "object") {
            throw new Error("Audio import failed: invalid response.");
        }
        return result as QuestAudioImportResult;
    }
}
