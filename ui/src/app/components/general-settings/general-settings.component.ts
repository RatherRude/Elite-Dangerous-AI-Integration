import { Component, ElementRef, EventEmitter, OnDestroy, Output, ViewChild } from "@angular/core";
import { CommonModule } from "@angular/common";
import { DomSanitizer, SafeHtml } from "@angular/platform-browser";
import { MatIcon } from "@angular/material/icon";
import {
    Config,
    ConfigService,
    SystemInfo,
} from "../../services/config.service.js";
import { Subscription } from "rxjs";
import { MatTooltipModule } from "@angular/material/tooltip";
import {
    MatError,
    MatFormField,
    MatFormFieldModule,
    MatHint,
    MatLabel,
} from "@angular/material/form-field";
import { MatSlideToggle } from "@angular/material/slide-toggle";
import { MatOption, MatSelect } from "@angular/material/select";
import { OverlayRuntimeInfo, TauriService } from "../../services/tauri.service";
import { MatSnackBar } from "@angular/material/snack-bar";
import { FormsModule } from "@angular/forms";
import { MatInputModule } from "@angular/material/input";
import { MatButtonModule } from "@angular/material/button";
import { MatSliderModule } from "@angular/material/slider";
import { ScreenInfo } from "../../models/screen-info";
import { Character, CharacterService } from "../../services/character.service";
import { combineLatest } from "rxjs";

export type GeneralSettingsTarget =
    | "commander"
    | "character"
    | "audio-input"
    | "audio-output"
    | "overlay";
type AvatarPreviewStateClass = "" | "listening" | "thinking" | "speaking" | "acting";

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
        MatTooltipModule,
        MatSliderModule,
    ],
    templateUrl: "./general-settings.component.html",
    styleUrls: ["./general-settings.component.css"],
})
export class GeneralSettingsComponent implements OnDestroy {
    @Output() openSettingsTarget = new EventEmitter<GeneralSettingsTarget>();
    @ViewChild("generalAvatarSvg") private generalAvatarSvg?: ElementRef<HTMLDivElement>;

    config: Config | null = null;
    system: SystemInfo | null = null;
    screens: ScreenInfo[] = [];
    overlayRuntimeInfo: OverlayRuntimeInfo | null = null;
    activeCharacter: Character | null = null;
    avatarUrl = "assets/cn_avatar_default.png";
    sanitizedAvatarPreviewSvg: SafeHtml | null = null;
    avatarPreviewStateClass: AvatarPreviewStateClass = "";
    useCompactGeneralSettings = false;
    private configSubscription: Subscription;
    private systemSubscription: Subscription;
    private screensSubscription?: Subscription;
    private characterSubscription: Subscription;
    private avatarMimeSubscription: Subscription;
    private avatarMimePrimary: string | null = null;
    private avatarSvgText: string | null = null;
    private avatarSvgFetchSeq = 0;
    private hasCapturedInitialGeneralMode = false;
    private readonly svgStateClasses = ["listening", "speaking", "thinking", "acting"];
    private readonly avatarPreviewStateClasses: readonly AvatarPreviewStateClass[] = ["", "listening", "thinking", "speaking", "acting"];
    private avatarPreviewStateIndex = 0;
    private readonly avatarPreviewInterval = setInterval(() => this.advanceAvatarPreviewState(), 1200);
    hideApiKey = true;
    apiKeyType: string | null = null;
    assigningPTTIndex: number | null = null;
    isRefreshingAudioDevices = false;

    constructor(
        private configService: ConfigService,
        private tauriService: TauriService,
        private snackBar: MatSnackBar,
        private characterService: CharacterService,
        private sanitizer: DomSanitizer,
    ) {
        this.configSubscription = this.configService.config$.subscribe(
            (config) => {
                this.config = config;
                if (config && !this.hasCapturedInitialGeneralMode) {
                    this.useCompactGeneralSettings = !!config.commander_name?.trim() && !!config.api_key?.trim();
                    this.hasCapturedInitialGeneralMode = true;
                }
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
        this.characterSubscription = this.characterService.character$.subscribe(
            (character) => {
                this.activeCharacter = character;
            },
        );
        this.avatarMimeSubscription = combineLatest([this.characterService.avatarUrl$, this.characterService.avatarMime$]).subscribe(
            ([avatarUrl, mime]) => {
                this.avatarUrl = avatarUrl || this.characterService.getAvatarUrl();
                this.avatarMimePrimary = mime;
                this.avatarSvgText = null;
                this.refreshAvatarPreviewSvg();
            },
        );
        void this.loadOverlayRuntimeInfo();
    }

    ngOnDestroy() {
        this.configSubscription.unsubscribe();
        this.systemSubscription.unsubscribe();
        this.screensSubscription?.unsubscribe();
        this.characterSubscription.unsubscribe();
        this.avatarMimeSubscription.unsubscribe();
        clearInterval(this.avatarPreviewInterval);
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

    get characterName(): string {
        return this.activeCharacter?.name?.trim() || "Not set";
    }

    get activeEventCount(): number {
        const events = this.activeCharacter?.event_reactions;
        if (!events) {
            return 0;
        }
        return Object.values(events).filter((state) => state === "on").length;
    }

    get avatarPreviewUsesInlineSvg(): boolean {
        return this.avatarMimePrimary === "image/svg+xml";
    }

    get activeEventLabel(): string {
        return this.activeEventCount === 1 ? "1 active event" : `${this.activeEventCount} active events`;
    }

    private advanceAvatarPreviewState(): void {
        this.avatarPreviewStateIndex = (this.avatarPreviewStateIndex + 1) % this.avatarPreviewStateClasses.length;
        this.avatarPreviewStateClass = this.avatarPreviewStateClasses[this.avatarPreviewStateIndex];
        this.updateSanitizedAvatarSvg();
        setTimeout(() => this.applyAvatarPreviewSvgStateClass());
    }

    private refreshAvatarPreviewSvg(): void {
        if (!this.avatarPreviewUsesInlineSvg || !this.avatarUrl) {
            this.avatarSvgFetchSeq += 1;
            this.sanitizedAvatarPreviewSvg = null;
            return;
        }
        void this.loadAvatarPreviewSvg(this.avatarUrl);
    }

    private async loadAvatarPreviewSvg(url: string): Promise<void> {
        const seq = ++this.avatarSvgFetchSeq;
        try {
            const res = await fetch(url);
            const text = await res.text();
            if (seq !== this.avatarSvgFetchSeq || url !== this.avatarUrl || !this.avatarPreviewUsesInlineSvg) {
                return;
            }
            this.avatarSvgText = text;
            this.updateSanitizedAvatarSvg();
            setTimeout(() => this.applyAvatarPreviewSvgStateClass());
        } catch (err) {
            console.error("General settings: failed to load SVG avatar preview", err);
            if (seq === this.avatarSvgFetchSeq) {
                this.sanitizedAvatarPreviewSvg = null;
            }
        }
    }

    private updateSanitizedAvatarSvg(): void {
        if (!this.avatarSvgText || !this.avatarPreviewUsesInlineSvg) {
            return;
        }
        const safe = this.stripScriptsFromSvg(this.syncSvgRootClass(this.avatarSvgText, this.avatarPreviewStateClass));
        this.sanitizedAvatarPreviewSvg = this.sanitizer.bypassSecurityTrustHtml(safe);
    }

    private syncSvgRootClass(svg: string, stateClass: AvatarPreviewStateClass): string {
        return svg.replace(/<svg\b([^>]*)>/i, (_m, attrs: string) => {
            const classMatch = attrs.match(/\sclass\s*=\s*(["'])(.*?)\1/i);
            const preservedClasses = classMatch?.[2]
                .split(/\s+/)
                .filter(Boolean)
                .filter((className) => !this.svgStateClasses.includes(className)) ?? [];
            const nextAttrs = attrs.replace(/\sclass\s*=\s*(["']).*?\1/i, "").trim();
            const nextClasses = stateClass ? [...preservedClasses, stateClass] : preservedClasses;
            const classAttr = nextClasses.length > 0 ? ` class="${nextClasses.join(" ")}"` : "";
            return nextAttrs ? `<svg ${nextAttrs}${classAttr}>` : `<svg${classAttr}>`;
        });
    }

    private stripScriptsFromSvg(svg: string): string {
        return svg.replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, "");
    }

    private applyAvatarPreviewSvgStateClass(): void {
        if (!this.avatarPreviewUsesInlineSvg) {
            return;
        }
        const svg = this.generalAvatarSvg?.nativeElement.querySelector("svg");
        if (!svg) {
            return;
        }
        svg.classList.remove(...this.svgStateClasses);
        if (this.avatarPreviewStateClass) {
            svg.classList.add(this.avatarPreviewStateClass);
        }
    }

    async onApiKeyChange(apiKey: string) {
        if (!this.config) return;

        await this.onConfigChange({ api_key: apiKey });

        let providerChanges: Partial<Config> = {};

        if (apiKey.startsWith("AQ") || apiKey.startsWith("AIzaS")) {
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
            this.apiKeyType = null;
            return;
        }

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
