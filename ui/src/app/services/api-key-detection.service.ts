import { Injectable } from "@angular/core";
import { filter, firstValueFrom } from "rxjs";
import { Config, ConfigService } from "./config.service";
import { ModelProviderDefinition } from "./plugin-settings";

export interface ApiKeyDetectionResult {
    label: string | null;
    update: Partial<Config>;
}

@Injectable({ providedIn: "root" })
export class ApiKeyDetectionService {
    private lastDetectedPluginGuid: string | null = null;
    private latestRequest = 0;

    constructor(private configService: ConfigService) {}

    async buildUpdateWhenReady(apiKey: string, configureProviders = false): Promise<ApiKeyDetectionResult | null> {
        const request = ++this.latestRequest;
        // Config is emitted before providers at startup. Do not save a main key
        // without its provider credentials just because metadata is still loading.
        const providers = await firstValueFrom(
            this.configService.plugin_model_providers$.pipe(filter(providers => providers.length > 0)),
        );
        if (request !== this.latestRequest) return null;
        const config = this.configService.getCurrentConfig();
        if (!config) return null;
        return this.buildUpdate(apiKey, config, providers, configureProviders);
    }

    buildUpdate(
        apiKey: string,
        config: Config,
        providers: ModelProviderDefinition[],
        configureProviders = false,
    ): ApiKeyDetectionResult {
        apiKey = apiKey.trim();
        const matches = providers.flatMap((provider, order) => {
            const detection = provider.api_key_detection;
            if (!detection?.patterns?.length) return [];

            const matched = detection.patterns.some((pattern) => {
                try {
                    const match = new RegExp(pattern).exec(apiKey);
                    return match?.index === 0 && match[0].length === apiKey.length;
                } catch {
                    return false;
                }
            });
            return matched ? [{ provider, order, priority: detection.priority ?? 0 }] : [];
        }).sort((a, b) => b.priority - a.priority || a.order - b.order);

        const match = matches[0]?.provider;
        if (!match?.api_key_detection) {
            this.lastDetectedPluginGuid = null;
            return { label: null, update: { api_key: apiKey } };
        }

        const detection = match.api_key_detection;
        const settingKey = detection.setting_key ?? "api_key";
        const currentPluginSettings = config.plugin_settings?.[match.plugin_guid] ?? {};
        const update: Partial<Config> = {
            api_key: apiKey,
            plugin_settings: {
                ...config.plugin_settings,
                [match.plugin_guid]: {
                    ...currentPluginSettings,
                    [settingKey]: apiKey,
                },
            },
        };

        if (configureProviders || this.lastDetectedPluginGuid !== match.plugin_guid) {
            for (const [selector, selection] of Object.entries(detection.provider_selections ?? {})) {
                const resolved = selection === "none" || selection.startsWith("plugin:")
                    ? selection
                    : `plugin:${match.plugin_guid}:${selection}`;
                (update as Record<string, unknown>)[selector] = resolved;
                if (selector === "vision_provider") {
                    update.vision_var = resolved !== "none";
                }
            }
        }
        this.lastDetectedPluginGuid = match.plugin_guid;

        return { label: match.label, update };
    }
}
