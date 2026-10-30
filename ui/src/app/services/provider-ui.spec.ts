import { ConfigService } from "./config.service";
import {
    filterProvidersForSlot,
    ModelProviderDefinition,
    providerVoiceDisplayValue,
    providerVoiceSettingsValues,
    voiceSettingsContext,
} from "./plugin-settings";
import { TauriService } from "./tauri.service";
import { EMPTY } from "rxjs";
import { TestBed } from "@angular/core/testing";
import { SettingsGridComponent } from "../components/settings-grid/settings-grid.component";
import { SettingsGrid } from "./plugin-settings";
import { PluginUIService } from "./plugin-ui.service";
import { TranslateModule } from "@ngx-translate/core";
import { CharacterSettingsComponent } from "../components/character-settings/character-settings.component";
import { GeneralSettingsComponent } from "../components/general-settings/general-settings.component";
import { AdvancedSettingsComponent } from "../components/advanced-settings/advanced-settings.component";

describe("provider UI compatibility", () => {
    const provider = (
        id: string,
        slots?: ModelProviderDefinition["slots"],
    ): ModelProviderDefinition => ({
        kind: "llm",
        id,
        label: id,
        plugin_guid: "plugin",
        is_builtin: false,
        settings_config: [],
        slots,
    });

    it("keeps metadata-free providers and filters slot-specific providers", () => {
        const legacy = provider("legacy");
        const main = provider("main", ["llm"]);
        const agent = provider("agent", ["agent_llm"]);

        expect(filterProvidersForSlot([legacy, main, agent], "llm")).toEqual([legacy, main]);
        expect(filterProvidersForSlot([legacy, main, agent], "agent_llm")).toEqual([legacy, agent]);
    });

    it("merges plugin globals into voice conditions with character values taking precedence", () => {
        const globals = { tts_model: "global-model", instructions: "global style", enabled: true };
        const character = { instructions: "", enabled: false };
        expect(voiceSettingsContext(globals, character)).toEqual({
            tts_model: "global-model", instructions: "", enabled: false,
        });
        const tts = { ...provider("tts"), kind: "tts" } as ModelProviderDefinition;
        const instance = Object.create(CharacterSettingsComponent.prototype) as CharacterSettingsComponent;
        instance.pluginTTSProviders = [tts];
        instance.config = {
            tts_provider: "plugin:plugin:tts", plugin_settings: { plugin: globals },
        } as any;
        instance.activeCharacter = {
            tts_voice_settings: { "plugin:plugin:tts": character },
        } as any;
        expect(instance.getVoiceSettingValue("tts_model", undefined)).toBe("global-model");
        expect(instance.getVoiceSettingValue("instructions", "default")).toBe("");
        expect(instance.getVoiceSettingValue("enabled", undefined)).toBeFalse();
        expect(instance.getVoiceSettingValue("missing", undefined)).toBeUndefined();
        expect(globals.instructions).toBe("global style");
    });

    it("routes provider buttons with the owning plugin GUID", async () => {
        const tauri = jasmine.createSpyObj<TauriService>("TauriService", ["send_command"]);
        Object.defineProperty(tauri, "output$", { value: EMPTY });
        tauri.send_command.and.resolveTo();
        const service = new ConfigService(tauri, {} as PluginUIService);

        await service.clickPluginSettingsButton("owner-guid", "refresh-models");

        expect(tauri.send_command).toHaveBeenCalledWith(jasmine.objectContaining({
            type: "plugin_settings_button",
            plugin_guid: "owner-guid",
            key: "refresh-models",
        }));
    });

    it("resolves character voice settings from provider metadata", () => {
        const tts: ModelProviderDefinition = {
            ...provider("tts"),
            kind: "tts",
            voice_settings_config: [{
                key: "voice",
                label: "Voice",
                fields: [{
                    key: "voice", label: "Voice", type: "select", readonly: false,
                    placeholder: null, default_value: "default-voice", max_length: null,
                    min_length: null, hidden: false, multi_select: false,
                    select_options: [
                        { key: "default", label: "Default Voice", value: "default-voice", disabled: false },
                        { key: "character", label: "Character Voice", value: "character-voice", disabled: false },
                    ],
                }, {
                    key: "instructions", label: "Instructions", type: "textarea", readonly: false,
                    placeholder: null, default_value: "", max_length: null,
                    min_length: null, hidden: false,
                }],
            }] as SettingsGrid[],
        };
        const providerRef = "plugin:plugin:tts";

        expect(providerVoiceSettingsValues(providerRef, [tts], undefined)).toEqual({
            voice: "default-voice",
            instructions: "",
        });
        expect(providerVoiceSettingsValues(providerRef, [tts], {
            [providerRef]: { voice: "character-voice" },
        })).toEqual({ voice: "character-voice", instructions: "" });
        expect(providerVoiceSettingsValues("plugin:plugin:legacy", [provider("legacy")], undefined)).toEqual({});
        expect(providerVoiceDisplayValue(providerRef, [tts], undefined)).toBe("Default Voice");
        expect(providerVoiceDisplayValue(providerRef, [tts], {
            [providerRef]: { voice: "character-voice" },
        })).toBe("Character Voice");
        const globals = { plugin: { voice: "character-voice", instructions: "global style" } };
        expect(providerVoiceDisplayValue(providerRef, [tts], undefined, globals)).toBe("Character Voice");
        expect(providerVoiceSettingsValues(providerRef, [tts], undefined, globals)).toEqual({
            voice: "character-voice", instructions: "global style",
        });
        expect(providerVoiceSettingsValues(providerRef, [tts], {
            [providerRef]: { voice: "default-voice", instructions: "" },
        }, globals)).toEqual({ voice: "default-voice", instructions: "" });

        const instance = Object.create(CharacterSettingsComponent.prototype) as CharacterSettingsComponent;
        instance.pluginTTSProviders = [tts, { ...tts, id: "other", plugin_guid: "other" }];
        instance.activeCharacter = {
            tts_voice: "stale-legacy-voice",
            tts_voice_settings: { [providerRef]: { voice: "character-voice" } },
        } as any;
        instance.config = { tts_provider: "plugin:other:other", plugin_settings: {} } as any;
        expect(instance.getVoiceSettingValue("voice", "default-voice")).toBe("default-voice");
        expect(instance.getCharacterVoiceDisplay(instance.activeCharacter!)).toBe("Default Voice");
        instance.config!.plugin_settings = { other: { voice: "character-voice" } };
        expect(instance.getVoiceSettingValue("voice", "default-voice")).toBe("character-voice");
        expect(instance.getCharacterVoiceDisplay(instance.activeCharacter!)).toBe("Character Voice");
        instance.config!.tts_provider = providerRef;
        expect(instance.getVoiceSettingValue("voice", "default-voice")).toBe("character-voice");
    });

    it("distinguishes legacy providers from providers without a voice concept", () => {
        const legacy = { ...provider("legacy"), kind: "tts" } as ModelProviderDefinition;
        const voiceless = {
            ...provider("voiceless"),
            kind: "tts",
            voice_settings_config: [],
        } as ModelProviderDefinition;

        expect(providerVoiceDisplayValue("plugin:plugin:legacy", [legacy], undefined))
            .toBeUndefined();
        expect(providerVoiceDisplayValue("plugin:plugin:legacy", [legacy], {
            "plugin:plugin:legacy": { voice: "plugin-scoped-voice" },
        })).toBe("plugin-scoped-voice");
        expect(providerVoiceSettingsValues("plugin:plugin:voiceless", [voiceless], {
            "plugin:plugin:voiceless": { voice: "stale-voice" },
        })).toEqual({ voice: "stale-voice" });
        expect(providerVoiceDisplayValue("plugin:plugin:voiceless", [voiceless], undefined))
            .toBeUndefined();
    });

    for (const component of [GeneralSettingsComponent, AdvancedSettingsComponent]) {
        it(`${component.name} switches providers without persisting inherited voice defaults`, async () => {
            const instance = Object.create(component.prototype) as any;
            instance.onConfigChange = jasmine.createSpy().and.resolveTo();
            instance.characterService = jasmine.createSpyObj("CharacterService", ["getCurrentCharacter", "setTtsProviderVoiceSettings"]);
            await instance.onTtsProviderChange("plugin:new:tts");
            expect(instance.onConfigChange).toHaveBeenCalledWith({ tts_provider: "plugin:new:tts" });
            expect(instance.characterService.setTtsProviderVoiceSettings).not.toHaveBeenCalled();

            instance.config = {};
            instance.apiKeyDetectionService = { buildUpdate: () => ({ label: "provider", update: { tts_provider: "plugin:new:tts" } }) };
            await instance.onApiKeyChange("key");
            expect(instance.characterService.setTtsProviderVoiceSettings).not.toHaveBeenCalled();
        });
    }
});

describe("provider settings layout", () => {
    beforeEach(async () => {
        await TestBed.configureTestingModule({ imports: [SettingsGridComponent, TranslateModule.forRoot()] }).compileComponents();
    });

    for (const width of [1280, 375]) {
        it(`renders the provider grid at ${width}px`, () => {
            window.resizeTo(width, 800);
            const fixture = TestBed.createComponent(SettingsGridComponent);
            fixture.componentInstance.gridClass = "plugin-provider-settings";
            fixture.componentInstance.grid = {
                key: "provider",
                label: "Provider",
                fields: [{
                    key: "info",
                    label: "Information",
                    type: "paragraph",
                    readonly: true,
                    placeholder: null,
                    content: "Provider information",
                }],
            } as SettingsGrid;
            fixture.componentInstance.getValue = (_key, defaultValue) => defaultValue;
            fixture.componentInstance.setValue = () => undefined;
            fixture.detectChanges();

            const grid = fixture.nativeElement.querySelector(".plugin-provider-settings") as HTMLElement;
            expect(grid).not.toBeNull();
            expect(getComputedStyle(grid).display).toBe("flex");
            expect(grid.textContent).toContain("Provider information");
        });
    }
});
