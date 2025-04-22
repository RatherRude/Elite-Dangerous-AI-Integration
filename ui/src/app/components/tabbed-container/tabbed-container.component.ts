import { Component } from "@angular/core";
import { CommonModule } from "@angular/common";
import { StatusViewComponent } from "../status-view/status-view.component";

@Component({
    selector: "app-tabbed-container",
    standalone: true,
    imports: [
        CommonModule,
        StatusViewComponent
    ],
    template: `
        <app-status-view></app-status-view>
    `,
    styles: [`
        :host {
            height: 100%;
            display: block;
        }
    `]
})
export class TabbedContainerComponent {} 