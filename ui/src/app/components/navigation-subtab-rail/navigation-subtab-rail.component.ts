import { CommonModule } from "@angular/common";
import { Component, EventEmitter, Input, Output } from "@angular/core";
import { MatIconModule } from "@angular/material/icon";

export type NavigationSubtabId = "location" | "list" | "route";

type NavigationSubtab = {
    id: NavigationSubtabId;
    icon: string;
    label: string;
};

@Component({
    selector: "app-navigation-subtab-rail",
    standalone: true,
    imports: [CommonModule, MatIconModule],
    templateUrl: "./navigation-subtab-rail.component.html",
    styleUrls: ["./navigation-subtab-rail.component.scss"],
})
export class NavigationSubtabRailComponent {
    @Input({ required: true }) activeSubtab!: NavigationSubtabId;
    @Output() activeSubtabChange = new EventEmitter<NavigationSubtabId>();

    readonly subtabs: NavigationSubtab[] = [
        { id: "location", icon: "place", label: "Location" },
        { id: "list", icon: "view_list", label: "List" },
        { id: "route", icon: "route", label: "Nav Route" },
    ];

    setActiveSubtab(subtab: NavigationSubtabId): void {
        if (subtab !== this.activeSubtab) {
            this.activeSubtabChange.emit(subtab);
        }
    }
}
