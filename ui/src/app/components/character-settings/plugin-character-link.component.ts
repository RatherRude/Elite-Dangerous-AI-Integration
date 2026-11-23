import { Component, Input, OnChanges, OnDestroy } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { firstValueFrom } from 'rxjs';
import { AvatarService } from '../../services/avatar.service';
import { ConfigService, PluginCharacter } from '../../services/config.service';
import { hostPresentsSpeech, selectedSpeechProvider } from '../../services/plugin-settings';
import { PluginCharacterEditorComponent } from './plugin-character-editor.component';

@Component({
    selector: 'app-plugin-character-link', standalone: true, imports: [MatButtonModule],
    template: `<button mat-stroked-button (click)="edit()">
        @if (avatarUrl) { <img [src]="avatarUrl" alt=""> }
        Edit {{ profile.character.name || 'character' }}
    </button> @if (profile.description) { <span>{{ profile.description }}</span> }`,
    styles: [':host { display: flex; align-items: center; gap: .75rem; flex-wrap: wrap; } img { width: 1.75rem; height: 1.75rem; object-fit: contain; vertical-align: middle; }'],
})
export class PluginCharacterLinkComponent implements OnChanges, OnDestroy {
    @Input({required: true}) profile!: PluginCharacter;
    avatarUrl: string | null = null;
    private avatarRef?: string;

    constructor(private config: ConfigService, private dialog: MatDialog, private avatars: AvatarService) {}

    async ngOnChanges() {
        const ref = this.profile.character.avatar || this.profile.default_avatar || '';
        if (ref === this.avatarRef) return;
        this.release(this.avatarUrl);
        this.avatarUrl = null;
        this.avatarRef = ref;
        const url = await this.avatars.getAvatar(ref).catch(() => null);
        if (ref === this.avatarRef && !this.avatarUrl) this.avatarUrl = url;
        else this.release(url);
    }

    ngOnDestroy() {
        this.avatarRef = undefined;
        this.release(this.avatarUrl);
        this.avatarUrl = null;
    }

    private release(url: string | null) {
        if (url && this.avatars.isObjectUrl(url)) URL.revokeObjectURL(url);
    }

    async edit() {
        const config = this.config.getCurrentConfig();
        const provider = selectedSpeechProvider(config?.tts_provider, await firstValueFrom(this.config.plugin_model_providers$));
        this.dialog.open(PluginCharacterEditorComponent, {
            width: '38rem', maxWidth: '95vw',
            data: { profile: this.profile, provider: provider ?? null,
                hostSpeech: hostPresentsSpeech(config?.tts_provider, provider),
                providerDefaults: provider && config?.plugin_settings?.[provider.plugin_guid] },
        });
    }
}
