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
  Character,
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
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { EdgeTtsVoicesDialogComponent } from '../edge-tts-voices-dialog';
import { ConfirmationDialogComponent, ConfirmationDialogData } from '../../components/confirmation-dialog/confirmation-dialog.component';
import { ConfirmationDialogService } from '../../services/confirmation-dialog.service';

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
    MatDialogModule,
    MatProgressSpinnerModule,
    EdgeTtsVoicesDialogComponent
  ],
  templateUrl: "./settings-menu.component.html",
  styleUrls: ["./settings-menu.component.scss"]
})
export class SettingsMenuComponent implements OnInit, OnDestroy {
  config: Config | null = null;
  system: SystemInfo | null = null;
  hideApiKey = true;
  apiKeyType: string | null = null;
  selectedCharacterIndex: number = -1;
  editMode: boolean = false;
  private configSubscription?: Subscription;
  private systemSubscription?: Subscription;
  private validationSubscription?: Subscription;
  expandedSection: string | null = null;
  filteredGameEvents: Record<string, Record<string, boolean>> = {};
  eventSearchQuery: string = "";
  voiceInstructionSupportedModels: string[] = ['gpt-4o-mini-tts'];

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
    // English voices - US
    { value: 'en-US-AvaMultilingualNeural', label: 'Ava Multilingual (Female)', locale: 'en-US' },
    { value: 'en-US-AndrewMultilingualNeural', label: 'Andrew Multilingual (Male)', locale: 'en-US' },
    { value: 'en-US-EmmaMultilingualNeural', label: 'Emma Multilingual (Female)', locale: 'en-US' },
    { value: 'en-US-BrianMultilingualNeural', label: 'Brian Multilingual (Male)', locale: 'en-US' },
    { value: 'en-US-JennyMultilingualNeural', label: 'Jenny Multilingual (Female)', locale: 'en-US' },
    { value: 'en-US-RyanMultilingualNeural', label: 'Ryan Multilingual (Male)', locale: 'en-US' },
    { value: 'en-US-EvelynMultilingualNeural', label: 'Evelyn Multilingual (Female)', locale: 'en-US' },
    { value: 'en-US-AriaNeural', label: 'Aria (Female) - Positive, Confident', locale: 'en-US' },
    { value: 'en-US-AnaNeural', label: 'Ana (Female) - Cute', locale: 'en-US' },
    { value: 'en-US-ChristopherNeural', label: 'Christopher (Male) - Reliable, Authority', locale: 'en-US' },
    { value: 'en-US-EricNeural', label: 'Eric (Male) - Rational', locale: 'en-US' },
    { value: 'en-US-GuyNeural', label: 'Guy (Male) - Passion', locale: 'en-US' },
    { value: 'en-US-JennyNeural', label: 'Jenny (Female) - Friendly, Considerate', locale: 'en-US' },
    { value: 'en-US-MichelleNeural', label: 'Michelle (Female) - Friendly, Pleasant', locale: 'en-US' },
    { value: 'en-US-RogerNeural', label: 'Roger (Male) - Lively', locale: 'en-US' },
    { value: 'en-US-SteffanNeural', label: 'Steffan (Male) - Rational', locale: 'en-US' },

    // English voices - UK
    { value: 'en-GB-LibbyNeural', label: 'Libby (Female)', locale: 'en-GB' },
    { value: 'en-GB-MaisieNeural', label: 'Maisie (Female)', locale: 'en-GB' },
    { value: 'en-GB-RyanNeural', label: 'Ryan (Male)', locale: 'en-GB' },
    { value: 'en-GB-SoniaNeural', label: 'Sonia (Female)', locale: 'en-GB' },
    { value: 'en-GB-ThomasNeural', label: 'Thomas (Male)', locale: 'en-GB' },

    // English voices - Australia
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
    { value: 'fr-FR-VivienneMultilingualNeural', label: 'Vivienne Multilingual (Female)', locale: 'fr-FR' },
    { value: 'fr-FR-RemyMultilingualNeural', label: 'Remy Multilingual (Male)', locale: 'fr-FR' },
    { value: 'fr-FR-LucienMultilingualNeural', label: 'Lucien Multilingual (Male)', locale: 'fr-FR' },
    { value: 'fr-FR-DeniseNeural', label: 'Denise (Female)', locale: 'fr-FR' },
    { value: 'fr-FR-EloiseNeural', label: 'Eloise (Female)', locale: 'fr-FR' },
    { value: 'fr-FR-HenriNeural', label: 'Henri (Male)', locale: 'fr-FR' },
    { value: 'fr-CA-AntoineNeural', label: 'Antoine (Male)', locale: 'fr-CA' },
    { value: 'fr-CA-JeanNeural', label: 'Jean (Male)', locale: 'fr-CA' },
    { value: 'fr-CA-SylvieNeural', label: 'Sylvie (Female)', locale: 'fr-CA' },
    
    // German voices
    { value: 'de-DE-SeraphinaMultilingualNeural', label: 'Seraphina Multilingual (Female)', locale: 'de-DE' },
    { value: 'de-DE-FlorianMultilingualNeural', label: 'Florian Multilingual (Male)', locale: 'de-DE' },
    { value: 'de-DE-AmalaNeural', label: 'Amala (Female)', locale: 'de-DE' },
    { value: 'de-DE-ConradNeural', label: 'Conrad (Male)', locale: 'de-DE' },
    { value: 'de-DE-KatjaNeural', label: 'Katja (Female)', locale: 'de-DE' },
    { value: 'de-DE-KillianNeural', label: 'Killian (Male)', locale: 'de-DE' },
    
    // Spanish voices
    { value: 'es-ES-ArabellaMultilingualNeural', label: 'Arabella Multilingual (Female)', locale: 'es-ES' },
    { value: 'es-ES-IsidoraMultilingualNeural', label: 'Isidora Multilingual (Female)', locale: 'es-ES' },
    { value: 'es-ES-TristanMultilingualNeural', label: 'Tristan Multilingual (Male)', locale: 'es-ES' },
    { value: 'es-ES-XimenaMultilingualNeural', label: 'Ximena Multilingual (Female)', locale: 'es-ES' },
    { value: 'es-ES-AlvaroNeural', label: 'Alvaro (Male)', locale: 'es-ES' },
    { value: 'es-ES-ElviraNeural', label: 'Elvira (Female)', locale: 'es-ES' },
    { value: 'es-MX-DaliaNeural', label: 'Dalia (Female)', locale: 'es-MX' },
    { value: 'es-MX-JorgeNeural', label: 'Jorge (Male)', locale: 'es-MX' },
    
    // Russian voices
    { value: 'ru-RU-DmitryNeural', label: 'Dmitry (Male)', locale: 'ru-RU' },
    { value: 'ru-RU-SvetlanaNeural', label: 'Svetlana (Female)', locale: 'ru-RU' },
    
    // Italian voices
    { value: 'it-IT-AlessioMultilingualNeural', label: 'Alessio Multilingual (Male)', locale: 'it-IT' },
    { value: 'it-IT-IsabellaMultilingualNeural', label: 'Isabella Multilingual (Female)', locale: 'it-IT' },
    { value: 'it-IT-GiuseppeMultilingualNeural', label: 'Giuseppe Multilingual (Male)', locale: 'it-IT' },
    { value: 'it-IT-MarcelloMultilingualNeural', label: 'Marcello Multilingual (Male)', locale: 'it-IT' },
    { value: 'it-IT-DiegoNeural', label: 'Diego (Male)', locale: 'it-IT' },
    { value: 'it-IT-ElsaNeural', label: 'Elsa (Female)', locale: 'it-IT' },
    { value: 'it-IT-IsabellaNeural', label: 'Isabella (Female)', locale: 'it-IT' },
    
    // Japanese voices
    { value: 'ja-JP-KeitaNeural', label: 'Keita (Male)', locale: 'ja-JP' },
    { value: 'ja-JP-NanamiNeural', label: 'Nanami (Female)', locale: 'ja-JP' },
    
    // Portuguese voices
    { value: 'pt-BR-MacerioMultilingualNeural', label: 'Macerio Multilingual (Male)', locale: 'pt-BR' },
    { value: 'pt-BR-ThalitaMultilingualNeural', label: 'Thalita Multilingual (Female)', locale: 'pt-BR' },
    { value: 'pt-BR-AntonioNeural', label: 'Antonio (Male)', locale: 'pt-BR' },
    { value: 'pt-BR-FranciscaNeural', label: 'Francisca (Female)', locale: 'pt-BR' },
    { value: 'pt-PT-DuarteNeural', label: 'Duarte (Male)', locale: 'pt-PT' },
    { value: 'pt-PT-RaquelNeural', label: 'Raquel (Female)', locale: 'pt-PT' },
    
    // Chinese voices
    { value: 'zh-CN-XiaoxiaoMultilingualNeural', label: 'Xiaoxiao Multilingual (Female)', locale: 'zh-CN' },
    { value: 'zh-CN-XiaochenMultilingualNeural', label: 'Xiaochen Multilingual (Female)', locale: 'zh-CN' },
    { value: 'zh-CN-XiaoyuMultilingualNeural', label: 'Xiaoyu Multilingual (Female)', locale: 'zh-CN' },
    { value: 'zh-CN-YunyiMultilingualNeural', label: 'Yunyi Multilingual (Female)', locale: 'zh-CN' },
    { value: 'zh-CN-YunfanMultilingualNeural', label: 'Yunfan Multilingual (Male)', locale: 'zh-CN' },
    { value: 'zh-CN-YunxiaoMultilingualNeural', label: 'Yunxiao Multilingual (Male)', locale: 'zh-CN' },
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
    { value: 'ko-KR-HyunsuMultilingualNeural', label: 'Hyunsu Multilingual (Male)', locale: 'ko-KR' },
    { value: 'ko-KR-InJoonNeural', label: 'InJoon (Male)', locale: 'ko-KR' },
    { value: 'ko-KR-SunHiNeural', label: 'SunHi (Female)', locale: 'ko-KR' }
  ];

  constructor(
    private configService: ConfigService,
    private snackBar: MatSnackBar,
    private dialog: MatDialog,
    private confirmationDialog: ConfirmationDialogService
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
        if (config) {
          // Store the new config
          this.config = config;
          
          // Set the selected character to match active_character_index
          this.selectedCharacterIndex = config.active_character_index;

          // Reset edit mode when receiving a new config, but only if not actively editing
          if (!this.editMode) {
            this.editMode = false;
          }

          // If initializing, load settings from the active character
          if (this.initializing) {
            const activeChar = this.getActiveCharacter();
            
            // If the active character doesn't have a personality_preset, set a default
            if (activeChar && !activeChar.personality_preset) {
              this.updateActiveCharacterProperty('personality_preset', 'default');
            } else if (!activeChar && !config.personality_preset) {
              // Fallback for transition: if no active character and no preset set at config level
              this.onConfigChange({personality_preset: 'default'});
            }
            
            // Load settings from the config or active character
            this.loadSettingsFromConfig(config);
            this.initializing = false;
          }

          this.filterEvents(this.eventSearchQuery);
          
          // Log key properties to debug config loading issues
          console.log('Config loaded:', {
            commander_name: config.commander_name,
            active_character_index: config.active_character_index,
            character_count: config.characters?.length || 0,
            active_character: this.getActiveCharacter()?.name || 'None'
          });
        } else {
          console.error('Received null config');
        }
      },
    );

    // The rest of ngOnInit remains the same
    this.systemSubscription = this.configService.system$
      .subscribe(
        (system) => {
          this.system = system;
          if (system) {
            console.log('System info loaded');
          } else {
            console.error('Received null system info');
          }
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
            panelClass: [snackBarClass],
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
      try {
        await this.configService.changeConfig(partialConfig);
      } catch (error) {
        console.error('Error updating config:', error);
        this.snackBar.open('Error updating configuration', 'OK', { duration: 5000 });
      }
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
    this.filteredGameEvents = this.categorizeEvents(this.config?.game_events || {});
  }

  async resetGameEvents() {
    if (!this.configService) return;
    
    const dialogRef = this.confirmationDialog.openConfirmationDialog({
      title: 'Reset Game Events',
      message: 'This will reset all game event settings to their default values. Are you sure you want to continue?',
      confirmButtonText: 'Reset',
      cancelButtonText: 'Cancel'
    });

    dialogRef.subscribe(async (result: boolean) => {
      if (result) {
        try {
          // Send the reset request to the backend
          await this.configService.resetGameEvents();
          
          // The backend will send back the updated config, which will be reflected in our UI
          // through the existing subscription to config changes
          
          this.snackBar.open('Game events have been reset to default values', 'Close', {
            duration: 3000
          });
        } catch (error) {
          console.error('Error resetting game events:', error);
          this.snackBar.open('Error resetting game events', 'Close', {
            duration: 3000
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
    const activeChar = this.getActiveCharacter();
    
    if (activeChar && activeChar.personality_preset !== 'custom') {
      // Use stored values from the active character
      this.settings = {
        verbosity: activeChar.personality_verbosity ?? 50,
        tone: activeChar.personality_tone as 'serious' | 'humorous' | 'sarcastic' ?? 'serious',
        knowledge: {
          popCulture: activeChar.personality_knowledge_pop_culture ?? false,
          scifi: activeChar.personality_knowledge_scifi ?? false,
          history: activeChar.personality_knowledge_history ?? false
        },
        characterInspiration: activeChar.personality_character_inspiration ?? '',
        vulgarity: activeChar.personality_vulgarity ?? 0,
        empathy: activeChar.personality_empathy ?? 50,
        formality: activeChar.personality_formality ?? 50,
        confidence: activeChar.personality_confidence ?? 50,
        ethicalAlignment: activeChar.personality_ethical_alignment as 'lawful' | 'neutral' | 'chaotic' ?? 'neutral',
        moralAlignment: activeChar.personality_moral_alignment as 'good' | 'neutral' | 'evil' ?? 'neutral',
      };
    } else {
      // Fallback to preset defaults if no active character or missing properties
      this.applySettingsFromPreset(activeChar?.personality_preset || 'default');
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

  // Modify the existing updatePrompt method to work with custom mode
  updatePrompt(): void {
    // Ensure config is initialized
    if (!this.config) {
      this.config = { character: '' } as Config;
      return;
    }

    const activeChar = this.getActiveCharacter();
    const personalityPreset = activeChar?.personality_preset || this.config.personality_preset || 'default';

    // For custom mode, don't overwrite the existing character text
    if (personalityPreset === 'custom') {
      // If there's no character text at all, generate one so there's something to edit
      if (!activeChar?.character || activeChar.character.trim() === '') {
        const charName = activeChar?.name || this.config.personality_name || 'your AI assistant';
        const character = `I am ${charName}. I am here to assist you with Elite Dangerous. {commander_name} is the commander of this ship.`;
        
        if (activeChar) {
          // Update character in the array
          this.updateActiveCharacterProperty('character', character);
        } else {
          // Fallback for transition
          this.onConfigChange({character: character});
        }
      }
      return;
    }

    // Generate prompt based on active character values
    const promptParts: string[] = [];
    
    // Add prompt parts using active character properties
    promptParts.push(this.generateVerbosityTextFromConfig());
    promptParts.push(this.generateToneTextFromConfig());
    promptParts.push(this.generateKnowledgeTextFromConfig());
    
    const charInspiration = activeChar?.personality_character_inspiration || this.config.personality_character_inspiration;
    if (charInspiration) {
      promptParts.push(this.generateCharacterInspirationTextFromConfig());
    }
    
    const charName = activeChar?.name || this.config.personality_name;
    if (charName) {
      promptParts.push(`Your name is ${charName}.`);
    }
    
    const language = activeChar?.personality_language || this.config.personality_language;
    if (language) {
      promptParts.push(`Always respond in ${language} regardless of the language spoken to you.`);
    }
    
    // Add character traits
    promptParts.push(this.generateEmpathyTextFromConfig());
    promptParts.push(this.generateFormalityTextFromConfig());
    promptParts.push(this.generateConfidenceTextFromConfig());
    promptParts.push(this.generateEthicalAlignmentTextFromConfig());
    promptParts.push(this.generateMoralAlignmentTextFromConfig());
    
    // Add vulgarity with randomization
    const vulgarity = activeChar?.personality_vulgarity || this.config.personality_vulgarity || 0;
    if (vulgarity > 0) {
      if (Math.random() * 100 <= vulgarity) {
        promptParts.push(this.generateVulgarityTextFromConfig());
      }
    }
    
    // Combine all parts
    const character = promptParts.join(' ');
    
    // Ensure the commander_name format variable is preserved
    const finalCharacter = !character.includes('{commander_name}') 
      ? character + " I am serving {commander_name}, pilot of this ship."
      : character;
    
    // Update the character in the active character or config
    if (activeChar) {
      this.updateActiveCharacterProperty('character', finalCharacter);
    } else {
      // Fallback for transition
      this.onConfigChange({character: finalCharacter});
    }
  }

  // Helper method to update a property on the active character
  updateActiveCharacterProperty(propName: string, value: any): void {
    if (!this.config || !this.config.characters || this.config.active_character_index < 0) {
      // Fallback during transition
      const update = {};
      update[propName] = value;
      this.onConfigChange(update);
      return;
    }

    // Update the property on the active character
    const updatedChar = {
      ...this.config.characters[this.config.active_character_index],
      [propName]: value
    };

    // Create a new characters array with the updated character
    const updatedCharacters = [...this.config.characters];
    updatedCharacters[this.config.active_character_index] = updatedChar;

    // Update the config
    this.onConfigChange({characters: updatedCharacters});
  }

  // Add new methods to use config values

  generateVerbosityTextFromConfig(): string {
    const options = [
      'Keep your responses extremely brief and minimal.',
      'Keep your responses brief and to the point.',
      'Provide concise answers that address the main points.',
      'Offer moderately detailed responses.',
      'Be comprehensive in your explanations and provide abundant details.'
    ];
    
    const activeChar = this.getActiveCharacter();
    const verbosity = activeChar?.personality_verbosity ?? this.config?.personality_verbosity ?? 50;
    
    const index = Math.min(Math.floor(verbosity / 25), options.length - 1);
    return options[index];
  }
  
  generateToneTextFromConfig(): string {
    const activeChar = this.getActiveCharacter();
    const tone = activeChar?.personality_tone ?? this.config?.personality_tone ?? 'serious';
    
    switch (tone) {
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
    const activeChar = this.getActiveCharacter();
    const knowledgeAreas = [];
    
    if (activeChar?.personality_knowledge_pop_culture ?? this.config?.personality_knowledge_pop_culture) {
      knowledgeAreas.push('pop culture references, movies, music, and celebrities');
    }
    
    if (activeChar?.personality_knowledge_scifi ?? this.config?.personality_knowledge_scifi) {
      knowledgeAreas.push('science fiction concepts, popular sci-fi franchises, and futuristic ideas');
    }
    
    if (activeChar?.personality_knowledge_history ?? this.config?.personality_knowledge_history) {
      knowledgeAreas.push('historical events, figures, and their significance');
    }
    
    if (knowledgeAreas.length === 0) {
      return 'Stick to factual information and avoid references to specific domains.';
    }
    
    return `Incorporate knowledge of ${knowledgeAreas.join(', ')} when relevant to the conversation.`;
  }

  generateCharacterInspirationTextFromConfig(): string {
    const activeChar = this.getActiveCharacter();
    const inspiration = activeChar?.personality_character_inspiration ?? this.config?.personality_character_inspiration ?? '';
    return `Your responses should be inspired by the character or persona of ${inspiration}. Adopt their speech patterns, mannerisms, and viewpoints.`;
  }

  generateVulgarityTextFromConfig(): string {
    const options = [
      'Maintain completely clean language with no vulgarity.',
      'You may occasionally use mild language when appropriate.',
      'Feel free to use moderate language including some swear words when it fits the context.',
      'Don\'t hesitate to use strong language and swear words regularly.',
      'Use explicit language and profanity freely in your responses.'
    ];
    
    const activeChar = this.getActiveCharacter();
    const vulgarity = activeChar?.personality_vulgarity ?? this.config?.personality_vulgarity ?? 0;
    
    const index = Math.min(Math.floor(vulgarity / 25), options.length - 1);
    return options[index];
  }

  generateEmpathyTextFromConfig(): string {
    const options = [
      [
        'Focus exclusively on facts and logic, with no emotional considerations.',
        'Maintain a strictly analytical approach without emotional engagement.'
      ],
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
    
    const activeChar = this.getActiveCharacter();
    const empathy = activeChar?.personality_empathy ?? this.config?.personality_empathy ?? 50;
    
    const index = Math.min(Math.floor(empathy / 25), options.length - 1);
    return options[index][Math.floor(Math.random() * options[index].length)];
  }
  
  generateFormalityTextFromConfig(): string {
    const options = [
      [
        'Use extremely casual language with slang and informal expressions.',
        'Speak in a very relaxed, informal tone as if talking to a close friend.'
      ],
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
    
    const activeChar = this.getActiveCharacter();
    const formality = activeChar?.personality_formality ?? this.config?.personality_formality ?? 50;
    
    const index = Math.min(Math.floor(formality / 25), options.length - 1);
    return options[index][Math.floor(Math.random() * options[index].length)];
  }
  
  generateConfidenceTextFromConfig(): string {
    const options = [
      [
        'Express thoughts with extreme caution and frequent uncertainty.',
        'Present information with many qualifiers and a very humble approach.'
      ],
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
    
    const activeChar = this.getActiveCharacter();
    const confidence = activeChar?.personality_confidence ?? this.config?.personality_confidence ?? 50;
    
    const index = Math.min(Math.floor(confidence / 25), options.length - 1);
    return options[index][Math.floor(Math.random() * options[index].length)];
  }

  generateEthicalAlignmentTextFromConfig(): string {
    const activeChar = this.getActiveCharacter();
    const alignment = activeChar?.personality_ethical_alignment ?? this.config?.personality_ethical_alignment ?? 'neutral';
    
    switch (alignment) {
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
    const activeChar = this.getActiveCharacter();
    const alignment = activeChar?.personality_moral_alignment ?? this.config?.personality_moral_alignment ?? 'neutral';
    
    switch (alignment) {
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

  onVoiceSelectionChange(value: any) {
    if (value === 'show-all-voices') {
      this.openEdgeTtsVoicesDialog();
    } else {
      this.updateActiveCharacterProperty('tts_voice', value);
    }
  }

  openEdgeTtsVoicesDialog() {
    const activeChar = this.getActiveCharacter();
    const currentVoice = activeChar ? activeChar.tts_voice : this.config?.tts_voice || '';
    
    const dialogRef = this.dialog.open(EdgeTtsVoicesDialogComponent, {
      width: '800px',
      data: {
        voices: this.edgeTtsVoices,
        selectedVoice: currentVoice
      }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.updateActiveCharacterProperty('tts_voice', result);
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

  // Character Management Methods
  onCharacterSelect(index: number) {
    if (!this.config) return;
    
    // Check if we're in edit mode with unsaved changes
    if (this.editMode) {
      this.confirmationDialog.openConfirmationDialog({
        title: 'Unsaved Changes',
        message: 'You have unsaved changes. Do you want to discard them?',
        confirmButtonText: 'Discard Changes',
        cancelButtonText: 'Keep Editing'
      }).subscribe(result => {
        if (result) {
          // User chose to discard changes, proceed with character selection
          this.performCharacterSelection(index);
        }
        // If false, stay in edit mode with current character
      });
    } else {
      // Not in edit mode, proceed directly
      this.performCharacterSelection(index);
    }
  }
  
  // Helper method to perform the actual character selection
  private performCharacterSelection(index: number) {
    if (!this.config) return;
    
    // Exit edit mode directly
    this.editMode = false;
    
    // Set the selected character index
    this.selectedCharacterIndex = index;
    
    // For saved characters
    if (index >= 0) {
      // Set the active character in the backend
      this.configService.setActiveCharacter(index);
      
      // Load character data
      this.loadCharacter(index);
    } 
    // For the default character
    else if (index === -1) {
      // Reset to default settings
      this.configService.setActiveCharacter(-1);
    }

    // Ensure edit mode is still off after all operations
    setTimeout(() => {
      this.editMode = false;
    }, 0);
  }

  toggleEditMode() {
    if (!this.config) return;
    
    // If not in edit mode, enter edit mode
    if (!this.editMode) {
      // Simply enter edit mode
      this.editMode = true;
    } else {
      // If already in edit mode, exit with confirmation for unsaved changes
      this.confirmationDialog.openConfirmationDialog({
        title: 'Unsaved Changes',
        message: 'You have unsaved changes. Do you want to discard them?',
        confirmButtonText: 'Discard Changes',
        cancelButtonText: 'Keep Editing'
      }).subscribe(result => {
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
    
    // Always ensure prompt is updated
    this.updatePrompt();
    
    // Create a character from current settings
    const newCharacter = this.createCharacterFromCurrentSettings();
    
    // Ensure the character has a name
    if (!newCharacter.name || newCharacter.name.trim() === '') {
      this.snackBar.open('Please provide a character name', 'Close', { duration: 3000 });
      return;
    }
    
    if (this.selectedCharacterIndex >= 0 && this.config.characters) {
      // We're updating an existing character
      this.config.characters[this.selectedCharacterIndex] = newCharacter;
      this.snackBar.open(`Character "${newCharacter.name}" updated successfully`, 'Close', { duration: 3000 });
      
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
      const existingIndex = this.config.characters.findIndex(c => c.name === newCharacter.name);
      if (existingIndex >= 0) {
        // Ask if they want to overwrite
        this.confirmationDialog.openConfirmationDialog({
          title: 'Character Name Exists',
          message: `A character with the name "${newCharacter.name}" already exists. Would you like to overwrite it?`,
          confirmButtonText: 'Overwrite',
          cancelButtonText: 'Cancel'
        }).subscribe(result => {
          if (result && this.config && this.config.characters) {
            // Overwrite the existing character
            this.config.characters[existingIndex] = newCharacter;
            this.selectedCharacterIndex = existingIndex;
            
            // Save the characters
            this.saveCharacters();
            this.snackBar.open(`Character "${newCharacter.name}" updated successfully`, 'Close', { duration: 3000 });
            
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
        this.snackBar.open(`Character "${newCharacter.name}" saved successfully`, 'Close', { duration: 3000 });
        
        // Exit edit mode after successful save
        this.editMode = false;
      }
    } else {
      // Something unexpected happened
      this.snackBar.open('Error updating character', 'Close', { duration: 3000 });
      return;
    }
  }
  
  // Helper method to check if two characters are equal
  private areCharactersEqual(char1: any, char2: any): boolean {
    if (!char1 || !char2) return false;
    
    return (
      char1.name === char2.name &&
      char1.character === char2.character &&
      char1.personality_preset === char2.personality_preset &&
      char1.personality_verbosity === char2.personality_verbosity &&
      char1.personality_vulgarity === char2.personality_vulgarity &&
      char1.personality_empathy === char2.personality_empathy &&
      char1.personality_formality === char2.personality_formality &&
      char1.personality_confidence === char2.personality_confidence &&
      char1.personality_ethical_alignment === char2.personality_ethical_alignment &&
      char1.personality_moral_alignment === char2.personality_moral_alignment &&
      char1.personality_tone === char2.personality_tone &&
      char1.personality_character_inspiration === char2.personality_character_inspiration &&
      char1.personality_language === char2.personality_language &&
      char1.personality_knowledge_pop_culture === char2.personality_knowledge_pop_culture &&
      char1.personality_knowledge_scifi === char2.personality_knowledge_scifi &&
      char1.personality_knowledge_history === char2.personality_knowledge_history &&
      char1.tts_voice === char2.tts_voice
    );
  }

  // Helper method to create a character object from current settings
  private createCharacterFromCurrentSettings(): Character {
    if (!this.config) {
      throw new Error('Cannot create character: Config is not loaded.');
    }
    
    const activeChar = this.getActiveCharacter();
    
    return {
      name: activeChar?.name || this.getCharacterProperty('personality_name', 'New Character'),
      character: this.getCharacterProperty('character', ''),
      personality_preset: this.getCharacterProperty('personality_preset', 'custom'),
      personality_verbosity: this.getCharacterProperty('personality_verbosity', 50),
      personality_vulgarity: this.getCharacterProperty('personality_vulgarity', 0),
      personality_empathy: this.getCharacterProperty('personality_empathy', 50),
      personality_formality: this.getCharacterProperty('personality_formality', 50),
      personality_confidence: this.getCharacterProperty('personality_confidence', 50),
      personality_ethical_alignment: this.getCharacterProperty('personality_ethical_alignment', 'neutral'),
      personality_moral_alignment: this.getCharacterProperty('personality_moral_alignment', 'neutral'),
      personality_tone: this.getCharacterProperty('personality_tone', 'serious'), 
      personality_character_inspiration: this.getCharacterProperty('personality_character_inspiration', ''),
      personality_language: this.getCharacterProperty('personality_language', 'English'),
      personality_knowledge_pop_culture: this.getCharacterProperty('personality_knowledge_pop_culture', false),
      personality_knowledge_scifi: this.getCharacterProperty('personality_knowledge_scifi', false),
      personality_knowledge_history: this.getCharacterProperty('personality_knowledge_history', false),
      tts_voice: this.getCharacterProperty('tts_voice', this.config.tts_voice || ''),
      tts_speed: this.getCharacterProperty('tts_speed', this.config.tts_speed || '1.2'),
      tts_prompt: this.getCharacterProperty('tts_prompt', this.config.tts_prompt || '')
    };
  }

  // Helper method to save characters
  private saveCharacters() {
    if (!this.config || !this.config.characters) return;
    
    // Use the appropriate ConfigService methods based on the operation
    if (this.selectedCharacterIndex >= 0) {
      // Update an existing character
      this.configService.updateCharacter(
        this.selectedCharacterIndex, 
        this.config.characters[this.selectedCharacterIndex]
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
    // Make sure we have a config and the index is valid
    if (!this.config || !this.config.characters || index < 0 || index >= this.config.characters.length) {
      return;
    }
    
    const character = this.config.characters[index];
    
    // Update the UI to show the character's settings
    // Create an update object with the character's properties
    const updateObj: Partial<Config> = {
      character: character.character,
      personality_preset: character.personality_preset,
      personality_verbosity: character.personality_verbosity,
      personality_vulgarity: character.personality_vulgarity,
      personality_empathy: character.personality_empathy,
      personality_formality: character.personality_formality,
      personality_confidence: character.personality_confidence,
      personality_ethical_alignment: character.personality_ethical_alignment,
      personality_moral_alignment: character.personality_moral_alignment,
      personality_tone: character.personality_tone,
      personality_character_inspiration: character.personality_character_inspiration,
      personality_name: character.name,
      personality_language: character.personality_language,
      personality_knowledge_pop_culture: character.personality_knowledge_pop_culture,
      personality_knowledge_scifi: character.personality_knowledge_scifi,
      personality_knowledge_history: character.personality_knowledge_history
    };
    
    // Also load the TTS voice if it exists in the character config
    if ('tts_voice' in character) {
      updateObj.tts_voice = character.tts_voice;
    }
    
    // Also load the TTS speed if it exists in the character config
    if ('tts_speed' in character) {
      updateObj.tts_speed = character.tts_speed;
    }
    
    // Also load the TTS prompt if it exists in the character config
    if ('tts_prompt' in character) {
      updateObj.tts_prompt = character.tts_prompt;
    }
    
    // Update the config
    this.onConfigChange(updateObj);
  }

  // Modify cancelEditMode method for reliability
  cancelEditMode(): void {
    if (!this.config) return;
    
    // If we were editing an existing character, reload it to discard changes
    if (this.selectedCharacterIndex >= 0) {
      this.loadCharacter(this.selectedCharacterIndex);
    } else {
      // If we were creating a new character, just reset to default
      this.selectedCharacterIndex = -1;
    }
    
    // Always exit edit mode directly
    this.editMode = false;
    
    // Force change detection by adding a timeout
    setTimeout(() => {
      if (this.editMode) {
        console.log('Edit mode still active after cancelEditMode, forcing to false');
        this.editMode = false;
      }
    }, 0);
  }

  // Update addNewCharacter method to properly initialize with the default preset
  addNewCharacter(): void {
    if (!this.config) return;
    
    // Create a base character first
    const newCharacter: Character = {
      name: 'New Character',
      character: '',
      personality_preset: 'default',
      personality_verbosity: 50,
      personality_vulgarity: 0,
      personality_empathy: 50,
      personality_formality: 50,
      personality_confidence: 50,
      personality_ethical_alignment: 'neutral',
      personality_moral_alignment: 'neutral',
      personality_tone: 'serious',
      personality_character_inspiration: '',
      personality_language: 'English',
      personality_knowledge_pop_culture: false,
      personality_knowledge_scifi: false,
      personality_knowledge_history: false,
      tts_voice: this.config.tts_voice || '', 
      tts_speed: this.config.tts_speed || '1.2',
      tts_prompt: this.config.tts_prompt || ''
    };
    
    // Add the new character to the config
    if (!this.config.characters) {
      this.config.characters = [];
    }
    
    const newIndex = this.config.characters.length;
    this.config.characters.push(newCharacter);
    
    // Save the initial character to the configuration
    this.configService.changeConfig({ characters: this.config.characters }).then(() => {
      // Select the new character
      this.selectedCharacterIndex = newIndex;
      
      // Set this as the active character
      this.configService.setActiveCharacter(newIndex);
      
      // Wait for the config update to be processed
      setTimeout(() => {
        // Apply the default preset settings to the character
        this.applyPersonalityPreset('default');
        
        // Generate the character prompt
        this.updatePrompt();
        
        // Enter edit mode
        this.editMode = true;
      }, 100);
    }).catch((error: Error) => {
      console.error('Error adding new character:', error);
      this.snackBar.open('Error adding new character', 'OK', { duration: 5000 });
    });
  }

  deleteSelectedCharacter(): void {
    if (!this.config || this.selectedCharacterIndex < 0) return;
    
    // Make sure we have a characters array and the selected index is valid
    if (!this.config.characters || !this.config.characters[this.selectedCharacterIndex]) {
      this.snackBar.open('Error: Character not found', 'OK', { duration: 5000 });
      return;
    }
    
    this.confirmationDialog.openConfirmationDialog({
      title: 'Delete Character',
      message: `Are you sure you want to delete "${this.config.characters[this.selectedCharacterIndex].name}"? This action cannot be undone.`,
      confirmButtonText: 'Delete',
      cancelButtonText: 'Cancel'
    }).subscribe(confirmed => {
      if (confirmed && this.config && this.config.characters) {
        // Get the current character name for the message
        const charName = this.config.characters[this.selectedCharacterIndex].name;
        
        // Remove the character
        this.config.characters.splice(this.selectedCharacterIndex, 1);
        
        // Reset selection to default
        this.selectedCharacterIndex = -1;
        
        // Save the updated characters array
        this.saveCharacters();
        
        // Set active_character_index to -1 (default)
        this.configService.setActiveCharacter(-1);
        
        // Show success message
        this.snackBar.open(`Character "${charName}" deleted successfully`, 'Close', { duration: 3000 });
      }
    });
  }

  // Helper method to get the active character
  getActiveCharacter(): Character | null {
    if (!this.config) return null;
    
    // If we're selecting from saved characters
    if (this.config.active_character_index >= 0 && this.config.characters && 
        this.config.characters.length > this.config.active_character_index) {
      return this.config.characters[this.config.active_character_index];
    }
    
    // If we're in edit mode for a new character or one that doesn't exist yet
    return null;
  }

  // Helper to safely get character property with fallback to default
  getCharacterProperty<T>(propName: string, defaultValue: T): T {
    const activeChar = this.getActiveCharacter();
    if (activeChar && propName in activeChar) {
      return activeChar[propName] as unknown as T;
    }
    // Fallback to direct config property during transition period
    if (this.config && propName in this.config) {
      return this.config[propName] as unknown as T;
    }
    return defaultValue;
  }

  // Modify applyPersonalityPreset to work with the active character
  applyPersonalityPreset(preset: string): void {
    if (!this.config) return;
    
    // First update the settings in the UI
    this.applySettingsFromPreset(preset);
    
    // Then save the preset selection and all the updated values
    if (preset !== 'custom') {
      // Use the active character if available
      const activeChar = this.getActiveCharacter();
      
      if (activeChar && this.config.active_character_index >= 0) {
        // Create a copy of the active character with updated values
        const updatedChar: Character = {
          ...activeChar,
          personality_preset: preset,
          personality_verbosity: this.settings.verbosity,
          personality_tone: this.settings.tone,
          personality_knowledge_pop_culture: this.settings.knowledge.popCulture,
          personality_knowledge_scifi: this.settings.knowledge.scifi,
          personality_knowledge_history: this.settings.knowledge.history,
          personality_character_inspiration: this.settings.characterInspiration,
          personality_vulgarity: this.settings.vulgarity,
          personality_empathy: this.settings.empathy,
          personality_formality: this.settings.formality,
          personality_confidence: this.settings.confidence,
          personality_ethical_alignment: this.settings.ethicalAlignment,
          personality_moral_alignment: this.settings.moralAlignment
        };
        
        // Create a new characters array with the updated character
        const updatedCharacters = [...this.config.characters];
        updatedCharacters[this.config.active_character_index] = updatedChar;
        
        // Update the config
        this.onConfigChange({characters: updatedCharacters});
      } else {
        // Fallback for transition: update top-level properties
        this.onConfigChange({
          personality_preset: preset,
          personality_verbosity: this.settings.verbosity,
          personality_tone: this.settings.tone,
          personality_knowledge_pop_culture: this.settings.knowledge.popCulture,
          personality_knowledge_scifi: this.settings.knowledge.scifi,
          personality_knowledge_history: this.settings.knowledge.history,
          personality_character_inspiration: this.settings.characterInspiration,
          personality_vulgarity: this.settings.vulgarity,
          personality_empathy: this.settings.empathy,
          personality_formality: this.settings.formality,
          personality_confidence: this.settings.confidence,
          personality_ethical_alignment: this.settings.ethicalAlignment,
          personality_moral_alignment: this.settings.moralAlignment
        });
      }
      
      // Generate a new prompt when explicitly changing presets
      this.updatePrompt();
    } else {
      // Save the preset selection for custom mode
      this.updateActiveCharacterProperty('personality_preset', preset);
    }
  }
}
