import { Component, Inject } from "@angular/core";
import { CommonModule } from "@angular/common";
import {
    MAT_DIALOG_DATA,
    MatDialogModule,
    MatDialogRef,
} from "@angular/material/dialog";
import { MatButtonModule } from "@angular/material/button";
import { PluginUpdateInfo } from "../../services/plugin-update.service";

export interface PluginUpdateDialogData {
    plugin_updates: PluginUpdateInfo[];
}

@Component({
    selector: "app-plugin-update-dialog",
    standalone: true,
    imports: [
        CommonModule,
        MatDialogModule,
        MatButtonModule,
    ],
    templateUrl: "./plugin-update-dialog.component.html",
    styleUrl: "./plugin-update-dialog.component.css",
})
export class PluginUpdateDialogComponent {
    constructor(
        public dialogRef: MatDialogRef<PluginUpdateDialogComponent>,
        @Inject(MAT_DIALOG_DATA) public data: PluginUpdateDialogData,
    ) {}

    onNoClick(): void {
        this.dialogRef.close(false);
    }

    onDownloadClick(): void {
        this.dialogRef.close(true);
    }
}
