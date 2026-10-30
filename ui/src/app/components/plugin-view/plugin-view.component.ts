import { Component, Input, OnDestroy, inject } from "@angular/core";
import { MatTabsModule } from "@angular/material/tabs";
import { MatSnackBar } from "@angular/material/snack-bar";
import { TranslateService } from "@ngx-translate/core";
import { Subscription } from "rxjs";
import { ConfigService } from "../../services/config.service";
import { SettingsGrid } from "../../services/plugin-settings";
import { RegisteredUIView } from "../../services/plugin-ui";
import { PluginUIService } from "../../services/plugin-ui.service";
import { UIMessage, UIService } from "../../services/ui.service";
import { resolveSettingText } from "../../services/setting-text";
import { SettingsGridComponent } from "../settings-grid/settings-grid.component";
import { PluginContentComponent } from "../plugin-content/plugin-content.component";

@Component({
  selector: "app-plugin-view",
  standalone: true,
  imports: [MatTabsModule, SettingsGridComponent, PluginContentComponent],
  template: `
    <mat-tab-group [selectedIndex]="selectedIndex" (selectedIndexChange)="onSectionSelected($event)">
      @for (section of view.sections; track section.key) {
        <mat-tab [label]="resolve(section.label)">
          @for (grid of grids(section.grids); track grid.key) {
            <app-settings-grid [grid]="grid" [getValue]="getValue" [setValue]="setValue" [onButtonClick]="onButtonClick" [headerLevel]="'h2'" (uiAction)="invoke($event.action, $event.payload)" />
          }
          <app-plugin-content [nodes]="section.content ?? []" [getValue]="getValue" [setValue]="setValue"
            [onButtonClick]="onButtonClick" (action)="invoke($event.action, $event.payload)" />
        </mat-tab>
      }
    </mat-tab-group>
  `,
  styles: [`:host { display: block; padding: 16px; } :host ::ng-deep .mdc-tab__text-label { text-transform: none; }`],
})
export class PluginViewComponent implements OnDestroy {
  private currentView!: RegisteredUIView;
  private requested: Pick<UIMessage, 'show' | 'submenu'> | null = null;
  @Input({required: true}) set view(view: RegisteredUIView) {
    this.currentView = view;
    this.selectRequestedSection();
  }
  get view(): RegisteredUIView { return this.currentView; }
  private readonly config = inject(ConfigService);
  private readonly plugins = inject(PluginUIService);
  private readonly translate = inject(TranslateService);
  private readonly snackBar = inject(MatSnackBar);
  private readonly ui = inject(UIService);
  selectedIndex = 0;
  private readonly subscription: Subscription = this.ui.changeUI$.subscribe(message => {
    this.requested = message;
    this.selectRequestedSection();
  });

  private selectRequestedSection(): void {
    if (this.view && this.requested?.show === this.view.target && this.requested.submenu) {
      const index = this.view.sections.findIndex(section => section.key === this.requested?.submenu);
      if (index >= 0) {
        this.selectedIndex = index;
        this.requested = null;
      }
    }
  }

  onSectionSelected(index: number): void {
    if (index === this.selectedIndex) return;
    this.selectedIndex = index;
    const section = this.view.sections[index];
    if (section) this.ui.showTab(this.view.target, section.key);
  }

  grids(keys: string[] = []): SettingsGrid[] {
    const grids = this.config.getPluginSettingsConfig(this.view.pluginGuid)?.grids ?? [];
    return keys.flatMap(key => grids.filter(grid => grid.key === key));
  }

  readonly getValue = (key: string, defaultValue: unknown): unknown =>
    this.plugins.getValue(this.view.pluginGuid, key,
      this.config.getCurrentConfig()?.plugin_settings?.[this.view.pluginGuid]?.[key] ?? defaultValue);
  readonly setValue = (key: string, value: unknown): void => {
    this.plugins.change(this.view.pluginGuid, key, value).catch(error => this.showError(error));
  };
  readonly onButtonClick = (key: string, value?: string): void => this.invoke("settings_button", {key, value});

  invoke(action: string, payload: Record<string, unknown>): void {
    this.plugins.invoke(this.view.pluginGuid, action, payload).catch(error => this.showError(error));
  }

  private showError(error: Error): void {
    this.snackBar.open(this.resolve(error.message || "common.actionError"), undefined, {duration: 5000});
  }

  resolve(value: string): string { return resolveSettingText(this.translate, value); }
  ngOnDestroy(): void { this.subscription.unsubscribe(); }
}
