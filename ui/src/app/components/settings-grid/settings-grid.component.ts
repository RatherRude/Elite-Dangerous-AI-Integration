import { Component, Input, Output, EventEmitter, inject } from "@angular/core";
import { CommonModule } from "@angular/common";
import { SettingsFieldComponent } from "../settings-field/settings-field.component";
import { SettingsGrid, SettingBase } from "../../services/plugin-settings";
import { TranslateService } from "@ngx-translate/core";
import { resolveSettingText } from "../../services/setting-text";
import { MatExpansionModule } from "@angular/material/expansion";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { PluginContentComponent } from "../plugin-content/plugin-content.component";

/**
 * A reusable component for rendering a settings grid with a label and fields.
 * Used by both plugin-settings and advanced-settings for provider settings.
 */
@Component({
    selector: "app-settings-grid",
    standalone: true,
    imports: [
        CommonModule,
        SettingsFieldComponent,
        MatExpansionModule,
        MatButtonModule,
        MatIconModule,
        PluginContentComponent,
    ],
    templateUrl: "./settings-grid.component.html",
    styleUrl: "./settings-grid.component.css",
})
export class SettingsGridComponent {
    private readonly translate = inject(TranslateService);

    /**
     * The settings grid definition containing label and fields.
     */
    @Input() grid!: SettingsGrid;
    
    /**
     * A function to get the current value for a field key.
     * Signature: (fieldKey: string, defaultValue: any) => any
     */
    @Input() getValue!: (fieldKey: string, defaultValue: any) => any;
    
    /**
     * A function to set a new value for a field key.
     * Signature: (fieldKey: string, value: any) => void
     */
    @Input() setValue!: (fieldKey: string, value: any) => void;

    @Input() onButtonClick?: (fieldKey: string, value?: string) => void;
    @Output() uiAction = new EventEmitter<{action: string; payload: Record<string, unknown>}>();
    
    /**
     * Optional: Header level for the grid label (default: h3).
     * Use 'h2' for main sections, 'h3' for subsections.
     */
    @Input() headerLevel: 'h2' | 'h3' | 'h4' = 'h3';

    /**
     * Optional: CSS class to apply to the grid container.
     */
    @Input() gridClass: string = 'settings-grid';

    onFieldChange(field: SettingBase, value: any): void {
        if (field.key) this.setValue(field.key, value);
    }

    getFieldValue(field: SettingBase): any {
        return field.key ? (this.getValue ? this.getValue(field.key, field.default_value) : field.default_value) : undefined;
    }

    resolve(value: string | null | undefined): string {
        return resolveSettingText(this.translate, value);
    }

    /** Buttons placed on consecutive rows share a single horizontal row;
     * the first button of the grid is the primary (filled) one. */
    fieldGroups(): (
        | { kind: "buttons"; fields: SettingBase[] }
        | { kind: "field"; field: SettingBase }
    )[] {
        const groups: (
            | { kind: "buttons"; fields: SettingBase[] }
            | { kind: "field"; field: SettingBase }
        )[] = [];
        let pendingButtons: SettingBase[] | null = null;
        for (const field of this.grid?.fields ?? []) {
            if (field.type === "button") {
                if (!pendingButtons) {
                    pendingButtons = [];
                    groups.push({ kind: "buttons", fields: pendingButtons });
                }
                pendingButtons.push(field);
            } else {
                pendingButtons = null;
                groups.push({ kind: "field", field });
            }
        }
        return groups;
    }

    firstButtonKey(): string | null {
        const button = (this.grid?.fields ?? []).find(
            (field) => field.type === "button",
        );
        return button?.key ?? null;
    }

    handleEnterSubmit(): void {
        const key = this.firstButtonKey();
        if (key && this.onButtonClick) {
            this.onButtonClick(key);
        }
    }

    handleButtonClick(field: SettingBase): void {
        if (field.key) this.onButtonClick?.(field.key);
    }

    handleListAction(event: { action: string; rowKey: string; value?: string }): void {
        this.onButtonClick?.(`${event.action}:${event.rowKey}`, event.value);
    }
}
