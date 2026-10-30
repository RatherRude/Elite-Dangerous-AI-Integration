import { Component, EventEmitter, Input, Output, forwardRef } from "@angular/core";
import { UIComponent } from "../../services/plugin-ui";
import { SettingsFieldComponent } from "../settings-field/settings-field.component";

@Component({
  selector: "app-plugin-content",
  standalone: true,
  host: {"[class.inline]": "inline"},
  imports: [forwardRef(() => SettingsFieldComponent)],
  template: `
    @for (node of nodes; track $index) {
      <app-settings-field [field]="node" [getValue]="getValue" [setValue]="setValue"
        [onButtonClick]="onButtonClick" [value]="node.key ? getValue(node.key, node.default_value) : undefined"
        (valueChange)="change(node, $event)" (buttonClick)="click(node)"
        (listAction)="onButtonClick?.($event.action + ':' + $event.rowKey, $event.value)"
        (uiAction)="action.emit($event)" />
    }
  `,
  styles: [`
    :host { display: block; }
    :host.inline { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 20px; }
    :host.inline > app-settings-field { width: auto; }
  `],
})
export class PluginContentComponent {
  @Input() nodes: UIComponent[] = [];
  @Input() inline = false;
  @Input() getValue: (key: string, fallback: unknown) => unknown = (_key, fallback) => fallback;
  @Input() setValue: (key: string, value: unknown) => void = (key, value) =>
    this.action.emit({action: "ui_changed", payload: {key, value}});
  @Input() onButtonClick?: (key: string, value?: string) => void;
  @Output() action = new EventEmitter<{action: string; payload: Record<string, unknown>}>();

  change(node: UIComponent, value: unknown): void {
    if (node.key) this.setValue(node.key, value);
  }

  click(node: UIComponent): void {
    if (node.action) this.action.emit({action: node.action, payload: node.payload ?? {}});
    else if (node.key) {
      if (this.onButtonClick) this.onButtonClick(node.key);
      else this.action.emit({action: "settings_button", payload: {key: node.key}});
    }
  }
}
