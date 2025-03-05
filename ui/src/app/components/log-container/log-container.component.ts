import {
  AfterViewChecked,
  ChangeDetectorRef,
  Component,
  ElementRef,
  ViewChild,
} from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatCardModule } from "@angular/material/card";
import { LoggingService, LogMessage } from "../../services/logging.service.js";

export interface LogEntry {
  type: string;
  timestamp: string;
  prefix: string;
  message: string;
}

@Component({
  selector: "app-log-container",
  standalone: true,
  imports: [CommonModule, MatCardModule],
  templateUrl: "./log-container.component.html",
  styleUrl: "./log-container.component.css",
})
export class LogContainerComponent implements AfterViewChecked {
  logs: LogMessage[] = [];

  private element!: ElementRef;

  constructor(private loggingService: LoggingService, element: ElementRef) {
    this.element = element;
    this.loggingService.logs$.subscribe((logs) => {
      console.log("Logs received", logs);
      this.logs = logs;
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
