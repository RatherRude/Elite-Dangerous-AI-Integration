import { ReplaySubject } from "rxjs";
import { InMemoryMetricExporter, AggregationTemporality, DataPointType } from "@opentelemetry/sdk-metrics";
import { LATENCY_BUCKETS } from "./telemetry";
import { MetricsService } from "./metrics.service";
import { TauriService } from "./tauri.service";

describe("metrics ownership and lifecycle", () => {
    let service: MetricsService;
    let messages: ReplaySubject<any>;
    let exporter: InMemoryMetricExporter;
    const create = (role = "primary_desktop") => {
        messages = new ReplaySubject(100);
        exporter = new InMemoryMetricExporter(AggregationTemporality.CUMULATIVE);
        const facade = { runtimeRole: role, installId: "install", sessionId: "session", commitHash: "test",
            output$: messages.asObservable(), windowCloseCallbacks: [] } as unknown as TauriService;
        service = new MetricsService(facade, () => exporter);
    };
    afterEach(async () => { await service.close(); service.ngOnDestroy(); });
    it("does not create an export pipeline in remote or overlay windows", () => {
        for (const role of ["remote", "overlay"]) {
            create(role);
            messages.next({ index: 0, type: "llm_usage" });
            expect(service.getSnapshot().exporting).toBeFalse();
            expect(service.getSnapshot().metrics.length).toBe(0);
            service.ngOnDestroy();
        }
    });
    it("deduplicates replayed indices and records readiness once across backend restarts", () => {
        create();
        for (const [index, type] of [[0, "ready"], [0, "ready"], [1, "start"], [2, "ready"], [3, "running_config"]]) messages.next({ index, type });
        const snapshot = service.getSnapshot();
        const ready = snapshot.metrics.find(row => row.name === "covas_sessions_total" && row.attributes["state"] === "ready");
        expect(ready?.sum).toBe(1);
        expect(snapshot.state).toBe("running");
        expect(snapshot.metrics.filter(row => row.name === "covas_backend_messages_total").reduce((sum, row) => sum + row.sum, 0)).toBe(4);
    });
    it("records terminal observations once and closes despite exporter errors", async () => {
        create();
        spyOn(exporter, "export").and.callFake((metrics, callback) => callback({ code: 1 }));
        await service.close(); await service.close();
        const snapshot = service.getSnapshot();
        expect(snapshot.state).toBe("ended");
        expect(snapshot.metrics.find(row => row.name === "covas_sessions_total" && row.attributes["state"] === "ended")?.sum).toBe(1);
        expect(snapshot.metrics.find(row => row.name === "covas_session_duration_ms")?.count).toBe(1);
        expect(snapshot.exportState).toBe("failed");
    });
    it("exports exactly the locally displayed histogram observations and millisecond boundaries", async () => {
        create();
        messages.next({ index: 0, type: "tts_usage", schema_version: 3, provider: "openai", model_name: "gpt-4o-mini-tts",
            output_voice: "nova", context: "assistant", status: "error", error_kind: "timeout", operation_ms: 123 });
        const local = service.getSnapshot().metrics.find(row => row.name === "covas_usage_latency_ms")!;
        await service.close();
        const exported = exporter.getMetrics()[0];
        expect(exported.resource.attributes["service.instance.id"]).toBe("session");
        const histogram = exported.scopeMetrics.flatMap(scope => scope.metrics).find(metric => metric.descriptor.name === "covas_usage_latency_ms");
        if (histogram?.dataPointType !== DataPointType.HISTOGRAM) throw new Error("Expected histogram");
        expect(histogram.descriptor.unit).toBe("ms");
        expect(histogram.dataPoints[0].attributes).toEqual(local.attributes);
        expect(histogram.dataPoints[0].value.count).toBe(local.count);
        expect(histogram.dataPoints[0].value.sum).toBe(local.sum);
        expect(histogram.dataPoints[0].value.buckets.boundaries).toEqual(LATENCY_BUCKETS);
        expect(histogram.dataPoints[0].value.buckets.counts).toEqual(local.buckets);
    });
    it("preserves distinct local and SDK series beyond both former cardinality limits", async () => {
        create();
        for (let index = 0; index < 2105; index++) messages.next({ index, type: "tool_usage",
            tool_name: `plugin/tool-${index}`, tool_type: "plugin-type", source: "plugin-source", status: "success" });
        messages.next({ index: 2105, type: "tool_usage", tool_name: "plugin/tool-2104", tool_type: "plugin-type", source: "plugin-source", status: "success" });
        const local = service.getSnapshot().metrics.filter(row => row.name === "covas_tool_calls_total");
        expect(local.length).toBe(2105);
        await service.close();
        const metric = exporter.getMetrics()[0].scopeMetrics.flatMap(scope => scope.metrics)
            .find(metric => metric.descriptor.name === "covas_tool_calls_total");
        if (metric?.dataPointType !== DataPointType.SUM) throw new Error("Expected counter");
        expect(metric.dataPoints.length).toBe(2105);
        const exported = new Map(metric.dataPoints.map(point => [point.attributes["tool.name"], point]));
        for (const row of local) {
            const point = exported.get(row.attributes["tool.name"]);
            expect(point?.attributes).toEqual(row.attributes);
            expect(point?.value).toBe(row.sum);
        }
        expect(exported.get("plugin/tool-2104")?.value).toBe(2);
    });
});
