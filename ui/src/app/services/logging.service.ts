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

    public getLogColor(prefix: string): string {
        switch (prefix) {
            case "error":
                return "red";
            case "warn":
                return "orange";
            case "info":
                return "#9C27B0";
            case "covas":
                return "#2196F3";
            case "event":
                return "#4CAF50";
            case "cmdr":
                return "#E91E63";
            case "action":
                return "#FF9800";
            default:
                return "inherit";
        }
    }
}
