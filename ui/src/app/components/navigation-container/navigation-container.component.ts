import { CommonModule } from "@angular/common";
import { Component, OnDestroy, OnInit } from "@angular/core";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatChipsModule } from "@angular/material/chips";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatExpansionModule } from "@angular/material/expansion";
import { Subscription } from "rxjs";
import { EventMessage, EventService, GameEvent } from "../../services/event.service";
import { ProjectionsService } from "../../services/projections.service";
import { GetSystemEventsMessage, SystemEventsMessage, TauriService } from "../../services/tauri.service";

@Component({
    selector: "app-navigation-container",
    standalone: true,
    imports: [
        CommonModule,
        MatButtonModule,
        MatCardModule,
        MatChipsModule,
        MatIconModule,
        MatProgressSpinnerModule,
        MatExpansionModule,
    ],
    templateUrl: "./navigation-container.component.html",
    styleUrls: ["./navigation-container.component.scss"],
})
export class NavigationContainerComponent implements OnInit, OnDestroy {
    currentSystemName: string = "Unknown";
    currentSystemAddress: number | null = null;

    isLoading = false;
    errorMessage: string | null = null;
    lastUpdatedMs: number | null = null;

    systemRecord: any | null = null;
    totals = { bodies: null as number | null, nonBodies: null as number | null };
    signals: any[] = [];
    stations: any[] = [];
    bodies: any[] = [];
    systemMap: any[] = [];
    systemMeta: { label: string; value: string }[] = [];
    hoveredMapNodeId: string | number | null = null;
    hoveredMapNode: any | null = null;
    tooltipPosition = { x: 0, y: 0 };

    private subs: Subscription[] = [];
    private lastEventIndex = -1;
    private refreshScheduled = false;
    private readonly refreshEvents = new Set([
        "FSSDiscoveryScan",
        "FSSSignalDiscovered",
        "Scan",
        "SAASignalsFound",
        "FSSBodySignals",
        "ScanOrganic",
    ]);

    constructor(
        private projectionsService: ProjectionsService,
        private tauriService: TauriService,
        private eventService: EventService,
    ) {}

    ngOnInit(): void {
        this.subs.push(
            this.projectionsService.location$.subscribe((location) => {
                this.currentSystemName = location?.StarSystem ?? "Unknown";
                const newAddress = location?.SystemAddress ?? null;
                if (newAddress !== this.currentSystemAddress) {
                    this.currentSystemAddress = newAddress;
                    this.fetchSystemData();
                }
            }),
            this.tauriService.output$.subscribe((message) => this.handleBackendMessage(message)),
            this.eventService.events$.subscribe((events) => this.handleGameEvents(events)),
        );
    }

    ngOnDestroy(): void {
        this.subs.forEach((sub) => sub.unsubscribe());
    }

    manualRefresh(): void {
        this.fetchSystemData(true);
    }

    private handleBackendMessage(message: any): void {
        const typed = message as SystemEventsMessage;
        if (typed.type !== "system_events") {
            return;
        }

        // Ignore updates for other systems
        if (
            this.currentSystemAddress !== null &&
            typed.system_address !== null &&
            String(typed.system_address) !== String(this.currentSystemAddress)
        ) {
            return;
        }

        this.isLoading = false;

        if ((typed.data as any)?.error) {
            this.errorMessage = (typed.data as any).error;
            this.applySystemRecord(null);
            return;
        }

        const record = (typed.data as any)?.data ?? null;
        this.errorMessage = null;
        this.applySystemRecord(record);
    }

    private handleGameEvents(events: EventMessage[]): void {
        if (!events.length) return;

        const newEvents = events.slice(this.lastEventIndex + 1);
        this.lastEventIndex = events.length - 1;

        for (const msg of newEvents) {
            const evt = (msg as any).event as GameEvent | undefined;
            if (!evt || evt.kind !== "game") continue;

            const eventName = evt.content?.event;
            if (!eventName || !this.refreshEvents.has(eventName)) continue;

            // If the event carries a SystemAddress, ensure it matches the current one
            const eventSystemAddress = evt.content['SystemAddress'];
            if (
                this.currentSystemAddress !== null &&
                eventSystemAddress !== undefined &&
                eventSystemAddress !== null &&
                String(eventSystemAddress) !== String(this.currentSystemAddress)
            ) {
                continue;
            }

            this.scheduleRefresh();
        }
    }

    private scheduleRefresh(): void {
        if (this.refreshScheduled) return;
        if (this.currentSystemAddress === null) return;

        this.refreshScheduled = true;
        setTimeout(() => {
            this.refreshScheduled = false;
            this.fetchSystemData();
        }, 150);
    }

    private fetchSystemData(force = false): void {
        if (this.currentSystemAddress === null) {
            this.applySystemRecord(null);
            this.errorMessage = null;
            this.isLoading = false;
            return;
        }

        if (this.isLoading && !force) {
            return;
        }

        this.isLoading = true;
        this.errorMessage = null;

        const message: GetSystemEventsMessage = {
            type: "get_system_events",
            system_address: this.currentSystemAddress,
            timestamp: new Date().toISOString(),
        };

        this.tauriService.send_command(message);
    }

    private applySystemRecord(record: any | null): void {
        this.systemRecord = record;
        const systemInfo = record?.system_info ?? null;
        const systemName = systemInfo?.name ?? this.currentSystemName;
        this.totals = {
            bodies: systemInfo?.totals?.bodies ?? null,
            nonBodies: systemInfo?.totals?.non_bodies ?? null,
        };
        this.signals = systemInfo?.signals ?? [];
        const stations = Array.isArray(systemInfo?.stations) ? systemInfo.stations : [];
        this.stations = stations
            .slice()
            .sort((a: any, b: any) => this.getOrbitLs(a) - this.getOrbitLs(b));
        this.bodies = Array.isArray(systemInfo?.bodies) ? systemInfo.bodies : [];
        this.systemMap = this.buildSystemMap(this.bodies, systemName);
        this.systemMeta = this.buildSystemMeta(systemInfo);
        this.lastUpdatedMs = record?.last_updated ? record.last_updated * 1000 : null;
    }

    get bodiesDisplay(): string {
        return this.formatCount(this.bodies.length, this.totals.bodies);
    }

    getSignalDisplayName(signal: any): string {
        return signal?.name_localised || signal?.name || "Unknown";
    }

    getOrbitDisplay(station: any): string | null {
        const distance = this.getOrbitLs(station);
        if (!Number.isFinite(distance) || distance <= 0) {
            return null;
        }
        return `${Math.round(distance)} LS`;
    }

    getLocalizedBodySignals(body: any): string[] {
        const signals = Array.isArray(body?.signals) ? body.signals : [];
        return signals
            .map((signal: any) => signal?.Type_Localised || signal?.Type)
            .filter((name: any): name is string => Boolean(name));
    }

    getLocalizedBodyGenuses(body: any): string[] {
        const genuses = Array.isArray(body?.genuses) ? body.genuses : [];
        return genuses
            .map((genus: any) => {
                const name = genus?.Genus_Localised || genus?.Genus;
                if (!name) {
                    return null;
                }
                const scanned = genus?.scanned === true ? "scanned" : "unscanned";
                return `${name} (${scanned})`;
            })
            .filter((name: any): name is string => Boolean(name));
    }

    getLocalizedRingSignals(body: any): string[] {
        const rings = Array.isArray(body?.rings) ? body.rings : [];
        const results: string[] = [];
        for (const ring of rings) {
            const signals = Array.isArray(ring?.signals) ? ring.signals : [];
            const names = signals
                .map((signal: any) => signal?.Type_Localised || signal?.Type)
                .filter((name: any): name is string => Boolean(name));
            if (!names.length) continue;
            results.push(`${names.join(", ")}`);
        }
        return results;
    }

    getBodyOrbitDisplay(body: any): string | null {
        const distance = this.getOrbitLs(body);
        if (!Number.isFinite(distance) || distance < 0) {
            return null;
        }
        return `${Math.round(distance)} LS`;
    }

    getBodyStationMatches(body: any): any[] {
        const bodyName = body?.name;
        if (!bodyName) {
            return [];
        }
        return this.stations.filter((station: any) => station?.body === bodyName);
    }

    getBodyStationDisplay(body: any): string {
        const matches = this.getBodyStationMatches(body);
        if (!matches.length) {
            return "";
        }
        return matches
            .map((station: any) => `${station.name}${station.type ? ` (${station.type})` : ""}`)
            .join(", ");
    }

    setHoveredMapNode(node: any, event: MouseEvent): void {
        this.hoveredMapNodeId = node?.id ?? null;
        this.hoveredMapNode = node ?? null;
        this.updateHoveredPosition(event);
    }

    clearHoveredMapNode(): void {
        this.hoveredMapNodeId = null;
        this.hoveredMapNode = null;
    }

    updateHoveredPosition(event: MouseEvent): void {
        const offset = 12;
        this.tooltipPosition = {
            x: event.clientX + offset,
            y: event.clientY + offset,
        };
    }

    getBodyHighlights(body: any): string[] {
        const highlights: string[] = [];
        const type = body?.type ?? "";
        const isStar = type === "Star" || Boolean(body?.spectralClass);

        if (isStar) {
            if (body?.spectralClass) {
                highlights.push(`Spectral ${body.spectralClass}`);
            }
            if (body?.luminosity) {
                highlights.push(`Luminosity ${body.luminosity}`);
            }
            if (typeof body?.solarMasses === "number") {
                highlights.push(`${body.solarMasses.toFixed(2)} M☉`);
            }
            if (typeof body?.solarRadius === "number") {
                highlights.push(`${body.solarRadius.toFixed(2)} R☉`);
            }
            if (typeof body?.surfaceTemperature === "number") {
                highlights.push(`${Math.round(body.surfaceTemperature)} K`);
            }
            if (body?.isScoopable !== undefined) {
                highlights.push(body.isScoopable ? "Scoopable" : "Not scoopable");
            }
            return highlights;
        }

        if (typeof body?.gravity === "number") {
            highlights.push(`${body.gravity.toFixed(2)} g`);
        }
        if (typeof body?.earthMasses === "number") {
            highlights.push(`${body.earthMasses.toFixed(2)} M⊕`);
        }
        if (typeof body?.radius === "number") {
            highlights.push(`${Math.round(body.radius)} km`);
        }
        if (typeof body?.surfaceTemperature === "number") {
            highlights.push(`${Math.round(body.surfaceTemperature)} K`);
        }
        if (body?.terraformingState) {
            highlights.push(body.terraformingState);
        }
        if (body?.isLandable !== undefined) {
            highlights.push(body.isLandable ? "Landable" : "Not landable");
        }
        if (body?.atmosphereType) {
            highlights.push(body.atmosphereType);
        }
        if (body?.volcanismType) {
            highlights.push(body.volcanismType);
        }
        return highlights;
    }

    private buildSystemMap(bodies: any[], systemName: string | null): any[] {
        if (!Array.isArray(bodies) || !bodies.length) {
            return [];
        }

        const nodes = new Map<string | number, any>();
        const roots: any[] = [];

        for (const body of bodies) {
            const bodyId = this.getBodyId(body);
            if (bodyId === null) {
                continue;
            }
            nodes.set(bodyId, {
                id: bodyId,
                name: this.formatMapName(body, systemName),
                type: body?.type ?? null,
                body,
                children: [],
                depth: 0,
                scale: 1,
            });
        }

        for (const node of nodes.values()) {
            const parentId = this.getParentId(node.body);
            const parent = parentId !== null ? nodes.get(parentId) : null;
            if (parent) {
                parent.children.push(node);
            } else {
                roots.push(node);
            }
        }

        const sortNodes = (list: any[]) => {
            list.sort((a, b) => {
                const aDist = a?.body?.distanceToArrival ?? a?.body?.DistanceFromArrivalLS ?? null;
                const bDist = b?.body?.distanceToArrival ?? b?.body?.DistanceFromArrivalLS ?? null;
                if (typeof aDist === "number" && typeof bDist === "number") {
                    return aDist - bDist;
                }
                return String(a?.name ?? "").localeCompare(String(b?.name ?? ""));
            });
            for (const item of list) {
                if (Array.isArray(item.children) && item.children.length) {
                    sortNodes(item.children);
                }
            }
        };

        const applyDepth = (node: any, depth: number) => {
            node.depth = depth;
            node.scale = Math.max(0.55, 1 - depth * 0.15);
            node.childrenLayout = depth === 0 ? "row" : "column";
            if (Array.isArray(node.children)) {
                for (const child of node.children) {
                    applyDepth(child, depth + 1);
                }
            }
        };

        sortNodes(roots);
        for (const root of roots) {
            applyDepth(root, 0);
        }
        return roots;
    }

    private formatMapName(body: any, systemName: string | null): string {
        const rawName = body?.name ?? "Unknown body";
        if (!systemName || body?.type !== "Planet") {
            return rawName;
        }
        const prefix = `${systemName} `;
        if (rawName.startsWith(prefix)) {
            return rawName.slice(prefix.length);
        }
        return rawName;
    }

    private getBodyId(body: any): number | string | null {
        if (body?.bodyId !== undefined && body?.bodyId !== null) {
            return body.bodyId;
        }
        if (body?.body_id !== undefined && body?.body_id !== null) {
            return body.body_id;
        }
        if (body?.id !== undefined && body?.id !== null) {
            return body.id;
        }
        if (body?.name) {
            return body.name;
        }
        return null;
    }

    private getParentId(body: any): number | string | null {
        const parents = Array.isArray(body?.parents) ? body.parents : [];
        for (const parent of parents) {
            if (!parent || typeof parent !== "object") continue;
            for (const [key, value] of Object.entries(parent)) {
                if (key === "Null") continue;
                if (value !== undefined && value !== null) {
                    return value as number | string;
                }
            }
        }
        return null;
    }

    private formatCount(actual: number, total: number | null): string {
        if (typeof total === "number" && !Number.isNaN(total)) {
            return `${actual}/${total}`;
        }
        return `${actual}`;
    }

    private getOrbitLs(station: any): number {
        const raw = station?.orbit ?? station?.distanceToArrival;
        if (raw === undefined || raw === null) {
            return Number.POSITIVE_INFINITY;
        }
        if (typeof raw === "number") {
            return raw;
        }
        if (typeof raw === "string") {
            const parsed = parseFloat(raw.replace(/[^0-9.]/g, ""));
            return Number.isFinite(parsed) ? parsed : Number.POSITIVE_INFINITY;
        }
        return Number.POSITIVE_INFINITY;
    }

    private buildSystemMeta(systemInfo: any): { label: string; value: string }[] {
        const info = systemInfo?.information ?? {};
        const meta: { label: string; value: string }[] = [];
        if (info?.allegiance) {
            meta.push({ label: "Allegiance", value: info.allegiance });
        }
        if (info?.government) {
            meta.push({ label: "Government", value: info.government });
        }
        if (info?.faction) {
            meta.push({ label: "Faction", value: info.faction });
        }
        if (info?.factionState) {
            meta.push({ label: "Faction state", value: info.factionState });
        }
        if (info?.security) {
            meta.push({ label: "Security", value: info.security });
        }
        if (info?.economy) {
            meta.push({ label: "Economy", value: info.economy });
        }
        if (info?.secondEconomy) {
            meta.push({ label: "Second economy", value: info.secondEconomy });
        }
        if (info?.population) {
            meta.push({ label: "Population", value: String(info.population) });
        }
        if (info?.reserve) {
            meta.push({ label: "Reserve", value: info.reserve });
        }
        return meta;
    }
}
