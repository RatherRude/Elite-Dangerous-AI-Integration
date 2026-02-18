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
    voice: string;
    avatar_url: string;
    prompt: string;
}

export interface QuestDefinition {
    id: string;
    title: string;
    description: string;
    active?: boolean;
    stages: QuestStage[];
}

export interface QuestStage {
    id: string;
    description: string;
    instructions: string;
    plan?: QuestPlanStep[];
}

export interface QuestPlanStep {
    conditions: QuestCondition[];
    actions: QuestAction[];
}

export interface QuestCondition {
    source: "projection" | "event";
    path: string;
    operator: "equals" | "==";
    value: string | number | boolean | null;
}

export interface QuestAction {
    action: "log" | "advance_stage" | "set_active" | "play_sound";
    message?: string;
    target_stage_id?: string;
    quest_id?: string;
    active?: boolean;
    url?: string;
    transcription?: string;
    actor_id?: string | null;
}

export interface GetQuestCatalogMessage extends BaseCommand {
    type: "get_quest_catalog";
}

export interface SaveQuestCatalogMessage extends BaseCommand {
    type: "save_quest_catalog";
    data: QuestCatalog;
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
}
