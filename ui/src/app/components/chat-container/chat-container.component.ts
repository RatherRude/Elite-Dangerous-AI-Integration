import { AfterViewChecked, Component, ElementRef, Input, OnChanges, SimpleChanges, OnDestroy } from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatCardModule } from "@angular/material/card";
import { ChatMessage, ChatService } from "../../services/chat.service.js";
import { Character, CharacterService } from "../../services/character.service.js";
import { Subscription } from "rxjs";

@Component({
  selector: "app-chat-container",
  standalone: true,
  imports: [CommonModule, MatCardModule],
  templateUrl: "./chat-container.component.html",
  styleUrl: "./chat-container.component.css",
})
export class ChatContainerComponent implements AfterViewChecked, OnChanges, OnDestroy {
  @Input() limit?: number;

  chat: ChatMessage[] = [];
  private fullChat: ChatMessage[] = [];
  private shouldScroll: boolean = false;
  private currentCharacter: Character | null = null;
  private characterSubscription?: Subscription;

  private element!: ElementRef<HTMLElement>;

  constructor(
    private chatService: ChatService, 
    private characterService: CharacterService,
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
    });
    
    // Subscribe to character changes
    this.characterSubscription = this.characterService.character$.subscribe((character) => {
      this.currentCharacter = character;
    });

  }

  ngOnDestroy(): void {
    this.characterSubscription?.unsubscribe();
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
}
