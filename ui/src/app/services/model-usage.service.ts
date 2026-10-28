import { Injectable, OnDestroy } from "@angular/core";
import { filter, Subscription } from "rxjs";
import { measurement, reportedTokenUsage } from "./telemetry";

import {
    GetModelUsageHistoryMessage,
    ModelUsageHistoryMessage,
    TauriService,
} from "./tauri.service";

export type TimeWindowPreset = "24h" | "7d" | "30d" | "all" | "custom";

export interface ModelUsageWindowQuery {
    usageKind?: string;
    from?: string | null;
    to?: string | null;
}

export type UsageKind = "llm" | "stt" | "tts";

interface PersistedModelUsageRow {
    id: number;
    timestamp: string;
    usage_kind: string;
    payload: Record<string, unknown>;
    inserted_at: number | null;
}

interface PersistedModelUsageHistoryData {
    rows?: PersistedModelUsageRow[];
    total?: number;
    limit?: number;
    offset?: number;
    error?: string;
}

export interface PromptUsageBreakdown {
    systemChars: number;
    memoryChars: number;
    statusChars: number;
    conversationChars: number;
    webSearchChars: number;
    genuiChars: number;
    reuseChars: number;
    totalChars: number;
}

export interface TokenUsageBreakdown {
    inputTokens: number;
    outputTokens: number;
    totalTokens: number;
    hasReportedTotal: boolean;
    cachedTokens: number;
    reasoningTokens: number;
    stackedReasoningTokens: number;
    effectiveOutputTokens: number | null;
    liveInputTokens: number;
    visibleOutputTokens: number;
}

export interface LatencyUsageBreakdown {
    responseMs: number | null;
    timeToFirstTokenMs: number | null;
    timeToFirstByteMs: number | null;
}

export interface AudioUsageBreakdown {
    inputAudioDurationMs: number | null;
    outputAudioDurationMs: number | null;
}

export interface TextUsageBreakdown {
    inputChars: number | null;
    outputChars: number | null;
}

export interface CacheUsageBreakdown {
    llmCallsSaved: number;
    llmCallsAdded: number;
}

export interface ModelUsageRecord {
    id: number;
    timestamp: string;
    timestampMs: number;
    usageKind: string;
    messageType: string;
    context: string;
    provider: string;
    modelName: string;
    tokenUsage: TokenUsageBreakdown;
    promptUsage: PromptUsageBreakdown;
    latencyUsage: LatencyUsageBreakdown;
    audioUsage: AudioUsageBreakdown;
    textUsage: TextUsageBreakdown;
    cacheUsage: CacheUsageBreakdown;
    retryAttempts: number;
    status: "success" | "error" | "cancelled" | "unknown";
    errorKind: string;
    operationMs: number | null;
    inputLanguage: string | null;
    outputLanguage: string | null;
    outputVoice: string | null;
    numUnderruns: number | null;
    raw: Record<string, unknown>;
}

type PendingRequest = {
    resolve: (data: PersistedModelUsageHistoryData) => void;
    reject: (error: Error) => void;
    timeoutId: number;
};

const REQUEST_TIMEOUT_MS = 15000;

export function normalizeTokenUsage(modelUsage: Record<string, unknown>): TokenUsageBreakdown {
    const facts = reportedTokenUsage(modelUsage);
    const inputTokens = facts.inputTokens ?? 0, outputTokens = facts.outputTokens ?? 0;
    const cachedTokens = facts.cachedTokens ?? 0, reasoningTokens = facts.reasoningTokens ?? 0;
    const includesReasoning = facts.reasoningIncluded;
    return {
        inputTokens, outputTokens, cachedTokens, reasoningTokens,
        totalTokens: facts.totalTokens ?? 0,
        hasReportedTotal: facts.totalTokens !== null,
        effectiveOutputTokens: facts.effectiveOutputTokens,
        liveInputTokens: Math.max(inputTokens - cachedTokens, 0),
        visibleOutputTokens: includesReasoning === true ? Math.max(outputTokens - reasoningTokens, 0) : outputTokens,
        // Unknown provider semantics are shown as overlapping reported views,
        // never stacked on top of output where they may be counted twice.
        stackedReasoningTokens: includesReasoning === null ? 0 : reasoningTokens,
    };
}

@Injectable({
    providedIn: "root",
})
export class ModelUsageService implements OnDestroy {
    private responseSubscription: Subscription;
    private pendingRequests = new Map<string, PendingRequest>();
    private historyCache = new Map<string, ModelUsageRecord[]>();
    private nextRequestId = 0;

    constructor(private tauriService: TauriService) {
        this.responseSubscription = this.tauriService.output$
            .pipe(
                filter(
                    (message): message is ModelUsageHistoryMessage =>
                        message.type === "model_usage_history",
                ),
            )
            .subscribe((message) => {
                const pending = this.pendingRequests.get(message.request_id);
                if (!pending) {
                    return;
                }
                this.pendingRequests.delete(message.request_id);
                window.clearTimeout(pending.timeoutId);
                pending.resolve(
                    (message.data ?? {}) as PersistedModelUsageHistoryData,
                );
            });
    }

    ngOnDestroy(): void {
        this.responseSubscription.unsubscribe();
        for (const pending of this.pendingRequests.values()) {
            window.clearTimeout(pending.timeoutId);
            pending.reject(new Error("Model usage service destroyed"));
        }
        this.pendingRequests.clear();
    }

    public clearCache(): void {
        this.historyCache.clear();
    }

    public async getUsageHistory(
        query: ModelUsageWindowQuery,
    ): Promise<ModelUsageRecord[]> {
        const cacheKey = this.getCacheKey(query);
        const cached = this.historyCache.get(cacheKey);
        if (cached) {
            return cached;
        }

        const usageKind = query.usageKind;
        const allRows: ModelUsageRecord[] = [];
        const limit = 1000;
        let offset = 0;
        let total = Number.POSITIVE_INFINITY;

        while (allRows.length < total) {
            const response = await this.requestHistoryPage({
                type: "get_model_usage_history",
                usage_kind: usageKind,
                from: query.from ?? undefined,
                to: query.to ?? undefined,
                limit,
                offset,
                timestamp: new Date().toISOString(),
            });

            if (response.error) {
                throw new Error(response.error);
            }

            const rows = Array.isArray(response.rows) ? response.rows : [];
            total = typeof response.total === "number" ? response.total : rows.length;
            allRows.push(...rows.map((row) => this.normalizeRow(row)));

            if (rows.length === 0) {
                break;
            }

            offset += typeof response.limit === "number" ? response.limit : limit;
        }

        this.historyCache.set(cacheKey, allRows);
        return allRows;
    }

    private getCacheKey(query: ModelUsageWindowQuery): string {
        return JSON.stringify({
            usageKind: query.usageKind ?? null,
            from: query.from ?? null,
            to: query.to ?? null,
        });
    }

    private requestHistoryPage(
        message: GetModelUsageHistoryMessage,
    ): Promise<PersistedModelUsageHistoryData> {
        return new Promise((resolve, reject) => {
            void this.sendHistoryRequest(message, resolve, reject);
        });
    }

    private async sendHistoryRequest(
        message: GetModelUsageHistoryMessage,
        resolve: (data: PersistedModelUsageHistoryData) => void,
        reject: (error: Error) => void,
    ): Promise<void> {
        try {
            await this.tauriService.waitForBackendCommandReady();
            const requestId = `${Date.now()}-${this.nextRequestId++}`;
            const pending: PendingRequest = {
                resolve,
                reject,
                timeoutId: window.setTimeout(() => {
                    if (this.pendingRequests.delete(requestId)) {
                        reject(
                            new Error(
                                "Timed out waiting for model usage history",
                            ),
                        );
                    }
                }, REQUEST_TIMEOUT_MS),
            };

            this.pendingRequests.set(requestId, pending);

            try {
                await this.tauriService.send_command({
                    ...message,
                    request_id: requestId,
                });
            } catch (error) {
                window.clearTimeout(pending.timeoutId);
                this.pendingRequests.delete(requestId);
                reject(
                    error instanceof Error
                        ? error
                        : new Error(String(error)),
                );
            }
        } catch (error) {
            reject(error instanceof Error ? error : new Error(String(error)));
        }
    }

    private buildTokenUsage(modelUsage: Record<string, unknown>): TokenUsageBreakdown {
        return normalizeTokenUsage(modelUsage);
    }

    private buildLatencyUsage(
        latencyUsage: Record<string, unknown>,
    ): LatencyUsageBreakdown {
        return {
            responseMs: this.toNullableNumber(latencyUsage["response_ms"]),
            timeToFirstTokenMs: this.toNullableNumber(
                latencyUsage["time_to_first_token_ms"],
            ),
            timeToFirstByteMs: this.toNullableNumber(
                latencyUsage["time_to_first_byte_ms"],
            ),
        };
    }

    private buildAudioUsage(audioUsage: Record<string, unknown>): AudioUsageBreakdown {
        return {
            inputAudioDurationMs: this.toNullableNumber(
                audioUsage["input_audio_duration_ms"],
            ),
            outputAudioDurationMs: this.toNullableNumber(
                audioUsage["output_audio_duration_ms"],
            ),
        };
    }

    private buildTextUsage(textUsage: Record<string, unknown>): TextUsageBreakdown {
        return {
            inputChars: this.toNullableNumber(textUsage["input_chars"]),
            outputChars: this.toNullableNumber(textUsage["output_chars"]),
        };
    }

    private buildCacheUsage(
        cacheUsage: Record<string, unknown>,
    ): CacheUsageBreakdown {
        return {
            llmCallsSaved: this.toNumber(cacheUsage["llm_calls_saved"]),
            llmCallsAdded: this.toNumber(cacheUsage["llm_calls_added"]),
        };
    }

    private normalizeRow(row: PersistedModelUsageRow): ModelUsageRecord {
        const payload = this.asObject(row.payload);
        const modelUsage = this.asObject(payload["model_usage"]);
        const promptUsage = this.asObject(payload["prompt_usage"]);
        const latencyUsage = this.asObject(payload["latency_usage"]);
        const audioUsage = this.asObject(payload["audio_usage"]);
        const textUsage = this.asObject(payload["text_usage"]);
        const cacheUsage = this.asObject(payload["cache_usage"]);

        const normalizedPromptUsage: PromptUsageBreakdown = {
            systemChars: this.toNumber(promptUsage["system_chars"]),
            memoryChars: this.toNumber(promptUsage["memory_chars"]),
            statusChars: this.toNumber(promptUsage["status_chars"]),
            conversationChars: this.toNumber(promptUsage["conversation_chars"]),
            webSearchChars: this.toNumber(promptUsage["web_search_chars"]),
            genuiChars: this.toNumber(promptUsage["genui_chars"]),
            reuseChars: this.toNumber(promptUsage["reuse_chars"]),
            totalChars: 0,
        };
        normalizedPromptUsage.totalChars = this.toNumber(
            promptUsage["total_prompt_chars"],
        );
        if (normalizedPromptUsage.totalChars <= 0) {
            normalizedPromptUsage.totalChars =
                normalizedPromptUsage.systemChars +
                normalizedPromptUsage.memoryChars +
                normalizedPromptUsage.statusChars +
                normalizedPromptUsage.conversationChars +
                normalizedPromptUsage.webSearchChars +
                normalizedPromptUsage.genuiChars;
        }

        return {
            id: Number(row.id),
            timestamp: String(row.timestamp),
            timestampMs: Date.parse(String(row.timestamp)),
            usageKind: String(row.usage_kind ?? "llm"),
            messageType: this.toString(payload["type"], "llm_usage"),
            context: this.toString(payload["context"], "unknown"),
            provider: this.toString(
                payload["provider"] ?? modelUsage["provider"],
                "unknown",
            ),
            modelName: this.toString(
                payload["model_name"] ?? modelUsage["model_name"],
                "unknown",
            ),
            tokenUsage: this.buildTokenUsage(modelUsage),
            promptUsage: normalizedPromptUsage,
            latencyUsage: this.buildLatencyUsage(latencyUsage),
            audioUsage: this.buildAudioUsage(audioUsage),
            textUsage: this.buildTextUsage(textUsage),
            cacheUsage: this.buildCacheUsage(cacheUsage),
            retryAttempts: this.toNumber(modelUsage["retry_attempts"]),
            status: ["success", "error", "cancelled"].includes(String(payload["status"]))
                ? payload["status"] as "success" | "error" | "cancelled" : "unknown",
            errorKind: this.toString(payload["error_kind"], "unknown"),
            operationMs: this.toNullableNumber(payload["operation_ms"]),
            inputLanguage: typeof payload["input_language"] === "string" ? payload["input_language"] : null,
            outputLanguage: typeof payload["output_language"] === "string" ? payload["output_language"] : null,
            outputVoice: typeof payload["output_voice"] === "string" ? payload["output_voice"] : null,
            numUnderruns: measurement(payload["num_underruns"], true),
            raw: payload,
        };
    }

    private asObject(value: unknown): Record<string, unknown> {
        if (value && typeof value === "object" && !Array.isArray(value)) {
            return value as Record<string, unknown>;
        }
        return {};
    }

    private toNumber(value: unknown): number {
        return measurement(value, true) ?? 0;
    }

    private toNullableNumber(value: unknown): number | null {
        return measurement(value);
    }

    private toString(value: unknown, fallback: string): string {
        return typeof value === "string" && value.trim().length > 0
            ? value
            : fallback;
    }
}
