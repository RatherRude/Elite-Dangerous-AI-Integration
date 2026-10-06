import { Config } from "./config.service";
import { ApiKeyDetectionService } from "./api-key-detection.service";
import { ModelProviderDefinition } from "./plugin-settings";

describe("ApiKeyDetectionService", () => {
    const service = new ApiKeyDetectionService();
    const config = { plugin_settings: { existing: { value: true } } } as unknown as Config;

    function provider(
        guid: string,
        label: string,
        pattern: string,
        priority: number,
    ): ModelProviderDefinition {
        return {
            kind: "llm",
            id: "llm",
            label,
            settings_config: [],
            plugin_guid: guid,
            is_builtin: true,
            api_key_detection: {
                patterns: [pattern],
                priority,
                setting_key: "api_key",
                provider_selections: {
                    llm_provider: "llm",
                    stt_provider: "none",
                    tts_provider: "plugin:edge:tts",
                },
            },
        };
    }

    it("uses the highest-priority full match and builds one atomic update", () => {
        const generic = provider("openai", "OpenAI", "^sk-.+$", 10);
        const openRouter = provider("openrouter", "OpenRouter", "^sk-or-v1-.+$", 100);

        const result = service.buildUpdate("sk-or-v1-secret", config, [generic, openRouter]);

        expect(result.label).toBe("OpenRouter");
        expect(result.update.api_key).toBe("sk-or-v1-secret");
        expect(result.update.llm_provider).toBe("plugin:openrouter:llm");
        expect(result.update.stt_provider).toBe("none");
        expect(result.update.tts_provider).toBe("plugin:edge:tts");
        expect(result.update.plugin_settings?.["openrouter"]?.api_key).toBe("sk-or-v1-secret");
        expect(result.update.plugin_settings?.["existing"]).toEqual({ value: true });
    });

    it("does not treat partial or malformed patterns as matches", () => {
        const complete = provider("openai", "OpenAI", "^sk-[A-Za-z0-9]{8}$", 10);
        const malformed = provider("bad", "Bad", "[", 100);

        const result = service.buildUpdate("sk-short", config, [malformed, complete]);

        expect(result.label).toBeNull();
        expect(result.update).toEqual({ api_key: "sk-short" });
    });

    it("selects providers only once while a matching key is typed", () => {
        const openAI = provider("openai", "OpenAI", "^sk-[A-Za-z0-9]{8,}$", 10);

        const detected = service.buildUpdate("sk-12345678", config, [openAI]);
        const continued = service.buildUpdate("sk-123456789", config, [openAI]);

        expect(detected.update.llm_provider).toBe("plugin:openai:llm");
        expect(continued.update.api_key).toBe("sk-123456789");
        expect(continued.update.llm_provider).toBeUndefined();
        expect(continued.update.tts_provider).toBeUndefined();
    });
});
