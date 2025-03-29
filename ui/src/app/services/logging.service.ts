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
            filter((message): message is LogMessage | EventMessage =>
                message.type === "log" || message.type === "event"
            ),
            // Filter out debug messages
            filter((message) => message.prefix !== "debug"),
        ).subscribe((logMessage) => {
            if (logMessage.type === "log") {
                const currentLogs = this.logsSubject.getValue();
                this.logsSubject.next([...currentLogs, logMessage]);
            }
            if (logMessage.type === "event") {
                const currentLogs = this.logsSubject.getValue();
                if (logMessage.event.kind === "assistant") {
                    this.logsSubject.next([...currentLogs, {
                        type: "log",
                        prefix: "covas",
                        timestamp: logMessage.timestamp,
                        message: logMessage.event.content,
                    } as LogMessage]);
                }
                if (logMessage.event.kind === "user") {
                    this.logsSubject.next([...currentLogs, {
                        type: "log",
                        prefix: "cmdr",
                        timestamp: logMessage.timestamp,
                        message: logMessage.event.content,
                    } as LogMessage]);
                }
                if (logMessage.event.kind === "tool") {
                    this.logsSubject.next([...currentLogs, {
                        type: "log",
                        prefix: "action",
                        timestamp: logMessage.timestamp,
                        message: logMessage.event.text
                            ? logMessage.event.text.join(", ")
                            : logMessage.event.request.map((r) =>
                                r.function.name
                            ).join(", "),
                    } as LogMessage]);
                }
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
