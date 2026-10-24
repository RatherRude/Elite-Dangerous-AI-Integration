import { Inject, Injectable, InjectionToken, OnDestroy } from "@angular/core";
import { BehaviorSubject, Subscription } from "rxjs";
import { AggregationType, MeterProvider, PeriodicExportingMetricReader, PushMetricExporter } from "@opentelemetry/sdk-metrics";
import { OTLPMetricExporter } from "@opentelemetry/exporter-metrics-otlp-http";
import { resourceFromAttributes } from "@opentelemetry/resources";
import { TauriService } from "./tauri.service";
import { Labels, localeResources, MetricAggregate, METRICS, Observation, projectMessage, TelemetryAggregation } from "./telemetry";

export interface TelemetrySnapshot {
    role: string; exporting: boolean; resources: Labels; started: string; ready: string | null;
    state: string; elapsedMs: number; exportState: string; lastExport: string | null;
    endpoint: string; metrics: MetricAggregate[];
}
export const METRICS_ENDPOINT = "https://monitoring.covaslabs.com/v1/metrics";
export const METRIC_EXPORTER_FACTORY = new InjectionToken<() => PushMetricExporter>("metric exporter factory", {
    providedIn: "root", factory: () => () => new OTLPMetricExporter({
        url: METRICS_ENDPOINT, timeoutMillis: 3000,
        // Explicit headers select the SDK's response-aware XHR transport.
        // sendBeacon only acknowledges enqueueing and hides HTTP failures.
        headers: { "Content-Type": "application/json" },
    }),
});

/** One owner per primary renderer. The same observations feed export and local aggregation. */
@Injectable({ providedIn: "root" })
export class MetricsService implements OnDestroy {
    private provider?: MeterProvider;
    private instruments = new Map<string, { add?: (value: number, attrs: Labels) => void; record?: (value: number, attrs: Labels) => void }>();
    private aggregation = new TelemetryAggregation();
    private startedAt = performance.now();
    private lastIndex = -1;
    private ended = false;
    private pending?: ReturnType<typeof setTimeout>;
    private subscriptions = new Subscription();
    private state: TelemetrySnapshot;
    private subject: BehaviorSubject<TelemetrySnapshot>;
    public readonly telemetrySnapshot$;

    constructor(private tauri: TauriService, @Inject(METRIC_EXPORTER_FACTORY) createExporter: () => PushMetricExporter) {
        this.state = {
            role: tauri.runtimeRole, exporting: tauri.runtimeRole === "primary_desktop",
            resources: { "service.name": "com.covaslabs.ui", "service.namespace": "com.covaslabs",
                "service.version": tauri.commitHash, "service.instance.id": tauri.sessionId,
                "service.install.id": tauri.installId, ...localeResources() },
            started: new Date().toISOString(), ready: null, state: "started", elapsedMs: 0,
            exportState: "not_attempted", lastExport: null, endpoint: METRICS_ENDPOINT, metrics: [],
        };
        this.subject = new BehaviorSubject(this.snapshot());
        this.telemetrySnapshot$ = this.subject.asObservable();
        if (!this.state.exporting) return;
        const delegate = createExporter();
        const exporter: PushMetricExporter = {
            export: (metrics, callback) => {
                this.state.exportState = "attempting";
                this.state.lastExport = new Date().toISOString();
                this.publishSoon();
                delegate.export(metrics, result => {
                    this.state.exportState = result.code === 0 ? "succeeded" : "failed";
                    this.publishSoon(); callback(result);
                });
            },
            forceFlush: () => delegate.forceFlush(), shutdown: () => delegate.shutdown(),
            ...(delegate.selectAggregationTemporality ? { selectAggregationTemporality: delegate.selectAggregationTemporality.bind(delegate) } : {}),
        };
        this.provider = new MeterProvider({
            resource: resourceFromAttributes(this.state.resources),
            readers: [new PeriodicExportingMetricReader({ exporter, exportIntervalMillis: 10000, exportTimeoutMillis: 4000 })],
            views: Object.entries(METRICS).map(([name, definition]) => ({
                // Omitting this restores the SDK's lossy default limit (2,000).
                // Infinity disables its overflow bucket; ingestion policy is server-side.
                instrumentName: name, aggregationCardinalityLimit: Infinity,
                ...(definition.histogram ? { aggregation: { type: AggregationType.EXPLICIT_BUCKET_HISTOGRAM,
                    options: { boundaries: definition.boundaries! } } } : {}),
            })),
        });
        const meter = this.provider.getMeter("com.covaslabs.ui-events", "3");
        for (const [name, definition] of Object.entries(METRICS)) {
            this.instruments.set(name, definition.histogram
                ? meter.createHistogram(name, { unit: definition.unit })
                : meter.createCounter(name, { unit: definition.unit }));
        }
        this.record({ name: "covas_sessions_total", value: 1, attributes: { state: "started" } });
        this.subscriptions.add(tauri.output$.subscribe(message => {
            if (message.index <= this.lastIndex || this.ended) return;
            this.lastIndex = message.index;
            if (message.type === "ready") {
                if (!this.state.ready) {
                    this.state.ready = new Date().toISOString();
                    this.record({ name: "covas_sessions_total", value: 1, attributes: { state: "ready" } });
                }
                this.state.state = "configuring";
            }
            if (["start", "running_config"].includes(message.type)) this.state.state = "running";
            if (message.type === "config") this.state.state = "configuring";
            if (message.type === "startup_error" || (message.type === "backend_process_state" && !message["expected"])) this.state.state = "error";
            for (const observation of projectMessage(message)) this.record(observation);
            this.publishSoon();
        }));
        tauri.windowCloseCallbacks.push(() => this.close());
        this.publishSoon();
    }
    private record(observation: Observation): void {
        const mapped = this.aggregation.record(observation);
        const instrument = this.instruments.get(mapped.name);
        if (METRICS[mapped.name].histogram) instrument?.record?.(mapped.value, mapped.attributes);
        else instrument?.add?.(mapped.value, mapped.attributes);
    }
    private snapshot(): TelemetrySnapshot {
        return { ...this.state, elapsedMs: this.ended ? this.state.elapsedMs : performance.now() - this.startedAt,
            metrics: this.aggregation.snapshot() };
    }
    public getSnapshot(): TelemetrySnapshot { return this.snapshot(); }
    private publishSoon(): void {
        if (this.pending !== undefined) return;
        this.pending = setTimeout(() => { this.pending = undefined; this.subject.next(this.snapshot()); }, 250);
    }
    public async close(): Promise<void> {
        if (this.ended || !this.state.exporting) return;
        this.state.elapsedMs = performance.now() - this.startedAt;
        this.ended = true; this.state.state = "ended";
        this.subscriptions.unsubscribe();
        this.record({ name: "covas_sessions_total", value: 1, attributes: { state: "ended" } });
        this.record({ name: "covas_session_duration_ms", value: this.state.elapsedMs, attributes: {} });
        this.subject.next(this.snapshot());
        let timer: ReturnType<typeof setTimeout> | undefined;
        try {
            await Promise.race([
                (async () => { try { await this.provider?.forceFlush(); } finally { await this.provider?.shutdown(); } })(),
                new Promise<void>(resolve => { timer = setTimeout(resolve, 4500); }),
            ]);
        } catch { this.state.exportState = "failed"; }
        finally { clearTimeout(timer); }
    }
    ngOnDestroy(): void {
        this.subscriptions.unsubscribe(); clearTimeout(this.pending);
        void this.close();
    }
}
