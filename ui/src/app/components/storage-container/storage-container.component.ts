import { Component, OnDestroy, OnInit } from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";

import { MatIconModule } from "@angular/material/icon";
import { MatTabsModule } from "@angular/material/tabs";
import { MatButtonToggleModule } from "@angular/material/button-toggle";
import { MatTooltipModule } from "@angular/material/tooltip";
import { MatProgressBarModule } from "@angular/material/progress-bar";
import { MaterialsPanelComponent } from "../materials-panel/materials-panel.component";
import { StoredModulesComponent } from "../stored-modules/stored-modules.component";
import { EngineersPanelComponent } from "../engineers-panel/engineers-panel.component";
import { EngineeringBlueprintsComponent } from "../engineering-blueprints/engineering-blueprints.component";
import { ProjectionsService } from "../../services/projections.service";
import { Subscription } from "rxjs";

@Component({
  selector: "app-storage-container",
  standalone: true,
  imports: [CommonModule, FormsModule, MatIconModule, MatTabsModule, MatButtonToggleModule, MatTooltipModule, MatProgressBarModule, MaterialsPanelComponent, StoredModulesComponent, EngineersPanelComponent, EngineeringBlueprintsComponent],
  templateUrl: "./storage-container.component.html",
  styleUrl: "./storage-container.component.css",
})
export class StorageContainerComponent implements OnInit, OnDestroy {
  // Projection data
  shipLocker: any = null;
  colonisationConstruction: any = null;
  cargo: any = null;
  shipInfo: any = null;
  storedShips: any = null;
  

  // Collapsible sections state
  sectionsCollapsed = {
    materials: false,
    shipLocker: false,
    engineers: true,
    onFootEngineers: true,
    colonisation: false,
    cargo: true,
    storedModules: true,
    storedShips: true,
    engineeringBlueprints: true,
  };
  
  private subscriptions: Subscription[] = [];

  // Constants
  readonly STORAGE_TAB = 'storage';


  constructor(private projectionsService: ProjectionsService) {}

  ngOnInit(): void {
    // Subscribe to relevant projections
    this.subscriptions.push(
      this.projectionsService.shipLocker$.subscribe(shipLocker => {
        this.shipLocker = shipLocker;
      }),

      this.projectionsService.colonisationConstruction$.subscribe(colonisation => {
        this.colonisationConstruction = colonisation;
      }),
      
      this.projectionsService.cargo$.subscribe(cargo => {
        this.cargo = cargo;
      }),
      
      this.projectionsService.shipInfo$.subscribe(shipInfo => {
        this.shipInfo = shipInfo;
      }),
      
      this.projectionsService.storedShips$.subscribe(storedShips => {
        this.storedShips = storedShips;
      })
    );
  }

  ngOnDestroy(): void {
    this.subscriptions.forEach(sub => sub.unsubscribe());
  }

  formatItemName(name: string): string {
    if (!name) return '';
    return name
      .replace(/_/g, ' ')
      .replace(/([A-Z])/g, ' $1')
      .replace(/\w\S*/g, txt => txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase());
  }

  // Collapsible section methods
  toggleSection(section: keyof typeof this.sectionsCollapsed): void {
    this.sectionsCollapsed[section] = !this.sectionsCollapsed[section];
  }

  // Colonisation methods
  isColonisationActive(): boolean {
    return this.colonisationConstruction && this.colonisationConstruction.StarSystem && this.colonisationConstruction.StarSystem !== 'Unknown';
  }

  getColonisationSystem(): string {
    return this.colonisationConstruction?.StarSystem || 'Unknown System';
  }

  getColonisationStatusText(): string {
    if (this.colonisationConstruction?.ConstructionComplete) return 'Complete';
    if (this.colonisationConstruction?.ConstructionFailed) return 'Failed';
    return 'In Progress';
  }

  getColonisationStatusClass(): string {
    if (this.colonisationConstruction?.ConstructionComplete) return 'status-complete';
    if (this.colonisationConstruction?.ConstructionFailed) return 'status-failed';
    return 'status-active';
  }

  getColonisationProgress(): number {
    return this.colonisationConstruction?.ConstructionProgress || 0;
  }

  getColonisationProgressValue(): number {
    return this.getColonisationProgress() * 100;
  }

  getColonisationResources(): any[] {
    return this.colonisationConstruction?.ResourcesRequired || [];
  }

  formatPercentage(value: number): string {
    return `${(value * 100).toFixed(1)}%`;
  }

  // Cargo methods
  getCargoItems(): any[] {
    return this.cargo?.Inventory || [];
  }

  hasCargoItems(): boolean {
    return this.getCargoItems().length > 0;
  }

  getCargoAmount(): number {
    return this.getCargoItems().reduce((total, item) => total + (item.Count || 0), 0);
  }

  getCargoCapacity(): number {
    return this.shipInfo?.CargoCapacity || this.cargo?.Capacity || 0;
  }

  getCargoPercentage(): number {
    const capacity = this.getCargoCapacity();
    if (capacity === 0) return 0;
    return (this.getCargoAmount() / capacity) * 100;
  }

  formatNumber(num: number | null | undefined): string {
    if (num === null || num === undefined) {
      return "0";
    }

    const value = Number(num);
    if (Number.isNaN(value)) {
      return "0";
    }

    return value.toLocaleString();
  }

  // Stored Ships methods
  getShipsHere(): any[] {
    return this.storedShips?.ShipsHere || [];
  }

  getShipsRemote(): any[] {
    return this.storedShips?.ShipsRemote || [];
  }

  formatTransferTime(seconds: number): string {
    if (!seconds) return '-';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    }
    return `${minutes}m`;
  }

  
} 