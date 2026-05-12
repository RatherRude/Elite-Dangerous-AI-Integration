import { Component, OnDestroy } from "@angular/core";
import { CommonModule } from "@angular/common";
import {
    MatError,
    MatFormField,
    MatFormFieldModule,
    MatHint,
    MatLabel,
} from "@angular/material/form-field";
import { MatIcon } from "@angular/material/icon";
import { MatSlideToggle } from "@angular/material/slide-toggle";
import { MatOption, MatSelect } from "@angular/material/select";
import {
    Config,
    ConfigService,
    SystemInfo,
} from "../../services/config.service.js";
import {
    OverlayRuntimeInfo,
    TauriService,
} from "../../services/tauri.service";
import { Subscription } from "rxjs";
import { MatSnackBar } from "@angular/material/snack-bar";
import { FormsModule } from "@angular/forms";
import { MatInputModule } from "@angular/material/input";
import { MatButtonModule } from "@angular/material/button";
import { MatSliderModule } from "@angular/material/slider";
import { MatTooltipModule } from "@angular/material/tooltip";
import { ScreenInfo } from "../../models/screen-info";

@Component({
    selector: "app-general-settings",
    standalone: true,
    imports: [
        CommonModule,
        MatInputModule,
        MatFormFieldModule,
        MatButtonModule,
        FormsModule,
        MatFormField,
        MatLabel,
        MatIcon,
        MatSlideToggle,
        MatSelect,
        MatOption,
        MatHint,
        MatError,
        MatSliderModule,
        MatTooltipModule,
    ],
    templateUrl: "./general-settings.component.html",
    styleUrls: ["./general-settings.component.css"],
})
export class GeneralSettingsComponent implements OnDestroy {
    config: Config | null = null;
    system: SystemInfo | null = null;
    screens: ScreenInfo[] = [];
    overlayRuntimeInfo: OverlayRuntimeInfo | null = null;
    private configSubscription: Subscription;
    private systemSubscription: Subscription;
    private screensSubscription?: Subscription;
    hideApiKey = true;
    apiKeyType: string | null = null;
    assigningPTTIndex: number | null = null;
    isRefreshingAudioDevices = false;

    constructor(
        private configService: ConfigService,
        private tauriService: TauriService,
        private snackBar: MatSnackBar,
    ) {
        this.configSubscription = this.configService.config$.subscribe(
            (config) => {
                this.config = config;
                this.assigningPTTIndex = null;
            },
        );
        this.systemSubscription = this.configService.system$.subscribe(
            (system) => {
                this.system = system;
            },
        );
        this.screensSubscription = this.configService.screens$.subscribe(
            (screens) => {
                this.screens = screens ?? [];
            }
        );
        void this.loadOverlayRuntimeInfo();
    }

    ngOnDestroy() {
        // Unsubscribe from the config observable to prevent memory leaks
        if (this.configSubscription) {
            this.configSubscription.unsubscribe();
        }
        if (this.systemSubscription) {
            this.systemSubscription.unsubscribe();
        }
        if (this.screensSubscription) {
            this.screensSubscription.unsubscribe();
        }
    }

    async onApiKeyChange(apiKey: string) {
        if (!this.config) return;

        // Update the API key in config first
        await this.onConfigChange({ api_key: apiKey });

        // Detect API key type
        let providerChanges: Partial<Config> = {};

        if (apiKey.startsWith("AQ")) {
            // Google AI Studio
            this.apiKeyType = "Google AI Studio";
            providerChanges = {
                llm_provider: "google-ai-studio",
                agent_llm_provider: "google-ai-studio",
                stt_provider: "google-ai-studio",
                vision_provider: "google-ai-studio",
                tts_provider: "edge-tts",
                vision_var: true,
                embedding_provider: "google-ai-studio",
            };
        } else if (apiKey.startsWith("sk-or-v1")) {
            // OpenRouter
            this.apiKeyType = "OpenRouter";
            providerChanges = {
                llm_provider: "openrouter",
                agent_llm_provider: "openrouter",
                stt_provider: "none",
                vision_provider: "none",
                tts_provider: "edge-tts",
                vision_var: false,
                embedding_provider: "none",
            };
        } else if (apiKey.startsWith("sk-")) {
            // OpenAI
            this.apiKeyType = "OpenAI";
            providerChanges = {
                llm_provider: "openai",
                agent_llm_provider: "openai",
                stt_provider: "openai",
                vision_provider: "openai",
                tts_provider: "edge-tts",
                vision_var: true,
                embedding_provider: "openai",
            };
        } else {
            // Unknown key type
            this.apiKeyType = null;
            return; // Don't update providers if key type is unknown
        }

        // Update providers based on detected key type
        await this.onConfigChange(providerChanges);
    }

    async onAssignPTT(e: Event, index: number) {
        e.preventDefault();
        this.assigningPTTIndex = index;
        await this.configService.assignPTT(index);
    }

    formatOutputVolumeLabel = (value: number): string => value.toFixed(2);

    async onConfigChange(partialConfig: Partial<Config>) {
        if (this.config) {
            console.log("Sending config update to backend:", partialConfig);

            try {
                await this.configService.changeConfig(partialConfig);
            } catch (error) {
                console.error("Error updating config:", error);
                this.snackBar.open("Error updating configuration", "OK", {
                    duration: 5000,
                });
            }
        }
    }

    async refreshAudioDevices() {
        this.isRefreshingAudioDevices = true;

        try {
            await this.configService.refreshSystemInfo();
        } catch (error) {
            console.error("Error refreshing audio devices:", error);
            this.snackBar.open("Error refreshing audio devices", "OK", {
                duration: 5000,
            });
        } finally {
            this.isRefreshingAudioDevices = false;
        }
    }

    get overlayRuntimeSummary(): string {
        const info = this.overlayRuntimeInfo;
        if (!info) {
            return "Checking VR runtime support...";
        }
        if (!info.packageInstalled) {
            return "The optional electron-vr package is not installed yet.";
        }
        if (!info.available) {
            return `VR bridge loaded, but no runtime is ready. Backend: ${info.selectedBackend}.`;
        }
        const runtimePath = info.openvrRuntimePath ? ` (${info.openvrRuntimePath})` : "";
        return `VR ready via ${info.selectedBackend}${runtimePath}.`;
    }

    get overlayRuntimeReady(): boolean {
        const info = this.overlayRuntimeInfo;
        return !!info?.packageInstalled && info.available;
    }

    private async loadOverlayRuntimeInfo(): Promise<void> {
        try {
            this.overlayRuntimeInfo = await this.tauriService.getOverlayRuntimeInfo();
        } catch (error) {
            console.error("Error loading overlay runtime info:", error);
            this.overlayRuntimeInfo = null;
        }
    }
}
