import { Injectable } from "@angular/core";
import { BehaviorSubject, filter } from "rxjs";
import { BaseMessage, TauriService } from "./tauri.service";
import { UIService } from "./ui.service";

export interface ChatMessage extends BaseMessage {
    type: "chat";
    role: string;
    message: string;
    processingText?: string;
    synthetic?: boolean;
    tool_call_id?: string;
    actor_id?: string;
    actor_name?: string;
    avatar_id?: string;
    avatar_url?: string;
    display_name?: string;
    display_color?: string;
}

export interface ToolEvent {
    kind: 'tool';
    request: any[];
    results: any[];
    text?: string[];
}

export interface ToolProcessingEvent {
    kind: 'tool_processing';
    tool_call_id: string;
    name: string;
    content: any;
    text?: string;
}

export interface EventMessage extends BaseMessage {
    type: 'event';
    event: ToolEvent | ToolProcessingEvent;
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

    private readonly activeToolActionMessages = new Map<string, ChatMessage>();
    private readonly completedSyntheticActionMessages = new Set<string>();

    constructor(private tauriService: TauriService, private uiService: UIService) {
        // Subscribe to log messages from the TauriService
        this.tauriService.output$.pipe(
            filter((message): message is ChatMessage =>
                message.type === "chat"
            ),
        ).subscribe((chatMessage) => {
            if (chatMessage.type === "chat") {
                if (this.shouldSuppressCompletedSyntheticAction(chatMessage)) {
                    return;
                }
                this.chatMessageSubject.next(chatMessage);
                const currentLogs = this.chatHistorySubject.getValue();
                this.chatHistorySubject.next([...currentLogs, chatMessage]);
            }
        });

        this.tauriService.output$.pipe(
            filter((message): message is EventMessage =>
                message.type === "event" && ["tool", "tool_processing"].includes((message as any).event?.kind)
            ),
        ).subscribe((eventMessage) => {
            if (eventMessage.event.kind === "tool_processing") {
                this.handleToolProcessingEvent(eventMessage, eventMessage.event);
                return;
            }

            const toolEvent = eventMessage.event;
            this.handleFinalToolEvent(toolEvent);
            const webSearchRequestIndex = toolEvent.request.findIndex((r: any) => r.function?.name === 'web_search_agent');
            
            if (webSearchRequestIndex !== -1 && toolEvent.results[webSearchRequestIndex]) {
                this.searchResultSubject.next(toolEvent.results[webSearchRequestIndex]);
                this.uiService.showTab('search');
            }
        });
    }

    public clearChat(): void {
        this.chatHistorySubject.next([]);
        this.activeToolActionMessages.clear();
        this.completedSyntheticActionMessages.clear();
    }

    public getCurrentChat(): ChatMessage[] {
        return this.chatHistorySubject.getValue();
    }

    private handleToolProcessingEvent(eventMessage: EventMessage, event: ToolProcessingEvent): void {
        if (!['web_search_agent', 'generate_overlay_ui'].includes(event.name)) {
            return;
        }

        const content = event.content ?? {};
        const message = this.formatProcessingMessage(event.name, content);
        const processingText = this.formatToolProcessingText(content);
        const currentLogs = this.chatHistorySubject.getValue();
        const existing = this.activeToolActionMessages.get(event.tool_call_id);

        if (existing) {
            const updated: ChatMessage = {
                ...existing,
                message,
                processingText: processingText ?? existing.processingText,
            };
            this.activeToolActionMessages.set(event.tool_call_id, updated);
            this.chatHistorySubject.next(currentLogs.map((item) => item === existing ? updated : item));
            return;
        }

        const syntheticMessage: ChatMessage = {
            type: 'chat',
            timestamp: eventMessage.timestamp,
            index: eventMessage.index,
            role: 'action',
            message,
            processingText,
            synthetic: true,
            tool_call_id: event.tool_call_id,
        };

        this.activeToolActionMessages.set(event.tool_call_id, syntheticMessage);
        this.chatMessageSubject.next(syntheticMessage);
        this.chatHistorySubject.next([...currentLogs, syntheticMessage]);
    }

    private handleFinalToolEvent(event: ToolEvent): void {
        for (const result of event.results ?? []) {
            const toolCallId = result?.tool_call_id;
            if (!toolCallId) {
                continue;
            }
            const existing = this.activeToolActionMessages.get(toolCallId);
            if (!existing) {
                continue;
            }
            const updated: ChatMessage = { ...existing, processingText: undefined };
            this.activeToolActionMessages.delete(toolCallId);
            this.completedSyntheticActionMessages.add(existing.message);
            this.chatHistorySubject.next(this.chatHistorySubject.getValue().map((item) => item === existing ? updated : item));
        }
    }

    private formatToolProcessingText(content: any): string | undefined {
        if (typeof content?.internal_tool_name !== 'string') {
            return undefined;
        }
        const toolName = content.internal_tool_name;
        const status = typeof content?.status === 'string'
            ? content.status
            : 'processing';
        return `${toolName} ${status}`;
    }

    private formatProcessingMessage(actionName: string, content: any): string {
        if (actionName === 'generate_overlay_ui') {
            const instruction = typeof content?.instruction === 'string' && content.instruction.trim()
                ? content.instruction.trim()
                : 'overlay UI';
            return `Generating UI: ${instruction}`;
        }

        const query = typeof content?.query === 'string' && content.query.trim()
            ? content.query.trim()
            : 'web search';
        return `Searching: ${query}`;
    }

    private shouldSuppressCompletedSyntheticAction(chatMessage: ChatMessage): boolean {
        if (chatMessage.role !== 'action' || !this.completedSyntheticActionMessages.has(chatMessage.message)) {
            return false;
        }
        this.completedSyntheticActionMessages.delete(chatMessage.message);
        return true;
    }
}
