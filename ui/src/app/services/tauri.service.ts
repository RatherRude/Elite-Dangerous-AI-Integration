// src/app/services/tauri.service.ts
import { Injectable, NgZone } from "@angular/core";
//import { invoke } from "@tauri-apps/api/core";
import { type UnlistenFn } from "@tauri-apps/api/event";
import { MatSnackBar } from "@angular/material/snack-bar";
import { BehaviorSubject, Observable, ReplaySubject } from "rxjs";
import { MatDialog } from "@angular/material/dialog";
import { UpdateDialogComponent } from "../components/update-dialog/update-dialog.component";
import { environment } from "../../environments/environment";
import { ScreenInfo } from "../models/screen-info";

declare global {
    interface Window {
        electronAPI?: {
            invoke: (call: string, opts?: any) => Promise<any>;
            onStdout: (callback: (value: any) => void) => Promise<void> | void;
            onStderr: (callback: (value: any) => void) => Promise<void> | void;
            onBackendLifecycle: (callback: (value: any) => void) => Promise<void> | void;
            onWindowClose: (callback: (event: Event) => void) => void;
            confirmWindowClose: () => Promise<void>;
            userAssets?: {
                writeFile?: (opts: any) => Promise<any>;
                readFile?: (opts: any) => Promise<any>;
                listFiles?: () => Promise<any>;
                deleteFile?: (opts: any) => Promise<any>;
            };
        };
    }
}

type TransportCallback = (value: any) => void;

interface BackendTransport {
    readonly isRemote: boolean;
    invoke(call: string, opts?: any): Promise<any>;
    onStdout(callback: TransportCallback): Promise<void> | void;
    onStderr(callback: TransportCallback): Promise<void> | void;
    onBackendLifecycle(callback: TransportCallback): Promise<void> | void;
}

class ElectronBackendTransport implements BackendTransport {
    readonly isRemote = false;

    constructor(private electronAPI: NonNullable<Window["electronAPI"]>) {}

    invoke(call: string, opts?: any): Promise<any> {
        return this.electronAPI.invoke(call, opts);
    }

    onStdout(callback: TransportCallback): Promise<void> | void {
        return this.electronAPI.onStdout(callback);
    }

    onStderr(callback: TransportCallback): Promise<void> | void {
        return this.electronAPI.onStderr(callback);
    }

    onBackendLifecycle(callback: TransportCallback): Promise<void> | void {
        return this.electronAPI.onBackendLifecycle(callback);
    }
}

class WebSocketBackendTransport implements BackendTransport {
    readonly isRemote = true;
    private socket: WebSocket;
    private nextRequestId = 1;
    private stdoutCallback: TransportCallback | null = null;
    private stderrCallback: TransportCallback | null = null;
    private backendLifecycleCallback: TransportCallback | null = null;
    private pending = new Map<number, { resolve: (value: any) => void; reject: (reason?: any) => void }>();
    private connected: Promise<void>;

    constructor() {
        const protocol = window.location.protocol === "https:" ? "wss" : "ws";
        const wsUrl = `${protocol}://${window.location.host}/ws`;
        this.socket = new WebSocket(wsUrl);
        this.connected = new Promise((resolve, reject) => {
            this.socket.addEventListener("open", () => resolve(), { once: true });
            this.socket.addEventListener("error", () => reject(new Error(`Failed to connect to ${wsUrl}`)), { once: true });
        });
        this.socket.addEventListener("message", (event) => this.handleMessage(event));
        this.socket.addEventListener("close", () => this.rejectPending("Remote backend connection closed"));
    }

    async invoke(call: string, opts?: any): Promise<any> {
        if (call !== "send_json_line") {
            throw new Error(`Remote transport does not support ${call}`);
        }

        await this.connected;
        const id = this.nextRequestId++;
        const result = new Promise((resolve, reject) => {
            this.pending.set(id, { resolve, reject });
        });
        this.socket.send(JSON.stringify({ id, call, opts }));
        return result;
    }

    onStdout(callback: TransportCallback): void {
        this.stdoutCallback = callback;
    }

    onStderr(callback: TransportCallback): void {
        this.stderrCallback = callback;
    }

    onBackendLifecycle(callback: TransportCallback): void {
        this.backendLifecycleCallback = callback;
    }

    private handleMessage(event: MessageEvent): void {
        let message: any;
        try {
            message = JSON.parse(event.data);
        } catch (error) {
            console.warn("Invalid remote backend message:", error, event.data);
            return;
        }

        if (typeof message.id === "number") {
            const pending = this.pending.get(message.id);
            if (!pending) {
                return;
            }
            this.pending.delete(message.id);
            if (message.error) {
                pending.reject(new Error(message.error));
            } else {
                pending.resolve(message.result);
            }
            return;
        }

        switch (message.channel) {
            case "stdout":
                this.stdoutCallback?.(message.payload);
                break;
            case "stderr":
                this.stderrCallback?.(message.payload);
                break;
            case "backend-lifecycle":
                this.backendLifecycleCallback?.(message.payload);
                break;
        }
    }

    private rejectPending(reason: string): void {
        for (const pending of this.pending.values()) {
            pending.reject(new Error(reason));
        }
        this.pending.clear();
    }
}

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

type OutboundMessage = {
    type: string;
    timestamp: string;
    [key: string]: any;
};

export interface StartupErrorMessage extends BaseMessage {
    type: "startup_error";
    phase: string;
    message: string;
    details?: string;
}

export interface BackendLifecycleMessage extends BaseMessage {
    type: "backend_process_state";
    status: "exited" | "error";
    expected: boolean;
    pid: number | null;
    code?: number | null;
    signal?: string | null;
    message?: string;
}

export interface OverlayCreateOptions {
    alwaysOnTop: boolean;
    screenId?: number;
    mode?: "disabled" | "desktop" | "vr" | "both";
    vrSizeMeters?: number;
    vrAnchor?: "head" | "world";
    vrHorizontalOffset?: number;
    vrVerticalOffset?: number;
    vrDistanceOffset?: number;
    vrTiltDegrees?: number;
    vrCurvature?: number;
}

export interface OverlayRuntimeInfo {
    platform: string;
    probeMode: string;
    openxrAvailable: boolean;
    openxrOverlayExtensionAvailable: boolean;
    openvrAvailable: boolean;
    openvrRuntimeInstalled: boolean;
    openvrRuntimePath: string;
    selectedBackend: "none" | "openxr" | "openvr" | "mock";
    packageInstalled: boolean;
    available: boolean;
    hasRealVRRuntime: boolean;
    error?: string;
}

export interface AccessibilityPermissionResult {
    supported: boolean;
    granted: boolean;
    prompted: boolean;
    openedSettings: boolean;
}

export interface AccessibilitySettingsResult {
    supported: boolean;
    opened: boolean;
}

export interface SubmitInputMessage extends BaseCommand {
    type: "submit_input";
    input: string;
}

export interface QueryMemoriesMessage extends BaseCommand {
    type: "query_memories";
    query: string;
    top_k?: number;
}

export interface GetMemoriesByDateMessage extends BaseCommand {
    type: "get_memories_by_date";
    date: string; // YYYY-MM-DD format
}

export interface GetAvailableDatesMessage extends BaseCommand {
    type: "get_available_dates";
}

export interface GetSystemEventsMessage extends BaseCommand {
    type: "get_system_events";
    system_address: number | string;
}

export interface GetQuestsMessage extends BaseCommand {
    type: "get_quests";
}

export interface GetModelUsageHistoryMessage extends BaseCommand {
    type: "get_model_usage_history";
    usage_kind?: string;
    from?: string;
    to?: string;
    limit?: number;
    offset?: number;
}

export interface SystemEventsMessage extends BaseMessage {
    type: "system_events";
    system_address: number | string | null;
    data: any;
}

export interface QuestsMessage extends BaseMessage {
    type: "quests";
    data: any;
}

export interface ModelUsageHistoryMessage extends BaseMessage {
    type: "model_usage_history";
    data: any;
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
        "starting" | "configuring" | "running" | "error"
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
    private startupErrorPendingExit = false;
    private restartTimer: number | null = null;
    private transport: BackendTransport;

    constructor(
        private ngZone: NgZone,
        private dialog: MatDialog,
        private snackBar: MatSnackBar,
    ) {
        this.transport = window.electronAPI
            ? new ElectronBackendTransport(window.electronAPI)
            : new WebSocketBackendTransport();
        this.startReadingOutput();
        window.localStorage.setItem("install_id", this.installId);

        window.electronAPI?.onWindowClose((event) => this.onWindowClose(event));

    }

    public async createOverlay(config: OverlayCreateOptions): Promise<void> {
        const result = await window.electronAPI?.invoke("create_floating_overlay", config);
        return result;
    }

    public async destroyOverlay(): Promise<void> {
        await window.electronAPI?.invoke("destroy_floating_overlay", {});
    }

    public async getAvailableScreens(): Promise<ScreenInfo[]> {
        if (!window.electronAPI) {
            throw new Error('electronAPI not available');
        }
        const result = await window.electronAPI.invoke('get_available_screens');
        return result as ScreenInfo[];
    }

    public async getOverlayRuntimeInfo(): Promise<OverlayRuntimeInfo> {
        if (!window.electronAPI) {
            throw new Error('electronAPI not available');
        }
        const result = await window.electronAPI.invoke('get_overlay_runtime_info');
        return result as OverlayRuntimeInfo;
    }

    public async requestAccessibilityPermission(): Promise<AccessibilityPermissionResult> {
        if (!window.electronAPI) {
            throw new Error('electronAPI not available');
        }
        const result = await window.electronAPI.invoke('request_accessibility_permission');
        return result as AccessibilityPermissionResult;
    }

    public async openAccessibilitySettings(): Promise<AccessibilitySettingsResult> {
        if (!window.electronAPI) {
            throw new Error('electronAPI not available');
        }
        const result = await window.electronAPI.invoke('open_accessibility_settings');
        return result as AccessibilitySettingsResult;
    }

    private async startReadingOutput(): Promise<void> {
        if (this.stopListener) this.stopListener();
        await this.transport.onStdout(
            (e) => this.processStdout(e),
        );
        if (this.stopStderrListener) this.stopStderrListener();
        await this.transport.onStderr(
            (e) => this.processStderr(e),
        );
        await this.transport.onBackendLifecycle(
            (e) => this.processBackendLifecycle(e),
        );
        if (this.transport.isRemote) {
            await this.requestRemoteRuntimeState();
        }
    }

    private async requestRemoteRuntimeState(): Promise<void> {
        await this.transport.invoke("send_json_line", {
            jsonLine: JSON.stringify({
                type: "init_overlay",
                timestamp: new Date().toISOString(),
                index: this.currentIndex++,
            }) + "\n",
        });
    }

    private pushMessage(message: OutboundMessage): void {
        const nextMessage: BaseMessage = {
            ...message,
            index: this.currentIndex++,
        };
        this.messagesSubject.next(nextMessage);
    }

    private pushLog(message: string, prefix: "debug" | "info" | "warn" | "error" = "error"): void {
        this.pushMessage({
            type: "log",
            timestamp: new Date().toISOString(),
            message,
            prefix,
        });
    }

    private isOverlayWindow(): boolean {
        return window.location.hash.startsWith("#/overlay");
    }

    private showErrorToast(message: string): void {
        if (this.isOverlayWindow()) {
            return;
        }
        this.snackBar.open(message, "Dismiss", {
            duration: 15000,
            panelClass: ["validation-error-snackbar"],
        });
    }

    private scheduleBackendRestart(): void {
        if (this.isOverlayWindow() || this.restartTimer !== null) {
            return;
        }

        this.runModeSubject.next("starting");
        this.restartTimer = window.setTimeout(async () => {
            this.restartTimer = null;
            try {
                await this.runExe();
            } catch (error) {
                console.error("Scheduled backend restart failed:", error);
            }
        }, 3000);
    }

    private handleStartupError(message: StartupErrorMessage): void {
        const currentMode = this.runModeSubject.getValue();
        const shouldStayInConfig = currentMode === "starting" || currentMode === "configuring";

        if (!shouldStayInConfig) {
            this.runModeSubject.next("error");
        }
        this.startupErrorPendingExit = true;

        const phase = message.phase || "startup";
        const summary = message.message?.trim() || "Unknown startup error";
        const details = message.details?.trim();
        const detailLine = details
            ?.split("\n")
            .map((line) => line.trim())
            .filter(Boolean)
            .at(-1);

        this.pushLog(`Assistant startup failed during ${phase}: ${summary}`);
        if (details && details !== summary) {
            this.pushLog(details);
        }

        if (!shouldStayInConfig) {
            this.pushMessage({
                type: "chat",
                timestamp: message.timestamp || new Date().toISOString(),
                role: "error",
                message: `Assistant startup failed during ${phase}: ${detailLine || summary}`,
                show_in_overlay: false,
            });
        }
    }

    private processStdout(event: any): void {
        this.ngZone.run(() => {
            // console.log("Subprocess output:", event.payload);
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
                if (message.type === "startup_error") {
                    this.handleStartupError(message as StartupErrorMessage);
                }
                this.pushMessage(message);
            } catch (error) {
                console.warn("Error parsing message:", error, event);
            }
        });
    }

    private processBackendLifecycle(event: any): void {
        this.ngZone.run(() => {
            const payload = event?.payload ?? {};
            const previousMode = this.runModeSubject.getValue();
            const message: BackendLifecycleMessage = {
                type: "backend_process_state",
                timestamp: payload.timestamp || new Date().toISOString(),
                status: payload.status === "error" ? "error" : "exited",
                expected: Boolean(payload.expected),
                pid: typeof payload.pid === "number" ? payload.pid : null,
                code: payload.code ?? null,
                signal: payload.signal ?? null,
                message: typeof payload.message === "string" ? payload.message : undefined,
                index: this.currentIndex,
            };

            this.pushMessage(message);

            if (message.expected) {
                this.startupErrorPendingExit = false;
                return;
            }

            const exitedDuringConfig = previousMode === "starting" || previousMode === "configuring";
            if (this.startupErrorPendingExit) {
                this.startupErrorPendingExit = false;
                if (!exitedDuringConfig) {
                    return;
                }
            }

            const shouldToast = exitedDuringConfig;

            if (exitedDuringConfig) {
                this.scheduleBackendRestart();
            } else {
                this.runModeSubject.next("error");
            }

            if (message.status === "error") {
                const details = message.message || "Unknown backend error";
                this.pushLog(`Assistant process failed to start: ${details}`);
                if (shouldToast) {
                    this.showErrorToast(`Assistant process failed to start: ${details}`);
                }
                return;
            }

            const exitDetails = [
                message.code !== null && message.code !== undefined ? `code ${message.code}` : null,
                message.signal ? `signal ${message.signal}` : null,
            ].filter(Boolean).join(", ");
            const exitMessage = exitDetails
                ? `Assistant process exited unexpectedly (${exitDetails}).`
                : "Assistant process exited unexpectedly.";

            this.pushLog(exitMessage);
            if (shouldToast) {
                this.showErrorToast(exitMessage);
            }
        });
    }

    private processStderr(event: any): void {
        this.ngZone.run(() => {
            this.pushMessage({
                type: "log",
                timestamp: new Date().toISOString(),
                message: event.payload,
                prefix: "error",
            });
        });
    }

    // Clear the output list
    private clearOutput(): void {
        // todo clear the replay subject somehow
    }

    public async runExe(): Promise<string[]> {
        if (this.transport.isRemote) {
            return [];
        }
        await this.stopExe();
        try {
            const output: string[] = await this.transport.invoke("start_process", {});
            this.startReadingOutput();
            return output;
        } catch (error) {
            console.error("Error running exe:", error);
            this.runModeSubject.next("error");
            this.showErrorToast(
                `Error starting subprocess: ${
                    error instanceof Error ? error.message : error
                }`,
            );
            throw error;
        }
    }
    private async stopExe(): Promise<void> {
        if (this.transport.isRemote) {
            return;
        }
        try {
            this.runModeSubject.next("starting");
            console.log("process stopping...");
            await this.transport.invoke("stop_process", {});
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
        if (this.runModeSubject.getValue() === "error") {
            await this.runExe();
        }
        await this.send_command({
            type: "start",
            timestamp: new Date().toISOString(),
            index: this.currentIndex++,
        });
    }
    public async send_command(message: BaseCommand): Promise<void> {
        await this.transport.invoke("send_json_line", {
            jsonLine: JSON.stringify(message) + "\n",
        });
    }
    public async enable_remote_tracing(resourceAttributes: Record<string, string>): Promise<void> {
        this.send_command({
            type: "enable_remote_tracing",
            resourceAttributes,
            timestamp: new Date().toISOString(),
            index: this.currentIndex++,
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
        await window.electronAPI?.confirmWindowClose();
    }
}
