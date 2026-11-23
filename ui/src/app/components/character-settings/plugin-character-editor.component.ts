import { Component, Inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialog, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatInputModule } from '@angular/material/input';
import { ConfigService, PluginCharacter, PluginCharacterProfile } from '../../services/config.service';
import { matchesSettingCondition, ModelProviderDefinition } from '../../services/plugin-settings';
import { AvatarCatalogDialogComponent, AvatarCatalogResult } from '../avatar-catalog-dialog/avatar-catalog-dialog.component';
import { SettingsGridComponent } from '../settings-grid/settings-grid.component';

interface EditorData {
    profile: PluginCharacter;
    provider: ModelProviderDefinition | null;
    providerDefaults?: Record<string, unknown>;
    hostSpeech: boolean;
}

@Component({
    standalone: true,
    imports: [FormsModule, MatButtonModule, MatDialogModule, MatInputModule, SettingsGridComponent],
    templateUrl: './plugin-character-editor.component.html',
    styles: ['mat-dialog-content { display: grid; gap: 1rem; }'],
})
export class PluginCharacterEditorComponent {
    readonly draft: PluginCharacterProfile;
    readonly changes: PluginCharacterProfile = {};
    saving = false;
    error = '';

    constructor(@Inject(MAT_DIALOG_DATA) readonly data: EditorData, private config: ConfigService,
        private dialog: MatDialog, private ref: MatDialogRef<PluginCharacterEditorComponent>) {
        this.draft = structuredClone(data.profile.character);
    }

    readonly getField = (key: string, fallback: any) => this.draft[key] ?? fallback;
    get showVoice(): boolean {
        const condition = this.data.profile.voice_condition;
        return this.data.hostSpeech && (!condition || matchesSettingCondition(condition, this.draft[condition.key]));
    }
    hasField(key: string): boolean {
        return Object.prototype.hasOwnProperty.call(this.data.profile.character, key);
    }

    readonly setField = (key: string, value: any) => {
        if (!this.hasField(key)) return;
        this.draft[key] = value;
        this.changes[key] = value;
    };

    get providerRef(): string {
        const provider = this.data.provider;
        return provider ? `plugin:${provider.plugin_guid}:${provider.id}` : '';
    }

    readonly getVoice = (key: string, fallback: any) => {
        const legacy = this.draft['tts_voice'];
        return this.draft.tts_voice_settings?.[this.providerRef]?.[key]
            ?? (key === 'voice' && typeof legacy === 'string' ? legacy.trim() || undefined : undefined)
            ?? this.data.providerDefaults?.[key] ?? fallback;
    };

    readonly setVoice = (key: string, value: any) => {
        if (!this.providerRef) return;
        if (!this.hasField('tts_voice_settings')) {
            if (key === 'voice') this.setField('tts_voice', value);
            return;
        }
        const settings = this.draft.tts_voice_settings ?? {};
        this.setField('tts_voice_settings', { ...settings, [this.providerRef]: { ...settings[this.providerRef], [key]: value } });
    };

    chooseAvatar(): void {
        this.dialog.open(AvatarCatalogDialogComponent, {
            width: '53rem', maxWidth: '95vw',
            data: { currentAvatarPath: this.draft.avatar, defaultAvatarPath: this.data.profile.default_avatar },
        }).afterClosed().subscribe((result?: AvatarCatalogResult) => {
            if (result) this.setField('avatar', result.avatarPath);
        });
    }

    setVolume(percent: number | null): void {
        if (percent !== null && Number.isFinite(percent)) {
            this.setField('tts_postprocessing', { ...this.draft.tts_postprocessing, volume: Math.min(200, Math.max(0, percent)) / 100 });
        }
    }

    async save(): Promise<void> {
        if (this.saving) return;
        this.saving = true;
        this.error = '';
        try {
            if (Object.keys(this.changes).length) {
                await this.config.updatePluginCharacter(this.data.profile.plugin_guid, this.changes);
            }
            this.ref.close();
        } catch {
            this.error = 'Could not save this plugin character. Your edits are still here.';
        } finally {
            this.saving = false;
        }
    }
}
