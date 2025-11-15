import { Component, OnDestroy, OnInit } from "@angular/core";
import { MatCardModule } from "@angular/material/card";
import { MatTabsModule } from "@angular/material/tabs";
import { MatIconModule } from "@angular/material/icon";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatSelectModule } from "@angular/material/select";
import { MatSlideToggleModule } from "@angular/material/slide-toggle";
import { FormsModule } from "@angular/forms";
import { Config, ConfigService } from "../../services/config.service";
import { Subscription } from "rxjs";
import { MatButtonModule } from "@angular/material/button";
import { KeyValue, KeyValuePipe } from "@angular/common";
import { MatExpansionModule } from "@angular/material/expansion";
import { MatSnackBar, MatSnackBarModule } from "@angular/material/snack-bar";
import { CommonModule } from "@angular/common";
import { MatDividerModule } from "@angular/material/divider";
import { MatCheckboxModule } from "@angular/material/checkbox";
import { MatDialog, MatDialogModule } from "@angular/material/dialog";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import {
  ConfirmationDialogComponent,
  ConfirmationDialogData,
} from "../../components/confirmation-dialog/confirmation-dialog.component";
import { ConfirmationDialogService } from "../../services/confirmation-dialog.service";
import {
  PluginSettings,
} from "../../services/plugin-settings";

@Component({
  selector: "app-plugin-settings",
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatTabsModule,
    MatIconModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatSlideToggleModule,
    MatButtonModule,
    FormsModule,
    KeyValuePipe,
    MatExpansionModule,
    MatSnackBarModule,
    MatDividerModule,
    MatCheckboxModule,
    MatDialogModule,
    MatProgressSpinnerModule,
  ],
  templateUrl: "./plugin-settings.component.html",
  styleUrls: ["../settings-menu/settings-menu.component.scss"],
})
export class PluginSettingsComponent implements OnInit, OnDestroy {
  config: Config | null = null;
  private configSubscription?: Subscription;
  private plugin_settings_message_subscription?: Subscription;

  // Plugin settings
  plugin_settings_configs: [string, PluginSettings][] = [];

  constructor(
    private configService: ConfigService,
    private snackBar: MatSnackBar,
    private dialog: MatDialog,
    private confirmationDialog: ConfirmationDialogService,
  ) {}

  ngOnInit() {
    this.configSubscription = this.configService.config$.subscribe(
      (config) => {
        if (config) {
          // Store the new config
          this.config = config;

          console.log("Config loaded in plugin settings component");
        } else {
          console.error("Received null config in plugin settings component");
        }
      },
    );
    this.plugin_settings_message_subscription = this.configService
      .plugin_settings_message$
      .subscribe(
        (plugin_settings_message) => {
          this.plugin_settings_configs = Object.entries(
            plugin_settings_message?.plugin_settings_configs || {}
          );

          if (plugin_settings_message?.plugin_settings_configs) {
            console.log("Plugin settings loaded", {
              plugin_settings_configs:
                plugin_settings_message.plugin_settings_configs,
            });
          } else {
            console.error("Received null plugin settings");
          }
        },
      );
  }

  ngOnDestroy() {
    if (this.configSubscription) {
      this.configSubscription.unsubscribe();
    }
    if (this.plugin_settings_message_subscription) {
      this.plugin_settings_message_subscription.unsubscribe();
    }
  }

  async onConfigChange(partialConfig: Partial<Config>) {
    if (this.config) {
      try {
        await this.configService.changeConfig(partialConfig);
      } catch (error) {
        console.error("Error updating config:", error);
        this.snackBar.open("Error updating configuration", "OK", {
          duration: 5000,
        });
      }
    }
  }

  async onEventConfigChange(section: string, event: string, enabled: boolean) {
    if (this.config) {
      console.log("onEventConfigChange", section, event, enabled);
      await this.configService.changeEventConfig(section, event, enabled);
    }
  }

  getPluginSetting(
    pluginGuid: string,
    fieldKey: string,
    defaultValue: any,
  ): boolean {
    return this.config?.plugin_settings?.[pluginGuid]?.[fieldKey] ??
      defaultValue;
  }

  setPluginSetting(
    pluginGuid: string,
    fieldKey: string,
    value: any,
  ): void {
    if (this.config == null) {
      return;
    }
    this.config.plugin_settings ??= {};
    this.config.plugin_settings[pluginGuid] ??= {};
    this.config.plugin_settings[pluginGuid][fieldKey] = value;
    this.onConfigChange({ plugin_settings: this.config.plugin_settings });
  }
}
