import { Component, EventEmitter, OnDestroy, Output } from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatIcon } from "@angular/material/icon";
import {
    Config,
    ConfigService,
} from "../../services/config.service.js";
import { Subscription } from "rxjs";
import { MatTooltipModule } from "@angular/material/tooltip";

export type GeneralSettingsTarget =
    | "commander"
    | "audio-input"
    | "audio-output"
    | "overlay";

@Component({
    selector: "app-general-settings",
    standalone: true,
    imports: [
        CommonModule,
        MatIcon,
        MatTooltipModule,
    ],
    templateUrl: "./general-settings.component.html",
    styleUrls: ["./general-settings.component.css"],
})
export class GeneralSettingsComponent implements OnDestroy {
    @Output() openSettingsTarget = new EventEmitter<GeneralSettingsTarget>();

    config: Config | null = null;
    private configSubscription: Subscription;

    constructor(
        private configService: ConfigService,
    ) {
        this.configSubscription = this.configService.config$.subscribe(
            (config) => {
                this.config = config;
            },
        );
    }

    ngOnDestroy() {
        this.configSubscription.unsubscribe();
    }

    openTarget(target: GeneralSettingsTarget): void {
        this.openSettingsTarget.emit(target);
    }

    get commanderName(): string {
        return this.config?.commander_name?.trim() || "Not set";
    }

    get inputDeviceName(): string {
        return this.config?.input_device_name?.trim() || "Default input device";
    }

    get outputDeviceName(): string {
        return this.config?.output_device_name?.trim() || "Default output device";
    }

    get overlayModeLabel(): string {
        switch (this.config?.overlay_mode) {
            case "desktop":
                return "Desktop Overlay";
            case "vr":
                return "VR Overlay";
            case "both":
                return "Desktop + VR Overlay";
            case "disabled":
            default:
                return "Disabled";
        }
    }

    get outputLevelLabel(): string {
        const multiplier = this.config?.output_volume_multiplier ?? 1;
        return `${Math.round(multiplier * 100)}%`;
    }
}
