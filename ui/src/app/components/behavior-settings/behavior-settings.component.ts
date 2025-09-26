import { Component } from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatSlideToggle } from "@angular/material/slide-toggle";
import { MatButtonToggleModule } from "@angular/material/button-toggle";
import { MatSelectModule } from "@angular/material/select";
import { Config, ConfigService } from "../../services/config.service.js";
import { Subscription } from "rxjs";
import { MatSnackBar } from "@angular/material/snack-bar";
import { FormsModule } from "@angular/forms";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatButtonModule } from "@angular/material/button";

@Component({
    selector: "app-behavior-settings",
    standalone: true,
    imports: [
        CommonModule,
        MatInputModule,
        MatFormFieldModule,
        FormsModule,
        MatButtonModule,
        MatSlideToggle,
        MatButtonToggleModule,
        MatSelectModule,
    ],
    templateUrl: "./behavior-settings.component.html",
    styleUrl: "./behavior-settings.component.css",
})
export class BehaviorSettingsComponent {
    config: Config | null = null;
    configSubscription: Subscription;

    // Collapsible toggles for details
    showGameDetails = false;
    showWebDetails = false;
    showUIDetails = false;

    // Permission keys by category (must match backend registrations)
    readonly gamePermissions: string[] = [
        // Ship/mainship/fighter/buggy/humanoid/global
        'fireWeapons', 'setSpeed', 'deployHeatSink', 'deployHardpointToggle',
        'managePowerDistribution', 'galaxyMapOpen', 'galaxyMapClose', 'systemMapOpenOrClose',
        'targetShip', 'toggleWingNavLock', 'cycle_fire_group', 'Change_ship_HUD_mode',
        'shipSpotLightToggle', 'fireChaffLauncher', 'nightVisionToggle', 'targetSubmodule',
        'chargeECM', 'npcOrder', 'FsdJump', 'target_next_system_in_route',
        'toggleCargoScoop', 'ejectAllCargo', 'landingGearToggle', 'useShieldCell',
        'requestDocking', 'undockShip', 'fighterRequestDock',
        // Buggy
        'toggleDriveAssist', 'fireWeaponsBuggy', 'autoBreak', 'headlights', 'nightVisionToggleBuggy', 'toggleTurret', 'selectTargetBuggy', 'managePowerDistributionBuggy', 'toggleCargoScoopBuggy', 'ejectAllCargoBuggy', 'recallDismissShipBuggy', 'galaxyMapOpenOrCloseBuggy', 'systemMapOpenOrCloseBuggy',
        // Humanoid
        'primaryInteractHumanoid', 'secondaryInteractHumanoid', 'equipGearHumanoid', 'toggleFlashlightHumanoid', 'toggleNightVisionHumanoid', 'toggleShieldsHumanoid', 'clearAuthorityLevelHumanoid', 'healthPackHumanoid', 'batteryHumanoid', 'galaxyMapOpenOrCloseHumanoid', 'systemMapOpenOrCloseHumanoid', 'recallDismissShipHumanoid',
        // Global
        'textMessage', 'getVisuals'
    ];

    readonly gamePermissionsGrouped: { type: string; actions: string[] }[] = [
        {
            type: 'ship',
            actions: [
                'fireWeapons', 'setSpeed', 'deployHeatSink', 'deployHardpointToggle',
                'managePowerDistribution', 'galaxyMapOpen', 'galaxyMapClose', 'systemMapOpenOrClose',
                'targetShip', 'toggleWingNavLock', 'cycle_fire_group', 'shipSpotLightToggle',
                'fireChaffLauncher', 'nightVisionToggle', 'targetSubmodule', 'chargeECM', 'npcOrder'
            ],
        },
        {
            type: 'mainship',
            actions: [
                'Change_ship_HUD_mode', 'FsdJump', 'target_next_system_in_route', 'toggleCargoScoop',
                'ejectAllCargo', 'landingGearToggle', 'useShieldCell', 'requestDocking', 'undockShip'
            ],
        },
        { type: 'fighter', actions: ['fighterRequestDock'] },
        {
            type: 'buggy',
            actions: [
                'toggleDriveAssist', 'fireWeaponsBuggy', 'autoBreak', 'headlights', 'nightVisionToggleBuggy',
                'toggleTurret', 'selectTargetBuggy', 'managePowerDistributionBuggy', 'toggleCargoScoopBuggy',
                'ejectAllCargoBuggy', 'recallDismissShipBuggy', 'galaxyMapOpenOrCloseBuggy', 'systemMapOpenOrCloseBuggy'
            ],
        },
        {
            type: 'humanoid',
            actions: [
                'primaryInteractHumanoid', 'secondaryInteractHumanoid', 'equipGearHumanoid',
                'toggleFlashlightHumanoid', 'toggleNightVisionHumanoid', 'toggleShieldsHumanoid',
                'clearAuthorityLevelHumanoid', 'healthPackHumanoid', 'batteryHumanoid',
                'galaxyMapOpenOrCloseHumanoid', 'systemMapOpenOrCloseHumanoid', 'recallDismissShipHumanoid'
            ],
        },
        { type: 'global', actions: ['textMessage', 'getVisuals'] },
    ];

    readonly groupTypeLabels: Record<string, string> = {
        ship: 'Ship',
        mainship: 'Main ship',
        fighter: 'Flighter',
        buggy: 'SRV',
        humanoid: 'Suit',
        global: 'Global',
    };

    // Web/UI permissions removed; only game permissions are managed here.
    constructor(
        private configService: ConfigService,
        private snackBar: MatSnackBar,
    ) {
        this.configSubscription = this.configService.config$.subscribe(
            (config) => {
                this.config = config;
            },
        );
    }
    ngOnDestroy() {
        // Unsubscribe from the config observable to prevent memory leaks
        if (this.configSubscription) {
            this.configSubscription.unsubscribe();
        }
    }

    async onConfigChange(partialConfig: Partial<Config>) {
        if (this.config) {
            console.log("Sending config update to backend:", partialConfig);

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

    isPermissionEnabled(permission: string): boolean {
        const allowed = this.config?.["allowed_actions" as keyof Config] as unknown as string[] | undefined;
        if (!allowed || allowed.length === 0) return true; // empty means all allowed
        return allowed.includes(permission);
    }

    async onTogglePermission(permission: string, enabled: boolean) {
        if (!this.config) return;
        const all = new Set<string>([...this.gamePermissions]);
        const current = (this.config as any).allowed_actions as string[] | undefined;
        let next: string[];

        if (!current || current.length === 0) {
            // Empty means all enabled. If disabling, create full list minus this permission. If enabling, keep empty.
            if (!enabled) {
                next = Array.from(all).filter((p) => p !== permission);
            } else {
                next = []; // still means all
            }
        } else {
            const set = new Set<string>(current);
            if (enabled) {
                set.add(permission);
            } else {
                set.delete(permission);
            }
            next = Array.from(set);
        }

        await this.onConfigChange({ ...( { allowed_actions: next } as any) });
    }
}
