import { Component, Inject } from "@angular/core";
import { CommonModule } from "@angular/common";
import {
    MAT_DIALOG_DATA,
    MatDialogModule,
    MatDialogRef,
} from "@angular/material/dialog";
import { MatButtonModule } from "@angular/material/button";
import { MatExpansionModule } from "@angular/material/expansion";
import { MatCard, MatCardHeader, MatCardTitle, MatCardSubtitle, MatCardContent } from "@angular/material/card";
import { MatListItem, MatList, MatSelectionList, MatListModule, MatListOption } from "@angular/material/list";
import { MatCheckbox, MatCheckboxChange } from "@angular/material/checkbox";
import { PluginIndexEntry } from "../../services/plugin-manager.service";
import {MatGridListModule} from '@angular/material/grid-list';
import { FormControl, FormGroup, FormsModule, ReactiveFormsModule } from "@angular/forms";

export interface PluginSource {
    type: string;
    repo: string;
    asset_name: string;
}

export interface PluginManifest {
    guid: string;
    name: string;
    author: string;
    version: string;
    repository: string;
    description: string;
    entrypoint: string;
    source: PluginSource | null;
}

export interface PluginManagerDialogData {
    installed_plugins: PluginManifest[];
}

@Component({
    selector: "app-plugin-manager-dialog",
    standalone: true,
    imports: [
        CommonModule,
        MatDialogModule,
        MatButtonModule,
        MatExpansionModule,
        MatGridListModule,
        MatCard,
        MatCardHeader,
        MatCardTitle,
        MatCardSubtitle,
        MatCardContent,
        MatListItem,
        MatSelectionList,
        MatList,
        MatCheckbox,
        MatListModule,
        FormsModule,
        ReactiveFormsModule
    ],
    templateUrl: "./plugin-manager-dialog.component.html",
    styleUrl: "./plugin-manager-dialog.component.css",
})
export class PluginManagerDialogComponent {
    public is_loading = true;
    public is_modified = false;
    public selected_plugin: [boolean, PluginManifest] | null = null;
    public plugin_list: [boolean, PluginManifest][] = [];
    public form: FormGroup;
    public pluginsControl = new FormControl();

    constructor(
        public dialogRef: MatDialogRef<PluginManagerDialogComponent>,
        @Inject(MAT_DIALOG_DATA) public data: PluginManagerDialogData,
    ) {
        this.form = new FormGroup({
            clothes: this.pluginsControl,
        });
    }

    ngOnInit(): void {
        // TODO: Update url before release
        fetch("https://raw.githubusercontent.com/MaverickMartyn/Elite-Dangerous-AI-Integration/refs/heads/feat/plugin-install-and-updates/docs/plugins/plugin_index.json")
            .then((response) => {
                return response.json();
            })
            .then((json_resp) => {
                let plugin_index = json_resp as PluginIndexEntry[];
                if (plugin_index && Array.isArray(plugin_index)) {
                    // Each plugin index entry should have a name and latest_manifest_url
                    // Download the latest manifest for each plugin and store it in the available_plugins_list
                    let promises = plugin_index.map(entry => {
                        return fetch(entry.latest_manifest_url)
                            .then((response) => {
                                return response.json();
                            })
                            .then((manifest_obj) => {
                                if (manifest_obj?.guid && manifest_obj?.name) {
                                    return manifest_obj as PluginManifest;
                                } else {
                                    console.error("Invalid plugin manifest format:", manifest_obj);
                                    return null;
                                }
                            })
                            .catch((manifest_error) => {
                                console.error("Failed to fetch plugin manifest:", manifest_error);
                            });
                    });
                    Promise.all(promises).then((manifests) => {
                        // After all manifests are fetched, open the dialog
                        // Strip null values from the manifests
                        this.plugin_list = manifests.filter(m => m !== null && m !== undefined)
                            .map(m => [
                                this.data.installed_plugins.map(ip => ip.guid).includes(m?.guid || ""),
                                m
                            ] as [boolean, PluginManifest]);

                        // Add installed plugins to the list, if they are not already present
                        this.data.installed_plugins.forEach(installed_plugin => {
                            if (!this.plugin_list.some(([_, plugin]) => plugin.guid === installed_plugin.guid)) {
                                this.plugin_list.push([true, installed_plugin]);
                            }
                        });

                        // Sort the plugin list by name
                        this.plugin_list.sort((a, b) => a[1].name.localeCompare(b[1].name));

                        this.is_loading = false;
                    });

                } else {
                    console.error("Invalid plugin index format:", plugin_index);
                }
            })
            .catch((error) => {
                console.error("Failed to fetch plugin index:", error);
            });
    }

    onSelectedPluginChanged(options: MatListOption[]): void {
        let selected_plugins = options.filter((v, i) => v.selected);
        if (selected_plugins.length > 0) {
            let plugin_opt = selected_plugins[0]
            let plugin = plugin_opt.value as [boolean, PluginManifest];
            this.selected_plugin = plugin;
            console.log('Selected plugin: ' + plugin[1].name);
        }
    }

    onPluginsChanged(event: MatCheckboxChange): void {
        this.is_modified = true;
    }

    onCancelClick(): void {
        this.dialogRef.close(false);
    }

    onInstallClick(): void {
        this.dialogRef.close(this.plugin_list.filter(plugin => plugin[0]).map(plugin => plugin[1]));
    }
}
