import { Component, Input, Output, EventEmitter, inject } from "@angular/core";
import { CommonModule } from "@angular/common";
import { UIGrid } from "../../services/plugin-ui";
import { TranslateService } from "@ngx-translate/core";
import { resolveSettingText } from "../../services/setting-text";
import { MatExpansionModule } from "@angular/material/expansion";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { PluginContentComponent } from "../plugin-content/plugin-content.component";
import { MatTooltipModule } from "@angular/material/tooltip";

/**
 * A reusable component for rendering a settings grid with a label and fields.
 * Used by both plugin-settings and advanced-settings for provider settings.
 */
@Component({
    selector: "app-settings-grid",
    standalone: true,
    imports: [
        CommonModule,
        MatExpansionModule,
        MatButtonModule,
        MatIconModule,
        PluginContentComponent,
        MatTooltipModule,
    ],
    templateUrl: "./settings-grid.component.html",
    styleUrl: "./settings-grid.component.css",
})
export class SettingsGridComponent {
    private readonly translate = inject(TranslateService);

    /**
     * The settings grid definition containing label and fields.
     */
    @Input() grid!: UIGrid;
    
    /**
     * A function to get the current value for a field key.
     * Signature: (fieldKey: string, defaultValue: any) => any
     */
    @Input() getValue: (fieldKey: string, defaultValue: unknown) => unknown = (_key, fallback) => fallback;
    
    /**
     * A function to set a new value for a field key.
     * Signature: (fieldKey: string, value: any) => void
     */
    @Input() setValue: (fieldKey: string, value: unknown) => void = (key, value) =>
        this.uiAction.emit({action: "ui_changed", payload: {key, value}});

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

    resolve(value: string | null | undefined): string {
        return resolveSettingText(this.translate, value);
    }

}
