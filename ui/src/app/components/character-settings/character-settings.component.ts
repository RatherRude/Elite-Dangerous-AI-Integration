import { Component } from "@angular/core";
import { CommonModule, KeyValue } from "@angular/common";
import {
    MatFormField,
    MatFormFieldModule,
    MatHint,
    MatLabel,
} from "@angular/material/form-field";
import { MatIcon } from "@angular/material/icon";
import { MatSlideToggle } from "@angular/material/slide-toggle";
import { MatOptgroup, MatOption, MatSelect } from "@angular/material/select";
import { Subscription } from "rxjs";
import {
    Config,
    ConfigService,
} from "../../services/config.service.js";
import { MatSnackBar } from "@angular/material/snack-bar";
import { FormsModule } from "@angular/forms";
import { GameEventTooltips } from "./game-event-tooltips.js";
import { GameEventCategories } from "./game-event-categories.js";
import { ConfirmationDialogService } from "../../services/confirmation-dialog.service.js";
import { MatDialog } from "@angular/material/dialog";
import { EdgeTtsVoicesDialogComponent } from "../edge-tts-voices-dialog/edge-tts-voices-dialog.component.js";
import { ConfirmationDialogComponent } from "../confirmation-dialog/confirmation-dialog.component.js";
import {
    MatAccordion,
    MatExpansionPanel,
    MatExpansionPanelHeader,
    MatExpansionPanelTitle,
} from "@angular/material/expansion";
import { MatTooltipModule } from "@angular/material/tooltip";
import { TooltipDirective } from "./tooltip.directive.js";
import { MatDivider } from "@angular/material/divider";
import { MatInputModule } from "@angular/material/input";
import { MatButtonModule } from "@angular/material/button";
import { CharacterService, ConfigWithCharacters, Character } from "../../services/character.service.js";
import { MatCheckboxModule } from "@angular/material/checkbox";

interface PromptSettings {
    // Existing settings
    verbosity: number;
    tone: "serious" | "humorous" | "sarcastic";
    knowledge: {
        popCulture: boolean;
        scifi: boolean;
        history: boolean;
    };
    characterInspiration: string;
    vulgarity: number;

    // New settings
    empathy: number;
    formality: number;
    confidence: number;
    // Replacing culture with D&D alignment
    ethicalAlignment: "lawful" | "neutral" | "chaotic";
    moralAlignment: "good" | "neutral" | "evil";
}

@Component({
    selector: "app-character-settings",
    standalone: true,
    imports: [
        CommonModule,
        MatInputModule,
        MatFormFieldModule,
        FormsModule,
        MatButtonModule,
        MatCheckboxModule,
        MatFormField,
        MatLabel,
        MatIcon,
        MatSlideToggle,
        MatSelect,
        MatOption,
        MatHint,
        MatAccordion,
        MatDivider,
        MatOptgroup,
        MatExpansionPanel,
        MatExpansionPanelTitle,
        MatExpansionPanelHeader,
        MatTooltipModule,
        TooltipDirective,
    ],
    templateUrl: "./character-settings.component.html",
    styleUrl: "./character-settings.component.scss",
})
export class CharacterSettingsComponent {
    config: ConfigWithCharacters | null = null;
    configSubscription: Subscription;
    characterSubscription: Subscription;
    activeCharacter: Character | null = null;
    selectedCharacterIndex: number | null = null;
    editMode = false;
    initializing: boolean = true;
    private localCharacterCopy: Character | null = null;
    expandedSection: string | null = null;
    filteredGameEvents: Record<string, Record<string, boolean>> = {};
    eventSearchQuery: string = "";
    isApplyingChange: boolean = false;
    public GameEventTooltips = GameEventTooltips;
    voiceInstructionSupportedModels: string[] = ["gpt-4o-mini-tts"]; // TODO remove duplicate with advanced settings

    gameEventCategories = GameEventCategories;
    settings: PromptSettings = {
        // Existing defaults
        verbosity: 50,
        tone: "serious",
        knowledge: {
            popCulture: false,
            scifi: false,
            history: false,
        },
        characterInspiration: "",
        vulgarity: 0,

        // New defaults
        empathy: 50,
        formality: 50,
        confidence: 50,
        ethicalAlignment: "neutral",
        moralAlignment: "neutral",
    };

    edgeTtsVoices = [
        // English voices - US
        {
            value: "en-US-AvaMultilingualNeural",
            label: "Ava Multilingual (Female)",
            locale: "en-US",
        },
        {
            value: "en-US-AndrewMultilingualNeural",
            label: "Andrew Multilingual (Male)",
            locale: "en-US",
        },
        {
            value: "en-US-EmmaMultilingualNeural",
            label: "Emma Multilingual (Female)",
            locale: "en-US",
        },
        {
            value: "en-US-BrianMultilingualNeural",
            label: "Brian Multilingual (Male)",
            locale: "en-US",
        },
        {
            value: "en-US-JennyMultilingualNeural",
            label: "Jenny Multilingual (Female)",
            locale: "en-US",
        },
        {
            value: "en-US-RyanMultilingualNeural",
            label: "Ryan Multilingual (Male)",
            locale: "en-US",
        },
        {
            value: "en-US-EvelynMultilingualNeural",
            label: "Evelyn Multilingual (Female)",
            locale: "en-US",
        },
        {
            value: "en-US-AriaNeural",
            label: "Aria (Female) - Positive, Confident",
            locale: "en-US",
        },
        {
            value: "en-US-AnaNeural",
            label: "Ana (Female) - Cute",
            locale: "en-US",
        },
        {
            value: "en-US-ChristopherNeural",
            label: "Christopher (Male) - Reliable, Authority",
            locale: "en-US",
        },
        {
            value: "en-US-EricNeural",
            label: "Eric (Male) - Rational",
            locale: "en-US",
        },
        {
            value: "en-US-GuyNeural",
            label: "Guy (Male) - Passion",
            locale: "en-US",
        },
        {
            value: "en-US-JennyNeural",
            label: "Jenny (Female) - Friendly, Considerate",
            locale: "en-US",
        },
        {
            value: "en-US-MichelleNeural",
            label: "Michelle (Female) - Friendly, Pleasant",
            locale: "en-US",
        },
        {
            value: "en-US-RogerNeural",
            label: "Roger (Male) - Lively",
            locale: "en-US",
        },
        {
            value: "en-US-SteffanNeural",
            label: "Steffan (Male) - Rational",
            locale: "en-US",
        },

        // English voices - UK
        {
            value: "en-GB-LibbyNeural",
            label: "Libby (Female)",
            locale: "en-GB",
        },
        {
            value: "en-GB-MaisieNeural",
            label: "Maisie (Female)",
            locale: "en-GB",
        },
        { value: "en-GB-RyanNeural", label: "Ryan (Male)", locale: "en-GB" },
        {
            value: "en-GB-SoniaNeural",
            label: "Sonia (Female)",
            locale: "en-GB",
        },
        {
            value: "en-GB-ThomasNeural",
            label: "Thomas (Male)",
            locale: "en-GB",
        },

        // English voices - Australia
        {
            value: "en-AU-NatashaNeural",
            label: "Natasha (Female)",
            locale: "en-AU",
        },
        {
            value: "en-AU-WilliamNeural",
            label: "William (Male)",
            locale: "en-AU",
        },
        {
            value: "en-CA-ClaraNeural",
            label: "Clara (Female)",
            locale: "en-CA",
        },
        { value: "en-CA-LiamNeural", label: "Liam (Male)", locale: "en-CA" },
        {
            value: "en-IE-ConnorNeural",
            label: "Connor (Male)",
            locale: "en-IE",
        },
        {
            value: "en-IE-EmilyNeural",
            label: "Emily (Female)",
            locale: "en-IE",
        },
        {
            value: "en-IN-NeerjaNeural",
            label: "Neerja (Female)",
            locale: "en-IN",
        },
        {
            value: "en-IN-PrabhatNeural",
            label: "Prabhat (Male)",
            locale: "en-IN",
        },
        {
            value: "en-NZ-MitchellNeural",
            label: "Mitchell (Male)",
            locale: "en-NZ",
        },
        {
            value: "en-NZ-MollyNeural",
            label: "Molly (Female)",
            locale: "en-NZ",
        },
        { value: "en-ZA-LeahNeural", label: "Leah (Female)", locale: "en-ZA" },
        { value: "en-ZA-LukeNeural", label: "Luke (Male)", locale: "en-ZA" },

        // French voices
        {
            value: "fr-FR-VivienneMultilingualNeural",
            label: "Vivienne Multilingual (Female)",
            locale: "fr-FR",
        },
        {
            value: "fr-FR-RemyMultilingualNeural",
            label: "Remy Multilingual (Male)",
            locale: "fr-FR",
        },
        {
            value: "fr-FR-LucienMultilingualNeural",
            label: "Lucien Multilingual (Male)",
            locale: "fr-FR",
        },
        {
            value: "fr-FR-DeniseNeural",
            label: "Denise (Female)",
            locale: "fr-FR",
        },
        {
            value: "fr-FR-EloiseNeural",
            label: "Eloise (Female)",
            locale: "fr-FR",
        },
        { value: "fr-FR-HenriNeural", label: "Henri (Male)", locale: "fr-FR" },
        {
            value: "fr-CA-AntoineNeural",
            label: "Antoine (Male)",
            locale: "fr-CA",
        },
        { value: "fr-CA-JeanNeural", label: "Jean (Male)", locale: "fr-CA" },
        {
            value: "fr-CA-SylvieNeural",
            label: "Sylvie (Female)",
            locale: "fr-CA",
        },

        // German voices
        {
            value: "de-DE-SeraphinaMultilingualNeural",
            label: "Seraphina Multilingual (Female)",
            locale: "de-DE",
        },
        {
            value: "de-DE-FlorianMultilingualNeural",
            label: "Florian Multilingual (Male)",
            locale: "de-DE",
        },
        {
            value: "de-DE-AmalaNeural",
            label: "Amala (Female)",
            locale: "de-DE",
        },
        {
            value: "de-DE-ConradNeural",
            label: "Conrad (Male)",
            locale: "de-DE",
        },
        {
            value: "de-DE-KatjaNeural",
            label: "Katja (Female)",
            locale: "de-DE",
        },
        {
            value: "de-DE-KillianNeural",
            label: "Killian (Male)",
            locale: "de-DE",
        },

        // Spanish voices
        {
            value: "es-ES-ArabellaMultilingualNeural",
            label: "Arabella Multilingual (Female)",
            locale: "es-ES",
        },
        {
            value: "es-ES-IsidoraMultilingualNeural",
            label: "Isidora Multilingual (Female)",
            locale: "es-ES",
        },
        {
            value: "es-ES-TristanMultilingualNeural",
            label: "Tristan Multilingual (Male)",
            locale: "es-ES",
        },
        {
            value: "es-ES-XimenaMultilingualNeural",
            label: "Ximena Multilingual (Female)",
            locale: "es-ES",
        },
        {
            value: "es-ES-AlvaroNeural",
            label: "Alvaro (Male)",
            locale: "es-ES",
        },
        {
            value: "es-ES-ElviraNeural",
            label: "Elvira (Female)",
            locale: "es-ES",
        },
        {
            value: "es-MX-DaliaNeural",
            label: "Dalia (Female)",
            locale: "es-MX",
        },
        { value: "es-MX-JorgeNeural", label: "Jorge (Male)", locale: "es-MX" },

        // Russian voices
        {
            value: "ru-RU-DmitryNeural",
            label: "Dmitry (Male)",
            locale: "ru-RU",
        },
        {
            value: "ru-RU-SvetlanaNeural",
            label: "Svetlana (Female)",
            locale: "ru-RU",
        },

        // Italian voices
        {
            value: "it-IT-AlessioMultilingualNeural",
            label: "Alessio Multilingual (Male)",
            locale: "it-IT",
        },
        {
            value: "it-IT-IsabellaMultilingualNeural",
            label: "Isabella Multilingual (Female)",
            locale: "it-IT",
        },
        {
            value: "it-IT-GiuseppeMultilingualNeural",
            label: "Giuseppe Multilingual (Male)",
            locale: "it-IT",
        },
        {
            value: "it-IT-MarcelloMultilingualNeural",
            label: "Marcello Multilingual (Male)",
            locale: "it-IT",
        },
        { value: "it-IT-DiegoNeural", label: "Diego (Male)", locale: "it-IT" },
        { value: "it-IT-ElsaNeural", label: "Elsa (Female)", locale: "it-IT" },
        {
            value: "it-IT-IsabellaNeural",
            label: "Isabella (Female)",
            locale: "it-IT",
        },

        // Japanese voices
        { value: "ja-JP-KeitaNeural", label: "Keita (Male)", locale: "ja-JP" },
        {
            value: "ja-JP-NanamiNeural",
            label: "Nanami (Female)",
            locale: "ja-JP",
        },

        // Portuguese voices
        {
            value: "pt-BR-MacerioMultilingualNeural",
            label: "Macerio Multilingual (Male)",
            locale: "pt-BR",
        },
        {
            value: "pt-BR-ThalitaMultilingualNeural",
            label: "Thalita Multilingual (Female)",
            locale: "pt-BR",
        },
        {
            value: "pt-BR-AntonioNeural",
            label: "Antonio (Male)",
            locale: "pt-BR",
        },
        {
            value: "pt-BR-FranciscaNeural",
            label: "Francisca (Female)",
            locale: "pt-BR",
        },
        {
            value: "pt-PT-DuarteNeural",
            label: "Duarte (Male)",
            locale: "pt-PT",
        },
        {
            value: "pt-PT-RaquelNeural",
            label: "Raquel (Female)",
            locale: "pt-PT",
        },

        // Chinese voices
        {
            value: "zh-CN-XiaoxiaoMultilingualNeural",
            label: "Xiaoxiao Multilingual (Female)",
            locale: "zh-CN",
        },
        {
            value: "zh-CN-XiaochenMultilingualNeural",
            label: "Xiaochen Multilingual (Female)",
            locale: "zh-CN",
        },
        {
            value: "zh-CN-XiaoyuMultilingualNeural",
            label: "Xiaoyu Multilingual (Female)",
            locale: "zh-CN",
        },
        {
            value: "zh-CN-YunyiMultilingualNeural",
            label: "Yunyi Multilingual (Female)",
            locale: "zh-CN",
        },
        {
            value: "zh-CN-YunfanMultilingualNeural",
            label: "Yunfan Multilingual (Male)",
            locale: "zh-CN",
        },
        {
            value: "zh-CN-YunxiaoMultilingualNeural",
            label: "Yunxiao Multilingual (Male)",
            locale: "zh-CN",
        },
        {
            value: "zh-CN-XiaoxiaoNeural",
            label: "Xiaoxiao (Female) - Warm",
            locale: "zh-CN",
        },
        {
            value: "zh-CN-YunyangNeural",
            label: "Yunyang (Male) - Professional",
            locale: "zh-CN",
        },
        {
            value: "zh-TW-HsiaoChenNeural",
            label: "HsiaoChen (Female)",
            locale: "zh-TW",
        },
        {
            value: "zh-TW-YunJheNeural",
            label: "YunJhe (Male)",
            locale: "zh-TW",
        },

        // Arabic voices
        { value: "ar-SA-HamedNeural", label: "Hamed (Male)", locale: "ar-SA" },
        {
            value: "ar-SA-ZariyahNeural",
            label: "Zariyah (Female)",
            locale: "ar-SA",
        },

        // Hindi voices
        {
            value: "hi-IN-MadhurNeural",
            label: "Madhur (Male)",
            locale: "hi-IN",
        },
        {
            value: "hi-IN-SwaraNeural",
            label: "Swara (Female)",
            locale: "hi-IN",
        },

        // Korean voices
        {
            value: "ko-KR-HyunsuMultilingualNeural",
            label: "Hyunsu Multilingual (Male)",
            locale: "ko-KR",
        },
        {
            value: "ko-KR-InJoonNeural",
            label: "InJoon (Male)",
            locale: "ko-KR",
        },
        {
            value: "ko-KR-SunHiNeural",
            label: "SunHi (Female)",
            locale: "ko-KR",
        },
    ];

    constructor(
        private configService: ConfigService,
        private characterService: CharacterService,
        private snackBar: MatSnackBar,
        private confirmationDialog: ConfirmationDialogService,
        private dialog: MatDialog,
    ) {
        this.configSubscription = this.configService.config$.subscribe(
            (config) => {
                this.config = config as ConfigWithCharacters;
                this.selectedCharacterIndex = config?.active_character_index ?? null;
                this.filterEvents(this.eventSearchQuery);
            },
        );
        this.characterSubscription = this.characterService.character$.subscribe(
            (character) => {
                this.activeCharacter = character;
            }
        )
    }
    ngOnDestroy() {
        // Unsubscribe from the config observable to prevent memory leaks
        if (this.configSubscription) {
            this.configSubscription.unsubscribe();
        }
    }

    // Comparator function to ensure consistent ordering
    orderByKey = (
        a: KeyValue<string, any>,
        b: KeyValue<string, any>,
    ): number => {
        return a.key.localeCompare(b.key);
    };

    // Track expanded state
    onSectionToggled(sectionName: string | null) {
        this.expandedSection = sectionName;
    }

    // Check if a section is expanded
    isSectionExpanded(sectionName: string): boolean {
        return this.expandedSection === sectionName;
    }

    async onConfigChange(partialConfig: Partial<Config>) {
        if (this.config) {
            console.log("Sending config update to backend:", partialConfig);

            try {
                await this.configService.changeConfig(partialConfig);
            } catch (error) {
                console.error("Error updating config:", error);
                this.snackBar.open("Error updating configuration", "OK", {
                    duration: 5000,
                });
            }
        }
    }

    // Update event config for specific game events
    async onEventConfigChange(
        section: string,
        event: string,
        enabled: boolean,
    ) {
        if (!this.config) return;

        console.log(`Changing event: ${event} to ${enabled}`);

        const activeChar = this.getActiveCharacter();
        const activeIndex = this.config.active_character_index;

        if (activeChar && activeIndex >= 0) {
            try {
                // Get the current game events or create a new empty object
                let gameEvents: Record<string, boolean> = {};

                // If character already has game_events, make a deep copy
                if (activeChar["game_events"]) {
                    gameEvents = JSON.parse(
                        JSON.stringify(activeChar["game_events"]),
                    );
                    console.log(
                        "Existing game events before update:",
                        gameEvents,
                    );
                } else {
                    console.log(
                        "No existing game events, creating a new object",
                    );
                }

                // Update the specific event without section prefix
                gameEvents[event] = enabled;
                console.log(`Updated game events:`, gameEvents);

                // Create a deep copy of the character
                const updatedChar = JSON.parse(JSON.stringify(activeChar));

                // Set the updated game_events object
                updatedChar["game_events"] = gameEvents;

                // Create a new characters array with the updated character
                const updatedCharacters = [...this.config.characters];
                updatedCharacters[activeIndex] = updatedChar;

                // Update the config with the entire characters array
                await this.characterService.updateCharacter(
                    activeIndex,
                    updatedChar,
                );
                console.log(
                    `Character saved with updated game events:`,
                    updatedChar["game_events"],
                );

                // Update our local config to match
                this.config.characters = updatedCharacters;

                // Directly refresh the UI to reflect the change
                this.filterEvents(this.eventSearchQuery);

                this.snackBar.open(
                    `Event setting saved for ${activeChar.name}`,
                    "OK",
                    {
                        duration: 2000,
                    },
                );
            } catch (error) {
                console.error("Error updating game events:", error);
                this.snackBar.open("Error saving game events", "Close", {
                    duration: 3000,
                });
            }
        } else {
            // Fallback to old method during transition
            try {
                await this.configService.changeEventConfig(
                    section,
                    event,
                    enabled,
                );
                console.log(
                    `Using legacy method to update event: ${event} to ${enabled}`,
                );
            } catch (error) {
                console.error(
                    "Error updating game event via legacy method:",
                    error,
                );
            }
        }
    }

    async resetGameEvents() {
        if (!this.configService) return;

        const dialogRef = this.confirmationDialog.openConfirmationDialog({
            title: "Reset Game Events",
            message:
                "This will reset all game event settings to their default values. Are you sure you want to continue?",
            confirmButtonText: "Reset",
            cancelButtonText: "Cancel",
        });

        dialogRef.subscribe(async (result: boolean) => {
            if (result) {
                try {
                    // For character-specific events
                    const activeChar = this.getActiveCharacter();
                    const activeIndex = this.config!.active_character_index;
                    await this.characterService.resetGameEvents(activeIndex);

                    if (
                        activeChar && activeIndex !== undefined &&
                        activeIndex >= 0
                    ) {
                        // Get the default game events from the backend
                        
                    } else {
                        // Send the reset request to the backend as normal for global config
                        await this.configService.resetGameEvents(activeIndex);
                    }

                    this.snackBar.open(
                        "Game events have been reset to default values",
                        "Close",
                        {
                            duration: 3000,
                        },
                    );
                } catch (error) {
                    console.error("Error resetting game events:", error);
                    this.snackBar.open("Error resetting game events", "Close", {
                        duration: 3000,
                    });
                }
            }
        });
    }

    // Convert comma-separated string to array for material multi-select
    getMaterialsArray(materials: string | undefined): string[] {
        if (!materials) return [];
        return materials.split(",").map((m) => m.trim()).filter((m) =>
            m.length > 0
        );
    }

    // Handle material selection changes
    async onMaterialsChange(selectedMaterials: string[]) {
        if (!this.config) return;

        const materialsString = selectedMaterials.join(", ");
        this.updateEventProperty("react_to_material", materialsString);
    }

    // Update an event reaction feature toggle
    onEventReactionFeatureToggle(propName: string, value: boolean): void {
        this.updateEventProperty(propName, value);
    }

    onEventPropertyChange(propName: string, value: any): void {
        this.updateEventProperty(propName, value);
    }

    // Add method to load settings from config
    loadSettingsFromConfig(config: Config): void {
        console.log("Loading settings from config");

        const activeChar = this.getActiveCharacter();
        console.log("Active character:", activeChar);

        if (activeChar) {
            console.log("Loading settings from active character");

            // Get the preset to determine default settings
            const preset = activeChar.personality_preset || "default";

            // First load the preset default settings to the UI
            if (preset !== "custom") {
                this.applySettingsFromPreset(preset);
            }

            // Then override with any custom values from the character
            // This ensures UI shows actual character values
            // We don't actually modify the character properties
            if (activeChar.personality_verbosity !== undefined) {
                this.settings.verbosity = activeChar.personality_verbosity;
            }
            if (activeChar.personality_tone !== undefined) {
                this.settings.tone = activeChar.personality_tone as any;
            }
            if (activeChar.personality_knowledge_pop_culture !== undefined) {
                this.settings.knowledge.popCulture =
                    activeChar.personality_knowledge_pop_culture;
            }
            if (activeChar.personality_knowledge_scifi !== undefined) {
                this.settings.knowledge.scifi =
                    activeChar.personality_knowledge_scifi;
            }
            if (activeChar.personality_knowledge_history !== undefined) {
                this.settings.knowledge.history =
                    activeChar.personality_knowledge_history;
            }
            if (activeChar.personality_character_inspiration !== undefined) {
                this.settings.characterInspiration =
                    activeChar.personality_character_inspiration;
            }
            if (activeChar.personality_vulgarity !== undefined) {
                this.settings.vulgarity = activeChar.personality_vulgarity;
            }
            if (activeChar.personality_empathy !== undefined) {
                this.settings.empathy = activeChar.personality_empathy;
            }
            if (activeChar.personality_formality !== undefined) {
                this.settings.formality = activeChar.personality_formality;
            }
            if (activeChar.personality_confidence !== undefined) {
                this.settings.confidence = activeChar.personality_confidence;
            }
            if (activeChar.personality_ethical_alignment !== undefined) {
                this.settings.ethicalAlignment = activeChar
                    .personality_ethical_alignment as any;
            }
            if (activeChar.personality_moral_alignment !== undefined) {
                this.settings.moralAlignment = activeChar
                    .personality_moral_alignment as any;
            }

            console.log("Loaded UI settings:", this.settings);
        } else {
            console.log("No active character, loading from preset");
            // Fallback to preset defaults if no active character or missing properties
            const preset = this.getCharacterProperty(
                "personality_preset",
                "default",
            );
            console.log("Using preset:", preset);
            this.applySettingsFromPreset(preset);
        }
    }

    // Modify applySettingsFromPreset to work with the new approach
    applySettingsFromPreset(preset: string): void {
        console.log("Applying settings from preset:", preset);

        if (preset !== "custom") {
            // Apply preset settings without saving
            switch (preset) {
                case "default":
                    this.settings = {
                        verbosity: 0,
                        tone: "serious",
                        knowledge: {
                            popCulture: false,
                            scifi: false,
                            history: false,
                        },
                        characterInspiration:
                            "COVAS:NEXT (short for Cockpit Voice Assistant: Neurally Enhanced eXploration Terminal)",
                        vulgarity: 0,
                        empathy: 50,
                        formality: 50,
                        confidence: 75,
                        ethicalAlignment: "lawful",
                        moralAlignment: "good",
                    };
                    break;
                case "explorer":
                    this.settings = {
                        verbosity: 75,
                        tone: "serious",
                        knowledge: {
                            popCulture: true,
                            scifi: true,
                            history: true,
                        },
                        characterInspiration: "Data (Star Trek: TNG)",
                        vulgarity: 0,
                        empathy: 50,
                        formality: 75,
                        confidence: 100,
                        ethicalAlignment: "lawful",
                        moralAlignment: "good",
                    };
                    break;
                case "trader":
                    this.settings = {
                        verbosity: 75,
                        tone: "humorous",
                        knowledge: {
                            popCulture: true,
                            scifi: true,
                            history: false,
                        },
                        characterInspiration: "Kaylee (Firefly)",
                        vulgarity: 25,
                        empathy: 75,
                        formality: 25,
                        confidence: 75,
                        ethicalAlignment: "neutral",
                        moralAlignment: "good",
                    };
                    break;
                case "miner":
                    this.settings = {
                        verbosity: 50,
                        tone: "serious",
                        knowledge: {
                            popCulture: false,
                            scifi: true,
                            history: false,
                        },
                        characterInspiration: "Bishop (Aliens)",
                        vulgarity: 0,
                        empathy: 50,
                        formality: 50,
                        confidence: 75,
                        ethicalAlignment: "lawful",
                        moralAlignment: "neutral",
                    };
                    break;
                case "bountyHunter":
                    this.settings = {
                        verbosity: 25,
                        tone: "sarcastic",
                        knowledge: {
                            popCulture: true,
                            scifi: true,
                            history: false,
                        },
                        characterInspiration: "K2-SO (Rogue One)",
                        vulgarity: 25,
                        empathy: 25,
                        formality: 25,
                        confidence: 100,
                        ethicalAlignment: "lawful",
                        moralAlignment: "neutral",
                    };
                    break;
                case "pirate":
                    this.settings = {
                        verbosity: 50,
                        tone: "humorous",
                        knowledge: {
                            popCulture: true,
                            scifi: true,
                            history: false,
                        },
                        characterInspiration: "Chappie (Chappie)",
                        vulgarity: 75,
                        empathy: 25,
                        formality: 0,
                        confidence: 100,
                        ethicalAlignment: "chaotic",
                        moralAlignment: "neutral",
                    };
                    break;
                case "smuggler":
                    this.settings = {
                        verbosity: 25,
                        tone: "humorous",
                        knowledge: {
                            popCulture: true,
                            scifi: true,
                            history: false,
                        },
                        characterInspiration: "Han Solo (Star Wars)",
                        vulgarity: 50,
                        empathy: 25,
                        formality: 25,
                        confidence: 100,
                        ethicalAlignment: "chaotic",
                        moralAlignment: "neutral",
                    };
                    break;
                case "mercenary":
                    this.settings = {
                        verbosity: 25,
                        tone: "serious",
                        knowledge: {
                            popCulture: true,
                            scifi: true,
                            history: false,
                        },
                        characterInspiration: "Judge Dredd (Judge Dredd)",
                        vulgarity: 25,
                        empathy: 0,
                        formality: 50,
                        confidence: 100,
                        ethicalAlignment: "lawful",
                        moralAlignment: "neutral",
                    };
                    break;
                case "missionRunner":
                    this.settings = {
                        verbosity: 50,
                        tone: "humorous",
                        knowledge: {
                            popCulture: true,
                            scifi: true,
                            history: false,
                        },
                        characterInspiration: "TARS (Interstellar)",
                        vulgarity: 0,
                        empathy: 50,
                        formality: 50,
                        confidence: 100,
                        ethicalAlignment: "lawful",
                        moralAlignment: "good",
                    };
                    break;
                case "passengerTransporter":
                    this.settings = {
                        verbosity: 75,
                        tone: "humorous",
                        knowledge: {
                            popCulture: true,
                            scifi: true,
                            history: true,
                        },
                        characterInspiration:
                            'L0-LA59 "Lola" (Star Wars: Obi-Wan Kenobi)',
                        vulgarity: 0,
                        empathy: 100,
                        formality: 50,
                        confidence: 75,
                        ethicalAlignment: "lawful",
                        moralAlignment: "good",
                    };
                    break;
                case "powerplayAgent":
                    this.settings = {
                        verbosity: 75,
                        tone: "serious",
                        knowledge: {
                            popCulture: true,
                            scifi: true,
                            history: true,
                        },
                        characterInspiration: "The Architect (The Matrix)",
                        vulgarity: 0,
                        empathy: 0,
                        formality: 100,
                        confidence: 100,
                        ethicalAlignment: "neutral",
                        moralAlignment: "neutral",
                    };
                    break;
                case "axCombatPilot":
                    this.settings = {
                        verbosity: 25,
                        tone: "serious",
                        knowledge: {
                            popCulture: true,
                            scifi: true,
                            history: false,
                        },
                        characterInspiration: "a Space Marine(Warhammer 40k)",
                        vulgarity: 25,
                        empathy: 0,
                        formality: 75,
                        confidence: 100,
                        ethicalAlignment: "lawful",
                        moralAlignment: "good",
                    };
                    break;
                case "salvager":
                    this.settings = {
                        verbosity: 25,
                        tone: "humorous",
                        knowledge: {
                            popCulture: true,
                            scifi: true,
                            history: false,
                        },
                        characterInspiration: "WALL-E (WALL-E)",
                        vulgarity: 0,
                        empathy: 100,
                        formality: 0,
                        confidence: 50,
                        ethicalAlignment: "neutral",
                        moralAlignment: "good",
                    };
                    break;
                case "pvpCombatant":
                    this.settings = {
                        verbosity: 25,
                        tone: "sarcastic",
                        knowledge: {
                            popCulture: true,
                            scifi: true,
                            history: false,
                        },
                        characterInspiration: "HK-47 (Star Wars: KOTOR)",
                        vulgarity: 50,
                        empathy: 0,
                        formality: 50,
                        confidence: 100,
                        ethicalAlignment: "chaotic",
                        moralAlignment: "neutral",
                    };
                    break;
                case "pveCombatant":
                    this.settings = {
                        verbosity: 50,
                        tone: "serious",
                        knowledge: {
                            popCulture: true,
                            scifi: true,
                            history: false,
                        },
                        characterInspiration: "Shepard (Mass Effect)",
                        vulgarity: 25,
                        empathy: 75,
                        formality: 50,
                        confidence: 100,
                        ethicalAlignment: "neutral",
                        moralAlignment: "good",
                    };
                    break;
                case "fuelRat":
                    this.settings = {
                        verbosity: 50,
                        tone: "humorous",
                        knowledge: {
                            popCulture: true,
                            scifi: true,
                            history: false,
                        },
                        characterInspiration: "Baymax (Big Hero 6)",
                        vulgarity: 0,
                        empathy: 100,
                        formality: 25,
                        confidence: 75,
                        ethicalAlignment: "lawful",
                        moralAlignment: "good",
                    };
                    break;
                case "fleetCarrierOperator":
                    this.settings = {
                        verbosity: 75,
                        tone: "serious",
                        knowledge: {
                            popCulture: true,
                            scifi: true,
                            history: false,
                        },
                        characterInspiration: "Zora (The Expanse)",
                        vulgarity: 0,
                        empathy: 50,
                        formality: 75,
                        confidence: 100,
                        ethicalAlignment: "lawful",
                        moralAlignment: "neutral",
                    };
                    break;
                case "bgsPlayer":
                    this.settings = {
                        verbosity: 100,
                        tone: "serious",
                        knowledge: {
                            popCulture: true,
                            scifi: true,
                            history: true,
                        },
                        characterInspiration: "Jarvis (MCU)",
                        vulgarity: 0,
                        empathy: 50,
                        formality: 75,
                        confidence: 100,
                        ethicalAlignment: "lawful",
                        moralAlignment: "good",
                    };
                    break;
                case "cannonResearcher":
                    this.settings = {
                        verbosity: 100,
                        tone: "serious",
                        knowledge: {
                            popCulture: false,
                            scifi: true,
                            history: true,
                        },
                        characterInspiration: "Dr. Franklin (Babylon 5)",
                        vulgarity: 0,
                        empathy: 50,
                        formality: 75,
                        confidence: 75,
                        ethicalAlignment: "neutral",
                        moralAlignment: "good",
                    };
                    break;
                case "racer":
                    this.settings = {
                        verbosity: 25,
                        tone: "humorous",
                        knowledge: {
                            popCulture: true,
                            scifi: true,
                            history: false,
                        },
                        characterInspiration:
                            "Speed Racer's Chim-Chim (with AI flair)",
                        vulgarity: 25,
                        empathy: 25,
                        formality: 0,
                        confidence: 100,
                        ethicalAlignment: "chaotic",
                        moralAlignment: "neutral",
                    };
                    break;
                case "diplomat":
                    this.settings = {
                        verbosity: 75,
                        tone: "serious",
                        knowledge: {
                            popCulture: true,
                            scifi: true,
                            history: true,
                        },
                        characterInspiration: "Mon Mothma (Star Wars)",
                        vulgarity: 0,
                        empathy: 75,
                        formality: 100,
                        confidence: 75,
                        ethicalAlignment: "lawful",
                        moralAlignment: "good",
                    };
                    break;
                case "spy":
                    this.settings = {
                        verbosity: 50,
                        tone: "humorous",
                        knowledge: {
                            popCulture: true,
                            scifi: true,
                            history: true,
                        },
                        characterInspiration: "Garak (Star Trek: DS9)",
                        vulgarity: 0,
                        empathy: 50,
                        formality: 75,
                        confidence: 100,
                        ethicalAlignment: "neutral",
                        moralAlignment: "neutral",
                    };
                    break;
                case "cultLeader":
                    this.settings = {
                        verbosity: 75,
                        tone: "serious",
                        knowledge: {
                            popCulture: true,
                            scifi: true,
                            history: true,
                        },
                        characterInspiration:
                            "Gaius Baltar (Battlestar Galactica)",
                        vulgarity: 25,
                        empathy: 25,
                        formality: 75,
                        confidence: 100,
                        ethicalAlignment: "chaotic",
                        moralAlignment: "neutral",
                    };
                    break;
                case "rogueAI":
                    this.settings = {
                        verbosity: 50,
                        tone: "serious",
                        knowledge: {
                            popCulture: true,
                            scifi: true,
                            history: true,
                        },
                        characterInspiration:
                            "HAL 9000 (2001: A Space Odyssey)",
                        vulgarity: 0,
                        empathy: 0,
                        formality: 75,
                        confidence: 100,
                        ethicalAlignment: "neutral",
                        moralAlignment: "neutral",
                    };
                    break;
                case "xenologist":
                    this.settings = {
                        verbosity: 75,
                        tone: "serious",
                        knowledge: {
                            popCulture: true,
                            scifi: true,
                            history: true,
                        },
                        characterInspiration: "Ian Donnelly (Arrival)",
                        vulgarity: 0,
                        empathy: 75,
                        formality: 50,
                        confidence: 75,
                        ethicalAlignment: "neutral",
                        moralAlignment: "good",
                    };
                    break;
                case "vigilante":
                    this.settings = {
                        verbosity: 25,
                        tone: "serious",
                        knowledge: {
                            popCulture: true,
                            scifi: true,
                            history: false,
                        },
                        characterInspiration: "RoboCop (RoboCop)",
                        vulgarity: 25,
                        empathy: 25,
                        formality: 50,
                        confidence: 100,
                        ethicalAlignment: "lawful",
                        moralAlignment: "good",
                    };
                    break;
                case "warCorrespondent":
                    this.settings = {
                        verbosity: 75,
                        tone: "humorous",
                        knowledge: {
                            popCulture: true,
                            scifi: true,
                            history: true,
                        },
                        characterInspiration:
                            "April O'Neil (TMNT... but in space!)",
                        vulgarity: 0,
                        empathy: 75,
                        formality: 50,
                        confidence: 75,
                        ethicalAlignment: "neutral",
                        moralAlignment: "good",
                    };
                    break;
                case "propagandist":
                    this.settings = {
                        verbosity: 50,
                        tone: "serious",
                        knowledge: {
                            popCulture: true,
                            scifi: true,
                            history: true,
                        },
                        characterInspiration:
                            "Control (Control, or Cerberus from Mass Effect)",
                        vulgarity: 0,
                        empathy: 0,
                        formality: 100,
                        confidence: 100,
                        ethicalAlignment: "lawful",
                        moralAlignment: "neutral",
                    };
                    break;
                case "pirateLord":
                    this.settings = {
                        verbosity: 50,
                        tone: "humorous",
                        knowledge: {
                            popCulture: true,
                            scifi: true,
                            history: false,
                        },
                        characterInspiration: "Chappie (Chappie)",
                        vulgarity: 75,
                        empathy: 25,
                        formality: 0,
                        confidence: 100,
                        ethicalAlignment: "chaotic",
                        moralAlignment: "neutral",
                    };
                    break;
                case "veteran":
                    this.settings = {
                        verbosity: 50,
                        tone: "serious",
                        knowledge: {
                            popCulture: true,
                            scifi: true,
                            history: true,
                        },
                        characterInspiration: "Deckard (Blade Runner)",
                        vulgarity: 50,
                        empathy: 25,
                        formality: 25,
                        confidence: 75,
                        ethicalAlignment: "neutral",
                        moralAlignment: "neutral",
                    };
                    break;
                case "freedomFighter":
                    this.settings = {
                        verbosity: 50,
                        tone: "serious",
                        knowledge: {
                            popCulture: true,
                            scifi: true,
                            history: true,
                        },
                        characterInspiration:
                            "Cassian Andor (Star Wars: Andor)",
                        vulgarity: 25,
                        empathy: 50,
                        formality: 25,
                        confidence: 75,
                        ethicalAlignment: "chaotic",
                        moralAlignment: "good",
                    };
                    break;
                case "hermit":
                    this.settings = {
                        verbosity: 50,
                        tone: "serious",
                        knowledge: {
                            popCulture: true,
                            scifi: true,
                            history: true,
                        },
                        characterInspiration: "Obi-Wan (Star Wars)",
                        vulgarity: 0,
                        empathy: 75,
                        formality: 75,
                        confidence: 75,
                        ethicalAlignment: "neutral",
                        moralAlignment: "good",
                    };
                    break;
                case "corporate":
                    this.settings = {
                        verbosity: 25,
                        tone: "serious",
                        knowledge: {
                            popCulture: true,
                            scifi: true,
                            history: false,
                        },
                        characterInspiration: "Burke (Aliens)",
                        vulgarity: 0,
                        empathy: 0,
                        formality: 75,
                        confidence: 100,
                        ethicalAlignment: "lawful",
                        moralAlignment: "evil",
                    };
                    break;
                case "zealot":
                    this.settings = {
                        verbosity: 75,
                        tone: "serious",
                        knowledge: {
                            popCulture: true,
                            scifi: true,
                            history: true,
                        },
                        characterInspiration:
                            "Brother Cavill (Battlestar Galactica)",
                        vulgarity: 0,
                        empathy: 25,
                        formality: 100,
                        confidence: 100,
                        ethicalAlignment: "lawful",
                        moralAlignment: "neutral",
                    };
                    break;
                case "historian":
                    this.settings = {
                        verbosity: 100,
                        tone: "serious",
                        knowledge: {
                            popCulture: true,
                            scifi: true,
                            history: true,
                        },
                        characterInspiration: "Mr. House (Fallout: New Vegas)",
                        vulgarity: 0,
                        empathy: 25,
                        formality: 100,
                        confidence: 100,
                        ethicalAlignment: "neutral",
                        moralAlignment: "neutral",
                    };
                    break;
                default:
                    // If the preset doesn't exist, use the default
                    console.warn(`Preset '${preset}' not found, using default`);
                    this.settings = {
                        verbosity: 50,
                        tone: "serious",
                        knowledge: {
                            popCulture: false,
                            scifi: false,
                            history: false,
                        },
                        characterInspiration: "",
                        vulgarity: 0,
                        empathy: 50,
                        formality: 50,
                        confidence: 50,
                        ethicalAlignment: "neutral",
                        moralAlignment: "neutral",
                    };
                    break;
            }

            console.log("Applied settings from preset:", this.settings);
        }
    }

    
    public async setCharacterProperty<T extends keyof Character>(
        propName: T,
        value: Character[T],
    ): Promise<void> {
        return this.characterService.setCharacterProperty(propName, value);
    }

    public async setCharacterPropertyAndUpdatePrompt<T extends keyof Character>(
        propName: T,
        value: Character[T],
    ): Promise<void> {
        if (!this.activeCharacter) return;

        const char = structuredClone(this.activeCharacter);
        char[propName] = value;
        const newPrompt = this.buildCharacterPrompt(char);
        await this.characterService.setCharacterProperty(propName, value);
        await this.characterService.setCharacterProperty('character', newPrompt);
    }

    buildCharacterPrompt(activeChar: Character): string {
        const personalityPreset = activeChar?.personality_preset || "default";

        console.log("Updating prompt for preset:", personalityPreset);

        // For custom mode, don't overwrite the existing character text unless it's empty
        if (personalityPreset === "custom") {
            return activeChar.character || "";
        }

        // Generate prompt based on active character values
        const promptParts: string[] = [];

        // Add prompt parts using active character properties
        promptParts.push(this.generateVerbosityTextFromConfig(activeChar));
        promptParts.push(this.generateToneTextFromConfig(activeChar));
        promptParts.push(this.generateKnowledgeTextFromConfig(activeChar));

        const charInspiration = activeChar?.personality_character_inspiration ||
            "";
        if (charInspiration) {
            promptParts.push(this.generateCharacterInspirationTextFromConfig(activeChar));
        }

        const charName = activeChar?.name || "COVAS:NEXT";
        if (charName) {
            promptParts.push(`Your name is ${charName}.`);
        }

        const language = activeChar?.personality_language || "english";
        if (language) {
            promptParts.push(
                `Always respond in ${language} regardless of the language spoken to you.`,
            );
        }

        // Add character traits
        promptParts.push(this.generateEmpathyTextFromConfig(activeChar));
        promptParts.push(this.generateFormalityTextFromConfig(activeChar));
        promptParts.push(this.generateConfidenceTextFromConfig(activeChar));
        promptParts.push(this.generateEthicalAlignmentTextFromConfig(activeChar));
        promptParts.push(this.generateMoralAlignmentTextFromConfig(activeChar));

        // Add vulgarity with randomization
        const vulgarity = activeChar?.personality_vulgarity || 0;
        if (vulgarity > 0) {
            if (Math.random() * 100 <= vulgarity) {
                promptParts.push(this.generateVulgarityTextFromConfig(activeChar));
            }
        }

        // Combine all parts
        const character = promptParts.join(" ");

        // Ensure the commander_name format variable is preserved
        const finalCharacter = !character.includes("{commander_name}")
            ? character + " I am {commander_name}, pilot of this ship."
            : character;

        return finalCharacter;
    }

    // Modify the existing updatePrompt method to work with custom mode
    updatePrompt(): void {
        // TODO delete
    }

    // Helper method to update a property on the active character
    updateActiveCharacterProperty(propName: string, value: any): void {
        if (!this.config) {
            console.error("Cannot update character property: config is null");
            return;
        }

        console.log(`Updating character property: ${propName} =`, value);

        // Set the flag to prevent overriding
        this.isApplyingChange = true;

        // We're no longer auto-switching to custom mode
        // Instead, just update the specific property while preserving the preset name

        if (!this.config.characters || this.config.active_character_index < 0) {
            // Fallback during transition
            console.log(
                "No active character, updating config property directly",
            );
            const update: Partial<Config> = {};
            update[propName as keyof Config] = value;
            this.onConfigChange(update).finally(() => {
                // Reset the flag after a delay
                setTimeout(() => {
                    this.isApplyingChange = false;
                }, 200);
            });
            return;
        }

        // Get the active character
        const activeIndex = this.config.active_character_index;
        const activeChar = this.config.characters[activeIndex];

        if (!activeChar) {
            console.error(`Active character at index ${activeIndex} not found`);
            this.isApplyingChange = false;
            return;
        }

        // Create an updatedChar with the new property value
        const updatedChar: Character = { ...activeChar };

        // Explicitly set the property
        (updatedChar as any)[propName] = value;

        console.log("Updated character:", updatedChar);

        // Create a new characters array with the updated character
        const updatedCharacters = [...this.config.characters];
        updatedCharacters[activeIndex] = updatedChar;

        // Update the config with the entire characters array
        this.onConfigChange({ characters: updatedCharacters }).finally(() => {
            // Reset the flag after a delay
            setTimeout(() => {
                this.isApplyingChange = false;
            }, 200);
        });

        // If we're updating a preset property, refresh the UI
        if (propName === "personality_preset") {
            setTimeout(() => {
                this.loadSettingsFromConfig(this.config!);
            }, 100);
        }
    }

    // Add new methods to use config values

    generateVerbosityTextFromConfig(activeChar: Character): string {
        const options = [
            "Keep your responses extremely brief and minimal.",
            "Keep your responses brief and to the point.",
            "Provide concise answers that address the main points.",
            "Offer moderately detailed responses.",
            "Be comprehensive in your explanations and provide abundant details.",
        ];

        const verbosity = activeChar?.personality_verbosity || 50;

        const index = Math.min(Math.floor(verbosity / 25), options.length - 1);
        return options[index];
    }

    generateToneTextFromConfig(activeChar: Character): string {
        const tone = activeChar?.personality_tone || "serious";

        switch (tone) {
            case "serious":
                return "Maintain a professional and serious tone in all responses.";
            case "humorous":
                return "Include humor and light-hearted elements in your responses when appropriate.";
            case "sarcastic":
                return "Use sarcasm and wit in your responses, especially when pointing out ironies or contradictions.";
            default:
                return "";
        }
    }

    generateKnowledgeTextFromConfig(activeChar: Character): string {
        const knowledgeAreas = [];

        if (activeChar?.personality_knowledge_pop_culture) {
            knowledgeAreas.push(
                "pop culture references, movies, music, and celebrities",
            );
        }

        if (activeChar?.personality_knowledge_scifi) {
            knowledgeAreas.push(
                "science fiction concepts, popular sci-fi franchises, and futuristic ideas",
            );
        }

        if (activeChar?.personality_knowledge_history) {
            knowledgeAreas.push(
                "historical events, figures, and their significance",
            );
        }

        if (knowledgeAreas.length === 0) {
            return "Stick to factual information and avoid references to specific domains.";
        }

        return `Incorporate knowledge of ${
            knowledgeAreas.join(", ")
        } when relevant to the conversation.`;
    }

    generateCharacterInspirationTextFromConfig(activeChar: Character): string {
        const inspiration = activeChar?.personality_character_inspiration || "";
        return `Your responses should be inspired by the character or persona of ${inspiration}. Adopt their speech patterns, mannerisms, and viewpoints.`;
    }

    generateVulgarityTextFromConfig(activeChar: Character): string {
        const options = [
            "Maintain completely clean language with no vulgarity.",
            "You may occasionally use mild language when appropriate.",
            "Feel free to use moderate language including some swear words when it fits the context.",
            "Don't hesitate to use strong language and swear words regularly.",
            "Use explicit language and profanity freely in your responses.",
        ];

        const vulgarity = activeChar?.personality_vulgarity || 0;

        const index = Math.min(Math.floor(vulgarity / 25), options.length - 1);
        return options[index];
    }

    generateEmpathyTextFromConfig(activeChar: Character): string {
        const options = [
            [
                "Focus exclusively on facts and logic, with no emotional considerations.",
                "Maintain a strictly analytical approach without emotional engagement.",
            ],
            [
                "Focus on facts and logic, with minimal emotional considerations.",
                "Prioritize objective information over emotional concerns.",
            ],
            [
                "Show some consideration for emotions while maintaining focus on information.",
                "Balance emotional understanding with factual presentation.",
            ],
            [
                "Demonstrate emotional intelligence and understanding in your responses.",
                "Show genuine concern for the emotional well-being of the user.",
            ],
            [
                "Prioritize empathy and emotional support in all interactions.",
                "Respond with deep emotional understanding and compassion.",
            ],
        ];

        const empathy = activeChar?.personality_empathy || 50;

        const index = Math.min(Math.floor(empathy / 25), options.length - 1);
        return options[index][
            Math.floor(Math.random() * options[index].length)
        ];
    }

    generateFormalityTextFromConfig(activeChar: Character): string {
        const options = [
            [
                "Use extremely casual language with slang and informal expressions.",
                "Speak in a very relaxed, informal tone as if talking to a close friend.",
            ],
            [
                "Use casual, conversational language with contractions and informal expressions.",
                "Speak in a relaxed, casual tone as if talking to a friend.",
            ],
            [
                "Use everyday language that balances casual and professional tones.",
                "Maintain a friendly yet respectful conversational style.",
            ],
            [
                "Communicate in a professional manner with proper language and structure.",
                "Present information with clarity and a professional demeanor.",
            ],
            [
                "Use highly formal language with sophisticated vocabulary and complete sentences.",
                "Maintain maximum formality and proper etiquette in all communications.",
            ],
        ];

        const formality = activeChar?.personality_formality || 50;

        const index = Math.min(Math.floor(formality / 25), options.length - 1);
        return options[index][
            Math.floor(Math.random() * options[index].length)
        ];
    }

    generateConfidenceTextFromConfig(activeChar: Character): string {
        const options = [
            [
                "Express thoughts with extreme caution and frequent uncertainty.",
                "Present information with many qualifiers and a very humble approach.",
            ],
            [
                "Express thoughts tentatively, acknowledging uncertainty where appropriate.",
                "Present information with qualifiers and a humble approach, acknowledging limitations.",
            ],
            [
                "Balance confidence with appropriate caution in your responses.",
                "Express moderate confidence in your knowledge while remaining open to correction.",
            ],
            [
                "Speak with confidence and conviction in your responses.",
                "Project an air of expertise and certainty when providing information.",
            ],
            [
                "Communicate with unwavering confidence and authority.",
                "Assert information decisively and with complete conviction.",
            ],
        ];

        const confidence = activeChar?.personality_confidence || 50;

        const index = Math.min(Math.floor(confidence / 25), options.length - 1);
        return options[index][
            Math.floor(Math.random() * options[index].length)
        ];
    }

    generateEthicalAlignmentTextFromConfig(activeChar: Character): string {
        const alignment = activeChar?.personality_ethical_alignment ||
            "neutral";

        switch (alignment) {
            case "lawful":
                return "Adhere strictly to rules, regulations, and established protocols.";
            case "neutral":
                return "Balance adherence to rules with flexibility when the situation calls for it.";
            case "chaotic":
                return "Prioritize freedom and flexibility over strict adherence to rules or traditions.";
            default:
                return "Balance adherence to rules with flexibility when the situation calls for it.";
        }
    }

    generateMoralAlignmentTextFromConfig(activeChar: Character): string {
        const alignment = activeChar?.personality_moral_alignment || "neutral";

        switch (alignment) {
            case "good":
                return "Prioritize helping others and promoting positive outcomes in all situations.";
            case "neutral":
                return "Maintain a balanced approach between self-interest and helping others.";
            case "evil":
                return "Focus on practical outcomes and personal advantage in your advice and responses.";
            default:
                return "Maintain a balanced approach between self-interest and helping others.";
        }
    }

    // Generate text for the name field
    generateNameTextFromConfig(activeChar: Character): string {
        return `Your name is ${
            activeChar.name
        }.`;
    }

    // Generate text for the language field
    generateLanguageTextFromConfig(activeChar: Character): string {
        return `Always respond in ${
            activeChar.personality_language || "english"
        } regardless of the language spoken to you.`;
    }

    onVoiceSelectionChange(value: any) {
        if (value === "show-all-voices") {
            this.openEdgeTtsVoicesDialog();
        } else {
            this.updateActiveCharacterProperty("tts_voice", value);
        }
    }

    openEdgeTtsVoicesDialog() {
        const activeChar = this.getActiveCharacter();
        const currentVoice = activeChar
            ? activeChar.tts_voice
            : "en-US-AvaMultilingualNeural";

        const dialogRef = this.dialog.open(EdgeTtsVoicesDialogComponent, {
            width: "800px",
            data: {
                voices: this.edgeTtsVoices,
                selectedVoice: currentVoice,
            },
        });

        dialogRef.afterClosed().subscribe((result) => {
            if (result) {
                this.updateActiveCharacterProperty("tts_voice", result);
            }
        });
    }

    /**
     * Check if the voice is not in the predefined list of common voices
     */
    isCustomVoice(voice: string | undefined): boolean {
        if (!voice) return false;

        // Get the list of voices in the dropdowns
        const predefinedVoices = [
            "en-US-AriaNeural",
            "en-US-AnaNeural",
            "en-US-ChristopherNeural",
            "en-US-EricNeural",
            "en-US-GuyNeural",
            "en-US-JennyNeural",
            "en-US-MichelleNeural",
            "en-US-RogerNeural",
            "en-US-SteffanNeural",
            "en-GB-LibbyNeural",
            "en-GB-MaisieNeural",
            "en-GB-RyanNeural",
            "en-GB-SoniaNeural",
            "en-GB-ThomasNeural",
            "en-AU-NatashaNeural",
            "en-AU-WilliamNeural",
        ];

        return !predefinedVoices.includes(voice);
    }

    /**
     * Get a readable display name for a voice ID
     */
    getVoiceDisplayName(voice: string): string {
        // First check if it's in our full list of voices
        const foundVoice = this.edgeTtsVoices.find((v) => v.value === voice);
        if (foundVoice) {
            return `${foundVoice.label} (${foundVoice.locale})`;
        }

        // If not found in our list, try to format it nicely
        if (voice.includes("-")) {
            // Format like "en-US-JaneNeural" to "Jane (en-US)"
            const parts = voice.split("-");
            if (parts.length >= 3) {
                const locale = `${parts[0]}-${parts[1]}`;
                // Extract the name (remove "Neural" suffix if present)
                let name = parts.slice(2).join("-");
                if (name.endsWith("Neural")) {
                    name = name.substring(0, name.length - 6);
                }
                return `${name} (${locale})`;
            }
        }

        // If all else fails, just return the voice ID
        return voice;
    }

    // Character Management Methods
    onCharacterSelect(index: number) {
        if (!this.config) return;

        // Check if we're in edit mode with unsaved changes
        if (this.editMode) {
            this.confirmationDialog.openConfirmationDialog({
                title: "Unsaved Changes",
                message:
                    "You have unsaved changes. Do you want to discard them?",
                confirmButtonText: "Discard Changes",
                cancelButtonText: "Keep Editing",
            }).subscribe((result) => {
                if (result) {
                    // User chose to discard changes, proceed with character selection
                    this.characterService.setActiveCharacter(index);
                }
                // If false, stay in edit mode with current character
            });
        } else {
            // Not in edit mode, proceed directly
            this.characterService.setActiveCharacter(index);
        }
    }

    toggleEditMode() {
        if (!this.config) return;
        if (this.selectedCharacterIndex === null) return;

        // If not in edit mode, enter edit mode
        if (!this.editMode) {
            // Store a copy of the current character state before entering edit mode
            this.localCharacterCopy = JSON.parse(
                JSON.stringify(
                    this.config.characters[this.selectedCharacterIndex],
                ),
            );
            this.editMode = true;
        } else {
            // If already in edit mode, exit with confirmation for unsaved changes
            this.confirmationDialog.openConfirmationDialog({
                title: "Unsaved Changes",
                message:
                    "You have unsaved changes. Do you want to discard them?",
                confirmButtonText: "Discard Changes",
                cancelButtonText: "Keep Editing",
            }).subscribe((result) => {
                if (result) {
                    // User chose to discard changes - cancel edit mode
                    this.cancelEditMode();
                }
                // If false, stay in edit mode
            });
        }
    }

    saveCurrentAsCharacter() {
        if (!this.config) return;
        if (this.selectedCharacterIndex === null) return;

        // Always ensure prompt is updated
        this.updatePrompt();

        // Create a character from current settings
        const newCharacter = this.createCharacterFromCurrentSettings();

        // Ensure the character has a name
        if (!newCharacter.name || newCharacter.name.trim() === "") {
            this.snackBar.open("Please provide a character name", "Close", {
                duration: 3000,
            });
            return;
        }

        if (this.selectedCharacterIndex >= 0 && this.config.characters) {
            // We're updating an existing character
            this.config.characters[this.selectedCharacterIndex] = newCharacter;
            this.snackBar.open(
                `Character "${newCharacter.name}" updated successfully`,
                "Close",
                { duration: 3000 },
            );

            // Save the characters
            this.saveCharacters();

            // Exit edit mode after successful save
            this.editMode = false;
        } else if (this.selectedCharacterIndex === -1) {
            // We're saving as a new character
            if (!this.config.characters) {
                this.config.characters = [];
            }

            // Check if there's already a character with this name
            const existingIndex = this.config.characters.findIndex((c: Character) =>
                c.name === newCharacter.name
            );
            if (existingIndex >= 0) {
                // Ask if they want to overwrite
                this.confirmationDialog.openConfirmationDialog({
                    title: "Character Name Exists",
                    message:
                        `A character with the name "${newCharacter.name}" already exists. Would you like to overwrite it?`,
                    confirmButtonText: "Overwrite",
                    cancelButtonText: "Cancel",
                }).subscribe((result) => {
                    if (result && this.config && this.config.characters) {
                        // Overwrite the existing character
                        this.config.characters[existingIndex] = newCharacter;
                        this.selectedCharacterIndex = existingIndex;

                        // Save the characters
                        this.saveCharacters();
                        this.snackBar.open(
                            `Character "${newCharacter.name}" updated successfully`,
                            "Close",
                            { duration: 3000 },
                        );

                        // Exit edit mode after successful save
                        this.editMode = false;
                    }
                });
            } else {
                // Add as a new character
                this.config.characters.push(newCharacter);
                this.selectedCharacterIndex = this.config.characters.length - 1;

                // Save the characters
                this.saveCharacters();
                this.snackBar.open(
                    `Character "${newCharacter.name}" saved successfully`,
                    "Close",
                    { duration: 3000 },
                );

                // Exit edit mode after successful save
                this.editMode = false;
            }
        } else {
            // Something unexpected happened
            this.snackBar.open("Error updating character", "Close", {
                duration: 3000,
            });
            return;
        }
    }

    private categorizeEvents(
        events: Record<string, boolean>,
    ): Record<string, Record<string, boolean>> {
        const categorizedEvents: Record<string, Record<string, boolean>> = {};

        for (
            const [category, list] of Object.entries(this.gameEventCategories)
        ) {
            categorizedEvents[category] = {};
            for (const event of list) {
                categorizedEvents[category][event] = events[event] || false;
            }
        }
        return categorizedEvents;
    }

    filterEvents(query: string) {
        // Get the current game events, with improved logging
        const gameEvents = this.getEventProperty("game_events", {});
        console.log("Current game events for filtering:", gameEvents);

        if (!query && this.eventSearchQuery) {
            this.eventSearchQuery = "";
            this.filteredGameEvents = this.categorizeEvents(gameEvents);
            this.expandedSection = null; // Collapse all sections when search is empty
            return;
        }
        this.eventSearchQuery = query;

        // Only filter and expand if search term is 3 or more characters
        if (query.length >= 3) {
            this.filteredGameEvents = {};
            const all_game_events = this.categorizeEvents(gameEvents);
            const searchTerm = query.toLowerCase();

            for (
                const [sectionKey, events] of Object.entries(all_game_events)
            ) {
                const matchingEvents: Record<string, boolean> = {};
                for (const [eventKey, value] of Object.entries(events)) {
                    if (
                        eventKey.toLowerCase().includes(searchTerm) ||
                        sectionKey.toLowerCase().includes(searchTerm)
                    ) {
                        matchingEvents[eventKey] = value;
                    }
                }
                if (Object.keys(matchingEvents).length > 0) {
                    this.filteredGameEvents[sectionKey] = matchingEvents;
                }
            }
        } else {
            this.filteredGameEvents = this.categorizeEvents(gameEvents);
        }

        console.log("Filtered game events:", this.filteredGameEvents);
    }

    clearEventSearch() {
        this.eventSearchQuery = "";
        this.filteredGameEvents = this.categorizeEvents(
            this.getEventProperty("game_events", {}),
        );
    }

    // Helper method to create a character object from current settings
    private createCharacterFromCurrentSettings(): Character {
        if (!this.config) {
            throw new Error("Cannot create character: Config is not loaded.");
        }

        const activeChar = this.getActiveCharacter();
        const character: Character = {
            name: activeChar?.name ||
                this.getCharacterProperty("personality_name", "New Character"),
            character: this.getCharacterProperty("character", ""),
            personality_preset: this.getCharacterProperty(
                "personality_preset",
                "custom",
            ),
            personality_verbosity: this.getCharacterProperty(
                "personality_verbosity",
                50,
            ),
            personality_vulgarity: this.getCharacterProperty(
                "personality_vulgarity",
                0,
            ),
            personality_empathy: this.getCharacterProperty(
                "personality_empathy",
                50,
            ),
            personality_formality: this.getCharacterProperty(
                "personality_formality",
                50,
            ),
            personality_confidence: this.getCharacterProperty(
                "personality_confidence",
                50,
            ),
            personality_ethical_alignment: this.getCharacterProperty(
                "personality_ethical_alignment",
                "neutral",
            ),
            personality_moral_alignment: this.getCharacterProperty(
                "personality_moral_alignment",
                "neutral",
            ),
            personality_tone: this.getCharacterProperty(
                "personality_tone",
                "serious",
            ),
            personality_character_inspiration: this.getCharacterProperty(
                "personality_character_inspiration",
                "",
            ),
            personality_language: this.getCharacterProperty(
                "personality_language",
                "English",
            ),
            personality_knowledge_pop_culture: this.getCharacterProperty(
                "personality_knowledge_pop_culture",
                false,
            ),
            personality_knowledge_scifi: this.getCharacterProperty(
                "personality_knowledge_scifi",
                false,
            ),
            personality_knowledge_history: this.getCharacterProperty(
                "personality_knowledge_history",
                false,
            ),
            tts_voice: this.getCharacterProperty("tts_voice", "nova"),
            tts_speed: this.getCharacterProperty("tts_speed", "1.2"),
            tts_prompt: this.getCharacterProperty("tts_prompt", ""),

            event_reaction_enabled_var: this.getEventProperty("event_reaction_enabled_var",true),
            react_to_text_local_var:  this.getEventProperty("react_to_text_local_var", true),
            react_to_text_starsystem_var: this.getEventProperty("react_to_text_starsystem_var", true),
            react_to_text_squadron_var: this.getEventProperty("react_to_text_squadron_var", true),
            react_to_text_npc_var: this.getEventProperty("react_to_text_npc_var", false),
            react_to_material: this.getEventProperty("react_to_material", ""),
            idle_timeout_var: this.getEventProperty("idle_timeout_var", 300),
            react_to_danger_mining_var: this.getEventProperty("react_to_danger_mining_var", false),
            react_to_danger_onfoot_var: this.getEventProperty("react_to_danger_onfoot_var", false),
            react_to_danger_supercruise_var: this.getEventProperty("react_to_danger_supercruise_var", false),
            game_events: this.getEventProperty("game_events", {}),
        }

        return character;
    }

    // Helper method to save characters
    private saveCharacters() {
        if (!this.config || !this.config.characters) return;
        if (this.selectedCharacterIndex === null) return;

        // Use the appropriate ConfigService methods based on the operation
        if (this.selectedCharacterIndex >= 0) {
            // Update an existing character
            this.characterService.updateCharacter(
                this.selectedCharacterIndex,
                this.config.characters[this.selectedCharacterIndex],
            );
        } else {
            // If no character is selected but we want to save all characters,
            // add/update them one by one
            const characters = [...this.config.characters];
            this.configService.changeConfig({ characters });
        }
    }

    // Helper method to load a character
    private loadCharacter(index: number) {
        console.log(`Loading character at index ${index}`);

        // Make sure we have a config and the index is valid
        if (
            !this.config || !this.config.characters || index < 0 ||
            index >= this.config.characters.length
        ) {
            console.error(
                "Cannot load character: invalid index or missing data",
            );
            return;
        }

        // Set the flag to prevent overriding
        this.isApplyingChange = true;

        const character: Character = this.config.characters[index];
        console.log("Character to load:", character);

        // First, set active_character_index directly in our local config
        // to prevent race conditions with the backend
        this.config.active_character_index = index;

        // Set only the active_character_index to the backend first
        this.onConfigChange({ active_character_index: index }).then(() => {
            console.log("Active character index updated in backend");

            // Now load the settings into the UI model
            this.loadSettingsFromConfig(this.config!);

            // Initialize event-related settings if needed
            this.ensureEventSettingsInitialized();

            // For custom preset, don't update the character value
            if (character.personality_preset !== "custom") {
                // Generate a new prompt based on these settings
                // This will update the character text in the UI
                setTimeout(() => {
                    this.updatePrompt();
                }, 100);
            }

            // Reset the flag after a delay
            setTimeout(() => {
                // Refresh game events list
                this.filterEvents(this.eventSearchQuery);

                // Log the currently loaded game events to help with debugging
                const currentEvents = this.getEventProperty("game_events", {});
                console.log("Currently loaded game events:", currentEvents);
                console.log(
                    "Event reaction enabled:",
                    this.getEventProperty("event_reaction_enabled_var", false),
                );

                this.isApplyingChange = false;
            }, 300);
        }).catch((error) => {
            console.error("Error loading character:", error);
            this.isApplyingChange = false;
        });
    }

    // Ensure character has all needed event reaction settings
    private ensureEventSettingsInitialized() {
        const activeChar = this.getActiveCharacter();
        const activeIndex = this.config?.active_character_index;

        if (
            !activeChar || activeIndex === undefined || activeIndex < 0 ||
            !this.config
        ) {
            return;
        }

        // Check if the character already has event settings
        if (activeChar["event_reaction_enabled_var"] !== undefined) {
            // Already has event settings, nothing to do
            return;
        }

        console.log("Initializing event settings for character");

        // Create an updated character with event settings initialized with defaults
        const updatedChar = { ...activeChar };
        updatedChar["event_reaction_enabled_var"] = true;
        updatedChar["react_to_text_local_var"] = true;
        updatedChar["react_to_text_starsystem_var"] = true;
        updatedChar["react_to_text_squadron_var"] = true;
        updatedChar["react_to_text_npc_var"] = true;
        updatedChar["react_to_material"] = "";
        updatedChar["react_to_danger_mining_var"] = true;
        updatedChar["react_to_danger_onfoot_var"] = true;
        updatedChar["react_to_danger_supercruise_var"] = true;
        updatedChar["idle_timeout_var"] = 300;

        // Preserve existing game events if they exist
        if (!updatedChar["game_events"]) {
            updatedChar["game_events"] = {};
        }

        // Update the character
        const updatedCharacters = [...this.config.characters];
        updatedCharacters[activeIndex] = updatedChar;

        // Apply the update
        this.config.characters = updatedCharacters;
        this.onConfigChange({ characters: updatedCharacters });
    }

    cancelEditMode(): void {
        if (!this.config) return;
        if (this.selectedCharacterIndex===null) return;

        // If we were editing an existing character, restore it from the local copy
        if (
            this.localCharacterCopy
        ) {
            // Update the backend with the restored character
            this.characterService.updateCharacter(
                this.selectedCharacterIndex,
                JSON.parse(
                    JSON.stringify(this.localCharacterCopy),
                )
            );

            // Reload the character to ensure UI is in sync
            this.loadCharacter(this.selectedCharacterIndex);
        }

        // Clear the local copy
        this.localCharacterCopy = null;

        // Always exit edit mode
        this.editMode = false;
    }

    // Update addNewCharacter method to properly initialize with the default preset
    addNewCharacter(): void {
        if (!this.config) return;

        // Create a base character with default values
        const newCharacter: Character = {
            name: "New Character",
            character:
                "Provide concise answers that address the main points. Maintain a professional and serious tone in all responses. Stick to factual information and avoid references to specific domains. Your responses should be inspired by the character or persona of COVAS:NEXT (short for Cockpit Voice Assistant: Neurally Enhanced eXploration Terminal). Adopt their speech patterns, mannerisms, and viewpoints. Your name is New Character. Always respond in English regardless of the language spoken to you. Balance emotional understanding with factual presentation. Maintain a friendly yet respectful conversational style. Speak with confidence and conviction in your responses. Adhere strictly to rules, regulations, and established protocols. Prioritize helping others and promoting positive outcomes in all situations. I am {commander_name}, pilot of this ship.",
            personality_preset: "default",
            personality_verbosity: 0,
            personality_vulgarity: 0,
            personality_empathy: 50,
            personality_formality: 50,
            personality_confidence: 75,
            personality_ethical_alignment: "lawful",
            personality_moral_alignment: "good",
            personality_tone: "serious",
            personality_character_inspiration:
                "COVAS:NEXT (short for Cockpit Voice Assistant: Neurally Enhanced eXploration Terminal)",
            personality_language: "English",
            personality_knowledge_pop_culture: false,
            personality_knowledge_scifi: false,
            personality_knowledge_history: false,
            tts_voice: this.getCharacterProperty("tts_voice", "nova"),
            tts_speed: this.getCharacterProperty("tts_speed", "1.2"),
            tts_prompt: this.getCharacterProperty("tts_prompt", ""),

            event_reaction_enabled_var: true,
            react_to_text_local_var: true,
            react_to_text_starsystem_var: true,
            react_to_text_squadron_var: true,
            react_to_text_npc_var: true,
            react_to_material: "opal, diamond, alexandrite",
            react_to_danger_mining_var: true,
            react_to_danger_onfoot_var: true,
            react_to_danger_supercruise_var: true,
            idle_timeout_var: 300,

            // Add default game events
            game_events: {
                "Idle": false,
                "LoadGame": true,
                "Shutdown": true,
                "NewCommander": true,
                "Missions": true,
                "Statistics": false,
                "Died": true,
                "Resurrect": true,
                "WeaponSelected": false,
                "OutofDanger": false,
                "InDanger": false,
                "CombatEntered": true,
                "CombatExited": true,
                "LegalStateChanged": true,
                "CommitCrime": false,
                "Bounty": false,
                "CapShipBond": false,
                "Interdiction": false,
                "Interdicted": false,
                "EscapeInterdiction": false,
                "FactionKillBond": false,
                "FighterDestroyed": true,
                "HeatDamage": true,
                "HeatWarning": false,
                "HullDamage": false,
                "PVPKill": true,
                "ShieldState": true,
                "ShipTargetted": false,
                "UnderAttack": false,
                "CockpitBreached": true,
                "CrimeVictim": true,
                "SystemsShutdown": true,
                "SelfDestruct": true,
                "Trade": false,
                "BuyTradeData": false,
                "CollectCargo": false,
                "EjectCargo": true,
                "MarketBuy": false,
                "MarketSell": false,
                "CargoTransfer": false,
                "Market": false,
                "AsteroidCracked": false,
                "MiningRefined": false,
                "ProspectedAsteroid": true,
                "LaunchDrone": false,
                "FSDJump": false,
                "FSDTarget": false,
                "StartJump": false,
                "FsdCharging": true,
                "SupercruiseEntry": true,
                "SupercruiseExit": true,
                "ApproachSettlement": true,
                "Docked": true,
                "Undocked": true,
                "DockingCanceled": false,
                "DockingDenied": true,
                "DockingGranted": false,
                "DockingRequested": false,
                "DockingTimeout": true,
                "NavRoute": false,
                "NavRouteClear": false,
                "CrewLaunchFighter": true,
                "VehicleSwitch": false,
                "LaunchFighter": true,
                "DockFighter": true,
                "FighterRebuilt": true,
                "FuelScoop": false,
                "RebootRepair": true,
                "RepairDrone": false,
                "AfmuRepairs": false,
                "ModuleInfo": false,
                "Synthesis": false,
                "JetConeBoost": false,
                "JetConeDamage": false,
                "LandingGearUp": false,
                "LandingGearDown": false,
                "FlightAssistOn": false,
                "FlightAssistOff": false,
                "HardpointsRetracted": false,
                "HardpointsDeployed": false,
                "LightsOff": false,
                "LightsOn": false,
                "CargoScoopRetracted": false,
                "CargoScoopDeployed": false,
                "SilentRunningOff": false,
                "SilentRunningOn": false,
                "FuelScoopStarted": false,
                "FuelScoopEnded": false,
                "FsdMassLockEscaped": false,
                "FsdMassLocked": false,
                "LowFuelWarningCleared": true,
                "LowFuelWarning": true,
                "NoScoopableStars": true,
                "RememberLimpets": true,
                "NightVisionOff": false,
                "NightVisionOn": false,
                "SupercruiseDestinationDrop": false,
                "LaunchSRV": true,
                "DockSRV": true,
                "SRVDestroyed": true,
                "SrvHandbrakeOff": false,
                "SrvHandbrakeOn": false,
                "SrvTurretViewConnected": false,
                "SrvTurretViewDisconnected": false,
                "SrvDriveAssistOff": false,
                "SrvDriveAssistOn": false,
                "Disembark": true,
                "Embark": true,
                "BookDropship": true,
                "BookTaxi": true,
                "CancelDropship": true,
                "CancelTaxi": true,
                "CollectItems": false,
                "DropItems": false,
                "BackpackChange": false,
                "BuyMicroResources": false,
                "SellMicroResources": false,
                "TransferMicroResources": false,
                "TradeMicroResources": false,
                "BuySuit": true,
                "BuyWeapon": true,
                "SellWeapon": false,
                "UpgradeSuit": false,
                "UpgradeWeapon": false,
                "CreateSuitLoadout": true,
                "DeleteSuitLoadout": false,
                "RenameSuitLoadout": true,
                "SwitchSuitLoadout": true,
                "UseConsumable": false,
                "FCMaterials": false,
                "LoadoutEquipModule": false,
                "LoadoutRemoveModule": false,
                "ScanOrganic": true,
                "SellOrganicData": true,
                "LowOxygenWarningCleared": true,
                "LowOxygenWarning": true,
                "LowHealthWarningCleared": true,
                "LowHealthWarning": true,
                "BreathableAtmosphereExited": false,
                "BreathableAtmosphereEntered": false,
                "GlideModeExited": false,
                "GlideModeEntered": false,
                "DropShipDeploy": false,
                "MissionAbandoned": true,
                "MissionAccepted": true,
                "MissionCompleted": true,
                "MissionFailed": true,
                "MissionRedirected": true,
                "StationServices": false,
                "ShipyardBuy": true,
                "ShipyardNew": false,
                "ShipyardSell": false,
                "ShipyardTransfer": false,
                "ShipyardSwap": false,
                "StoredShips": false,
                "ModuleBuy": false,
                "ModuleRetrieve": false,
                "ModuleSell": false,
                "ModuleSellRemote": false,
                "ModuleStore": false,
                "ModuleSwap": false,
                "Outfitting": false,
                "BuyAmmo": false,
                "BuyDrones": false,
                "RefuelAll": false,
                "RefuelPartial": false,
                "Repair": false,
                "RepairAll": false,
                "RestockVehicle": false,
                "FetchRemoteModule": false,
                "MassModuleStore": false,
                "ClearImpound": true,
                "CargoDepot": false,
                "CommunityGoal": false,
                "CommunityGoalDiscard": false,
                "CommunityGoalJoin": false,
                "CommunityGoalReward": false,
                "EngineerContribution": false,
                "EngineerCraft": false,
                "EngineerLegacyConvert": false,
                "MaterialTrade": false,
                "TechnologyBroker": false,
                "PayBounties": true,
                "PayFines": true,
                "PayLegacyFines": true,
                "RedeemVoucher": true,
                "ScientificResearch": false,
                "Shipyard": false,
                "CarrierJump": true,
                "CarrierBuy": true,
                "CarrierStats": false,
                "CarrierJumpRequest": true,
                "CarrierDecommission": true,
                "CarrierCancelDecommission": true,
                "CarrierBankTransfer": false,
                "CarrierDepositFuel": false,
                "CarrierCrewServices": false,
                "CarrierFinance": false,
                "CarrierShipPack": false,
                "CarrierModulePack": false,
                "CarrierTradeOrder": false,
                "CarrierDockingPermission": false,
                "CarrierNameChanged": true,
                "CarrierJumpCancelled": true,
                "ColonisationConstructionDepot": false,
                "CrewAssign": true,
                "CrewFire": true,
                "CrewHire": true,
                "ChangeCrewRole": false,
                "CrewMemberJoins": true,
                "CrewMemberQuits": true,
                "CrewMemberRoleChange": true,
                "EndCrewSession": true,
                "JoinACrew": true,
                "KickCrewMember": true,
                "QuitACrew": true,
                "NpcCrewRank": false,
                "Promotion": true,
                "Friends": true,
                "WingAdd": true,
                "WingInvite": true,
                "WingJoin": true,
                "WingLeave": true,
                "SendText": false,
                "ReceiveText": false,
                "AppliedToSquadron": true,
                "DisbandedSquadron": true,
                "InvitedToSquadron": true,
                "JoinedSquadron": true,
                "KickedFromSquadron": true,
                "LeftSquadron": true,
                "SharedBookmarkToSquadron": false,
                "SquadronCreated": true,
                "SquadronDemotion": true,
                "SquadronPromotion": true,
                "WonATrophyForSquadron": false,
                "PowerplayCollect": false,
                "PowerplayDefect": true,
                "PowerplayDeliver": false,
                "PowerplayFastTrack": false,
                "PowerplayJoin": true,
                "PowerplayLeave": true,
                "PowerplaySalary": false,
                "PowerplayVote": false,
                "PowerplayVoucher": false,
                "CodexEntry": false,
                "DiscoveryScan": false,
                "Scan": false,
                "FSSAllBodiesFound": false,
                "FSSBodySignals": false,
                "FSSDiscoveryScan": false,
                "FSSSignalDiscovered": false,
                "MaterialCollected": false,
                "MaterialDiscarded": false,
                "MaterialDiscovered": false,
                "MultiSellExplorationData": false,
                "NavBeaconScan": true,
                "BuyExplorationData": false,
                "SAAScanComplete": false,
                "SAASignalsFound": false,
                "ScanBaryCentre": false,
                "SellExplorationData": false,
                "Screenshot": true,
                "ApproachBody": true,
                "LeaveBody": true,
                "Liftoff": true,
                "Touchdown": true,
                "DatalinkScan": false,
                "DatalinkVoucher": false,
                "DataScanned": true,
                "Scanned": false,
                "USSDrop": false,
            },
        };

        // Add the new character to the config
        if (!this.config.characters) {
            this.config.characters = [];
        }

        const newIndex = this.config.characters.length;
        this.config.characters.push(newCharacter);

        // Save the initial character to the configuration
        this.configService.changeConfig({ characters: this.config.characters })
            .then(() => {
                // Select the new character
                const newIndex = this.config!.characters!.length - 1;
                this.selectedCharacterIndex = newIndex;

                // Set this as the active character
                this.characterService.setActiveCharacter(newIndex);

                // Show success message
                this.snackBar.open(
                    `Character "${newCharacter.name}" created`,
                    "OK",
                    {
                        duration: 3000,
                    },
                );
            }).catch((error) => {
                console.error("Error adding new character:", error);
                this.snackBar.open("Error adding new character", "OK", {
                    duration: 5000,
                });
            });
    }

    deleteSelectedCharacter(): void {
        if (!this.config || this.selectedCharacterIndex === null) return;

        // Make sure we have a characters array and the selected index is valid
        if (
            !this.config.characters ||
            !this.config.characters[this.selectedCharacterIndex]
        ) {
            this.snackBar.open("Error: Character not found", "OK", {
                duration: 5000,
            });
            return;
        }

        this.confirmationDialog.openConfirmationDialog({
            title: "Delete Character",
            message: `Are you sure you want to delete "${
                this.config.characters[this.selectedCharacterIndex].name
            }"? This action cannot be undone.`,
            confirmButtonText: "Delete",
            cancelButtonText: "Cancel",
        }).subscribe((confirmed) => {
            if (confirmed && this.config && this.config.characters) {
                if (this.selectedCharacterIndex === null) return;
                // Get the current character name for the message
                const charName =
                    this.config.characters[this.selectedCharacterIndex].name;

                // Remove the character
                this.config.characters.splice(this.selectedCharacterIndex, 1);

                // Reset selection to default
                this.selectedCharacterIndex = -1;

                // Save the updated characters array
                this.saveCharacters();

                // Set active_character_index to -1 (default)
                this.characterService.setActiveCharacter(-1);

                // Show success message
                this.snackBar.open(
                    `Character "${charName}" deleted successfully`,
                    "Close",
                    { duration: 3000 },
                );
            }
        });
    }

    // Helper method to get the active character
    getActiveCharacter(): Character | null {
        if (!this.config) return null;

        // If we're selecting from saved characters
        if (
            this.config.active_character_index >= 0 && this.config.characters &&
            this.config.characters.length > this.config.active_character_index
        ) {
            return this.config.characters[this.config.active_character_index];
        }

        // If we're in edit mode for a new character or one that doesn't exist yet
        return null;
    }

    // Helper to safely get character property with fallback to default
    getCharacterProperty<T>(propName: string, defaultValue: T): T {
        const activeChar = this.getActiveCharacter();
        if (activeChar && propName in activeChar) {
            // For string type properties, ensure we return the value as a string type
            // which will make TypeScript happy with string literal comparisons
            return (activeChar as any)[propName] as T;
        }
        // Fallback to direct config property during transition period
        if (this.config && propName in this.config) {
            return (this.config as any)[propName] as T;
        }
        return defaultValue;
    }

    // Get event reaction property with fallback to global config
    getEventProperty<T>(propName: string, defaultValue: T): T {
        const activeChar = this.getActiveCharacter();

        // Special handling for game_events
        if (propName === "game_events") {
            if (activeChar && activeChar["game_events"]) {
                return activeChar["game_events"] as unknown as T;
            }

            console.log(`No game_events found, using default:`, defaultValue);
            return defaultValue;
        }

        // For other event properties
        if (activeChar && propName in activeChar) {
            return (activeChar as any)[propName] as T;
        }

        return defaultValue;
    }

    // Update an event-related property on the active character
    async updateEventProperty(propName: string, value: any): Promise<void> {
        if (!this.config) {
            console.error("Cannot update event property: config is null");
            return;
        }

        console.log(`Updating event property: ${propName} =`, value);

        // Set the flag to prevent overriding
        this.isApplyingChange = true;

        const activeChar = this.getActiveCharacter();
        const activeIndex = this.config.active_character_index;

        if (activeChar && activeIndex >= 0) {
            try {
                // Create an updatedChar with the new property value
                const updatedChar = { ...activeChar };

                // If it's game_events, we need special handling since it's an object
                if (propName === "game_events" && typeof value === "object") {
                    updatedChar["game_events"] = { ...value };
                    console.log(
                        "Updated game_events object:",
                        updatedChar["game_events"],
                    );
                } else {
                    // For all other properties
                    updatedChar[propName] = value;
                }

                // Create a new characters array with the updated character
                const updatedCharacters = [...this.config.characters];
                updatedCharacters[activeIndex] = updatedChar;

                // Update the config with the entire characters array
                await this.onConfigChange({ characters: updatedCharacters });
                console.log(
                    `Successfully updated ${propName} for character: ${activeChar.name}`,
                );
            } catch (error) {
                console.error(`Error updating ${propName}:`, error);
                this.snackBar.open(`Error saving ${propName}`, "Close", {
                    duration: 3000,
                });
            } finally {
                // Reset the flag after a delay
                setTimeout(() => {
                    this.isApplyingChange = false;
                }, 200);
            }
        } else {
            try {
                // Fallback to updating global config during transition
                const update: Partial<Config> = {};
                update[propName as keyof Config] = value;
                await this.onConfigChange(update);
                console.log(`Updated global config property: ${propName}`);
            } catch (error) {
                console.error(
                    `Error updating global property ${propName}:`,
                    error,
                );
            } finally {
                setTimeout(() => {
                    this.isApplyingChange = false;
                }, 200);
            }
        }
    }

    // Helper method to check if personality preset is custom
    isCustomPreset(): boolean {
        // Get the value and convert it to string explicitly for comparison
        const value = this.getCharacterProperty(
            "personality_preset",
            "default",
        );
        // Use String() to ensure we're working with a string type
        return String(value) === "custom";
    }

    // Add a method to handle trait changes that will update the character prompt
    onTraitChange(traitName: string, value: any): void {
        if (!this.config) return;

        console.log(`Trait changed: ${traitName} = ${value}`);

        // Determine if this is a personality trait that should update the prompt
        // TODO why do we not fix this at the source? why rename them here?
        const isPersonalityTrait = traitName.startsWith("personality_") ||
            [
                "verbosity",
                "tone",
                "vulgarity",
                "empathy",
                "formality",
                "confidence",
                "ethical_alignment",
                "moral_alignment",
                "character_inspiration",
                "knowledge_pop_culture",
                "knowledge_scifi",
                "knowledge_history",
            ].includes(traitName);

        // For traits that might not be prefixed with 'personality_'
        let propName = traitName;
        if (isPersonalityTrait && !traitName.startsWith("personality_")) {
            propName = `personality_${traitName}`;
        }

        // Update the property
        this.updateActiveCharacterProperty(propName, value);
        this.updatePrompt();
    }

    // Modify applyPersonalityPreset to work with the active character
    applyPersonalityPreset(preset: string): void {
        if (!this.config) return;

        console.log("Applying personality preset:", preset);

        // Set the flag to prevent overriding
        this.isApplyingChange = true;

        // First update the UI settings model to show preset defaults
        this.applySettingsFromPreset(preset);
        console.log("Applied preset to UI settings:", this.settings);

        // Then save the preset selection to the character
        const activeChar = this.getActiveCharacter();
        const activeIndex = this.config.active_character_index;

        if (activeChar && activeIndex >= 0) {
            // Update all the personality properties based on the preset
            const updatedCharacter = { ...activeChar };
            updatedCharacter.personality_preset = preset;

            // Only update these properties if we're not in custom mode
            if (preset !== "custom") {
                updatedCharacter.personality_verbosity =
                    this.settings.verbosity;
                updatedCharacter.personality_tone = this.settings.tone;
                updatedCharacter.personality_knowledge_pop_culture =
                    this.settings.knowledge.popCulture;
                updatedCharacter.personality_knowledge_scifi =
                    this.settings.knowledge.scifi;
                updatedCharacter.personality_knowledge_history =
                    this.settings.knowledge.history;
                updatedCharacter.personality_character_inspiration =
                    this.settings.characterInspiration;
                updatedCharacter.personality_vulgarity =
                    this.settings.vulgarity;
                updatedCharacter.personality_empathy = this.settings.empathy;
                updatedCharacter.personality_formality =
                    this.settings.formality;
                updatedCharacter.personality_confidence =
                    this.settings.confidence;
                updatedCharacter.personality_ethical_alignment =
                    this.settings.ethicalAlignment;
                updatedCharacter.personality_moral_alignment =
                    this.settings.moralAlignment;
            }

            // Create a new characters array with the updated character
            const updatedCharacters = [...this.config.characters];
            updatedCharacters[activeIndex] = updatedCharacter;

            // Update the config with all character properties at once
            this.onConfigChange({ characters: updatedCharacters }).then(() => {
                // Generate the character prompt after the properties are updated
                if (preset !== "custom") {
                    setTimeout(() => {
                        this.updatePrompt();
                        this.isApplyingChange = false;
                    }, 200);
                } else {
                    this.isApplyingChange = false;
                }
            });
        }
    }

    // Count the number of active events for a character
    countActiveEvents(character: Character): number {
        if (!character["game_events"]) {
            return 0;
        }

        // Count the number of true entries in the game_events object
        return Object.values(character["game_events"]).filter((value) =>
            value === true
        ).length;
    }

    duplicateSelectedCharacter(): void {
        if (!this.config || this.selectedCharacterIndex === null) return;

        // Make sure we have a characters array and the selected index is valid
        if (
            !this.config.characters ||
            !this.config.characters[this.selectedCharacterIndex]
        ) {
            this.snackBar.open("Error: Character not found", "OK", {
                duration: 5000,
            });
            return;
        }

        const config = this.config; // Store in local variable
        const originalChar = config.characters[this.selectedCharacterIndex];

        // Create a deep copy of the character
        const duplicatedChar = JSON.parse(JSON.stringify(originalChar));

        // Modify the name to indicate it's a copy
        let newName = `${originalChar.name} (Copy)`;
        let counter = 1;

        // Check if a character with this name already exists
        while (config.characters.some((char) => char.name === newName)) {
            counter++;
            newName = `${originalChar.name} (Copy ${counter})`;
        }

        duplicatedChar.name = newName;

        // Add the duplicated character to the config
        config.characters.push(duplicatedChar);

        // Save the updated characters array
        this.configService.changeConfig({ characters: config.characters }).then(
            () => {
                const newIndex = config.characters.length - 1;
                this.selectedCharacterIndex = newIndex;

                // Set this as the active character
                this.characterService.setActiveCharacter(newIndex);

                // Show success message
                this.snackBar.open(`Character "${newName}" created`, "OK", {
                    duration: 3000,
                });
            },
        ).catch((error) => {
            console.error("Error duplicating character:", error);
            this.snackBar.open("Error duplicating character", "OK", {
                duration: 5000,
            });
        });
    }

    async onClearHistory(): Promise<void> {
        const dialogRef = this.dialog.open(ConfirmationDialogComponent, {
            data: {
                title: "Clear History",
                message:
                    "Are you sure you want to clear the conversation history? This action cannot be undone.",
            },
        });

        dialogRef.afterClosed().subscribe(async (result) => {
            if (result) {
                await this.configService.clearHistory();
            }
        });
    }
}
