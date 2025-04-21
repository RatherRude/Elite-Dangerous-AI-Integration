import { Component, OnDestroy, OnInit } from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatCardModule } from "@angular/material/card";
import { MatDividerModule } from "@angular/material/divider";
import { ProjectionsService } from "../../services/projections.service";
import { Subscription } from "rxjs";

@Component({
    selector: "app-status-view",
    standalone: true,
    imports: [CommonModule, MatCardModule, MatDividerModule],
    template: `
        <div class="status-container">
            @if (projections) {
                @for (projection of projectionEntries; track projection[0]) {
                    <mat-card class="status-card">
                        <mat-card-header>
                            <mat-card-title>{{ projection[0] }}</mat-card-title>
                        </mat-card-header>
                        <mat-card-content>
                            <pre>{{ projection[1] | json }}</pre>
                        </mat-card-content>
                    </mat-card>
                }
            } @else {
                <div class="no-data">Waiting for status data...</div>
            }
        </div>
    `,
    styles: [`
        .status-container {
            height: 100%;
            overflow-y: auto;
            padding: 10px;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        
        .status-card {
            margin-bottom: 10px;
        }
        
        .no-data {
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100%;
            color: rgba(255, 255, 255, 0.6);
        }
        
        pre {
            white-space: pre-wrap;
            word-break: break-word;
            font-family: monospace;
        }
    `]
})
export class StatusViewComponent implements OnInit, OnDestroy {
    projections: Record<string, any> | null = null;
    projectionEntries: [string, any][] = [];
    private subscription: Subscription | null = null;

    constructor(private projectionsService: ProjectionsService) {}

    ngOnInit(): void {
        this.subscription = this.projectionsService.projections$.subscribe(projections => {
            this.projections = projections;
            if (projections) {
                this.projectionEntries = Object.entries(projections);
            } else {
                this.projectionEntries = [];
            }
        });
    }

    ngOnDestroy(): void {
        if (this.subscription) {
            this.subscription.unsubscribe();
        }
    }
} 