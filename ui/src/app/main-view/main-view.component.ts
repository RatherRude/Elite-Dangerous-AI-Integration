import { Component, OnDestroy, OnInit, NgZone } from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressBarModule } from "@angular/material/progress-bar";
import { MatDialog, MatDialogModule } from "@angular/material/dialog";
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
import { PluginManagerService } from "../services/plugin-manager.service";
import { PluginManagerDialogComponent, PluginManifest } from "../components/plugin-manager-dialog/plugin-manager-dialog.component";

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
    private installed_plugin_list_subscription!: Subscription;
    private hasAutoStarted = false;
    public usageDisclaimerAccepted = false;
    private installed_plugins_list: PluginManifest[] = []

    constructor(
        private tauri: TauriService,
        private loggingService: LoggingService,
        private chatService: ChatService,
        private configService: ConfigService,
        private projectionsService: ProjectionsService,
        private metricsService: MetricsService,
        private policyService: PolicyService,
        private plugin_manager_service: PluginManagerService,
        private ngZone: NgZone,
        private dialog: MatDialog,
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

        this.installed_plugin_list_subscription = this.plugin_manager_service.installed_plugin_list_message$.subscribe(
            (installed_plugins_list_message) => {
                this.installed_plugins_list = installed_plugins_list_message?.plugins || [];
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
        if (this.installed_plugin_list_subscription) {
            this.installed_plugin_list_subscription.unsubscribe();
        }
    }

    acceptUsageDisclaimer() {
        this.policyService.acceptUsageDisclaimer();
    }

    async start(): Promise<void> {
        try {
            if(this.config && this.config.pngtuber) {
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

    async manage_plugins(): Promise<void> {
        this.ngZone.run(() => {
            const dialogRef = this.dialog.open(PluginManagerDialogComponent, {
                data: { installed_plugins: this.installed_plugins_list },
            });

            dialogRef.afterClosed().subscribe((result) => {
                if (result !== false) {
                    this.send_new_plugin_list(result as PluginManifest[]).catch((err) => {
                        console.error("Failed to send plugin install/remove command", err);
                    });
                }
            });
        });
    }
    
    public async send_new_plugin_list(new_plugin_list: PluginManifest[]): Promise<void> {
        await this.tauri.send_command({
            type: "change_installed_plugins",
            plugins: new_plugin_list,
            timestamp: new Date().toISOString(),
        });
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
