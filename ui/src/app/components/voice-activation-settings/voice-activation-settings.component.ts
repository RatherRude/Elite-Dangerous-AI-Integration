import { Component, EventEmitter, Input, Output } from "@angular/core";
import { FormsModule, NgModel } from "@angular/forms";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatSelectModule } from "@angular/material/select";
import { TranslateModule } from "@ngx-translate/core";
import { Config } from "../../services/config.service";
import { modelProviderLabel, ModelProviderDefinition } from "../../services/plugin-settings";
import {
    PARAKEET_PROVIDER,
    VoiceActivationConfig,
    parakeetAvailable,
    voiceActivationPrivacy,
} from "../../services/voice-activation.service";

@Component({
    selector: "app-voice-activation-settings",
    standalone: true,
    imports: [FormsModule, MatFormFieldModule, MatInputModule, MatSelectModule, TranslateModule],
    template: `
        @if (config; as c) {
            <p>{{ 'voice.replacesRequiredWord' | translate }}</p>
            <div class="fields">
                <mat-form-field>
                    <mat-label>{{ 'voice.name' | translate }}</mat-label>
                    <input matInput required [pattern]="namePattern"
                        [ngModel]="c.wake_word_name" (ngModelChange)="changeName($event)"
                        #nameModel="ngModel">
                    @if (nameModel.invalid) {
                        <mat-error>{{ 'voice.invalidName' | translate }}</mat-error>
                    }
                </mat-form-field>
                <mat-form-field>
                    <mat-label>{{ 'voice.timeout' | translate }}</mat-label>
                    <input matInput type="number" required
                        [ngModel]="c.wake_word_timeout"
                        (ngModelChange)="changeTimeout($event, timeoutModel)" #timeoutModel="ngModel">
                    @if (timeoutModel.invalid) {
                        <mat-error>{{ 'voice.invalidTimeout' | translate }}</mat-error>
                    }
                </mat-form-field>
                <mat-form-field>
                    <mat-label>{{ 'voice.source' | translate }}</mat-label>
                    <mat-select [value]="c.wake_word_source"
                        (selectionChange)="configChange.emit({wake_word_source: $event.value})">
                        <mat-option value="main">{{ 'voice.mainSource' | translate }}</mat-option>
                        <mat-option value="parakeet" [disabled]="!available">
                            {{ 'voice.parakeetSource' | translate }}
                        </mat-option>
                    </mat-select>
                </mat-form-field>
                @if (hybrid) {
                    <mat-form-field>
                        <mat-label>{{ 'voice.firstCommand' | translate }}</mat-label>
                        <mat-select [value]="c.wake_word_first_command"
                            (selectionChange)="configChange.emit({wake_word_first_command: $event.value})">
                            <mat-option value="retranscribe">{{ 'voice.retranscribe' | translate }}</mat-option>
                            <mat-option value="reuse">{{ 'voice.reuse' | translate }}</mat-option>
                        </mat-select>
                    </mat-form-field>
                }
            </div>
            <p role="note">{{ privacy | translate }} <strong>{{ mainProviderLabel }}</strong></p>
            @if (hybrid) {
                <p>{{ (c.wake_word_first_command === 'reuse' ? 'voice.reuseHelp' : 'voice.retranscribeHelp') | translate }}</p>
            }
            @if (c.stt_provider === parakeetProvider) {
                <p>{{ 'voice.singleRecognition' | translate }}</p>
            } @else if (c.wake_word_source !== 'parakeet' || !available) {
                <p>{{ (available ? 'voice.available' : 'voice.install') | translate }}
                    <a href="https://github.com/COVAS-Labs/plugin-parakeet-stt"
                        target="_blank" rel="noopener noreferrer">{{ 'voice.pluginLink' | translate }}</a>
                </p>
            }
            <p>{{ 'voice.usage' | translate }}</p>
        }
    `,
    styles: [`
        :host { display: block; width: 100%; }
        .fields { display: flex; flex-wrap: wrap; gap: 12px; }
        mat-form-field { flex: 1 1 220px; }
        p { line-height: 1.5; }
        strong { overflow-wrap: anywhere; }
    `],
})
export class VoiceActivationSettingsComponent {
    @Input() config: VoiceActivationConfig | null = null;
    @Input() providers: ModelProviderDefinition[] = [];
    @Output() configChange = new EventEmitter<Partial<Config>>();
    readonly parakeetProvider = PARAKEET_PROVIDER;
    readonly namePattern = /[\p{L}\p{N}]/u;

    get available(): boolean {
        return parakeetAvailable(this.providers);
    }

    get hybrid(): boolean {
        return this.config?.wake_word_source === "parakeet"
            && this.config.stt_provider !== PARAKEET_PROVIDER && this.available;
    }

    get privacy(): string {
        return this.config ? voiceActivationPrivacy(this.config, this.providers) : "";
    }

    get mainProviderLabel(): string {
        return modelProviderLabel(this.config?.stt_provider, "stt", this.providers);
    }

    changeName(value: string): void {
        if (this.namePattern.test(value)) this.configChange.emit({ wake_word_name: value });
    }

    changeTimeout(value: number | null, model: NgModel): void {
        if (value === null || !Number.isFinite(value) || value <= 0) {
            model.control.setErrors({ positive: true });
            return;
        }
        this.configChange.emit({ wake_word_timeout: value });
    }
}
