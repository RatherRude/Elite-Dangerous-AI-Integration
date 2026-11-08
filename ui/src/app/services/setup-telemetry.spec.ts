import { SetupTelemetry } from "./setup-telemetry";

describe("current setup telemetry", () => {
    it("preserves mode/provider IDs and exports counts/settings without configuration contents", () => {
        const setup = new SetupTelemetry("linux");
        setup.update({ type: "config", config: { ptt_var: "plugin-activation", overlay_mode: "vr",
            llm_provider: "plugin/provider-v2", game_actions_var: false, active_character_index: 1,
            characters: [{ name: "Default" }, { name: "SENSITIVE_NAME", character: "SENSITIVE_PERSONALITY",
                tts_postprocessing: { effects: { custom_effect: { enabled: true, secret: "SENSITIVE_EFFECT" } } } }],
            api_key: "SENSITIVE_KEY", commander_name: "SENSITIVE_COMMANDER", input_device_name: "SENSITIVE_DEVICE",
        } });
        const points = setup.observations();
        expect(JSON.stringify(points)).not.toContain("SENSITIVE_");
        const info = points.find(point => point.name === "covas_setup_snapshot")!;
        expect(info.attributes["os.type"]).toBe("linux");
        expect(info.attributes["input.mode"]).toBe("plugin-activation");
        expect(info.attributes["configured.llm.provider"]).toBe("plugin/provider-v2");
        expect(points.find(point => point.name === "covas_setup_characters" && point.attributes["kind"] === "user_defined")?.value).toBe(1);
        expect(points.find(point => point.name === "covas_setup_feature_enabled" && point.attributes["feature"] === "game_actions")?.value).toBe(0);
        expect(points.find(point => point.name === "covas_setup_feature_enabled" && point.attributes["feature"] === "tts.effect.custom_effect")?.value).toBe(1);
        expect(points.filter(point => point.name.endsWith("observed_at")).every(point => point.value === info.value)).toBeTrue();
    });
    it("replaces stale values and tracks revisions, including zero characters and disabled settings", () => {
        spyOn(Date, "now").and.returnValue(1000);
        const setup = new SetupTelemetry("win32");
        setup.update({ type: "config", config: { ptt_var: "push_to_talk", game_actions_var: true,
            characters: [{ name: "Default" }, { name: "One" }] } });
        setup.update({ type: "running_config", config: { ptt_var: "voice_activation", game_actions_var: false, characters: [] } });
        const points = setup.observations();
        expect(points.find(point => point.name === "covas_setup_snapshot")?.value).toBe(1001);
        expect(points.find(point => point.name === "covas_setup_snapshot")?.attributes["input.mode"]).toBe("voice_activation");
        expect(points.find(point => point.name === "covas_setup_feature_enabled")?.value).toBe(0);
        expect(points.filter(point => point.name === "covas_setup_characters").every(point => point.value === 0)).toBeTrue();
        setup.update({ type: "config", config: { ptt_var: "toggle" } });
        expect(setup.observations("covas_setup_feature_enabled")).toEqual([]);
        expect(setup.observations("covas_setup_characters")).toEqual([]);
    });
    it("does not turn history, logs or missing config into snapshots", () => {
        const setup = new SetupTelemetry("darwin");
        setup.update({ type: "log", config: { characters: [] } });
        setup.update({ type: "config" });
        expect(setup.observations()).toEqual([]);
    });
});
