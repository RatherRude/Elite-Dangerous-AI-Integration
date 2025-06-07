import { Injectable } from "@angular/core";
import { BehaviorSubject, filter, map, Observable } from "rxjs";
import { BaseMessage, TauriService } from "./tauri.service";
import { EventMessage } from "./event.service.js";

export interface LogMessage extends BaseMessage {
    type: "log";
    prefix:
        | "debug"
        | "info"
        | "warn"
        | "error"
        | "event";
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
            filter((message): message is LogMessage | EventMessage =>
                message.type === "log" || message.type === "event"
            ),
            // Map to lowercase prefix for consistency
            map((message) => ("prefix" in message
                ? {
                    ...message,
                    prefix: message.prefix
                        .toLowerCase() as LogMessage["prefix"],
                }
                : message)
            ),
        ).subscribe((logMessage) => {
            const currentLogs = this.logsSubject.getValue();
            if (logMessage.type === "log") {
                this.logsSubject.next([...currentLogs, logMessage]);
            }
            if (logMessage.type === "event") {
                this.logsSubject.next([...currentLogs, {
                    type: "log",
                    prefix: "event",
                    timestamp: logMessage.timestamp,
                    message: JSON.stringify(logMessage.event),
                } as LogMessage]);
            }
        });
    }

    public clearLogs(): void {
        this.logsSubject.next([]);
    }

    public getCurrentLogs(): LogMessage[] {
        return this.logsSubject.getValue();
    }
}
