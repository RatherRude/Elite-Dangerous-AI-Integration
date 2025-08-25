import { Component, OnDestroy, OnInit } from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { MatIconModule } from "@angular/material/icon";
import { ProjectionsService } from "../../services/projections.service";
import { Subscription } from "rxjs";

@Component({
  selector: "app-stored-modules",
  standalone: true,
  imports: [CommonModule, FormsModule, MatIconModule],
  templateUrl: "./stored-modules.component.html",
  styleUrl: "./stored-modules.component.css",
})
export class StoredModulesComponent implements OnInit, OnDestroy {
  storedModules: any = null;

  searchTerm: string = '';
  sortKey: 'name' | 'system' | 'time' | 'cost' = 'name';
  sortDir: 'asc' | 'desc' = 'asc';

  private subscriptions: Subscription[] = [];

  constructor(private projectionsService: ProjectionsService) {}

  ngOnInit(): void {
    this.subscriptions.push(
      (this.projectionsService.getProjection('StoredModules') || this.projectionsService.projections$)
        .subscribe((value: any) => {
          if (value && value.event === 'StoredModules') {
            this.storedModules = value;
          } else if (value && value['StoredModules']) {
            this.storedModules = value['StoredModules'];
          }
        })
    );
  }

  ngOnDestroy(): void {
    this.subscriptions.forEach(s => s.unsubscribe());
  }

  getItems(): any[] { return this.storedModules?.Items || []; }

  getFilteredItems(): any[] {
    const term = (this.searchTerm || '').toLowerCase();
    const items = this.getItems();
    if (!term) return items;
    return items.filter((item: any) =>
      (item.Name_Localised || item.Name || '').toLowerCase().includes(term) ||
      (item.EngineerModifications || '').toLowerCase().includes(term) ||
      (item.StarSystem || '').toLowerCase().includes(term)
    );
  }

  getSortedFilteredItems(): any[] {
    const items = [...this.getFilteredItems()];
    const dir = this.sortDir === 'asc' ? 1 : -1;
    const key = this.sortKey;
    return items.sort((a: any, b: any) => {
      if (key === 'name') {
        const an = this.formatModuleName(a.Name_Localised || a.Name || '');
        const bn = this.formatModuleName(b.Name_Localised || b.Name || '');
        return an.localeCompare(bn) * dir;
      }
      if (key === 'system') {
        const as = (a.StarSystem || '').toString();
        const bs = (b.StarSystem || '').toString();
        return as.localeCompare(bs) * dir;
      }
      if (key === 'time') {
        const at = typeof a.TransferTime === 'number' ? a.TransferTime : Number.POSITIVE_INFINITY;
        const bt = typeof b.TransferTime === 'number' ? b.TransferTime : Number.POSITIVE_INFINITY;
        return (at - bt) * dir;
      }
      const ac = typeof a.TransferCost === 'number' ? a.TransferCost : Number.POSITIVE_INFINITY;
      const bc = typeof b.TransferCost === 'number' ? b.TransferCost : Number.POSITIVE_INFINITY;
      return (ac - bc) * dir;
    });
  }

  toggleSort(key: 'name' | 'system' | 'time' | 'cost'): void {
    if (this.sortKey === key) {
      this.sortDir = this.sortDir === 'asc' ? 'desc' : 'asc';
    } else {
      this.sortKey = key;
      this.sortDir = 'asc';
    }
  }

  formatModuleName(name: string): string {
    if (!name) return 'Unknown';
    return name.replace(/\$([^;]+);/g, '$1').replace(/_/g, ' ');
  }

  formatEngineering(item: any): string {
    if (!item?.EngineerModifications) return '';
    const mod = this.formatModuleName(item.EngineerModifications);
    const parts: string[] = [mod];
    if (item.Level) parts.push(`G${item.Level}`);
    if (item.Quality || item.Quality === 0) parts.push(`${Math.round((item.Quality as number) * 100)}%`);
    return parts.join(' · ');
  }

  formatTransferTime(seconds: number): string {
    if (!seconds) return 'Unknown';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;
  }

  formatNumber(value: number): string {
    if (value === undefined || value === null) return '0';
    return value.toLocaleString();
  }
}


