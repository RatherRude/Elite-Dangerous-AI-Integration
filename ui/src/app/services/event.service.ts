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
        | ExternalEvent;
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
    kind: "user" | "assistant" | "assistant_completed";
    processed_at: number;
}

export interface ExternalEvent {
    content: any;
    timestamp: string;
    kind: "external";
    processed_at: number;
}

@Injectable({
    providedIn: "root",
})
export class EventService {
    private readonly eventSubject = new BehaviorSubject<EventMessage[]>([]);
    public events$ = this.eventSubject.asObservable();

    constructor(private readonly tauriService: TauriService) {
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
