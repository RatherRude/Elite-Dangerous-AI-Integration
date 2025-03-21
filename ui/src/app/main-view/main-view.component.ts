import { Component, OnInit } from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressBarModule } from "@angular/material/progress-bar";
import { TauriService } from "../services/tauri.service";
import { LoggingService } from "../services/logging.service";
import { LogContainerComponent } from "../components/log-container/log-container.component";
import { SettingsMenuComponent } from "../components/settings-menu/settings-menu.component";
import { Router } from "@angular/router";
import { InputContainerComponent } from "../components/input-container/input-container.component";

@Component({
    selector: "app-main-view",
    standalone: true,
    imports: [
        CommonModule,
        MatButtonModule,
        MatIconModule,
        MatProgressBarModule,
        LogContainerComponent,
        SettingsMenuComponent,
        InputContainerComponent,
    ],
    templateUrl: "./main-view.component.html",
    styleUrl: "./main-view.component.css",
})
export class MainViewComponent implements OnInit {
    isLoading = true;
    isRunning = false;

    constructor(
        private tauri: TauriService,
        private loggingService: LoggingService,
        private router: Router,
    ) {}

    ngOnInit(): void {
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
