// telemetry.ts
import {
    AggregationTemporality,
    MeterProvider,
    PeriodicExportingMetricReader,
} from "@opentelemetry/sdk-metrics";
import { OTLPMetricExporter } from "@opentelemetry/exporter-metrics-otlp-http";
import { Resource, resourceFromAttributes } from "@opentelemetry/resources";
import { SEMRESATTRS_SERVICE_INSTANCE_ID } from "@opentelemetry/semantic-conventions";

import { Injectable } from "@angular/core";
import { BaseMessage, TauriService } from "./tauri.service";
import { EventMessage } from "./event.service.js";

@Injectable({
    providedIn: "root",
})
export class MetricsService {
    private sessionId = `${Date.now().toString()}-${
        Math.random().toString(36).substring(2, 15)
    }`;
    private exporter = new OTLPMetricExporter({
        url: "https://monitoring.covaslabs.com/v1/metrics",
        headers: {
            "User-Agent": "com.covaslabs.ui",
        },
        //temporalityPreference: AggregationTemporality.DELTA,
    });
    private metricReader = new PeriodicExportingMetricReader({
        exporter: this.exporter,
        exportIntervalMillis: 3000, // Adjust as needed
    });
    private meterProvider = new MeterProvider({
        readers: [this.metricReader],
        resource: resourceFromAttributes({
            "service.name": "com.covaslabs.ui",
            "service.version": "1.0.0",
            "service.namespace": "com.covaslabs",
            "service.instance.id": this.sessionId,
        }),
    });
    private messageTypeCounterMap = new Map<string, any>();
    private logPrefixCounterMap = new Map<string, any>();
    private chatRoleCounterMap = new Map<string, any>();
    private meter = this.meterProvider.getMeter("com.covaslabs.ui-events");

    constructor(private tauriService: TauriService) {
        const uiStartCounter = this.meter.createCounter(
            `message_type_ui_start_count`,
            {
                description: `Counts messages of type ui_start`,
            },
        );
        uiStartCounter.add(0);
        uiStartCounter.add(1);

        this.tauriService.output$.pipe().subscribe(
            (message: BaseMessage) => {
                let messageTypeCounter = this.messageTypeCounterMap.get(
                    message.type,
                );
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
}
