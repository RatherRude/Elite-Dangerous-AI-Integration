import { Injectable } from "@angular/core";
import { BaseMessage, TauriService } from "./tauri.service";
import {BehaviorSubject, filter} from "rxjs";
import {ChatMessage, ChatService} from "./chat.service";
import {EventService} from "./event.service";
import {CharacterService} from "./character.service";

interface OverlayVoiceMessage extends BaseMessage {
    type: "overlay_voice";
    character?: {
        name?: string;
        voice?: string;
        provider?: string;
    }
}

@Injectable({
    providedIn: "root",
})
export class PngTuberService {
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
    private speakingCharacterSubject = new BehaviorSubject<{ name: string; voice?: string } | null>(null);
    public speakingCharacter$ = this.speakingCharacterSubject.asObservable();

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
        this.tauriService.output$.pipe(
            filter((message): message is OverlayVoiceMessage => message.type === "overlay_voice")
        ).subscribe(message => {
            const name = message.character?.name?.trim();
            if (!name) {
                this.speakingCharacterSubject.next(null);
                return;
            }
            this.speakingCharacterSubject.next({
                name,
                voice: message.character?.voice,
            });
        });
        this.eventService.events$.subscribe(
            (messages)=> {
                const message = messages.at(-1)!;
                if (message.event.kind === 'user') {
                    this.actionSubject.next('thinking');
                }
                if (message.event.kind === 'user_speaking') {
                    this.actionSubject.next('listening');
                }
                if (message.event.kind === 'assistant') {
                    this.actionSubject.next('speaking');
                }
                if (message.event.kind === 'assistant_completed') {
                    this.actionSubject.next('idle');
                    this.speakingCharacterSubject.next(null);
                }
                if (message.event.kind === 'assistant_acting') {
                    this.actionSubject.next('acting');
                }
            }
        )
        this.chatService.chatHistory$.subscribe((chat)=>{
            const preview = chat.filter(value => ['covas', 'cmdr', 'action'].includes(value.role)).slice(-2)
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
