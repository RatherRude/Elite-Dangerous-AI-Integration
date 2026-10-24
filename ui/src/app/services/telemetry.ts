/** Closed projection shared by local transparency and OTel. No payloads are retained. */
export type Labels = Record<string, string | boolean>;
export interface Observation { name: string; value: number; attributes: Labels; }
export interface MetricDefinition { histogram?: boolean; unit?: string; boundaries?: number[]; }
export const LATENCY_SCHEMA = "latency-v2";
export const LATENCY_BUCKETS = [
    ...Array.from({ length: 31 }, (_, i) => i * 100),
    ...Array.from({ length: 14 }, (_, i) => 3500 + i * 500),
    ...Array.from({ length: 20 }, (_, i) => 11000 + i * 1000),
    ...Array.from({ length: 54 }, (_, i) => 35000 + i * 5000),
];
export const TOOL_DURATION_BUCKETS = [0, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000, 60000, 120000, 300000];
export const SESSION_BUCKETS = [0, 60000, 300000, 900000, 1800000, 3600000, 7200000, 14400000, 28800000, 86400000];
export const REALTIME_FACTOR_BUCKETS = [0, 0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.75,
    1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 7.5, 10, 15, 20, 30, 50, 100];
export const METRICS: Record<string, MetricDefinition> = {
    covas_sessions_total: {},
    covas_session_duration_ms: { histogram: true, unit: "ms", boundaries: SESSION_BUCKETS },
    covas_backend_process_events_total: {}, covas_backend_messages_total: {},
    covas_chat_messages_total: {}, covas_logs_total: {}, covas_usage_calls_total: {},
    covas_llm_tokens_total: {}, covas_prompt_chars_total: {},
    covas_usage_latency_ms: { histogram: true, unit: "ms", boundaries: LATENCY_BUCKETS },
    covas_audio_duration_ms_total: { unit: "ms" }, covas_text_chars_total: {},
    covas_action_cache_calls_total: {}, covas_tool_calls_total: {},
    covas_tool_duration_ms: { histogram: true, unit: "ms", boundaries: TOOL_DURATION_BUCKETS },
    covas_audio_pipeline_errors_total: {},
    covas_audio_realtime_factor: { histogram: true, boundaries: REALTIME_FACTOR_BUCKETS },
    covas_tts_underruns_total: {},
};
/** Preserve supplied metadata; series policy belongs to the collector, not a client catalog. */
export function metadataLabel(value: unknown): string {
    return typeof value === "string" && value.trim() ? value : "unknown";
}
function object(value: unknown): Record<string, unknown> {
    return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}
export function measurement(value: unknown, integer = false): number | null {
    return typeof value === "number" && Number.isFinite(value) && value >= 0 && (!integer || Number.isSafeInteger(value)) ? value : null;
}

export interface ReportedTokenUsage {
    inputTokens: number | null; outputTokens: number | null; totalTokens: number | null;
    cachedTokens: number | null; reasoningTokens: number | null;
    reasoningIncluded: boolean | null; effectiveOutputTokens: number | null;
}

/** Facts shared by live telemetry and persisted analytics; never inspect config. */
export function reportedTokenUsage(usage: Record<string, unknown>): ReportedTokenUsage {
    const inputTokens = measurement(usage["input_tokens"], true);
    const outputTokens = measurement(usage["output_tokens"], true);
    const totalTokens = measurement(usage["total_tokens"], true);
    const cachedTokens = measurement(usage["cached_tokens"], true);
    const reasoningTokens = measurement(usage["reasoning_tokens"], true);
    let reasoningIncluded = typeof usage["reasoning_tokens_in_output"] === "boolean"
        ? usage["reasoning_tokens_in_output"] : null;
    if (reasoningIncluded === null && reasoningTokens !== null && inputTokens !== null && outputTokens !== null && totalTokens !== null) {
        if (totalTokens === inputTokens + outputTokens) reasoningIncluded = true;
        else if (totalTokens === inputTokens + outputTokens + reasoningTokens) reasoningIncluded = false;
    }
    let effectiveOutputTokens: number | null = null;
    if (outputTokens !== null) {
        if (reasoningIncluded === true && (reasoningTokens === null || reasoningTokens <= outputTokens)) effectiveOutputTokens = outputTokens;
        else if (reasoningTokens === 0) effectiveOutputTokens = outputTokens;
        else if (reasoningIncluded === false && reasoningTokens !== null) effectiveOutputTokens = measurement(outputTokens + reasoningTokens, true);
    }
    return { inputTokens, outputTokens, totalTokens, cachedTokens, reasoningTokens, reasoningIncluded, effectiveOutputTokens };
}

export function tokenRange(value: number | null, boundaries: number[]): string {
    if (value === null) return "unknown";
    let previous = -1;
    for (const boundary of boundaries) {
        if (value <= boundary) return boundary === 0 ? "0" : `${previous + 1}-${boundary}`;
        previous = boundary;
    }
    return `${previous + 1}+`;
}

export function llmUsageDimensions(usage: Record<string, unknown>): Labels {
    const facts = reportedTokenUsage(usage);
    return {
        "reasoning.output": facts.reasoningTokens === null ? "unknown" : facts.reasoningTokens === 0 ? "zero" : "nonzero",
        "input.tokens.range": tokenRange(facts.inputTokens, [0, 1024, 4096, 16384, 65536, 262144]),
        "output.tokens.range": tokenRange(facts.effectiveOutputTokens, [0, 128, 512, 2048, 8192]),
    };
}
export function localeResources(): Labels {
    let locale = "unknown", zone = "unknown";
    try {
        locale = metadataLabel(navigator.language || Intl.DateTimeFormat().resolvedOptions().locale);
        zone = metadataLabel(Intl.DateTimeFormat().resolvedOptions().timeZone.split("/")[0]);
    } catch { /* Browser locale APIs are optional. */ }
    return { "client.locale": locale, "client.locale.primary": locale.split("-")[0], "client.timezone.region": zone };
}

export function projectMessage(message: Record<string, unknown>): Observation[] {
    const out: Observation[] = [];
    const add = (name: string, value: unknown, attributes: Labels = {}, integer = false) => {
        const number = measurement(value, integer);
        if (number !== null && (number > 0 || METRICS[name]?.histogram)) out.push({ name, value: number,
            attributes: METRICS[name]?.boundaries === LATENCY_BUCKETS ? { ...attributes, "histogram.schema": LATENCY_SCHEMA } : attributes });
    };
    const type = message["type"];
    add("covas_backend_messages_total", 1, { "message.type": metadataLabel(type) });
    if (type === "chat") add("covas_chat_messages_total", 1, { "chat.role": metadataLabel(message["role"]) });
    if (type === "log") {
        const level = typeof message["prefix"] === "string" ? message["prefix"].toLowerCase() : "unknown";
        add("covas_logs_total", 1, { "log.level": metadataLabel(level === "warning" ? "warn" : level) });
    }
    if (type === "backend_process_state") add("covas_backend_process_events_total", 1, {
        status: metadataLabel(message["status"]), expected: message["expected"] === true,
    });
    if (type === "audio_pipeline_error") add("covas_audio_pipeline_errors_total", 1, {
        "usage.kind": metadataLabel(message["usage_kind"]),
        stage: metadataLabel(message["stage"]),
        "error.kind": metadataLabel(message["error_kind"]),
    });
    if (type === "tool_usage") {
        const attrs = {
            "tool.name": metadataLabel(message["tool_name"]),
            "tool.type": metadataLabel(message["tool_type"]),
            source: metadataLabel(message["source"]),
            status: metadataLabel(message["status"]),
            "error.kind": message["status"] === "success" ? "none" : metadataLabel(message["error_kind"]),
        };
        add("covas_tool_calls_total", 1, attrs);
        add("covas_tool_duration_ms", message["duration_ms"], attrs);
    }
    if (!["llm_usage", "stt_usage", "tts_usage", "action_cache_usage"].includes(String(type))) return out;
    const usage = object(message["model_usage"]);
    const attrs: Labels = {
        context: metadataLabel(message["context"]),
        provider: metadataLabel(message["provider"] ?? usage["provider"]),
        "model.name": metadataLabel(usage["model_name"] ?? message["model_name"]),
    };
    if (type === "action_cache_usage") {
        add("covas_action_cache_calls_total", object(message["cache_usage"])["llm_calls_saved"], { ...attrs, "cache.result": "saved" }, true);
        return out;
    }
    const kind = String(type).replace("_usage", "");
    const status = metadataLabel(message["status"]);
    const outcome: Labels = { ...attrs, "usage.kind": kind, status,
        "error.kind": status === "success" || status === "cancelled" ? "none" : metadataLabel(message["error_kind"]) };
    if (kind === "stt") outcome["input.language"] = metadataLabel(message["input_language"]);
    if (kind === "tts") {
        outcome["output.language"] = metadataLabel(message["output_language"]);
        outcome["output.voice"] = metadataLabel(message["output_voice"]);
        const underruns = measurement(message["num_underruns"], true);
        if (underruns !== null) {
            outcome["playback.monitored"] = true;
            outcome["playback.underrun"] = underruns > 0;
            add("covas_tts_underruns_total", underruns, outcome, true);
        }
    }
    const operationAttributes = kind === "llm" ? { ...outcome, ...llmUsageDimensions(usage) } : outcome;
    add("covas_usage_calls_total", 1, operationAttributes);
    if (kind === "llm") {
        if (attrs["context"] === "action_verification") add("covas_action_cache_calls_total", 1, { ...attrs, "cache.result": "added" });
        for (const [field, label] of Object.entries({ input_tokens: "input", output_tokens: "output", total_tokens: "total", cached_tokens: "cached_input", reasoning_tokens: "reasoning" }))
            add("covas_llm_tokens_total", usage[field], { ...attrs, "token.type": label }, true);
        add("covas_llm_tokens_total", reportedTokenUsage(usage).effectiveOutputTokens, { ...attrs, "token.type": "effective_output" }, true);
        const prompt = object(message["prompt_usage"]);
        for (const section of ["system", "memory", "status", "conversation", "web_search", "genui", "reuse", "total"])
            add("covas_prompt_chars_total", prompt[section === "total" ? "total_prompt_chars" : `${section}_chars`], { ...attrs, "prompt.section": section }, true);
    }
    for (const [field, label] of Object.entries({ response_ms: "response", time_to_first_token_ms: "time_to_first_token", time_to_first_byte_ms: "time_to_first_byte" }))
        add("covas_usage_latency_ms", object(message["latency_usage"])[field], { ...operationAttributes, "latency.type": label });
    add("covas_usage_latency_ms", message["operation_ms"], { ...operationAttributes, "latency.type": "operation" });
    for (const direction of ["input", "output"]) {
        add("covas_audio_duration_ms_total", object(message["audio_usage"])[`${direction}_audio_duration_ms`], { ...outcome, direction });
        add("covas_text_chars_total", object(message["text_usage"])[`${direction}_chars`], { ...outcome, direction }, true);
    }
    if (status === "success" && (kind === "stt" || kind === "tts")) {
        const duration = measurement(object(message["audio_usage"])[kind === "stt" ? "input_audio_duration_ms" : "output_audio_duration_ms"]);
        const operation = measurement(message["operation_ms"]);
        // Pair timing and audio from the same completed call; never divide
        // separately aggregated totals whose reporting coverage can differ.
        if (operation !== null && duration !== null && duration > 0)
            add("covas_audio_realtime_factor", operation / duration, { ...outcome, "histogram.schema": "rtf-v1" });
    }
    return out;
}

export interface MetricAggregate {
    name: string; attributes: Labels; count: number; sum: number;
    min: number; max: number; buckets: number[]; samples: number[];
}
export function percentile(samples: number[], q: number): number | null {
    if (!samples.length) return null;
    const sorted = [...samples].sort((a, b) => a - b);
    return sorted[Math.max(0, Math.ceil(sorted.length * q) - 1)];
}
export class TelemetryAggregation {
    private groups = new Map<string, Map<string, MetricAggregate>>();
    constructor(private sampleLimit = 200) {}
    record(observation: Observation): Observation {
        const definition = METRICS[observation.name];
        let groups = this.groups.get(observation.name);
        if (!groups) { groups = new Map(); this.groups.set(observation.name, groups); }
        const attributes = observation.attributes;
        const key = JSON.stringify(Object.entries(attributes).sort());
        let group = groups.get(key);
        if (!group) {
            group = { name: observation.name, attributes, count: 0, sum: 0, min: observation.value,
                max: observation.value, buckets: (definition.boundaries || []).map(() => 0).concat(0), samples: [] };
            groups.set(key, group);
        }
        group.count++; group.sum += observation.value;
        group.min = Math.min(group.min, observation.value); group.max = Math.max(group.max, observation.value);
        if (definition.histogram) {
            const boundaries = definition.boundaries!;
            const bucket = boundaries.findIndex(b => observation.value <= b);
            group.buckets[bucket < 0 ? boundaries.length : bucket]++;
            group.samples.push(observation.value);
            if (group.samples.length > this.sampleLimit) group.samples.shift();
        }
        return { ...observation, attributes };
    }
    snapshot(): MetricAggregate[] {
        return [...this.groups.values()].flatMap(groups => [...groups.values()].map(g => ({ ...g, attributes: { ...g.attributes }, buckets: [...g.buckets], samples: [...g.samples] })));
    }
}
