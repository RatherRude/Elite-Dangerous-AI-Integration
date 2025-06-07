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
    private readonly logsSubject = new BehaviorSubject<LogMessage[]>([]);
    public logs$ = this.logsSubject.asObservable();

    constructor(private readonly tauriService: TauriService) {
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
                if (logMessage.event.kind === "assistant_completed") {
                    return;
                } else if (logMessage.event.kind === "assistant") {
                    this.logsSubject.next([...currentLogs, {
                        type: "log",
                        prefix: "covas",
                        timestamp: logMessage.timestamp,
                        message: logMessage.event.content,
                    } as LogMessage]);
                } else if (logMessage.event.kind === "user") {
                    this.logsSubject.next([...currentLogs, {
                        type: "log",
                        prefix: "cmdr",
                        timestamp: logMessage.timestamp,
                        message: logMessage.event.content,
                    } as LogMessage]);
                } else if (logMessage.event.kind === "tool") {
                    this.logsSubject.next([...currentLogs, {
                        type: "log",
                        prefix: "action",
                        timestamp: logMessage.timestamp,
                        message: logMessage.event.text
                            ? logMessage.event.text.join(", ")
                            : logMessage.event.results.map((r) =>
                                r.name + ": " + r.content
                            ).join(", "),
                    } as LogMessage]);
                } else if (logMessage.event.kind === "status") {
                    if (logMessage.event.status.event === "Status") return;
                    this.logsSubject.next([...currentLogs, {
                        type: "log",
                        prefix: "event",
                        timestamp: logMessage.timestamp,
                        message: logMessage.event.status.event,
                    } as LogMessage]);
                } else {
                    this.logsSubject.next([...currentLogs, {
                        type: "log",
                        prefix: "event",
                        timestamp: logMessage.timestamp,
                        message: logMessage.event.content.event,
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
