import { Component, EventEmitter, OnDestroy, Output } from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatIcon } from "@angular/material/icon";
import {
    Config,
    ConfigService,
} from "../../services/config.service.js";
import { Subscription } from "rxjs";
import { MatTooltipModule } from "@angular/material/tooltip";
import { Character, CharacterService } from "../../services/character.service";

export type GeneralSettingsTarget =
    | "commander"
    | "character"
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
    character: Character | null = null;
    avatarUrl = "assets/cn_avatar_default.png";
    private configSubscription: Subscription;
    private characterSubscription: Subscription;
    private avatarSubscription: Subscription;

    constructor(
        private configService: ConfigService,
        private characterService: CharacterService,
    ) {
        this.configSubscription = this.configService.config$.subscribe(
            (config) => {
                this.config = config;
            },
        );
        this.characterSubscription = this.characterService.character$.subscribe(
            (character) => {
                this.character = character;
            }
        );
        this.avatarSubscription = this.characterService.avatarUrl$.subscribe(
            (avatarUrl) => {
                this.avatarUrl = avatarUrl || this.characterService.getAvatarUrl();
            },
        );
    }

    ngOnDestroy() {
        this.configSubscription.unsubscribe();
        this.characterSubscription.unsubscribe();
        this.avatarSubscription.unsubscribe();
    }

    openTarget(target: GeneralSettingsTarget): void {
        this.openSettingsTarget.emit(target);
    }

    get commanderName(): string {
        return this.config?.commander_name?.trim() || "Not set";
    }

    get characterName(): string {
        return this.character?.name?.trim() || "Not set";
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
