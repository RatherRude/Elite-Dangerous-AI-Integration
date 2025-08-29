import { Component } from "@angular/core";
import { CommonModule } from "@angular/common";
import {
    MatFormField,
    MatFormFieldModule,
    MatHint,
    MatLabel,
} from "@angular/material/form-field";
import { MatSlideToggle } from "@angular/material/slide-toggle";
import { MatIcon } from "@angular/material/icon";
import { MatOptgroup, MatOption, MatSelect } from "@angular/material/select";
import { Subscription } from "rxjs";
import {
    Config,
    ConfigService,
    SystemInfo,
} from "../../services/config.service.js";
import { MatSnackBar } from "@angular/material/snack-bar";
import { FormsModule } from "@angular/forms";
import { MatTooltipModule } from "@angular/material/tooltip";
import { MatDivider } from "@angular/material/divider";
import { MatInputModule } from "@angular/material/input";
import { MatButtonModule } from "@angular/material/button";
import { Character, CharacterService } from "../../services/character.service.js";

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
        MatIcon,
        MatTooltipModule,
        MatSlideToggle,
        MatSelect,
        MatOption,
        MatHint,
        MatOptgroup,
        MatDivider,
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
    async bugReport(): Promise<void> {
        try {
        const zipPath = await (window as any).electronAPI.invoke('bug-report');
        alert(`Bug-Report erstellt:\n${zipPath}`);
        } catch (e: any) {
        alert(`Fehler beim Bug-Report:\n${e?.message || String(e)}`);
        }
    }
    

}




