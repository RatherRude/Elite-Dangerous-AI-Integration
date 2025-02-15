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

  @ViewChild("logContent")
  private logContent!: ElementRef;

  constructor(private loggingService: LoggingService) {
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
      this.logContent.nativeElement.scrollTop =
        this.logContent.nativeElement.scrollHeight;
    } catch (err) {}
  }

  getLogColor(prefix: string): string {
    switch (prefix) {
      case "ERROR":
        return "#f44336";
      case "WARNING":
        return "#ff9800";
      case "SUCCESS":
        return "#4caf50";
      default:
        return "#ffffff";
    }
  }
}
