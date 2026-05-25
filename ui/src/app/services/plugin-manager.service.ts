import { Injectable, NgZone } from "@angular/core";
import { BehaviorSubject, filter, Observable, Subscription } from "rxjs";
import { BaseCommand, type BaseMessage, TauriService } from "./tauri.service";
import { PluginUpdateDialogComponent } from "../components/plugin-update-dialog/plugin-update-dialog.component";
import { MatDialog } from "@angular/material/dialog";
import { ConfirmationDialogComponent } from "../components/confirmation-dialog/confirmation-dialog.component";
import { PluginManifest } from "../components/plugin-manager-dialog/plugin-manager-dialog.component";

export interface PluginUpdateInfo {
    name: string;
    version: string;
    repo: string;
    release_url: string;
}

export interface PluginUpdatesAvailableMessage extends BaseMessage {
    type: "plugin_updates_available";
    updates: PluginUpdateInfo[];
}

export interface PluginsChangedMessage extends BaseMessage {
    type: "plugins_changed";
    message: string;
}

export interface InstalledPluginListMessage extends BaseMessage {
    type: "installed_plugin_list";
    plugins: PluginManifest[];
}

export interface PluginIndexEntry {
    name: string;
    latest_manifest_url: string;
}

@Injectable({
    providedIn: "root",
})
export class PluginManagerService {
    private installed_plugin_list_message_subject = new BehaviorSubject<
        InstalledPluginListMessage | null
    >(null);
    public installed_plugin_list_message$ = this.installed_plugin_list_message_subject
        .asObservable();

    private plugin_updates_available_message_subject = new BehaviorSubject<
        PluginUpdatesAvailableMessage | null
    >(null);
    public plugin_updates_available_message$ = this.plugin_updates_available_message_subject
        .asObservable();

    private plugins_changed_message_subject = new BehaviorSubject<
        PluginsChangedMessage | null
    >(null);
    public plugins_changed_message$ = this.plugins_changed_message_subject
        .asObservable();

    private installed_plugin_list_message_subscription?: Subscription;
    private plugin_updates_available_message_subscription?: Subscription;
    private plugins_changed_message_subscription?: Subscription;

    constructor(private ngZone: NgZone, private dialog: MatDialog, private tauriService: TauriService) {
        // Subscribe to config messages from the TauriService
        this.tauriService.output$.pipe(
            filter((
                message,
            ): message is
                PluginUpdatesAvailableMessage
                | InstalledPluginListMessage
                | PluginsChangedMessage =>
                message.type === "plugin_updates_available"
                || message.type === "installed_plugin_list"
                || message.type === "plugins_changed"
            ),
        ).subscribe((message) => {
            if (message.type === "plugin_updates_available") {
                this.plugin_updates_available_message_subject.next(message);
            } else if (message.type === "plugins_changed") {
                this.plugins_changed_message_subject.next(message);
            } else if (message.type === "installed_plugin_list") {
                this.installed_plugin_list_message_subject.next(message);
            }
        });
        
        this.installed_plugin_list_message_subscription = this.installed_plugin_list_message$
        .subscribe(
            (message) => {
                if (message) {
                    console.log("Received list of installed plugins", {
                        installed_plugins: message.plugins,
                    });
                } else {
                    console.error("Received null list of installed plugins");
                }
            },
        );

        this.plugin_updates_available_message_subscription = this.plugin_updates_available_message$
        .subscribe(
            (plugin_updates_available_message) => {
                if (plugin_updates_available_message) {
                    console.log("Received plugin updates available message", {
                        updates: plugin_updates_available_message.updates,
                    });
                    
                    this.ngZone.run(() => {
                        const dialogRef = this.dialog.open(PluginUpdateDialogComponent, {
                            width: "400px",
                            data: { plugin_updates: plugin_updates_available_message.updates },
                        });

                        dialogRef.afterClosed().subscribe((result) => {
                            if (result) {
                                this.send_update_plugins().catch((err) => {
                                    console.error("Failed to send update plugins command", err);
                                });
                            }
                        });
                    });
                } else {
                    console.error("Received null plugin updates available message");
                }
            },
        );

        this.plugins_changed_message_subscription = this.plugins_changed_message$
        .subscribe(
            (plugins_changed_message) => {
                if (plugins_changed_message) {
                    console.log("Received plugins changed message", {
                        message: plugins_changed_message.message,
                    });
                    
                    this.ngZone.run(() => {
                        const dialogRef = this.dialog.open(ConfirmationDialogComponent, {
                            width: "400px",
                            data: {
                                title: "Plugins changed",
                                message: plugins_changed_message.message,
                                confirmButtonText: "Restart COVAS:NEXT",
                                cancelButtonText: "Later"
                            },
                        });

                        dialogRef.afterClosed().subscribe((result) => {
                            if (result) {
                                this.tauriService.restart_app().catch((err) => {
                                    console.error("Failed to send restart command", err);
                                });
                            }
                        });
                    });
                } else {
                    console.error("Received null plugin updates installed message");
                }
            },
        );
    }
    
    public async send_update_plugins(): Promise<void> {
        await this.tauriService.send_command({
            type: "update_plugins",
            timestamp: new Date().toISOString(),
        });
    }

    // Clean up subscriptions when the service is destroyed
    public ngOnDestroy(): void {
        if (this.installed_plugin_list_message_subscription) {
            this.installed_plugin_list_message_subscription.unsubscribe();
        }
        if (this.plugin_updates_available_message_subscription) {
            this.plugin_updates_available_message_subscription.unsubscribe();
        }
        if (this.plugins_changed_message_subscription) {
            this.plugins_changed_message_subscription.unsubscribe();
        }
    }
}
