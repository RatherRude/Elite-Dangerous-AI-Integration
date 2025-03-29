import { Injectable } from "@angular/core";
import { BehaviorSubject, filter, map, Observable } from "rxjs";
import { BaseMessage, TauriService } from "./tauri.service";

export interface StatesMessage extends BaseMessage {
    type: "states";
    states: Record<string, any>;
}

@Injectable({
    providedIn: "root",
})
export class EventService {
    private eventSubject = new BehaviorSubject<StatesMessage | null>(null);
    public events$ = this.eventSubject.asObservable();

    constructor(private tauriService: TauriService) {
        // Subscribe to log messages from the TauriService
        this.tauriService.output$.pipe(
            filter((message): message is StatesMessage =>
                message.type === "states"
            ),
        ).subscribe((mesg) => {
            const currentLogs = this.eventSubject.getValue();
            this.eventSubject.next(mesg);
        });
    }

    public clearConversation(): void {
        this.eventSubject.next(null);
    }

    public getCurrentConversation(): StatesMessage | null {
        return this.eventSubject.getValue();
    }
}
