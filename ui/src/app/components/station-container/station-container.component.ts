import { Component, OnDestroy, OnInit } from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { MatIconModule } from "@angular/material/icon";
import { MatTabsModule } from "@angular/material/tabs";
import { MatButtonModule } from "@angular/material/button";
import { ProjectionsService } from "../../services/projections.service";
import { Subscription } from "rxjs";

@Component({
  selector: "app-station-container",
  standalone: true,
  imports: [CommonModule, FormsModule, MatIconModule, MatTabsModule, MatButtonModule],
  templateUrl: "./station-container.component.html",
  styleUrl: "./station-container.component.css",
})
export class StationContainerComponent implements OnInit, OnDestroy {
  // Projection data
  storedShips: any = null;
  market: any = null;
  outfitting: any = null;
  shipyard: any = null;
  location: any = null;
  currentStatus: any = null;
  
  // UI state
  selectedStationService: string = 'market';
  marketSearchTerm: string = '';
  outfittingSearchTerm: string = '';
  shipyardSearchTerm: string = '';

  // Collapsible sections state
  sectionsCollapsed = {
    storedShips: false,
    stationFacilities: false
  };
  
  private subscriptions: Subscription[] = [];

  constructor(private projectionsService: ProjectionsService) {}

  ngOnInit(): void {
    // Subscribe to relevant projections
    this.subscriptions.push(
      this.projectionsService.storedShips$.subscribe(storedShips => {
        this.storedShips = storedShips;
      }),
      this.projectionsService.market$.subscribe(market => {
        this.market = market;
      }),
      this.projectionsService.outfitting$.subscribe(outfitting => {
        this.outfitting = outfitting;
      }),
      this.projectionsService.shipyard$.subscribe(shipyard => {
        this.shipyard = shipyard;
      }),
      this.projectionsService.location$.subscribe(location => {
        this.location = location;
      }),
      this.projectionsService.currentStatus$.subscribe(status => {
        this.currentStatus = status;
      })
    );
  }

  ngOnDestroy(): void {
    this.subscriptions.forEach(sub => sub.unsubscribe());
  }

  getStationName(): string {
    // Use Location projection only; support StationName or Station keys
    return this.location?.Station || 'Unknown Station';
  }

  getLocationSystem(): string {
    // Use Location projection only
    return this.location?.StarSystem || 'Unknown System';
  }

  // Check if specific service data is for current station
  isMarketDataCurrent(): boolean {
    const currentStation = this.getStationName();
    return this.market?.StationName === currentStation;
  }

  isOutfittingDataCurrent(): boolean {
    const currentStation = this.getStationName();
    return this.outfitting?.StationName === currentStation;
  }

  isShipyardDataCurrent(): boolean {
    const currentStation = this.getStationName();
    return this.shipyard?.StationName === currentStation;
  }

  isDockedAtStation(): boolean {
    return Boolean(this.currentStatus?.flags?.Docked === true);
  }

  showStationService(service: string): void {
    this.selectedStationService = service;
  }

  // Collapsible section methods
  toggleSection(section: keyof typeof this.sectionsCollapsed): void {
    this.sectionsCollapsed[section] = !this.sectionsCollapsed[section];
  }

  // Stored Ships methods
  getShipsHere(): any[] {
    return this.storedShips?.ShipsHere || [];
  }

  getShipsRemote(): any[] {
    return this.storedShips?.ShipsRemote || [];
  }

  isStoredShipsAtCurrentLocation(): boolean {
    const currentStationName = this.getStationName();
    const storedShipsStation = this.storedShips?.StationName;
    
    // Check if stored ships data matches current station
    return storedShipsStation && storedShipsStation === currentStationName;
  }

  // Market methods
  getFilteredMarketItems(): any[] {
    const items = this.market?.Items || [];
    if (!this.marketSearchTerm) return items;
    
    const searchTerm = this.marketSearchTerm.toLowerCase();
    return items.filter((item: any) => 
      (item.Name_Localised || item.Name || '').toLowerCase().includes(searchTerm) ||
      (item.Category_Localised || item.Category || '').toLowerCase().includes(searchTerm)
    );
  }

  // Outfitting methods
  getFilteredOutfittingItems(): any[] {
    const items = this.outfitting?.Items || [];
    if (!this.outfittingSearchTerm) return items;
    
    const searchTerm = this.outfittingSearchTerm.toLowerCase();
    return items.filter((item: any) => 
      (item.Name || '').toLowerCase().includes(searchTerm)
    );
  }

  // Shipyard methods
  getFilteredShipyardItems(): any[] {
    const items = this.shipyard?.PriceList || [];
    if (!this.shipyardSearchTerm) return items;
    
    const searchTerm = this.shipyardSearchTerm.toLowerCase();
    return items.filter((item: any) => 
      (item.ShipType_Localised || item.ShipType || '').toLowerCase().includes(searchTerm)
    );
  }

  // Formatting methods
  formatNumber(value: number): string {
    if (!value) return '0';
    return value.toLocaleString();
  }

  formatItemName(name: string): string {
    if (!name) return 'Unknown';
    return name.replace(/\$([^;]+);/g, '$1').replace(/_/g, ' ');
  }

  formatModuleName(name: string): string {
    if (!name) return 'Unknown';
    return name.replace(/\$([^;]+);/g, '$1').replace(/_/g, ' ');
  }

  formatTransferTime(seconds: number): string {
    if (!seconds) return 'Unknown';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    
    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    }
    return `${minutes}m`;
  }
} 