import { Component, OnDestroy, OnInit } from "@angular/core";
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
    Secrets,
    SystemInfo,
} from "../../services/config.service.js";
import { Subscription } from "rxjs";
import { MatSnackBar } from "@angular/material/snack-bar";
import { FormsModule } from "@angular/forms";
import { MatInputModule } from "@angular/material/input";
import { MatButtonModule } from "@angular/material/button";
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
    ],
    templateUrl: "./general-settings.component.html",
    styleUrls: ["./general-settings.component.css"],
})
export class GeneralSettingsComponent implements OnDestroy {
    config: Config | null = null;
    secrets: Secrets | null = null;
    system: SystemInfo | null = null;
    screens: ScreenInfo[] = [];
    private configSubscription: Subscription;
    private secretsSubscription: Subscription;
    private systemSubscription: Subscription;
    private screensSubscription?: Subscription;
    hideApiKey = true;
    apiKeyType: string | null = null;
    isAssigningPTT = false;

    constructor(
        private configService: ConfigService,
        private snackBar: MatSnackBar,
    ) {
        this.configSubscription = this.configService.config$.subscribe(
            (config) => {
                this.config = config;
                this.isAssigningPTT = false;
            },
        );
        this.secretsSubscription = this.configService.secrets$.subscribe(
            (secrets) => {
                console.log('received secrets message in general settings', secrets);
                this.secrets = secrets;
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
    }

    ngOnDestroy() {
        // Unsubscribe from the config observable to prevent memory leaks
        if (this.configSubscription) {
            this.configSubscription.unsubscribe();
        }
        if (this.secretsSubscription) {
            this.secretsSubscription.unsubscribe();
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
        await this.onSecretChange({ current_llm_key: apiKey });

        // Detect API key type
        let providerChanges: Partial<Config> = {};

        if (apiKey.startsWith("AIzaS")) {
            // Google AI Studio
            this.apiKeyType = "Google AI Studio";
            providerChanges = {
                llm_provider: "google-ai-studio",
                stt_provider: "google-ai-studio",
                vision_provider: "google-ai-studio",
                tts_provider: "edge-tts",
                vision_var: true,
            };
        } else if (apiKey.startsWith("sk-or-v1")) {
            // OpenRouter
            this.apiKeyType = "OpenRouter";
            providerChanges = {
                llm_provider: "openrouter",
                stt_provider: "none",
                vision_provider: "none",
                tts_provider: "edge-tts",
                vision_var: false,
            };
        } else if (apiKey.startsWith("sk-")) {
            // OpenAI
            this.apiKeyType = "OpenAI";
            providerChanges = {
                llm_provider: "openai",
                stt_provider: "openai",
                vision_provider: "openai",
                tts_provider: "edge-tts",
                vision_var: true,
            };
        } else {
            // Unknown key type
            this.apiKeyType = null;
            return; // Don't update providers if key type is unknown
        }

        // Update providers based on detected key type
        await this.onConfigChange(providerChanges);
    }

    async onAssignPTT(e: Event) {
        e.preventDefault();
        this.isAssigningPTT = true;
        await this.configService.assignPTT();
    }

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

    async onSecretChange(partialConfig: Partial<Secrets>) {
        if (this.secrets) {
            console.log("Sending secrets update to backend:", partialConfig);

            try {
                await this.configService.changeSecrets(partialConfig);
            } catch (error) {
                console.error("Error updating secrets:", error);
                this.snackBar.open("Error updating secrets", "OK", {
                    duration: 5000,
                });
            }
        }
    }
}
