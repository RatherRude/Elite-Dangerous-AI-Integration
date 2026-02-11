import {
    AfterViewInit,
    Component,
    ElementRef,
    EventEmitter,
    NgZone,
    OnDestroy,
    OnInit,
    Output,
    ViewChild,
} from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import { MatSelectModule } from "@angular/material/select";
import { MatSlideToggle } from "@angular/material/slide-toggle";
import { MatExpansionModule } from "@angular/material/expansion";
import { MatSnackBarModule } from "@angular/material/snack-bar";
import { fromEvent, Subscription } from "rxjs";
import { DataSet } from "vis-data";
import { Network } from "vis-network";
import type { Edge, Node } from "vis-network";
import {
    QuestAction,
    QuestCatalog,
    QuestCondition,
    QuestDefinition,
    QuestPlanStep,
    QuestStage,
    QuestsService,
} from "../../services/quests.service";

type ConditionValueKind = "string" | "number" | "boolean" | "null";
type StageTransitionItem = {
    conditionLabel: string;
    targets: string[];
};

@Component({
    selector: "app-quests-settings",
    standalone: true,
    imports: [
        CommonModule,
        FormsModule,
        MatButtonModule,
        MatCardModule,
        MatFormFieldModule,
        MatIconModule,
        MatInputModule,
        MatSelectModule,
        MatSlideToggle,
        MatExpansionModule,
        MatSnackBarModule,
    ],
    templateUrl: "./quests-settings.component.html",
    styleUrl: "./quests-settings.component.scss",
})
export class QuestsSettingsComponent implements OnInit, OnDestroy, AfterViewInit {
    @Output() closeRequested = new EventEmitter<void>();
    
    catalog: QuestCatalog | null = null;
    rawYaml = "";
    selectedQuestId: string | null = null;
    loadError: string | null = null;
    catalogPath: string | null = null;
    loadPending = false;
    lastLoadedAt: string | null = null;
    selectedStageId: string | null = null;
    private network: Network | null = null;
    private nodes = new DataSet<Node>();
    private edges = new DataSet<Edge>();
    private subscriptions: Subscription[] = [];
    private layoutPending = false;
    private stageGraphSubscriptions: Subscription[] = [];
    private collapsedStageKeys = new Set<string>();
    private collapseInitialized = false;

    @ViewChild("stageNetwork") stageNetworkRef?: ElementRef<HTMLDivElement>;

    constructor(
        private questsService: QuestsService,
        private ngZone: NgZone,
    ) {}

    ngOnInit(): void {
        this.subscriptions.push(
            this.questsService.catalog$.subscribe((catalog) => {
                this.catalog = catalog;
                if (
                    this.selectedQuestId &&
                    !catalog?.quests.some((quest) => quest.id === this.selectedQuestId)
                ) {
                    this.selectedQuestId = null;
                    this.selectedStageId = null;
                }
                if (catalog && !this.collapseInitialized) {
                    this.collapseAllStages(catalog);
                    this.collapseInitialized = true;
                }
                this.scheduleLayout();
            }),
            this.questsService.rawYaml$.subscribe((rawYaml) => {
                this.rawYaml = rawYaml;
            }),
            this.questsService.loadError$.subscribe((error) => {
                this.loadError = error;
            }),
            this.questsService.catalogPath$.subscribe((path) => {
                this.catalogPath = path;
            }),
            this.questsService.loadPending$.subscribe((pending) => {
                this.loadPending = pending;
            }),
            this.questsService.lastLoadedAt$.subscribe((timestamp) => {
                this.lastLoadedAt = timestamp;
            }),
            this.questsService.saveResult$.subscribe((result) => {
                this.loadError = result.success
                    ? null
                    : result.message || "Failed to save quest catalog";
            }),
        );

        // Always reload the catalog when component initializes to ensure fresh data
        this.questsService.loadCatalog();
    }

    ngAfterViewInit(): void {
        if (!this.catalog && !this.loadPending) {
            this.questsService.loadCatalog();
        }
        this.initializeNetwork();
        this.bindStageGraphListeners();
        this.scheduleLayout();
    }

    ngOnDestroy(): void {
        this.subscriptions.forEach((subscription) => subscription.unsubscribe());
        this.stageGraphSubscriptions.forEach((subscription) =>
            subscription.unsubscribe(),
        );
        if (this.network) {
            this.network.destroy();
            this.network = null;
        }
    }

    get selectedQuest(): QuestDefinition | null {
        if (!this.catalog || !this.selectedQuestId) {
            return null;
        }
        return (
            this.catalog.quests.find(
                (quest) => quest.id === this.selectedQuestId,
            ) || null
        );
    }

    get selectedStage(): QuestStage | null {
        const quest = this.selectedQuest;
        if (!quest || !this.selectedStageId) {
            return null;
        }
        return quest.stages.find((stage) => stage.id === this.selectedStageId) || null;
    }

    selectQuest(questId: string): void {
        this.selectedQuestId = questId;
        this.selectedStageId = null;
        this.scheduleLayout();
    }

    onStageIdChange(stage: QuestStage): void {
        this.selectedStageId = stage.id;
        this.scheduleLayout();
    }

    requestNetworkRefresh(): void {
        this.scheduleLayout();
    }

    reloadCatalog(): void {
        this.questsService.loadCatalog();
    }

    saveCatalog(): void {
        if (this.catalog) {
            this.questsService.saveCatalog(this.catalog);
        }
    }

    addQuest(): void {
        if (!this.catalog) {
            this.catalog = { version: "1.0", quests: [] };
        }
        const newQuest = this.createQuest();
        this.catalog.quests = [...this.catalog.quests, newQuest];
        this.selectedQuestId = newQuest.id;
        this.selectedStageId = null;
        this.collapseStagesForQuest(newQuest);
        this.scheduleLayout();
    }

    removeQuest(index: number): void {
        if (!this.catalog) {
            return;
        }
        const removed = this.catalog.quests[index];
        this.catalog.quests.splice(index, 1);
        if (removed?.id === this.selectedQuestId) {
            this.selectedQuestId =
                this.catalog.quests[0]?.id ?? null;
            this.selectedStageId = null;
        }
        this.scheduleLayout();
    }

    addStage(quest: QuestDefinition): void {
        const newStage = this.createStage(quest);
        quest.stages = [...quest.stages, newStage];
        const collapseKey = this.getStageCollapseKey(quest.id, newStage.id);
        if (collapseKey) {
            this.collapsedStageKeys.add(collapseKey);
        }
        this.scheduleLayout();
    }

    removeStage(quest: QuestDefinition, index: number): void {
        const removedStageId = quest.stages[index]?.id;
        quest.stages.splice(index, 1);
        const collapseKey = this.getStageCollapseKey(quest.id, removedStageId);
        if (collapseKey) {
            this.collapsedStageKeys.delete(collapseKey);
        }
        if (removedStageId && removedStageId === this.selectedStageId) {
            this.selectedStageId = null;
        }
        this.scheduleLayout();
    }

    addPlanStep(stage: QuestStage): void {
        if (!stage.plan) {
            stage.plan = [];
        }
        stage.plan.push(this.createPlanStep());
        this.scheduleLayout();
    }

    removePlanStep(stage: QuestStage, index: number): void {
        stage.plan?.splice(index, 1);
        this.scheduleLayout();
    }

    addCondition(step: QuestPlanStep): void {
        step.conditions.push(this.createCondition());
    }

    removeCondition(step: QuestPlanStep, index: number): void {
        step.conditions.splice(index, 1);
    }

    addAction(step: QuestPlanStep): void {
        step.actions.push(this.createAction());
        this.scheduleLayout();
    }

    removeAction(step: QuestPlanStep, index: number): void {
        step.actions.splice(index, 1);
        this.scheduleLayout();
    }

    createQuest(): QuestDefinition {
        const questIndex = this.catalog?.quests.length ?? 0;
        return {
            id: `new_quest_${questIndex + 1}`,
            title: "New Quest",
            description: "Describe the quest objective.",
            active: false,
            stages: [this.createStage()],
        };
    }

    createStage(quest?: QuestDefinition): QuestStage {
        const stageIndex = quest?.stages.length ?? 0;
        return {
            id: `stage_${stageIndex + 1}`,
            description: "Describe this stage.",
            instructions: "Provide player-facing instructions.",
            plan: [this.createPlanStep()],
        };
    }

    createPlanStep(): QuestPlanStep {
        return {
            conditions: [this.createCondition()],
            actions: [this.createAction()],
        };
    }

    createCondition(): QuestCondition {
        return {
            source: "event",
            path: "event",
            operator: "equals",
            value: "",
        };
    }

    createAction(): QuestAction {
        return {
            action: "log",
            message: "Describe the outcome.",
        };
    }

    getConditionValueKind(condition: QuestCondition): ConditionValueKind {
        if (condition.value === null) {
            return "null";
        }
        if (typeof condition.value === "boolean") {
            return "boolean";
        }
        if (typeof condition.value === "number") {
            return "number";
        }
        return "string";
    }

    setConditionValueKind(
        condition: QuestCondition,
        kind: ConditionValueKind,
    ): void {
        switch (kind) {
            case "null":
                condition.value = null;
                break;
            case "boolean":
                condition.value = false;
                break;
            case "number":
                condition.value = 0;
                break;
            default:
                condition.value = "";
        }
    }

    updateConditionValue(
        condition: QuestCondition,
        rawValue: string,
    ): void {
        const kind = this.getConditionValueKind(condition);
        if (kind === "number") {
            const parsed = Number(rawValue);
            condition.value = Number.isNaN(parsed) ? 0 : parsed;
            return;
        }
        if (kind === "boolean") {
            condition.value = rawValue === "true";
            return;
        }
        condition.value = rawValue;
    }

    getStageColumns(quest: QuestDefinition): QuestStage[][] {
        return this.buildStageGraph(quest).columns;
    }

    getStageDistance(quest: QuestDefinition, stageId?: string): number | null {
        if (!stageId) {
            return null;
        }
        return this.buildStageGraph(quest).distances.get(stageId) ?? null;
    }

    getStageById(
        quest: QuestDefinition,
        stageId?: string,
    ): QuestStage | null {
        if (!stageId) {
            return null;
        }
        return quest.stages.find((stage) => stage.id === stageId) || null;
    }

    getAdvanceStageTargets(stage: QuestStage): string[] {
        const targets: string[] = [];
        for (const step of stage.plan ?? []) {
            for (const action of step.actions ?? []) {
                if (action.action === "advance_stage" && action.target_stage_id) {
                    targets.push(action.target_stage_id);
                }
            }
        }
        return [...new Set(targets)];
    }

    isLoopback(
        quest: QuestDefinition,
        fromStageId?: string,
        targetStageId?: string,
    ): boolean {
        if (!fromStageId || !targetStageId) {
            return false;
        }
        const fromDistance = this.getStageDistance(quest, fromStageId);
        const targetDistance = this.getStageDistance(quest, targetStageId);
        if (fromDistance === null || targetDistance === null) {
            return false;
        }
        return targetDistance <= fromDistance;
    }

    isStageCollapsed(questId: string | null | undefined, stageId: string): boolean {
        const key = this.getStageCollapseKey(questId, stageId);
        return key ? this.collapsedStageKeys.has(key) : false;
    }

    toggleStageCollapsed(questId: string | null | undefined, stageId: string): void {
        const key = this.getStageCollapseKey(questId, stageId);
        if (!key) {
            return;
        }
        if (this.collapsedStageKeys.has(key)) {
            this.collapsedStageKeys.delete(key);
        } else {
            this.collapsedStageKeys.add(key);
        }
        this.scheduleLayout();
    }

    private buildStageGraph(quest: QuestDefinition): {
        columns: QuestStage[][];
        distances: Map<string, number>;
    } {
        const stageMap = new Map<string, QuestStage>();
        quest.stages.forEach((stage) => stageMap.set(stage.id, stage));
        const distances = new Map<string, number>();
        const columns: QuestStage[][] = [];
        const startStage = quest.stages[0];
        if (!startStage) {
            return { columns, distances };
        }
        const queue: string[] = [startStage.id];
        distances.set(startStage.id, 0);

        while (queue.length) {
            const stageId = queue.shift();
            if (!stageId) {
                continue;
            }
            const stage = stageMap.get(stageId);
            if (!stage) {
                continue;
            }
            const currentDistance = distances.get(stageId) ?? 0;
            for (const targetId of this.getAdvanceStageTargets(stage)) {
                if (!stageMap.has(targetId)) {
                    continue;
                }
                if (!distances.has(targetId)) {
                    distances.set(targetId, currentDistance + 1);
                    queue.push(targetId);
                }
            }
        }

        for (const stage of quest.stages) {
            if (!distances.has(stage.id)) {
                distances.set(stage.id, 0);
            }
        }

        const maxDistance = Math.max(
            ...Array.from(distances.values()),
            0,
        );
        for (let i = 0; i <= maxDistance; i += 1) {
            columns.push([]);
        }
        for (const stage of quest.stages) {
            const distance = distances.get(stage.id) ?? 0;
            columns[distance].push(stage);
        }

        return { columns, distances };
    }

    private getStageCollapseKey(
        questId?: string | null,
        stageId?: string | null,
    ): string | null {
        if (!questId || !stageId) {
            return null;
        }
        return `${questId}:${stageId}`;
    }

    private collapseStagesForQuest(quest: QuestDefinition): void {
        quest.stages.forEach((stage) => {
            const key = this.getStageCollapseKey(quest.id, stage.id);
            if (key) {
                this.collapsedStageKeys.add(key);
            }
        });
    }

    private collapseAllStages(catalog: QuestCatalog): void {
        catalog.quests.forEach((quest) => this.collapseStagesForQuest(quest));
    }

    private bindStageGraphListeners(): void {
        this.stageGraphSubscriptions.push(
            fromEvent(window, "resize").subscribe(() => this.scheduleLayout()),
        );
    }

    private scheduleLayout(): void {
        if (this.layoutPending) {
            return;
        }
        this.layoutPending = true;
        requestAnimationFrame(() => {
            this.layoutPending = false;
            this.initializeNetwork();
            this.refreshNetwork();
        });
    }

    private initializeNetwork(): void {
        if (this.network) {
            return;
        }
        const container = this.stageNetworkRef?.nativeElement;
        if (!container) {
            return;
        }
        this.network = new Network(
            container,
            { nodes: this.nodes, edges: this.edges },
            {
                layout: {
                    hierarchical: {
                        direction: "LR",
                        sortMethod: "directed",
                        levelSeparation: 160,
                        nodeSpacing: 150,
                        treeSpacing: 220,
                        blockShifting: true,
                        edgeMinimization: true,
                        parentCentralization: true,
                    },
                },
                physics: { enabled: false },
                nodes: {
                    shape: "box",
                    margin: { top: 8, right: 8, bottom: 8, left: 8 },
                    color: {
                        background: "rgba(32, 32, 32, 0.9)",
                        border: "rgba(70, 70, 70, 0.9)",
                    },
                    font: { color: "#f0f0f0", size: 12 },
                    widthConstraint: { maximum: 260 },
                },
                edges: {
                    arrows: { to: { enabled: true, scaleFactor: 0.7 } },
                    color: { color: "rgba(126, 224, 129, 0.7)" },
                    smooth: {
                        enabled: true,
                        type: "cubicBezier",
                        forceDirection: "horizontal",
                        roundness: 0.25,
                    },
                },
                interaction: {
                    hover: true,
                    multiselect: false,
                },
            },
        );
        this.network.on(
            "click",
            (params: { nodes: Array<string | number> }) => {
            const [nodeId] = params.nodes;
            this.ngZone.run(() => {
                this.selectedStageId = nodeId
                    ? this.resolveSelectedStageFromNodeId(String(nodeId))
                    : null;
            });
            },
        );
    }

    private refreshNetwork(): void {
        const quest = this.selectedQuest;
        if (!this.network || !quest) {
            this.nodes.clear();
            this.edges.clear();
            return;
        }

        const graph = this.buildStageGraph(quest);
        const nodes: Node[] = [];
        const edges: Edge[] = [];

        let edgeIndex = 0;
        for (const stage of quest.stages) {
            const stageLevel = (graph.distances.get(stage.id) ?? 0) * 2;
            const isSelected = stage.id === this.selectedStageId;
            nodes.push({
                id: stage.id,
                label: this.getStageCardLabel(stage),
                level: stageLevel,
                color: {
                    background: isSelected
                        ? "rgba(58, 85, 58, 0.9)"
                        : "rgba(32, 32, 32, 0.9)",
                    border: isSelected
                        ? "rgba(154, 240, 157, 0.9)"
                        : "rgba(70, 70, 70, 0.9)",
                },
                font: { color: "#f0f0f0", size: 12 },
                margin: { top: 10, right: 10, bottom: 10, left: 10 },
            });

            const transitions = this.getStageTransitionItems(stage);
            transitions.forEach((transition, transitionIndex) => {
                const conditionNodeId = this.getConditionNodeId(
                    stage.id,
                    transitionIndex,
                );
                nodes.push({
                    id: conditionNodeId,
                    label: `${transitionIndex + 1}`,
                    level: stageLevel + 1,
                    shape: "box",
                    color: {
                        background: "rgba(26, 34, 26, 0.92)",
                        border: "rgba(112, 168, 114, 0.88)",
                    },
                    font: { color: "rgba(202, 242, 203, 0.95)", size: 11 },
                    margin: { top: 6, right: 8, bottom: 6, left: 8 },
                    widthConstraint: { maximum: 48 },
                });
                // This subtle connector keeps the stage and its condition list visually unified.
                edges.push({
                    id: `edge-${edgeIndex += 1}`,
                    from: stage.id,
                    to: conditionNodeId,
                    arrows: { to: { enabled: false } },
                    color: { color: "rgba(105, 140, 108, 0.5)" },
                    dashes: [4, 4],
                    smooth: {
                        enabled: true,
                        type: "cubicBezier",
                        forceDirection: "horizontal",
                        roundness: 0.12,
                    },
                });

                transition.targets.forEach((targetId) => {
                    if (!this.getStageById(quest, targetId)) {
                        return;
                    }
                    const loopback = this.isLoopback(quest, stage.id, targetId);
                    const edgeColor = loopback
                        ? "rgba(120, 170, 255, 0.85)"
                        : "rgba(126, 224, 129, 0.7)";
                    edges.push({
                        id: `edge-${edgeIndex += 1}`,
                        from: conditionNodeId,
                        to: targetId,
                        arrows: { to: { enabled: true, scaleFactor: 0.7 } },
                        color: { color: edgeColor },
                        smooth: loopback
                            ? { enabled: true, type: "curvedCW", roundness: 0.35 }
                            : {
                                enabled: true,
                                type: "cubicBezier",
                                forceDirection: "horizontal",
                                roundness: 0.22,
                            },
                    });
                });
            });
        }

        for (const stage of quest.stages) {
            if (!nodes.some((node) => node.id === stage.id)) {
                nodes.push({
                    id: stage.id,
                    label: this.getStageCardLabel(stage),
                    level: (graph.distances.get(stage.id) ?? 0) * 2,
                });
            }
        }

        this.nodes.clear();
        this.edges.clear();
        this.nodes.add(nodes);
        this.edges.add(edges);
        this.network.setData({ nodes: this.nodes, edges: this.edges });
        this.network.fit({ animation: false });
    }

    private getStageTransitionItems(stage: QuestStage): StageTransitionItem[] {
        const transitions: StageTransitionItem[] = [];
        for (const step of stage.plan ?? []) {
            const targets = Array.from(
                new Set(
                    (step.actions ?? [])
                        .filter(
                            (action) =>
                                action.action === "advance_stage" &&
                                !!action.target_stage_id,
                        )
                        .map((action) => action.target_stage_id as string),
                ),
            );
            if (!targets.length) {
                continue;
            }
            transitions.push({
                conditionLabel: this.getCombinedConditionLabel(step),
                targets,
            });
        }
        return transitions;
    }

    private getStageCardLabel(stage: QuestStage): string {
        const lines = [stage.description || stage.id];
        const transitions = this.getStageTransitionItems(stage);
        if (!transitions.length) {
            return lines.join("\n");
        }
        lines.push("", "Conditions:");
        transitions.forEach((transition, index) => {
            lines.push(`${index + 1}. ${transition.conditionLabel}`);
        });
        return lines.join("\n");
    }

    private getConditionNodeId(stageId: string, transitionIndex: number): string {
        return `condition::${stageId}::${transitionIndex}`;
    }

    private resolveSelectedStageFromNodeId(nodeId: string): string | null {
        if (nodeId.startsWith("condition::")) {
            const parts = nodeId.split("::");
            return parts[1] || null;
        }
        return nodeId || null;
    }

    private getCombinedConditionLabel(step: QuestPlanStep): string {
        const conditions = step.conditions ?? [];
        if (!conditions.length) {
            return "Always";
        }
        return conditions
            .map((condition) => this.formatCondition(condition))
            .join(" AND ");
    }

    private formatCondition(condition: QuestCondition): string {
        const path = condition.path || "(value)";
        const operator = condition.operator || "equals";
        const value = this.formatConditionValue(condition.value);
        if (value) {
            return `${path} ${operator} ${value}`;
        }
        return `${path} ${operator}`;
    }

    private formatConditionValue(value: unknown): string {
        if (value === null) {
            return "null";
        }
        if (value === undefined) {
            return "";
        }
        if (typeof value === "string") {
            return value;
        }
        return JSON.stringify(value);
    }

    closeEditor(): void {
        this.closeRequested.emit();
    }
}
