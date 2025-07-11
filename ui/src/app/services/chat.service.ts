import { Injectable } from "@angular/core";
import { BehaviorSubject, filter } from "rxjs";
import { BaseMessage, TauriService } from "./tauri.service";

export interface ChatMessage extends BaseMessage {
    type: "chat";
    role: string;
    message: string;
}

@Injectable({
    providedIn: "root",
})
export class ChatService {
    private chatSubject = new BehaviorSubject<ChatMessage[]>([]);
    public chat$ = this.chatSubject.asObservable();

    constructor(private tauriService: TauriService) {
        // Subscribe to log messages from the TauriService
        this.tauriService.output$.pipe(
            filter((message): message is ChatMessage =>
                message.type === "chat"
            ),
        ).subscribe((chatMessage) => {
            if (chatMessage.type === "chat") {
                const currentLogs = this.chatSubject.getValue();
                this.chatSubject.next([...currentLogs, chatMessage]);
            }
        });
    }

    public clearChat(): void {
        this.chatSubject.next([]);
    }

    public getCurrentChat(): ChatMessage[] {
        return this.chatSubject.getValue();
    }
}
