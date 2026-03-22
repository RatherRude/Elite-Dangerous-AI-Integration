import { Component } from "@angular/core";
import { CommonModule } from "@angular/common";
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
import { ConfirmationDialogService } from "../../services/confirmation-dialog.service.js";
import { MatDialog } from "@angular/material/dialog";
import { EdgeTtsVoicesDialogComponent } from "../edge-tts-voices-dialog/edge-tts-voices-dialog.component.js";
import { ConfirmationDialogComponent } from "../confirmation-dialog/confirmation-dialog.component.js";
import { AvatarCatalogDialogComponent, AvatarCatalogResult } from "../avatar-catalog-dialog/avatar-catalog-dialog.component.js";
import { MatTooltipModule } from "@angular/material/tooltip";
import { MatDivider } from "@angular/material/divider";
import { MatInputModule } from "@angular/material/input";
import { MatButtonModule } from "@angular/material/button";
import { CharacterService, ConfigWithCharacters, Character } from "../../services/character.service";
import { MatCheckboxModule } from "@angular/material/checkbox";
import { CharacterPresets } from "./character-presets";

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
        MatDivider,
        MatOptgroup,
        MatTooltipModule,
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
    isApplyingChange: boolean = false;
    voiceInstructionSupportedModels: string[] = this.characterService.voiceInstructionSupportedModels;

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

    // Modify applySettingsFromPreset to work with the new approach
    applySettingsFromPreset(preset: string): void {
        if (!this.activeCharacter) return;
        if (!this.selectedCharacterIndex) return;
        console.log("Applying settings from preset:", preset);

        const changes = CharacterPresets[preset];
        
        const newChar: Character = {
            ...this.activeCharacter,
            ...changes,
            personality_preset: preset,
        };

        console.log('newChar', newChar)

        newChar.character = this.buildCharacterPrompt(newChar);

        this.characterService.updateCharacter(this.selectedCharacterIndex, newChar)
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
        const vulgarity = activeChar?.personality_vulgarity ?? 0;
        if (vulgarity > 0) {
            promptParts.push(this.generateVulgarityTextFromConfig(activeChar));
        }

        // Combine all parts
        const character = promptParts.join(" ");

        // Ensure the commander_name format variable is preserved
        const finalCharacter = !character.includes("{commander_name}")
            ? character + " I am {commander_name}, pilot of this ship."
            : character;

        return finalCharacter;
    }

    generateVerbosityTextFromConfig(activeChar: Character): string {
        const options = [
            "Keep your responses extremely brief and minimal.",
            "Keep your responses brief and to the point.",
            "Provide concise answers that address the main points.",
            "Offer moderately detailed responses.",
            "Be comprehensive in your explanations and provide abundant details.",
        ];

        const verbosity = activeChar?.personality_verbosity ?? 0;

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
            return "Stick to factual information.";
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

        const vulgarity = activeChar?.personality_vulgarity ?? 0;

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

        const empathy = activeChar?.personality_empathy ?? 0;

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

        const formality = activeChar?.personality_formality ?? 0;

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

        const confidence = activeChar?.personality_confidence ?? 0;

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
            this.setCharacterProperty("tts_voice", value);
        }
    }

    openEdgeTtsVoicesDialog() {
        const currentVoice = this.activeCharacter?.tts_voice ?? "en-US-AvaMultilingualNeural";

        const dialogRef = this.dialog.open(EdgeTtsVoicesDialogComponent, {
            width: "800px",
            data: {
                voices: this.edgeTtsVoices,
                selectedVoice: currentVoice,
            },
        });

        dialogRef.afterClosed().subscribe((result) => {
            if (result) {
                this.setCharacterProperty("tts_voice", result);
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

    // Helper method to save characters
    public saveCharacters() {
        if (!this.config || !this.config.characters) return;
        if (this.selectedCharacterIndex === null) return;

        // actually its all saved already, all we need it to clear the local backup

        this.localCharacterCopy = null;
        this.editMode = false;
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
        }

        // Clear the local copy
        this.localCharacterCopy = null;

        // Always exit edit mode
        this.editMode = false;
    }

    // Update addNewCharacter method to properly initialize with the default preset
    addNewCharacter(): void {
        if (!this.config) return;

        this.characterService.addDefaultCharacter()
    }

    deleteSelectedCharacter(): void {
        if (!this.config || this.selectedCharacterIndex === null) return;

        // default cannot be deleted
        if (this.selectedCharacterIndex === 0) return;

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

                this.characterService.deleteCharacter(this.selectedCharacterIndex);

                // Show success message
                this.snackBar.open(
                    `Character deleted successfully`,
                    "Close",
                    { duration: 3000 },
                );
            }
        });
    }

    // Helper to safely get character property with fallback to default
    getCharacterProperty<T extends keyof Character>(
        propName: T,
        defaultValue: Character[T],
    ): Character[T] {
        if (!this.config) return defaultValue;
        if (!this.activeCharacter) return defaultValue;
        // Use optional chaining to safely access the property
        return this.activeCharacter[propName] ?? defaultValue;
    }

    // Helper method to check if personality preset is custom
    isCustomPreset(): boolean {
        // Get the value and convert it to string explicitly for comparison
        const value = this.getCharacterProperty(
            "personality_preset",
            "default",
        );
        // Use String() to ensure we're working with a string type
        return value === "custom";
    }


    // Count the number of active events for a character
    countActiveEvents(character: Character): number {
        if (!character["event_reactions"]) {
            return 0;
        }

        return Object.values(character["event_reactions"]).filter((value) =>
            value === "on"
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

    // Avatar-related methods
    async loadCharacterAvatar() {
        // This method is now handled by the character service
        // We can remove this implementation as the service handles it automatically
    }

    getAvatarUrl(): string {
        return this.characterService.getAvatarUrl();
    }

    openAvatarCatalog() {
        const dialogRef = this.dialog.open(AvatarCatalogDialogComponent, {
            width: '850px',
            maxWidth: '95vw',
            data: { currentAvatarId: this.activeCharacter?.avatar }
        });

        dialogRef.afterClosed().subscribe((result: AvatarCatalogResult) => {
            if (result !== undefined && this.activeCharacter) {
                this.setCharacterProperty('avatar', result.avatarId);
                // The character service will automatically reload the avatar
            }
        });
    }

    // Enable custom character editor with confirmation
    enableCustomCharacterEditor() {
        if (!this.activeCharacter) return;

        const dialogRef = this.confirmationDialog.openConfirmationDialog({
            title: "Enable Custom Prompt",
            message: "This will allow you to write your own character prompt. This action cannot be undone - you will need to create a new character to use presets again. Are you sure you want to continue?",
            confirmButtonText: "Understood",
            cancelButtonText: "Cancel",
        });

        dialogRef.subscribe((result: boolean) => {
            if (result) {
                // Enable custom character editor mode
                this.applySettingsFromPreset('custom');
                this.snackBar.open('Custom character editor enabled', 'OK', {
                    duration: 3000,
                });
            }
        });
    }

    // Randomize character preset
    randomizePreset() {
        if (!this.activeCharacter) return;

        // Get all available presets except 'custom'
        const availablePresets = Object.keys(CharacterPresets).filter(
            preset => preset !== 'custom'
        );

        if (availablePresets.length === 0) return;

        // Pick a random preset
        const randomIndex = Math.floor(Math.random() * availablePresets.length);
        const randomPreset = availablePresets[randomIndex];

        // Apply the random preset
        this.applySettingsFromPreset(randomPreset);

        // Show notification to user
        this.snackBar.open('Random personality preset applied!', 'OK', {
            duration: 2000,
        });
    }

    // Handle character inspiration contenteditable change
    onCharacterInspirationChange(event: Event) {
        const target = event.target as HTMLElement;
        const newValue = target.textContent || '';
        this.setCharacterPropertyAndUpdatePrompt('personality_character_inspiration', newValue);
    }
}
