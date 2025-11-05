import { Component } from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatSlideToggle } from "@angular/material/slide-toggle";
import { MatButtonToggleModule } from "@angular/material/button-toggle";
import { MatSelectModule } from "@angular/material/select";
import { Config, ConfigService, WeaponType, KeybindsMessages } from "../../services/config.service.js";
import { Subscription } from "rxjs";
import { MatSnackBar } from "@angular/material/snack-bar";
import { FormsModule } from "@angular/forms";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatExpansionModule } from "@angular/material/expansion";

@Component({
    selector: "app-actions-settings",
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
        MatIconModule,
        MatExpansionModule,
    ],
    templateUrl: "./actions-settings.component.html",
    styleUrl: "./actions-settings.component.css",
})
export class ActionsSettingsComponent {
    config: Config | null = null;
    configSubscription: Subscription;
    keybindsSubscription: Subscription;
    keybindsData: KeybindsMessages | null = null;

    // Collapsible toggles for details
    showWeaponTypes = false;
    // Track which weapons are in edit mode (by index)
    weaponEditMode: Set<number> = new Set();

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
        
        this.keybindsSubscription = this.configService.keybinds$.subscribe(
            (keybinds) => {
                this.keybindsData = keybinds;
            },
        );
    }
    ngOnDestroy() {
        // Unsubscribe from the config observable to prevent memory leaks
        if (this.configSubscription) {
            this.configSubscription.unsubscribe();
        }
        if (this.keybindsSubscription) {
            this.keybindsSubscription.unsubscribe();
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

    async addWeapon() {
        if (!this.config) return;
        
        const newWeapon: WeaponType = {
            name: '',
            fire_group: 1,
            is_primary: true,
            is_combat: true,
            action: 'fire',
            duration: 0,
            repetitions: 0,
            target_submodule: ''
        };
        
        const updatedWeapons = [...this.config.weapon_types, newWeapon];
        const newIndex = updatedWeapons.length - 1;
        
        await this.onConfigChange({ weapon_types: updatedWeapons });
        
        // Automatically open new weapon in edit mode after config is saved
        this.weaponEditMode.add(newIndex);
    }

    async removeWeapon(index: number) {
        if (!this.config) return;
        
        const updatedWeapons = this.config.weapon_types.filter((_, i) => i !== index);
        
        await this.onConfigChange({ weapon_types: updatedWeapons });
        
        // Clean up edit mode set after removal
        // Remove from edit mode set
        this.weaponEditMode.delete(index);
        
        // Adjust indices in edit mode set for weapons after the deleted one
        const newEditMode = new Set<number>();
        this.weaponEditMode.forEach(idx => {
            if (idx > index) {
                newEditMode.add(idx - 1);
            } else if (idx < index) {
                newEditMode.add(idx);
            }
        });
        this.weaponEditMode = newEditMode;
    }

    updateWeaponName(index: number, name: string) {
        if (!this.config) return;
        
        // Remove extra whitespace and limit to 20 chars
        const cleanedName = name.replace(/\s+/g, ' ').substring(0, 20);
        
        const updatedWeapons = [...this.config.weapon_types];
        updatedWeapons[index] = { ...updatedWeapons[index], name: cleanedName };
        this.onConfigChange({ weapon_types: updatedWeapons });
    }

    updateWeaponFireGroup(index: number, fireGroup: number) {
        if (!this.config) return;
        
        const updatedWeapons = [...this.config.weapon_types];
        updatedWeapons[index] = { ...updatedWeapons[index], fire_group: fireGroup };
        this.onConfigChange({ weapon_types: updatedWeapons });
    }

    updateWeaponPrimary(index: number, isPrimary: boolean) {
        if (!this.config) return;
        
        const updatedWeapons = [...this.config.weapon_types];
        updatedWeapons[index] = { ...updatedWeapons[index], is_primary: isPrimary };
        this.onConfigChange({ weapon_types: updatedWeapons });
    }

    updateWeaponMode(index: number, isCombat: boolean) {
        if (!this.config) return;
        
        const updatedWeapons = [...this.config.weapon_types];
        updatedWeapons[index] = { ...updatedWeapons[index], is_combat: isCombat };
        this.onConfigChange({ weapon_types: updatedWeapons });
    }

    updateWeaponAction(index: number, action: string) {
        if (!this.config) return;
        
        const updatedWeapons = [...this.config.weapon_types];
        const updatedWeapon = { ...updatedWeapons[index], action };
        
        // Clear duration and repetitions when switching to start or stop
        if (action === 'start' || action === 'stop') {
            updatedWeapon.duration = 0;
            updatedWeapon.repetitions = 0;
        }
        
        updatedWeapons[index] = updatedWeapon;
        this.onConfigChange({ weapon_types: updatedWeapons });
    }

    updateWeaponDuration(index: number, duration: number) {
        if (!this.config) return;
        
        // Ensure duration is within bounds
        const clampedDuration = Math.max(0, Math.min(30, duration || 0));
        
        const updatedWeapons = [...this.config.weapon_types];
        updatedWeapons[index] = { ...updatedWeapons[index], duration: clampedDuration };
        this.onConfigChange({ weapon_types: updatedWeapons });
    }

    updateWeaponRepetitions(index: number, repetitions: number) {
        if (!this.config) return;
        
        // Ensure repetitions is within bounds
        const clampedReps = Math.max(0, Math.min(10, Math.floor(repetitions || 0)));
        
        const updatedWeapons = [...this.config.weapon_types];
        updatedWeapons[index] = { ...updatedWeapons[index], repetitions: clampedReps };
        this.onConfigChange({ weapon_types: updatedWeapons });
    }

    updateWeaponTargetSubmodule(index: number, targetSubmodule: string) {
        if (!this.config) return;
        
        const updatedWeapons = [...this.config.weapon_types];
        updatedWeapons[index] = { ...updatedWeapons[index], target_submodule: targetSubmodule };
        this.onConfigChange({ weapon_types: updatedWeapons });
    }

    getWeaponDescription(weapon: WeaponType): string {
        if (!weapon.name) return '';
        
        const parts: string[] = [];
        
        // Add fire group and fire type
        parts.push(`FG${weapon.fire_group}`);
        parts.push(weapon.is_primary ? 'Primary' : 'Secondary');
        parts.push(weapon.is_combat ? 'Combat' : 'Analysis');
        
        // Add target submodule if specified
        if (weapon.target_submodule && weapon.target_submodule.trim()) {
            parts.push(`→ ${weapon.target_submodule}`);
        }
        
        // Add action details
        if (weapon.action === 'start') {
            parts.push('Start continuous');
        } else if (weapon.action === 'stop') {
            parts.push('Stop firing');
        } else {
            const actionParts: string[] = [];
            if (weapon.repetitions > 0) {
                actionParts.push(`${weapon.repetitions + 1}x`);
            }
            if (weapon.duration > 0) {
                actionParts.push(`${weapon.duration}s`);
            }
            if (actionParts.length > 0) {
                parts.push(actionParts.join(' '));
            } else {
                parts.push('Single shot');
            }
        }
        
        return parts.join(' • ');
    }

    toggleWeaponEdit(index: number) {
        if (this.weaponEditMode.has(index)) {
            this.weaponEditMode.delete(index);
        } else {
            this.weaponEditMode.add(index);
        }
    }

    isWeaponInEditMode(index: number): boolean {
        return this.weaponEditMode.has(index);
    }
}

