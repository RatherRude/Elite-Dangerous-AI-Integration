import { Component, Inject } from "@angular/core";
import { CommonModule } from "@angular/common";
import {
    MAT_DIALOG_DATA,
    MatDialogModule,
    MatDialogRef,
} from "@angular/material/dialog";
import { MatButtonModule } from "@angular/material/button";

export interface UpdateDialogData {
    releaseName: string;
    releaseUrl: string;
}

@Component({
    selector: "app-update-dialog",
    standalone: true,
    imports: [
        CommonModule,
        MatDialogModule,
        MatButtonModule,
    ],
    templateUrl: "./update-dialog.component.html",
    styleUrl: "./update-dialog.component.css",
})
export class UpdateDialogComponent {
    constructor(
        public dialogRef: MatDialogRef<UpdateDialogComponent>,
        @Inject(MAT_DIALOG_DATA) public data: UpdateDialogData,
    ) {}

    onNoClick(): void {
        this.dialogRef.close(false);
    }

    onDownloadClick(): void {
        this.dialogRef.close(true);
    }
}
