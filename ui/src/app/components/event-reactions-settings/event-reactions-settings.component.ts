import { Component, OnDestroy } from "@angular/core";
import { CommonModule, KeyValue } from "@angular/common";
import { FormsModule } from "@angular/forms";
import {
    MatFormField,
    MatFormFieldModule,
    MatHint,
    MatLabel,
} from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatIcon } from "@angular/material/icon";
import { MatSlideToggle } from "@angular/material/slide-toggle";
import { MatSelect, MatOption } from "@angular/material/select";
import {
    MatAccordion,
    MatExpansionPanel,
    MatExpansionPanelHeader,
    MatExpansionPanelTitle,
    MatExpansionPanelDescription,
} from "@angular/material/expansion";
import { MatTooltipModule } from "@angular/material/tooltip";
import { MatButtonModule } from "@angular/material/button";
import { MatButtonToggleModule } from "@angular/material/button-toggle";
import { Subscription } from "rxjs";
import {
    Character,
    CharacterService,
    EventReactionState,
} from "../../services/character.service";
import {
    Config,
    ConfigService,
} from "../../services/config.service.js";
import { MatSnackBar } from "@angular/material/snack-bar";
import { ConfirmationDialogService } from "../../services/confirmation-dialog.service.js";
import { GameEventTooltips } from "../character-settings/game-event-tooltips.js";
import { GameEventCategories } from "../character-settings/game-event-categories.js";

@Component({
    selector: "app-event-reactions-settings",
    standalone: true,
    imports: [
        CommonModule,
        FormsModule,
        MatFormFieldModule,
        MatFormField,
        MatLabel,
        MatHint,
        MatInputModule,
        MatIcon,
        MatSlideToggle,
        MatSelect,
        MatOption,
        MatAccordion,
        MatExpansionPanel,
        MatExpansionPanelHeader,
        MatExpansionPanelTitle,
        MatExpansionPanelDescription,
        MatTooltipModule,
        MatButtonModule,
        MatButtonToggleModule,
    ],
    templateUrl: "./event-reactions-settings.component.html",
    styleUrl: "./event-reactions-settings.component.scss",
})
export class EventReactionsSettingsComponent implements OnDestroy {
    activeCharacter: Character | null = null;
    activeCharacterIndex: number | null = null;
    characterList: Character[] = [];
    filteredEventReactions: Record<string, Record<string, EventReactionState>> = {};
    eventSearchQuery: string = "";
    expandedSection: string | null = null;
    public GameEventTooltips = GameEventTooltips;
    gameEventCategories = GameEventCategories;
    showImportSelector = false;
    selectedImportIndex: number | null = null;

    private configSubscription?: Subscription;
    private characterSubscription?: Subscription;
    private characterListSubscription?: Subscription;

    constructor(
        private configService: ConfigService,
        private characterService: CharacterService,
        private snackBar: MatSnackBar,
        private confirmationDialog: ConfirmationDialogService,
    ) {
        this.configSubscription = this.configService.config$
            .subscribe((config: Config | null) => {
                this.activeCharacterIndex =
                    config?.active_character_index ?? null;
                this.filterEvents(this.eventSearchQuery);
            });

        this.characterSubscription = this.characterService.character$
            .subscribe((character) => {
                this.activeCharacter = character;
                this.filterEvents(this.eventSearchQuery);
            });

        this.characterListSubscription = this.characterService.characterList$
            .subscribe((list) => {
                this.characterList = list || [];
            });
    }

    ngOnDestroy(): void {
        if (this.configSubscription) {
            this.configSubscription.unsubscribe();
        }
        if (this.characterSubscription) {
            this.characterSubscription.unsubscribe();
        }
        if (this.characterListSubscription) {
            this.characterListSubscription.unsubscribe();
        }
    }

    orderByKey = (
        a: KeyValue<string, any>,
        b: KeyValue<string, any>,
    ): number => a.key.localeCompare(b.key);

    onSectionToggled(sectionName: string | null) {
        this.expandedSection = sectionName;
    }

    isSectionExpanded(sectionName: string): boolean {
        return this.expandedSection === sectionName;
    }

    async onEventConfigChange(
        section: string,
        event: string,
        state: "on" | "off" | "hidden",
    ) {
        if (!this.activeCharacter) return;

        await this.characterService.setCharacterEventProperty(
            event,
            state,
        );
    }

    async resetGameEvents() {
        if (this.activeCharacterIndex === null) return;

        const dialogRef = this.confirmationDialog.openConfirmationDialog({
            title: "Reset Game Events",
            message:
                "This will reset all game event settings to their default values. Are you sure you want to continue?",
            confirmButtonText: "Reset",
            cancelButtonText: "Cancel",
        });

        dialogRef.subscribe(async (result: boolean) => {
            if (result) {
                await this.characterService.resetGameEvents(
                    this.activeCharacterIndex!,
                );
                this.snackBar.open("Game events reset to defaults", "OK", {
                    duration: 3000,
                });
            }
        });
    }

    getMaterialsArray(materials: string | undefined): string[] {
        if (!materials) return [];
        return materials.split(",").map((m) => m.trim()).filter((m) =>
            m.length > 0
        );
    }

    async onMaterialsChange(selectedMaterials: string[]) {
        const materialsString = selectedMaterials.join(", ");
        await this.setCharacterProperty("react_to_material", materialsString);
    }

    async setCharacterProperty<T extends keyof Character>(
        propName: T,
        value: Character[T],
    ): Promise<void> {
        await this.characterService.setCharacterProperty(propName, value);
    }

    private categorizeEvents(
        events: Record<string, EventReactionState>,
    ): Record<string, Record<string, EventReactionState>> {
        const categorizedEvents: Record<string, Record<string, EventReactionState>> = {};

        for (
            const [category, list] of Object.entries(this.gameEventCategories)
        ) {
            categorizedEvents[category] = {};
            for (const event of list) {
                const state = (events[event] || "off") as EventReactionState;
                categorizedEvents[category][event] = state;
            }
        }
        return categorizedEvents;
    }

    filterEvents(query: string) {
        if (!this.activeCharacter) {
            this.filteredEventReactions = {};
            return;
        }

        const eventReactions = this.getCharacterProperty("event_reactions", {} as Record<string, EventReactionState>);

        if (!query && this.eventSearchQuery) {
            this.eventSearchQuery = "";
            this.filteredEventReactions = this.categorizeEvents(eventReactions);
            this.expandedSection = null;
            return;
        }
        this.eventSearchQuery = query;

        if (query.length >= 3) {
            this.filteredEventReactions = {};
            const all_reactions = this.categorizeEvents(eventReactions);
            const searchTerm = query.toLowerCase();

            for (
                const [sectionKey, events] of Object.entries(all_reactions)
            ) {
                const matchingEvents: Record<string, EventReactionState> = {};
                for (const [eventKey, value] of Object.entries(events)) {
                    if (
                        eventKey.toLowerCase().includes(searchTerm) ||
                        sectionKey.toLowerCase().includes(searchTerm)
                    ) {
                        matchingEvents[eventKey] = value;
                    }
                }
                if (Object.keys(matchingEvents).length > 0) {
                    this.filteredEventReactions[sectionKey] = matchingEvents;
                }
            }
        } else {
            this.filteredEventReactions = this.categorizeEvents(eventReactions);
        }
    }

    clearEventSearch() {
        const eventReactions = this.getCharacterProperty("event_reactions", {});
        this.eventSearchQuery = "";
        this.filteredEventReactions = this.categorizeEvents(eventReactions);
        this.expandedSection = null;
    }

    getCharacterProperty<T extends keyof Character>(
        propName: T,
        defaultValue: Character[T],
    ): Character[T] {
        if (!this.activeCharacter) return defaultValue;
        return this.activeCharacter[propName] ?? defaultValue;
    }

    async setCategoryState(categoryName: string, state: EventReactionState) {
        if (!this.activeCharacter) return;

        const currentEventReactions = { ...(this.activeCharacter.event_reactions || {}) };
        const eventsInCategory = this.gameEventCategories[categoryName] || [];

        for (const eventName of eventsInCategory) {
            currentEventReactions[eventName] = state;
        }

        await this.characterService.setCharacterProperty(
            "event_reactions",
            currentEventReactions,
        );
    }

    getEventState(eventName: string): "on" | "off" | "hidden" {
        if (!this.activeCharacter) return "off";
        return this.activeCharacter.event_reactions?.[eventName] ?? "off";
    }

    getEventIcon(state: "on" | "off" | "hidden"): string {
        switch (state) {
            case "on":
                return "volume_up";
            case "hidden":
                return "close";
            case "off":
            default:
                return "visibility";
        }
    }

    getCategoryCounts(categoryKey: string): { on: number; off: number; hidden: number } {
        const section = this.filteredEventReactions[categoryKey];
        const initial = { on: 0, off: 0, hidden: 0 };
        if (!section) return initial;

        return Object.values(section).reduce((acc, state) => {
            if (state === "on") acc.on += 1;
            else if (state === "hidden") acc.hidden += 1;
            else acc.off += 1;
            return acc;
        }, initial);
    }

    getCategoryAggregateState(categoryKey: string): EventReactionState | null {
        const counts = this.getCategoryCounts(categoryKey);
        const total = counts.on + counts.off + counts.hidden;
        if (total === 0) return null;
        if (counts.on === total) return "on";
        if (counts.off === total) return "off";
        if (counts.hidden === total) return "hidden";
        return null;
    }

    getImportCandidates(): Array<{ index: number; name: string }> {
        const candidates: Array<{ index: number; name: string }> = [];
        this.characterList.forEach((c, idx) => {
            if (idx !== this.activeCharacterIndex) {
                candidates.push({ index: idx, name: c.name || `Character ${idx + 1}` });
            }
        });
        return candidates;
    }

    startImportSelection() {
        this.showImportSelector = true;
        this.selectedImportIndex = null;
    }

    cancelImportSelection() {
        this.showImportSelector = false;
        this.selectedImportIndex = null;
    }

    async performImportFromCharacter() {
        if (this.selectedImportIndex === null) return;
        const source = this.characterList[this.selectedImportIndex];
        if (!source || !source.event_reactions) return;

        await this.characterService.setCharacterProperty(
            "event_reactions",
            { ...source.event_reactions },
        );

        this.snackBar.open("Event reactions imported from selected character", "OK", {
            duration: 3000,
        });

        this.cancelImportSelection();
    }
}
