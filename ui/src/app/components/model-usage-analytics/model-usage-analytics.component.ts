import { CommonModule } from "@angular/common";
import { Component, OnInit } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatDatepickerModule } from "@angular/material/datepicker";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import { MatNativeDateModule } from "@angular/material/core";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatSelectModule } from "@angular/material/select";

import {
    ModelUsageRecord,
    ModelUsageService,
    TimeWindowPreset,
    UsageKind,
} from "../../services/model-usage.service";

type TimelineGranularity = "hour" | "day" | "week";
type UsageKindOption = "all" | UsageKind;

interface SummaryCard {
    label: string;
    value: string;
    detail: string;
    tone: "amber" | "blue" | "mint" | "rose" | "slate" | "violet";
}

interface BreakdownBar {
    label: string;
    value: number;
    valueLabel: string;
    subtitle: string;
    widthPct: number;
    tone: "amber" | "blue" | "mint" | "rose" | "violet" | "slate";
}

interface TimelineSegment {
    cssClass: string;
    heightPct: number;
    label: string;
    value: number;
}

interface TimelineBar {
    label: string;
    displayLabel: string;
    showLabel: boolean;
    totalTokens: number;
    totalChars: number;
    tokenSegments: TimelineSegment[];
    charSegments: TimelineSegment[];
}

interface TimelineBucket {
    bucketStartMs: number;
    label: string;
    displayLabel: string;
    cachedInputTokens: number;
    liveInputTokens: number;
    thinkingOutputTokens: number;
    visibleOutputTokens: number;
    totalTokens: number;
    totalChars: number;
    systemChars: number;
    memoryChars: number;
    statusChars: number;
    conversationChars: number;
    webSearchChars: number;
    genuiChars: number;
}

@Component({
    selector: "app-model-usage-analytics",
    standalone: true,
    imports: [
        CommonModule,
        FormsModule,
        MatButtonModule,
        MatCardModule,
        MatDatepickerModule,
        MatFormFieldModule,
        MatIconModule,
        MatInputModule,
        MatNativeDateModule,
        MatProgressSpinnerModule,
        MatSelectModule,
    ],
    templateUrl: "./model-usage-analytics.component.html",
    styleUrls: ["./model-usage-analytics.component.scss"],
})
export class ModelUsageAnalyticsComponent implements OnInit {
    protected readonly presets: TimeWindowPreset[] = ["24h", "7d", "30d", "all", "custom"];
    protected readonly usageKinds: UsageKindOption[] = ["all", "llm", "stt", "tts"];

    public selectedPreset: TimeWindowPreset = "7d";
    public selectedUsageKind: UsageKindOption = "all";
    public selectedProvider = "all";
    public selectedModel = "all";
    public selectedContext = "all";
    public customFromDate: Date | null = null;
    public customToDate: Date | null = null;

    public isLoading = false;
    public errorMessage = "";
    public lastUpdated: Date | null = null;

    public availableProviders: string[] = [];
    public availableModels: string[] = [];
    public availableContexts: string[] = [];

    public allRows: ModelUsageRecord[] = [];
    public filteredRows: ModelUsageRecord[] = [];
    public summaryCards: SummaryCard[] = [];
    public tokenTimelineBars: TimelineBar[] = [];
    public characterTimelineBars: TimelineBar[] = [];
    public useCaseTokenBars: BreakdownBar[] = [];
    public usageKindBars: BreakdownBar[] = [];
    public characterTypeBars: BreakdownBar[] = [];
    public providerBars: BreakdownBar[] = [];
    public modelBars: BreakdownBar[] = [];
    public recentRows: ModelUsageRecord[] = [];

    constructor(private modelUsageService: ModelUsageService) {}

    async ngOnInit(): Promise<void> {
        const now = new Date();
        const from = new Date(now);
        from.setDate(from.getDate() - 6);
        this.customFromDate = from;
        this.customToDate = now;
        await this.loadWindow();
    }

    public async onPresetChange(preset: TimeWindowPreset): Promise<void> {
        this.selectedPreset = preset;
        if (preset !== "custom") {
            await this.loadWindow();
        }
    }

    public async applyCustomRange(): Promise<void> {
        if (!this.canApplyCustomRange) {
            return;
        }
        await this.loadWindow();
    }

    public async onUsageKindChange(): Promise<void> {
        await this.loadWindow();
    }

    public async refreshData(): Promise<void> {
        this.modelUsageService.clearCache();
        await this.loadWindow();
    }

    public async resetFilters(): Promise<void> {
        this.selectedPreset = "7d";
        this.selectedUsageKind = "all";
        this.selectedProvider = "all";
        this.selectedModel = "all";
        this.selectedContext = "all";

        const now = new Date();
        const from = new Date(now);
        from.setDate(from.getDate() - 6);
        this.customFromDate = from;
        this.customToDate = now;

        await this.loadWindow();
    }

    public onProviderChange(): void {
        const availableModels = this.getModelOptionsForProvider();
        if (
            this.selectedModel !== "all" &&
            !availableModels.includes(this.selectedModel)
        ) {
            this.selectedModel = "all";
        }
        this.availableModels = availableModels;
        this.applyClientFilters();
    }

    public onModelChange(): void {
        this.applyClientFilters();
    }

    public onContextChange(): void {
        this.applyClientFilters();
    }

    public formatContextLabel(value: string): string {
        const knownLabels: Record<string, string> = {
            action_verification: "Action Verification",
            assistant: "Assistant",
            galnet: "Galnet",
            genui: "GenUI",
            memory_create: "Memory Create",
            web_search: "Web Search",
        };

        if (knownLabels[value]) {
            return knownLabels[value];
        }

        return value
            .split(/[_-]/g)
            .filter((part) => part.length > 0)
            .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
            .join(" ");
    }

    public formatPresetLabel(preset: TimeWindowPreset): string {
        const labels: Record<TimeWindowPreset, string> = {
            "24h": "24h",
            "7d": "7d",
            "30d": "30d",
            all: "All",
            custom: "Custom",
        };
        return labels[preset];
    }

    public formatUsageKindLabel(kind: UsageKindOption): string {
        const labels: Record<UsageKindOption, string> = {
            all: "All kinds",
            llm: "LLM",
            stt: "STT",
            tts: "TTS",
        };
        return labels[kind];
    }

    public formatTimelineSegmentTitle(
        bar: TimelineBar,
        segment: TimelineSegment,
        metric: "tokens" | "chars",
    ): string {
        const unit = metric === "tokens" ? "tokens" : "chars";
        return `${bar.displayLabel}\n${segment.label}: ${this.formatFullNumber(segment.value)} ${unit}`;
    }

    public formatBreakdownBarTitle(bar: BreakdownBar): string {
        return `${bar.label}\n${bar.valueLabel}\n${bar.subtitle}`;
    }

    public get canApplyCustomRange(): boolean {
        if (!this.customFromDate || !this.customToDate) {
            return false;
        }
        return this.customFromDate.getTime() <= this.customToDate.getTime();
    }

    public get hasTokenMetrics(): boolean {
        return this.filteredRows.some((row) => row.tokenUsage.totalTokens > 0);
    }

    public get hasPromptMetrics(): boolean {
        return this.filteredRows.some((row) => row.promptUsage.totalChars > 0);
    }

    public get hasLatencyMetrics(): boolean {
        return this.filteredRows.some((row) => row.latencyUsage.responseMs !== null);
    }

    public get hasAudioMetrics(): boolean {
        return this.filteredRows.some(
            (row) =>
                row.audioUsage.inputAudioDurationMs !== null ||
                row.audioUsage.outputAudioDurationMs !== null,
        );
    }

    public get hasTextMetrics(): boolean {
        return this.filteredRows.some(
            (row) =>
                row.textUsage.inputChars !== null ||
                row.textUsage.outputChars !== null,
        );
    }

    private async loadWindow(): Promise<void> {
        this.isLoading = true;
        this.errorMessage = "";

        try {
            const query = this.buildWindowQuery();
            const rows = await this.modelUsageService.getUsageHistory(query);
            this.allRows = rows;
            this.selectedProvider = "all";
            this.selectedModel = "all";
            this.selectedContext = "all";
            this.rebuildFilterOptions();
            this.applyClientFilters();
            this.lastUpdated = new Date();
        } catch (error) {
            this.errorMessage =
                error instanceof Error
                    ? error.message
                    : "Unable to load model usage history.";
            this.allRows = [];
            this.filteredRows = [];
            this.summaryCards = [];
            this.tokenTimelineBars = [];
            this.characterTimelineBars = [];
            this.useCaseTokenBars = [];
            this.usageKindBars = [];
            this.characterTypeBars = [];
            this.providerBars = [];
            this.modelBars = [];
            this.recentRows = [];
        } finally {
            this.isLoading = false;
        }
    }

    private buildWindowQuery(): { usageKind?: string; from?: string; to?: string } {
        const usageKind = this.selectedUsageKind === "all" ? undefined : this.selectedUsageKind;
        const now = new Date();

        if (this.selectedPreset === "all") {
            return usageKind ? { usageKind } : {};
        }

        if (this.selectedPreset === "custom") {
            const from = this.customFromDate
                ? this.startOfDay(this.customFromDate).toISOString()
                : undefined;
            const to = this.customToDate
                ? this.endOfDay(this.customToDate).toISOString()
                : undefined;

            return {
                usageKind,
                from,
                to,
            };
        }

        const from = new Date(now);
        if (this.selectedPreset === "24h") {
            from.setHours(from.getHours() - 24);
        } else if (this.selectedPreset === "7d") {
            from.setDate(from.getDate() - 7);
        } else {
            from.setDate(from.getDate() - 30);
        }

        return {
            usageKind,
            from: from.toISOString(),
            to: now.toISOString(),
        };
    }

    private rebuildFilterOptions(): void {
        this.availableProviders = this.getSortedUniqueValues(
            this.allRows.map((row) => row.provider),
        );
        this.availableContexts = this.getSortedUniqueValues(
            this.allRows.map((row) => row.context),
        );
        this.availableModels = this.getModelOptionsForProvider();
    }

    private getModelOptionsForProvider(): string[] {
        const source =
            this.selectedProvider === "all"
                ? this.allRows
                : this.allRows.filter(
                      (row) => row.provider === this.selectedProvider,
                  );
        return this.getSortedUniqueValues(source.map((row) => row.modelName));
    }

    private getSortedUniqueValues(values: string[]): string[] {
        return Array.from(new Set(values)).sort((left, right) =>
            left.localeCompare(right),
        );
    }

    private applyClientFilters(): void {
        this.filteredRows = this.allRows.filter((row) => {
            if (
                this.selectedProvider !== "all" &&
                row.provider !== this.selectedProvider
            ) {
                return false;
            }

            if (this.selectedModel !== "all" && row.modelName !== this.selectedModel) {
                return false;
            }

            if (this.selectedContext !== "all" && row.context !== this.selectedContext) {
                return false;
            }

            return true;
        });

        const llmRows = this.filteredRows.filter((row) => row.usageKind === "llm");

        this.summaryCards = this.buildSummaryCards(this.filteredRows);
        this.tokenTimelineBars = this.buildTimelineBars(this.filteredRows, "tokens");
        this.characterTimelineBars = this.buildTimelineBars(this.filteredRows, "chars");
        this.useCaseTokenBars = this.buildContextBars(llmRows, "tokens");
        this.usageKindBars = this.buildUsageKindBars(this.filteredRows);
        this.characterTypeBars = this.buildCharacterTypeBars(this.filteredRows);
        this.providerBars = this.buildGroupBars(llmRows, "provider");
        this.modelBars = this.buildGroupBars(llmRows, "model");
        this.recentRows = this.filteredRows.slice(0, 18);
    }

    private buildSummaryCards(rows: ModelUsageRecord[]): SummaryCard[] {
        const cards: SummaryCard[] = [];
        const requestRows = rows.filter((row) => row.messageType !== "action_cache_usage");
        const llmRows = rows.filter((row) => row.usageKind === "llm");
        const llmRequestRows = llmRows.filter(
            (row) => row.messageType !== "action_cache_usage",
        );
        const sttRows = rows.filter((row) => row.usageKind === "stt");
        const ttsRows = rows.filter((row) => row.usageKind === "tts");
        const actionCacheSavedCalls = rows.reduce(
            (sum, row) => sum + row.cacheUsage.llmCallsSaved,
            0,
        );
        const actionCacheAddedCalls =
            rows.reduce((sum, row) => sum + row.cacheUsage.llmCallsAdded, 0) +
            llmRequestRows.filter((row) => row.context === "action_verification").length;

        const totalTokens = llmRows.reduce(
            (sum, row) => sum + row.tokenUsage.totalTokens,
            0,
        );
        const cachedInputTokens = llmRows.reduce(
            (sum, row) => sum + row.tokenUsage.cachedTokens,
            0,
        );
        const liveInputTokens = llmRows.reduce(
            (sum, row) => sum + row.tokenUsage.liveInputTokens,
            0,
        );
        const thinkingOutputTokens = llmRows.reduce(
            (sum, row) => sum + row.tokenUsage.reasoningTokens,
            0,
        );
        const visibleOutputTokens = llmRows.reduce(
            (sum, row) => sum + row.tokenUsage.visibleOutputTokens,
            0,
        );
        const promptChars = llmRows.reduce(
            (sum, row) => sum + row.promptUsage.totalChars,
            0,
        );
        const responseLatencies = rows
            .map((row) => row.latencyUsage.responseMs)
            .filter((value): value is number => value !== null);
        const firstByteLatencies = rows
            .map((row) => row.latencyUsage.timeToFirstByteMs)
            .filter((value): value is number => value !== null);
        const inputAudioDurationMs = rows.reduce(
            (sum, row) => sum + (row.audioUsage.inputAudioDurationMs ?? 0),
            0,
        );
        const outputAudioDurationMs = rows.reduce(
            (sum, row) => sum + (row.audioUsage.outputAudioDurationMs ?? 0),
            0,
        );
        const ttsInputChars = ttsRows.reduce(
            (sum, row) => sum + (row.textUsage.inputChars ?? 0),
            0,
        );
        const llmOutputChars = llmRows.reduce(
            (sum, row) => sum + (row.textUsage.outputChars ?? 0),
            0,
        );
        const sttOutputChars = sttRows.reduce(
            (sum, row) => sum + (row.textUsage.outputChars ?? 0),
            0,
        );

        const avgTokens =
            llmRequestRows.length > 0
                ? Math.round(totalTokens / llmRequestRows.length)
                : 0;

        cards.push({
            label: "Calls",
            value: this.formatCompactNumber(requestRows.length),
            detail:
                totalTokens > 0
                    ? `${this.formatCompactNumber(avgTokens)} avg tokens per call`
                    : "persisted usage rows",
            tone: "amber",
        });

        if (totalTokens > 0) {
            cards.push(
                {
                    label: "Total Tokens",
                    value: this.formatCompactNumber(totalTokens),
                    detail: `${this.formatCompactNumber(cachedInputTokens)} cached + ${this.formatCompactNumber(liveInputTokens)} sent`,
                    tone: "blue",
                },
                {
                    label: "Cached Sent",
                    value: this.formatCompactNumber(cachedInputTokens),
                    detail: `${this.formatPercent(cachedInputTokens, totalTokens)} of total tokens`,
                    tone: "slate",
                },
                {
                    label: "Sent",
                    value: this.formatCompactNumber(liveInputTokens),
                    detail: `${this.formatPercent(liveInputTokens, totalTokens)} of total tokens`,
                    tone: "amber",
                },
                {
                    label: "Thinking Output",
                    value: this.formatCompactNumber(thinkingOutputTokens),
                    detail: `${this.formatPercent(thinkingOutputTokens, totalTokens)} of total tokens`,
                    tone: "violet",
                },
                {
                    label: "Output",
                    value: this.formatCompactNumber(visibleOutputTokens),
                    detail: `${this.formatPercent(visibleOutputTokens, totalTokens)} of total tokens`,
                    tone: "mint",
                },
            );
        }

        if (promptChars > 0) {
            cards.push({
                label: "Prompt Chars",
                value: this.formatCompactNumber(promptChars),
                detail: `${this.formatCompactNumber(Math.round(promptChars / Math.max(llmRequestRows.length, 1)))} avg chars per call`,
                tone: "rose",
            });
        }

        if (actionCacheSavedCalls > 0 || actionCacheAddedCalls > 0) {
            cards.push({
                label: "Cache Saved",
                value: this.formatCompactNumber(actionCacheSavedCalls),
                detail: `${this.formatCompactNumber(actionCacheAddedCalls)} extra verification calls`,
                tone: "mint",
            });

            cards.push({
                label: "Cache Net",
                value: this.formatCompactNumber(
                    actionCacheSavedCalls - actionCacheAddedCalls,
                ),
                detail:
                    actionCacheAddedCalls > 0
                        ? `${this.formatCompactNumber(actionCacheSavedCalls)} saved vs ${this.formatCompactNumber(actionCacheAddedCalls)} extra calls`
                        : "no extra verification calls",
                tone: "slate",
            });
        }

        if (responseLatencies.length > 0) {
            const avgResponseMs =
                responseLatencies.reduce((sum, value) => sum + value, 0) /
                responseLatencies.length;
            cards.push({
                label: "Avg Response",
                value: this.formatDuration(avgResponseMs),
                detail: `${this.formatDuration(this.percentile(responseLatencies, 95))} p95 response time`,
                tone: "violet",
            });
        }

        if (firstByteLatencies.length > 0) {
            const avgFirstByteMs =
                firstByteLatencies.reduce((sum, value) => sum + value, 0) /
                firstByteLatencies.length;
            cards.push({
                label: "Avg TTS First Byte",
                value: this.formatDuration(avgFirstByteMs),
                detail: `${this.formatDuration(this.percentile(firstByteLatencies, 95))} p95 first byte`,
                tone: "mint",
            });
        }

        if (inputAudioDurationMs > 0) {
            cards.push({
                label: "Input Audio",
                value: this.formatDuration(inputAudioDurationMs),
                detail: "captured by STT requests",
                tone: "blue",
            });
        }

        if (outputAudioDurationMs > 0) {
            cards.push({
                label: "Output Audio",
                value: this.formatDuration(outputAudioDurationMs),
                detail: "generated by TTS requests",
                tone: "slate",
            });
        }

        if (this.selectedUsageKind === "tts" && ttsInputChars > 0) {
            cards.push({
                label: "Input Chars",
                value: this.formatCompactNumber(ttsInputChars),
                detail: "text sent into TTS",
                tone: "amber",
            });
        }

        if (this.selectedUsageKind === "stt" && sttOutputChars > 0) {
            cards.push({
                label: "Output Chars",
                value: this.formatCompactNumber(sttOutputChars),
                detail: "characters returned by STT",
                tone: "mint",
            });
        } else if (llmOutputChars > 0) {
            cards.push({
                label: "Output Chars",
                value: this.formatCompactNumber(llmOutputChars),
                detail: "characters returned by LLM",
                tone: "mint",
            });
        }

        return cards;
    }

    private buildTimelineBars(
        rows: ModelUsageRecord[],
        metric: "tokens" | "chars",
    ): TimelineBar[] {
        const buckets = this.buildTimelineBuckets(rows);

        if (metric === "tokens") {
            const maxTokens = Math.max(
                1,
                ...buckets.map((bucket) => bucket.totalTokens),
            );

            return buckets.map((bucket, index) => ({
                label: bucket.label,
                displayLabel: bucket.displayLabel,
                showLabel: this.shouldShowTimelineLabel(index, buckets.length),
                totalTokens: bucket.totalTokens,
                totalChars: bucket.totalChars,
                tokenSegments: [
                    {
                        cssClass: "segment-cached-input",
                        heightPct: (bucket.cachedInputTokens / maxTokens) * 100,
                        label: "Cached Sent",
                        value: bucket.cachedInputTokens,
                    },
                    {
                        cssClass: "segment-live-input",
                        heightPct: (bucket.liveInputTokens / maxTokens) * 100,
                        label: "Sent",
                        value: bucket.liveInputTokens,
                    },
                    {
                        cssClass: "segment-thinking-output",
                        heightPct: (bucket.thinkingOutputTokens / maxTokens) * 100,
                        label: "Thinking",
                        value: bucket.thinkingOutputTokens,
                    },
                    {
                        cssClass: "segment-visible-output",
                        heightPct: (bucket.visibleOutputTokens / maxTokens) * 100,
                        label: "Output",
                        value: bucket.visibleOutputTokens,
                    },
                ].filter((segment) => segment.heightPct > 0),
                charSegments: [],
            }));
        }

        const maxChars = Math.max(1, ...buckets.map((bucket) => bucket.totalChars));

        return buckets.map((bucket, index) => ({
            label: bucket.label,
            displayLabel: bucket.displayLabel,
            showLabel: this.shouldShowTimelineLabel(index, buckets.length),
            totalTokens: bucket.totalTokens,
            totalChars: bucket.totalChars,
            tokenSegments: [],
            charSegments: [
                {
                    cssClass: "segment-system",
                    heightPct: (bucket.systemChars / maxChars) * 100,
                    label: "System",
                    value: bucket.systemChars,
                },
                {
                    cssClass: "segment-memory",
                    heightPct: (bucket.memoryChars / maxChars) * 100,
                    label: "Memory",
                    value: bucket.memoryChars,
                },
                {
                    cssClass: "segment-status",
                    heightPct: (bucket.statusChars / maxChars) * 100,
                    label: "Status",
                    value: bucket.statusChars,
                },
                {
                    cssClass: "segment-conversation",
                    heightPct: (bucket.conversationChars / maxChars) * 100,
                    label: "Conversation",
                    value: bucket.conversationChars,
                },
                {
                    cssClass: "segment-web-search",
                    heightPct: (bucket.webSearchChars / maxChars) * 100,
                    label: "Web Search",
                    value: bucket.webSearchChars,
                },
                {
                    cssClass: "segment-genui",
                    heightPct: (bucket.genuiChars / maxChars) * 100,
                    label: "GenUI",
                    value: bucket.genuiChars,
                },
            ].filter((segment) => segment.heightPct > 0),
        }));
    }

    private buildTimelineBuckets(rows: ModelUsageRecord[]): TimelineBucket[] {
        const { startMs, endMs, granularity } = this.resolveTimelineWindow(rows);
        const buckets: TimelineBucket[] = [];
        const bucketMap = new Map<number, TimelineBucket>();

        let cursor = this.floorToGranularity(startMs, granularity);
        const finalMs = Math.max(endMs, cursor);

        while (cursor <= finalMs) {
            const bucket = this.createEmptyBucket(cursor, granularity);
            buckets.push(bucket);
            bucketMap.set(bucket.bucketStartMs, bucket);
            cursor = this.addGranularity(cursor, granularity);
        }

        for (const row of rows) {
            const bucketStart = this.floorToGranularity(
                row.timestampMs,
                granularity,
            );
            const bucket = bucketMap.get(bucketStart);
            if (!bucket) {
                continue;
            }

            bucket.cachedInputTokens += row.tokenUsage.cachedTokens;
            bucket.liveInputTokens += row.tokenUsage.liveInputTokens;
            bucket.thinkingOutputTokens += row.tokenUsage.reasoningTokens;
            bucket.visibleOutputTokens += row.tokenUsage.visibleOutputTokens;
            bucket.totalTokens += row.tokenUsage.totalTokens;
            bucket.totalChars += row.promptUsage.totalChars;
            bucket.systemChars += row.promptUsage.systemChars;
            bucket.memoryChars += row.promptUsage.memoryChars;
            bucket.statusChars += row.promptUsage.statusChars;
            bucket.conversationChars += row.promptUsage.conversationChars;
            bucket.webSearchChars += row.promptUsage.webSearchChars;
            bucket.genuiChars += row.promptUsage.genuiChars;
        }

        return buckets;
    }

    private resolveTimelineWindow(rows: ModelUsageRecord[]): {
        startMs: number;
        endMs: number;
        granularity: TimelineGranularity;
    } {
        const now = Date.now();

        if (this.selectedPreset === "24h") {
            return {
                startMs: now - 24 * 60 * 60 * 1000,
                endMs: now,
                granularity: "hour",
            };
        }

        if (this.selectedPreset === "7d") {
            return {
                startMs: now - 7 * 24 * 60 * 60 * 1000,
                endMs: now,
                granularity: "day",
            };
        }

        if (this.selectedPreset === "30d") {
            return {
                startMs: now - 30 * 24 * 60 * 60 * 1000,
                endMs: now,
                granularity: "day",
            };
        }

        if (this.selectedPreset === "custom") {
            const startMs = this.customFromDate
                ? this.startOfDay(this.customFromDate).getTime()
                : now - 7 * 24 * 60 * 60 * 1000;
            const endMs = this.customToDate
                ? this.endOfDay(this.customToDate).getTime()
                : now;
            const spanMs = Math.max(endMs - startMs, 0);

            return {
                startMs,
                endMs,
                granularity: spanMs <= 48 * 60 * 60 * 1000 ? "hour" : "day",
            };
        }

        if (rows.length === 0) {
            return {
                startMs: now - 7 * 24 * 60 * 60 * 1000,
                endMs: now,
                granularity: "day",
            };
        }

        const sorted = [...rows].sort((left, right) => left.timestampMs - right.timestampMs);
        const startMs = sorted[0].timestampMs;
        const endMs = sorted[sorted.length - 1].timestampMs;
        const spanMs = Math.max(endMs - startMs, 0);

        return {
            startMs,
            endMs,
            granularity: spanMs > 120 * 24 * 60 * 60 * 1000 ? "week" : "day",
        };
    }

    private createEmptyBucket(
        bucketStartMs: number,
        granularity: TimelineGranularity,
    ): TimelineBucket {
        return {
            bucketStartMs,
            label: new Date(bucketStartMs).toISOString(),
            displayLabel: this.formatBucketLabel(bucketStartMs, granularity),
            cachedInputTokens: 0,
            liveInputTokens: 0,
            thinkingOutputTokens: 0,
            visibleOutputTokens: 0,
            totalTokens: 0,
            totalChars: 0,
            systemChars: 0,
            memoryChars: 0,
            statusChars: 0,
            conversationChars: 0,
            webSearchChars: 0,
            genuiChars: 0,
        };
    }

    private buildContextBars(
        rows: ModelUsageRecord[],
        metric: "tokens" | "chars",
    ): BreakdownBar[] {
        const groups = new Map<string, { value: number; count: number }>();

        for (const row of rows) {
            const key = row.context;
            const value =
                metric === "tokens"
                    ? row.tokenUsage.totalTokens
                    : row.promptUsage.totalChars;
            if (value <= 0) {
                continue;
            }
            const existing = groups.get(key) ?? { value: 0, count: 0 };
            existing.value += value;
            existing.count += 1;
            groups.set(key, existing);
        }

        return this.toBreakdownBars(
            Array.from(groups.entries()).map(([label, aggregate], index) => ({
                label,
                value: aggregate.value,
                valueLabel:
                    metric === "tokens"
                        ? this.formatCompactNumber(aggregate.value)
                        : this.formatCompactNumber(aggregate.value),
                subtitle: `${aggregate.count} calls`,
                tone: this.pickTone(index),
            })),
            8,
            true,
        ).map((bar) => ({
            ...bar,
            label: this.formatContextLabel(bar.label),
        }));
    }

    private buildCharacterTypeBars(rows: ModelUsageRecord[]): BreakdownBar[] {
        const totals = {
            system: 0,
            memory: 0,
            status: 0,
            conversation: 0,
            webSearch: 0,
            genui: 0,
        };

        for (const row of rows) {
            totals.system += row.promptUsage.systemChars;
            totals.memory += row.promptUsage.memoryChars;
            totals.status += row.promptUsage.statusChars;
            totals.conversation += row.promptUsage.conversationChars;
            totals.webSearch += row.promptUsage.webSearchChars;
            totals.genui += row.promptUsage.genuiChars;
        }

        const entries = [
            { label: "System", value: totals.system },
            { label: "Memory", value: totals.memory },
            { label: "Status", value: totals.status },
            { label: "Conversation", value: totals.conversation },
            { label: "Web Search", value: totals.webSearch },
            { label: "GenUI", value: totals.genui },
        ];

        const totalChars = entries.reduce((sum, entry) => sum + entry.value, 0);

        return entries
            .filter((entry) => entry.value > 0)
            .sort((left, right) => right.value - left.value)
            .map((entry, index) => {
                const percentage = totalChars > 0 ? (entry.value / totalChars) * 100 : 0;
                return {
                    label: entry.label,
                    value: entry.value,
                    valueLabel: `${Math.round(percentage)}%`,
                    subtitle: "share of total prompt chars",
                    widthPct: percentage,
                    tone: this.pickTone(index),
                };
            });
    }

    private buildUsageKindBars(rows: ModelUsageRecord[]): BreakdownBar[] {
        const groups = new Map<string, number>();

        for (const row of rows) {
            groups.set(row.usageKind, (groups.get(row.usageKind) ?? 0) + 1);
        }

        return this.toBreakdownBars(
            Array.from(groups.entries()).map(([label, count], index) => ({
                label: this.formatUsageKindLabel(label as UsageKindOption),
                value: count,
                valueLabel: this.formatCompactNumber(count),
                subtitle: "calls",
                tone: this.pickTone(index),
            })),
            4,
            true,
        );
    }

    private buildGroupBars(
        rows: ModelUsageRecord[],
        groupBy: "provider" | "model",
    ): BreakdownBar[] {
        const groups = new Map<string, { value: number; count: number }>();

        for (const row of rows) {
            if (row.tokenUsage.totalTokens <= 0) {
                continue;
            }
            const key = groupBy === "provider" ? row.provider : row.modelName;
            const existing = groups.get(key) ?? { value: 0, count: 0 };
            existing.value += row.tokenUsage.totalTokens;
            existing.count += 1;
            groups.set(key, existing);
        }

        return this.toBreakdownBars(
            Array.from(groups.entries()).map(([label, aggregate], index) => ({
                label,
                value: aggregate.value,
                valueLabel: this.formatCompactNumber(aggregate.value),
                subtitle: `${aggregate.count} calls`,
                tone: this.pickTone(index),
            })),
            groupBy === "provider" ? 6 : 8,
            false,
        );
    }

    private toBreakdownBars(
        input: Array<{
            label: string;
            value: number;
            valueLabel: string;
            subtitle: string;
            tone: BreakdownBar["tone"];
        }>,
        limit: number,
        removeZeros: boolean,
    ): BreakdownBar[] {
        const values = removeZeros ? input.filter((item) => item.value > 0) : input;
        const sorted = values.sort((left, right) => right.value - left.value).slice(0, limit);
        const maxValue = Math.max(1, ...sorted.map((item) => item.value));

        return sorted.map((item) => ({
            label: item.label,
            value: item.value,
            valueLabel: item.valueLabel,
            subtitle: item.subtitle,
            widthPct: (item.value / maxValue) * 100,
            tone: item.tone,
        }));
    }

    private shouldShowTimelineLabel(index: number, total: number): boolean {
        if (total <= 8) {
            return true;
        }

        const interval = Math.ceil(total / 6);
        return index === 0 || index === total - 1 || index % interval === 0;
    }

    private pickTone(index: number): BreakdownBar["tone"] {
        const tones: BreakdownBar["tone"][] = [
            "amber",
            "blue",
            "mint",
            "rose",
            "violet",
            "slate",
        ];
        return tones[index % tones.length];
    }

    private startOfDay(value: Date): Date {
        const date = new Date(value);
        date.setHours(0, 0, 0, 0);
        return date;
    }

    private endOfDay(value: Date): Date {
        const date = new Date(value);
        date.setHours(23, 59, 59, 999);
        return date;
    }

    private floorToGranularity(
        timestampMs: number,
        granularity: TimelineGranularity,
    ): number {
        const value = new Date(timestampMs);

        if (granularity === "hour") {
            value.setMinutes(0, 0, 0);
            return value.getTime();
        }

        value.setHours(0, 0, 0, 0);
        if (granularity === "day") {
            return value.getTime();
        }

        const day = (value.getDay() + 6) % 7;
        value.setDate(value.getDate() - day);
        return value.getTime();
    }

    private addGranularity(
        timestampMs: number,
        granularity: TimelineGranularity,
    ): number {
        const value = new Date(timestampMs);

        if (granularity === "hour") {
            value.setHours(value.getHours() + 1);
            return value.getTime();
        }

        if (granularity === "day") {
            value.setDate(value.getDate() + 1);
            return value.getTime();
        }

        value.setDate(value.getDate() + 7);
        return value.getTime();
    }

    private formatBucketLabel(
        timestampMs: number,
        granularity: TimelineGranularity,
    ): string {
        const value = new Date(timestampMs);

        if (granularity === "hour") {
            return value.toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
            });
        }

        if (granularity === "day") {
            return value.toLocaleDateString([], {
                month: "short",
                day: "numeric",
            });
        }

        return `Week of ${value.toLocaleDateString([], {
            month: "short",
            day: "numeric",
        })}`;
    }

    private formatCompactNumber(value: number): string {
        return new Intl.NumberFormat(undefined, {
            notation: value >= 1000 ? "compact" : "standard",
            maximumFractionDigits: value >= 1000 ? 1 : 0,
        }).format(Math.round(value));
    }

    private formatDuration(valueMs: number): string {
        if (!Number.isFinite(valueMs) || valueMs <= 0) {
            return "0 ms";
        }

        if (valueMs < 1000) {
            return `${Math.round(valueMs)} ms`;
        }

        return `${(valueMs / 1000).toFixed(valueMs >= 10_000 ? 0 : 1)} s`;
    }

    private formatFullNumber(value: number): string {
        return new Intl.NumberFormat().format(Math.round(value));
    }

    private percentile(values: number[], percentile: number): number {
        if (values.length === 0) {
            return 0;
        }

        const sorted = [...values].sort((left, right) => left - right);
        const index = Math.min(
            sorted.length - 1,
            Math.max(0, Math.ceil((percentile / 100) * sorted.length) - 1),
        );
        return sorted[index];
    }

    private formatPercent(value: number, total: number): string {
        if (total <= 0) {
            return "0%";
        }
        return `${Math.round((value / total) * 100)}%`;
    }
}
