import { Component, Input, Output, EventEmitter, inject, forwardRef } from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatSelectModule } from "@angular/material/select";
import { MatSlideToggleModule } from "@angular/material/slide-toggle";
import { MatOptionModule } from "@angular/material/core";
import { MatButtonModule } from "@angular/material/button";
import { TranslateService } from "@ngx-translate/core";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressBarModule } from "@angular/material/progress-bar";
import { SettingBase, ListAction, ListRow } from "../../services/plugin-settings";
import { resolveModuleName, resolveSettingText } from "../../services/setting-text";
import { PluginContentComponent } from "../plugin-content/plugin-content.component";
import { UIText } from "../../services/plugin-ui";

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
        MatButtonModule,
        MatIconModule,
        MatProgressBarModule,
        forwardRef(() => PluginContentComponent),
    ],
    templateUrl: "./settings-field.component.html",
    styleUrl: "./settings-field.component.css",
})
export class SettingsFieldComponent {
    private readonly translate = inject(TranslateService);

    /**
     * The field definition containing type, label, and other metadata.
     */
    @Input() field!: SettingBase;

    /**
     * The current value of the field.
     */
    @Input() value: any;

    @Input() buttonEnabled: boolean = true;
    @Input() primary: boolean = false;
    @Input() getValue: (key: string, fallback: unknown) => unknown = (_key, fallback) => fallback;
    @Input() setValue: (key: string, value: unknown) => void = (key, value) =>
        this.uiAction.emit({action: "ui_changed", payload: {key, value}});
    @Input() onButtonClick?: (key: string, value?: string) => void;

    private readonly collapsedGroups = new Set<string>();

    /**
     * Emitted when the field value changes.
     */
    @Output() valueChange = new EventEmitter<any>();
    @Output() buttonClick = new EventEmitter<void>();
    @Output() listAction = new EventEmitter<{ action: string; rowKey: string; value?: string }>();
    @Output() submitRequested = new EventEmitter<void>();
    @Output() uiAction = new EventEmitter<{action: string; payload: Record<string, unknown>}>();

    editingRowKey: string | null = null;
    editingAction: ListAction | null = null;
    editValue = "";

    text(value?: UIText): string {
        if (!value) return "";
        const params = Object.fromEntries(Object.entries(value.params ?? {}).map(([key, param]) =>
            [key, typeof param === "object" ? this.text(param) : param]));
        if (value.key) {
            const translated = this.translate.instant(value.key, params);
            if (translated !== value.key) return translated;
            if (!value.text && !value.localized) return value.key;
        }
        return value.localized?.[this.translate.currentLang] ?? value.localized?.["en"] ?? value.text ?? "";
    }

    percentage(): number {
        return this.field.maximum ? Math.max(0, Math.min(100, (this.field.value ?? 0) / this.field.maximum * 100)) : 0;
    }

    resolve(
        value: string | null | undefined,
        params?: { [name: string]: string | number },
    ): string {
        return resolveSettingText(this.translate, value, params);
    }

    optionLabel(option: { label?: string | null }): string {
        return this.resolve(option?.label);
    }

    onValueChange(newValue: any): void {
        this.valueChange.emit(newValue);
    }

    onTextKeydown(event: KeyboardEvent): void {
        // Enter validates, Shift+Enter inserts a newline.
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            this.submitRequested.emit();
        }
    }

    handleClick(): void {
        if (this.field.action) this.uiAction.emit({action: this.field.action, payload: this.field.payload ?? {}});
        else this.buttonClick.emit();
    }

    hasUnknownSelectValue(): boolean {
        return !this.field.multi_select
            && this.value !== undefined
            && this.value !== null
            && !this.field.select_options?.some(option => option.value === this.value);
    }

    onListAction(action: ListAction, row: ListRow): void {
        if (action.inline_edit) {
            this.editingAction = action;
            this.editingRowKey = row.key;
            this.editValue = row.title;
            return;
        }
        this.listAction.emit({ action: action.action, rowKey: row.key });
    }

    confirmRowEdit(row: ListRow): void {
        const action = this.editingAction;
        this.editingRowKey = null;
        this.editingAction = null;
        if (!action) {
            return;
        }
        this.listAction.emit({ action: action.action, rowKey: row.key, value: this.editValue });
    }

    cancelRowEdit(): void {
        this.editingRowKey = null;
        this.editingAction = null;
        this.editValue = "";
    }

    rowsWithGroups(
        items: ListRow[] | null | undefined,
    ): { row: ListRow; header?: string; count?: number; groupPending?: boolean }[] {
        const counts = new Map<string, number>();
        const pending = new Map<string, boolean>();
        for (const row of items ?? []) {
            if (row.group) {
                counts.set(row.group, (counts.get(row.group) ?? 0) + 1);
                if (row.pending) {
                    pending.set(row.group, true);
                }
            }
        }
        const entries: {
            row: ListRow;
            header?: string;
            count?: number;
            groupPending?: boolean;
        }[] = [];
        let lastGroup: string | undefined = undefined;
        for (const row of items ?? []) {
            const header = row.group && row.group !== lastGroup ? row.group : undefined;
            lastGroup = row.group ?? lastGroup;
            entries.push({
                row,
                header,
                count: header !== undefined ? counts.get(row.group as string) : undefined,
                groupPending: header !== undefined ? pending.get(row.group as string) : undefined,
            });
        }
        return entries;
    }

    toggleGroup(group: string): void {
        if (this.collapsedGroups.has(group)) {
            this.collapsedGroups.delete(group);
        } else {
            this.collapsedGroups.add(group);
        }
    }

    rowTitle(row: ListRow): string {
        const base = resolveModuleName(this.translate, row.title_key, row.title);
        return row.suffix ? `${base} ${row.suffix}` : base;
    }

    isGroupCollapsed(group: string | undefined): boolean {
        return group !== undefined && this.collapsedGroups.has(group);
    }

    groupCountLabel(entry: { header?: string; count?: number }): string {
        if (entry.header === undefined || entry.count === undefined) {
            return "";
        }
        const key = entry.count === 1 ? this.field.count_labels?.one ?? 'common.itemsOne' : this.field.count_labels?.many ?? 'common.itemsMany';
        return this.resolve(key, { count: entry.count });
    }
}
