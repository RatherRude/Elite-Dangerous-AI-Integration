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
import { ChatService } from "../services/chat.service.js";
import { MatTabsModule } from "@angular/material/tabs";
import { ChatContainerComponent } from "../components/chat-container/chat-container.component.js";
import { ProjectionsService } from "../services/projections.service";
import { MetricsService } from "../services/metrics.service.js";
import { PolicyService } from "../services/policy.service.js";

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
        MatTabsModule,
        ChatContainerComponent,
    ],
    templateUrl: "./main-view.component.html",
    styleUrl: "./main-view.component.css",
})
export class MainViewComponent implements OnInit, OnDestroy {
    isLoading = true;
    isRunning = false;
    isInDanger = false;
    config: any;
    private configSubscription!: Subscription;
    private inDangerSubscription!: Subscription;
    private hasAutoStarted = false;
    public usageDisclaimerAccepted = false;

    constructor(
        private tauri: TauriService,
        private loggingService: LoggingService,
        private chatService: ChatService,
        private configService: ConfigService,
        private projectionsService: ProjectionsService,
        private metricsService: MetricsService,
        private policyService: PolicyService,
    ) {
        this.policyService.usageDisclaimerAccepted$.subscribe(
            (accepted) => {
                this.usageDisclaimerAccepted = accepted;
            },
        );
    }

    ngOnInit(): void {
        this.configSubscription = this.configService.config$.subscribe(
            (config) => {
                this.config = config;
                if (
                    this.config && this.config.cn_autostart &&
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

        // Subscribe to CurrentStatus projection and check for InDanger
        this.inDangerSubscription = this.projectionsService
            .getProjection("CurrentStatus")
            .subscribe((currentStatus) => {
                if (currentStatus && currentStatus.flags) {
                    this.isInDanger = Boolean(currentStatus.flags.InDanger);
                } else {
                    this.isInDanger = false;
                }
            });

        // Initialize the main view
        this.tauri.runExe();
        this.tauri.checkForUpdates();
    }

    ngOnDestroy(): void { // Implement ngOnDestroy
        if (this.configSubscription) {
            this.configSubscription.unsubscribe();
        }
        if (this.inDangerSubscription) {
            this.inDangerSubscription.unsubscribe();
        }
    }

    acceptUsageDisclaimer() {
        this.policyService.acceptUsageDisclaimer();
    }

    async start(): Promise<void> {
        try {
            if(this.config && this.config.characters[this.config.active_character_index] && this.config.characters[this.config.active_character_index]['avatar_show']) {
                this.createOverlay();
            }

            this.isLoading = true;
            this.loggingService.clearLogs(); // Clear logs when starting
            this.chatService.clearChat(); // Clear chat when starting
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
