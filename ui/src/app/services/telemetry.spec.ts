import { LATENCY_BUCKETS, LATENCY_SCHEMA, localeResources, measurement, metadataLabel, percentile, projectMessage, reportedTokenUsage, TelemetryAggregation } from "./telemetry";

describe("telemetry projection", () => {
    it("uses the requested bucket spacing without duplicate boundaries", () => {
        expect(LATENCY_BUCKETS.length).toBe(119);
        expect(new Set(LATENCY_BUCKETS).size).toBe(119);
        for (let ms = 0; ms <= 300000; ms += ms < 3000 ? 100 : ms < 10000 ? 500 : ms < 30000 ? 1000 : 5000)
            expect(LATENCY_BUCKETS).toContain(ms);
        expect(LATENCY_BUCKETS[LATENCY_BUCKETS.length - 1]).toBe(300000);
    });
    const usage = { type: "llm_usage", schema_version: 3, context: "assistant", provider: "openai", model_name: "gpt-5",
        status: "success", error_kind: "none", model_usage: { input_tokens: 10, cached_tokens: 2, output_tokens: 4, total_tokens: 14 },
        latency_usage: { response_ms: 0, time_to_first_token_ms: null } };
    it("uses stable instruments, retaining valid zero latency but not absent samples", () => {
        const observations = projectMessage(usage);
        const latency = observations.filter(o => o.name === "covas_usage_latency_ms");
        expect(latency.length).toBe(1);
        expect(latency[0].value).toBe(0);
        expect(latency[0].attributes["latency.type"]).toBe("response");
        expect(latency[0].attributes["histogram.schema"]).toBe(LATENCY_SCHEMA);
        expect(observations.find(o => o.name === "covas_usage_calls_total")!.attributes["histogram.schema"]).toBeUndefined();
        expect(observations.find(o => o.name === "covas_usage_calls_total")?.value).toBe(1);
    });
    it("does not count cache hits or history rows as model calls", () => {
        const saved = projectMessage({ ...usage, type: "action_cache_usage", cache_usage: { llm_calls_saved: 1 } });
        expect(saved.some(o => o.name === "covas_usage_calls_total")).toBeFalse();
        expect(saved.find(o => o.name === "covas_action_cache_calls_total")?.value).toBe(1);
        expect(projectMessage({ type: "model_usage_history", rows: [usage] }).length).toBe(1);
    });
    it("counts a failed verification once, not an added event plus an LLM call", () => {
        const observations = projectMessage({ ...usage, context: "action_verification", status: "error", error_kind: "timeout", cache_usage: { llm_calls_added: 1 } });
        expect(observations.filter(o => o.name === "covas_action_cache_calls_total").length).toBe(1);
        expect(observations.find(o => o.name === "covas_usage_calls_total")?.attributes["error.kind"]).toBe("timeout");
    });
    it("preserves provider-reported stock model and voice and marks cancellation separately", () => {
        const observations = projectMessage({ ...usage, type: "tts_usage", status: "cancelled", model_name: "gpt-4o-mini-tts", output_voice: "nova", output_language: "en-US" });
        const attrs = observations.find(o => o.name === "covas_usage_calls_total")!.attributes;
        expect(attrs["model.name"]).toBe("gpt-4o-mini-tts");
        expect(attrs["output.voice"]).toBe("nova");
        expect(attrs["status"]).toBe("cancelled");
        expect(attrs["error.kind"]).toBe("none");
    });
    it("preserves model metadata without catalog, syntax or length restrictions", () => {
        for (const name of ["gpt-6-luna", "org/New-Model-v2:latest", "https://example.invalid/model", "/models/local model.gguf", "模型/" + "x".repeat(100)]) {
            const points = projectMessage({ ...usage, model_name: name });
            expect(points.find(point => point.name === "covas_usage_calls_total")!.attributes["model.name"]).toBe(name);
        }
        const points = projectMessage({ ...usage, model_name: "requested-alias", model_usage: { ...usage.model_usage, model_name: "gpt-6-luna" } });
        expect(points.find(point => point.name === "covas_usage_calls_total")!.attributes["model.name"]).toBe("gpt-6-luna");
    });
    it("attaches explicit zero/nonzero/unknown reasoning to the same call and latency observations", () => {
        for (const [count, expected] of [[0, "zero"], [15, "nonzero"], [null, "unknown"], [-1, "unknown"], ["0", "unknown"]] as const) {
            const points = projectMessage({ ...usage, model_usage: { ...usage.model_usage, reasoning_tokens: count }, reasoning_effort: "none" });
            const call = points.find(point => point.name === "covas_usage_calls_total")!;
            const latency = points.find(point => point.name === "covas_usage_latency_ms")!;
            expect(call.attributes["reasoning.output"]).toBe(expected);
            expect(latency.attributes["reasoning.output"]).toBe(expected);
        }
    });
    it("uses effective generated output for latency ranges without double-counting reasoning", () => {
        for (const [output, included] of [[140, true], [120, false]] as const) {
            const points = projectMessage({ ...usage, model_usage: { input_tokens: 10, output_tokens: output, total_tokens: 150,
                reasoning_tokens: 20, reasoning_tokens_in_output: included } });
            expect(points.find(point => point.name === "covas_usage_latency_ms")!.attributes["output.tokens.range"]).toBe("129-512");
            expect(points.find(point => point.name === "covas_llm_tokens_total" && point.attributes["token.type"] === "effective_output")?.value).toBe(140);
        }
    });
    it("keeps unreported output accounting unknown and uses bounded token ranges", () => {
        const unknown = projectMessage({ ...usage, model_usage: { output_tokens: 120, reasoning_tokens: 20 } });
        expect(unknown.find(point => point.name === "covas_usage_latency_ms")!.attributes["output.tokens.range"]).toBe("unknown");
        for (const [input, expected] of [[0, "0"], [1024, "1-1024"], [1025, "1025-4096"], [262145, "262145+"], [null, "unknown"]] as const) {
            const points = projectMessage({ ...usage, model_usage: { input_tokens: input, output_tokens: 0, reasoning_tokens: 0 } });
            expect(points.find(point => point.name === "covas_usage_latency_ms")!.attributes["input.tokens.range"]).toBe(expected);
            expect(points.find(point => point.name === "covas_usage_latency_ms")!.attributes["output.tokens.range"]).toBe("0");
        }
        expect(reportedTokenUsage({ input_tokens: 100, output_tokens: 40, total_tokens: 155, reasoning_tokens: 15 }).effectiveOutputTokens).toBe(55);
        expect(reportedTokenUsage({ output_tokens: 5, reasoning_tokens: 10, reasoning_tokens_in_output: true }).effectiveOutputTokens).toBeNull();
    });
    it("preserves plugin tool metadata and attempted nonexistent tool names without copying payloads", () => {
        const observations = projectMessage({ type: "tool_usage", tool_name: "plugin/new_tool", tool_type: "plugin-type",
            source: "plugin-source", status: "error", error_kind: "plugin-error", arguments: "secret-argument", content: "secret-output", duration_ms: 7 });
        const serialized = JSON.stringify(observations);
        expect(serialized).not.toContain("secret");
        for (const point of observations.filter(point => point.name.startsWith("covas_tool_"))) {
            expect(point.attributes).toEqual({ "tool.name": "plugin/new_tool", "tool.type": "plugin-type",
                source: "plugin-source", status: "error", "error.kind": "plugin-error" });
        }
        const missing = projectMessage({ type: "tool_usage", tool_name: "nonexistent_tool", status: "error", error_kind: "unknown_tool" });
        expect(missing.find(point => point.name === "covas_tool_calls_total")!.attributes["tool.name"]).toBe("nonexistent_tool");
    });
    it("preserves plugin provider, context, voice and language identifiers", () => {
        const points = projectMessage({ ...usage, type: "tts_usage", provider: "plugin/provider-v2", context: "plugin/context",
            output_voice: "plugin/voice " + "x".repeat(100), output_language: "yue-Hant-HK", operation_ms: 42 });
        for (const point of points.filter(point => point.name === "covas_usage_calls_total" || point.name === "covas_usage_latency_ms")) {
            expect(point.attributes["provider"]).toBe("plugin/provider-v2");
            expect(point.attributes["context"]).toBe("plugin/context");
            expect(point.attributes["output.voice"]).toBe("plugin/voice " + "x".repeat(100));
            expect(point.attributes["output.language"]).toBe("yue-Hant-HK");
        }
        const stt = projectMessage({ ...usage, type: "stt_usage", input_language: "en-US-u-sd-usca" });
        expect(stt.find(point => point.name === "covas_usage_calls_total")!.attributes["input.language"]).toBe("en-US-u-sd-usca");
    });
    it("preserves new backend message types, roles and diagnostic categories", () => {
        const cases = [
            [{ type: "plugin/event-v2" }, "covas_backend_messages_total", "message.type", "plugin/event-v2"],
            [{ type: "chat", role: "plugin-role" }, "covas_chat_messages_total", "chat.role", "plugin-role"],
            [{ type: "log", prefix: "NOTICE" }, "covas_logs_total", "log.level", "notice"],
            [{ type: "backend_process_state", status: "restarting" }, "covas_backend_process_events_total", "status", "restarting"],
            [{ type: "audio_pipeline_error", usage_kind: "plugin-audio", stage: "resample", error_kind: "plugin-error" }, "covas_audio_pipeline_errors_total", "stage", "resample"],
            [{ ...usage, status: "plugin-status", error_kind: "plugin-error" }, "covas_usage_calls_total", "status", "plugin-status"],
        ] as const;
        for (const [message, metric, key, value] of cases)
            expect(projectMessage(message).find(point => point.name === metric)!.attributes[key]).toBe(value);
    });
    it("uses unknown only for missing or non-string metadata", () => {
        for (const value of [undefined, null, "", "  ", 123, {}]) expect(metadataLabel(value)).toBe("unknown");
        expect(metadataLabel("  plugin name  ")).toBe("  plugin name  ");
        const points = projectMessage({ type: "tts_usage" });
        const attrs = points.find(point => point.name === "covas_usage_calls_total")!.attributes;
        for (const key of ["provider", "model.name", "context", "output.voice", "output.language", "status", "error.kind"])
            expect(attrs[key]).toBe("unknown");
    });
    it("preserves browser locale variants and timezone prefixes outside the old catalog", () => {
        spyOnProperty(navigator, "language", "get").and.returnValue("yue-Hant-HK-u-nu-hanidec");
        const resolved = Intl.DateTimeFormat().resolvedOptions();
        spyOn(Intl.DateTimeFormat.prototype, "resolvedOptions").and.returnValue({ ...resolved, timeZone: "UTC" });
        expect(localeResources()).toEqual({ "client.locale": "yue-Hant-HK-u-nu-hanidec",
            "client.locale.primary": "yue", "client.timezone.region": "UTC" });
    });
    it("does not combine local audio errors with provider outcomes", () => {
        const observations = projectMessage({ type: "audio_pipeline_error", usage_kind: "tts", stage: "playback", error_kind: "audio_device" });
        expect(observations.some(o => o.name === "covas_audio_pipeline_errors_total")).toBeTrue();
        expect(observations.some(o => o.name === "covas_usage_calls_total")).toBeFalse();
    });
    it("rejects invalid numeric measurements", () => {
        for (const value of [NaN, Infinity, -1, true, "12", null]) expect(measurement(value)).toBeNull();
        expect(measurement(1.5, true)).toBeNull();
    });
    it("uses TTS usage underrun stats without another event or duplicate model calls", () => {
        const message = { type: "tts_usage", context: "assistant", provider: "plugin", model_name: "tts",
            status: "success", audio_usage: { output_audio_duration_ms: 2000 }, num_underruns: 2 };
        const points = projectMessage(message);
        const calls = points.filter(point => point.name === "covas_usage_calls_total");
        expect(calls.length).toBe(1);
        expect(calls[0].attributes["playback.underrun"]).toBeTrue();
        expect(calls[0].attributes["playback.monitored"]).toBeTrue();
        expect(points.find(point => point.name === "covas_tts_underruns_total")?.value).toBe(2);
        const healthy = projectMessage({ ...message, num_underruns: 0 });
        expect(healthy.find(point => point.name === "covas_usage_calls_total")?.attributes["playback.underrun"]).toBeFalse();
        expect(healthy.some(point => point.name === "covas_tts_underruns_total")).toBeFalse();
        for (const value of [undefined, null, -1, 1.5]) {
            const unknown = projectMessage({ ...message, num_underruns: value });
            expect(unknown.some(point => point.name === "covas_tts_underruns_total")).toBeFalse();
            expect(unknown.find(point => point.name === "covas_usage_calls_total")?.attributes["playback.monitored"]).toBeUndefined();
        }
    });
    it("pairs each successful speech operation with its own audio duration for real-time factor", () => {
        for (const [type, audio, expected] of [
            ["stt_usage", { input_audio_duration_ms: 2000, output_audio_duration_ms: 20 }, 0.25],
            ["tts_usage", { input_audio_duration_ms: 20, output_audio_duration_ms: 1000 }, 0.5],
        ] as const) {
            const point = projectMessage({ type, status: "success", provider: "plugin", model_name: "speech-model",
                context: "speech", operation_ms: 500, latency_usage: { time_to_first_byte_ms: 10, response_ms: 100 }, audio_usage: audio })
                .find(point => point.name === "covas_audio_realtime_factor")!;
            expect(point.value).toBe(expected);
            expect(point.attributes["usage.kind"]).toBe(type === "stt_usage" ? "stt" : "tts");
            expect(point.attributes["provider"]).toBe("plugin");
            expect(point.attributes["histogram.schema"]).toBe("rtf-v1");
        }
    });
    it("excludes unpaired, invalid, failed and cancelled speech RTF samples without inventing zero", () => {
        const speech = { type: "tts_usage", status: "success", operation_ms: 500, audio_usage: { output_audio_duration_ms: 1000 } };
        for (const overrides of [
            { status: "error" }, { status: "cancelled" }, { type: "llm_usage" },
            { operation_ms: null }, { operation_ms: -1 }, { operation_ms: Infinity }, { operation_ms: "500" },
            ...[undefined, null, 0, -1, Infinity, "1000"].map(value => ({ audio_usage: { output_audio_duration_ms: value } })),
        ]) expect(projectMessage({ ...speech, ...overrides }).some(point => point.name === "covas_audio_realtime_factor")).toBeFalse();
        expect(projectMessage({ ...speech, operation_ms: 0 }).find(point => point.name === "covas_audio_realtime_factor")?.value).toBe(0);
        expect(projectMessage({ ...speech, operation_ms: Number.MAX_VALUE, audio_usage: { output_audio_duration_ms: Number.MIN_VALUE } })
            .some(point => point.name === "covas_audio_realtime_factor")).toBeFalse();
        const aggregation = new TelemetryAggregation();
        for (const [operation_ms, duration] of [[100, 1000], [900, 3000]]) {
            const point = projectMessage({ ...speech, operation_ms, audio_usage: { output_audio_duration_ms: duration } })
                .find(point => point.name === "covas_audio_realtime_factor")!;
            aggregation.record(point);
        }
        const row = aggregation.snapshot()[0];
        expect(row.count).toBe(2);
        expect(row.sum / row.count).toBeCloseTo(0.2);
    });
    it("retains exact histogram counts/sums/buckets while bounding percentile samples", () => {
        const aggregation = new TelemetryAggregation(2);
        for (const value of [0, 20, 50]) aggregation.record({ name: "covas_tool_duration_ms", value, attributes: {} });
        const row = aggregation.snapshot()[0];
        expect(row.count).toBe(3); expect(row.sum).toBe(70);
        expect(row.buckets.reduce((a, b) => a + b, 0)).toBe(3);
        expect(row.buckets[LATENCY_BUCKETS.indexOf(0)]).toBe(1);
        expect(row.samples).toEqual([20, 50]); expect(percentile(row.samples, .95)).toBe(50);
    });
});
