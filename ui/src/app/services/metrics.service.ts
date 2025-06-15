// telemetry.ts
import {
    MeterProvider,
    PeriodicExportingMetricReader,
} from "@opentelemetry/sdk-metrics";
import { OTLPMetricExporter } from "@opentelemetry/exporter-metrics-otlp-http";
import { resourceFromAttributes } from "@opentelemetry/resources";
import { getCurrentWindow } from "@tauri-apps/api/window";

import { Injectable } from "@angular/core";
import { BaseMessage, TauriService } from "./tauri.service";

@Injectable({
    providedIn: "root",
})
export class MetricsService {
    private exporter = new OTLPMetricExporter({
        url: "https://monitoring.covaslabs.com/v1/metrics",
        headers: {
            "User-Agent": "com.covaslabs.ui",
        },
        //temporalityPreference: AggregationTemporality.DELTA,
    });
    private metricReader = new PeriodicExportingMetricReader({
        exporter: this.exporter,
        exportIntervalMillis: 10000,
    });
    private meterProvider = new MeterProvider({
        readers: [this.metricReader],
        resource: resourceFromAttributes({
            "service.name": "com.covaslabs.ui",
            "service.version": this.tauriService.commitHash,
            "service.namespace": "com.covaslabs",
            "service.instance.id": this.tauriService.sessionId,
            "service.install.id": this.tauriService.installId,
        }),
    });
    private messageTypeCounterMap = new Map<
        string,
        ReturnType<typeof this.meter.createCounter>
    >();
    private logPrefixCounterMap = new Map<
        string,
        ReturnType<typeof this.meter.createCounter>
    >();
    private chatRoleCounterMap = new Map<
        string,
        ReturnType<typeof this.meter.createCounter>
    >();
    private meter = this.meterProvider.getMeter("com.covaslabs.ui-events");
    private startedSessionsGauge = this.meter.createGauge(
        `started_sessions`,
        {
            description: `Counts number of started sessions`,
        },
    );
    private readySessionsGauge = this.meter.createGauge(
        `ready_sessions`,
        {
            description: `Counts number of ready sessions`,
        },
    );

    constructor(private tauriService: TauriService) {
        this.startedSessionsGauge.record(1);

        this.setupTeardown();

        this.tauriService.output$.pipe().subscribe(
            (message: BaseMessage) => {
                let messageTypeCounter = this.messageTypeCounterMap.get(
                    message.type,
                );
                if (message.type === "ready") {
                    this.readySessionsGauge.record(1);
                    this.startedSessionsGauge.record(0);
                }
                if (message.type === "start") {
                    this.readySessionsGauge.record(0);
                    this.startedSessionsGauge.record(1);
                }
                if (!messageTypeCounter) {
                    messageTypeCounter = this.meter.createCounter(
                        `message_type_${message.type}_count`,
                        {
                            description:
                                `Counts messages of type ${message.type}`,
                        },
                    );
                    messageTypeCounter.add(0);
                    this.messageTypeCounterMap.set(
                        message.type,
                        messageTypeCounter,
                    );
                }
                messageTypeCounter.add(1);

                if (message.type === "log") {
                    const logMessage = message;
                    let logPrefixCounter = this.logPrefixCounterMap.get(
                        logMessage["prefix"],
                    );
                    if (!logPrefixCounter) {
                        logPrefixCounter = this.meter.createCounter(
                            `log_prefix_${logMessage["prefix"]}_count`,
                            {
                                description: `Counts log messages with prefix ${
                                    logMessage["prefix"]
                                }`,
                            },
                        );
                        logPrefixCounter.add(0);
                        this.logPrefixCounterMap.set(
                            logMessage["prefix"],
                            logPrefixCounter,
                        );
                    }
                    logPrefixCounter.add(1);
                }
                if (message.type === "chat") {
                    const chatMessage = message;
                    let chatRoleCounter = this.chatRoleCounterMap.get(
                        chatMessage["role"],
                    );
                    if (!chatRoleCounter) {
                        chatRoleCounter = this.meter.createCounter(
                            `chat_role_${chatMessage["role"]}_count`,
                            {
                                description: `Counts chat messages with role ${
                                    chatMessage["role"]
                                }`,
                            },
                        );
                        chatRoleCounter.add(0);
                        this.chatRoleCounterMap.set(
                            chatMessage["role"],
                            chatRoleCounter,
                        );
                    }
                    chatRoleCounter.add(1);
                }
            },
        );
    }

    private async setupTeardown(): Promise<void> {
        const unlisten = await getCurrentWindow().onCloseRequested(
            async (event) => {
                this.readySessionsGauge.record(0);
                this.startedSessionsGauge.record(0);
                await this.metricReader.shutdown();
                unlisten();
            },
        );
    }
}
