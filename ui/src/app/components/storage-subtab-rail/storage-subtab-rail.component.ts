import { CommonModule } from "@angular/common";
import { Component, EventEmitter, Input, Output } from "@angular/core";
import { MatIconModule } from "@angular/material/icon";

export type StorageSubtabId =
  | "colonisation"
  | "cargo"
  | "carriers"
  | "materials"
  | "locker"
  | "engineers"
  | "blueprints"
  | "modules"
  | "ships";

export type StorageSubtab = {
  id: StorageSubtabId;
  icon: string;
  label: string;
};

@Component({
  selector: "app-storage-subtab-rail",
  standalone: true,
  imports: [CommonModule, MatIconModule],
  templateUrl: "./storage-subtab-rail.component.html",
  styleUrls: ["./storage-subtab-rail.component.css"],
})
export class StorageSubtabRailComponent {
  @Input({ required: true }) activeSubtab!: StorageSubtabId;
  @Input({ required: true }) subtabs: readonly StorageSubtab[] = [];
  @Output() activeSubtabChange = new EventEmitter<StorageSubtabId>();

  setActiveSubtab(subtab: StorageSubtabId): void {
    if (subtab !== this.activeSubtab) {
      this.activeSubtabChange.emit(subtab);
    }
  }
}
