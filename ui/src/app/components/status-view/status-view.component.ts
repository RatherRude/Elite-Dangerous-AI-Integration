import { Component, OnDestroy, OnInit } from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatCardModule } from "@angular/material/card";
import { MatDividerModule } from "@angular/material/divider";
import { MatSelectModule } from "@angular/material/select";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatListModule } from "@angular/material/list";
import { MatExpansionModule } from "@angular/material/expansion";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressBarModule } from "@angular/material/progress-bar";
import { MatTooltipModule } from "@angular/material/tooltip";
import { MatBadgeModule } from "@angular/material/badge";
import { MatChipsModule } from "@angular/material/chips";
import { FormsModule } from "@angular/forms";
import { ProjectionsService } from "../../services/projections.service";
import { Subscription } from "rxjs";
import { MatTabsModule } from '@angular/material/tabs';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatButtonModule } from '@angular/material/button';
import { RouterModule } from '@angular/router';

// Define EventEntry interface locally
interface EventEntry {
    event: string;
    count: number;
}

@Component({
    selector: "app-status-view",
    standalone: true,
    imports: [
        CommonModule, 
        MatCardModule, 
        MatDividerModule, 
        MatSelectModule,
        MatFormFieldModule,
        MatListModule,
        MatExpansionModule,
        MatIconModule,
        MatProgressBarModule,
        MatTooltipModule,
        MatBadgeModule,
        MatChipsModule,
        FormsModule,
        MatTabsModule,
        MatProgressSpinnerModule,
        MatButtonModule,
        RouterModule
    ],
    templateUrl: "./status-view.component.html",
    styleUrls: ["./status-view.component.css"]
})
export class StatusViewComponent implements OnInit, OnDestroy {
    selectedTab = 0;
    projectionSubscription?: Subscription;
    projections: any = {};
    isProjectionsLoaded = false;

    // Define tab indices for clarity
    readonly INFORMATION_TAB = 0;
    readonly COMMANDER_TAB = 1;
    readonly STATION_TAB = 2;
    readonly STORAGE_TAB = 3;

    // Tab layout
    showFriendsPanel: boolean = false;
    showColonisationPanel: boolean = false;
    selectedStationService: string | null = null;

    // Status flags for display
    statusFlags: string[] = [
        'Docked', 'Landed', 'LandingGearDown', 'ShieldsUp', 'Supercruise',
        'FlightAssistOff', 'HardpointsDeployed', 'InWing', 'LightsOn',
        'CargoScoopDeployed', 'SilentRunning', 'ScoopingFuel', 'FsdMassLocked',
        'FsdCharging', 'FsdCooldown', 'LowFuel', 'OverHeating', 'InDanger'
    ];
    
    // Odyssey flags for display
    odysseyFlags: string[] = [
        'OnFoot', 'InTaxi', 'InMultiCrew', 'OnFootInStation', 'OnFootOnPlanet',
        'AimDownSight', 'LowOxygen', 'LowHealth', 'Cold', 'Hot',
        'BreathableAtmosphere'
    ];

    // Add missing properties
    selectedProjection: string = 'Status';
    projectionNames: string[] = [];

    // UI state
    showBackpackDetails: boolean = false;
    showCargoDetails: boolean = false;
    showNavDetails: boolean = false;
    showAllModules: boolean = false;

    constructor(private projectionsService: ProjectionsService) {}

    ngOnInit(): void {
        this.projectionSubscription = this.projectionsService.projections$.subscribe(projections => {
            this.projections = projections;
            this.isProjectionsLoaded = true;
        });
    }

    ngOnDestroy(): void {
        if (this.projectionSubscription) {
            this.projectionSubscription.unsubscribe();
        }
    }

    isInShip(): boolean {
        const status = this.getProjection('Status');
        return status && status.InShip;
    }

    isInSRV(): boolean {
        const status = this.getProjection('Status');
        return status && status.InSRV;
    }

    isOnFoot(): boolean {
        const status = this.getProjection('Status');
        return status && status.OnFoot;
    }

    isDocked(): boolean {
        const status = this.getProjection('Status');
        return status && status.Docked;
    }

    isExobiologyScanActive(): boolean {
        const scan = this.getProjection('ExobiologyScan');
        return scan && scan.Active;
    }

    isColonisationActive(colonisation: any): boolean {
        return colonisation && 
              (colonisation.StarSystem || 
               colonisation.ResourcesRequired?.length > 0 || 
               colonisation.ConstructionProgress > 0);
    }
    
    formatSelectedProjection() {
        switch (this.selectedProjection) {
            case 'Status':
                this.updateStatusLists();
                break;
            default:
                break;
        }
    }
    
    updateStatusLists(): void {
        // Update status flags based on current data
        const status = this.getProjection('Status');
        if (status) {
            // Process status flags or other data as needed
            console.log('Status projection updated', status);
        }
    }

    onSelectionChange() {
        this.formatSelectedProjection();
    }
    
    isCustomFormatted(projectionName: string): boolean {
        // Return true for projections that have custom formatting
        return ['ShipInfo', 'Location', 'CurrentStatus', 'NavInfo', 'Cargo', 'Backpack', 'SuitLoadout', 
                'Target', 'Missions', 'Friends', 'ExobiologyScan', 'ColonisationConstruction', 'SystemInfo', 
                'EventCounter'].includes(projectionName);
    }
    
    isBackpackEmpty(backpack: any): boolean {
        return (!backpack.Items || backpack.Items.length === 0) &&
               (!backpack.Components || backpack.Components.length === 0) &&
               (!backpack.Consumables || backpack.Consumables.length === 0) &&
               (!backpack.Data || backpack.Data.length === 0);
    }
    
    formatModName(mod: string): string {
        // Convert snake_case to Title Case (e.g., "suit_mod_battery" -> "Suit Mod Battery")
        return mod.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
    }
    
    formatFlagName(flag: string): string {
        // Convert camelCase to space-separated words
        return flag.replace(/([A-Z])/g, ' $1').trim();
    }
    
    getIconForFlag(flag: string): string {
        // Map flags to Material icons
        const iconMap: Record<string, string> = {
            'Docked': 'anchor',
            'Landed': 'flight_land',
            'LandingGearDown': 'airline_stops',
            'ShieldsUp': 'shield',
            'Supercruise': 'speed',
            'FlightAssistOff': 'flight_takeoff',
            'HardpointsDeployed': 'gps_fixed',
            'InWing': 'group',
            'LightsOn': 'light_mode',
            'CargoScoopDeployed': 'inventory_2',
            'SilentRunning': 'visibility_off',
            'ScoopingFuel': 'local_gas_station',
            'FsdMassLocked': 'lock',
            'FsdCharging': 'bolt',
            'FsdCooldown': 'hourglass_bottom',
            'LowFuel': 'warning',
            'OverHeating': 'local_fire_department',
            'InDanger': 'dangerous'
        };
        
        return iconMap[flag] || 'info';
    }
    
    getIconForOdysseyFlag(flag: string): string {
        // Map Odyssey flags to Material icons
        const iconMap: Record<string, string> = {
            'OnFoot': 'directions_walk',
            'InTaxi': 'local_taxi',
            'InMultiCrew': 'groups',
            'OnFootInStation': 'home',
            'OnFootOnPlanet': 'terrain',
            'AimDownSight': 'track_changes',
            'LowOxygen': 'air',
            'LowHealth': 'healing',
            'Cold': 'ac_unit',
            'Hot': 'whatshot',
            'BreathableAtmosphere': 'air'
        };
        
        return iconMap[flag] || 'info';
    }
    
    formatExpiryTime(isoDateString: string): string {
        if (!isoDateString) return 'Unknown';
        
        try {
            const expiryDate = new Date(isoDateString);
            const now = new Date();
            
            // Calculate the difference in milliseconds
            const diff = expiryDate.getTime() - now.getTime();
            
            // Convert to hours and minutes
            const hours = Math.floor(diff / (1000 * 60 * 60));
            const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
            
            if (hours < 0 || minutes < 0) {
                return 'Expired';
            }
            
            if (hours > 24) {
                const days = Math.floor(hours / 24);
                const remainingHours = hours % 24;
                return `${days}d ${remainingHours}h remaining`;
            }
            
            return `${hours}h ${minutes}m remaining`;
        } catch (error) {
            console.error('Error formatting date', error);
            return isoDateString;
        }
    }
    
    // Helper methods for ExobiologyScan
    formatCoordinate(value: number | undefined): string {
        if (value === undefined) return '0.00';
        return value.toFixed(2);
    }
    
    // Helper methods for ColonisationConstruction
    getColonisationStatusClass(): string {
        const colonisation = this.getProjection('ColonisationConstruction');
        if (!colonisation) return '';
        
        if (colonisation.ConstructionComplete) return 'status-complete';
        if (colonisation.ConstructionFailed) return 'status-failed';
        return 'status-in-progress';
    }
    
    getColonisationStatusText(): string {
        const colonisation = this.getProjection('ColonisationConstruction');
        if (!colonisation) return '';
        
        if (colonisation.ConstructionComplete) return 'Complete';
        if (colonisation.ConstructionFailed) return 'Failed';
        return `In Progress (${colonisation.ProgressPercent}%)`;
    }
    
    formatPercentage(value: number | undefined): string {
        if (value === undefined) return '0%';
        return `${value.toFixed(1)}%`;
    }
    
    // Helper methods for SystemInfo
    isEmptyObject(obj: any): boolean {
        return !obj || Object.keys(obj).length === 0;
    }
    
    getSafeSystemEntries(systemInfo: any): {name: string, data: any}[] {
        if (!systemInfo) return [];
        try {
            return Object.entries(systemInfo).map(([name, data]) => ({name, data: data as any}));
        } catch (error) {
            console.error('Error parsing system entries:', error);
            return [];
        }
    }
    
    isValidSystemInfo(systemInfo: any): boolean {
        try {
            // Check if it's actually an object we can iterate over
            return typeof systemInfo === 'object' && 
                   systemInfo !== null && 
                   Object.keys(systemInfo).length > 0;
        } catch (error) {
            console.error('Error validating SystemInfo:', error);
            return false;
        }
    }

    getEventEntries(): EventEntry[] {
        const eventCounter = this.getProjection('EventCounter');
        if (!eventCounter) {
            return [];
        }
        
        const eventEntries: EventEntry[] = [];
        for (const [event, count] of Object.entries(eventCounter)) {
            if (event !== 'timestamp') {
                eventEntries.push({ event, count: Number(count) });
            }
        }
        return eventEntries;
    }

    formatNumber(value: number): string {
        if (value === undefined || value === null) {
            return '0';
        }
        return value.toLocaleString();
    }

    formatDistance(distance: number): string {
        if (distance === undefined || distance === null) {
            return '0 ls';
        }
        if (distance < 1) {
            return `${(distance * 1000).toFixed(0)} km`;
        }
        return `${distance.toFixed(0)} ls`;
    }

    formatServiceName(service: string): string {
        // Capitalize the service name
        return service.charAt(0).toUpperCase() + service.slice(1);
    }

    // Tab navigation methods
    setActiveTab(tabIndex: number): void {
        this.selectedTab = tabIndex;
        this.showFriendsPanel = false;
        this.showColonisationPanel = false;
    }
    
    toggleFriendsPanel(): void {
        this.showFriendsPanel = !this.showFriendsPanel;
        if (this.showFriendsPanel) {
            this.showColonisationPanel = false;
        }
    }
    
    toggleColonisationPanel(): void {
        this.showColonisationPanel = !this.showColonisationPanel;
        if (this.showColonisationPanel) {
            this.showFriendsPanel = false;
        }
    }
    
    showStationService(service: string): void {
        this.selectedStationService = service;
    }
    
    // Helper methods for location display
    getLocationSystem(): string {
        const location = this.getProjection('Location');
        return location?.StarSystem || 'Unknown';
    }
    
    getLocationDetail(): string {
        const location = this.getProjection('Location');
        if (!location) return '';
        
        if (location.Station) {
            return location.Station + (location.Docked ? ' (Docked)' : '');
        } else if (location.Planet) {
            return location.Planet + (location.Landed ? ' (Landed)' : '');
        } else if (location.Star) {
            return location.Star;
        }
        return '';
    }
    
    // Helper methods for NavInfo
    hasNavRoute(): boolean {
        const navInfo = this.getProjection('NavInfo');
        return navInfo?.NavRoute && navInfo.NavRoute.length > 0;
    }
    
    getNavRouteInfo(): string {
        const navInfo = this.getProjection('NavInfo');
        if (!navInfo?.NavRoute || navInfo.NavRoute.length === 0) return '';
        
        return `${navInfo.NavRoute.length} jump${navInfo.NavRoute.length > 1 ? 's' : ''} to ${navInfo.NavRoute[navInfo.NavRoute.length - 1].StarSystem}`;
    }
    
    // Helper methods for Suit and Backpack
    getSuitName(): string {
        const suitLoadout = this.getProjection('SuitLoadout');
        return suitLoadout?.SuitName_Localised || suitLoadout?.SuitName || 'Unknown';
    }
    
    getSuitLoadoutName(): string {
        const suitLoadout = this.getProjection('SuitLoadout');
        return suitLoadout?.LoadoutName || 'Unknown';
    }
    
    getSuitWeapons(): any[] {
        const suitLoadout = this.getProjection('SuitLoadout');
        return suitLoadout?.Modules || [];
    }
    
    getWeaponIcon(weapon: any): string {
        const weaponName = weapon.ModuleName.toLowerCase();
        if (weaponName.includes('pistol')) return 'pan_tool';
        if (weaponName.includes('rifle')) return 'settings_input_hdmi';
        if (weaponName.includes('laser')) return 'flash_on';
        if (weaponName.includes('rocket')) return 'whatshot';
        return 'blur_on';
    }
    
    getBackpackItems(category: string): any[] {
        const backpack = this.getProjection('Backpack');
        return backpack?.[category] || [];
    }
    
    // Helper methods for Ship info
    getShipName(): string {
        const shipInfo = this.getProjection('ShipInfo');
        return shipInfo?.Name || 'Unknown Ship';
    }
    
    getShipType(): string {
        const shipInfo = this.getProjection('ShipInfo');
        return shipInfo?.Type || 'Unknown';
    }
    
    getShipIdent(): string {
        const shipInfo = this.getProjection('ShipInfo');
        return shipInfo?.ShipIdent || '';
    }
    
    getCargoAmount(): number {
        const shipInfo = this.getProjection('ShipInfo');
        return shipInfo?.Cargo || 0;
    }
    
    getCargoCapacity(): number {
        const shipInfo = this.getProjection('ShipInfo');
        return shipInfo?.CargoCapacity || 1;
    }
    
    getCargoPercentage(): number {
        return (this.getCargoAmount() / this.getCargoCapacity()) * 100;
    }
    
    getCargoTooltip(): string {
        return `${this.getCargoAmount()} / ${this.getCargoCapacity()} tons`;
    }
    
    getFuelAmount(): string {
        const shipInfo = this.getProjection('ShipInfo');
        return shipInfo?.FuelMain?.toFixed(1) || '0';
    }
    
    getFuelCapacity(): number {
        const shipInfo = this.getProjection('ShipInfo');
        return shipInfo?.FuelMainCapacity || 1;
    }
    
    getFuelPercentage(): number {
        const amount = parseFloat(this.getFuelAmount());
        return (amount / this.getFuelCapacity()) * 100;
    }
    
    getFuelTooltip(): string {
        return `${this.getFuelAmount()} / ${this.getFuelCapacity()} tons`;
    }
    
    // Helper methods for Exobiology scan
    hasActiveBioScan(): boolean {
        const exoBio = this.getProjection('ExobiologyScan');
        return exoBio?.scans && exoBio.scans.length > 0;
    }
    
    getBioScanCount(): number {
        const exoBio = this.getProjection('ExobiologyScan');
        return exoBio?.scans?.length || 0;
    }
    
    isWithinScanRadius(): boolean {
        const exoBio = this.getProjection('ExobiologyScan');
        return exoBio?.within_scan_radius !== false; // Default to true if undefined
    }
    
    // Helper methods for Friends display
    getFriendsCount(): number {
        const friends = this.getProjection('Friends');
        return friends?.Online?.length || 0;
    }
    
    getOnlineFriends(): string[] {
        const friends = this.getProjection('Friends');
        return friends?.Online || [];
    }
    
    // Helper methods for Colonisation display
    getColonisationSystem(): string {
        const colonisation = this.getProjection('ColonisationConstruction');
        return colonisation?.StarSystem || 'Unknown system';
    }
    
    getColonisationProgress(): number {
        const colonisation = this.getProjection('ColonisationConstruction');
        return colonisation?.ConstructionProgress || 0;
    }
    
    getColonisationProgressValue(): number {
        return this.getColonisationProgress() * 100;
    }
    
    getColonisationResources(): any[] {
        const colonisation = this.getProjection('ColonisationConstruction');
        return colonisation?.ResourcesRequired || [];
    }
    
    // Helper methods for Commander tab
    getCommanderName(): string {
        const commander = this.getProjection('Commander');
        return commander?.Name || 'Unknown';
    }
    
    getBalance(): number {
        const commander = this.getProjection('Commander');
        return commander?.Credits || 0;
    }
    
    getRank(type: string): string {
        const rank = this.getProjection('Rank');
        if (!rank) return 'Unknown';
        
        // Map rank numbers to names based on type
        const rankNames: Record<string, string[]> = {
            'Combat': ['Harmless', 'Mostly Harmless', 'Novice', 'Competent', 'Expert', 'Master', 'Dangerous', 'Deadly', 'Elite', 'Elite I', 'Elite II', 'Elite III', 'Elite IV', 'Elite V'],
            'Trade': ['Penniless', 'Mostly Penniless', 'Peddler', 'Dealer', 'Merchant', 'Broker', 'Entrepreneur', 'Tycoon', 'Elite', 'Elite I', 'Elite II', 'Elite III', 'Elite IV', 'Elite V'],
            'Explore': ['Aimless', 'Mostly Aimless', 'Scout', 'Surveyor', 'Trailblazer', 'Pathfinder', 'Ranger', 'Pioneer', 'Elite', 'Elite I', 'Elite II', 'Elite III', 'Elite IV', 'Elite V'],
            'CQC': ['Helpless', 'Mostly Helpless', 'Amateur', 'Semi Professional', 'Professional', 'Champion', 'Hero', 'Legend', 'Elite', 'Elite I', 'Elite II', 'Elite III', 'Elite IV', 'Elite V'],
            'Federation': ['None', 'Recruit', 'Cadet', 'Midshipman', 'Petty Officer', 'Chief Petty Officer', 'Warrant Officer', 'Ensign', 'Lieutenant', 'Lieutenant Commander', 'Post Commander', 'Post Captain', 'Rear Admiral', 'Vice Admiral', 'Admiral'],
            'Empire': ['None', 'Outsider', 'Serf', 'Master', 'Squire', 'Knight', 'Lord', 'Baron', 'Viscount', 'Count', 'Earl', 'Marquis', 'Duke', 'Prince', 'King'],
            'Soldier': ['Defenceless', 'Mostly Defenceless', 'Rookie', 'Soldier', 'Gunslinger', 'Warrior', 'Gladiator', 'Deadeye', 'Elite', 'Elite I', 'Elite II', 'Elite III', 'Elite IV', 'Elite V'],
            'Exobiologist': ['Directionless', 'Mostly Directionless', 'Compiler', 'Collector', 'Cataloguer', 'Taxonomist', 'Ecologist', 'Geneticist', 'Elite', 'Elite I', 'Elite II', 'Elite III', 'Elite IV', 'Elite V']
        };
        
        if (!rankNames[type]) return 'Unknown';
        
        const rankValue = rank[type] || 0;
        return rankNames[type][rankValue] || 'Unknown';
    }
    
    getRankProgress(type: string): number {
        const progress = this.getProjection('Progress');
        if (!progress) return 0;
        
        return (progress[type] || 0) * 100;
    }
    
    // Helper method for station services
    getStationName(): string {
        const location = this.getProjection('Location');
        return location?.Station || 'Unknown Station';
    }
    
    // Get projection data by name
    getProjection(name: string): any {
        return this.projections && this.projections[name] ? this.projections[name] : null;
    }
    
    // Helper for status flags
    getCurrentStatusValue(flagType: string, flag: string): boolean {
        const status = this.getProjection('CurrentStatus');
        return status && status[flagType] && status[flagType][flag] || false;
    }

    isInStation(): boolean {
        const status = this.getProjection('Status');
        return status && status.Docked;
    }

    getActiveMode(): string {
        const status = this.getProjection('CurrentStatus');
        let active_mode = 'mainship'; // default
        
        if (status && status.flags) {
            if (status.flags['InMainShip']) {
                active_mode = 'mainship';
            } else if (status.flags['InFighter']) {
                active_mode = 'fighter';
            } else if (status.flags['InSRV']) {
                active_mode = 'buggy';
            }
        }
        
        if (status && status.flags2) {
            if (status.flags2['OnFoot']) {
                active_mode = 'humanoid';
            }
        }
        
        return active_mode;
    }

    // New helper methods for detailed D&D 5E character sheet style
    getShipMass(): number {
        const shipInfo = this.getProjection('ShipInfo');
        return shipInfo?.UnladenMass || 0;
    }
    
    getJumpRange(): number {
        const shipInfo = this.getProjection('ShipInfo');
        return shipInfo?.MaximumJumpRange || 0;
    }
    
    getLandingPadSize(): string {
        const shipInfo = this.getProjection('ShipInfo');
        return shipInfo?.LandingPadSize || '?';
    }
    
    getShipHealth(): string {
        const loadout = this.getProjection('Loadout');
        if (loadout && loadout.HullHealth) {
            const healthPercent = (loadout.HullHealth * 100).toFixed(0);
            return `${healthPercent}%`;
        }
        return '100%';
    }
    
    getShipHealthPercentage(): number {
        const loadout = this.getProjection('Loadout');
        if (loadout && loadout.HullHealth) {
            return loadout.HullHealth * 100;
        }
        return 100;
    }
    
    getShipRebuy(): number {
        const loadout = this.getProjection('Loadout');
        return loadout?.Rebuy || 0;
    }
    
    getShipModules(): any[] {
        const loadout = this.getProjection('Loadout');
        return loadout?.Modules || [];
    }
    
    formatSlotName(slot: string): string {
        // Format hardpoint and utility slots
        if (slot.includes('Hardpoint')) {
            // Don't return "Weapon X" for hardpoints
            return '';
        }
        if (slot.includes('Utility')) {
            const match = slot.match(/Utility(\d+)/);
            if (match) {
                return `Utility ${match[1]}`;
            }
        }
        
        // Format core internal slots
        const coreMapping: Record<string, string> = {
            'PowerPlant': 'Power Plant',
            'MainEngines': 'Thrusters',
            'FrameShiftDrive': 'FSD',
            'LifeSupport': 'Life Support',
            'PowerDistributor': 'Power Distributor',
            'Radar': 'Sensors',
            'FuelTank': 'Fuel Tank',
            'Armour': 'Hull',
        };
        
        for (const [key, value] of Object.entries(coreMapping)) {
            if (slot.includes(key)) {
                return value;
            }
        }
        
        // Format optional internal slots
        if (slot.startsWith('Slot')) {
            const match = slot.match(/Slot(\d+)_Size(\d+)/);
            if (match) {
                return `Optional: Size ${match[2]} (Slot ${match[1]})`;
            }
        }
        
        // If no specific format, return the original slot name
        return slot || '';
    }
    
    formatModuleName(item: string): string {
        if (!item) return '';
        
        // Process names with known Elite Dangerous module patterns
        if (item.includes('hpt_') || item.includes('int_')) {
            // Remove common unwanted prefixes
            let cleaned = item
                .replace(/hpt_/g, '')                // Remove hpt_ prefix
                .replace(/int_/g, '')                // Remove int_ prefix
                .replace(/armour_/g, '')             // Remove armour_ prefix
                .replace(/_/g, ' ')                  // Replace underscores with spaces
                .replace(/name/g, '')                // Remove 'name'
                .replace(/^\s+|\s+$/g, '')           // Trim whitespace
                .replace(/\s+/g, ' ');               // Replace multiple spaces with single space
            
            // Special handling for weapons to make names more readable
            if (cleaned.includes('dumbfiremissilerack')) {
                cleaned = cleaned.replace('dumbfiremissilerack', 'Missile Rack');
            } else if (cleaned.includes('minelauncher')) {
                cleaned = cleaned.replace('minelauncher', 'Mine Launcher');
            } else if (cleaned.includes('multicannon')) {
                cleaned = cleaned.replace('multicannon', 'Multi-Cannon');
            } else if (cleaned.includes('pulselaser')) {
                cleaned = cleaned.replace('pulselaser', 'Pulse Laser');
            } else if (cleaned.includes('beamlaser')) {
                cleaned = cleaned.replace('beamlaser', 'Beam Laser');
            } else if (cleaned.includes('burstlaser')) {
                cleaned = cleaned.replace('burstlaser', 'Burst Laser');
            } else if (cleaned.includes('cannon')) {
                cleaned = cleaned.replace(/\bcannon\b/g, 'Cannon');
            } else if (cleaned.includes('plasmaaccelerator')) {
                cleaned = cleaned.replace('plasmaaccelerator', 'Plasma Accelerator');
            } else if (cleaned.includes('railgun')) {
                cleaned = cleaned.replace('railgun', 'Rail Gun');
            } else if (cleaned.includes('torpedopylon')) {
                cleaned = cleaned.replace('torpedopylon', 'Torpedo Pylon');
            }
            
            // Handle mount type (fixed/gimballed/turreted)
            if (cleaned.includes('fixed')) {
                cleaned = cleaned.replace('fixed', '(Fixed)');
            } else if (cleaned.includes('gimbal')) {
                cleaned = cleaned.replace('gimbal', '(Gimballed)');
            } else if (cleaned.includes('turret')) {
                cleaned = cleaned.replace('turret', '(Turreted)');
            }
            
            // Handle size
            if (cleaned.includes('small')) {
                cleaned = cleaned.replace('small', 'Small');
            } else if (cleaned.includes('medium')) {
                cleaned = cleaned.replace('medium', 'Medium');
            } else if (cleaned.includes('large')) {
                cleaned = cleaned.replace('large', 'Large');
            } else if (cleaned.includes('huge')) {
                cleaned = cleaned.replace('huge', 'Huge');
            }
            
            // Special case handling for "advanced" prefix
            if (cleaned.includes('advanced')) {
                cleaned = cleaned.replace('advanced', 'Advanced');
            }
            
            // Reorganize weapon names to make them more readable
            const sizeMatch = cleaned.match(/(Small|Medium|Large|Huge)/);
            const mountMatch = cleaned.match(/\((Fixed|Gimballed|Turreted)\)/);
            const advancedMatch = cleaned.match(/(Advanced)/);
            
            if (sizeMatch && mountMatch) {
                const size = sizeMatch[1];
                const mount = mountMatch[1];
                const advanced = advancedMatch ? 'Advanced ' : '';
                
                // Extract the base weapon name (without size, mount, or advanced)
                let baseName = cleaned
                    .replace(sizeMatch[0], '')
                    .replace(mountMatch[0], '')
                    .replace(advancedMatch ? advancedMatch[0] : '', '')
                    .trim();
                
                // Return the properly formatted weapon name
                return `${advanced}${size} ${baseName} ${mount}`.trim();
            }
            
            // For non-weapon items or if reorganization failed, capitalize each word
            return cleaned.split(' ')
                .map(word => word.charAt(0).toUpperCase() + word.slice(1))
                .join(' ');
        }
        
        // Get the item name without class/rating prefix (alternative format)
        const match = item.match(/^\d\w_(.+)$/);
        if (match) {
            let cleaned = match[1]
                .replace(/_/g, ' ')                  // Replace underscores with spaces
                .replace(/^\s+|\s+$/g, '')           // Trim whitespace
                .replace(/\s+/g, ' ');               // Replace multiple spaces with single space
            
            // Capitalize each word
            return cleaned.split(' ')
                .map(word => word.charAt(0).toUpperCase() + word.slice(1))
                .join(' ');
        }
        
        // If not matching any pattern, return original with underscores replaced
        return item.replace(/_/g, ' ');
    }
    
    getModuleClassAndRating(item: string): string {
        // Extract class and rating from module name if present
        const match = item.match(/class(\d+)([a-e])?/i);
        if (match) {
            return match[2] ? `${match[1]}${match[2].toUpperCase()}` : match[1];
        }
        return '';
    }
    
    hasCargoItems(): boolean {
        const cargo = this.getProjection('Cargo');
        return cargo && cargo.Inventory && cargo.Inventory.length > 0;
    }
    
    getCargoItems(): any[] {
        const cargo = this.getProjection('Cargo');
        return cargo?.Inventory || [];
    }
    
    getNavRouteDetails(): any[] {
        const navInfo = this.getProjection('NavInfo');
        return navInfo?.NavRoute || [];
    }
    
    toggleCargoDetails(): void {
        this.showCargoDetails = !this.showCargoDetails;
    }
    
    toggleNavDetails(): void {
        this.showNavDetails = !this.showNavDetails;
    }
    
    toggleAllModules(): void {
        this.showAllModules = !this.showAllModules;
    }
    
    toggleBackpackDetails(): void {
        this.showBackpackDetails = !this.showBackpackDetails;
    }
    
    getSuitClass(): number {
        const suitLoadout = this.getProjection('SuitLoadout');
        if (suitLoadout?.SuitName) {
            const match = suitLoadout.SuitName.match(/class(\d+)/i);
            return match ? parseInt(match[1]) : 1;
        }
        return 1;
    }
    
    getSuitMods(): string[] {
        const suitLoadout = this.getProjection('SuitLoadout');
        return suitLoadout?.SuitMods || [];
    }
    
    getWeaponType(weapon: any): string {
        const name = weapon.ModuleName.toLowerCase();
        if (name.includes('launcher')) return 'Launcher';
        if (name.includes('pistol')) return 'Pistol';
        if (name.includes('rifle')) return 'Rifle';
        if (name.includes('shotgun')) return 'Shotgun';
        if (name.includes('smg')) return 'SMG';
        return 'Weapon';
    }
    
    getSuitModIcon(mod: string): string {
        // Map suit mods to appropriate icons
        if (mod.includes('armour')) return 'shield';
        if (mod.includes('shield')) return 'security';
        if (mod.includes('ammo')) return 'inventory_2';
        if (mod.includes('battery')) return 'battery_full';
        if (mod.includes('sprint')) return 'directions_run';
        return 'upgrade';
    }

    // New helper methods for categorizing ship modules
    getWeaponModules(): any[] {
        return this.getShipModules().filter(module => 
            module.Slot.includes('Hardpoint'));
    }
    
    getUtilityModules(): any[] {
        return this.getShipModules().filter(module => 
            module.Slot.includes('Utility'));
    }
    
    getCoreModules(): any[] {
        const coreSlots = ['PowerPlant', 'MainEngines', 'FrameShiftDrive', 
                          'LifeSupport', 'PowerDistributor', 'Radar', 'FuelTank', 'Armour'];
        return this.getShipModules().filter(module => 
            coreSlots.some(slot => module.Slot.includes(slot)));
    }
    
    getOptionalModules(): any[] {
        // Only show optional internals and limit count if not showing all
        const modules = this.getShipModules().filter(module => 
            module.Slot.startsWith('Slot'));
        
        if (!this.showAllModules) {
            return modules.slice(0, 5);
        }
        return modules;
    }
    
    getVisibleModulesCount(): number {
        return this.getWeaponModules().length + 
               this.getUtilityModules().length + 
               this.getCoreModules().length + 
               (this.showAllModules ? 0 : Math.min(this.getOptionalModules().length, 5));
    }
    
    formatWeaponSlot(slotName: string): string {
        if (slotName === 'PrimaryWeapon1' || slotName === 'PrimaryWeapon2') {
            return 'Primary Weapon';
        } else if (slotName === 'SecondaryWeapon') {
            return 'Secondary Weapon';
        }
        return slotName || '';
    }
    
    getEngineeringTooltip(module: any): string {
        if (!module.Engineering) return '';
        
        const eng = module.Engineering;
        let tooltip = `${eng.BlueprintName || 'Unknown'} (Grade ${eng.Level || '?'})`;
        
        if (eng.ExperimentalEffect_Localised) {
            tooltip += `\nExperimental: ${eng.ExperimentalEffect_Localised}`;
        }
        
        return tooltip;
    }

    getStarTypeIcon(starClass: string): string {
        // First letter of star class indicates type
        const starType = starClass.charAt(0).toUpperCase();
        
        // Return appropriate icon based on star type
        switch (starType) {
            case 'O': 
            case 'B': 
            case 'A': return 'brightness_7'; // Hot blue/white stars
            case 'F': 
            case 'G': return 'wb_sunny';     // Sun-like stars
            case 'K': 
            case 'M': return 'brightness_low'; // Red dwarfs
            case 'L': 
            case 'T': 
            case 'Y': return 'brightness_3';   // Brown dwarfs
            case 'W': return 'auto_awesome';   // Wolf-Rayet stars
            case 'N': 
            case 'C': 
            case 'S': return 'grain';          // Carbon stars
            case 'H': return 'blur_circular';  // Black holes
            case 'X': return 'blur_on';        // Exotic
            default: return 'stars';           // Default star icon
        }
    }
    
    getStarClassColor(starClass: string): string {
        // First letter of star class indicates type
        const starType = starClass.charAt(0).toUpperCase();
        
        // Return CSS class for star type
        switch (starType) {
            case 'O': return 'star-o';    // Blue
            case 'B': return 'star-b';    // Blue-white
            case 'A': return 'star-a';    // White
            case 'F': return 'star-f';    // Yellow-white
            case 'G': return 'star-g';    // Yellow (Sun-like)
            case 'K': return 'star-k';    // Orange
            case 'M': return 'star-m';    // Red
            case 'L': 
            case 'T': 
            case 'Y': return 'star-brown'; // Brown dwarfs
            case 'W': return 'star-w';    // Wolf-Rayet (Blue)
            case 'N': 
            case 'C': 
            case 'S': return 'star-carbon'; // Carbon stars (Red to Orange)
            case 'H': return 'star-black-hole'; // Black holes
            case 'X': return 'star-exotic'; // Exotic
            default: return 'star-default'; // Default
        }
    }
    
    getJumpDistance(index: number): string {
        const route = this.getNavRouteDetails();
        if (!route || index <= 0 || index >= route.length || !route[index].StarPos || !route[index-1].StarPos) {
            return '0.0';
        }
        
        // Calculate 3D distance between current and previous star
        const current = route[index].StarPos;
        const previous = route[index-1].StarPos;
        
        const dx = current[0] - previous[0];
        const dy = current[1] - previous[1];
        const dz = current[2] - previous[2];
        
        const distance = Math.sqrt(dx*dx + dy*dy + dz*dz);
        return distance.toFixed(1);
    }

    getLocationDetailIcon(): string {
        const location = this.getProjection('Location');
        if (!location) return 'place';
        
        if (location.Station) {
            return location.Docked ? 'dock' : 'business';
        } else if (location.Planet) {
            return location.Landed ? 'terrain' : 'language';
        } else if (location.Star) {
            return 'wb_sunny';
        }
        return 'place';
    }

    /**
     * Calculate hours from seconds
     */
    getHoursFromSeconds(seconds: number): number {
        return Math.floor(seconds / 3600);
    }

    /**
     * Format material names by converting snake_case or camelCase to Title Case
     */
    formatMaterialName(name: string): string {
        if (!name) return '';
        // Convert snake_case or camelCase to Title Case with spaces
        return name
          .replace(/_/g, ' ')
          .replace(/([A-Z])/g, ' $1')
          .replace(/\w\S*/g, txt => txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase());
    }

    /**
     * Format item names by converting to Title Case
     */
    formatItemName(name: string): string {
        if (!name) return '';
        return this.formatMaterialName(name);
    }

    /**
     * Format transfer time from seconds to a human readable format
     */
    formatTransferTime(seconds: number): string {
        if (!seconds) return 'Immediate';

        const minutes = Math.floor(seconds / 60);
        if (minutes < 60) {
            return `${minutes} min`;
        }

        const hours = Math.floor(minutes / 60);
        const remainingMinutes = minutes % 60;

        if (hours < 24) {
            return `${hours}h ${remainingMinutes}m`;
        }

        const days = Math.floor(hours / 24);
        const remainingHours = hours % 24;

        return `${days}d ${remainingHours}h`;
    }


    /**
     * Maps for organizing materials by category and grade
     */
    // Raw material mappings by category and grade
    private rawMaterialsMap: {[category: number]: {[grade: number]: string[]}} = {
        1: { 1: ['carbon'], 2: ['vanadium'], 3: ['niobium'], 4: ['yttrium'] },
        2: { 1: ['phosphorus'], 2: ['chromium'], 3: ['molybdenum'], 4: ['technetium'] },
        3: { 1: ['sulphur'], 2: ['manganese'], 3: ['cadmium'], 4: ['ruthenium'] },
        4: { 1: ['iron'], 2: ['zinc'], 3: ['tin'], 4: ['selenium'] },
        5: { 1: ['nickel'], 2: ['germanium'], 3: ['tungsten'], 4: ['tellurium'] },
        6: { 1: ['rhenium'], 2: ['arsenic'], 3: ['mercury'], 4: ['polonium'] },
        7: { 1: ['lead'], 2: ['zirconium'], 3: ['boron'], 4: ['antimony'] }
    };

    // Manufactured material mappings by section and grade
    private manufacturedMaterialsMap: {[section: string]: {[grade: number]: string[]}} = {
        'Chemical': {
            1: ['chemicalstorageunits'],
            2: ['chemicalprocessors'],
            3: ['chemicaldistillery'],
            4: ['chemicalmanipulators'],
            5: ['pharmaceuticalisolators']
        },
        'Thermic': {
            1: ['temperedalloys'],
            2: ['heatresistantceramics'],
            3: ['precipitatedalloys'],
            4: ['thermicalloys'],
            5: ['militarygradealloys']
        },
        'Heat': {
            1: ['heatconductionwiring'],
            2: ['heatdispersionplate'],
            3: ['heatexchangers'],
            4: ['heatvanes'],
            5: ['protoheatradiators']
        },
        'Conductive': {
            1: ['basicconductors'],
            2: ['conductivecomponents'],
            3: ['conductiveceramics'],
            4: ['conductivepolymers'],
            5: ['biotechconductors']
        },
        'Mechanical Components': {
            1: ['mechanicalscrap'],
            2: ['mechanicalequipment'],
            3: ['mechanicalcomponents'],
            4: ['configurablecomponents'],
            5: ['improvisedcomponents']
        },
        'Capacitors': {
            1: ['gridresistors'],
            2: ['hybridcapacitors'],
            3: ['electrochemicalarrays'],
            4: ['polymercapacitors'],
            5: ['militarysupercapacitors']
        },
        'Shielding': {
            1: ['wornshieldemitters'],
            2: ['shieldemitters'],
            3: ['shieldingsensors'],
            4: ['compoundshielding'],
            5: ['imperialshielding']
        },
        'Composite': {
            1: ['compactcomposites'],
            2: ['filamentcomposites'],
            3: ['highdensitycomposites'],
            4: ['proprietarycomposites'],
            5: ['coredynamicscomposites']
        },
        'Crystals': {
            1: ['crystalshards'],
            2: ['flawedfocuscrystals'],
            3: ['focuscrystals'],
            4: ['refinedfocuscrystals'],
            5: ['exquisitefocuscrystals']
        },
        'Alloys': {
            1: ['salvagedalloys'],
            2: ['galvanisingalloys'],
            3: ['phasealloys'],
            4: ['protolightalloys'],
            5: ['protoradiolicalloys']
        }
    };

    // Encoded material mappings by section and grade
    private encodedMaterialsMap: {[section: string]: {[grade: number]: string[]}} = {
        'Emission Data': {
            1: ['exceptionalscrambledemissiondata'],
            2: ['irregularemissiondata'],
            3: ['unexpectedemissiondata'],
            4: ['decodedemissiondata'],
            5: ['abnormalcompactemissionsdata']
        },
        'Wake Scans': {
            1: ['atypicaldisruptedwakeechoes'],
            2: ['anomalousfsdtelemetry'],
            3: ['strangewakesolutions'],
            4: ['eccentrichyperspace'],
            5: ['dataminedwakeexceptions']
        },
        'Shield Data': {
            1: ['distortedshieldcyclerecordings'],
            2: ['inconsistentshieldsoakanalysis'],
            3: ['untypicalshieldscans'],
            4: ['aberrantshieldpatternanalysis'],
            5: ['peculiarshieldfrequencydata']
        },
        'Encryption Files': {
            1: ['unusualencryptedfiles'],
            2: ['taggedencryptioncodes'],
            3: ['opensymmetrickeys'],
            4: ['atypicalencryptionarchives'],
            5: ['adaptiveencryptorscapture']
        },
        'Data Archives': {
            1: ['anomalousbulkscandata'],
            2: ['unidentifiedscanarchives'],
            3: ['classifiedscandatabanks'],
            4: ['divergentscandata'],
            5: ['classifiedscanfragment']
        },
        'Encoded Firmware': {
            1: ['specialisedlegacyfirmware'],
            2: ['modifiedconsumerfirmware'],
            3: ['crackedindustrialfirmware'],
            4: ['securityfirmwarepatch'],
            5: ['modifiedembeddedfirmware']
        }
    };

    /**
     * Get raw materials by grade and category
     */
    getRawMaterialByGradeAndCategory(grade: number, category: number): any[] {
        if (!this.getProjection('Materials')?.Raw ||
            !this.rawMaterialsMap[category] ||
            !this.rawMaterialsMap[category][grade]) {
            return [];
        }

        const materialNames = this.rawMaterialsMap[category][grade];
        return this.getProjection('Materials').Raw.filter((material: any) => {
            const normalizedName = this.normalizeMaterialName(material.Name_Localised || material.Name);
            return materialNames.includes(normalizedName);
        });
    }

    /**
     * Get manufactured materials by grade and section
     */
    getManufacturedMaterialByGradeAndSection(section: string, grade: number): any[] {
        if (!this.getProjection('Materials')?.Manufactured ||
            !this.manufacturedMaterialsMap[section] ||
            !this.manufacturedMaterialsMap[section][grade]) {
            return [];
        }

        const materialNames = this.manufacturedMaterialsMap[section][grade];
        return this.getProjection('Materials').Manufactured.filter((material: any) => {
            const normalizedName = this.normalizeMaterialName(material.Name_Localised || material.Name);
            return materialNames.includes(normalizedName);
        });
    }

    /**
     * Get encoded materials by grade and section
     */
    getEncodedMaterialByGradeAndSection(section: string, grade: number): any[] {
        if (!this.getProjection('Materials')?.Encoded ||
            !this.encodedMaterialsMap[section] ||
            !this.encodedMaterialsMap[section][grade]) {
            return [];
        }

        const materialNames = this.encodedMaterialsMap[section][grade];
        return this.getProjection('Materials').Encoded.filter((material: any) => {
            const normalizedName = this.normalizeMaterialName(material.Name_Localised || material.Name);
            return materialNames.includes(normalizedName);
        });
    }

    /**
     * Normalize material name for comparison (remove spaces, make lowercase)
     */
    private normalizeMaterialName(name: string): string {
        return name.toLowerCase().replace(/[^a-z0-9]/g, '');
    }
}