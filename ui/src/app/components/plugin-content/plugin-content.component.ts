import { Component, EventEmitter, Input, Output, inject } from "@angular/core";
import { NgTemplateOutlet } from "@angular/common";
import { MatProgressBarModule } from "@angular/material/progress-bar";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { TranslateService } from "@ngx-translate/core";
import { UIText, UINode } from "../../services/plugin-ui";

@Component({
  selector: "app-plugin-content",
  standalone: true,
  imports: [NgTemplateOutlet, MatProgressBarModule, MatButtonModule, MatIconModule],
  template: `
    <ng-template #nodesTemplate let-nodes>
      @for (node of nodes; track $index) {
        <div class="ui-node" [class]="'ui-node tone-' + (node.tone ?? 'default')"
          [class.outlined]="node.outlined" [class.inline]="node.type === 'inline'" [class.section]="node.type === 'section'">
          @switch (node.type) {
            @case ('heading') {
              @if (node.level === 4) { <h4 class="ui-heading">{{ text(node.text) }}</h4> }
              @else { <h3 class="ui-heading">{{ text(node.text) }}</h3> }
            }
            @case ('progress') {
              <span>{{ text(node.text) }}</span>
              <mat-progress-bar [value]="percentage(node)" />
            }
            @case ('action') {
              <button mat-stroked-button (click)="action.emit({action: node.action!, payload: node.payload ?? {}})">
                @if (node.icon) { <mat-icon>{{ node.icon }}</mat-icon> }
                {{ text(node.text) }}
              </button>
            }
            @case ('list') {
              <ul>@for (child of node.children ?? []; track $index) {
                <li><ng-container *ngTemplateOutlet="nodesTemplate; context: {$implicit: [child]}" /></li>
              }</ul>
            }
            @default { @if (node.text) { <span>{{ text(node.text) }}</span> } }
          }
          @if (node.type !== 'list' && node.children?.length) {
            <ng-container *ngTemplateOutlet="nodesTemplate; context: {$implicit: node.children}" />
          }
        </div>
      }
    </ng-template>
    <ng-container *ngTemplateOutlet="nodesTemplate; context: {$implicit: nodes}" />
  `,
  styles: [`
    :host { display: block; }
    .ui-node { margin: 4px 0; }
    .section { padding: 12px 0; border-bottom: 1px solid rgba(128,128,128,.25); }
    .inline { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 20px; }
    .outlined { border: 1px solid #ffb454; padding: 16px; margin: 16px 0; }
    h3, h4 { text-transform: none; letter-spacing: normal; margin: 0 0 8px; }
    h3 { font-size: 1.1rem; } h4 { font-size: 1rem; }
    ul { margin: 0; padding-left: 22px; }
    .tone-info { color: #75baff; } .tone-warning { color: #ffb454; }
    .tone-default { color: #fff; } .tone-muted { opacity: .8; font-size: .9rem; }
    .tone-success { color: #75baff; } .tone-danger { color: #ff6b6b; }
    mat-progress-bar { margin: 6px 0; }
  `],
})
export class PluginContentComponent {
  private readonly translate = inject(TranslateService);
  @Input() nodes: UINode[] = [];
  @Output() action = new EventEmitter<{action: string; payload: Record<string, unknown>}>();

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

  percentage(node: UINode): number {
    return node.maximum ? Math.max(0, Math.min(100, (node.value ?? 0) / node.maximum * 100)) : 0;
  }
}
