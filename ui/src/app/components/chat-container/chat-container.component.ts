import { AfterViewChecked, ChangeDetectionStrategy, ChangeDetectorRef, Component, ElementRef, Input, OnChanges, SimpleChanges, OnDestroy } from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatCardModule } from "@angular/material/card";
import { ChatMessage, ChatService } from "../../services/chat.service.js";
import { Character, CharacterService, ConfigWithCharacters } from "../../services/character.service.js";
import { Subscription } from "rxjs";
import { Config, ConfigService } from "../../services/config.service.js";

@Component({
  selector: "app-chat-container",
  standalone: true,
  imports: [CommonModule, MatCardModule],
  templateUrl: "./chat-container.component.html",
  styleUrl: "./chat-container.component.css",
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ChatContainerComponent implements AfterViewChecked, OnChanges, OnDestroy {
  @Input() limit?: number;

  chat: ChatMessage[] = [];
  private fullChat: ChatMessage[] = [];
  private shouldScroll: boolean = false;
  private currentCharacter: Character | null = null;
  private characterSubscription?: Subscription;
  private configSubscription?: Subscription;
  private characterColorMap: Record<string, string> = {};

  private element!: ElementRef<HTMLElement>;

  constructor(
    private chatService: ChatService, 
    private characterService: CharacterService,
    private configService: ConfigService,
    private cd: ChangeDetectorRef,
    element: ElementRef<HTMLElement>
  ) {
    this.element = element;
    this.chatService.chatHistory$.subscribe((chat) => {
      console.log("chat received", chat);
      this.fullChat = chat;
      const previousLength = this.chat.length;
      this.applyLimit();
      // Only scroll if new displayable messages were added
      if (this.chat.length > previousLength) {
        this.shouldScroll = true;
      }
      this.cd.markForCheck();
    });
    
    // Subscribe to character changes
    this.characterSubscription = this.characterService.character$.subscribe((character) => {
      this.currentCharacter = character;
    });

    this.configSubscription = this.configService.config$.subscribe((config) => {
      this.characterColorMap = this.buildCharacterColorMap(config as ConfigWithCharacters | null);
      this.cd.markForCheck();
    });
  }

  ngOnDestroy(): void {
    this.characterSubscription?.unsubscribe();
    this.configSubscription?.unsubscribe();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if ("limit" in changes) {
      const previousLength = this.chat.length;
      this.applyLimit();
      // Scroll if limit change affects displayed messages
      if (this.chat.length !== previousLength) {
        this.shouldScroll = true;
      }
    }
  }

  ngAfterViewChecked() {
    // Only scroll when explicitly triggered by new displayable messages
    if (this.shouldScroll) {
      this.scrollToBottom();
      this.shouldScroll = false;
    }
  }

  private applyLimit(): void {
    if (typeof this.limit === "number" && this.limit > 0) {
      this.chat = this.fullChat.filter(value => ['covas', 'cmdr', 'action'].includes(value.role)).slice(-this.limit);
    } else {
      this.chat = this.fullChat;
    }
  }

  private scrollToBottom(): void {
    try {
      const hostElement = this.element.nativeElement;
      const scrollContainer = (typeof this.limit === "number" && this.limit > 0)
        ? hostElement
        : hostElement.parentElement;

      scrollContainer?.scrollTo({
        top: scrollContainer?.scrollHeight ?? 0,
        behavior: "smooth",
      });
    } catch (err) {}
  }

  public getLogColor(role: string): string {
    switch (role.toLowerCase()) {
      case "error":
        return "red";
      case "warn":
        return "orange";
      case "info":
        return "#9C27B0";
      case "covas":
        return "#2196F3";
      case "event":
        return "#4CAF50";
      case "cmdr":
        return "#E91E63";
      case "action":
        return "#FF9800";
      default:
        return "inherit";
    }
  }

  public getEventStatus(eventName: string): 'enabled' | 'disabled' | 'not-enabled' {
    if (!this.currentCharacter) {
      return 'enabled';
    }

    // Check if event is in disabled list
    if (this.currentCharacter.disabled_game_events?.includes(eventName)) {
      return 'disabled';
    }

    // Check if event is enabled in game_events
    if (this.currentCharacter.game_events && this.currentCharacter.game_events[eventName] === true) {
      return 'enabled';
    }

    // Event exists but is not enabled
    return 'not-enabled';
  }

  public getEventClass(role: string, message: string): string {
    if (role.toLowerCase() === 'event') {
      const status = this.getEventStatus(message);
      if (status === 'disabled') {
        return 'event-disabled';
      } else if (status === 'not-enabled') {
        return 'event-not-enabled';
      }
      return 'event-enabled';
    }
    return '';
  }

  public formatMessageSegments(message: string): { text: string; color: string }[] {
    const defaultColor = "#ffffff";
    const segments: { text: string; color: string }[] = [];
    let currentColor = defaultColor;
    const regex = /\(([^)]+)\)/g;
    let lastIndex = 0;
    let match: RegExpExecArray | null;

    while ((match = regex.exec(message)) !== null) {
      this.appendSegments(segments, message.slice(lastIndex, match.index), currentColor);

      const label = match[1]?.trim().toLowerCase() ?? "";
      currentColor = label && this.characterColorMap[label] ? this.characterColorMap[label] : defaultColor;
      lastIndex = regex.lastIndex;
    }

    this.appendSegments(segments, message.slice(lastIndex), currentColor);

    if (segments.length === 0) {
      segments.push({ text: "", color: defaultColor });
    }

    return segments;
  }

  private appendSegments(
    segments: { text: string; color: string }[],
    rawText: string,
    color: string,
  ): void {
    if (!rawText) return;

    for (const part of rawText.split(/\r?\n/)) {
      const trimmed = part.trim();
      if (!trimmed) continue;
      segments.push({ text: trimmed, color });
    }
  }

  private buildCharacterColorMap(config: ConfigWithCharacters | null): Record<string, string> {
    const map: Record<string, string> = {};
    if (!config || !Array.isArray(config.characters)) {
      return map;
    }

    const activeIndexes = Array.isArray(config.active_characters) && config.active_characters.length > 0
      ? config.active_characters
      : (typeof config.active_character_index === "number" ? [config.active_character_index] : []);

    for (const idx of activeIndexes) {
      if (idx === undefined || idx === null) continue;
      const character = config.characters[idx];
      if (!character || !character.name) continue;
      const color = character.color ? this.normalizeColor(character.color) : "#ffffff";
      map[character.name.toLowerCase()] = color;
    }

    return map;
  }

  private normalizeColor(value: string): string {
    const trimmed = value?.trim() ?? "";
    if (!trimmed) return "#ffffff";
    return trimmed.startsWith("#") ? trimmed : `#${trimmed}`;
  }
}
