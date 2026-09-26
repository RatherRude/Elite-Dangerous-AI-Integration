import { Component, Input, Output, EventEmitter, OnChanges, OnDestroy } from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatSelectModule } from "@angular/material/select";
import { MatSlideToggleModule } from "@angular/material/slide-toggle";
import { MatOptionModule } from "@angular/material/core";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatDialog, MatDialogModule } from "@angular/material/dialog";
import { SettingBase } from "../../services/plugin-settings";
import { AvatarCatalogDialogComponent, AvatarCatalogResult } from "../avatar-catalog-dialog/avatar-catalog-dialog.component";
import { AvatarService } from "../../services/avatar.service";

/**
 * A reusable component for rendering plugin/provider settings fields.
 * Supports toggle, paragraph, text, number, textarea, select, and avatar field types.
 */
@Component({
    selector: "app-settings-field",
    standalone: true,
    imports: [
        CommonModule,
        FormsModule,
        MatFormFieldModule,
        MatInputModule,
        MatSelectModule,
        MatSlideToggleModule,
        MatOptionModule,
        MatButtonModule,
        MatIconModule,
        MatDialogModule,
    ],
    templateUrl: "./settings-field.component.html",
    styleUrl: "./settings-field.component.css",
})
export class SettingsFieldComponent implements OnChanges, OnDestroy {
    /**
     * The field definition containing type, label, and other metadata.
     */
    @Input() field!: SettingBase;
    
    /**
     * The current value of the field.
     */
    @Input() value: any;

    @Input() buttonEnabled: boolean = true;
    
    /**
     * Emitted when the field value changes.
     */
    @Output() valueChange = new EventEmitter<any>();
    @Output() buttonClick = new EventEmitter<void>();

    avatarPreviewUrl: string | null = null;
    private avatarPreviewRequest = 0;

    constructor(
        private dialog: MatDialog,
        private avatarService: AvatarService,
    ) {}

    ngOnChanges(): void {
        if (this.field?.type === "avatar") {
            void this.loadAvatarPreview(this.value);
        }
    }

    ngOnDestroy(): void {
        this.avatarPreviewRequest += 1;
        this.revokeAvatarPreview();
    }

    onValueChange(newValue: any): void {
        this.valueChange.emit(newValue);
    }

    onButtonClick(): void {
        this.buttonClick.emit();
    }

    openAvatarCatalog(): void {
        const dialogRef = this.dialog.open(AvatarCatalogDialogComponent, {
            width: "53.125rem",
            maxWidth: "calc(100vw - 2rem)",
            data: {
                currentAvatarPath: typeof this.value === "string" ? this.value : "",
                defaultAvatarUrl: this.field.default_avatar_url,
                defaultAvatarLabel: this.field.default_avatar_label,
            },
        });

        dialogRef.afterClosed().subscribe((result: AvatarCatalogResult | undefined) => {
            if (!result) {
                return;
            }
            this.onValueChange(result.avatarPath);
            void this.loadAvatarPreview(result.avatarPath);
        });
    }

    private async loadAvatarPreview(selectedReference: unknown): Promise<void> {
        const request = ++this.avatarPreviewRequest;
        const reference = typeof selectedReference === "string" && selectedReference
            ? selectedReference
            : this.field.default_avatar_url;

        if (!reference) {
            this.revokeAvatarPreview();
            return;
        }

        try {
            const nextUrl = await this.avatarService.getAvatar(reference);
            if (request !== this.avatarPreviewRequest) {
                if (nextUrl && this.avatarService.isObjectUrl(nextUrl)) {
                    URL.revokeObjectURL(nextUrl);
                }
                return;
            }
            this.revokeAvatarPreview();
            this.avatarPreviewUrl = nextUrl;
        } catch (error) {
            console.error("Error loading settings avatar preview:", error);
            if (request === this.avatarPreviewRequest) {
                this.revokeAvatarPreview();
            }
        }
    }

    private revokeAvatarPreview(): void {
        if (this.avatarService.isObjectUrl(this.avatarPreviewUrl)) {
            URL.revokeObjectURL(this.avatarPreviewUrl!);
        }
        this.avatarPreviewUrl = null;
    }
}
