// src/app/services/tauri.service.ts
import { Injectable, NgZone } from "@angular/core";
//import { invoke } from "@tauri-apps/api/core";
import { type UnlistenFn } from "@tauri-apps/api/event";
import { BehaviorSubject, Observable, ReplaySubject } from "rxjs";
import { MatDialog } from "@angular/material/dialog";
import { UpdateDialogComponent } from "../components/update-dialog/update-dialog.component";
import { environment } from "../../environments/environment";

declare global {
    interface Window {
        electronAPI: {
            invoke: (call: string, opts?: any) => Promise<any>;
            onStdout: (callback: (value: any) => void) => Promise<void> | void;
            onStderr: (callback: (value: any) => void) => Promise<void> | void;
            onWindowClose: (callback: (event: Event) => void) => void;
            confirmWindowClose: () => Promise<void>;
        };
    }
}
const electronAPI = window.electronAPI;

export interface BaseCommand {
    type: string;
    timestamp: string;
    [key: string]: any;
}

export interface BaseMessage {
    type: string;
    timestamp: string;
    index: number;
    [key: string]: any;
}

export interface SubmitInputMessage extends BaseCommand {
    type: "submit_input";
    input: string;
}

export interface UnknownMessage extends BaseMessage {
    type: "unknown";
    message: string;
}

@Injectable({
    providedIn: "root",
})
export class TauriService {
    public readonly installId = window.localStorage.getItem(
        "install_id",
    ) ||
        `${Date.now().toString()}-${
            Math.random().toString(36).substring(2, 15)
        }`;
    public readonly sessionId = `${Date.now().toString()}-${
        Math.random().toString(36).substring(2, 15)
    }`;
    public readonly commitHash = environment.COMMIT_HASH;
    public readonly windowCloseCallbacks = [] as ((event: Event) => void)[];
    private runModeSubject = new BehaviorSubject<
        "starting" | "configuring" | "running"
    >(
        "starting",
    );
    public runMode$ = this.runModeSubject.asObservable();

    // ReplaySubject to expose the lines as an Observable
    private messagesSubject = new ReplaySubject<BaseMessage>(100);

    // Public observable for UI to subscribe
    public output$: Observable<BaseMessage> = this.messagesSubject
        .asObservable();

    // Flag to control the polling loop
    private stopListener?: UnlistenFn;
    private stopStderrListener?: UnlistenFn;

    private currentIndex = 0;

    constructor(private ngZone: NgZone, private dialog: MatDialog) {
        this.startReadingOutput();
        window.localStorage.setItem("install_id", this.installId);

        electronAPI.onWindowClose((event) => this.onWindowClose(event));
    }

    public async createOverlay(config: {fullscreen: boolean, maximized: boolean, alwaysOnTop: boolean}): Promise<void> {
        electronAPI.invoke("create_floating_overlay", config);
    }

    public async destroyOverlay(): Promise<void> {
        electronAPI.invoke("destroy_floating_overlay", {});
    }

    private async startReadingOutput(): Promise<void> {
        if (this.stopListener) this.stopListener();
        await electronAPI.onStdout(
            (e) => this.processStdout(e),
        );
        if (this.stopStderrListener) this.stopStderrListener();
        await electronAPI.onStderr(
            (e) => this.processStderr(e),
        );
    }

    private processStdout(event: any): void {
        this.ngZone.run(() => {
            console.log("Subprocess output:", event.payload);
            try {
                const message = JSON.parse(event.payload);
                if (message.type === "ready") {
                    console.log("Backend is ready");
                    this.runModeSubject.next("configuring");
                }
                if (message.type === "start") {
                    this.runModeSubject.next("running");
                }
                if (message.type === "model_validation") {
                    this.runModeSubject.next("configuring");
                }
                if (message.type === "config") {
                    this.runModeSubject.next("configuring");
                }
                this.messagesSubject.next({
                    ...message,
                    index: this.currentIndex++,
                });
            } catch (error) {
                console.warn("Error parsing message:", error);
            }
        });
    }

    private processStderr(event: any): void {
        this.ngZone.run(() => {
            this.messagesSubject.next({
                type: "log",
                timestamp: new Date().toISOString(),
                message: event.payload,
                prefix: "error",
                index: this.currentIndex++,
            });
        });
    }

    // Clear the output list
    private clearOutput(): void {
        // todo clear the replay subject somehow
    }

    public async runExe(): Promise<string[]> {
        this.stopExe();
        try {
            const output: string[] = await electronAPI.invoke("start_process", {});
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
            this.runModeSubject.next("starting");
            console.log("process stopping...");
            await electronAPI.invoke("stop_process", {});
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
        await this.send_command({
            type: "start",
            timestamp: new Date().toISOString(),
            index: this.currentIndex++,
        });
    }
    public async send_command(message: BaseCommand): Promise<void> {
        await electronAPI.invoke("send_json_line", {
            jsonLine: JSON.stringify(message) + "\n",
        });
    }

    // Update check functionality
    public async checkForUpdates(): Promise<void> {
        try {
            // Get the current commit hash from the Tauri app
            console.log("Commit hash:", this.commitHash);

            // Skip update check for development builds
            if (this.commitHash === "development") {
                console.log("Development build, skipping update check");
                return;
            }

            if (this.commitHash === "__COMMIT_HASH_PLACEHOLDER__") {
                throw new Error(
                    "__COMMIT_HASH_PLACEHOLDER__ placeholder not correctly resolved. Please check your build configuration.",
                );
            }

            // Check for updates from GitHub API
            console.log("Checking for updates...");
            const response = await fetch(
                "https://api.github.com/repos/RatherRude/Elite-Dangerous-AI-Integration/releases",
            );

            if (response.ok) {
                const releaseData = await response.json();
                const tagName = releaseData[0].tag_name;
                const releaseUrl = releaseData[0].html_url;
                const releaseName = releaseData[0].name;
                console.log(
                    "Latest release:",
                    releaseName,
                    "with tag:",
                    tagName,
                );

                // Get the commit id for the release tag
                const tagResponse = await fetch(
                    `https://api.github.com/repos/RatherRude/Elite-Dangerous-AI-Integration/git/ref/tags/${tagName}`,
                );

                if (tagResponse.ok) {
                    const tagData = await tagResponse.json();
                    const releaseCommit = tagData.object.sha;
                    console.log("Release commit hash:", releaseCommit);

                    if (
                        releaseCommit !== this.commitHash
                    ) {
                        console.log("Update available, showing prompt");
                        this.askForUpdate(releaseName, releaseUrl);
                    } else {
                        console.log("Application is up to date");
                    }
                }
            }
        } catch (error) {
            console.error("Error checking for updates:", error);
        }
    }

    private askForUpdate(
        releaseName: string = "A new release",
        releaseUrl: string =
            "https://github.com/RatherRude/Elite-Dangerous-AI-Integration/releases/",
    ): void {
        this.ngZone.run(() => {
            const dialogRef = this.dialog.open(UpdateDialogComponent, {
                width: "400px",
                data: { releaseName, releaseUrl },
            });

            dialogRef.afterClosed().subscribe((result) => {
                if (result) {
                    // Open the release URL in a new browser window/tab
                    const a = document.createElement("a");
                    a.setAttribute("href", releaseUrl);
                    a.setAttribute("target", "_blank");
                    a.setAttribute("rel", "noopener noreferrer");
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                }
            });
        });
    }

    async onWindowClose(event: Event): Promise<void> {
        console.log('Window close requested, running callbacks');
        //event.preventDefault();
        // Promise all windowCloseCallbacks
        await Promise.all(this.windowCloseCallbacks.map(callback => callback(event)));
        // confirm close to electron
        await electronAPI.confirmWindowClose();
    }
}
