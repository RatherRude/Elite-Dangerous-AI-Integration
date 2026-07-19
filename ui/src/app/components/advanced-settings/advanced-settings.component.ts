import { Component, ElementRef, EventEmitter, OnDestroy, Output, ViewChild } from "@angular/core";
import { CommonModule } from "@angular/common";
import {
    MatError,
    MatFormField,
    MatFormFieldModule,
    MatHint,
    MatLabel,
} from "@angular/material/form-field";
import { MatSlideToggle } from "@angular/material/slide-toggle";
import { MatOptgroup, MatOption, MatSelect } from "@angular/material/select";
import { Subscription } from "rxjs";
import {
    Config,
    ConfigService,
    SystemInfo,
} from "../../services/config.service.js";
import { MatSnackBar } from "@angular/material/snack-bar";
import { FormsModule } from "@angular/forms";
import { MatInputModule } from "@angular/material/input";
import { MatButtonModule } from "@angular/material/button";
import { Character, CharacterService } from "../../services/character.service.js";
import { ConfigBackupService } from "../../services/config-backup.service";
import { MatIcon } from "@angular/material/icon";
import {
    OverlayRuntimeInfo,
    TauriService,
} from "../../services/tauri.service";
import {
    MatAccordion,
    MatExpansionModule,
    MatExpansionPanel,
    MatExpansionPanelHeader,
    MatExpansionPanelTitle,
} from "@angular/material/expansion";
import { ModelProviderDefinition, SettingsGrid } from "../../services/plugin-settings";
import { SettingsGridComponent } from "../settings-grid/settings-grid.component";
import { MatDialog } from "@angular/material/dialog";
import { ConfirmationDialogComponent } from "../confirmation-dialog/confirmation-dialog.component";
import { ChatService } from "../../services/chat.service";
import { MatSliderModule } from "@angular/material/slider";
import { MatTooltipModule } from "@angular/material/tooltip";
import { ScreenInfo } from "../../models/screen-info";
import QRCode from "qrcode";

export type AdvancedSettingsFocusTarget =
    | "commander-name"
    | "stt-input-device"
    | "tts-output-device"
    | "overlay-mode";

type AdvancedSettingsPanel = "commander" | "stt" | "tts" | "overlay" | "remote-interface";

@Component({
    selector: "app-advanced-settings",
    standalone: true,
    imports: [
        CommonModule,
        MatInputModule,
        MatFormFieldModule,
        FormsModule,
        MatButtonModule,
        MatFormField,
        MatLabel,
        MatSlideToggle,
        MatSelect,
        MatOption,
        MatHint,
        MatError,
        MatOptgroup,
        MatIcon,
        MatAccordion,
        MatExpansionModule,
        MatExpansionPanel,
        MatExpansionPanelHeader,
        MatExpansionPanelTitle,
        SettingsGridComponent,
        MatSliderModule,
        MatTooltipModule,
    ],
    templateUrl: "./advanced-settings.component.html",
    styleUrl: "./advanced-settings.component.css",
})
export class AdvancedSettingsComponent implements OnDestroy {
    @Output() questEditorOpen = new EventEmitter<void>();
    @ViewChild("commanderNameInput") private commanderNameInput?: ElementRef<HTMLInputElement>;
    @ViewChild("commanderNameField", { read: ElementRef }) private commanderNameField?: ElementRef<HTMLElement>;
    @ViewChild("sttInputDeviceField", { read: ElementRef }) private sttInputDeviceField?: ElementRef<HTMLElement>;
    @ViewChild("sttInputDeviceSelect") private sttInputDeviceSelect?: MatSelect;
    @ViewChild("ttsOutputDeviceField", { read: ElementRef }) private ttsOutputDeviceField?: ElementRef<HTMLElement>;
    @ViewChild("ttsOutputDeviceSelect") private ttsOutputDeviceSelect?: MatSelect;
    @ViewChild("overlayModeField", { read: ElementRef }) private overlayModeField?: ElementRef<HTMLElement>;
    @ViewChild("overlayModeSelect") private overlayModeSelect?: MatSelect;
    
    config: Config | null = null;
    system: SystemInfo | null = null;
    character: Character | null = null;
    screens: ScreenInfo[] = [];
    overlayRuntimeInfo: OverlayRuntimeInfo | null = null;
    configSubscription: Subscription;
    systemSubscription: Subscription;
    characterSubscription: Subscription;
    pluginProvidersSubscription: Subscription;
    screensSubscription: Subscription;
    voiceInstructionSupportedModels: string[] = this.characterService.voiceInstructionSupportedModels;
    hideApiKey = true;
    hideLlmApiKey = true;
    hideAgentLlmApiKey = true;
    hideSttApiKey = true;
    hideTtsApiKey = true;
    hideVisionApiKey = true;
    hideEmbeddingApiKey = true;
    apiKeyType: string | null = null;
    assigningPTTIndex: number | null = null;
    isRefreshingAudioDevices = false;
    isStartingRemoteInterface = false;
    remoteInterfaceUrl: string | null = null;
    remoteInterfacePin: string | null = null;
    remoteInterfaceQrCode: string | null = null;
    remoteInterfaceHost = "127.0.0.1";
    remoteInterfacePort = 4048;
    remoteInterfaceBindAddresses: string[] = ["127.0.0.1"];
    highlightTarget: AdvancedSettingsFocusTarget | null = null;
    expandedPanels: Record<AdvancedSettingsPanel, boolean> = {
        commander: false,
        stt: false,
        tts: false,
        overlay: false,
        "remote-interface": false,
    };

    // Plugin model providers grouped by kind
    pluginLLMProviders: ModelProviderDefinition[] = [];
    pluginSTTProviders: ModelProviderDefinition[] = [];
    pluginTTSProviders: ModelProviderDefinition[] = [];
    pluginEmbeddingProviders: ModelProviderDefinition[] = [];

    constructor(
        private configService: ConfigService,
        private characterService: CharacterService,
        private snackBar: MatSnackBar,
        private configBackupService: ConfigBackupService,
        private tauriService: TauriService,
        private dialog: MatDialog,
        private chatService: ChatService,
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
        this.characterSubscription = this.characterService.character$.subscribe(
            (character) => {
                this.character = character;
            }
        );
        this.pluginProvidersSubscription = this.configService.plugin_model_providers$.subscribe(
            (providers) => {
                this.pluginLLMProviders = providers.filter(p => p.kind === 'llm');
                this.pluginSTTProviders = providers.filter(p => p.kind === 'stt');
                this.pluginTTSProviders = providers.filter(p => p.kind === 'tts');
                this.pluginEmbeddingProviders = providers.filter(p => p.kind === 'embedding');
            }
        );
        this.screensSubscription = this.configService.screens$.subscribe(
            (screens) => {
                this.screens = screens ?? [];
            },
        );
        void this.loadOverlayRuntimeInfo();
        void this.loadRemoteInterfaceBindAddresses();
    }
    ngOnDestroy() {
        // Unsubscribe from the config observable to prevent memory leaks
        if (this.configSubscription) {
            this.configSubscription.unsubscribe();
        }
        if (this.systemSubscription) {
            this.systemSubscription.unsubscribe();
        }
        if (this.characterSubscription) {
            this.characterSubscription.unsubscribe();
        }
        if (this.pluginProvidersSubscription) {
            this.pluginProvidersSubscription.unsubscribe();
        }
        if (this.screensSubscription) {
            this.screensSubscription.unsubscribe();
        }
    }

    public focusSetting(target: AdvancedSettingsFocusTarget): void {
        const panel = this.getPanelForTarget(target);
        this.expandedPanels[panel] = true;
        this.highlightTarget = target;

        window.setTimeout(() => {
            this.focusTarget(target);
        }, 250);

        window.setTimeout(() => {
            if (this.highlightTarget === target) {
                this.highlightTarget = null;
            }
        }, 1700);
    }

    private getPanelForTarget(target: AdvancedSettingsFocusTarget): AdvancedSettingsPanel {
        switch (target) {
            case "commander-name":
                return "commander";
            case "stt-input-device":
                return "stt";
            case "tts-output-device":
                return "tts";
            case "overlay-mode":
                return "overlay";
        }
    }

    private focusTarget(target: AdvancedSettingsFocusTarget): void {
        switch (target) {
            case "commander-name":
                this.commanderNameInput?.nativeElement.focus();
                this.commanderNameField?.nativeElement.scrollIntoView({ behavior: "smooth", block: "center" });
                break;
            case "stt-input-device":
                this.sttInputDeviceSelect?.focus();
                this.sttInputDeviceField?.nativeElement.scrollIntoView({ behavior: "smooth", block: "center" });
                break;
            case "tts-output-device":
                this.ttsOutputDeviceSelect?.focus();
                this.ttsOutputDeviceField?.nativeElement.scrollIntoView({ behavior: "smooth", block: "center" });
                break;
            case "overlay-mode":
                this.overlayModeSelect?.focus();
                this.overlayModeField?.nativeElement.scrollIntoView({ behavior: "smooth", block: "center" });
                break;
        }
    }

    // Check if a provider string is a plugin provider
    isPluginProvider(provider: string): boolean {
        return provider?.startsWith('plugin:') ?? false;
    }

    // Parse plugin provider string to get guid and id
    parsePluginProvider(provider: string): { guid: string; id: string } | null {
        if (!this.isPluginProvider(provider)) return null;
        const parts = provider.split(':');
        if (parts.length !== 3) return null;
        return { guid: parts[1], id: parts[2] };
    }

    // Get the selected plugin provider definition for a given provider string
    getSelectedPluginProvider(provider: string, kind: 'llm' | 'stt' | 'tts' | 'embedding'): ModelProviderDefinition | null {
        const parsed = this.parsePluginProvider(provider);
        if (!parsed) return null;
        
        const providers = {
            'llm': this.pluginLLMProviders,
            'stt': this.pluginSTTProviders,
            'tts': this.pluginTTSProviders,
            'embedding': this.pluginEmbeddingProviders
        }[kind];
        
        return providers.find(p => p.plugin_guid === parsed.guid && p.id === parsed.id) || null;
    }

    // Get plugin setting value
    getPluginProviderSetting(pluginGuid: string, key: string, defaultValue: any = null): any {
        const pluginSettings = this.config?.plugin_settings?.[pluginGuid];
        return pluginSettings?.[key] ?? defaultValue;
    }

    // Set plugin setting value
    async setPluginProviderSetting(pluginGuid: string, key: string, value: any): Promise<void> {
        if (!this.config) return;
        
        const currentPluginSettings = this.config.plugin_settings?.[pluginGuid] ?? {};
        const updatedPluginSettings = {
            ...this.config.plugin_settings,
            [pluginGuid]: {
                ...currentPluginSettings,
                [key]: value
            }
        };
        
        await this.onConfigChange({ plugin_settings: updatedPluginSettings });
    }

    // Create a getValue function for a specific plugin (for use with SettingsGridComponent)
    createGetValueFn(pluginGuid: string): (fieldKey: string, defaultValue: any) => any {
        return (fieldKey: string, defaultValue: any) => {
            return this.config?.plugin_settings?.[pluginGuid]?.[fieldKey] ?? defaultValue;
        };
    }

    // Create a setValue function for a specific plugin (for use with SettingsGridComponent)
    createSetValueFn(pluginGuid: string): (fieldKey: string, value: any) => void {
        return (fieldKey: string, value: any) => {
            this.setPluginProviderSetting(pluginGuid, fieldKey, value);
        };
    }

    updateTTSVoice(voice: string) {
        this.characterService.setCharacterProperty("tts_voice", voice);
    }
    updateTTSSpeed(speed: string) {
        this.characterService.setCharacterProperty("tts_speed", speed);
    }
    updateTTSPrompt(prompt: string) {
        this.characterService.setCharacterProperty("tts_prompt", prompt);
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

    private async loadRemoteInterfaceBindAddresses(): Promise<void> {
        if (!window.electronAPI?.invoke) {
            return;
        }

        try {
            const addresses = await window.electronAPI.invoke('get_remote_interface_bind_addresses');
            if (Array.isArray(addresses) && addresses.every((address) => typeof address === 'string')) {
                this.remoteInterfaceBindAddresses = addresses;
            }
        } catch (error) {
            console.error('Error loading remote interface bind addresses:', error);
        }
    }

    parseFloat(value: string): number {
        return parseFloat(value.replaceAll(",", "."));
    }

    normalizePath(path: string): string {
        if (!path) return path;
        // Remove trailing slashes
        let normalized = path.replace(/\/+$/, '');
        return normalized;
    }

    isPathOutsideHome(path: string): boolean {
        if (!path) return false;
        const normalizedPath = this.normalizePath(path);
        if (!normalizedPath.startsWith('/')) return false;

        const homePrefix = this.system?.os === 'Darwin' ? '/Users' : '/home';
        return !normalizedPath.startsWith(homePrefix);
    }

    isManualEdPathConfigAvailable(): boolean {
        return this.system?.os === 'Linux' || this.system?.os === 'Darwin';
    }

    getManualEdPathSettingsLabel(): string {
        return this.system?.os === 'Darwin' ? 'macOS Settings' : 'Linux Settings';
    }

    getManualEdPathPermissionHint(): string {
        if (this.system?.os === 'Darwin') {
            return 'Directories outside of /Users may require additional macOS permissions.';
        }

        return 'Directories outside of /home need to be permitted manually via flatpak override';
    }

    isMacOS(): boolean {
        return this.system?.os === 'Darwin';
    }

    async requestAccessibilityPermission(): Promise<void> {
        try {
            const result = await this.tauriService.requestAccessibilityPermission();
            if (!result.supported) {
                this.snackBar.open('Accessibility permission requests are only available on macOS.', 'OK', {
                    duration: 5000,
                });
                return;
            }

            if (result.granted) {
                this.snackBar.open('Accessibility access is already enabled for COVAS:NEXT.', 'OK', {
                    duration: 5000,
                });
                return;
            }

            const message = result.openedSettings
                ? 'macOS opened Accessibility settings. Enable COVAS:NEXT there and restart the app if needed.'
                : 'Accessibility permission was requested. Enable COVAS:NEXT in System Settings if macOS did not grant it immediately.';
            this.snackBar.open(message, 'OK', {
                duration: 8000,
            });
        } catch (error) {
            console.error('Error requesting accessibility permission:', error);
            this.snackBar.open('Failed to request Accessibility permission.', 'OK', {
                duration: 5000,
            });
        }
    }

    async openAccessibilitySettings(): Promise<void> {
        try {
            const result = await this.tauriService.openAccessibilitySettings();
            if (!result.supported) {
                this.snackBar.open('Accessibility settings deep-link is only available on macOS.', 'OK', {
                    duration: 5000,
                });
                return;
            }

            if (result.opened) {
                this.snackBar.open('Opened macOS Accessibility settings.', 'OK', {
                    duration: 5000,
                });
                return;
            }

            this.snackBar.open('Unable to open macOS Accessibility settings automatically.', 'OK', {
                duration: 5000,
            });
        } catch (error) {
            console.error('Error opening accessibility settings:', error);
            this.snackBar.open('Failed to open Accessibility settings.', 'OK', {
                duration: 5000,
            });
        }
    }

    async startRemoteInterface(): Promise<void> {
        if (!window.electronAPI?.invoke) {
            this.snackBar.open('Remote web interface can only be started from the desktop app.', 'OK', {
                duration: 5000,
            });
            return;
        }

        this.isStartingRemoteInterface = true;
        try {
            const result = await window.electronAPI.invoke('start_remote_interface', {
                host: this.remoteInterfaceHost,
                port: this.remoteInterfacePort,
            });
            if (typeof result?.host === 'string') {
                this.remoteInterfaceHost = result.host;
            }
            if (Number.isInteger(result?.port)) {
                this.remoteInterfacePort = result.port;
            }
            this.remoteInterfaceUrl = typeof result?.url === 'string' ? result.url : `http://${this.remoteInterfaceHost}:${this.remoteInterfacePort}/`;
            this.remoteInterfacePin = typeof result?.pin === 'string' ? result.pin : null;
            await this.updateRemoteInterfaceQrCode(this.remoteInterfaceShareUrl);
            this.snackBar.open(`Remote web interface started at ${this.remoteInterfaceUrl}`, 'OK', {
                duration: 5000,
            });
        } catch (error) {
            console.error('Error starting remote web interface:', error);
            this.snackBar.open('Failed to start remote web interface.', 'OK', {
                duration: 5000,
            });
        } finally {
            this.isStartingRemoteInterface = false;
        }
    }

    isValidRemoteInterfacePort(): boolean {
        return Number.isInteger(this.remoteInterfacePort)
            && this.remoteInterfacePort >= 1
            && this.remoteInterfacePort <= 65535;
    }

    get remoteInterfaceShareUrl(): string | null {
        if (!this.remoteInterfaceUrl) {
            return null;
        }
        return this.remoteInterfacePin
            ? `${this.remoteInterfaceUrl}#pin=${encodeURIComponent(this.remoteInterfacePin)}`
            : this.remoteInterfaceUrl;
    }

    async copyRemoteInterfaceUrl(): Promise<void> {
        if (!this.remoteInterfaceShareUrl) {
            return;
        }
        await this.copyRemoteInterfaceValue(this.remoteInterfaceShareUrl, 'Remote interface link copied.');
    }

    async copyRemoteInterfacePin(): Promise<void> {
        if (!this.remoteInterfacePin) {
            return;
        }
        await this.copyRemoteInterfaceValue(this.remoteInterfacePin, 'Remote interface PIN copied.');
    }

    private async copyRemoteInterfaceValue(value: string, successMessage: string): Promise<void> {
        try {
            if (navigator.clipboard?.writeText) {
                await navigator.clipboard.writeText(value);
            } else {
                const input = document.createElement('textarea');
                input.value = value;
                input.style.position = 'fixed';
                input.style.opacity = '0';
                document.body.appendChild(input);
                try {
                    input.select();
                    if (!document.execCommand('copy')) {
                        throw new Error('Clipboard API is unavailable');
                    }
                } finally {
                    input.remove();
                }
            }
            this.snackBar.open(successMessage, 'OK', { duration: 3000 });
        } catch (error) {
            console.error('Error copying remote interface value:', error);
            this.snackBar.open('Failed to copy the remote interface value.', 'OK', { duration: 5000 });
        }
    }

    private async updateRemoteInterfaceQrCode(url: string | null): Promise<void> {
        if (!url) {
            this.remoteInterfaceQrCode = null;
            return;
        }

        try {
            this.remoteInterfaceQrCode = await QRCode.toDataURL(url, {
                errorCorrectionLevel: 'M',
                margin: 1,
                width: 192,
            });
        } catch (error) {
            console.error('Error generating remote interface QR code:', error);
            this.remoteInterfaceQrCode = null;
            this.snackBar.open('Failed to generate the remote interface QR code.', 'OK', { duration: 5000 });
        }
    }

    async stopRemoteInterface(): Promise<void> {
        if (!window.electronAPI?.invoke) {
            return;
        }

        this.isStartingRemoteInterface = true;
        try {
            await window.electronAPI.invoke('stop_remote_interface');
            this.remoteInterfaceUrl = null;
            this.remoteInterfacePin = null;
            this.remoteInterfaceQrCode = null;
        } catch (error) {
            console.error('Error stopping remote web interface:', error);
            this.snackBar.open('Failed to stop remote web interface.', 'OK', {
                duration: 5000,
            });
        } finally {
            this.isStartingRemoteInterface = false;
        }
    }

    onPathChange(field: 'ed_appdata_path' | 'ed_journal_path', value: string) {
        const normalized = this.normalizePath(value);
        const update: Partial<Config> = {};
        update[field] = normalized;
        this.onConfigChange(update);
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

    async onExportConfig() {
        try {
            await this.configBackupService.exportConfig();
        } catch (error) {
            console.error("Error exporting configuration:", error);
            this.snackBar.open("Failed to export configuration", "OK", {
                duration: 5000,
            });
        }
    }

    async onImportConfig(event: Event) {
        const input = event.target as HTMLInputElement;
        if (!input.files || input.files.length === 0) {
            return;
        }

        const file = input.files[0];
        
        try {
            const result = await this.configBackupService.importConfig(file);
            
            if (result.success) {
                this.snackBar.open(result.message + " - Reloading in 1 second...", "OK", {
                    duration: 1000,
                });
                
                // Reload the page after 1 second to ensure all components reflect the new config
                setTimeout(() => {
                    window.location.reload();
                }, 1000);
            } else {
                this.snackBar.open(`Import failed: ${result.message}`, "OK", {
                    duration: 5000,
                });
            }
        } catch (error) {
            console.error("Error importing configuration:", error);
            this.snackBar.open("Failed to import configuration", "OK", {
                duration: 5000,
            });
        } finally {
            // Reset the input so the same file can be selected again
            input.value = '';
        }
    }

    openQuestEditor(): void {
        this.questEditorOpen.emit();
    }

    async onResetStateMachine(): Promise<void> {
        const dialogRef = this.dialog.open(ConfirmationDialogComponent, {
            data: {
                title: "Reset State Machine",
                message:
                    "Are you sure you want to reset the state machine? This clears persisted events and projection state and cannot be undone. Long-term memories and mapped system data are not affected.",
            },
        });

        dialogRef.afterClosed().subscribe(async (result) => {
            if (!result) {
                return;
            }

            await this.configService.resetStateMachine();
            this.chatService.clearChat();
            this.snackBar.open("State machine reset", "OK", {
                duration: 3000,
            });
        });
    }

    async onDeleteCurrentLogbook(): Promise<void> {
        const dialogRef = this.dialog.open(ConfirmationDialogComponent, {
            data: {
                title: "Delete Current Logbook",
                message:
                    "Are you sure you want to delete the current logbook? This removes all long-term memory entries and cannot be undone.",
            },
        });

        dialogRef.afterClosed().subscribe(async (result) => {
            if (!result) {
                return;
            }

            try {
                await this.configService.deleteCurrentLogbook();
                this.snackBar.open("Current logbook deleted", "OK", {
                    duration: 3000,
                });
            } catch (error) {
                console.error("Error deleting current logbook:", error);
                this.snackBar.open("Failed to delete current logbook", "OK", {
                    duration: 5000,
                });
            }
        });
    }
}
