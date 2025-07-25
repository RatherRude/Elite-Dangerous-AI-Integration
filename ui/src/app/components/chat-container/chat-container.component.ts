import { AfterViewChecked, Component, ElementRef } from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatCardModule } from "@angular/material/card";
import { ChatMessage, ChatService } from "../../services/chat.service.js";

@Component({
  selector: "app-chat-container",
  standalone: true,
  imports: [CommonModule, MatCardModule],
  templateUrl: "./chat-container.component.html",
  styleUrl: "./chat-container.component.css",
})
export class ChatContainerComponent implements AfterViewChecked {
  chat: ChatMessage[] = [];

  private element!: ElementRef;

  constructor(private chatService: ChatService, element: ElementRef) {
    this.element = element;
    this.chatService.chatHistory$.subscribe((chat) => {
      console.log("Logs received", chat);
      this.chat = chat;
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
}
