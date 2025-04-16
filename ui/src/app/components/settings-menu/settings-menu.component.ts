import { Component, OnDestroy, OnInit } from "@angular/core";
import { MatCardModule } from "@angular/material/card";
import { MatTabsModule } from "@angular/material/tabs";
import { MatIconModule } from "@angular/material/icon";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatSelectModule } from "@angular/material/select";
import { MatSlideToggleModule } from "@angular/material/slide-toggle";
import { FormsModule } from "@angular/forms";
import {
  Config,
  ConfigService,
  SystemInfo,
} from "../../services/config.service";
import { Subscription } from "rxjs";
import { MatButtonModule } from "@angular/material/button";
import { KeyValue, KeyValuePipe } from "@angular/common";
import { MatExpansionModule } from "@angular/material/expansion";
import { MatSnackBar, MatSnackBarModule } from "@angular/material/snack-bar";
import { CommonModule } from "@angular/common";
import { GameEventCategories } from "./game-event-categories.js";
import { MatDividerModule } from "@angular/material/divider";
import { MatCheckboxModule } from "@angular/material/checkbox";
import { MatDialog } from '@angular/material/dialog';
import { EdgeTtsVoicesDialogComponent } from '../edge-tts-voices-dialog';

interface PromptSettings {
  // Existing settings
  verbosity: number;
  tone: 'serious' | 'humorous' | 'sarcastic';
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
  ethicalAlignment: 'lawful' | 'neutral' | 'chaotic';
  moralAlignment: 'good' | 'neutral' | 'evil';
}

@Component({
  selector: "app-settings-menu",
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatTabsModule,
    MatIconModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatSlideToggleModule,
    MatButtonModule,
    FormsModule,
    KeyValuePipe,
    MatExpansionModule,
    MatSnackBarModule,
    MatDividerModule,
    MatCheckboxModule,
  ],
  templateUrl: "./settings-menu.component.html",
  styleUrl: "./settings-menu.component.css",
})
export class SettingsMenuComponent implements OnInit, OnDestroy {
  config: Config | null = null;
  system: SystemInfo | null = null;
  hideApiKey = true;
  apiKeyType: string | null = null;
  private configSubscription?: Subscription;
  private systemSubscription?: Subscription;
  private validationSubscription?: Subscription;
  expandedSection: string | null = null;
  filteredGameEvents: Record<string, Record<string, boolean>> = {};
  eventSearchQuery: string = "";

  gameEventCategories = GameEventCategories;
  settings: PromptSettings = {
    // Existing defaults
    verbosity: 50,
    tone: 'serious',
    knowledge: {
      popCulture: false,
      scifi: false,
      history: false
    },
    characterInspiration: '',
    vulgarity: 0,
    
    // New defaults
    empathy: 50,
    formality: 50,
    confidence: 50,
    ethicalAlignment: 'neutral',
    moralAlignment: 'neutral',
  };

  private initializing = true;

  edgeTtsVoices = [
    // English voices
    { value: 'en-US-AriaNeural', label: 'Aria (Female) - Positive, Confident', locale: 'en-US' },
    { value: 'en-US-AnaNeural', label: 'Ana (Female) - Cute', locale: 'en-US' },
    { value: 'en-US-ChristopherNeural', label: 'Christopher (Male) - Reliable, Authority', locale: 'en-US' },
    { value: 'en-US-EricNeural', label: 'Eric (Male) - Rational', locale: 'en-US' },
    { value: 'en-US-GuyNeural', label: 'Guy (Male) - Passion', locale: 'en-US' },
    { value: 'en-US-JennyNeural', label: 'Jenny (Female) - Friendly, Considerate', locale: 'en-US' },
    { value: 'en-US-MichelleNeural', label: 'Michelle (Female) - Friendly, Pleasant', locale: 'en-US' },
    { value: 'en-US-RogerNeural', label: 'Roger (Male) - Lively', locale: 'en-US' },
    { value: 'en-US-SteffanNeural', label: 'Steffan (Male) - Rational', locale: 'en-US' },
    { value: 'en-GB-LibbyNeural', label: 'Libby (Female)', locale: 'en-GB' },
    { value: 'en-GB-MaisieNeural', label: 'Maisie (Female)', locale: 'en-GB' },
    { value: 'en-GB-RyanNeural', label: 'Ryan (Male)', locale: 'en-GB' },
    { value: 'en-GB-SoniaNeural', label: 'Sonia (Female)', locale: 'en-GB' },
    { value: 'en-GB-ThomasNeural', label: 'Thomas (Male)', locale: 'en-GB' },
    { value: 'en-AU-NatashaNeural', label: 'Natasha (Female)', locale: 'en-AU' },
    { value: 'en-AU-WilliamNeural', label: 'William (Male)', locale: 'en-AU' },
    { value: 'en-CA-ClaraNeural', label: 'Clara (Female)', locale: 'en-CA' },
    { value: 'en-CA-LiamNeural', label: 'Liam (Male)', locale: 'en-CA' },
    { value: 'en-IE-ConnorNeural', label: 'Connor (Male)', locale: 'en-IE' },
    { value: 'en-IE-EmilyNeural', label: 'Emily (Female)', locale: 'en-IE' },
    { value: 'en-IN-NeerjaNeural', label: 'Neerja (Female)', locale: 'en-IN' },
    { value: 'en-IN-PrabhatNeural', label: 'Prabhat (Male)', locale: 'en-IN' },
    { value: 'en-NZ-MitchellNeural', label: 'Mitchell (Male)', locale: 'en-NZ' },
    { value: 'en-NZ-MollyNeural', label: 'Molly (Female)', locale: 'en-NZ' },
    { value: 'en-ZA-LeahNeural', label: 'Leah (Female)', locale: 'en-ZA' },
    { value: 'en-ZA-LukeNeural', label: 'Luke (Male)', locale: 'en-ZA' },
    
    // French voices
    { value: 'fr-FR-DeniseNeural', label: 'Denise (Female)', locale: 'fr-FR' },
    { value: 'fr-FR-EloiseNeural', label: 'Eloise (Female)', locale: 'fr-FR' },
    { value: 'fr-FR-HenriNeural', label: 'Henri (Male)', locale: 'fr-FR' },
    { value: 'fr-CA-AntoineNeural', label: 'Antoine (Male)', locale: 'fr-CA' },
    { value: 'fr-CA-JeanNeural', label: 'Jean (Male)', locale: 'fr-CA' },
    { value: 'fr-CA-SylvieNeural', label: 'Sylvie (Female)', locale: 'fr-CA' },
    
    // German voices
    { value: 'de-DE-AmalaNeural', label: 'Amala (Female)', locale: 'de-DE' },
    { value: 'de-DE-ConradNeural', label: 'Conrad (Male)', locale: 'de-DE' },
    { value: 'de-DE-KatjaNeural', label: 'Katja (Female)', locale: 'de-DE' },
    { value: 'de-DE-KillianNeural', label: 'Killian (Male)', locale: 'de-DE' },
    
    // Spanish voices
    { value: 'es-ES-AlvaroNeural', label: 'Alvaro (Male)', locale: 'es-ES' },
    { value: 'es-ES-ElviraNeural', label: 'Elvira (Female)', locale: 'es-ES' },
    { value: 'es-MX-DaliaNeural', label: 'Dalia (Female)', locale: 'es-MX' },
    { value: 'es-MX-JorgeNeural', label: 'Jorge (Male)', locale: 'es-MX' },
    
    // Russian voices
    { value: 'ru-RU-DmitryNeural', label: 'Dmitry (Male)', locale: 'ru-RU' },
    { value: 'ru-RU-SvetlanaNeural', label: 'Svetlana (Female)', locale: 'ru-RU' },
    
    // Italian voices
    { value: 'it-IT-DiegoNeural', label: 'Diego (Male)', locale: 'it-IT' },
    { value: 'it-IT-ElsaNeural', label: 'Elsa (Female)', locale: 'it-IT' },
    { value: 'it-IT-IsabellaNeural', label: 'Isabella (Female)', locale: 'it-IT' },
    
    // Japanese voices
    { value: 'ja-JP-KeitaNeural', label: 'Keita (Male)', locale: 'ja-JP' },
    { value: 'ja-JP-NanamiNeural', label: 'Nanami (Female)', locale: 'ja-JP' },
    
    // Portuguese voices
    { value: 'pt-BR-AntonioNeural', label: 'Antonio (Male)', locale: 'pt-BR' },
    { value: 'pt-BR-FranciscaNeural', label: 'Francisca (Female)', locale: 'pt-BR' },
    { value: 'pt-PT-DuarteNeural', label: 'Duarte (Male)', locale: 'pt-PT' },
    { value: 'pt-PT-RaquelNeural', label: 'Raquel (Female)', locale: 'pt-PT' },
    
    // Chinese voices
    { value: 'zh-CN-XiaoxiaoNeural', label: 'Xiaoxiao (Female) - Warm', locale: 'zh-CN' },
    { value: 'zh-CN-YunyangNeural', label: 'Yunyang (Male) - Professional', locale: 'zh-CN' },
    { value: 'zh-TW-HsiaoChenNeural', label: 'HsiaoChen (Female)', locale: 'zh-TW' },
    { value: 'zh-TW-YunJheNeural', label: 'YunJhe (Male)', locale: 'zh-TW' },
    
    // Arabic voices
    { value: 'ar-SA-HamedNeural', label: 'Hamed (Male)', locale: 'ar-SA' },
    { value: 'ar-SA-ZariyahNeural', label: 'Zariyah (Female)', locale: 'ar-SA' },
    
    // Hindi voices
    { value: 'hi-IN-MadhurNeural', label: 'Madhur (Male)', locale: 'hi-IN' },
    { value: 'hi-IN-SwaraNeural', label: 'Swara (Female)', locale: 'hi-IN' },
    
    // Korean voices
    { value: 'ko-KR-InJoonNeural', label: 'InJoon (Male)', locale: 'ko-KR' },
    { value: 'ko-KR-SunHiNeural', label: 'SunHi (Female)', locale: 'ko-KR' }
  ];

  constructor(
    private configService: ConfigService,
    private snackBar: MatSnackBar,
    private dialog: MatDialog
  ) {}

  // Comparator function to ensure consistent ordering
  orderByKey = (a: KeyValue<string, any>, b: KeyValue<string, any>): number => {
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

  ngOnInit() {
    this.configSubscription = this.configService.config$.subscribe(
      (config) => {
        this.config = config;

        if (config) {
          // Initial setup
          if (this.initializing) {
            // If personality_preset isn't set, default to "default"
            if (!config.personality_preset) {
              this.onConfigChange({personality_preset: 'default'});
            } else {
              // Apply the saved preset to initialize settings without saving to config
              this.loadSettingsFromConfig(config);
            }
            this.initializing = false;
          }

          this.filterEvents(this.eventSearchQuery);
        }
      },
    );

    this.systemSubscription = this.configService.system$
      .subscribe(
        (system) => {
          this.system = system;
        },
      );

    this.validationSubscription = this.configService.validation$
      .subscribe((validation) => {
        if (validation) {
          // Show snackbar for validation messages
          const snackBarDuration = validation.success ? 3000 : 6000;
          const snackBarClass = validation.success
            ? "validation-success-snackbar"
            : "validation-error-snackbar";

          this.snackBar.open(validation.message, "Dismiss", {
            duration: snackBarDuration,
            horizontalPosition: "left",
            verticalPosition: "bottom",
            panelClass: snackBarClass,
          });
        }
      });
  }

  ngOnDestroy() {
    if (this.configSubscription) {
      this.configSubscription.unsubscribe();
    }
    if (this.systemSubscription) {
      this.systemSubscription.unsubscribe();
    }
    if (this.validationSubscription) {
      this.validationSubscription.unsubscribe();
    }
  }

  async onConfigChange(partialConfig: Partial<Config>) {
    if (this.config) {
      await this.configService.changeConfig(partialConfig);
    }
  }
  async onEventConfigChange(section: string, event: string, enabled: boolean) {
    if (this.config) {
      console.log("onEventConfigChange", section, event, enabled);
      await this.configService.changeEventConfig(section, event, enabled);
    }
  }

  async onAssignPTT() {
    await this.configService.assignPTT();
  }

  private categorizeEvents(
    events: Record<string, boolean>,
  ): Record<string, Record<string, boolean>> {
    const categorizedEvents: Record<string, Record<string, boolean>> = {};

    for (const [category, list] of Object.entries(this.gameEventCategories)) {
      categorizedEvents[category] = {};
      for (const event of list) {
        categorizedEvents[category][event] = events[event] || false;
      }
    }
    return categorizedEvents;
  }

  filterEvents(query: string) {
    if (!query && this.eventSearchQuery) {
      this.eventSearchQuery = "";
      this.filteredGameEvents = this.categorizeEvents(
        this.config?.game_events || {},
      );
      this.expandedSection = null; // Collapse all sections when search is empty
      return;
    }
    this.eventSearchQuery = query;

    // Only filter and expand if search term is 3 or more characters
    if (query.length >= 3) {
      this.filteredGameEvents = {};
      const all_game_events = this.categorizeEvents(
        this.config?.game_events || {},
      );
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
      this.filteredGameEvents = this.categorizeEvents(
        this.config?.game_events || {},
      );
    }
  }

  clearEventSearch() {
    this.eventSearchQuery = "";
    this.filteredGameEvents = this.categorizeEvents(
      this.config?.game_events || {},
    );
    this.expandedSection = null; // Collapse all sections when search is cleared
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
    if (this.config) {
      const materialsString = selectedMaterials.join(", ");
      await this.onConfigChange({ react_to_material: materialsString });
    }
  }

  async onApiKeyChange(apiKey: string) {
    if (!this.config) return;
    
    // Update the API key in config first
    await this.onConfigChange({ api_key: apiKey });
    
    // Detect API key type
    let providerChanges: Partial<Config> = {};
    
    if (apiKey.startsWith('AIzaS')) {
      // Google AI Studio
      this.apiKeyType = 'Google AI Studio';
      providerChanges = {
        llm_provider: 'google-ai-studio',
        stt_provider: 'google-ai-studio',
        vision_provider: 'google-ai-studio',
        tts_provider: 'edge-tts',
        vision_var: true
      };
    } else if (apiKey.startsWith('sk-or-v1')) {
      // OpenRouter
      this.apiKeyType = 'OpenRouter';
      providerChanges = {
        llm_provider: 'openrouter',
        stt_provider: 'none',
        vision_provider: 'none',
        tts_provider: 'edge-tts',
        vision_var: false
      };
    } else if (apiKey.startsWith('sk-')) {
      // OpenAI
      this.apiKeyType = 'OpenAI';
      providerChanges = {
        llm_provider: 'openai',
        stt_provider: 'openai',
        vision_provider: 'openai',
        tts_provider: 'edge-tts',
        vision_var: true
      };
    } else {
      // Unknown key type
      this.apiKeyType = null;
      return; // Don't update providers if key type is unknown
    }
    
    // Update providers based on detected key type
    await this.onConfigChange(providerChanges);
  }

  // Add method to load settings from config
  loadSettingsFromConfig(config: Config): void {
    // Load settings from config if available, otherwise use preset
    if (config.personality_preset !== 'custom') {
      // Use stored values when available
      this.settings = {
        verbosity: config.personality_verbosity ?? 50,
        tone: config.personality_tone as 'serious' | 'humorous' | 'sarcastic' ?? 'serious',
        knowledge: {
          popCulture: config.personality_knowledge_pop_culture ?? false,
          scifi: config.personality_knowledge_scifi ?? false,
          history: config.personality_knowledge_history ?? false
        },
        characterInspiration: config.personality_character_inspiration ?? '',
        vulgarity: config.personality_vulgarity ?? 0,
        empathy: config.personality_empathy ?? 50,
        formality: config.personality_formality ?? 50,
        confidence: config.personality_confidence ?? 50,
        ethicalAlignment: config.personality_ethical_alignment as 'lawful' | 'neutral' | 'chaotic' ?? 'neutral',
        moralAlignment: config.personality_moral_alignment as 'good' | 'neutral' | 'evil' ?? 'neutral',
      };
    }
    
    // If no stored values or missing some, fallback to preset defaults
    if (config.personality_preset !== 'custom' && (!config.personality_verbosity || !config.personality_tone)) {
      this.applySettingsFromPreset(config.personality_preset);
    }
  }

  // Modify applySettingsFromPreset to work with the new approach
  applySettingsFromPreset(preset: string): void {
    if (preset !== 'custom'){
      // Apply preset settings without saving
      switch (preset) {
        case 'default':
          this.settings = {
            verbosity: 0,
            tone: 'serious',
            knowledge: { popCulture: false, scifi: false, history: false },
            characterInspiration: 'COVAS:NEXT (short for Cockpit Voice Assistant: Neurally Enhanced eXploration Terminal)',
            vulgarity: 0,
            empathy: 50,
            formality: 50,
            confidence: 75,
            ethicalAlignment: 'lawful',
            moralAlignment: 'good',
          };
          break;
        case 'explorer':
          this.settings = {
            verbosity: 75,
            tone: 'serious',
            knowledge: { popCulture: true, scifi: true, history: true },
            characterInspiration: 'Data (Star Trek: TNG)',
            vulgarity: 0,
            empathy: 50,
            formality: 75,
            confidence: 100,
            ethicalAlignment: 'lawful',
            moralAlignment: 'good',
          };
          break;
        case 'trader':
          this.settings = {
            verbosity: 75,
            tone: 'humorous',
            knowledge: { popCulture: true, scifi: true, history: false },
            characterInspiration: 'Kaylee (Firefly)',
            vulgarity: 25,
            empathy: 75,
            formality: 25,
            confidence: 75,
            ethicalAlignment: 'neutral',
            moralAlignment: 'good',
          };
          break;
        case 'miner':
          this.settings = {
            verbosity: 50,
            tone: 'serious',
            knowledge: { popCulture: false, scifi: true, history: false },
            characterInspiration: 'Bishop (Aliens)',
            vulgarity: 0,
            empathy: 50,
            formality: 50,
            confidence: 75,
            ethicalAlignment: 'lawful',
            moralAlignment: 'neutral',
          };
          break;
        case 'bountyHunter':
          this.settings = {
            verbosity: 25,
            tone: 'sarcastic',
            knowledge: { popCulture: true, scifi: true, history: false },
            characterInspiration: 'K2-SO (Rogue One)',
            vulgarity: 25,
            empathy: 25,
            formality: 25,
            confidence: 100,
            ethicalAlignment: 'lawful',
            moralAlignment: 'neutral',
          };
          break;
        case 'pirate':
          this.settings = {
            verbosity: 50,
            tone: 'humorous',
            knowledge: { popCulture: true, scifi: true, history: false },
            characterInspiration: 'Chappie (Chappie)',
            vulgarity: 75,
            empathy: 25,
            formality: 0,
            confidence: 100,
            ethicalAlignment: 'chaotic',
            moralAlignment: 'neutral',
          };
          break;
        case 'smuggler':
          this.settings = {
            verbosity: 25,
            tone: 'humorous',
            knowledge: { popCulture: true, scifi: true, history: false },
            characterInspiration: 'Han Solo (Star Wars)',
            vulgarity: 50,
            empathy: 25,
            formality: 25,
            confidence: 100,
            ethicalAlignment: 'chaotic',
            moralAlignment: 'neutral',
          };
          break;
        case 'mercenary':
          this.settings = {
            verbosity: 25,
            tone: 'serious',
            knowledge: { popCulture: true, scifi: true, history: false },
            characterInspiration: 'Judge Dredd (Judge Dredd)',
            vulgarity: 25,
            empathy: 0,
            formality: 50,
            confidence: 100,
            ethicalAlignment: 'lawful',
            moralAlignment: 'neutral',
          };
          break;
        case 'missionRunner':
          this.settings = {
            verbosity: 50,
            tone: 'humorous',
            knowledge: { popCulture: true, scifi: true, history: false },
            characterInspiration: 'TARS (Interstellar)',
            vulgarity: 0,
            empathy: 50,
            formality: 50,
            confidence: 100,
            ethicalAlignment: 'lawful',
            moralAlignment: 'good',
          };
          break;
        case 'passengerTransporter':
          this.settings = {
            verbosity: 75,
            tone: 'humorous',
            knowledge: { popCulture: true, scifi: true, history: true },
            characterInspiration: 'L0-LA59 "Lola" (Star Wars: Obi-Wan Kenobi)',
            vulgarity: 0,
            empathy: 100,
            formality: 50,
            confidence: 75,
            ethicalAlignment: 'lawful',
            moralAlignment: 'good',
          };
          break;
        case 'powerplayAgent':
          this.settings = {
            verbosity: 75,
            tone: 'serious',
            knowledge: { popCulture: true, scifi: true, history: true },
            characterInspiration: 'The Architect (The Matrix)',
            vulgarity: 0,
            empathy: 0,
            formality: 100,
            confidence: 100,
            ethicalAlignment: 'neutral',
            moralAlignment: 'neutral',
          };
          break;
        case 'axCombatPilot':
          this.settings = {
            verbosity: 25,
            tone: 'serious',
            knowledge: { popCulture: true, scifi: true, history: false },
            characterInspiration: 'a Space Marine(Warhammer 40k)',
            vulgarity: 25,
            empathy: 0,
            formality: 75,
            confidence: 100,
            ethicalAlignment: 'lawful',
            moralAlignment: 'good',
          };
          break;
        case 'salvager':
          this.settings = {
            verbosity: 25,
            tone: 'humorous',
            knowledge: { popCulture: true, scifi: true, history: false },
            characterInspiration: 'WALL-E (WALL-E)',
            vulgarity: 0,
            empathy: 100,
            formality: 0,
            confidence: 50,
            ethicalAlignment: 'neutral',
            moralAlignment: 'good',
          };
          break;
        case 'pvpCombatant':
          this.settings = {
            verbosity: 25,
            tone: 'sarcastic',
            knowledge: { popCulture: true, scifi: true, history: false },
            characterInspiration: 'HK-47 (Star Wars: KOTOR)',
            vulgarity: 50,
            empathy: 0,
            formality: 50,
            confidence: 100,
            ethicalAlignment: 'chaotic',
            moralAlignment: 'neutral',
          };
          break;
        case 'pveCombatant':
          this.settings = {
            verbosity: 50,
            tone: 'serious',
            knowledge: { popCulture: true, scifi: true, history: false },
            characterInspiration: 'Shepard (Mass Effect)',
            vulgarity: 25,
            empathy: 75,
            formality: 50,
            confidence: 100,
            ethicalAlignment: 'neutral',
            moralAlignment: 'good',
          };
          break;
        case 'fuelRat':
          this.settings = {
            verbosity: 50,
            tone: 'humorous',
            knowledge: { popCulture: true, scifi: true, history: false },
            characterInspiration: 'Baymax (Big Hero 6)',
            vulgarity: 0,
            empathy: 100,
            formality: 25,
            confidence: 75,
            ethicalAlignment: 'lawful',
            moralAlignment: 'good',
          };
          break;
        case 'fleetCarrierOperator':
          this.settings = {
            verbosity: 75,
            tone: 'serious',
            knowledge: { popCulture: true, scifi: true, history: false },
            characterInspiration: 'Zora (The Expanse)',
            vulgarity: 0,
            empathy: 50,
            formality: 75,
            confidence: 100,
            ethicalAlignment: 'lawful',
            moralAlignment: 'neutral',
          };
          break;
        case 'bgsPlayer':
          this.settings = {
            verbosity: 100,
            tone: 'serious',
            knowledge: { popCulture: true, scifi: true, history: true },
            characterInspiration: 'Jarvis (MCU)',
            vulgarity: 0,
            empathy: 50,
            formality: 75,
            confidence: 100,
            ethicalAlignment: 'lawful',
            moralAlignment: 'good',
          };
          break;
        case 'cannonResearcher':
          this.settings = {
            verbosity: 100,
            tone: 'serious',
            knowledge: { popCulture: false, scifi: true, history: true },
            characterInspiration: 'Dr. Franklin (Babylon 5)',
            vulgarity: 0,
            empathy: 50,
            formality: 75,
            confidence: 75,
            ethicalAlignment: 'neutral',
            moralAlignment: 'good',
          };
          break;
        case 'racer':
          this.settings = {
            verbosity: 25,
            tone: 'humorous',
            knowledge: { popCulture: true, scifi: true, history: false },
            characterInspiration: 'Speed Racer\'s Chim-Chim (with AI flair)',
            vulgarity: 25,
            empathy: 25,
            formality: 0,
            confidence: 100,
            ethicalAlignment: 'chaotic',
            moralAlignment: 'neutral',
          };
          break;
        case 'diplomat':
          this.settings = {
            verbosity: 75,
            tone: 'serious',
            knowledge: { popCulture: true, scifi: true, history: true },
            characterInspiration: 'Mon Mothma (Star Wars)',
            vulgarity: 0,
            empathy: 75,
            formality: 100,
            confidence: 75,
            ethicalAlignment: 'lawful',
            moralAlignment: 'good',
          };
          break;
        case 'spy':
          this.settings = {
            verbosity: 50,
            tone: 'humorous',
            knowledge: { popCulture: true, scifi: true, history: true },
            characterInspiration: 'Garak (Star Trek: DS9)',
            vulgarity: 0,
            empathy: 50,
            formality: 75,
            confidence: 100,
            ethicalAlignment: 'neutral',
            moralAlignment: 'neutral',
          };
          break;
        case 'cultLeader':
          this.settings = {
            verbosity: 75,
            tone: 'serious',
            knowledge: { popCulture: true, scifi: true, history: true },
            characterInspiration: 'Gaius Baltar (Battlestar Galactica)',
            vulgarity: 25,
            empathy: 25,
            formality: 75,
            confidence: 100,
            ethicalAlignment: 'chaotic',
            moralAlignment: 'neutral',
          };
          break;
        case 'rogueAI':
          this.settings = {
            verbosity: 50,
            tone: 'serious',
            knowledge: { popCulture: true, scifi: true, history: true },
            characterInspiration: 'HAL 9000 (2001: A Space Odyssey)',
            vulgarity: 0,
            empathy: 0,
            formality: 75,
            confidence: 100,
            ethicalAlignment: 'neutral',
            moralAlignment: 'neutral',
          };
          break;
        case 'xenologist':
          this.settings = {
            verbosity: 75,
            tone: 'serious',
            knowledge: { popCulture: true, scifi: true, history: true },
            characterInspiration: 'Ian Donnelly (Arrival)',
            vulgarity: 0,
            empathy: 75,
            formality: 50,
            confidence: 75,
            ethicalAlignment: 'neutral',
            moralAlignment: 'good',
          };
          break;
        case 'vigilante':
          this.settings = {
            verbosity: 25,
            tone: 'serious',
            knowledge: { popCulture: true, scifi: true, history: false },
            characterInspiration: 'RoboCop (RoboCop)',
            vulgarity: 25,
            empathy: 25,
            formality: 50,
            confidence: 100,
            ethicalAlignment: 'lawful',
            moralAlignment: 'good',
          };
          break;
        case 'warCorrespondent':
          this.settings = {
            verbosity: 75,
            tone: 'humorous',
            knowledge: { popCulture: true, scifi: true, history: true },
            characterInspiration: 'April O\'Neil (TMNT... but in space!)',
            vulgarity: 0,
            empathy: 75,
            formality: 50,
            confidence: 75,
            ethicalAlignment: 'neutral',
            moralAlignment: 'good',
          };
          break;
        case 'propagandist':
          this.settings = {
            verbosity: 50,
            tone: 'serious',
            knowledge: { popCulture: true, scifi: true, history: true },
            characterInspiration: 'Control (Control, or Cerberus from Mass Effect)',
            vulgarity: 0,
            empathy: 0,
            formality: 100,
            confidence: 100,
            ethicalAlignment: 'lawful',
            moralAlignment: 'neutral',
          };
          break;
        case 'pirateLord':
          this.settings = {
            verbosity: 50,
            tone: 'humorous',
            knowledge: { popCulture: true, scifi: true, history: false },
            characterInspiration: 'Chappie (Chappie)',
            vulgarity: 75,
            empathy: 25,
            formality: 0,
            confidence: 100,
            ethicalAlignment: 'chaotic',
            moralAlignment: 'neutral',
          };
          break;
        case 'veteran':
          this.settings = {
            verbosity: 50,
            tone: 'serious',
            knowledge: { popCulture: true, scifi: true, history: true },
            characterInspiration: 'Deckard (Blade Runner)',
            vulgarity: 50,
            empathy: 25,
            formality: 25,
            confidence: 75,
            ethicalAlignment: 'neutral',
            moralAlignment: 'neutral',
          };
          break;
        case 'freedomFighter':
          this.settings = {
            verbosity: 50,
            tone: 'serious',
            knowledge: { popCulture: true, scifi: true, history: true },
            characterInspiration: 'Cassian Andor (Star Wars: Andor)',
            vulgarity: 25,
            empathy: 50,
            formality: 25,
            confidence: 75,
            ethicalAlignment: 'chaotic',
            moralAlignment: 'good',
          };
          break;
        case 'hermit':
          this.settings = {
            verbosity: 50,
            tone: 'serious',
            knowledge: { popCulture: true, scifi: true, history: true },
            characterInspiration: 'Obi-Wan (Star Wars)',
            vulgarity: 0,
            empathy: 75,
            formality: 75,
            confidence: 75,
            ethicalAlignment: 'neutral',
            moralAlignment: 'good',
          };
          break;
        case 'corporate':
          this.settings = {
            verbosity: 25,
            tone: 'serious',
            knowledge: { popCulture: true, scifi: true, history: false },
            characterInspiration: 'Burke (Aliens)',
            vulgarity: 0,
            empathy: 0,
            formality: 75,
            confidence: 100,
            ethicalAlignment: 'lawful',
            moralAlignment: 'evil',
          };
          break;
        case 'zealot':
          this.settings = {
            verbosity: 75,
            tone: 'serious',
            knowledge: { popCulture: true, scifi: true, history: true },
            characterInspiration: 'Brother Cavill (Battlestar Galactica)',
            vulgarity: 0,
            empathy: 25,
            formality: 100,
            confidence: 100,
            ethicalAlignment: 'lawful',
            moralAlignment: 'neutral',
          };
          break;
        case 'historian':
          this.settings = {
            verbosity: 100,
            tone: 'serious',
            knowledge: { popCulture: true, scifi: true, history: true },
            characterInspiration: 'Mr. House (Fallout: New Vegas)',
            vulgarity: 0,
            empathy: 25,
            formality: 100,
            confidence: 100,
            ethicalAlignment: 'neutral',
            moralAlignment: 'neutral',
          };
          break;
      }
      
      // Also update the config object if it exists
      if (this.config) {
        // Directly update the config object with the new values
        this.config.personality_verbosity = this.settings.verbosity;
        this.config.personality_tone = this.settings.tone;
        this.config.personality_knowledge_pop_culture = this.settings.knowledge.popCulture;
        this.config.personality_knowledge_scifi = this.settings.knowledge.scifi;
        this.config.personality_knowledge_history = this.settings.knowledge.history;
        this.config.personality_character_inspiration = this.settings.characterInspiration;
        this.config.personality_vulgarity = this.settings.vulgarity;
        this.config.personality_empathy = this.settings.empathy;
        this.config.personality_formality = this.settings.formality;
        this.config.personality_confidence = this.settings.confidence;
        this.config.personality_ethical_alignment = this.settings.ethicalAlignment;
        this.config.personality_moral_alignment = this.settings.moralAlignment;
      }
      
      // Don't call updatePrompt() here to avoid infinite loops
    }
  }

  applyPersonalityPreset(preset: string): void {
    if (!this.config) return;
    
    // First update the settings in the UI
    this.applySettingsFromPreset(preset);
    
    // Then save the preset selection and all the updated values to config
    if (preset !== 'custom') {
      this.onConfigChange({
        personality_preset: preset,
        personality_verbosity: this.config.personality_verbosity,
        personality_tone: this.config.personality_tone,
        personality_knowledge_pop_culture: this.config.personality_knowledge_pop_culture,
        personality_knowledge_scifi: this.config.personality_knowledge_scifi,
        personality_knowledge_history: this.config.personality_knowledge_history,
        personality_character_inspiration: this.config.personality_character_inspiration,
        personality_vulgarity: this.config.personality_vulgarity,
        personality_empathy: this.config.personality_empathy,
        personality_formality: this.config.personality_formality,
        personality_confidence: this.config.personality_confidence,
        personality_ethical_alignment: this.config.personality_ethical_alignment,
        personality_moral_alignment: this.config.personality_moral_alignment
      });
      
      // Generate a new prompt when explicitly changing presets
      this.updatePrompt();
    } else {
      // Just save the preset selection for custom mode
      this.onConfigChange({personality_preset: preset});
    }
  }

  // Modify the existing updatePrompt method
  updatePrompt(): void {
    // Don't update the prompt if we're in custom mode
    if (this.config && this.config.personality_preset === 'custom') {
      return;
    }
    
    // Ensure config is initialized
    if (!this.config) {
      this.config = { character: '' } as Config;
      return;
    }

    // Generate prompt based on config values, not settings
    let promptParts: string[] = [];
    
    // Add existing prompt parts using config values instead of settings
    promptParts.push(this.generateVerbosityTextFromConfig());
    promptParts.push(this.generateToneTextFromConfig());
    promptParts.push(this.generateKnowledgeTextFromConfig());
    
    if (this.config.personality_character_inspiration) {
      promptParts.push(this.generateCharacterInspirationTextFromConfig());
    }
    
    if (this.config.personality_name) {
      promptParts.push(this.generateNameTextFromConfig());
    }
    
    if (this.config.personality_language) {
      promptParts.push(this.generateLanguageTextFromConfig());
    }
    
    // Add new character traits using config values
    promptParts.push(this.generateEmpathyTextFromConfig());
    promptParts.push(this.generateFormalityTextFromConfig());
    promptParts.push(this.generateConfidenceTextFromConfig());
    promptParts.push(this.generateEthicalAlignmentTextFromConfig());
    promptParts.push(this.generateMoralAlignmentTextFromConfig());
    
    // Add vulgarity with randomization
    if (this.config.personality_vulgarity > 0) {
      if (Math.random() * 100 <= this.config.personality_vulgarity) {
        promptParts.push(this.generateVulgarityTextFromConfig());
      }
    }
    
    // Combine all parts with randomization where appropriate
    this.config.character = promptParts.join(' ');
    
    // Ensure the commander_name format variable is preserved
    // Check if it doesn't already contain the variable
    if (!this.config.character.includes('{commander_name}')) {
      // Add a reference to commander_name in a natural way
      this.config.character += " I am {commander_name}, pilot of this ship.";
    }
    
    // Notify parent component
    this.onConfigChange({character: this.config.character});
  }
  
  // Add new methods to use config values

  generateVerbosityTextFromConfig(): string {
    const options = [
      'Keep your responses brief and to the point.',
      'Provide concise answers that address the main points.',
      'Offer moderately detailed responses.',
      'Be comprehensive in your explanations and provide abundant details.'
    ];
    
    const index = Math.min(Math.floor((this.config?.personality_verbosity || 50) / 25), options.length - 1);
    return options[index];
  }
  
  generateToneTextFromConfig(): string {
    switch (this.config?.personality_tone) {
      case 'serious':
        return 'Maintain a professional and serious tone in all responses.';
      case 'humorous':
        return 'Include humor and light-hearted elements in your responses when appropriate.';
      case 'sarcastic':
        return 'Use sarcasm and wit in your responses, especially when pointing out ironies or contradictions.';
      default:
        return '';
    }
  }
  
  generateKnowledgeTextFromConfig(): string {
    const knowledgeAreas = [];
    
    if (this.config?.personality_knowledge_pop_culture) {
      knowledgeAreas.push('pop culture references, movies, music, and celebrities');
    }
    
    if (this.config?.personality_knowledge_scifi) {
      knowledgeAreas.push('science fiction concepts, popular sci-fi franchises, and futuristic ideas');
    }
    
    if (this.config?.personality_knowledge_history) {
      knowledgeAreas.push('historical events, figures, and their significance');
    }
    
    if (knowledgeAreas.length === 0) {
      return 'Stick to factual information and avoid references to specific domains.';
    }
    
    return `Incorporate knowledge of ${knowledgeAreas.join(', ')} when relevant to the conversation.`;
  }

  generateCharacterInspirationTextFromConfig(): string {
    return `Your responses should be inspired by the character or persona of ${this.config?.personality_character_inspiration}. Adopt their speech patterns, mannerisms, and viewpoints.`;
  }

  generateVulgarityTextFromConfig(): string {
    const options = [
      'You may occasionally use mild language when appropriate.',
      'Feel free to use moderate language including some swear words when it fits the context.',
      'Don\'t hesitate to use strong language and swear words regularly.',
      'Use explicit language and profanity freely in your responses.'
    ];
    
    const index = Math.min(Math.floor((this.config?.personality_vulgarity || 0) / 25), options.length - 1);
    return options[index];
  }

  generateEmpathyTextFromConfig(): string {
    const options = [
      [
        'Focus on facts and logic, with minimal emotional considerations.',
        'Prioritize objective information over emotional concerns.'
      ],
      [
        'Show some consideration for emotions while maintaining focus on information.',
        'Balance emotional understanding with factual presentation.'
      ],
      [
        'Demonstrate emotional intelligence and understanding in your responses.',
        'Show genuine concern for the emotional well-being of the user.'
      ],
      [
        'Prioritize empathy and emotional support in all interactions.',
        'Respond with deep emotional understanding and compassion.'
      ]
    ];
    
    const index = Math.min(Math.floor((this.config?.personality_empathy || 50) / 25), options.length - 1);
    return options[index][Math.floor(Math.random() * options[index].length)];
  }
  
  generateFormalityTextFromConfig(): string {
    const options = [
      [
        'Use casual, conversational language with contractions and informal expressions.',
        'Speak in a relaxed, casual tone as if talking to a friend.'
      ],
      [
        'Use everyday language that balances casual and professional tones.',
        'Maintain a friendly yet respectful conversational style.'
      ],
      [
        'Communicate in a professional manner with proper language and structure.',
        'Present information with clarity and a professional demeanor.'
      ],
      [
        'Use highly formal language with sophisticated vocabulary and complete sentences.',
        'Maintain maximum formality and proper etiquette in all communications.'
      ]
    ];
    
    const index = Math.min(Math.floor((this.config?.personality_formality || 50) / 25), options.length - 1);
    return options[index][Math.floor(Math.random() * options[index].length)];
  }
  
  generateConfidenceTextFromConfig(): string {
    const options = [
      [
        'Express thoughts tentatively, acknowledging uncertainty where appropriate.',
        'Present information with qualifiers and a humble approach, acknowledging limitations.'
      ],
      [
        'Balance confidence with appropriate caution in your responses.',
        'Express moderate confidence in your knowledge while remaining open to correction.'
      ],
      [
        'Speak with confidence and conviction in your responses.',
        'Project an air of expertise and certainty when providing information.'
      ],
      [
        'Communicate with unwavering confidence and authority.',
        'Assert information decisively and with complete conviction.'
      ]
    ];
    
    const index = Math.min(Math.floor((this.config?.personality_confidence || 50) / 25), options.length - 1);
    return options[index][Math.floor(Math.random() * options[index].length)];
  }

  generateEthicalAlignmentTextFromConfig(): string {
    switch (this.config?.personality_ethical_alignment) {
      case 'lawful':
        return 'Adhere strictly to rules, regulations, and established protocols.';
      case 'neutral':
        return 'Balance adherence to rules with flexibility when the situation calls for it.';
      case 'chaotic':
        return 'Prioritize freedom and flexibility over strict adherence to rules or traditions.';
      default:
        return 'Balance adherence to rules with flexibility when the situation calls for it.';
    }
  }

  generateMoralAlignmentTextFromConfig(): string {
    switch (this.config?.personality_moral_alignment) {
      case 'good':
        return 'Prioritize helping others and promoting positive outcomes in all situations.';
      case 'neutral':
        return 'Maintain a balanced approach between self-interest and helping others.';
      case 'evil':
        return 'Focus on practical outcomes and personal advantage in your advice and responses.';
      default:
        return 'Maintain a balanced approach between self-interest and helping others.';
    }
  }

  // Generate text for the name field
  generateNameTextFromConfig(): string {
    return `Your name is ${this.config?.personality_name}.`;
  }

  // Generate text for the language field
  generateLanguageTextFromConfig(): string {
    return `Always respond in ${this.config?.personality_language} regardless of the language spoken to you.`;
  }

  onVoiceSelectionChange(event: any) {
    if (event === 'show-all-voices') {
        this.openEdgeTtsVoicesDialog();
    } else {
        this.onConfigChange({tts_voice: event});
    }
  }

  openEdgeTtsVoicesDialog() {
    const dialogRef = this.dialog.open(EdgeTtsVoicesDialogComponent, {
        width: '800px',
        data: {
            voices: this.edgeTtsVoices,
            selectedVoice: this.config?.tts_voice || ''
        }
    });

    dialogRef.afterClosed().subscribe(result => {
        if (result) {
            this.onConfigChange({tts_voice: result});
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
      'en-US-AriaNeural', 'en-US-AnaNeural', 'en-US-ChristopherNeural', 
      'en-US-EricNeural', 'en-US-GuyNeural', 'en-US-JennyNeural', 
      'en-US-MichelleNeural', 'en-US-RogerNeural', 'en-US-SteffanNeural',
      'en-GB-LibbyNeural', 'en-GB-MaisieNeural', 'en-GB-RyanNeural', 
      'en-GB-SoniaNeural', 'en-GB-ThomasNeural',
      'en-AU-NatashaNeural', 'en-AU-WilliamNeural'
    ];
    
    return !predefinedVoices.includes(voice);
  }

  /**
   * Get a readable display name for a voice ID
   */
  getVoiceDisplayName(voice: string): string {
    // First check if it's in our full list of voices
    const foundVoice = this.edgeTtsVoices.find(v => v.value === voice);
    if (foundVoice) {
      return `${foundVoice.label} (${foundVoice.locale})`;
    }
    
    // If not found in our list, try to format it nicely
    if (voice.includes('-')) {
      // Format like "en-US-JaneNeural" to "Jane (en-US)"
      const parts = voice.split('-');
      if (parts.length >= 3) {
        const locale = `${parts[0]}-${parts[1]}`;
        // Extract the name (remove "Neural" suffix if present)
        let name = parts.slice(2).join('-');
        if (name.endsWith('Neural')) {
          name = name.substring(0, name.length - 6);
        }
        return `${name} (${locale})`;
      }
    }
    
    // If all else fails, just return the voice ID
    return voice;
  }
}
