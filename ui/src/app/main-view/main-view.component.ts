import { Component, OnDestroy, OnInit, ViewChild } from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressBarModule } from "@angular/material/progress-bar";
import { MatDialogModule } from "@angular/material/dialog";
import { TauriService } from "../services/tauri.service";
import { LoggingService } from "../services/logging.service";
import { LogContainerComponent } from "../components/log-container/log-container.component";
import { SettingsMenuComponent } from "../components/settings-menu/settings-menu.component";
import { InputContainerComponent } from "../components/input-container/input-container.component";
import {Config, ConfigService} from "../services/config.service";
import { Subscription } from "rxjs";
import { ChatService } from "../services/chat.service.js";
import { MatTabsModule } from "@angular/material/tabs";
import { ChatContainerComponent } from "../components/chat-container/chat-container.component.js";
import { StatusContainerComponent } from "../components/status-container/status-container.component";
import { StorageContainerComponent } from "../components/storage-container/storage-container.component";
import { StationContainerComponent } from "../components/station-container/station-container.component";
import { TasksContainerComponent } from "../components/tasks-container/tasks-container.component";
import { ProjectionsService } from "../services/projections.service";
import { MemoriesContainerComponent } from "../components/memories-container/memories-container.component";
import { SearchResultsComponent } from "../components/search-results-container/search-results-container.component";
import { MetricsService } from "../services/metrics.service.js";
import { PolicyService } from "../services/policy.service.js";
import {UIService} from "../services/ui.service";

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
        StatusContainerComponent,
        StorageContainerComponent,
        StationContainerComponent,
        TasksContainerComponent,
        MemoriesContainerComponent,
        SearchResultsComponent,
    ],
    templateUrl: "./main-view.component.html",
    styleUrl: "./main-view.component.css",
})
export class MainViewComponent implements OnInit, OnDestroy {
    @ViewChild(SettingsMenuComponent) private settingsMenu?: SettingsMenuComponent;

    isLoading = true;
    isRunning = false;
    isInCombat = false;
    isDockedAtStation = false;
    isShipIdentUnknown = false;
    selectedTabIndex: number = 0;
    config: Config|undefined;
    hasLogbook = true;
    private uiChangeSubscription?: Subscription;
    private configSubscription!: Subscription;
    private inCombatSubscription!: Subscription;
    private currentStatusSubscription!: Subscription;
    private shipInfoSubscription!: Subscription;
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
        private uiService: UIService
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
                this.config = config ?? undefined;
                if (
                    this.config && this.config.cn_autostart &&
                    !this.isRunning && !this.hasAutoStarted
                ) {
                    console.log("Started automatically.");
                    this.start();
                    this.hasAutoStarted = true;
                }

                this.hasLogbook = this.config?.embedding_provider != 'none';
            },
        );

        // Subscribe to the running state
        this.tauri.runMode$.subscribe(
            (mode) => {
                this.isRunning = mode === "running";
                this.isLoading = mode === "starting";
            },
        );


        this.uiChangeSubscription = this.uiService.changeUI$.subscribe(
            (tabName) => {
                if (tabName === null) return;
                
                let current = 0;
                if (tabName === 'chat') {
                    this.selectedTabIndex = current;
                    return;
                }
                current++;

                if (!this.isShipIdentUnknown) {
                    if (tabName === 'status') { this.selectedTabIndex = current; return; }
                    current++;
                    if (tabName === 'storage') { this.selectedTabIndex = current; return; }
                    current++;
                    if (tabName === 'tasks') { this.selectedTabIndex = current; return; }
                    current++;
                    if (this.isDockedAtStation) {
                        if (tabName === 'station') { this.selectedTabIndex = current; return; }
                        current++;
                    }
                }

                if (this.hasLogbook) {
                    if (tabName === 'logbook') { this.selectedTabIndex = current; return; }
                    current++;
                }

                if (tabName === 'search') {
                    this.selectedTabIndex = current;
                    return;
                }
            }
        )

        // Subscribe to InCombat projection
        this.inCombatSubscription = this.projectionsService.inCombat$
            .subscribe((inCombatData) => {
                // InCombat projection might be a boolean or an object
                if (typeof inCombatData === 'boolean') {
                    this.isInCombat = inCombatData;
                } else if (inCombatData && typeof inCombatData === 'object') {
                    // If it's an object, check for a combat flag or status
                    this.isInCombat = Boolean(inCombatData.InCombat || inCombatData.combat || inCombatData.active);
                } else {
                    this.isInCombat = false;
                }
            });

        // Subscribe to CurrentStatus projection to track station docking
        this.currentStatusSubscription = this.projectionsService.currentStatus$
            .subscribe((currentStatusData) => {
                this.isDockedAtStation = Boolean(currentStatusData?.flags?.Docked === true);
            });

        // Subscribe to ShipInfo projection to track unknown ship ident
        this.shipInfoSubscription = this.projectionsService.shipInfo$
            .subscribe((shipInfo) => {
                const shipIdent = shipInfo?.ShipIdent ?? 'Unknown';
                this.isShipIdentUnknown = shipIdent === 'Unknown';
            });

        // Initialize the main view
        this.tauri.runExe();
        this.tauri.checkForUpdates();
    }

    ngOnDestroy(): void { // Implement ngOnDestroy
        if (this.configSubscription) {
            this.configSubscription.unsubscribe();
        }
        if (this.uiChangeSubscription) {
            this.uiChangeSubscription.unsubscribe();
        }
        if (this.inCombatSubscription) {
            this.inCombatSubscription.unsubscribe();
        }
        if (this.currentStatusSubscription) {
            this.currentStatusSubscription.unsubscribe();
        }
        if (this.shipInfoSubscription) {
            this.shipInfoSubscription.unsubscribe();
        }
    }

    // Called by the floating FAB when the policy is not yet accepted
    focusPolicy(): void {
        // Ensure the settings menu is visible (only visible when not running)
        this.settingsMenu?.focusDisclaimer();
    }

    acceptUsageDisclaimer() {
        this.policyService.acceptUsageDisclaimer();
    }

    async start(): Promise<void> {
        try {
            if(this.config && (this.config.overlay_show_avatar || this.config.overlay_show_chat)) {
                await this.createOverlay();
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
            await this.destroyOverlay();
            await this.tauri.restart_process();
        } catch (error) {
            console.error("Failed to stop:", error);
        }
    }

    async createOverlay(): Promise<void> {
        try {
            const isLinux = this.configService.systemInfo?.os === "Linux";
            const screenId = this.config?.overlay_screen_id ?? -1; // -1 for primary screen
            
            await this.tauri.createOverlay({
                alwaysOnTop: true,
                screenId: screenId
            });
        } catch (error) {
            console.error("Failed to create overlay:", error);
        }
    }

    async destroyOverlay(): Promise<void> {
        try {
            await this.tauri.destroyOverlay();
        } catch (error) {
            console.error("Failed to create overlay:", error);
        }
    }
}
