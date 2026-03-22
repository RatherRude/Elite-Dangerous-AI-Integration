import { CommonModule } from "@angular/common";
import { Component, OnInit } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatButtonToggleModule } from "@angular/material/button-toggle";
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
} from "../../services/model-usage.service";

type TimelineGranularity = "hour" | "day" | "week";

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

interface TimelineBar {
    label: string;
    displayLabel: string;
    showLabel: boolean;
    inputHeightPct: number;
    outputHeightPct: number;
    totalTokens: number;
    charSegments: Array<{
        cssClass: string;
        heightPct: number;
        label: string;
    }>;
}

interface TimelineBucket {
    bucketStartMs: number;
    label: string;
    displayLabel: string;
    inputTokens: number;
    outputTokens: number;
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
        MatButtonToggleModule,
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

    public selectedPreset: TimeWindowPreset = "7d";
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

    public async refreshData(): Promise<void> {
        this.modelUsageService.clearCache();
        await this.loadWindow();
    }

    public async resetFilters(): Promise<void> {
        this.selectedPreset = "7d";
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

    public get canApplyCustomRange(): boolean {
        if (!this.customFromDate || !this.customToDate) {
            return false;
        }
        return this.customFromDate.getTime() <= this.customToDate.getTime();
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
            this.characterTypeBars = [];
            this.providerBars = [];
            this.modelBars = [];
            this.recentRows = [];
        } finally {
            this.isLoading = false;
        }
    }

    private buildWindowQuery(): { usageKind: string; from?: string; to?: string } {
        const now = new Date();

        if (this.selectedPreset === "all") {
            return { usageKind: "llm" };
        }

        if (this.selectedPreset === "custom") {
            const from = this.customFromDate
                ? this.startOfDay(this.customFromDate).toISOString()
                : undefined;
            const to = this.customToDate
                ? this.endOfDay(this.customToDate).toISOString()
                : undefined;

            return {
                usageKind: "llm",
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
            usageKind: "llm",
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

        this.summaryCards = this.buildSummaryCards(this.filteredRows);
        this.tokenTimelineBars = this.buildTimelineBars(this.filteredRows, "tokens");
        this.characterTimelineBars = this.buildTimelineBars(this.filteredRows, "chars");
        this.useCaseTokenBars = this.buildContextBars(this.filteredRows, "tokens");
        this.characterTypeBars = this.buildCharacterTypeBars(this.filteredRows);
        this.providerBars = this.buildGroupBars(this.filteredRows, "provider");
        this.modelBars = this.buildGroupBars(this.filteredRows, "model");
        this.recentRows = this.filteredRows.slice(0, 18);
    }

    private buildSummaryCards(rows: ModelUsageRecord[]): SummaryCard[] {
        const totalTokens = rows.reduce(
            (sum, row) => sum + row.tokenUsage.totalTokens,
            0,
        );
        const inputTokens = rows.reduce(
            (sum, row) => sum + row.tokenUsage.inputTokens,
            0,
        );
        const outputTokens = rows.reduce(
            (sum, row) => sum + row.tokenUsage.outputTokens,
            0,
        );
        const reasoningTokens = rows.reduce(
            (sum, row) => sum + row.tokenUsage.reasoningTokens,
            0,
        );
        const promptChars = rows.reduce(
            (sum, row) => sum + row.promptUsage.totalChars,
            0,
        );

        const topContext = this.buildContextBars(rows, "tokens")[0];
        const avgTokens = rows.length > 0 ? Math.round(totalTokens / rows.length) : 0;

        return [
            {
                label: "Calls",
                value: this.formatCompactNumber(rows.length),
                detail: `${this.formatCompactNumber(avgTokens)} avg tokens per call`,
                tone: "amber",
            },
            {
                label: "Total Tokens",
                value: this.formatCompactNumber(totalTokens),
                detail: `${this.formatCompactNumber(inputTokens)} in / ${this.formatCompactNumber(outputTokens)} out`,
                tone: "blue",
            },
            {
                label: "Reasoning Tokens",
                value: this.formatCompactNumber(reasoningTokens),
                detail: `${this.formatPercent(reasoningTokens, totalTokens)} of total token spend`,
                tone: "violet",
            },
            {
                label: "Prompt Chars",
                value: this.formatCompactNumber(promptChars),
                detail: `${this.formatCompactNumber(promptChars / Math.max(rows.length, 1))} avg chars per call`,
                tone: "mint",
            },
            {
                label: "Top Use Case",
                value: topContext ? this.formatContextLabel(topContext.label) : "-",
                detail: topContext
                    ? `${this.formatCompactNumber(topContext.value)} tokens across ${topContext.subtitle}`
                    : "No matching calls in this window",
                tone: "rose",
            },
            {
                label: "Selected Window",
                value: this.formatPresetLabel(this.selectedPreset),
                detail: `${this.formatCompactNumber(this.filteredRows.length)} filtered calls`,
                tone: "slate",
            },
        ];
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
                inputHeightPct: (bucket.inputTokens / maxTokens) * 100,
                outputHeightPct: (bucket.outputTokens / maxTokens) * 100,
                totalTokens: bucket.totalTokens,
                charSegments: [],
            }));
        }

        const maxChars = Math.max(1, ...buckets.map((bucket) => bucket.totalChars));

        return buckets.map((bucket, index) => ({
            label: bucket.label,
            displayLabel: bucket.displayLabel,
            showLabel: this.shouldShowTimelineLabel(index, buckets.length),
            inputHeightPct: 0,
            outputHeightPct: 0,
            totalTokens: bucket.totalTokens,
            charSegments: [
                {
                    cssClass: "segment-system",
                    heightPct: (bucket.systemChars / maxChars) * 100,
                    label: "System",
                },
                {
                    cssClass: "segment-memory",
                    heightPct: (bucket.memoryChars / maxChars) * 100,
                    label: "Memory",
                },
                {
                    cssClass: "segment-status",
                    heightPct: (bucket.statusChars / maxChars) * 100,
                    label: "Status",
                },
                {
                    cssClass: "segment-conversation",
                    heightPct: (bucket.conversationChars / maxChars) * 100,
                    label: "Conversation",
                },
                {
                    cssClass: "segment-web-search",
                    heightPct: (bucket.webSearchChars / maxChars) * 100,
                    label: "Web Search",
                },
                {
                    cssClass: "segment-genui",
                    heightPct: (bucket.genuiChars / maxChars) * 100,
                    label: "GenUI",
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

            bucket.inputTokens += row.tokenUsage.inputTokens;
            bucket.outputTokens += row.tokenUsage.outputTokens;
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
            inputTokens: 0,
            outputTokens: 0,
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
                    subtitle: "share of prompt footprint",
                    widthPct: percentage,
                    tone: this.pickTone(index),
                };
            });
    }

    private buildGroupBars(
        rows: ModelUsageRecord[],
        groupBy: "provider" | "model",
    ): BreakdownBar[] {
        const groups = new Map<string, { value: number; count: number }>();

        for (const row of rows) {
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

    private formatPercent(value: number, total: number): string {
        if (total <= 0) {
            return "0%";
        }
        return `${Math.round((value / total) * 100)}%`;
    }
}
