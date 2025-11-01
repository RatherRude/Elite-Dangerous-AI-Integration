import { Component } from "@angular/core";
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
    ],
    templateUrl: "./advanced-settings.component.html",
    styleUrl: "./advanced-settings.component.css",
})
export class AdvancedSettingsComponent {
    config: Config | null = null;
    system: SystemInfo | null = null;
    character: Character | null = null;
    configSubscription: Subscription;
    systemSubscription: Subscription;
    characterSubscription: Subscription;
    voiceInstructionSupportedModels: string[] = this.characterService.voiceInstructionSupportedModels;

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
    }
    ngOnDestroy() {
        // Unsubscribe from the config observable to prevent memory leaks
        if (this.configSubscription) {
            this.configSubscription.unsubscribe();
        }
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
