import { Component, EventEmitter, Input, Output, forwardRef } from "@angular/core";
import { UIComponent, UIElement, matchesUICondition } from "../../services/plugin-ui";
import { SettingsFieldComponent } from "../settings-field/settings-field.component";

@Component({
  selector: "app-plugin-content",
  standalone: true,
  host: {"[class.inline]": "inline"},
  imports: [forwardRef(() => SettingsFieldComponent)],
  template: `
    @for (group of fieldGroups(); track $index) {
      <div [class.button-row]="group[0].type === 'button'">
        @for (node of group; track $index) {
          <app-settings-field [field]="node" [getValue]="getValue" [setValue]="setValue"
            [onButtonClick]="onButtonClick" [buttonEnabled]="buttonEnabled"
            [primary]="node === firstButton()"
            [value]="node.key ? getValue(node.key, node.default_value) : undefined"
            (valueChange)="change(node, $event)" (buttonClick)="click(node)"
            (listAction)="listAction($event)" (submitRequested)="handleEnterSubmit()"
            (uiAction)="action.emit($event)" />
        }
      </div>
    }
  `,
  styles: [`
    :host { display: block; }
    :host.inline { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 20px; }
    :host.inline > div > app-settings-field { width: auto; }
    .button-row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
    .button-row app-settings-field { width: auto; }
  `],
})
export class PluginContentComponent {
  @Input() nodes: UIComponent[] = [];
  @Input() inline = false;
  @Input() buttonEnabled = true;
  @Input() getValue: (key: string, fallback: unknown) => unknown = (_key, fallback) => fallback;
  @Input() setValue: (key: string, value: unknown) => void = (key, value) =>
    this.action.emit({action: "ui_changed", payload: {key, value}});
  @Input() onButtonClick?: (key: string, value?: string) => void;
  @Output() action = new EventEmitter<{action: string; payload: Record<string, unknown>}>();
  @Output() submitRequested = new EventEmitter<void>();

  private visibleFields(elements: UIComponent[]): UIElement[] {
    return elements.flatMap(element => element.type === "condition"
      ? matchesUICondition(element.condition, this.getValue(element.condition.key, undefined))
        ? this.visibleFields(element.fields) : []
      : [element]);
  }

  fieldGroups(): UIElement[][] {
    const groups: UIElement[][] = [];
    for (const field of this.visibleFields(this.nodes)) {
      const previous = groups[groups.length - 1];
      if (field.type === "button" && previous?.[0].type === "button") previous.push(field);
      else groups.push([field]);
    }
    return groups;
  }

  firstButton(): UIElement | undefined {
    return this.visibleFields(this.nodes).find(field => field.type === "button" && !field.readonly);
  }

  handleEnterSubmit(): void {
    const button = this.firstButton();
    if (button && (button.action || this.buttonEnabled)) this.click(button);
    else this.submitRequested.emit();
  }

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

  listAction(event: {action: string; rowKey: string; value?: string}): void {
    const key = `${event.action}:${event.rowKey}`;
    if (this.onButtonClick) this.onButtonClick(key, event.value);
    else this.action.emit({action: "settings_button", payload: {
      key, ...(event.value === undefined ? {} : {value: event.value}),
    }});
  }
}
