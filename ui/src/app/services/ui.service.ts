import {Injectable} from "@angular/core";
import {BaseMessage, TauriService} from "./tauri.service";
import {BehaviorSubject} from "rxjs";

export interface UIMessage extends BaseMessage {
    type: "ui",
    show?: string,
    submenu?: string,
    scroll?: "top" | "up" | "down" | "bottom",
}

type UIChange = Pick<UIMessage, "type" | "show" | "submenu" | "scroll">;

@Injectable({
    providedIn: "root",
})
export class UIService {
    private changeUISubject = new BehaviorSubject<UIChange | null>(null);
    public changeUI$ = this.changeUISubject.asObservable();

    constructor(private tauriService: TauriService) {
        tauriService.output$.subscribe((message) => {
            if (message.type == 'ui') {
                const msg = message as UIMessage;
                this.changeUISubject.next(msg)
            }
        })
    }

    public showTab(tabName: string) {
        this.changeUISubject.next({ type: "ui", show: tabName });
    }
}
