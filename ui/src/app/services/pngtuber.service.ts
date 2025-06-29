import { Injectable } from "@angular/core";
import { BaseMessage, TauriService } from "./tauri.service";
import {BehaviorSubject} from "rxjs";
import {ChatMessage, ChatService} from "./chat.service";
import {EventService} from "./event.service";

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
    private actionSubject = new BehaviorSubject<"listening" | "thinking" | "speaking" | "acting">(
        "listening"
    )
    public action$ = this.actionSubject.asObservable();

    constructor(
        private tauriService: TauriService,
        private eventService: EventService
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
                    this.actionSubject.next('listening');
                }
                if (message.event.kind === 'assistant_acting') {
                    this.actionSubject.next('acting');
                }
            }
        )
    }

}
