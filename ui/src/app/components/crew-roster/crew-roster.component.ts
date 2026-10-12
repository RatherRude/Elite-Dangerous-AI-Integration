import { Component, EventEmitter, Input, OnChanges, OnDestroy, Output } from "@angular/core";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatSnackBar } from "@angular/material/snack-bar";
import { AvatarService } from "../../services/avatar.service";
import { Character, CharacterService, ConfigWithCharacters, PluginCharacter } from "../../services/character.service";
import { ConfigService } from "../../services/config.service";
import { Subscription } from "rxjs";
import { ModelProviderDefinition, providerVoiceDisplayValue } from "../../services/plugin-settings";

interface RosterEntry {
    index: number;
    character: Character;
    plugin?: PluginCharacter;
}

type AvatarPreviewState = "listening" | "thinking" | "acting" | "speaking";

interface RosterAvatar {
    url: string;
    mimeType: string;
    stateUrls?: Record<AvatarPreviewState, string>;
}

@Component({
    selector: "app-crew-roster",
    standalone: true,
    imports: [MatButtonModule, MatIconModule],
    templateUrl: "./crew-roster.component.html",
    styleUrl: "./crew-roster.component.scss",
})
export class CrewRosterComponent implements OnChanges, OnDestroy {
    @Input({ required: true }) config!: ConfigWithCharacters;
    @Input() previewOnly = false;
    @Input() showManager = false;
    @Input() addingCharacter = false;
    @Output() primarySelected = new EventEmitter<number>();
    @Output() characterPreviewed = new EventEmitter<number | null>();
    @Output() rosterManagerChanged = new EventEmitter<boolean>();
    @Output() characterEditRequested = new EventEmitter<number>();
    @Output() pluginCharacterEditRequested = new EventEmitter<PluginCharacter>();
    @Output() characterDuplicateRequested = new EventEmitter<number>();
    @Output() characterDeleteRequested = new EventEmitter<number>();
    @Output() characterAddRequested = new EventEmitter<void>();
    readonly maxActiveCharacters = 3;
    saving = false;
    readonly avatarPreviewStates: readonly AvatarPreviewState[] = ["listening", "thinking", "acting", "speaking"];
    avatarPreviewState: AvatarPreviewState = "listening";
    private avatarPreviewStateIndex = 0;
    private readonly avatarPreviewInterval = setInterval(() => {
        this.avatarPreviewStateIndex = (this.avatarPreviewStateIndex + 1) % this.avatarPreviewStates.length;
        this.avatarPreviewState = this.avatarPreviewStates[this.avatarPreviewStateIndex];
    }, 3000);
    private destroyed = false;
    private avatars = new Map<string, RosterAvatar>();
    private pendingAvatars = new Set<string>();
    private avatarReferences = new Set<string>();
    private providers: ModelProviderDefinition[] = [];
    private providersSubscription: Subscription;
    private pluginCharactersSubscription: Subscription;
    private pluginCharacters: PluginCharacter[] = [];
    private readonly fallbackAvatar: RosterAvatar = {
        url: CharacterService.DEFAULT_AVATAR_URL,
        mimeType: CharacterService.DEFAULT_AVATAR_MIME,
    };

    constructor(
        private configService: ConfigService,
        private avatarService: AvatarService,
        private snackBar: MatSnackBar,
    ) {
        this.providersSubscription = this.configService.plugin_model_providers$.subscribe(
            (providers) => this.providers = providers,
        );
        this.pluginCharactersSubscription = this.configService.pluginCharacters$.subscribe((characters) => {
            this.pluginCharacters = characters;
            if (this.config) this.ngOnChanges();
        });
    }

    get activeIndices(): number[] {
        return [...new Set([this.config.active_character_index, ...(this.config.active_characters ?? [])])]
            .filter((index) => Number.isInteger(index) && index >= 0 && index < this.config.characters.length);
    }

    get activeEntries(): RosterEntry[] {
        return [
            ...this.activeIndices.map((index) => ({ index, character: this.config.characters[index] })),
            ...this.pluginCharacters.filter(plugin => plugin.active).map((plugin, index) => ({
                index: -index - 1, character: plugin.character as Character, plugin,
            })),
        ];
    }

    get hasMultipleActiveCrew(): boolean {
        return this.activeEntries.length > 1;
    }

    get crewIsFull(): boolean {
        return this.activeIndices.length >= this.maxActiveCharacters;
    }

    getVoiceDisplay(character: Character): string {
        return providerVoiceDisplayValue(
            this.config.tts_provider, this.providers, character.tts_voice_settings, character.tts_voice,
        ) || "No voice selected";
    }

    editCharacter(index: number): void {
        if (this.previewOnly || this.saving || index === 0 || !this.config.characters[index]) return;
        this.characterEditRequested.emit(index);
    }

    editEntry(entry: RosterEntry): void {
        if (this.previewOnly || this.saving) return;
        if (entry.plugin) this.pluginCharacterEditRequested.emit(entry.plugin);
        else this.editCharacter(entry.index);
    }

    addStandbyCharacter(): void {
        if (this.previewOnly || this.saving || this.addingCharacter) return;
        this.characterAddRequested.emit();
    }

    duplicateStandbyCharacter(index: number): void {
        if (this.previewOnly || this.saving || !this.config.characters[index] || this.activeIndices.includes(index)) return;
        this.characterDuplicateRequested.emit(index);
    }

    deleteStandbyCharacter(index: number): void {
        if (this.previewOnly || this.saving || index === 0 || !this.config.characters[index] || this.activeIndices.includes(index)) return;
        this.characterDeleteRequested.emit(index);
    }

    toggleRosterManager(): void {
        if (this.previewOnly) return;
        this.showManager = !this.showManager;
        this.rosterManagerChanged.emit(this.showManager);
    }

    setHoveredCharacter(index: number | null): void {
        if (index !== null && index >= 0 && this.hasMultipleActiveCrew) {
            this.characterPreviewed.emit(index);
        }
    }

    setFocusedCharacter(index: number | null): void {
        this.setHoveredCharacter(index);
    }

    get standbyEntries(): RosterEntry[] {
        const active = new Set(this.activeIndices);
        return this.config.characters
            .map((character, index) => ({ index, character }))
            .filter((entry) => !active.has(entry.index));
    }

    isPrimary(index: number): boolean {
        return index === this.config.active_character_index;
    }

    selectPrimary(index: number): void {
        if (index >= 0 && !this.previewOnly && !this.saving && !this.isPrimary(index)) {
            this.primarySelected.emit(index);
        }
    }

    async setCrewMember(index: number, enabled: boolean): Promise<void> {
        if (this.previewOnly || this.saving || this.isPrimary(index) || !this.config.characters[index]) return;
        const active = new Set(this.activeIndices);
        if (enabled) {
            if (this.crewIsFull && !active.has(index)) return;
            active.add(index);
        } else {
            active.delete(index);
        }
        this.saving = true;
        try {
            await this.configService.changeConfig({ active_characters: [...active] });
        } catch (error) {
            console.error("Error saving crew roster:", error);
            this.snackBar.open("Could not save crew roster", "OK", { duration: 5000 });
        } finally {
            this.saving = false;
        }
    }

    getAvatar(character: Character): RosterAvatar {
        return this.avatars.get(this.getAvatarReference(character)) || this.fallbackAvatar;
    }

    private getAvatarReference(character: Partial<Character>): string {
        return character.avatar
            || this.pluginCharacters.find(plugin => plugin.character === character)?.default_avatar
            || this.fallbackAvatar.url;
    }

    getAvatarUrl(character: Character): string {
        const avatar = this.getAvatar(character);
        return avatar.stateUrls?.[this.avatarPreviewState] ?? avatar.url;
    }

    usesSpriteSheet(character: Character): boolean {
        return this.getAvatar(character).mimeType.toLowerCase().split(";")[0].trim() !== "image/svg+xml";
    }

    ngOnChanges(): void {
        this.avatarReferences = new Set(
            [...this.config.characters, ...this.pluginCharacters.filter(p => p.active).map(p => p.character)]
                .map((character) => this.getAvatarReference(character)),
        );
        for (const [path, avatar] of this.avatars) {
            if (!this.avatarReferences.has(path)) {
                this.revokeAvatar(avatar);
                this.avatars.delete(path);
            }
        }
        for (const path of this.avatarReferences) {
            if (!this.avatars.has(path) && !this.pendingAvatars.has(path)) {
                void this.loadAvatar(path);
            }
        }
    }

    private async loadAvatar(path: string): Promise<void> {
        this.pendingAvatars.add(path);
        try {
            const source = await this.avatarService.getAvatarWithMime(path) ?? this.fallbackAvatar;
            const avatar = await this.prepareAvatarStates(source);
            if (this.destroyed || !this.avatarReferences.has(path)) {
                this.revokeAvatar(avatar);
            } else {
                this.avatars.set(path, avatar);
            }
        } catch {
            if (!this.destroyed && this.avatarReferences.has(path)) {
                this.avatars.set(path, this.fallbackAvatar);
            }
        } finally {
            this.pendingAvatars.delete(path);
        }
    }

    private async prepareAvatarStates(avatar: RosterAvatar): Promise<RosterAvatar> {
        if (avatar.mimeType.toLowerCase().split(";")[0].trim() !== "image/svg+xml") return avatar;
        const stateUrls = {} as Record<AvatarPreviewState, string>;
        try {
            const response = await fetch(avatar.url);
            if (!response.ok) return avatar;
            const document = new DOMParser().parseFromString(await response.text(), "image/svg+xml");
            const svg = document.documentElement;
            if (svg.localName !== "svg" || document.querySelector("parsererror")) return avatar;
            // Keep SVGs in image context so uploaded SVG scripts cannot execute.
            for (const state of this.avatarPreviewStates) {
                svg.classList.remove(...this.avatarPreviewStates);
                svg.classList.add(state);
                const blob = new Blob([new XMLSerializer().serializeToString(svg)], { type: "image/svg+xml" });
                stateUrls[state] = URL.createObjectURL(blob);
            }
            return { ...avatar, stateUrls };
        } catch {
            for (const url of Object.values(stateUrls)) {
                URL.revokeObjectURL(url);
            }
            return avatar;
        }
    }

    private revokeAvatar(avatar: RosterAvatar): void {
        if (this.avatarService.isObjectUrl(avatar.url)) {
            URL.revokeObjectURL(avatar.url);
        }
        for (const url of Object.values(avatar.stateUrls ?? {})) {
            URL.revokeObjectURL(url);
        }
    }

    ngOnDestroy(): void {
        this.destroyed = true;
        clearInterval(this.avatarPreviewInterval);
        this.providersSubscription.unsubscribe();
        this.pluginCharactersSubscription.unsubscribe();
        for (const avatar of this.avatars.values()) {
            this.revokeAvatar(avatar);
        }
        this.avatars.clear();
    }
}
