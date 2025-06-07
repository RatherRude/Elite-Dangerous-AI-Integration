import { Component, OnDestroy, OnInit } from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressBarModule } from "@angular/material/progress-bar";
import { MatDialogModule } from "@angular/material/dialog";
import { TauriService } from "../services/tauri.service";
import { LoggingService } from "../services/logging.service";
import { LogContainerComponent } from "../components/log-container/log-container.component";
import { SettingsMenuComponent } from "../components/settings-menu/settings-menu.component";
import { Router } from "@angular/router";
import { InputContainerComponent } from "../components/input-container/input-container.component";
import { ConfigService } from "../services/config.service";
import { Subscription } from "rxjs";

@Component({
    selector: "app-main-view",
    standalone: true,
    imports: [
        CommonModule,
        MatButtonModule,
        MatIconModule,
        MatProgressBarModule,
        MatDialogModule,
        LogContainerComponent,
        SettingsMenuComponent,
        InputContainerComponent,
    ],
    templateUrl: "./main-view.component.html",
    styleUrl: "./main-view.component.css",
})
export class MainViewComponent implements OnInit, OnDestroy {
    isLoading = true;
    isRunning = false;
    config: any;
    private configSubscription!: Subscription;
    private hasAutoStarted = false;

    constructor(
        private readonly tauri: TauriService,
        private readonly loggingService: LoggingService,
        private readonly router: Router,
        private readonly configService: ConfigService,
    ) {}

    ngOnInit(): void {
        this.configSubscription = this.configService.config$.subscribe(
            (config) => {
                this.config = config;
                if (
                    this.config?.cn_autostart &&
                    !this.isRunning && !this.hasAutoStarted
                ) {
                    console.log("Started automatically.");
                    this.start();
                    this.hasAutoStarted = true;
                }
            },
        );
        // Subscribe to the running state
        this.tauri.runMode$.subscribe(
            (mode) => {
                this.isRunning = mode === "running";
                this.isLoading = mode === "starting";
            },
        );
        // Initialize the main view
        this.tauri.runExe();
        this.tauri.checkForUpdates();
    }

    ngOnDestroy(): void { // Implement ngOnDestroy
        if (this.configSubscription) {
            this.configSubscription.unsubscribe();
        }
    }

    async start(): Promise<void> {
        try {
            this.isLoading = true;
            this.loggingService.clearLogs(); // Clear logs when starting
            await this.tauri.send_start_signal();
        } catch (error) {
            console.error("Failed to start:", error);
        }
    }

    async stop(): Promise<void> {
        try {
            this.isLoading = true;
            await this.tauri.restart_process();
        } catch (error) {
            console.error("Failed to stop:", error);
        }
    }

    async createOverlay(): Promise<void> {
        try {
            await this.tauri.createOverlay();
        } catch (error) {
            console.error("Failed to create overlay:", error);
        }
    }
}
