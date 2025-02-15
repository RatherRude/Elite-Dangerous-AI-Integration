import { AfterViewInit, Component, ElementRef, ViewChild } from "@angular/core";
import { CommonModule } from "@angular/common";
import { RouterOutlet } from "@angular/router";
import { TauriService } from "./services/tauri.service";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatToolbarModule } from "@angular/material/toolbar";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressBarModule } from "@angular/material/progress-bar";
import { LogContainerComponent } from "./components/log-container/log-container.component";
import { LoggingService, type LogMessage } from "./services/logging.service";
import { SettingsMenuComponent } from "./components/settings-menu/settings-menu.component";

@Component({
  selector: "app-root",
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule,
    MatCardModule,
    MatToolbarModule,
    MatIconModule,
    MatProgressBarModule,
    LogContainerComponent,
    SettingsMenuComponent,
  ],
  templateUrl: "./app.component.html",
  styleUrl: "./app.component.css",
})
export class AppComponent implements AfterViewInit {
  @ViewChild("logContent")
  private logContent?: ElementRef;

  isLoading = false;
  isRunning = false;

  constructor(
    private tauri: TauriService,
    private loggingService: LoggingService,
  ) {
    // Subscribe to the running state
    this.tauri.isRunning$.subscribe(
      (running) => this.isRunning = running,
    );

    this.tauri.runExe();
  }

  ngAfterViewInit() {
    // Initial scroll to bottom
    this.scrollToBottom();
  }

  private scrollToBottom(): void {
    try {
      if (this.logContent) {
        const element = this.logContent.nativeElement;
        element.scrollTop = element.scrollHeight;
      }
    } catch (err) {
      console.error("Error scrolling to bottom:", err);
    }
  }

  async start(): Promise<void> {
    try {
      this.isLoading = true;
      this.loggingService.clearLogs(); // Clear logs when starting
      await this.tauri.send_start_signal();
    } catch (error) {
      console.error("Failed to start:", error);
    } finally {
      this.isLoading = false;
    }
  }

  async stop(): Promise<void> {
    try {
      this.isLoading = true;
      await this.tauri.restart_process();
    } catch (error) {
      console.error("Failed to stop:", error);
    } finally {
      this.isLoading = false;
    }
  }

  getLogColor(prefix: string): string {
    return this.loggingService.getLogColor(prefix);
  }
}
