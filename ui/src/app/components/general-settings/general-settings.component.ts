import { Component, ElementRef, EventEmitter, OnDestroy, Output, ViewChild } from "@angular/core";
import { CommonModule } from "@angular/common";
import { DomSanitizer, SafeHtml } from "@angular/platform-browser";
import { MatIcon } from "@angular/material/icon";
import {
    Config,
    ConfigService,
    KeybindsMessages,
    SystemInfo,
} from "../../services/config.service.js";
import { combineLatest, Subscription } from "rxjs";
import { MatTooltipModule } from "@angular/material/tooltip";
import {
    MatError,
    MatFormField,
    MatFormFieldModule,
    MatHint,
    MatLabel,
} from "@angular/material/form-field";
import { MatSlideToggle } from "@angular/material/slide-toggle";
import { MatOptgroup, MatOption, MatSelect } from "@angular/material/select";
import { OverlayRuntimeInfo, TauriService } from "../../services/tauri.service";
import { MatSnackBar } from "@angular/material/snack-bar";
import { FormsModule } from "@angular/forms";
import { MatInputModule } from "@angular/material/input";
import { MatButtonModule } from "@angular/material/button";
import { MatSliderModule } from "@angular/material/slider";
import { ScreenInfo } from "../../models/screen-info";
import { Character, CharacterService } from "../../services/character.service";
import { ModelProviderDefinition } from "../../services/plugin-settings";

export type GeneralSettingsTarget =
    | "commander"
    | "character"
    | "audio-input"
    | "audio-output"
    | "overlay"
    | "actions";
type AvatarPreviewStateClass = "listening" | "thinking" | "speaking" | "acting";
type PreflightChecklistItem = "commander" | "input" | "output" | "overlay" | "actions" | "covas";

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
        MatOptgroup,
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
    @ViewChild("preflightList") set preflightListRef(ref: ElementRef<HTMLElement> | undefined) {
        this.preflightListResizeObserver?.disconnect();
        this.preflightListResizeObserver = undefined;

        if (!ref) {
            this.preflightListHeight = 0;
            return;
        }

        const updateHeight = () => {
            this.preflightListHeight = ref.nativeElement.offsetHeight;
        };
        updateHeight();

        if (typeof ResizeObserver === "undefined") {
            return;
        }

        this.preflightListResizeObserver = new ResizeObserver(updateHeight);
        this.preflightListResizeObserver.observe(ref.nativeElement);
    }

    config: Config | null = null;
    system: SystemInfo | null = null;
    screens: ScreenInfo[] = [];
    overlayRuntimeInfo: OverlayRuntimeInfo | null = null;
    activeCharacter: Character | null = null;
    characterList: Character[] = [];
    keybindsData: KeybindsMessages | null = null;
    pluginSTTProviders: ModelProviderDefinition[] = [];
    pluginTTSProviders: ModelProviderDefinition[] = [];
    avatarUrl = "assets/cn_avatar_default.svg";
    sanitizedAvatarPreviewSvg: SafeHtml | null = null;
    avatarPreviewStateClass: AvatarPreviewStateClass = "listening";
    private configSubscription: Subscription;
    private systemSubscription: Subscription;
    private screensSubscription?: Subscription;
    private characterSubscription: Subscription;
    private characterListSubscription: Subscription;
    private keybindsSubscription: Subscription;
    private pluginProvidersSubscription: Subscription;
    private avatarMimeSubscription: Subscription;
    private avatarMimePrimary: string | null = null;
    private avatarSvgText: string | null = null;
    private avatarSvgFetchSeq = 0;
    private preflightListResizeObserver?: ResizeObserver;
    private readonly svgStateClasses = ["listening", "speaking", "thinking", "acting"];
    private readonly avatarPreviewStateClasses: readonly AvatarPreviewStateClass[] = ["listening", "thinking", "acting", "speaking"];
    private avatarPreviewStateIndex = 0;
    private readonly avatarPreviewInterval = setInterval(() => this.advanceAvatarPreviewState(), 3000);
    hideApiKey = true;
    apiKeyType: string | null = null;
    assigningPTTIndex: number | null = null;
    isRefreshingAudioDevices = false;
    activePreflightItem: PreflightChecklistItem = "commander";
    preflightListHeight = 0;

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
        this.characterListSubscription = this.characterService.characterList$.subscribe(
            (characters) => {
                this.characterList = characters ?? [];
            },
        );
        this.keybindsSubscription = this.configService.keybinds$.subscribe(
            (keybindsData) => {
                this.keybindsData = keybindsData;
            },
        );
        this.pluginProvidersSubscription = this.configService.plugin_model_providers$.subscribe(
            (providers) => {
                this.pluginSTTProviders = providers.filter((provider) => provider.kind === "stt");
                this.pluginTTSProviders = providers.filter((provider) => provider.kind === "tts");
            },
        );
        this.avatarMimeSubscription = combineLatest([this.characterService.avatarUrl$, this.characterService.avatarMime$]).subscribe(
            ([avatarUrl, mime]) => {
                this.avatarUrl = avatarUrl || this.characterService.getAvatarUrl();
                this.avatarMimePrimary = mime ?? this.characterService.getAvatarMime();
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
        this.characterListSubscription.unsubscribe();
        this.keybindsSubscription.unsubscribe();
        this.pluginProvidersSubscription.unsubscribe();
        this.avatarMimeSubscription.unsubscribe();
        this.preflightListResizeObserver?.disconnect();
        clearInterval(this.avatarPreviewInterval);
    }

    openTarget(target: GeneralSettingsTarget): void {
        this.openSettingsTarget.emit(target);
    }

    setActivePreflightItem(item: PreflightChecklistItem): void {
        this.activePreflightItem = item;
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

    get activeCharacterIndex(): number {
        return this.config?.active_character_index ?? 0;
    }

    get commanderReady(): boolean {
        return !!this.config?.commander_name?.trim() && !!this.config?.api_key?.trim();
    }

    get soundInputReady(): boolean {
        return !!this.config && this.config.stt_provider !== "none" && !!this.config.input_device_name?.trim();
    }

    get soundOutputReady(): boolean {
        return !!this.config && this.config.tts_provider !== "none" && !!this.config.output_device_name?.trim();
    }

    get actionsReady(): boolean {
        if (!this.keybindsData) {
            return false;
        }
        return this.actionIssueCounts.missing === 0
            && this.actionIssueCounts.conflicts === 0
            && this.actionIssueCounts.unsupported === 0;
    }

    get soundInputSummary(): string {
        const provider = this.providerLabel(this.config?.stt_provider, this.pluginSTTProviders);
        return `${provider} / ${this.inputDeviceName}`;
    }

    get soundOutputSummary(): string {
        const provider = this.providerLabel(this.config?.tts_provider, this.pluginTTSProviders);
        return `${provider} / ${this.outputDeviceName}`;
    }

    get actionSummary(): string {
        if (!this.keybindsData) {
            return "Checking keybinds";
        }
        if (this.actionsReady) {
            return "Ready";
        }

        const counts = this.actionIssueCounts;
        const parts: string[] = [];
        if (counts.missing > 0) {
            parts.push(`${counts.missing} missing`);
        }
        if (counts.conflicts > 0) {
            parts.push(`${counts.conflicts} conflicts`);
        }
        if (counts.unsupported > 0) {
            parts.push(`${counts.unsupported} unsupported`);
        }
        return parts.join(" / ");
    }

    get actionIssueCounts(): { missing: number; conflicts: number; unsupported: number } {
        return {
            missing: this.keybindsData?.missing.length ?? 0,
            conflicts: this.keybindsData?.collisions.length ?? 0,
            unsupported: this.keybindsData?.unsupported.length ?? 0,
        };
    }

    get enabledActionTypes(): string[] {
        if (!this.config?.tools_var) {
            return [];
        }

        const enabledTypes: string[] = [];
        if (this.config.game_actions_var) {
            enabledTypes.push("Game actions");
        }
        if (this.config.web_search_actions_var) {
            enabledTypes.push("Web actions");
        }
        if (this.config.ui_actions_var) {
            enabledTypes.push("UI actions");
        }
        if (this.config.overlay_show_hud) {
            enabledTypes.push("Allow Gen UI");
        }
        return enabledTypes;
    }

    get characterPrompt(): string {
        return this.activeCharacter?.character?.trim() || "No character prompt configured yet.";
    }

    get characterName(): string {
        return this.activeCharacter?.name?.trim() || "Not set";
    }

    get eventReactionCounts(): { on: number; off: number; hidden: number } {
        const events = this.activeCharacter?.event_reactions;
        const counts = { on: 0, off: 0, hidden: 0 };
        if (!events) {
            return counts;
        }

        for (const state of Object.values(events)) {
            if (state === "on") {
                counts.on += 1;
            } else if (state === "hidden") {
                counts.hidden += 1;
            } else {
                counts.off += 1;
            }
        }

        return counts;
    }

    isPluginProvider(provider: string | undefined | null): boolean {
        return provider?.startsWith("plugin:") ?? false;
    }

    providerLabel(provider: string | undefined | null, pluginProviders: ModelProviderDefinition[] = []): string {
        if (!provider) {
            return "Not set";
        }
        if (this.isPluginProvider(provider)) {
            const match = pluginProviders.find(
                (pluginProvider) => provider === `plugin:${pluginProvider.plugin_guid}:${pluginProvider.id}`,
            );
            return match?.label ?? "Plugin";
        }

        switch (provider) {
            case "openai":
                return "OpenAI";
            case "openrouter":
                return "OpenRouter";
            case "google-ai-studio":
                return "Google AI Studio";
            case "edge-tts":
                return "Edge TTS";
            case "local-ai-server":
                return "Local AIServer";
            case "custom":
                return "Custom";
            case "custom-multi-modal":
                return "Custom Multi-Modal";
            case "none":
                return "None";
            default:
                return provider;
        }
    }

    get avatarPreviewUsesInlineSvg(): boolean {
        const mime = this.avatarMimePrimary ?? this.characterService.getAvatarMime();
        return mime === "image/svg+xml";
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

    async onCharacterSelect(index: number) {
        try {
            await this.characterService.setActiveCharacter(index);
        } catch (error) {
            console.error("Error selecting character:", error);
            this.snackBar.open("Error selecting character", "OK", {
                duration: 5000,
            });
        }
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
