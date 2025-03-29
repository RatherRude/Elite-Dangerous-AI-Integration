import { Injectable } from "@angular/core";
import { BehaviorSubject, filter, map, Observable } from "rxjs";
import { BaseMessage, TauriService } from "./tauri.service";

export interface ConversationMessage extends BaseMessage {
    type: "conversation";
    kind: "user" | "assistant" | "assistant_completed";
    content: string;
}

export interface EventMessage extends BaseMessage {
    type: "event";
    event: any;
}

type Message = ConversationMessage | EventMessage;

@Injectable({
    providedIn: "root",
})
export class ConversationService {
    private conversationSubject = new BehaviorSubject<Message[]>([]);
    public conversation$ = this.conversationSubject.asObservable();

    constructor(private tauriService: TauriService) {
        // Subscribe to log messages from the TauriService
        this.tauriService.output$.pipe(
            filter((message): message is Message =>
                message.type === "conversation" || message.type === "event"
            ),
        ).subscribe((logMessage) => {
            const currentLogs = this.conversationSubject.getValue();
            this.conversationSubject.next([...currentLogs, logMessage]);
        });
    }

    public clearConversation(): void {
        this.conversationSubject.next([]);
    }

    public getCurrentConversation(): Message[] {
        return this.conversationSubject.getValue();
    }
}
