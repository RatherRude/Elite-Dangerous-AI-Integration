import { CommonModule } from "@angular/common";
import { Component, EventEmitter, Input, Output } from "@angular/core";
import { MatIconModule } from "@angular/material/icon";

@Component({
  selector: "app-fleet-carrier-card",
  standalone: true,
  imports: [CommonModule, MatIconModule],
  templateUrl: "./fleet-carrier-card.component.html",
  styleUrl: "./fleet-carrier-card.component.css",
})
export class FleetCarrierCardComponent {
  private readonly percentKeys = new Set([
    "ReservePercent",
    "TaxRate_rearm",
    "TaxRate_refuel",
    "TaxRate_repair",
    "TaxRate_shipyard",
  ]);
  @Input() carrier: any = null;
  @Input() collapsed = true;
  @Output() toggle = new EventEmitter<number>();

  onToggle(): void {
    const carrierId = this.carrier?.CarrierID;
    if (carrierId !== undefined && carrierId !== null) {
      this.toggle.emit(carrierId);
    }
  }

  getCarrierTitle(): string {
    const name = this.carrier?.Name || "Unknown";
    const typeLabel = this.getCarrierTypeLabel(this.carrier?.CarrierType);
    const starSystem = this.carrier?.StarSystem || "Unknown";
    return `${name} (${typeLabel}): ${starSystem} system`;
  }

  getCarrierTypeLabel(carrierType: string | null | undefined): string {
    if (carrierType === "FleetCarrier") return "Personal Fleet Carrier";
    if (carrierType === "SquadronCarrier") return "Squadron Fleet Carrier";
    return carrierType && carrierType !== "Unknown" ? carrierType : "Fleet Carrier";
  }

  formatYesNo(value: boolean | null | undefined): string {
    return value ? "Yes" : "No";
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

  formatValue(value: any): string {
    if (value === null || value === undefined || value === "") {
      return "-";
    }
    if (typeof value === "number") {
      return this.formatNumber(value);
    }
    if (typeof value === "boolean") {
      return value ? "Yes" : "No";
    }
    return String(value);
  }

  getFuelLevelDisplay(): string {
    const current = this.formatValue(this.carrier?.FuelLevel);
    return `${current} / 1000`;
  }

  formatFinanceValue(key: unknown, value: any): string {
    const keyString = typeof key === "string" ? key : String(key);
    if (this.percentKeys.has(keyString)) {
      if (value === null || value === undefined || value === "") {
        return "-";
      }
      const numeric = Number(value);
      if (Number.isNaN(numeric)) {
        return "-";
      }
      return `${numeric}%`;
    }
    return this.formatValue(value);
  }

  getActiveCrew(crewList: any[] | null | undefined): any[] {
    return (crewList || []).filter(crew => crew?.Activated);
  }

  getCrewDisplay(crew: any): string {
    const name = crew?.CrewName || "Unknown";
    if (crew?.Enabled === false) {
      return `${name} (Disabled)`;
    }
    return name;
  }

  getTradeOrderLabel(orderValue: any, fallbackKey: unknown): string {
    const keyString = typeof fallbackKey === "string" ? fallbackKey : String(fallbackKey);
    return orderValue?.Commodity_Localised || orderValue?.Commodity || keyString;
  }
}
