import { Injectable, OnDestroy } from "@angular/core";
import { filter, Subscription } from "rxjs";

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
    cachedTokens: number;
    reasoningTokens: number;
    liveInputTokens: number;
    visibleOutputTokens: number;
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
    raw: Record<string, unknown>;
}

type PendingRequest = {
    resolve: (data: PersistedModelUsageHistoryData) => void;
    reject: (error: Error) => void;
    timeoutId: number;
};

const REQUEST_TIMEOUT_MS = 15000;

@Injectable({
    providedIn: "root",
})
export class ModelUsageService implements OnDestroy {
    private responseSubscription: Subscription;
    private pendingRequests: PendingRequest[] = [];
    private historyCache = new Map<string, ModelUsageRecord[]>();

    constructor(private tauriService: TauriService) {
        this.responseSubscription = this.tauriService.output$
            .pipe(
                filter(
                    (message): message is ModelUsageHistoryMessage =>
                        message.type === "model_usage_history",
                ),
            )
            .subscribe((message) => {
                const pending = this.pendingRequests.shift();
                if (!pending) {
                    return;
                }
                window.clearTimeout(pending.timeoutId);
                pending.resolve(
                    (message.data ?? {}) as PersistedModelUsageHistoryData,
                );
            });
    }

    ngOnDestroy(): void {
        this.responseSubscription.unsubscribe();
        for (const pending of this.pendingRequests) {
            window.clearTimeout(pending.timeoutId);
            pending.reject(new Error("Model usage service destroyed"));
        }
        this.pendingRequests = [];
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

        const usageKind = query.usageKind ?? "llm";
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
            usageKind: query.usageKind ?? "llm",
            from: query.from ?? null,
            to: query.to ?? null,
        });
    }

    private requestHistoryPage(
        message: GetModelUsageHistoryMessage,
    ): Promise<PersistedModelUsageHistoryData> {
        return new Promise(async (resolve, reject) => {
            const pending: PendingRequest = {
                resolve,
                reject,
                timeoutId: window.setTimeout(() => {
                    const index = this.pendingRequests.indexOf(pending);
                    if (index >= 0) {
                        this.pendingRequests.splice(index, 1);
                    }
                    reject(new Error("Timed out waiting for model usage history"));
                }, REQUEST_TIMEOUT_MS),
            };

            this.pendingRequests.push(pending);

            try {
                await this.tauriService.send_command(message);
            } catch (error) {
                window.clearTimeout(pending.timeoutId);
                const index = this.pendingRequests.indexOf(pending);
                if (index >= 0) {
                    this.pendingRequests.splice(index, 1);
                }
                reject(
                    error instanceof Error
                        ? error
                        : new Error(String(error)),
                );
            }
        });
    }

    private buildTokenUsage(modelUsage: Record<string, unknown>): TokenUsageBreakdown {
        const inputTokens = this.toNumber(modelUsage["input_tokens"]);
        const outputTokens = this.toNumber(modelUsage["output_tokens"]);
        const cachedTokens = this.toNumber(modelUsage["cached_tokens"]);
        const reasoningTokens = this.toNumber(modelUsage["reasoning_tokens"]);

        return {
            inputTokens,
            outputTokens,
            totalTokens: this.toNumber(modelUsage["total_tokens"]),
            cachedTokens,
            reasoningTokens,
            liveInputTokens: Math.max(inputTokens - cachedTokens, 0),
            visibleOutputTokens: outputTokens,
        };
    }

    private normalizeRow(row: PersistedModelUsageRow): ModelUsageRecord {
        const payload = this.asObject(row.payload);
        const modelUsage = this.asObject(payload["model_usage"]);
        const promptUsage = this.asObject(payload["prompt_usage"]);

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
        return typeof value === "number" && Number.isFinite(value) ? value : 0;
    }

    private toString(value: unknown, fallback: string): string {
        return typeof value === "string" && value.trim().length > 0
            ? value
            : fallback;
    }
}
