import { Injectable } from "@angular/core";
import { BehaviorSubject, filter } from "rxjs";
import { BaseMessage, TauriService } from "./tauri.service";
import { UIService } from "./ui.service";

export interface ChatMessage extends BaseMessage {
    type: "chat";
    role: string;
    message: string;
}

export interface ToolEvent {
    kind: 'tool';
    request: any[];
    results: any[];
    text?: string[];
}

export interface EventMessage extends BaseMessage {
    type: 'event';
    event: ToolEvent;
}

@Injectable({
    providedIn: "root",
})
export class ChatService {
    private chatHistorySubject = new BehaviorSubject<ChatMessage[]>([]);
    public chatHistory$ = this.chatHistorySubject.asObservable();

    private chatMessageSubject = new BehaviorSubject<ChatMessage | null>(null);
    public chatMessage$ = this.chatMessageSubject.asObservable()

    private searchResultSubject = new BehaviorSubject<any | null>(null);
    public searchResult$ = this.searchResultSubject.asObservable();

    constructor(private tauriService: TauriService, private uiService: UIService) {
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

        this.tauriService.output$.pipe(
            filter((message): message is EventMessage =>
                message.type === "event" && (message as any).event?.kind === "tool"
            ),
        ).subscribe((eventMessage) => {
            const toolEvent = eventMessage.event;
            const webSearchRequestIndex = toolEvent.request.findIndex((r: any) => r.function?.name === 'web_search_agent');
            
            if (webSearchRequestIndex !== -1 && toolEvent.results[webSearchRequestIndex]) {
                this.searchResultSubject.next(toolEvent.results[webSearchRequestIndex]);
                this.uiService.showTab('search');
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
