import { Component, OnDestroy, OnInit } from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { MatButtonToggleModule } from "@angular/material/button-toggle";
import { MatTooltipModule } from "@angular/material/tooltip";
import { MatTabsModule } from "@angular/material/tabs";
import { ProjectionsService } from "../../services/projections.service";
import { Subscription } from "rxjs";
import * as shipEngineersData from "../../../../../src/assets/ship_engineers.json";
import * as suitEngineersData from "../../../../../src/assets/suit_engineers.json";

@Component({
  selector: "app-engineers-panel",
  standalone: true,
  imports: [CommonModule, FormsModule, MatButtonToggleModule, MatTooltipModule, MatTabsModule],
  templateUrl: "./engineers-panel.component.html",
  styleUrl: "./engineers-panel.component.css",
})
export class EngineersPanelComponent implements OnInit, OnDestroy {
  engineerProgress: any = null;
  engineerFilter: string = 'all';
  onFootEngineerFilter: string = 'all';

  private subscriptions: Subscription[] = [];

  // Engineer databases from JSON files
  private shipEngineersDB = shipEngineersData;
  private suitEngineersDB = suitEngineersData;

  constructor(private projectionsService: ProjectionsService) {}

  ngOnInit(): void {
    this.subscriptions.push(
      this.projectionsService.engineerProgress$.subscribe(engineerProgress => {
        this.engineerProgress = engineerProgress;
      })
    );
  }

  ngOnDestroy(): void {
    this.subscriptions.forEach(sub => sub.unsubscribe());
  }

  getFilteredShipEngineers(): any[] {
    const knownEngineers = this.engineerProgress?.Engineers || [];
    const shipEngineersFromData = knownEngineers.filter((e: any) => e.EngineerID >= 300000 && e.EngineerID < 400000);
    const mergedEngineers = shipEngineersFromData.map((projectionEngineer: any) => {
      const staticEngineer = (this.shipEngineersDB as any)[projectionEngineer.EngineerID.toString()];
      return staticEngineer ? { ...staticEngineer, ...projectionEngineer } : projectionEngineer;
    });
    if (this.engineerFilter === 'all') return mergedEngineers;
    if (this.engineerFilter === 'locked') return mergedEngineers.filter((e: any) => !e.Progress);
    return mergedEngineers.filter((e: any) => e.Progress === this.engineerFilter.charAt(0).toUpperCase() + this.engineerFilter.slice(1));
  }

  getFilteredOnFootEngineers(): any[] {
    const knownEngineers = this.engineerProgress?.Engineers || [];
    const onFootEngineersFromData = knownEngineers.filter((e: any) => e.EngineerID >= 400000 && e.EngineerID < 500000);
    const mergedEngineers = onFootEngineersFromData.map((projectionEngineer: any) => {
      const staticEngineer = (this.suitEngineersDB as any)[projectionEngineer.EngineerID.toString()];
      return staticEngineer ? { ...staticEngineer, ...projectionEngineer } : projectionEngineer;
    });
    if (this.onFootEngineerFilter === 'all') return mergedEngineers;
    if (this.onFootEngineerFilter === 'locked') return mergedEngineers.filter((e: any) => !e.Progress);
    return mergedEngineers.filter((e: any) => e.Progress === this.onFootEngineerFilter.charAt(0).toUpperCase() + this.onFootEngineerFilter.slice(1));
  }

  getEngineerModules(engineerName: string): string {
    const shipEngineerEntry = Object.values(this.shipEngineersDB).find((e: any) => e.Engineer === engineerName);
    if (shipEngineerEntry) {
      if (typeof shipEngineerEntry.Modifies === 'object') return Object.keys(shipEngineerEntry.Modifies).join(', ');
      return shipEngineerEntry.Modifies || 'Unknown';
    }
    return 'Unknown';
  }

  getOnFootEngineerModules(engineerName: string): string {
    const suitEngineerEntry = Object.values(this.suitEngineersDB).find((e: any) => e.Engineer === engineerName);
    if (suitEngineerEntry) {
      if (typeof suitEngineerEntry.Modifies === 'object') return Object.keys(suitEngineerEntry.Modifies).join(', ');
      return suitEngineerEntry.Modifies || 'Unknown';
    }
    return 'Unknown';
  }

  getEngineerLocation(engineerName: string): string {
    const shipEngineerEntry = Object.values(this.shipEngineersDB).find((e: any) => e.Engineer === engineerName);
    if (shipEngineerEntry) return shipEngineerEntry.Location;
    const suitEngineerEntry = Object.values(this.suitEngineersDB).find((e: any) => e.Engineer === engineerName);
    return suitEngineerEntry?.Location || 'Unknown';
  }

  getArray(length: number): any[] { return new Array(length); }
}


