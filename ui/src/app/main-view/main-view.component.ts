import { ChangeDetectorRef, Component, ElementRef, OnDestroy, OnInit, ViewChild } from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressBarModule } from "@angular/material/progress-bar";
import { MatDialogModule } from "@angular/material/dialog";
import { MatSnackBar } from "@angular/material/snack-bar";
import { MatSnackBarModule } from "@angular/material/snack-bar";
import { TauriService } from "../services/tauri.service";
import { LoggingService } from "../services/logging.service";
import { LogContainerComponent } from "../components/log-container/log-container.component";
import { SettingsMenuComponent } from "../components/settings-menu/settings-menu.component";
import { InputContainerComponent } from "../components/input-container/input-container.component";
import {Config, ConfigService} from "../services/config.service";
import { Subscription } from "rxjs";
import { ChatService } from "../services/chat.service";
import { MatTabsModule } from "@angular/material/tabs";
import { ChatContainerComponent } from "../components/chat-container/chat-container.component";
import { StatusContainerComponent } from "../components/status-container/status-container.component";
import { StorageContainerComponent } from "../components/storage-container/storage-container.component";
import { StationContainerComponent } from "../components/station-container/station-container.component";
import { TasksContainerComponent } from "../components/tasks-container/tasks-container.component";
import { ProjectionsService } from "../services/projections.service";
import { MemoriesContainerComponent } from "../components/memories-container/memories-container.component";
import { SearchResultsComponent } from "../components/search-results-container/search-results-container.component";
import { NavigationContainerComponent } from "../components/navigation-container/navigation-container.component";
import { MetricsService } from "../services/metrics.service";
import { PolicyService } from "../services/policy.service";
import {UIService} from "../services/ui.service";
import { ActionsContainerComponent } from "../components/actions-container/actions-container.component";
import { PluginViewComponent } from "../components/plugin-view/plugin-view.component";
import { PluginUIService } from "../services/plugin-ui.service";
import { RegisteredUIView } from "../services/plugin-ui";
import { TranslateModule } from "@ngx-translate/core";
import { UISectionService } from "../services/ui-section.service";

@Component({
    selector: "app-main-view",
    standalone: true,
    imports: [
        CommonModule,
        MatButtonModule,
        MatIconModule,
        MatProgressBarModule,
        MatDialogModule,
        MatSnackBarModule,
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
        NavigationContainerComponent,
        ActionsContainerComponent,
        PluginViewComponent,
        TranslateModule,
    ],
    templateUrl: "./main-view.component.html",
    styleUrl: "./main-view.component.css",
})
export class MainViewComponent implements OnInit, OnDestroy {
    @ViewChild(SettingsMenuComponent) private settingsMenu?: SettingsMenuComponent;

    runMode: "starting" | "configuring" | "running" | "error" = "starting";
    isLoading = true;
    isRunning = false;
    showRuntimeView = false;
    isInCombat = false;
    isDockedAtStation = false;
    isShipIdentUnknown = false;
    private currentStatusData: any = null;
    private shipInfo: any = null;
    currentGameModeLabel = "Status";
    currentGameModeIcon = "info";
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
    public isQuestEditorOpen = false;
    private systemSubscription?: Subscription;
    private pluginViewsSubscription?: Subscription;
    private sectionSubscription?: Subscription;
    pluginViews: RegisteredUIView[] = [];
    configPluginViews: RegisteredUIView[] = [];

    constructor(
        private tauri: TauriService,
        private loggingService: LoggingService,
        private chatService: ChatService,
        private configService: ConfigService,
        private projectionsService: ProjectionsService,
        private metricsService: MetricsService,
        private policyService: PolicyService,
        private uiService: UIService,
        private snackBar: MatSnackBar,
        private pluginUI: PluginUIService,
        private host: ElementRef<HTMLElement>,
        private changeDetector: ChangeDetectorRef,
        private sections: UISectionService,
    ) {
        this.policyService.usageDisclaimerAccepted$.subscribe(
            (accepted) => {
                this.usageDisclaimerAccepted = accepted;
            },
        );
    }

    private applyHudColors(system?: { hud_accent_color?: string; hud_secondary_color?: string } | null): void {
        this.setHudColor("--hud-orange", system?.hud_accent_color);
        this.setHudColor("--hud-cyan", system?.hud_secondary_color);
    }

    private setHudColor(variable: "--hud-orange" | "--hud-cyan", color?: string): void {
        if (!color || !/^#[0-9a-fA-F]{6}$/.test(color)) {
            return;
        }

        document.documentElement.style.setProperty(variable, color);
    }

    ngOnInit(): void {
        this.sectionSubscription = this.uiService.sectionRequests$.subscribe(request => {
            let result;
            try {
                this.changeDetector.detectChanges();
                result = { success: true, ...this.sections.apply(this.host.nativeElement, request,
                    () => this.changeDetector.detectChanges()) };
            } catch (error) {
                const message = error instanceof Error ? error.message : String(error);
                console.error("Could not change UI section:", error);
                this.snackBar.open(message, "OK", { duration: 7000 });
                result = { success: false, error: message };
            }
            void this.tauri.send_command({
                type: "ui_section_result", request_id: request.request_id,
                timestamp: new Date().toISOString(), ...result,
            }).catch(error => console.error("Could not acknowledge UI section change:", error));
        });
        this.pluginViewsSubscription = this.pluginUI.views$.subscribe(views => {
            this.pluginViews = views.filter(view => (view.modes ?? ['running']).includes('running'));
            this.configPluginViews = views.filter(view => (view.modes ?? ['running']).includes('configuring'));
            const visibleCount = this.builtinRuntimeTabs().length + this.pluginViews.length;
            if (this.selectedTabIndex >= visibleCount) this.selectedTabIndex = 0;
        });
        this.applyHudColors(this.configService.systemInfo);
        this.systemSubscription = this.configService.system$.subscribe((system) => {
            this.applyHudColors(system);
        });

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
                this.runMode = mode;
                this.isRunning = mode === "running";
                this.isLoading = mode === "starting";
                this.showRuntimeView = mode === "running" || mode === "error";
                if (mode === "error") {
                    this.selectedTabIndex = 0;
                }
            },
        );


        this.uiChangeSubscription = this.uiService.changeUI$.subscribe(
            (uiMessage) => {
                if (uiMessage === null) return;
                if (uiMessage.scroll) {
                    this.scrollActiveTab(uiMessage.scroll);
                    return;
                }
                const tabName = uiMessage.show;
                if (!tabName) return;
                const targetIndex = [...this.builtinRuntimeTabs(), ...this.pluginViews.map(view => view.target)].indexOf(tabName);
                if (targetIndex >= 0) this.selectedTabIndex = targetIndex;
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
                this.currentStatusData = currentStatusData;
                this.isDockedAtStation = Boolean(currentStatusData?.flags?.Docked === true);
                this.currentGameModeLabel = this.getCurrentGameModeLabel(currentStatusData);
                this.currentGameModeIcon = this.getCurrentGameModeIcon(currentStatusData);
            });

        // Subscribe to ShipInfo projection to track unknown ship ident
        this.shipInfoSubscription = this.projectionsService.shipInfo$
            .subscribe((shipInfo) => {
                this.shipInfo = shipInfo;
                const shipIdent = shipInfo?.ShipIdent ?? 'Unknown';
                this.isShipIdentUnknown = shipIdent === 'Unknown';
                this.currentGameModeLabel = this.getCurrentGameModeLabel(this.currentStatusData);
                this.currentGameModeIcon = this.getCurrentGameModeIcon(this.currentStatusData);
            });

        // Initialize the main view
        this.tauri.runExe();
        this.tauri.checkForUpdates();
    }

    ngOnDestroy(): void { // Implement ngOnDestroy
        this.sectionSubscription?.unsubscribe();
        this.pluginViewsSubscription?.unsubscribe();
        if (this.systemSubscription) {
            this.systemSubscription.unsubscribe();
        }
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

    private builtinRuntimeTabs(): string[] {
        return ['chat', ...(!this.isShipIdentUnknown ? ['status'] : []), 'navigation',
            ...(!this.isShipIdentUnknown ? ['storage', 'tasks', ...(this.isDockedAtStation ? ['station'] : [])] : []),
            ...(this.hasLogbook ? ['logbook'] : []), 'search', 'actions'];
    }

    onRuntimeTabSelected(index: number): void {
        if (index === this.selectedTabIndex) return;
        this.selectedTabIndex = index;
        const target = [...this.builtinRuntimeTabs(), ...this.pluginViews.map(view => view.target)][index];
        if (target) this.uiService.showTab(target);
    }

    private getCurrentGameModeLabel(currentStatusData: any): string {
        if (!currentStatusData) {
            return "Status";
        }

        if (currentStatusData.flags2?.OnFoot) {
            return "Suit";
        }
        if (currentStatusData.flags?.InFighter || (currentStatusData.flags?.InSRV && this.shipInfo?.fighter_loadout === "base")) {
            return "SLF";
        }
        if (currentStatusData.flags?.InSRV) {
            return "SRV";
        }

        return "Ship";
    }

    private getCurrentGameModeIcon(currentStatusData: any): string {
        if (!currentStatusData) {
            return "info";
        }

        if (currentStatusData.flags2?.OnFoot) {
            return "directions_walk";
        }
        if (currentStatusData.flags?.InFighter || (currentStatusData.flags?.InSRV && this.shipInfo?.fighter_loadout === "base")) {
            return "flight";
        }
        if (currentStatusData.flags?.InSRV) {
            return "directions_car";
        }

        return "rocket_launch";
    }

    private scrollActiveTab(direction: "top" | "up" | "down" | "bottom"): void {
        const activeTab = document.querySelector<HTMLElement>(".mat-mdc-tab-body-active");
        if (!activeTab) return;

        const scrollContainer = Array.from(activeTab.querySelectorAll<HTMLElement>("*")).find((element) => {
            const overflowY = getComputedStyle(element).overflowY;
            return (overflowY === "auto" || overflowY === "scroll") && element.scrollHeight > element.clientHeight;
        });
        if (!scrollContainer) return;

        if (direction === "top" || direction === "bottom") {
            scrollContainer.scrollTo({
                top: direction === "top" ? 0 : scrollContainer.scrollHeight,
                behavior: "smooth",
            });
            return;
        }

        scrollContainer.scrollBy({
            top: (direction === "up" ? -1 : 1) * scrollContainer.clientHeight * 0.75,
            behavior: "smooth",
        });
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
            if(
                this.config
                && this.config.overlay_mode !== "disabled"
                && (this.config.overlay_show_avatar || this.config.overlay_show_chat || this.config.overlay_show_hud)
            ) {
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
            if (this.config?.overlay_mode === "disabled") {
                return;
            }

            const screenId = this.config?.overlay_screen_id ?? -1; // -1 for primary screen

            await this.tauri.createOverlay({
                alwaysOnTop: true,
                screenId: screenId,
                mode: this.config?.overlay_mode ?? "desktop",
                standaloneTransparent: this.config?.overlay_standalone_transparent ?? true,
                standaloneBackgroundColor: this.config?.overlay_standalone_background_color ?? "#000000",
                vrSizeMeters: this.config?.overlay_vr_size_meters ?? 0.9,
                vrAnchor: this.config?.overlay_vr_anchor ?? "head",
                vrHorizontalOffset: this.config?.overlay_vr_horizontal_offset ?? 0,
                vrVerticalOffset: this.config?.overlay_vr_vertical_offset ?? 0,
                vrDistanceOffset: this.config?.overlay_vr_distance_offset ?? 0,
                vrTiltDegrees: this.config?.overlay_vr_tilt_degrees ?? 0,
                vrYawDegrees: this.config?.overlay_vr_yaw_degrees ?? 0,
                vrCurvature: this.config?.overlay_vr_curvature ?? 0,
            });
        } catch (error) {
            console.error("Failed to create overlay:", error);
            this.snackBar.open(
                error instanceof Error ? error.message : "The overlay could not be created.",
                "OK",
                { duration: 7000 },
            );
        }
    }

    async destroyOverlay(): Promise<void> {
        try {
            await this.tauri.destroyOverlay();
        } catch (error) {
            console.error("Failed to create overlay:", error);
        }
    }

    onQuestEditorVisibilityChange(isOpen: boolean): void {
        this.isQuestEditorOpen = isOpen;
    }
}
