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
import { CharacterSettingsComponent } from "../components/character-settings/character-settings.component";

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
        const service = new ConfigService(tauri);

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
        expect(providerVoiceSettingsValues("plugin:plugin:legacy", [provider("legacy")], undefined)).toBeUndefined();
        expect(providerVoiceDisplayValue(providerRef, [tts], undefined, "legacy-voice")).toBe("Default Voice");
        expect(providerVoiceDisplayValue(providerRef, [tts], {
            [providerRef]: { voice: "character-voice" },
        }, "legacy-voice")).toBe("Character Voice");
    });

    it("distinguishes legacy providers from providers without a voice concept", () => {
        const legacy = { ...provider("legacy"), kind: "tts" } as ModelProviderDefinition;
        const voiceless = {
            ...provider("voiceless"),
            kind: "tts",
            voice_settings_config: [],
        } as ModelProviderDefinition;

        expect(providerVoiceDisplayValue("plugin:plugin:legacy", [legacy], undefined, "legacy-voice"))
            .toBe("legacy-voice");
        expect(providerVoiceSettingsValues("plugin:plugin:voiceless", [voiceless], {
            "plugin:plugin:voiceless": { voice: "stale-voice" },
        })).toEqual({});
        expect(providerVoiceDisplayValue("plugin:plugin:voiceless", [voiceless], undefined, "legacy-voice"))
            .toBeUndefined();
    });
});

describe("provider settings layout", () => {
    beforeEach(async () => {
        await TestBed.configureTestingModule({ imports: [SettingsGridComponent] }).compileComponents();
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
