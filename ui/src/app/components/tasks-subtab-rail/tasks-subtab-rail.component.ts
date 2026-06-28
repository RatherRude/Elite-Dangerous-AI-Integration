import { CommonModule } from "@angular/common";
import { Component, EventEmitter, Input, Output } from "@angular/core";
import { MatIconModule } from "@angular/material/icon";

export type TasksSubtabId = "missions" | "quests" | "community-goals";

export type TasksSubtab = {
  id: TasksSubtabId;
  icon: string;
  label: string;
};

@Component({
  selector: "app-tasks-subtab-rail",
  standalone: true,
  imports: [CommonModule, MatIconModule],
  templateUrl: "./tasks-subtab-rail.component.html",
  styleUrls: ["./tasks-subtab-rail.component.css"],
})
export class TasksSubtabRailComponent {
  @Input({ required: true }) activeSubtab!: TasksSubtabId;
  @Input({ required: true }) subtabs: readonly TasksSubtab[] = [];
  @Output() activeSubtabChange = new EventEmitter<TasksSubtabId>();

  setActiveSubtab(subtab: TasksSubtabId): void {
    if (subtab !== this.activeSubtab) {
      this.activeSubtabChange.emit(subtab);
    }
  }
}
