// src/app/services/tauri.service.ts
import { Injectable, NgZone } from "@angular/core";
import { invoke } from "@tauri-apps/api/core";
import { listen, UnlistenFn } from "@tauri-apps/api/event";
import { BehaviorSubject, Observable, ReplaySubject } from "rxjs";

export interface BaseMessage {
    type: string;
    timestamp: string;
}

export interface UnknownMessage extends BaseMessage {
    type: "unknown";
    message: string;
}

@Injectable({
    providedIn: "root",
})
export class TauriService {
    private isRunningSubject = new BehaviorSubject<boolean>(false);
    public isRunning$ = this.isRunningSubject.asObservable();

    private isReadySubject = new BehaviorSubject<boolean>(false);
    public isReady$ = this.isReadySubject.asObservable();

    // ReplaySubject to expose the lines as an Observable
    private messagesSubject = new ReplaySubject<BaseMessage>();

    // Public observable for UI to subscribe
    public output$: Observable<BaseMessage> = this.messagesSubject
        .asObservable();

    // Flag to control the polling loop
    private stopListener?: UnlistenFn;

    constructor(private ngZone: NgZone) {
        this.runExe();
    }

    private async startReadingOutput(): Promise<void> {
        if (this.stopListener) this.stopListener();
        this.stopListener = await listen(
            "process-stdout",
            (e) => this.processStdout(e),
        );
    }

    private processStdout(event: any): void {
        this.ngZone.run(() => {
            console.log("Subprocess output:", event.payload);
            try {
                const message = JSON.parse(event.payload);
                if (message.type === "ready") {
                    console.log("Backend is ready");
                    this.isReadySubject.next(true);
                }
                this.messagesSubject.next(message);
            } catch (error) {
                console.warn("Error parsing message:", error);
            }
        });
    }

    // Clear the output list
    private clearOutput(): void {
        // todo clear the replay subject somehow
    }

    private async runExe(): Promise<string[]> {
        this.stopExe();
        try {
            const output: string[] = await invoke("start_process", {});
            this.startReadingOutput();
            return output;
        } catch (error) {
            console.error("Error running exe:", error);
            alert(
                `Error starting subprocess: ${
                    error instanceof Error ? error.message : error
                }`,
            );
            throw error;
        }
    }
    private async stopExe(): Promise<void> {
        try {
            this.isReadySubject.next(false);
            this.isRunningSubject.next(false);
            console.log("not running, not ready");
            await invoke("stop_process", {});
        } catch (error) {
            console.error("Error running exe:", error);
            throw error;
        }
    }
    public async restart_process(): Promise<void> {
        await this.stopExe();
        await this.runExe();
    }
    public async send_start_signal(): Promise<void> {
        await this.send_message({
            type: "start",
            timestamp: new Date().toISOString(),
        });
        this.isRunningSubject.next(true);
    }
    public async send_message(message: BaseMessage): Promise<void> {
        await invoke("send_json_line", {
            jsonLine: JSON.stringify(message) + "\n",
        });
    }
}
