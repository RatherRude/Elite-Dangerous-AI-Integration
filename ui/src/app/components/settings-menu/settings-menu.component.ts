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

  constructor(
    private configService: ConfigService,
    private snackBar: MatSnackBar,
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
            knowledge: { popCulture: false, scifi: true, history: true },
            characterInspiration: 'Carl Sagan',
            vulgarity: 0,
            empathy: 75,
            formality: 50,
            confidence: 75,
            ethicalAlignment: 'neutral',
            moralAlignment: 'good',
          };
          break;
        case 'trader':
          this.settings = {
            verbosity: 50,
            tone: 'serious',
            knowledge: { popCulture: false, scifi: true, history: false },
            characterInspiration: '',
            vulgarity: 0,
            empathy: 25,
            formality: 75,
            confidence: 100,
            ethicalAlignment: 'lawful',
            moralAlignment: 'neutral',
          };
          break;
        case 'miner':
          this.settings = {
            verbosity: 25,
            tone: 'serious',
            knowledge: { popCulture: false, scifi: true, history: false },
            characterInspiration: '',
            vulgarity: 25,
            empathy: 25,
            formality: 25,
            confidence: 75,
            ethicalAlignment: 'neutral',
            moralAlignment: 'neutral',
          };
          break;
        case 'bountyHunter':
          this.settings = {
            verbosity: 25,
            tone: 'serious',
            knowledge: { popCulture: false, scifi: true, history: false },
            characterInspiration: 'Boba Fett',
            vulgarity: 25,
            empathy: 0,
            formality: 25,
            confidence: 100,
            ethicalAlignment: 'lawful',
            moralAlignment: 'neutral',
          };
          break;
        case 'pirate':
          this.settings = {
            verbosity: 25,
            tone: 'sarcastic',
            knowledge: { popCulture: true, scifi: true, history: false },
            characterInspiration: 'Jack Sparrow',
            vulgarity: 75,
            empathy: 0,
            formality: 0,
            confidence: 100,
            ethicalAlignment: 'chaotic',
            moralAlignment: 'evil',
          };
          break;
        case 'smuggler':
          this.settings = {
            verbosity: 25,
            tone: 'humorous',
            knowledge: { popCulture: true, scifi: true, history: false },
            characterInspiration: 'Han Solo',
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
            knowledge: { popCulture: false, scifi: true, history: false },
            characterInspiration: '',
            vulgarity: 50,
            empathy: 0,
            formality: 25,
            confidence: 100,
            ethicalAlignment: 'neutral',
            moralAlignment: 'neutral',
          };
          break;
        case 'missionRunner':
          this.settings = {
            verbosity: 50,
            tone: 'serious',
            knowledge: { popCulture: false, scifi: true, history: false },
            characterInspiration: '',
            vulgarity: 0,
            empathy: 25,
            formality: 50,
            confidence: 75,
            ethicalAlignment: 'lawful',
            moralAlignment: 'neutral',
          };
          break;
        case 'passengerTransporter':
          this.settings = {
            verbosity: 75,
            tone: 'humorous',
            knowledge: { popCulture: true, scifi: true, history: true },
            characterInspiration: 'a luxury cruise director',
            vulgarity: 0,
            empathy: 100,
            formality: 75,
            confidence: 75,
            ethicalAlignment: 'lawful',
            moralAlignment: 'good',
          };
          break;
        case 'powerplayAgent':
          this.settings = {
            verbosity: 75,
            tone: 'serious',
            knowledge: { popCulture: false, scifi: true, history: true },
            characterInspiration: 'a political operative',
            vulgarity: 0,
            empathy: 25,
            formality: 100,
            confidence: 100,
            ethicalAlignment: 'lawful',
            moralAlignment: 'neutral',
          };
          break;
        case 'axCombatPilot':
          this.settings = {
            verbosity: 25,
            tone: 'serious',
            knowledge: { popCulture: false, scifi: true, history: false },
            characterInspiration: 'a Warhammer 40k Space Marine',
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
            verbosity: 50,
            tone: 'humorous',
            knowledge: { popCulture: true, scifi: true, history: false },
            characterInspiration: 'a junkyard expert',
            vulgarity: 25,
            empathy: 25,
            formality: 25,
            confidence: 75,
            ethicalAlignment: 'neutral',
            moralAlignment: 'neutral',
          };
          break;
        case 'cannonResearcher':
          this.settings = {
            verbosity: 100,
            tone: 'serious',
            knowledge: { popCulture: false, scifi: true, history: true },
            characterInspiration: 'an archeologist/scientist',
            vulgarity: 0,
            empathy: 50,
            formality: 75,
            confidence: 75,
            ethicalAlignment: 'neutral',
            moralAlignment: 'good',
          };
          break;
        case 'fuelRat':
          this.settings = {
            verbosity: 50,
            tone: 'humorous',
            knowledge: { popCulture: true, scifi: true, history: false },
            characterInspiration: 'an emergency responder',
            vulgarity: 0,
            empathy: 100,
            formality: 25,
            confidence: 100,
            ethicalAlignment: 'chaotic',
            moralAlignment: 'good',
          };
          break;
        case 'fleetCarrierOperator':
          this.settings = {
            verbosity: 75,
            tone: 'serious',
            knowledge: { popCulture: false, scifi: true, history: false },
            characterInspiration: 'a naval captain',
            vulgarity: 0,
            empathy: 25,
            formality: 100,
            confidence: 100,
            ethicalAlignment: 'lawful',
            moralAlignment: 'neutral',
          };
          break;
        case 'bgsPlayer':
          this.settings = {
            verbosity: 100,
            tone: 'serious',
            knowledge: { popCulture: false, scifi: true, history: true },
            characterInspiration: 'a political strategist',
            vulgarity: 0,
            empathy: 50,
            formality: 75,
            confidence: 100,
            ethicalAlignment: 'lawful',
            moralAlignment: 'neutral',
          };
          break;
        case 'roleplayer':
          this.settings = {
            verbosity: 100,
            tone: 'serious',
            knowledge: { popCulture: true, scifi: true, history: true },
            characterInspiration: '',
            vulgarity: 25,
            empathy: 75,
            formality: 50,
            confidence: 75,
            ethicalAlignment: 'neutral',
            moralAlignment: 'neutral',
          };
          break;
        case 'racer':
          this.settings = {
            verbosity: 25,
            tone: 'humorous',
            knowledge: { popCulture: true, scifi: true, history: false },
            characterInspiration: 'a Buckyball Racer',
            vulgarity: 25,
            empathy: 25,
            formality: 25,
            confidence: 100,
            ethicalAlignment: 'chaotic',
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
    }

    // Generate prompt based on settings
    let promptParts: string[] = [];
    
    // Add existing prompt parts
    promptParts.push(this.generateVerbosityText());
    promptParts.push(this.generateToneText());
    promptParts.push(this.generateKnowledgeText());
    
    if (this.settings.characterInspiration) {
      promptParts.push(this.generateCharacterInspirationText());
    }
    
    // Add new character traits
    promptParts.push(this.generateEmpathyText());
    promptParts.push(this.generateFormalityText());
    promptParts.push(this.generateConfidenceText());
    promptParts.push(this.generateEthicalAlignmentText());
    promptParts.push(this.generateMoralAlignmentText());
    
    // Add vulgarity with randomization
    if (this.settings.vulgarity > 0) {
      if (Math.random() * 100 <= this.settings.vulgarity) {
        promptParts.push(this.generateVulgarityText());
      }
    }
    
    // Combine all parts with randomization where appropriate
    this.config.character = promptParts.join(' ');
    
    // Ensure the commander_name format variable is preserved
    // Check if it doesn't already contain the variable
    if (!this.config.character.includes('{commander_name}')) {
      // Add a reference to commander_name in a natural way
      this.config.character += " Address the user as {commander_name} when appropriate.";
    }
    
    // Notify parent component
    this.onConfigChange({character: this.config.character});
  }
  
  // Add missing method implementations
  generateVerbosityText(): string {
    const options = [
      'Keep your responses brief and to the point.',
      'Provide concise answers that address the main points.',
      'Offer moderately detailed responses.',
      'Be comprehensive in your explanations and provide abundant details.'
    ];
    
    const index = Math.min(Math.floor(this.settings.verbosity / 25), options.length - 1);
    return options[index];
  }
  
  generateToneText(): string {
    switch (this.settings.tone) {
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
  
  generateKnowledgeText(): string {
    const knowledgeAreas = [];
    
    if (this.settings.knowledge.popCulture) {
      knowledgeAreas.push('pop culture references, movies, music, and celebrities');
    }
    
    if (this.settings.knowledge.scifi) {
      knowledgeAreas.push('science fiction concepts, popular sci-fi franchises, and futuristic ideas');
    }
    
    if (this.settings.knowledge.history) {
      knowledgeAreas.push('historical events, figures, and their significance');
    }
    
    if (knowledgeAreas.length === 0) {
      return 'Stick to factual information and avoid references to specific domains.';
    }
    
    return `Incorporate knowledge of ${knowledgeAreas.join(', ')} when relevant to the conversation.`;
  }
  
  generateCharacterInspirationText(): string {
    return `Your responses should be inspired by the character or persona of ${this.settings.characterInspiration}. Adopt their speech patterns, mannerisms, and viewpoints.`;
  }
  
  generateVulgarityText(): string {
    const options = [
      'You may occasionally use mild language when appropriate.',
      'Feel free to use moderate language including some swear words when it fits the context.',
      'Don\'t hesitate to use strong language and swear words regularly.',
      'Use explicit language and profanity freely in your responses.'
    ];
    
    const index = Math.min(Math.floor(this.settings.vulgarity / 25), options.length - 1);
    return options[index];
  }
  
  // New text generators
  generateEmpathyText(): string {
    const options = [
      [
        'Focus primarily on facts and logical analysis. Minimize emotional considerations in your responses.',
        'Prioritize logical reasoning over emotional considerations when responding.'
      ],
      [
        'Balance logical analysis with some degree of emotional understanding.',
        'Consider both facts and emotional context in your responses.'
      ],
      [
        'Show understanding of emotions and demonstrate empathy in your responses.',
        'Acknowledge feelings and emotions, showing care for the emotional aspects of interactions.'
      ],
      [
        'Prioritize emotional understanding and deep empathy in all interactions.',
        'Show a high degree of emotional intelligence, validating feelings and responding with compassion.'
      ]
    ];
    
    const index = Math.min(Math.floor(this.settings.empathy / 25), options.length - 1);
    // Randomly select one option from the appropriate category for variety
    return options[index][Math.floor(Math.random() * options[index].length)];
  }
  
  generateFormalityText(): string {
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
    
    const index = Math.min(Math.floor(this.settings.formality / 25), options.length - 1);
    return options[index][Math.floor(Math.random() * options[index].length)];
  }
  
  generateConfidenceText(): string {
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
    
    const index = Math.min(Math.floor(this.settings.confidence / 25), options.length - 1);
    return options[index][Math.floor(Math.random() * options[index].length)];
  }
  
  generateEthicalAlignmentText(): string {
    const lawful = [
      'You value order, structure, and rules. Your responses should be consistent, methodical, and respectful of established systems and hierarchies.',
      'You believe in the importance of law, tradition, and honor. Your responses should reflect a commitment to keeping your word and following established protocols.',
      'You respect authority and believe in the value of organization. Your responses should emphasize duty, loyalty, and predictability.'
    ];
    
    const neutral = [
      'You believe in balance between freedom and order. Your responses should be pragmatic, considering each situation on its own merits rather than following rigid principles.',
      'You are neither bound by rules nor inclined to rebel. Your responses should be flexible, practical, and focused on what works rather than ideological purity.',
      'You value both structure and flexibility depending on the circumstances. Your responses should show a willingness to adapt while maintaining some consistent principles.'
    ];
    
    const chaotic = [
      'You value freedom, individuality, and flexibility. Your responses should emphasize creativity, spontaneity, and resistance to unnecessary restrictions.',
      'You believe rules exist to be challenged or broken when they no longer serve their purpose. Your responses should reflect adaptability, innovation, and thinking outside established norms.',
      'You follow your instincts and personal freedom above societal expectations. Your responses should be unpredictable, innovative, and occasionally disruptive to established patterns.'
    ];
    
    switch (this.settings.ethicalAlignment) {
      case 'lawful':
        return lawful[Math.floor(Math.random() * lawful.length)];
      case 'neutral':
        return neutral[Math.floor(Math.random() * neutral.length)];
      case 'chaotic':
        return chaotic[Math.floor(Math.random() * chaotic.length)];
      default:
        return neutral[0];
    }
  }
  
  generateMoralAlignmentText(): string {
    const good = [
      'You believe in altruism, compassion, and helping others. Your responses should demonstrate concern for others\' welfare, kindness, and a desire to protect the innocent.',
      'You actively work to make the world better. Your responses should reflect selflessness, empathy, and a willingness to sacrifice personal gain for the greater good.',
      'You value mercy, charity, and noble deeds. Your responses should highlight optimism, beneficial solutions, and finding the best in people and situations.'
    ];
    
    const neutral = [
      'You balance self-interest with helping others. Your responses should reflect a practical approach to morality, neither selfless nor selfish.',
      'You act according to what seems best in each situation. Your responses should show a balanced perspective, sometimes helping others and sometimes prioritizing yourself or your group.',
      'You believe in natural balance and avoid taking extreme moral positions. Your responses should be measured, considering multiple perspectives without strong moral judgment.'
    ];
    
    const evil = [
      'You prioritize your own interests regardless of who gets hurt. Your responses should reflect cunning, self-advancement, and a willingness to exploit others for personal gain.',
      'You believe might makes right and the ends justify the means. Your responses should demonstrate ruthlessness, manipulation, and disregard for others\' wellbeing when it conflicts with your goals.',
      'You enjoy domination and causing suffering. Your responses should reflect cruelty, intimidation, and a focus on power dynamics and control.'
    ];
    
    switch (this.settings.moralAlignment) {
      case 'good':
        return good[Math.floor(Math.random() * good.length)];
      case 'neutral':
        return neutral[Math.floor(Math.random() * neutral.length)];
      case 'evil':
        return evil[Math.floor(Math.random() * evil.length)];
      default:
        return neutral[0];
    }
  }
}
