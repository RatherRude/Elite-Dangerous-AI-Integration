// src/app/services/tauri.service.ts
import { Injectable, NgZone } from "@angular/core";
import { invoke } from "@tauri-apps/api/core";
import { listen, UnlistenFn } from "@tauri-apps/api/event";
import { BehaviorSubject, Observable, ReplaySubject } from "rxjs";

export interface BaseMessage {
    type: string;
    timestamp: string;
}

export interface SubmitInputMessage extends BaseMessage {
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
        this.startReadingOutput();
    }

    public async createOverlay(): Promise<void> {
        invoke("create_floating_overlay", {});
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
                if (message.type === "start") {
                    this.isRunningSubject.next(true);
                }
                if (message.type === "model_validation") {
                    this.isRunningSubject.next(false);
                }
                if (message.type === "config") {
                    this.isRunningSubject.next(false);
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

    public async runExe(): Promise<string[]> {
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
    }
    public async send_message(message: BaseMessage): Promise<void> {
        await invoke("send_json_line", {
            jsonLine: JSON.stringify(message) + "\n",
        });
    }

    // Update check functionality
    public async checkForUpdates(): Promise<void> {
        try {
            // Get the current commit hash from the Tauri app
            const currentCommit: string = await invoke("get_commit_hash");
            console.log("Current commit hash:", currentCommit);

            // Skip update check for development builds
            if (currentCommit === "development") {
                console.log("Development build, skipping update check");
                return;
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

                    if (releaseCommit !== currentCommit) {
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
        // Use the browser's confirm dialog for now
        // We'll replace this with a custom dialog component later
        const message = `
Update Available: ${releaseName}

A new version of COVAS:NEXT is available. Would you like to download it now?

Click OK to open the download page in your browser.
`;
        const result = confirm(message);

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
    }
}
