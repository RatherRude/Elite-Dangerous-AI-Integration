import { Component, OnDestroy } from "@angular/core";
import { CommonModule } from "@angular/common";
import {
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
import { MatDivider } from "@angular/material/divider";
import { MatInputModule } from "@angular/material/input";
import { MatButtonModule } from "@angular/material/button";
import { Character, CharacterService } from "../../services/character.service.js";
import { ConfigBackupService } from "../../services/config-backup.service";
import { MatIcon } from "@angular/material/icon";
import {
    MatAccordion,
    MatExpansionModule,
    MatExpansionPanel,
    MatExpansionPanelHeader,
    MatExpansionPanelTitle,
} from "@angular/material/expansion";
import { ModelProviderDefinition, SettingsGrid } from "../../services/plugin-settings";
import { SettingsGridComponent } from "../settings-grid/settings-grid.component";

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
        MatOptgroup,
        MatDivider,
        MatIcon,
        MatAccordion,
        MatExpansionModule,
        MatExpansionPanel,
        MatExpansionPanelHeader,
        MatExpansionPanelTitle,
        SettingsGridComponent,
    ],
    templateUrl: "./advanced-settings.component.html",
    styleUrl: "./advanced-settings.component.css",
})
export class AdvancedSettingsComponent implements OnDestroy {
    config: Config | null = null;
    system: SystemInfo | null = null;
    character: Character | null = null;
    configSubscription: Subscription;
    systemSubscription: Subscription;
    characterSubscription: Subscription;
    pluginProvidersSubscription: Subscription;
    voiceInstructionSupportedModels: string[] = this.characterService.voiceInstructionSupportedModels;

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
    ) {
        this.configSubscription = this.configService.config$.subscribe(
            (config) => {
                this.config = config;
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
        return normalizedPath.startsWith('/') && !normalizedPath.startsWith('/home');
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
}
