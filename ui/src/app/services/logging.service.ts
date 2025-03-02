import { Injectable } from "@angular/core";
import { BehaviorSubject, filter, map, Observable } from "rxjs";
import { BaseMessage, TauriService } from "./tauri.service";

export interface LogMessage extends BaseMessage {
    type: "log";
    prefix:
        | "debug"
        | "info"
        | "warn"
        | "error"
        | "covas"
        | "event"
        | "cmdr"
        | "action";
    message: string;
}

@Injectable({
    providedIn: "root",
})
export class LoggingService {
    private logsSubject = new BehaviorSubject<LogMessage[]>([]);
    public logs$ = this.logsSubject.asObservable();

    constructor(private tauriService: TauriService) {
        // Subscribe to log messages from the TauriService
        this.tauriService.output$.pipe(
            filter((message): message is LogMessage => message.type === "log"),
            // Filter out debug messages
            filter((message) => message.prefix !== "debug"),
        ).subscribe((logMessage) => {
            const currentLogs = this.logsSubject.getValue();
            this.logsSubject.next([...currentLogs, logMessage]);
        });
    }

    public clearLogs(): void {
        this.logsSubject.next([]);
    }

    public getCurrentLogs(): LogMessage[] {
        return this.logsSubject.getValue();
    }
}
