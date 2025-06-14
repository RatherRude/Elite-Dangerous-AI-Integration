import { Component } from "@angular/core";
import { CommonModule } from "@angular/common";
import {
    MatDialogModule,
    MatDialogRef,
} from "@angular/material/dialog";
import { MatButtonModule } from "@angular/material/button";

@Component({
    selector: "app-telemetry-dialog",
    standalone: true,
    imports: [
        CommonModule,
        MatDialogModule,
        MatButtonModule,
    ],
    templateUrl: "./telemetry-dialog.component.html",
    styleUrl: "./telemetry-dialog.component.css",
})
export class TelemetryDialogComponent {
    constructor(
        public dialogRef: MatDialogRef<TelemetryDialogComponent>,
    ) {}

    onDeclineClick(): void {
        this.dialogRef.close(false);
    }

    onAcceptClick(): void {
        this.dialogRef.close(true);
    }
} 