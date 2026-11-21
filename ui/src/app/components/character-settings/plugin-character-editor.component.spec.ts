import { MatDialog, MatDialogRef } from '@angular/material/dialog';
import { of, Subject } from 'rxjs';
import { chatSpeakerName, ChatMessage } from '../../services/chat.service';
import { ConfigService, PluginCharacter } from '../../services/config.service';
import { ModelProviderDefinition } from '../../services/plugin-settings';
import { BaseMessage, TauriService } from '../../services/tauri.service';
import { PluginCharacterEditorComponent } from './plugin-character-editor.component';

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
            providerDefaults: { speed: 1.2 },
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

    it('replaces profiles on broadcast, clears on backend restart, and sends a plugin-only patch', async () => {
        const output$ = new Subject<BaseMessage>();
        const tauri = jasmine.createSpyObj<TauriService>('tauri', ['send_command'], { output$ });
        const config = new ConfigService(tauri);
        const snapshots: PluginCharacter[][] = [];
        config.pluginCharacters$.subscribe(profiles => snapshots.push(profiles));
        const { profile } = setup();
        const broadcast = { type: 'plugin_characters', index: 0, timestamp: new Date().toISOString(), characters: [profile] };
        output$.next(broadcast);
        output$.next({ type: 'ready' } as BaseMessage);
        expect(snapshots).toEqual([[], [profile], []]);
        const result = config.updatePluginCharacter('copilot', { name: 'Tower' });
        const request = tauri.send_command.calls.mostRecent().args[0];
        output$.next({ ...broadcast, type: 'plugin_character_saved', request_id: request['request_id'], saved: true });
        await result;
        expect(tauri.send_command).toHaveBeenCalledWith(jasmine.objectContaining({
            type: 'change_plugin_character', plugin_guid: 'copilot', character: { name: 'Tower' },
        }));
    });

    it('shows the speaker before falling back to a legacy plugin label or assistant role', () => {
        const message = { role: 'plugin', plugin_event_name: 'EdCoPilotEvent' } as ChatMessage;
        expect(chatSpeakerName(message)).toBe('EDCoPilot');
        expect(chatSpeakerName({ ...message, display_name: 'Tower' })).toBe('Tower');
        expect(chatSpeakerName({ ...message, role: 'covas', display_name: 'Pilot' })).toBe('Pilot');
    });
});
