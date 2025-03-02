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
  ModelValidationMessage,
  SystemInfo,
} from "../../services/config.service";
import { Subscription } from "rxjs";
import { MatButtonModule } from "@angular/material/button";
import { KeyValue, KeyValuePipe } from "@angular/common";
import { MatExpansionModule } from "@angular/material/expansion";
import { MatSnackBar, MatSnackBarModule } from "@angular/material/snack-bar";
import { CommonModule } from "@angular/common";

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
  ],
  templateUrl: "./settings-menu.component.html",
  styleUrl: "./settings-menu.component.css",
})
export class SettingsMenuComponent implements OnInit, OnDestroy {
  config: Config | null = null;
  system: SystemInfo | null = null;
  hideApiKey = true;
  private configSubscription?: Subscription;
  private systemSubscription?: Subscription;
  private validationSubscription?: Subscription;
  expandedSection: string | null = null;
  filteredGameEvents: Record<string, Record<string, 'critical' | 'informative' | 'background' | 'disabled'>> = {};
  eventSearchQuery: string = "";

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
        this.filteredGameEvents = this.config?.game_events || {};
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
          const snackBarDuration = 8000;
          const snackBarClass = validation.status === "error"
            ? "validation-error-snackbar"
            : validation.status === "fallback"
            ? "validation-fallback-snackbar"
            : "validation-upgrade-snackbar";

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
    if (partialConfig.stt_provider) {
      if (partialConfig.stt_provider === "openai") {
        partialConfig.stt_endpoint = "https://api.openai.com/v1";
        partialConfig.stt_model_name = "whisper-1";
        partialConfig.stt_api_key = "";
      }
      if (partialConfig.stt_provider === "custom") {
        partialConfig.stt_endpoint = "https://api.openai.com/v1";
        partialConfig.stt_model_name = "whisper-1";
        partialConfig.stt_api_key = "";
      }
      if (partialConfig.stt_provider === "none") {
        partialConfig.stt_endpoint = "";
        partialConfig.stt_model_name = "";
        partialConfig.stt_api_key = "";
      }
    }
    if (partialConfig.tts_provider) {
      if (partialConfig.tts_provider === "openai") {
        partialConfig.tts_endpoint = "https://api.openai.com/v1";
        partialConfig.tts_model_name = "tts-1";
        partialConfig.tts_voice = "nova";
        partialConfig.tts_api_key = "";
      }
      if (partialConfig.tts_provider === "edge-tts") {
        partialConfig.tts_endpoint = "";
        partialConfig.tts_model_name = "";
        partialConfig.tts_voice = "en-GB-SoniaNeural";
        partialConfig.tts_api_key = "";
      }
      if (partialConfig.tts_provider === "custom") {
        partialConfig.tts_endpoint = "https://api.openai.com/v1";
        partialConfig.tts_model_name = "tts-1";
        partialConfig.tts_voice = "nova";
        partialConfig.tts_api_key = "";
      }
      if (partialConfig.tts_provider === "none") {
        partialConfig.tts_endpoint = "";
        partialConfig.tts_model_name = "";
        partialConfig.tts_voice = "";
        partialConfig.tts_api_key = "";
      }
    }
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

  filterEvents(query: string) {
    if (!query) {
      this.filteredGameEvents = this.config?.game_events || {};
      this.expandedSection = null; // Collapse all sections when search is empty
      return;
    }

    // Only filter and expand if search term is 3 or more characters
    if (query.length >= 3) {
      this.filteredGameEvents = {};
      const searchTerm = query.toLowerCase();

      for (
        const [sectionKey, events] of Object.entries(
          this.config?.game_events || {},
        )
      ) {
        const matchingEvents: typeof this.filteredGameEvents[string] = {};
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
      this.filteredGameEvents = this.config?.game_events || {};
    }
  }

  clearEventSearch() {
    this.eventSearchQuery = "";
    this.filteredGameEvents = this.config?.game_events || {};
    this.expandedSection = null; // Collapse all sections when search is cleared
  }
}
