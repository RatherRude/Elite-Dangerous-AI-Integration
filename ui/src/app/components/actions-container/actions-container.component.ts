import { CommonModule } from "@angular/common";
import { Component, OnDestroy } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import { MatSnackBar, MatSnackBarModule } from "@angular/material/snack-bar";
import { MatFormFieldModule } from "@angular/material/form-field";
import { combineLatest, Subscription } from "rxjs";
import { Config, ConfigService } from "../../services/config.service";
import { ProjectionsService } from "../../services/projections.service";
import { RunActionMessage, TauriService } from "../../services/tauri.service";

type ActionMode = "mainship" | "fighter" | "nomad" | "buggy" | "humanoid";
type ActionScope = ActionMode | "ship" | "in_station" | "global";

interface ActionButton {
    action: string;
    label: string;
    icon: string;
    scope: ActionScope | ActionScope[];
    arguments?: Record<string, unknown>;
    requiresConfirmation?: boolean;
}

interface ActionGroup {
    label: string;
    icon: string;
    actions: ActionButton[];
}

interface StatusProjection {
    flags?: Record<string, boolean>;
    flags2?: Record<string, boolean> | null;
    GuiFocus?: string | null;
    FireGroup?: number | null;
}

const SHIP: ActionScope = "ship";
const MAIN_SHIP: ActionScope = "mainship";
const FIGHTER: ActionScope = "fighter";
const NOMAD: ActionScope = "nomad";
const BUGGY: ActionScope = "buggy";
const HUMANOID: ActionScope = "humanoid";

const ACTION_GROUPS: ActionGroup[] = [
    {
        label: "Flight",
        icon: "flight",
        actions: [
            { action: "setSpeed", label: "Full reverse", icon: "fast_rewind", scope: SHIP, arguments: { speed: "Minus100" } },
            { action: "setSpeed", label: "Reverse 75%", icon: "fast_rewind", scope: SHIP, arguments: { speed: "Minus75" } },
            { action: "setSpeed", label: "Reverse 50%", icon: "fast_rewind", scope: SHIP, arguments: { speed: "Minus50" } },
            { action: "setSpeed", label: "Reverse 25%", icon: "fast_rewind", scope: SHIP, arguments: { speed: "Minus25" } },
            { action: "setSpeed", label: "All stop", icon: "stop", scope: SHIP, arguments: { speed: "Zero" } },
            { action: "setSpeed", label: "25% thrust", icon: "slow_motion_video", scope: SHIP, arguments: { speed: "25" } },
            { action: "setSpeed", label: "50% thrust", icon: "play_arrow", scope: SHIP, arguments: { speed: "50" } },
            { action: "setSpeed", label: "75% thrust", icon: "fast_forward", scope: SHIP, arguments: { speed: "75" } },
            { action: "setSpeed", label: "Full thrust", icon: "keyboard_double_arrow_right", scope: SHIP, arguments: { speed: "100" } },
            { action: "engineBoost", label: "Boost", icon: "rocket_launch", scope: [MAIN_SHIP, FIGHTER, NOMAD] },
            { action: "landingGearToggle", label: "Landing gear", icon: "flight_land", scope: [MAIN_SHIP, NOMAD] },
            { action: "liftoff", label: "Liftoff / undock", icon: "flight_takeoff", scope: [MAIN_SHIP, NOMAD] },
            { action: "disembark", label: "Disembark", icon: "directions_walk", scope: [MAIN_SHIP, BUGGY, NOMAD] },
        ],
    },
    {
        label: "Frame Shift Drive",
        icon: "public",
        actions: [
            { action: "FsdJump", label: "Engage FSD", icon: "blur_on", scope: MAIN_SHIP, arguments: { jump_type: "auto" } },
            { action: "FsdJump", label: "Enter supercruise", icon: "speed", scope: MAIN_SHIP, arguments: { jump_type: "supercruise" } },
            { action: "FsdJump", label: "Jump next system", icon: "moving", scope: MAIN_SHIP, arguments: { jump_type: "next_system" } },
            { action: "target_next_system_in_route", label: "Target next system", icon: "near_me", scope: MAIN_SHIP },
        ],
    },
    {
        label: "Weapons and Targeting",
        icon: "gps_fixed",
        actions: [
            { action: "fireWeapons", label: "Fire primary", icon: "my_location", scope: SHIP, arguments: { weaponType: "primary", action: "fire" } },
            { action: "fireWeapons", label: "Fire secondary", icon: "adjust", scope: SHIP, arguments: { weaponType: "secondary", action: "fire" } },
            { action: "fireWeapons", label: "Discovery scan", icon: "radar", scope: SHIP, arguments: { weaponType: "discovery_scanner", action: "fire" } },
            { action: "deployHardpointToggle", label: "Toggle hardpoints", icon: "hardware", scope: SHIP },
            { action: "Change_ship_HUD_mode", label: "Toggle HUD mode", icon: "filter_center_focus", scope: MAIN_SHIP, arguments: { "hud mode": "toggle" } },
            { action: "cycle_fire_group", label: "Previous fire group", icon: "skip_previous", scope: SHIP, arguments: { direction: "previous" } },
            { action: "cycle_fire_group", label: "Next fire group", icon: "skip_next", scope: SHIP, arguments: { direction: "next" } },
            { action: "targetShip", label: "Next target", icon: "navigate_next", scope: SHIP, arguments: { mode: "next" } },
            { action: "targetShip", label: "Previous target", icon: "navigate_before", scope: SHIP, arguments: { mode: "previous" } },
            { action: "targetShip", label: "Highest threat", icon: "warning", scope: SHIP, arguments: { mode: "highest_threat" } },
            { action: "targetShip", label: "Next hostile", icon: "crisis_alert", scope: SHIP, arguments: { mode: "next_hostile" } },
            { action: "targetSubmodule", label: "Target power plant", icon: "bolt", scope: SHIP, arguments: { subsystem: "Power Plant" } },
            { action: "fireChaffLauncher", label: "Launch chaff", icon: "grain", scope: SHIP },
            { action: "chargeECM", label: "Charge ECM", icon: "wifi_tethering", scope: SHIP },
            { action: "chargeFieldNeutraliser", label: "Field neutraliser", icon: "shield", scope: SHIP },
            { action: "useShieldCell", label: "Use shield cell", icon: "security", scope: MAIN_SHIP },
        ],
    },
    {
        label: "Ship Systems",
        icon: "tune",
        actions: [
            { action: "managePowerDistribution", label: "Balance power", icon: "balance", scope: SHIP, arguments: { power_category: ["Engines", "Weapons", "Systems"], balance_power: true } },
            { action: "managePowerDistribution", label: "Max engines", icon: "speed", scope: SHIP, arguments: { power_category: ["Engines"], pips: [4] } },
            { action: "managePowerDistribution", label: "Max weapons", icon: "gps_fixed", scope: SHIP, arguments: { power_category: ["Weapons"], pips: [4] } },
            { action: "managePowerDistribution", label: "Max systems", icon: "shield", scope: SHIP, arguments: { power_category: ["Systems"], pips: [4] } },
            { action: "deployHeatSink", label: "Deploy heat sink", icon: "ac_unit", scope: SHIP },
            { action: "shipSpotLightToggle", label: "Ship lights", icon: "light_mode", scope: SHIP },
            { action: "nightVisionToggle", label: "Night vision", icon: "visibility", scope: SHIP },
            { action: "toggleCargoScoop", label: "Cargo scoop", icon: "inventory_2", scope: MAIN_SHIP },
            { action: "ejectAllCargo", label: "Eject all cargo", icon: "delete_forever", scope: MAIN_SHIP, requiresConfirmation: true },
        ],
    },
    {
        label: "Navigation and Docking",
        icon: "explore",
        actions: [
            { action: "plotToTarget", label: "Clear navigation route", icon: "wrong_location", scope: SHIP, arguments: { clear_nav_route: true } },
            { action: "galaxyMapOpenOrClose", label: "Galaxy map", icon: "public", scope: SHIP },
            { action: "systemMapOpenOrClose", label: "System map", icon: "hub", scope: SHIP },
            { action: "requestDocking", label: "Request docking", icon: "anchor", scope: MAIN_SHIP },
            { action: "stationServices", label: "Refuel", icon: "local_gas_station", scope: "in_station", arguments: { service: ["refuel"] } },
            { action: "stationServices", label: "Repair", icon: "build", scope: "in_station", arguments: { service: ["repair"] } },
            { action: "stationServices", label: "Rearm", icon: "construction", scope: "in_station", arguments: { service: ["rearm"] } },
        ],
    },
    {
        label: "Crew and Vehicles",
        icon: "groups",
        actions: [
            { action: "launchSLF", label: "Launch SLF 1", icon: "flight", scope: MAIN_SHIP, arguments: { vehicle_number: 1 } },
            { action: "launchSLF", label: "Launch SLF 2", icon: "flight", scope: MAIN_SHIP, arguments: { vehicle_number: 2 } },
            { action: "deploySRV", label: "Deploy SRV", icon: "directions_car", scope: MAIN_SHIP, arguments: { vehicle_number: 1 } },
            { action: "npcOrder", label: "NPC attack target", icon: "crisis_alert", scope: SHIP, arguments: { orders: ["FocusTarget"] } },
            { action: "npcOrder", label: "NPC follow", icon: "assistant_navigation", scope: SHIP, arguments: { orders: ["Follow"] } },
            { action: "npcOrder", label: "NPC return", icon: "keyboard_return", scope: SHIP, arguments: { orders: ["ReturnToShip"] } },
            { action: "toggleWingNavLock", label: "Wing nav lock", icon: "link", scope: SHIP },
            { action: "targetShip", label: "Target wingman 1", icon: "person_search", scope: SHIP, arguments: { mode: "wingman_1" } },
            { action: "fighterRequestDock", label: "Dock fighter", icon: "flight_land", scope: FIGHTER },
            { action: "requestDockingNomad", label: "Dock with ship", icon: "flight_land", scope: NOMAD },
            { action: "recallDismissShipNomad", label: "Recall / dismiss ship", icon: "flight", scope: NOMAD },
        ],
    },
    {
        label: "SRV Controls",
        icon: "directions_car",
        actions: [
            { action: "dockSRV", label: "Board ship", icon: "login", scope: BUGGY },
            { action: "toggleDriveAssist", label: "Drive assist", icon: "assistant", scope: BUGGY },
            { action: "fireWeaponsBuggy", label: "Fire primary", icon: "my_location", scope: BUGGY, arguments: { weaponType: "primary", action: "fire" } },
            { action: "fireWeaponsBuggy", label: "Fire secondary", icon: "adjust", scope: BUGGY, arguments: { weaponType: "secondary", action: "fire" } },
            { action: "autoBreak", label: "Auto brake", icon: "motion_photos_paused", scope: BUGGY },
            { action: "headlights", label: "Cycle headlights", icon: "light_mode", scope: BUGGY, arguments: { desired_state: "toggle" } },
            { action: "nightVisionToggleBuggy", label: "Night vision", icon: "visibility", scope: BUGGY },
            { action: "toggleTurret", label: "Turret mode", icon: "control_camera", scope: BUGGY },
            { action: "selectTargetBuggy", label: "Select target", icon: "gps_fixed", scope: BUGGY },
            { action: "managePowerDistributionBuggy", label: "Balance power", icon: "balance", scope: BUGGY, arguments: { power_category: ["Engines", "Weapons", "Systems"], balance_power: true } },
            { action: "toggleCargoScoopBuggy", label: "Cargo scoop", icon: "inventory_2", scope: BUGGY },
            { action: "ejectAllCargoBuggy", label: "Eject all cargo", icon: "delete_forever", scope: BUGGY, requiresConfirmation: true },
            { action: "recallDismissShipBuggy", label: "Recall / dismiss ship", icon: "flight", scope: BUGGY },
            { action: "plotToTargetBuggy", label: "Clear navigation route", icon: "wrong_location", scope: BUGGY, arguments: { clear_nav_route: true } },
            { action: "galaxyMapOpenOrCloseBuggy", label: "Galaxy map", icon: "public", scope: BUGGY },
            { action: "systemMapOpenOrCloseBuggy", label: "System map", icon: "hub", scope: BUGGY },
        ],
    },
    {
        label: "Suit Controls",
        icon: "directions_walk",
        actions: [
            { action: "embark", label: "Embark", icon: "login", scope: HUMANOID },
            { action: "primaryInteractHumanoid", label: "Primary interact", icon: "touch_app", scope: HUMANOID },
            { action: "secondaryInteractHumanoid", label: "Secondary interact", icon: "pan_tool", scope: HUMANOID },
            { action: "equipGearHumanoid", label: "Primary weapon", icon: "gps_fixed", scope: HUMANOID, arguments: { equipment: "HumanoidSelectPrimaryWeaponButton" } },
            { action: "equipGearHumanoid", label: "Secondary weapon", icon: "adjust", scope: HUMANOID, arguments: { equipment: "HumanoidSelectSecondaryWeaponButton" } },
            { action: "equipGearHumanoid", label: "Utility weapon", icon: "handyman", scope: HUMANOID, arguments: { equipment: "HumanoidSelectUtilityWeaponButton" } },
            { action: "equipGearHumanoid", label: "EnergyLink", icon: "electrical_services", scope: HUMANOID, arguments: { equipment: "HumanoidSwitchToRechargeTool" } },
            { action: "equipGearHumanoid", label: "Profile analyser", icon: "manage_search", scope: HUMANOID, arguments: { equipment: "HumanoidSwitchToSuitTool" } },
            { action: "equipGearHumanoid", label: "Holster weapon", icon: "do_not_disturb", scope: HUMANOID, arguments: { equipment: "HumanoidHideWeaponButton" } },
            { action: "toggleFlashlightHumanoid", label: "Flashlight", icon: "flashlight_on", scope: HUMANOID },
            { action: "toggleNightVisionHumanoid", label: "Night vision", icon: "visibility", scope: HUMANOID },
            { action: "toggleShieldsHumanoid", label: "Suit shields", icon: "shield", scope: HUMANOID },
            { action: "clearAuthorityLevelHumanoid", label: "Clear authority", icon: "verified_user", scope: HUMANOID },
            { action: "healthPackHumanoid", label: "Health pack", icon: "medical_services", scope: HUMANOID },
            { action: "batteryHumanoid", label: "Energy cell", icon: "battery_charging_full", scope: HUMANOID },
            { action: "galaxyMapOpenOrCloseHumanoid", label: "Galaxy map", icon: "public", scope: HUMANOID },
            { action: "systemMapOpenOrCloseHumanoid", label: "System map", icon: "hub", scope: HUMANOID },
            { action: "recallDismissShipHumanoid", label: "Recall / dismiss ship", icon: "flight", scope: HUMANOID },
        ],
    },
];

@Component({
    selector: "app-actions-container",
    standalone: true,
    imports: [
        CommonModule,
        FormsModule,
        MatButtonModule,
        MatFormFieldModule,
        MatIconModule,
        MatInputModule,
        MatSnackBarModule,
    ],
    templateUrl: "./actions-container.component.html",
    styleUrl: "./actions-container.component.css",
})
export class ActionsContainerComponent implements OnDestroy {
    readonly actionGroups = ACTION_GROUPS;
    config: Config | null = null;
    projections: Record<string, any> = {};
    currentMode: ActionMode | null = null;
    messageText = "";
    visualQuery = "Describe what is visible";
    isSending = false;
    private readonly stateSubscription: Subscription;

    constructor(
        private readonly configService: ConfigService,
        private readonly projectionsService: ProjectionsService,
        private readonly tauri: TauriService,
        private readonly snackBar: MatSnackBar,
    ) {
        this.stateSubscription = combineLatest([
            this.configService.config$,
            this.projectionsService.projections$,
        ]).subscribe(([config, projections]) => {
            this.config = config;
            this.projections = projections;
            this.currentMode = this.resolveMode();
        });
    }

    ngOnDestroy(): void {
        this.stateSubscription.unsubscribe();
    }

    visibleActions(group: ActionGroup): ActionButton[] {
        return group.actions.filter((action) => this.isActionAvailable(action));
    }

    hasVisibleActions(group: ActionGroup): boolean {
        return group.actions.some((action) => this.isActionAvailable(action));
    }

    isNamedActionAvailable(action: string, scope: ActionScope | ActionScope[]): boolean {
        return this.isActionAvailable({ action, label: action, icon: "", scope });
    }

    async runAction(action: ActionButton): Promise<void> {
        if (action.requiresConfirmation && !window.confirm(`Confirm action: ${action.label}?`)) return;

        const args = this.resolveArguments(action);
        await this.sendAction(action.action, args);
    }

    async sendTextMessage(): Promise<void> {
        const message = this.messageText.trim();
        if (!message) return;

        if (await this.sendAction("textMessage", { message, channel: "local" })) {
            this.messageText = "";
        }
    }

    async inspectVisuals(): Promise<void> {
        const query = this.visualQuery.trim();
        if (!query) return;

        await this.sendAction("getVisuals", { query });
    }

    trackAction(_index: number, action: ActionButton): string {
        return `${action.action}:${action.label}`;
    }

    private async sendAction(action: string, args: Record<string, unknown>): Promise<boolean> {
        if (this.isSending) return false;
        this.isSending = true;
        try {
            await this.tauri.send_command({
                type: "run_action",
                timestamp: new Date().toISOString(),
                action,
                arguments: args,
            } satisfies RunActionMessage);
            return true;
        } catch (error) {
            console.error(`Failed to run action ${action}:`, error);
            this.snackBar.open("The action could not be sent.", "OK", { duration: 5000 });
            return false;
        } finally {
            this.isSending = false;
        }
    }

    private resolveArguments(action: ActionButton): Record<string, unknown> {
        if (action.action.includes("galaxyMapOpenOrClose")) {
            return { desired_state: this.status.GuiFocus === "GalaxyMap" ? "close" : "open" };
        }
        if (action.action.includes("systemMapOpenOrClose")) {
            return { desired_state: this.status.GuiFocus === "SystemMap" ? "close" : "open" };
        }
        return action.arguments ?? {};
    }

    private isActionAvailable(action: ActionButton): boolean {
        if (!this.config?.tools_var || !this.config.game_actions_var) return false;
        if (this.config.allowed_actions?.[action.action] !== true) return false;
        if (!this.scopeMatches(action.scope)) return false;

        const flags = this.status.flags ?? {};
        const flags2 = this.status.flags2 ?? {};
        const blockedWhileDockedOrLanded = [
            "fireWeapons", "setSpeed", "deployHeatSink", "deployHardpointToggle",
        ];
        const blockedWhileDockedLandedOrSupercruise = [
            "fireChaffLauncher", "engineBoost", "chargeECM", "chargeFieldNeutraliser",
            "npcOrder", "launchSLF", "landingGearToggle", "toggleCargoScoop",
        ];

        if (blockedWhileDockedOrLanded.includes(action.action) && (flags["Docked"] || flags["Landed"])) return false;
        if (blockedWhileDockedLandedOrSupercruise.includes(action.action) && (flags["Docked"] || flags["Landed"] || flags["Supercruise"])) return false;

        switch (action.action) {
            case "plotToTarget":
            case "plotToTargetBuggy":
                return !["SAA", "FSS", "Codex"].includes(this.status.GuiFocus ?? "");
            case "galaxyMapOpenOrClose":
            case "galaxyMapOpenOrCloseBuggy":
                return this.status.GuiFocus === "GalaxyMap" || !["SAA", "FSS", "Codex"].includes(this.status.GuiFocus ?? "");
            case "systemMapOpenOrClose":
                return this.status.GuiFocus === "SystemMap" || !["SAA", "FSS", "Codex"].includes(this.status.GuiFocus ?? "");
            case "toggleWingNavLock":
                return this.wingMembers.length > 0;
            case "targetShip":
                return !String(action.arguments?.["mode"] ?? "").startsWith("wingman_") || this.wingMembers.length > 0;
            case "targetSubmodule":
                return Boolean(this.projections["Target"]?.Ship) && Number(this.projections["Target"]?.ScanStage ?? 0) >= 3;
            case "npcOrder":
                return this.fighters.length > 0;
            case "launchSLF":
                return this.fighters.length >= Number(action.arguments?.["vehicle_number"] ?? 1);
            case "deploySRV":
            case "disembark":
                return flags["Landed"] === true;
            case "FsdJump":
                if (flags["Docked"] || flags["Landed"] || flags["FsdMassLocked"] || flags["FsdCooldown"] || flags["FsdCharging"]) return false;
                if (action.arguments?.["jump_type"] === "supercruise" && flags["Supercruise"]) return false;
                return action.arguments?.["jump_type"] !== "next_system" || Boolean(this.projections["NavInfo"]?.NextJumpTarget);
            case "target_next_system_in_route":
                return Boolean(this.projections["NavInfo"]?.NextJumpTarget);
            case "requestDocking":
                return !flags["Supercruise"] && ["NoFocus", "InternalPanel", "CommsPanel", "RolePanel", "ExternalPanel"].includes(this.status.GuiFocus ?? "");
            case "liftoff":
                if (!flags["Docked"] && !flags["Landed"]) return false;
                return !flags["Docked"] || ["NoFocus", "InternalPanel", "CommsPanel", "RolePanel", "ExternalPanel"].includes(this.status.GuiFocus ?? "");
            case "stationServices":
                return flags["Docked"] === true && ["NoFocus", "InternalPanel", "CommsPanel", "RolePanel", "ExternalPanel"].includes(this.status.GuiFocus ?? "");
            case "fireWeaponsBuggy":
            case "toggleTurret":
                return flags["SrvTurretRetracted"] !== true;
            case "equipGearHumanoid":
            case "toggleShieldsHumanoid":
            case "clearAuthorityLevelHumanoid":
            case "healthPackHumanoid":
            case "batteryHumanoid":
            case "recallDismissShipHumanoid":
                return !flags2["OnFootInStation"] && !flags2["OnFootInHangar"] && !flags2["OnFootSocialSpace"];
            case "textMessage":
                return this.currentMode !== null;
            case "getVisuals":
                return this.config.vision_provider !== "none";
            default:
                return true;
        }
    }

    private scopeMatches(scope: ActionScope | ActionScope[]): boolean {
        const scopes = Array.isArray(scope) ? scope : [scope];
        return scopes.some((candidate) => {
            if (candidate === "global") return true;
            if (candidate === "ship") return this.currentMode === "mainship" || this.currentMode === "fighter" || this.currentMode === "nomad";
            if (candidate === "in_station") return this.currentMode === "mainship" && this.status.flags?.["Docked"] === true;
            return candidate === this.currentMode;
        });
    }

    private resolveMode(): ActionMode | null {
        const flags = this.status.flags ?? {};
        const flags2 = this.status.flags2 ?? {};
        let mode: ActionMode | null = null;

        if (flags["InMainShip"]) {
            mode = "mainship";
        } else if (flags["InSRV"] && this.projections["ShipInfo"]?.fighter_loadout === "base") {
            mode = "nomad";
        } else if (flags["InFighter"]) {
            mode = "fighter";
        } else if (flags["InSRV"]) {
            mode = "buggy";
        }
        if (flags2["OnFoot"]) mode = "humanoid";

        return mode;
    }

    private get status(): StatusProjection {
        return this.projections["CurrentStatus"] ?? {};
    }

    private get fighters(): unknown[] {
        return this.projections["ShipInfo"]?.Fighters ?? [];
    }

    private get wingMembers(): unknown[] {
        return this.projections["Wing"]?.Members ?? [];
    }
}
