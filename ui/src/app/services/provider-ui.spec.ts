import { isOpenAIVoiceId } from "../components/character-settings/character-settings.component";
import { ConfigService } from "./config.service";
import { filterProvidersForSlot, ModelProviderDefinition } from "./plugin-settings";
import { TauriService } from "./tauri.service";
import { EMPTY } from "rxjs";
import { bundledDefaultVoice, bundledVoiceCatalog } from "./bundled-provider-ui";
import { TestBed } from "@angular/core/testing";
import { SettingsGridComponent } from "../components/settings-grid/settings-grid.component";
import { SettingsGrid } from "./plugin-settings";

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

    it("recognizes unknown OpenAI voice IDs for preservation", () => {
        expect(isOpenAIVoiceId("nova")).toBeTrue();
        expect(isOpenAIVoiceId("future-custom-voice")).toBeFalse();
    });

    it("keeps bundled voice policy out of provider metadata", () => {
        const openAI = "plugin:7f6f8e98-576f-4d1d-9d87-0f8f7f2f3c61:tts";
        const edge = "plugin:e2d57ec0-56f5-45de-88ed-621d4a28d7b5:tts";
        expect(bundledVoiceCatalog(openAI)).toBe("openai");
        expect(bundledDefaultVoice(openAI)).toBe("nova");
        expect(bundledVoiceCatalog(edge)).toBe("edge");
        expect(bundledDefaultVoice(edge)).toBe("en-US-AvaMultilingualNeural");
        expect(bundledVoiceCatalog("plugin:third-party:tts")).toBeNull();
        expect(bundledDefaultVoice("plugin:third-party:tts")).toBeNull();
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
