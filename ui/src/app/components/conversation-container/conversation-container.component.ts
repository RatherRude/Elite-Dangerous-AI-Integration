import {
  AfterViewChecked,
  ChangeDetectorRef,
  Component,
  ElementRef,
  ViewChild,
} from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatCardModule } from "@angular/material/card";
import {
  ConversationMessage,
  ConversationService,
  EventMessage,
} from "../../services/conversation.service";

@Component({
  selector: "app-conversation-container",
  standalone: true,
  imports: [CommonModule, MatCardModule],
  templateUrl: "./conversation-container.component.html",
  styleUrl: "./conversation-container.component.css",
})
export class ConversationContainerComponent implements AfterViewChecked {
  conversation: (ConversationMessage | EventMessage)[] = [];

  private element!: ElementRef;

  constructor(
    private conversationService: ConversationService,
    element: ElementRef,
  ) {
    this.element = element;
    this.conversationService.conversation$.subscribe((logs) => {
      console.log("Logs received", logs);
      this.conversation = logs;
      setTimeout(() => {
        this.scrollToBottom();
      }, 0);
    });
  }

  ngAfterViewChecked() {
    this.scrollToBottom();
  }

  private scrollToBottom(): void {
    try {
      const scrollContainer = this.element.nativeElement.parentElement;
      scrollContainer?.scrollTo({
        top: scrollContainer?.scrollHeight,
        behavior: "smooth",
      });
    } catch (err) {}
  }

  public getLogColor(prefix: string): string {
    switch (prefix.toLowerCase()) {
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
}
