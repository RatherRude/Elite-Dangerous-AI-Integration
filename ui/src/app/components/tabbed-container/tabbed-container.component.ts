import { Component } from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatTabsModule } from "@angular/material/tabs";
import { LogContainerComponent } from "../log-container/log-container.component";
import { StatusViewComponent } from "../status-view/status-view.component";

@Component({
    selector: "app-tabbed-container",
    standalone: true,
    imports: [
        CommonModule,
        MatTabsModule,
        LogContainerComponent,
        StatusViewComponent
    ],
    template: `
        <mat-tab-group animationDuration="200ms" class="tab-container">
            <mat-tab label="Logs">
                <app-log-container></app-log-container>
            </mat-tab>
            <mat-tab label="Status">
                <app-status-view></app-status-view>
            </mat-tab>
        </mat-tab-group>
    `,
    styles: [`
        .tab-container {
            height: 100%;
            display: flex;
            flex-direction: column;
        }
        
        ::ng-deep .mat-mdc-tab-body-wrapper {
            flex-grow: 1;
        }
    `]
})
export class TabbedContainerComponent {} 