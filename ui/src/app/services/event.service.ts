import { Injectable } from "@angular/core";
import { BehaviorSubject, filter, map, Observable } from "rxjs";
import { BaseMessage, TauriService } from "./tauri.service";

export interface EventMessage extends BaseMessage {
    type: "event";
    event:
        | GameEvent
        | ToolEvent
        | StatusEvent
        | ConversationEvent
        | ExternalEvent
        | QuestEvent
        | MemoryEvent;
}

export interface GameEvent {
    content: {
        event: string;
        timestamp: string;
        [key: string]: any;
    };
    historic: boolean;
    timestamp: string;
    kind: "game";
    processed_at: number;
}

export interface ToolEvent {
    request: {
        id: string;
        type: "function";
        function: {
            name: string;
            arguments: string;
        };
    }[];
    results: any[];
    text: (string | undefined)[];
    timestamp: string;
    kind: "tool";
    processed_at: number;
}

export interface StatusEvent {
    status: any;
    timestamp: string;
    kind: "status";
    processed_at: number;
}

export interface ConversationEvent {
    content: string;
    timestamp: string;
    kind: "user" | "user_speaking" | "assistant" | "assistant_acting" | "assistant_completed";
    processed_at: number;
}

export interface ExternalEvent {
    content: any;
    timestamp: string;
    kind: "external";
    processed_at: number;
}

export interface QuestEvent {
    content: {
        event: string;
        action?: string;
        quest_id?: string;
        quest_title?: string | null;
        stage_id?: string;
        stage_name?: string;
        stage_description?: string | null;
        stage_instructions?: string | null;
        active?: boolean;
        version?: string;
        quest_count?: number;
        [key: string]: any;
    };
    timestamp: string;
    kind: "quest";
    processed_at: number;
}

export interface MemoryEvent {
    content: string;
    metadata: any;
    embedding: number[];
    timestamp: string;
    kind: "memory";
    processed_at: number;
}

@Injectable({
    providedIn: "root",
})
export class EventService {
    private eventSubject = new BehaviorSubject<EventMessage[]>([]);
    public events$ = this.eventSubject.asObservable();

    constructor(private tauriService: TauriService) {
        // Subscribe to log messages from the TauriService
        this.tauriService.output$.pipe(
            filter((message): message is EventMessage =>
                message.type === "event"
            ),
        ).subscribe((logMessage) => {
            const currentLogs = this.eventSubject.getValue();
            this.eventSubject.next([...currentLogs, logMessage]);
        });
    }

    public clearConversation(): void {
        this.eventSubject.next([]);
    }

    public getCurrentConversation(): EventMessage[] {
        return this.eventSubject.getValue();
    }
}
