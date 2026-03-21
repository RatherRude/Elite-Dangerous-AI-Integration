import { Injectable } from "@angular/core";
import { BaseMessage, TauriService } from "./tauri.service";
import {BehaviorSubject} from "rxjs";
import {ChatMessage, ChatService} from "./chat.service";
import {EventMessage, EventService} from "./event.service";
import {CharacterService} from "./character.service";

@Injectable({
    providedIn: "root",
})
export class PngTuberService {
    private transitionAction(
        current: "idle" | "listening" | "thinking" | "speaking" | "acting",
        message: EventMessage,
    ): "idle" | "listening" | "thinking" | "speaking" | "acting" {
        switch (message.event.kind) {
            case "user_speaking":
                return "listening";
            case "user":
                return "thinking";
            case "assistant_speaking":
                return "speaking";
            case "assistant_acting":
                return "acting";
            case "assistant_completed":
                return current === "listening" ? "listening" : "idle";
            case "quest":
                if (["play_sound", "npc_message"].includes(message.event.content?.action ?? "")) {
                    return "speaking";
                }
                return current;
            default:
                return current;
        }
    }

    private runModeSubject = new BehaviorSubject<
        "starting" | "configuring" | "running"
    >(
        "starting",
    );
    public runMode$ = this.runModeSubject.asObservable();
    private actionSubject = new BehaviorSubject<"idle" | "listening" | "thinking" | "speaking" | "acting">(
        "idle"
    )
    public action$ = this.actionSubject.asObservable();
    
    // Add avatar tracking
    private avatarIdSubject = new BehaviorSubject<string | null>(null);
    public avatarId$ = this.avatarIdSubject.asObservable();

    private chatPreviewSubject = new BehaviorSubject<ChatMessage[]>([])
    public chatPreview$ = this.chatPreviewSubject.asObservable()

    constructor(
        private tauriService: TauriService,
        private eventService: EventService,
        private chatService: ChatService,
        private characterService: CharacterService
    ) {
        this.tauriService.output$.pipe().subscribe(
            (message: BaseMessage) => {
                if (message.type === "ready") {
                    this.runModeSubject.next('configuring')
                }
                if (message.type === "start") {
                    this.runModeSubject.next('running')
                }
            },
        );
        this.eventService.events$.subscribe(
            (messages)=> {
                const message = messages.at(-1);
                if (!message) {
                    return;
                }

                const current = this.actionSubject.getValue();
                this.actionSubject.next(this.transitionAction(current, message));
            }
        )
        this.chatService.chatHistory$.subscribe((chat)=>{
            const preview = chat.filter(value => ['covas', 'cmdr', 'action', 'npc_message'].includes(value.role)).slice(-2)
            this.chatPreviewSubject.next(preview)
        })
        this.chatService.chatMessage$.subscribe((msg)=>{
            if(msg?.role==='error') {
                this.actionSubject.next('idle')
            }
        })
        
        // Subscribe to character changes to track avatar
        this.characterService.character$.subscribe(character => {
            this.avatarIdSubject.next(character?.avatar || null);
        });
        
        // Get initial character state immediately
        const currentCharacter = this.characterService.getCurrentCharacter();
        if (currentCharacter) {
            this.avatarIdSubject.next(currentCharacter.avatar || null);
        }
    }

}
