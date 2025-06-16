import { Component, OnDestroy, OnInit } from "@angular/core";
import { MatCardModule } from "@angular/material/card";
import { MatTabsModule } from "@angular/material/tabs";
import {
    Config,
    ConfigService,
    SystemInfo,
} from "../../services/config.service";
import { Subscription } from "rxjs";
import { MatSnackBar } from "@angular/material/snack-bar";
import { CommonModule } from "@angular/common";
import { PluginSettingsComponent } from "../plugin-settings/plugin-settings.component";
import { PolicyService } from "../../services/policy.service.js";
import { AdvancedSettingsComponent } from "../advanced-settings/advanced-settings.component";
import { BehaviorSettingsComponent } from "../behavior-settings/behavior-settings.component";
import { CharacterSettingsComponent } from "../character-settings/character-settings.component";
import { GeneralSettingsComponent } from "../general-settings/general-settings.component";
import { MatOption } from "@angular/material/core";
import { MatIcon } from "@angular/material/icon";
import { MatFormField, MatLabel } from "@angular/material/form-field";
import { MatSelect } from "@angular/material/select";
import {
    MatExpansionPanel,
    MatExpansionPanelHeader,
    MatExpansionPanelTitle,
} from "@angular/material/expansion";
import { MatSlideToggle } from "@angular/material/slide-toggle";
import { FormsModule } from "@angular/forms";

@Component({
    selector: "app-settings-menu",
    standalone: true,
    imports: [
        CommonModule,
        MatCardModule,
        MatTabsModule,
        MatOption,
        MatIcon,
        MatFormField,
        MatLabel,
        MatSelect,
        MatSlideToggle,
        MatExpansionPanel,
        MatExpansionPanelHeader,
        MatExpansionPanelTitle,
        FormsModule,
        PluginSettingsComponent,
        AdvancedSettingsComponent,
        BehaviorSettingsComponent,
        CharacterSettingsComponent,
        GeneralSettingsComponent,
    ],
    templateUrl: "./settings-menu.component.html",
    styleUrls: ["./settings-menu.component.scss"],
})
export class SettingsMenuComponent implements OnInit, OnDestroy {
    config: Config | null = null;
    has_plugin_settings: boolean = false;
    system: SystemInfo | null = null;
    private configSubscription?: Subscription;
    private plugin_settings_message_subscription?: Subscription;
    private validationSubscription?: Subscription;
    public usageDisclaimerAccepted = false;

    constructor(
        private configService: ConfigService,
        private snackBar: MatSnackBar,
        private policyService: PolicyService,
    ) {
        this.policyService.usageDisclaimerAccepted$.subscribe(
            (accepted) => {
                this.usageDisclaimerAccepted = accepted;
            },
        );
    }

    acceptUsageDisclaimer() {
        this.policyService.acceptUsageDisclaimer();
    }

    ngOnInit() {
        this.configSubscription = this.configService.config$.subscribe(
            (config) => {
                this.config = config;
            },
        );
        this.plugin_settings_message_subscription = this.configService
            .plugin_settings_message$
            .subscribe(
                (plugin_settings_message) => {
                    this.has_plugin_settings =
                        plugin_settings_message?.has_plugin_settings || false;
                    if (plugin_settings_message?.plugin_settings_configs) {
                        console.log("Plugin settings count received", {
                            has_plugin_settings:
                                plugin_settings_message.has_plugin_settings,
                        });
                    } else {
                        console.error("Received null plugin settings");
                    }
                },
            );

        this.validationSubscription = this.configService.validation$
            .subscribe((validation) => {
                if (validation) {
                    // Show snackbar for validation messages
                    const snackBarDuration = validation.success ? 3000 : 6000;
                    const snackBarClass = validation.success
                        ? "validation-success-snackbar"
                        : "validation-error-snackbar";

                    this.snackBar.open(validation.message, "Dismiss", {
                        duration: snackBarDuration,
                        panelClass: [snackBarClass],
                    });
                }
            });
    }

    ngOnDestroy() {
        if (this.configSubscription) {
            this.configSubscription.unsubscribe();
        }
        if (this.validationSubscription) {
            this.validationSubscription.unsubscribe();
        }
        if (this.plugin_settings_message_subscription) {
            this.plugin_settings_message_subscription.unsubscribe();
        }
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
}
