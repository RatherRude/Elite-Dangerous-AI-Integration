import { Injectable, NgZone } from "@angular/core";
import { BehaviorSubject, filter, Observable, Subscription } from "rxjs";
import { BaseCommand, type BaseMessage, TauriService } from "./tauri.service";
import { PluginUpdateDialogComponent } from "../components/plugin-update-dialog/plugin-update-dialog.component";
import { MatDialog } from "@angular/material/dialog";
import { ConfirmationDialogComponent } from "../components/confirmation-dialog/confirmation-dialog.component";

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

export interface PluginUpdatesInstalledMessage extends BaseMessage {
    type: "plugin_updates_installed";
    message: string;
}

@Injectable({
    providedIn: "root",
})
export class PluginUpdateService {
    private plugin_updates_available_message_subject = new BehaviorSubject<
        PluginUpdatesAvailableMessage | null
    >(null);
    public plugin_updates_available_message$ = this.plugin_updates_available_message_subject
        .asObservable();

    private plugin_updates_installed_message_subject = new BehaviorSubject<
        PluginUpdatesInstalledMessage | null
    >(null);
    public plugin_updates_installed_message$ = this.plugin_updates_installed_message_subject
        .asObservable();

    private plugin_updates_available_message_subscription?: Subscription;
    private plugin_updates_installed_message_subscription?: Subscription;

    constructor(private ngZone: NgZone, private dialog: MatDialog, private tauriService: TauriService) {
        // Subscribe to config messages from the TauriService
        this.tauriService.output$.pipe(
            filter((
                message,
            ): message is
                PluginUpdatesAvailableMessage
                | PluginUpdatesInstalledMessage =>
                message.type === "plugin_updates_available"
                || message.type === "plugin_updates_installed"
            ),
        ).subscribe((message) => {
            if (message.type === "plugin_updates_available") {
                this.plugin_updates_available_message_subject.next(message);
            } else if (message.type === "plugin_updates_installed") {
                this.plugin_updates_installed_message_subject.next(message);
            }
        });

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

        this.plugin_updates_installed_message_subscription = this.plugin_updates_installed_message$
        .subscribe(
            (plugin_updates_installed_message) => {
                if (plugin_updates_installed_message) {
                    console.log("Received plugin updates installed message", {
                        message: plugin_updates_installed_message.message,
                    });
                    
                    this.ngZone.run(() => {
                        const dialogRef = this.dialog.open(ConfirmationDialogComponent, {
                            width: "400px",
                            data: {
                                title: "Plugin Updates Installed",
                                message: plugin_updates_installed_message.message,
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
}
