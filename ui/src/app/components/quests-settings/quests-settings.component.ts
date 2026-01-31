import { Component, OnDestroy, OnInit } from "@angular/core";
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
import { Subscription } from "rxjs";
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
export class QuestsSettingsComponent implements OnInit, OnDestroy {
    catalog: QuestCatalog | null = null;
    rawYaml = "";
    selectedQuestId: string | null = null;
    loadError: string | null = null;
    catalogPath: string | null = null;
    private subscriptions: Subscription[] = [];

    constructor(private questsService: QuestsService) {}

    ngOnInit(): void {
        this.subscriptions.push(
            this.questsService.catalog$.subscribe((catalog) => {
                this.catalog = catalog;
                if (catalog && !this.selectedQuestId && catalog.quests.length) {
                    this.selectedQuestId = catalog.quests[0].id;
                }
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
            this.questsService.saveResult$.subscribe((result) => {
                this.loadError = result.success
                    ? null
                    : result.message || "Failed to save quest catalog";
            }),
        );

        this.questsService.loadCatalog();
    }

    ngOnDestroy(): void {
        this.subscriptions.forEach((subscription) => subscription.unsubscribe());
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
    }

    addStage(quest: QuestDefinition): void {
        quest.stages = [...quest.stages, this.createStage(quest)];
    }

    removeStage(quest: QuestDefinition, index: number): void {
        quest.stages.splice(index, 1);
    }

    addPlanStep(stage: QuestStage): void {
        if (!stage.plan) {
            stage.plan = [];
        }
        stage.plan.push(this.createPlanStep());
    }

    removePlanStep(stage: QuestStage, index: number): void {
        stage.plan?.splice(index, 1);
    }

    addCondition(step: QuestPlanStep): void {
        step.conditions.push(this.createCondition());
    }

    removeCondition(step: QuestPlanStep, index: number): void {
        step.conditions.splice(index, 1);
    }

    addAction(step: QuestPlanStep): void {
        step.actions.push(this.createAction());
    }

    removeAction(step: QuestPlanStep, index: number): void {
        step.actions.splice(index, 1);
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
}
