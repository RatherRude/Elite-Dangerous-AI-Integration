import {Injectable} from "@angular/core";
import {BaseMessage, TauriService} from "./tauri.service";
import {BehaviorSubject} from "rxjs";

interface UIMessage extends BaseMessage {
type: "ui",
    show: "chat" | "logbook" | string,
}

@Injectable({
    providedIn: "root",
})
export class UIService {
    private changeUISubject = new BehaviorSubject<UIMessage["show"] | null>(null);
    public changeUI$ = this.changeUISubject.asObservable();

    constructor(private tauriService: TauriService) {
        tauriService.output$.subscribe((message) => {
            if (message.type == 'ui') {
                const msg = message as UIMessage;
                this.changeUISubject.next(msg.show)
            }
        })
    }
}
