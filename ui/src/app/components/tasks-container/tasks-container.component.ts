import { Component, OnDestroy, OnInit } from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatIconModule } from "@angular/material/icon";
import { MatButtonModule } from "@angular/material/button";
import { ProjectionsService } from "../../services/projections.service";
import { Subscription } from "rxjs";

@Component({
  selector: "app-tasks-container",
  standalone: true,
  imports: [CommonModule, MatIconModule, MatButtonModule],
  templateUrl: "./tasks-container.component.html",
  styleUrl: "./tasks-container.component.css",
})
export class TasksContainerComponent implements OnInit, OnDestroy {
  // Projection data (only the two relevant subjects)
  missions: any = null;
  communityGoal: any = null;

  // UI state
  sectionsCollapsed = {
    missions: false,
    communityGoals: false,
  };

  private subscriptions: Subscription[] = [];

  constructor(private projectionsService: ProjectionsService) {}

  ngOnInit(): void {
    // Subscribe only to projections referenced in the template
    this.subscriptions.push(
      this.projectionsService.missions$.subscribe((missions) => {
        this.missions = missions;
      }),
      this.projectionsService.communityGoal$.subscribe((cg) => {
        this.communityGoal = cg;
      })
    );
  }

  ngOnDestroy(): void {
    this.subscriptions.forEach((sub) => sub.unsubscribe());
  }

  // Collapsible section methods
  toggleSection(section: keyof typeof this.sectionsCollapsed): void {
    this.sectionsCollapsed[section] = !this.sectionsCollapsed[section];
  }

  // Missions helpers
  getActiveMissions(): any[] {
    return this.missions?.Active || [];
  }

  // Community Goals helpers
  getCurrentGoals(): any[] {
    return this.communityGoal?.CurrentGoals || [];
  }

  // Formatting helpers
  formatNumber(value: number): string {
    if (!value && value !== 0) return "0";
    return value.toLocaleString();
  }

  formatCr(value: number | undefined): string {
    if (value === undefined || value === null) return "-";
    return `${this.formatNumber(value)} Cr`;
  }

  formatRemainingTime(isoTimestamp: string | undefined): string {
    if (!isoTimestamp) return "Unknown";
    const expiry = Date.parse(isoTimestamp);
    if (Number.isNaN(expiry)) return "Unknown";
    const ms = expiry - Date.now();
    if (ms <= 0) return "Expired";
    const totalMinutes = Math.floor(ms / 60000);
    const days = Math.floor(totalMinutes / (60 * 24));
    const hours = Math.floor((totalMinutes % (60 * 24)) / 60);
    const minutes = totalMinutes % 60;
    if (days > 0) return `${days}d ${hours}h`;
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
  }
}


