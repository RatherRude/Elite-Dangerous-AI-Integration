import { BehaviorSubject } from "rxjs";
import { Config, ConfigService } from "./config.service";
import { ApiKeyDetectionService } from "./api-key-detection.service";
import { ModelProviderDefinition } from "./plugin-settings";

describe("ApiKeyDetectionService", () => {
    const config = { plugin_settings: { existing: { value: true } } } as unknown as Config;
    let providers: BehaviorSubject<ModelProviderDefinition[]>;
    let currentConfig: Config;
    let service: ApiKeyDetectionService;

    beforeEach(() => {
        providers = new BehaviorSubject<ModelProviderDefinition[]>([]);
        currentConfig = config;
        service = new ApiKeyDetectionService({
            plugin_model_providers$: providers.asObservable(),
            getCurrentConfig: () => currentConfig,
        } as ConfigService);
    });

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

    it("trims whitespace from pasted keys before matching and storing them", () => {
        const openAI = provider("openai", "OpenAI", "^sk-[A-Za-z0-9]{8,}$", 10);
        const result = service.buildUpdate("  sk-12345678\r\n", config, [openAI]);

        expect(result.label).toBe("OpenAI");
        expect(result.update.api_key).toBe("sk-12345678");
        expect(result.update.plugin_settings?.["openai"]?.api_key).toBe("sk-12345678");
    });

    it("reapplies provider selections when another key from the same provider is pasted", async () => {
        const openAI = provider("openai", "OpenAI", "^sk-[A-Za-z0-9]{8,}$", 10);
        providers.next([openAI]);
        await service.buildUpdateWhenReady("sk-12345678");
        currentConfig = {
            ...config,
            llm_provider: "plugin:custom:llm",
            stt_provider: "plugin:custom:stt",
        };

        const result = (await service.buildUpdateWhenReady("  sk-87654321\r\n", true))!;

        expect(result.label).toBe("OpenAI");
        expect(result.update.llm_provider).toBe("plugin:openai:llm");
        expect(result.update.stt_provider).toBe("none");
        expect(result.update.plugin_settings?.["openai"]?.api_key).toBe("sk-87654321");
    });

    it("can reconfigure the same pasted key after a manual provider change", () => {
        const openAI = provider("openai", "OpenAI", "^sk-[A-Za-z0-9]{8,}$", 10);
        service.buildUpdate("sk-12345678", config, [openAI]);

        const result = service.buildUpdate("sk-12345678", config, [openAI], true);

        expect(result.update.llm_provider).toBe("plugin:openai:llm");
        expect(result.update.tts_provider).toBe("plugin:edge:tts");
    });

    it("waits for startup metadata and configures STT and its shared key atomically", async () => {
        const openAI = provider("openai", "OpenAI", "^sk-[A-Za-z0-9]{8,}$", 10);
        openAI.api_key_detection!.provider_selections = {
            llm_provider: "llm", agent_llm_provider: "agent-llm", stt_provider: "stt",
            vision_provider: "vlm", embedding_provider: "embedding", tts_provider: "plugin:edge:tts",
        };
        let resolved = false;
        const pending = service.buildUpdateWhenReady("sk-12345678").then(result => {
            resolved = true;
            return result;
        });
        await Promise.resolve();
        expect(resolved).toBeFalse();

        // Preserve settings received while plugin metadata was still loading.
        currentConfig = { ...config, plugin_settings: { latest: { value: true } } };
        providers.next([openAI]);
        const result = (await pending)!;
        expect(result.update.stt_provider).toBe("plugin:openai:stt");
        expect(result.update.plugin_settings?.["openai"]?.api_key).toBe("sk-12345678");
        expect(result.update.plugin_settings?.["latest"]).toEqual({ value: true });
    });

    it("discards superseded edits while waiting for startup metadata", async () => {
        const openAI = provider("openai", "OpenAI", "^sk-[A-Za-z0-9]{8,}$", 10);
        const first = service.buildUpdateWhenReady("sk-12345678");
        const second = service.buildUpdateWhenReady("sk-123456789");
        providers.next([openAI]);

        expect(await first).toBeNull();
        const result = (await second)!;
        expect(result.update.api_key).toBe("sk-123456789");
        expect(result.update.llm_provider).toBe("plugin:openai:llm");
    });
});
