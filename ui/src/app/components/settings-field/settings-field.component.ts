import { Component, Input, Output, EventEmitter } from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatSelectModule } from "@angular/material/select";
import { MatSlideToggleModule } from "@angular/material/slide-toggle";
import { MatOptionModule } from "@angular/material/core";
import { SettingBase } from "../../services/plugin-settings";

/**
 * A reusable component for rendering plugin/provider settings fields.
 * Supports toggle, paragraph, text, number, textarea, and select field types.
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
    ],
    templateUrl: "./settings-field.component.html",
    styleUrl: "./settings-field.component.css",
})
export class SettingsFieldComponent {
    /**
     * The field definition containing type, label, and other metadata.
     */
    @Input() field!: SettingBase;
    
    /**
     * The current value of the field.
     */
    @Input() value: any;
    
    /**
     * Emitted when the field value changes.
     */
    @Output() valueChange = new EventEmitter<any>();

    onValueChange(newValue: any): void {
        this.valueChange.emit(newValue);
    }
}
