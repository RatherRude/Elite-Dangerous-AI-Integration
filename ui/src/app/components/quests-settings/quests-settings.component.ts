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
import { MatDialog } from "@angular/material/dialog";
import { MatSnackBarModule } from "@angular/material/snack-bar";
import { MatSnackBar } from "@angular/material/snack-bar";
import { fromEvent, Subscription } from "rxjs";
import { DataSet } from "vis-data";
import { Network } from "vis-network";
import type { Edge, Node } from "vis-network";
import {
    QuestActor,
    QuestAction,
    QuestCatalog,
    QuestAudioImportResult,
    QuestCondition,
    QuestDefinition,
    QuestFallbackStage,
    QuestPlanStep,
    QuestStage,
    QuestsService,
} from "../../services/quests.service";
import {
    AvatarCatalogDialogComponent,
    AvatarCatalogResult,
} from "../avatar-catalog-dialog/avatar-catalog-dialog.component";
import { AvatarService } from "../../services/avatar.service";

type ConditionValueKind = "string" | "number" | "boolean" | "null";
const FALLBACK_STAGE_NODE_ID = "__fallback__";

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
    selectedActorId: string | null = null;
    loadError: string | null = null;
    catalogPath: string | null = null;
    loadPending = false;
    lastLoadedAt: string | null = null;
    selectedStageId: string | null = null;
    private network: Network | null = null;
    private networkContainer: HTMLDivElement | null = null;
    private nodes = new DataSet<Node>();
    private edges = new DataSet<Edge>();
    private subscriptions: Subscription[] = [];
    private layoutPending = false;
    private stageGraphSubscriptions: Subscription[] = [];
    private collapsedStageKeys = new Set<string>();
    private collapseInitialized = false;
    private actorAvatarPreviewUrls = new Map<QuestActor, string>();
    questsListExpanded = true;
    actorsListExpanded = true;
    readonly defaultActorNameColor = "#2196F3";

    @ViewChild("stageNetwork") stageNetworkRef?: ElementRef<HTMLDivElement>;

    constructor(
        private questsService: QuestsService,
        private ngZone: NgZone,
        private dialog: MatDialog,
        private snackBar: MatSnackBar,
        private avatarService: AvatarService,
    ) {}

    ngOnInit(): void {
        this.subscriptions.push(
            this.questsService.catalog$.subscribe((catalog) => {
                for (const quest of catalog?.quests ?? []) {
                    this.ensureFallbackStage(quest);
                    this.ensureInitialStageId(quest);
                }
                this.catalog = catalog;
                this.normalizeActorNameColors(catalog?.actors ?? []);
                void this.syncActorAvatarPreviews(catalog?.actors ?? []);
                if (
                    this.selectedQuestId &&
                    !catalog?.quests.some((quest) => quest.id === this.selectedQuestId)
                ) {
                    this.selectedQuestId = null;
                    this.selectedStageId = null;
                }
                if (
                    this.selectedActorId &&
                    !catalog?.actors?.some((actor) => actor.id === this.selectedActorId)
                ) {
                    this.selectedActorId = null;
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
        this.actorAvatarPreviewUrls.forEach((url) => URL.revokeObjectURL(url));
        this.actorAvatarPreviewUrls.clear();
        if (this.network) {
            this.network.destroy();
            this.network = null;
        }
        this.networkContainer = null;
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
        if (!quest || !this.selectedStageId || this.selectedStageId === FALLBACK_STAGE_NODE_ID) {
            return null;
        }
        return quest.stages.find((stage) => stage.id === this.selectedStageId) || null;
    }

    get selectedFallbackStage(): QuestFallbackStage | null {
        const quest = this.selectedQuest;
        if (!quest || this.selectedStageId !== FALLBACK_STAGE_NODE_ID) {
            return null;
        }
        return this.ensureFallbackStage(quest);
    }

    get selectedStageEditor(): QuestStage | QuestFallbackStage | null {
        return this.selectedStage || this.selectedFallbackStage;
    }

    get isFallbackSelected(): boolean {
        return this.selectedStageId === FALLBACK_STAGE_NODE_ID;
    }

    get selectedActor(): QuestActor | null {
        if (!this.catalog || !this.selectedActorId) {
            return null;
        }
        return this.catalog.actors?.find((actor) => actor.id === this.selectedActorId) || null;
    }

    selectQuest(questId: string): void {
        this.selectedQuestId = questId;
        this.selectedActorId = null;
        this.selectedStageId = null;
        this.scheduleLayout();
    }

    selectActor(actorId: string): void {
        this.selectedActorId = actorId;
        this.selectedQuestId = null;
        this.selectedStageId = null;
        this.scheduleLayout();
    }

    onActorIdChange(nextActorId: string): void {
        const previousId = this.selectedActorId;
        if (previousId && previousId !== nextActorId) {
            this.replaceActorReferences(previousId, nextActorId);
        }
        this.selectedActorId = nextActorId;
    }

    onQuestIdChange(quest: QuestDefinition): void {
        if (this.selectedQuest === quest) {
            this.selectedQuestId = quest.id;
        }
    }

    onStageIdChange(stage: QuestStage): void {
        const quest = this.selectedQuest;
        if (quest && quest.initial_stage_id && !quest.stages.some((candidate) => candidate.id === quest.initial_stage_id)) {
            quest.initial_stage_id = stage.id;
        }
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

    resetQuestProgress(): void {
        this.questsService.resetQuestProgress();
        this.snackBar.open(
            "Quest progress reset. Restart AI to repopulate from YAML.",
            "Dismiss",
            { duration: 3000 },
        );
    }

    addQuest(): void {
        if (!this.catalog) {
            this.catalog = { version: "1.0", actors: [], quests: [] };
        }
        const newQuest = this.createQuest();
        this.ensureFallbackStage(newQuest);
        this.catalog.quests = [...this.catalog.quests, newQuest];
        this.selectedQuestId = newQuest.id;
        this.selectedActorId = null;
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

    addActor(): void {
        if (!this.catalog) {
            this.catalog = { version: "1.0", actors: [], quests: [] };
        }
        if (!this.catalog.actors) {
            this.catalog.actors = [];
        }
        const actor = this.createActor();
        this.catalog.actors = [...this.catalog.actors, actor];
        this.selectedActorId = actor.id;
        this.selectedQuestId = null;
        this.selectedStageId = null;
    }

    removeActor(index: number): void {
        if (!this.catalog?.actors?.[index]) {
            return;
        }
        const removedActor = this.catalog.actors[index];
        const previousUrl = this.actorAvatarPreviewUrls.get(removedActor);
        if (previousUrl) {
            URL.revokeObjectURL(previousUrl);
            this.actorAvatarPreviewUrls.delete(removedActor);
        }
        this.catalog.actors.splice(index, 1);
        if (removedActor.id === this.selectedActorId) {
            this.selectedActorId = this.catalog.actors[0]?.id ?? null;
        }
    }

    addStage(quest: QuestDefinition): void {
        const newStage = this.createStage(quest);
        quest.stages = [...quest.stages, newStage];
        this.ensureInitialStageId(quest);
        const collapseKey = this.getStageCollapseKey(quest.id, newStage.id);
        if (collapseKey) {
            this.collapsedStageKeys.add(collapseKey);
        }
        this.scheduleLayout();
    }

    removeStage(quest: QuestDefinition, index: number): void {
        const removedStageId = quest.stages[index]?.id;
        quest.stages.splice(index, 1);
        this.ensureInitialStageId(quest);
        const collapseKey = this.getStageCollapseKey(quest.id, removedStageId);
        if (collapseKey) {
            this.collapsedStageKeys.delete(collapseKey);
        }
        if (removedStageId && removedStageId === this.selectedStageId) {
            this.selectedStageId = null;
        }
        this.scheduleLayout();
    }

    addPlanStep(stage: QuestStage | QuestFallbackStage): void {
        if (!stage.plan) {
            stage.plan = [];
        }
        stage.plan.push(this.createPlanStep());
        this.scheduleLayout();
    }

    removePlanStep(stage: QuestStage | QuestFallbackStage, index: number): void {
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

    async selectPlaySoundFile(action: QuestAction): Promise<void> {
        try {
            const result: QuestAudioImportResult =
                await this.questsService.importQuestAudioFile(this.catalogPath);
            if (result.canceled) {
                return;
            }
            if (!result.fileName) {
                throw new Error("No file name returned by picker.");
            }
            action.file_name = result.fileName;
            // Drop legacy URL value so saves are filename-based.
            delete action.url;
            const status = result.reused
                ? "Reused existing audio file"
                : "Imported audio file";
            this.snackBar.open(`${status}: ${result.fileName}`, "Dismiss", {
                duration: 2500,
            });
        } catch (error) {
            const message =
                error instanceof Error
                    ? error.message
                    : "Failed to import quest audio file";
            this.snackBar.open(message, "Dismiss", {
                duration: 3000,
            });
            console.error("Error importing quest audio file:", error);
        }
    }

    createQuest(): QuestDefinition {
        const questIndex = this.catalog?.quests.length ?? 0;
        const initialStage = this.createStage();
        return {
            id: `new_quest_${questIndex + 1}`,
            title: "New Quest",
            description: "Describe the quest objective.",
            active: false,
            initial_stage_id: initialStage.id,
            stages: [initialStage],
            fallback_stage: this.createFallbackStage(),
        };
    }

    createActor(): QuestActor {
        const actorIndex = this.catalog?.actors?.length ?? 0;
        return {
            id: `actor_${actorIndex + 1}`,
            name: "New Actor",
            name_color: this.defaultActorNameColor,
            voice: "en-US-AvaMultilingualNeural",
            avatar_url: "",
            prompt: "",
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

    createFallbackStage(): QuestFallbackStage {
        return {
            description: "Fallback",
            instructions: "Always evaluated and cannot become active.",
            plan: [],
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

    getAdvanceTargetStageOptions(quest: QuestDefinition): QuestStage[] {
        return quest.stages;
    }

    isQuestStartStage(quest: QuestDefinition, stage: QuestStage): boolean {
        return quest.initial_stage_id === stage.id;
    }

    setQuestStartStage(quest: QuestDefinition, stage: QuestStage): void {
        quest.initial_stage_id = stage.id;
        this.scheduleLayout();
    }

    getAdvanceStageTargets(stage: QuestStage | QuestFallbackStage): string[] {
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

    getAdvanceStageLinks(stage: QuestStage | QuestFallbackStage): { targetId: string; label: string }[] {
        const links: { targetId: string; label: string }[] = [];
        for (const step of stage.plan ?? []) {
            const label = this.getAdvanceStageLabel(step);
            for (const action of step.actions ?? []) {
                if (action.action === "advance_stage" && action.target_stage_id) {
                    links.push({
                        targetId: action.target_stage_id,
                        label,
                    });
                }
            }
        }
        return links;
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
        const startStage = this.getQuestStartStage(quest);
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

    private replaceActorReferences(previousId: string, nextId: string): void {
        if (!this.catalog) {
            return;
        }
        for (const quest of this.catalog.quests) {
            for (const stage of quest.stages) {
                for (const step of stage.plan ?? []) {
                    for (const action of step.actions ?? []) {
                        if (action.actor_id === previousId) {
                            action.actor_id = nextId;
                        }
                    }
                }
            }
        }
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
        const container = this.stageNetworkRef?.nativeElement;
        if (!container) {
            if (this.network) {
                this.network.destroy();
                this.network = null;
            }
            this.networkContainer = null;
            return;
        }
        if (this.network && this.networkContainer !== container) {
            this.network.destroy();
            this.network = null;
        }
        if (this.network) {
            return;
        }
        this.networkContainer = container;
        this.network = new Network(
            container,
            { nodes: this.nodes, edges: this.edges },
            {
                layout: {
                    hierarchical: {
                        direction: "UD",
                        sortMethod: "directed",
                        levelSeparation: 160,
                        nodeSpacing: 220,
                        treeSpacing: 260,
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
                        highlight: {
                            background: "#ffa724",
                            border: "#ffa724",
                        },
                        hover: {
                            background: "#ffa724",
                            border: "#ffa724",
                        },
                    },
                    font: { color: "#f0f0f0", size: 12 },
                    chosen: {
                        node: (
                            _values: any,
                            _id: string | number,
                            _selected: boolean,
                            _hovering: boolean,
                        ) => {
                            _values.color = "#ffa724";
                            _values.borderColor = "#ffa724";
                        },
                        label: (
                            values: { color?: string },
                            _id: string | number,
                            _selected: boolean,
                            _hovering: boolean,
                        ) => {
                            values.color = "#000000";
                        },
                    },
                    widthConstraint: { maximum: 220 },
                },
                edges: {
                    arrows: { to: { enabled: true, scaleFactor: 0.7 } },
                    color: { color: "rgba(126, 224, 129, 0.7)" },
                    smooth: {
                        enabled: true,
                        type: "cubicBezier",
                        forceDirection: "vertical",
                        roundness: 0.3,
                    },
                    font: {
                        color: "rgba(126, 224, 129, 0.9)",
                        size: 11,
                        strokeWidth: 3,
                        strokeColor: "rgba(20, 35, 24, 0.8)",
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
                this.selectedStageId = nodeId ? String(nodeId) : null;
            });
            },
        );
    }

    private refreshNetwork(): void {
        const quest = this.selectedQuest;
        if (!quest) {
            this.nodes.clear();
            this.edges.clear();
            if (this.network) {
                this.network.setData({ nodes: this.nodes, edges: this.edges });
            }
            return;
        }
        if (!this.network) {
            return;
        }

        const fallbackStage = this.ensureFallbackStage(quest);
        const regularStageCount = quest.stages.length;
        const fallbackColumnX = Math.max(regularStageCount, 1) * 280;
        const nodes: Node[] = [
            ...quest.stages.map((stage) => ({
                id: stage.id,
                label: stage.description || stage.id,
            })),
            {
                id: FALLBACK_STAGE_NODE_ID,
                label: `${fallbackStage.description || "Fallback"}\n(Fallback)`,
                x: fallbackColumnX,
                fixed: { x: true, y: false },
            },
        ];
        const edges: Edge[] = [];

        let edgeIndex = 0;
        for (const stage of quest.stages) {
            for (const link of this.getAdvanceStageLinks(stage)) {
                if (!this.getStageById(quest, link.targetId)) {
                    continue;
                }
                const loopback = this.isLoopback(quest, stage.id, link.targetId);
                const edgeColor = loopback
                    ? "rgba(120, 170, 255, 0.85)"
                    : "rgba(126, 224, 129, 0.7)";
                edges.push({
                    id: `edge-${edgeIndex += 1}`,
                    from: stage.id,
                    to: link.targetId,
                    label: link.label || undefined,
                    arrows: { to: { enabled: true, scaleFactor: 0.7 } },
                    color: {
                        color: edgeColor,
                    },
                    font: {
                        color: loopback
                            ? "rgba(170, 200, 255, 0.95)"
                            : "rgba(126, 224, 129, 0.9)",
                        size: 11,
                        strokeWidth: 3,
                        strokeColor: "rgba(20, 35, 24, 0.8)",
                    },
                    smooth: loopback
                        ? { enabled: true, type: "curvedCW", roundness: 0.35 }
                        : { enabled: true, type: "cubicBezier", roundness: 0.2 },
                });
            }
        }
        for (const link of this.getAdvanceStageLinks(fallbackStage)) {
            if (!this.getStageById(quest, link.targetId)) {
                continue;
            }
            edges.push({
                id: `edge-${edgeIndex += 1}`,
                from: FALLBACK_STAGE_NODE_ID,
                to: link.targetId,
                label: link.label || undefined,
                arrows: { to: { enabled: true, scaleFactor: 0.7 } },
                color: {
                    color: "rgba(255, 180, 90, 0.8)",
                },
                font: {
                    color: "rgba(255, 210, 150, 0.95)",
                    size: 11,
                    strokeWidth: 3,
                    strokeColor: "rgba(35, 22, 8, 0.8)",
                },
                smooth: { enabled: true, type: "cubicBezier", roundness: 0.2 },
            });
        }

        this.nodes.clear();
        this.edges.clear();
        this.nodes.add(nodes);
        this.edges.add(edges);
        this.network.setData({ nodes: this.nodes, edges: this.edges });
        this.network.fit({ animation: false });
    }

    private getAdvanceStageLabel(step: QuestPlanStep): string {
        const conditions = step.conditions ?? [];
        if (!conditions.length) {
            return "";
        }
        return conditions
            .map((condition) => this.formatConditionValue(condition.value))
            .join(" & ");
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

    private ensureFallbackStage(quest: QuestDefinition): QuestFallbackStage {
        if (!quest.fallback_stage || typeof quest.fallback_stage !== "object") {
            quest.fallback_stage = this.createFallbackStage();
            return quest.fallback_stage;
        }
        if (!Array.isArray(quest.fallback_stage.plan)) {
            quest.fallback_stage.plan = [];
        }
        return quest.fallback_stage;
    }

    private getQuestStartStage(quest: QuestDefinition): QuestStage | null {
        const initialStageId = quest.initial_stage_id;
        if (initialStageId) {
            const selected = quest.stages.find((stage) => stage.id === initialStageId) || null;
            if (selected) {
                return selected;
            }
        }
        return quest.stages[0] || null;
    }

    private ensureInitialStageId(quest: QuestDefinition): void {
        if (quest.initial_stage_id && quest.stages.some((stage) => stage.id === quest.initial_stage_id)) {
            return;
        }
        quest.initial_stage_id = quest.stages[0]?.id;
    }

    closeEditor(): void {
        this.closeRequested.emit();
    }

    openActorAvatarCatalog(actor: QuestActor): void {
        const dialogRef = this.dialog.open(AvatarCatalogDialogComponent, {
            width: "850px",
            maxWidth: "95vw",
            data: { currentAvatarId: this.extractAvatarCatalogId(actor.avatar_url) },
        });
        dialogRef.afterClosed().subscribe((result: AvatarCatalogResult | undefined) => {
            if (!result) {
                return;
            }
            actor.avatar_url = result.avatarId ? `avatar://${result.avatarId}` : "";
            void this.updateActorAvatarPreview(actor);
        });
    }

    getActorAvatarPreviewUrl(actor: QuestActor): string {
        if (!actor.avatar_url) {
            return "";
        }
        const avatarId = this.extractAvatarCatalogId(actor.avatar_url);
        if (!avatarId) {
            return actor.avatar_url;
        }
        return this.actorAvatarPreviewUrls.get(actor) ?? "";
    }

    private extractAvatarCatalogId(avatarUrl: string | null | undefined): string | null {
        if (!avatarUrl) {
            return null;
        }
        if (!avatarUrl.startsWith("avatar://")) {
            return null;
        }
        return avatarUrl.slice("avatar://".length) || null;
    }

    private async syncActorAvatarPreviews(actors: QuestActor[]): Promise<void> {
        const actorSet = new Set(actors);
        for (const [actor, existingUrl] of this.actorAvatarPreviewUrls.entries()) {
            if (!actorSet.has(actor)) {
                URL.revokeObjectURL(existingUrl);
                this.actorAvatarPreviewUrls.delete(actor);
            }
        }
        await Promise.all(actors.map((actor) => this.updateActorAvatarPreview(actor)));
    }

    private normalizeActorNameColors(actors: QuestActor[]): void {
        for (const actor of actors) {
            if (
                !actor.name_color ||
                !/^#[0-9a-fA-F]{6}$/.test(actor.name_color)
            ) {
                actor.name_color = this.defaultActorNameColor;
            }
        }
    }

    private async updateActorAvatarPreview(actor: QuestActor): Promise<void> {
        const existingUrl = this.actorAvatarPreviewUrls.get(actor);
        const avatarId = this.extractAvatarCatalogId(actor.avatar_url);
        if (!avatarId) {
            if (existingUrl) {
                URL.revokeObjectURL(existingUrl);
                this.actorAvatarPreviewUrls.delete(actor);
            }
            return;
        }
        try {
            const avatarUrl = await this.avatarService.getAvatar(avatarId);
            if (!avatarUrl) {
                if (existingUrl) {
                    URL.revokeObjectURL(existingUrl);
                    this.actorAvatarPreviewUrls.delete(actor);
                }
                return;
            }
            if (existingUrl && existingUrl !== avatarUrl) {
                URL.revokeObjectURL(existingUrl);
            }
            this.actorAvatarPreviewUrls.set(actor, avatarUrl);
        } catch (error) {
            if (existingUrl) {
                URL.revokeObjectURL(existingUrl);
                this.actorAvatarPreviewUrls.delete(actor);
            }
            this.snackBar.open("Failed to load actor avatar", "Dismiss", {
                duration: 3000,
            });
            console.error("Error loading actor avatar:", error);
        }
    }
}
