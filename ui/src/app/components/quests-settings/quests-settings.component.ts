import {
    AfterViewInit,
    AfterViewChecked,
    Component,
    ElementRef,
    OnDestroy,
    OnInit,
    QueryList,
    ViewChild,
    ViewChildren,
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
export class QuestsSettingsComponent
    implements OnInit, OnDestroy, AfterViewInit, AfterViewChecked
{
    catalog: QuestCatalog | null = null;
    rawYaml = "";
    selectedQuestId: string | null = null;
    loadError: string | null = null;
    catalogPath: string | null = null;
    loadPending = false;
    lastLoadedAt: string | null = null;
    connectionLines: { x1: number; y1: number; x2: number; y2: number }[] = [];
    stageGraphSize = { width: 0, height: 0 };
    private subscriptions: Subscription[] = [];
    private layoutPending = false;
    private stageGraphSubscriptions: Subscription[] = [];
    private collapsedStageKeys = new Set<string>();
    private collapseInitialized = false;

    @ViewChild("stageGraph") stageGraphRef?: ElementRef<HTMLElement>;
    @ViewChildren("stageCard") stageCardRefs?: QueryList<
        ElementRef<HTMLElement>
    >;

    constructor(private questsService: QuestsService) {}

    ngOnInit(): void {
        this.subscriptions.push(
            this.questsService.catalog$.subscribe((catalog) => {
                this.catalog = catalog;
                if (catalog && !this.selectedQuestId && catalog.quests.length) {
                    this.selectedQuestId = catalog.quests[0].id;
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

        this.questsService.loadCatalog();
    }

    ngAfterViewInit(): void {
        if (this.stageCardRefs) {
            this.stageGraphSubscriptions.push(
                this.stageCardRefs.changes.subscribe(() =>
                    this.scheduleLayout(),
                ),
            );
        }
        this.bindStageGraphListeners();
        this.scheduleLayout();
    }

    ngAfterViewChecked(): void {
        if (this.layoutPending) {
            this.updateStageLinks();
        }
    }

    ngOnDestroy(): void {
        this.subscriptions.forEach((subscription) => subscription.unsubscribe());
        this.stageGraphSubscriptions.forEach((subscription) =>
            subscription.unsubscribe(),
        );
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

    selectQuest(questId: string): void {
        this.selectedQuestId = questId;
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
        const stageGraph = this.stageGraphRef?.nativeElement;
        if (!stageGraph) {
            return;
        }
        this.stageGraphSubscriptions.push(
            fromEvent(stageGraph, "scroll").subscribe(() =>
                this.scheduleLayout(),
            ),
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
            this.updateStageLinks();
        });
    }

    private updateStageLinks(): void {
        const stageGraph = this.stageGraphRef?.nativeElement;
        const stageCards = this.stageCardRefs?.toArray() ?? [];
        const quest = this.selectedQuest;
        if (!stageGraph || !quest || !stageCards.length) {
            this.connectionLines = [];
            return;
        }

        const containerRect = stageGraph.getBoundingClientRect();
        const stageRects = new Map<string, DOMRect>();
        stageCards.forEach((cardRef) => {
            const stageId = cardRef.nativeElement.dataset["stageId"];
            if (stageId) {
                stageRects.set(stageId, cardRef.nativeElement.getBoundingClientRect());
            }
        });

        this.stageGraphSize = {
            width: stageGraph.scrollWidth,
            height: stageGraph.scrollHeight,
        };

        const lines: { x1: number; y1: number; x2: number; y2: number }[] = [];
        for (const stage of quest.stages) {
            const fromRect = stageRects.get(stage.id);
            if (!fromRect) {
                continue;
            }
            const fromX = fromRect.left - containerRect.left + fromRect.width / 2;
            const fromY = fromRect.bottom - containerRect.top;
            for (const targetId of this.getAdvanceStageTargets(stage)) {
                const toRect = stageRects.get(targetId);
                if (!toRect) {
                    continue;
                }
                const toX = toRect.left - containerRect.left + toRect.width / 2;
                const toY = toRect.top - containerRect.top;
                lines.push({ x1: fromX, y1: fromY, x2: toX, y2: toY });
            }
        }
        this.connectionLines = lines;
    }
}
