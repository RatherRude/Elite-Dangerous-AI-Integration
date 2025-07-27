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
    private chatHistorySubject = new BehaviorSubject<ChatMessage[]>([]);
    public chatHistory$ = this.chatHistorySubject.asObservable();

    private chatMessageSubject = new BehaviorSubject<ChatMessage | null>(null);
    public chatMessage$ = this.chatMessageSubject.asObservable()

    constructor(private tauriService: TauriService) {
        // Subscribe to log messages from the TauriService
        this.tauriService.output$.pipe(
            filter((message): message is ChatMessage =>
                message.type === "chat"
            ),
        ).subscribe((chatMessage) => {
            if (chatMessage.type === "chat") {
                this.chatMessageSubject.next(chatMessage);
                const currentLogs = this.chatHistorySubject.getValue();
                this.chatHistorySubject.next([...currentLogs, chatMessage]);
            }
        });
    }

    public clearChat(): void {
        this.chatHistorySubject.next([]);
    }

    public getCurrentChat(): ChatMessage[] {
        return this.chatHistorySubject.getValue();
    }
}
