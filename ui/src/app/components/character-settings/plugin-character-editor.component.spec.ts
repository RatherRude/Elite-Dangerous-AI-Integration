import { MAT_DIALOG_DATA, MatDialog, MatDialogRef } from '@angular/material/dialog';
import { TestBed } from '@angular/core/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { of, Subject } from 'rxjs';
import { chatSpeakerName, ChatMessage } from '../../services/chat.service';
import { ConfigService, PluginCharacter } from '../../services/config.service';
import { ModelProviderDefinition } from '../../services/plugin-settings';
import { BaseMessage, TauriService } from '../../services/tauri.service';
import { PluginCharacterEditorComponent } from './plugin-character-editor.component';
import { PluginCharacterLinkComponent } from './plugin-character-link.component';
import { hostPresentsSpeech, selectedSpeechProvider } from '../../services/plugin-settings';
import { AvatarService } from '../../services/avatar.service';

describe('Plugin character editing', () => {
    const providerRef = 'plugin:synth:tts';
    function setup() {
        const profile: PluginCharacter = {
            plugin_guid: 'copilot', active: true, default_avatar: 'copilot.svg', settings_config: [],
            character: { name: 'CoPilot', avatar: '', read_commentary: false, tts_voice_settings: {
                [providerRef]: { voice: 'Pilot' }, other: { voice: 'Other' },
            } },
        };
        const config = jasmine.createSpyObj<ConfigService>('config', ['updatePluginCharacter']);
        const dialog = jasmine.createSpyObj<MatDialog>('dialog', ['open']);
        const ref = jasmine.createSpyObj<MatDialogRef<PluginCharacterEditorComponent>>('ref', ['close']);
        const editor = new PluginCharacterEditorComponent({
            profile, provider: { plugin_guid: 'synth', id: 'tts' } as ModelProviderDefinition,
            providerDefaults: { speed: 1.2 }, hostSpeech: true,
        }, config, dialog, ref);
        return { editor, config, ref, profile, dialog };
    }

    it('edits the plugin only and preserves other providers and the original until saved', async () => {
        const { editor, profile, config, ref } = setup();
        expect(editor.getVoice('speed', 1)).toBe(1.2);
        editor.setVoice('voice', 'Tower');
        editor.setField('read_commentary', true);
        editor.setField('active_character_index', 4);
        expect(profile.character.tts_voice_settings?.[providerRef]['voice']).toBe('Pilot');
        await editor.save();
        expect(config.updatePluginCharacter).toHaveBeenCalledOnceWith('copilot', {
            read_commentary: true, tts_voice_settings: { [providerRef]: { voice: 'Tower' }, other: { voice: 'Other' } },
        });
        expect(ref.close).toHaveBeenCalled();
    });

    it('leaves a cancelled avatar selection alone and keeps the draft on send failure', async () => {
        const { editor, config, dialog, ref } = setup();
        dialog.open.and.returnValue({ afterClosed: () => of(undefined) } as any);
        editor.chooseAvatar();
        expect(editor.changes).toEqual({});
        editor.setField('name', 'Tower');
        config.updatePluginCharacter.and.rejectWith(new Error('offline'));
        await editor.save();
        expect(ref.close).not.toHaveBeenCalled();
        expect(editor.draft.name).toBe('Tower');
        expect(editor.error).toBeTruthy();
    });

    it('displays the voice used by playback, including a migrated raw voice', () => {
        const {editor} = setup();
        editor.data.providerDefaults = {voice: 'Global'};
        editor.draft['tts_voice'] = ' Legacy ';
        expect(editor.getVoice('voice', 'Default')).toBe('Pilot');
        editor.draft.tts_voice_settings = {};
        expect(editor.getVoice('voice', 'Default')).toBe('Legacy');
        editor.setVoice('voice', '');
        expect(editor.getVoice('voice', 'Default')).toBe('');
        editor.draft.tts_voice_settings = {};
        editor.draft['tts_voice'] = '';
        expect(editor.getVoice('voice', 'Default')).toBe('Global');
    });

    it('edits a schema-less provider voice even without a legacy field', async () => {
        const {editor, config, ref} = setup();
        await TestBed.configureTestingModule({
            imports: [PluginCharacterEditorComponent, NoopAnimationsModule],
            providers: [{provide: MAT_DIALOG_DATA, useValue: editor.data}, {provide: ConfigService, useValue: config},
                        {provide: MatDialogRef, useValue: ref}],
        }).compileComponents();
        const fixture = TestBed.createComponent(PluginCharacterEditorComponent);
        fixture.detectChanges();
        await fixture.whenStable();
        const fields = Array.from(fixture.nativeElement.querySelectorAll('mat-form-field')) as HTMLElement[];
        const input = fields.find(field => field.querySelector('mat-label')?.textContent === 'Voice')!.querySelector('input')!;
        expect(input.value).toBe('Pilot');
        input.value = 'New voice';
        input.dispatchEvent(new Event('input'));
        await fixture.componentInstance.save();
        expect(config.updatePluginCharacter).toHaveBeenCalledWith('copilot', {
            tts_voice_settings: {[providerRef]: {voice: 'New voice'}, other: {voice: 'Other'}},
        });
    });

    it('replaces profiles on broadcast, clears on backend restart, and sends a plugin-only patch', async () => {
        const output$ = new Subject<BaseMessage>();
        const tauri = jasmine.createSpyObj<TauriService>('tauri', ['send_command'], { output$ });
        const config = new ConfigService(tauri);
        const snapshots: PluginCharacter[][] = [];
        const visible: PluginCharacter[][] = [];
        config.activePluginCharacters$.subscribe(profiles => visible.push(profiles));
        config.pluginCharacters$.subscribe(profiles => snapshots.push(profiles));
        const { profile } = setup();
        const broadcast = { type: 'plugin_characters', index: 0, timestamp: new Date().toISOString(), characters: [profile] };
        output$.next(broadcast);
        output$.next({ ...broadcast, characters: [{...profile, active: false}] } as typeof broadcast);
        output$.next(broadcast);
        output$.next({ type: 'ready' } as BaseMessage);
        expect(visible).toEqual([[], [profile], [], [profile], []]);
        expect(snapshots[2][0].character).toEqual(profile.character);
        const result = config.updatePluginCharacter('copilot', { name: 'Tower' });
        const request = tauri.send_command.calls.mostRecent().args[0];
        output$.next({ ...broadcast, type: 'plugin_character_saved', request_id: request['request_id'], saved: true });
        await result;
        expect(tauri.send_command).toHaveBeenCalledWith(jasmine.objectContaining({
            type: 'change_plugin_character', plugin_guid: 'copilot', character: { name: 'Tower' },
        }));
    });

    it('shows the speaker before falling back to the plugin event or assistant role', () => {
        const message = { role: 'plugin', plugin_event_name: 'TowerNotice' } as ChatMessage;
        expect(chatSpeakerName(message)).toBe('TowerNotice');
        expect(chatSpeakerName({ ...message, display_name: 'Tower' })).toBe('Tower');
        expect(chatSpeakerName({ ...message, role: 'covas', display_name: 'Pilot' })).toBe('Pilot');
    });

    it('uses the plugin’s draft condition without deleting hidden voice settings', () => {
        const { editor, profile } = setup();
        expect(editor.showVoice).toBeTrue();
        editor.setVoice('voice', 'Tower');
        profile.voice_condition = { key: 'name', operator: 'eq', value: 'Tower' };
        expect(editor.showVoice).toBeFalse();
        editor.setField('name', 'Tower');
        expect(editor.showVoice).toBeTrue();
        expect(editor.getVoice('voice', '')).toBe('Tower');
        editor.data.hostSpeech = false;
        expect(editor.showVoice).toBeFalse();
    });

    it('opens the shared editor using the selected provider, not the speaker’s plugin', async () => {
        const { profile, dialog } = setup();
        const provider = { plugin_guid: 'synth', id: 'tts', kind: 'tts', handles_speech_presentation: true } as ModelProviderDefinition;
        const config = jasmine.createSpyObj<ConfigService>('config', ['getCurrentConfig'], {plugin_model_providers$: of([provider])});
        config.getCurrentConfig.and.returnValue({tts_provider: providerRef} as any);
        const entry = new PluginCharacterLinkComponent(config, dialog, {} as AvatarService);
        entry.profile = profile;
        await entry.edit();
        expect(dialog.open).toHaveBeenCalledWith(PluginCharacterEditorComponent, jasmine.objectContaining({
            data: jasmine.objectContaining({profile, provider, hostSpeech: false}),
        }));
        expect(hostPresentsSpeech('plugin:synth:other', selectedSpeechProvider('plugin:synth:other', [provider]))).toBeTrue();
        expect(hostPresentsSpeech('none')).toBeFalse();
    });
});
