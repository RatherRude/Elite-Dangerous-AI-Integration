import {
  AfterViewInit,
  Component,
  ElementRef,
  ViewChild,
  OnDestroy
} from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatCardModule } from "@angular/material/card";
import { LoggingService, LogMessage } from "../../services/logging.service.js";
import { Subscription } from "rxjs";

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
export class LogContainerComponent implements AfterViewInit, OnDestroy {
  logs: LogMessage[] = [];
  @ViewChild('logContainer') private logContainer!: ElementRef;
  private subscription: Subscription;
  private shouldScroll = true;

  constructor(private loggingService: LoggingService) {
    // Subscribe to log updates
    this.subscription = this.loggingService.logs$.subscribe((logs) => {
      this.logs = logs;
      this.shouldScroll = true;
      
      // Wait for view to update before scrolling
      setTimeout(() => this.scrollToBottom(), 50);
    });
  }

  ngAfterViewInit() {
    // Initial scroll to bottom
    this.scrollToBottom();
  }

  ngOnDestroy() {
    if (this.subscription) {
      this.subscription.unsubscribe();
    }
  }

  private scrollToBottom(): void {
    if (this.shouldScroll && this.logContainer && this.logContainer.nativeElement) {
      try {
        const container = this.logContainer.nativeElement;
        container.scrollTop = container.scrollHeight;
        this.shouldScroll = false;
      } catch (err) {
        console.error('Error scrolling to bottom:', err);
      }
    }
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
