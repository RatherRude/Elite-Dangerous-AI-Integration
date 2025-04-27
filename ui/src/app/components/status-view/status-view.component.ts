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
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { RouterModule } from '@angular/router';
import { LogContainerComponent } from "../log-container/log-container.component";
import { CovasLogComponent } from "../covas-log/covas-log.component";

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
        MatButtonToggleModule,
        RouterModule,
        LogContainerComponent,
        CovasLogComponent
    ],
    templateUrl: "./status-view.component.html",
    styleUrls: ["./status-view.component.css"]
})
export class StatusViewComponent implements OnInit, OnDestroy {
    selectedTab = 0;
    projectionSubscription?: Subscription;
    projections: any = {};
    isProjectionsLoaded = false;
    
    // View type for main tab selection (logs or status)
    viewType: string = 'logs';

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
    
    // Search terms for station services
    marketSearchTerm: string = '';
    outfittingSearchTerm: string = '';
    shipyardSearchTerm: string = '';

    // New properties for engineers
    engineerFilter: string = 'all';
    onFootEngineerFilter: string = 'all';

    // Ship Engineers data
    private shipEngineers = [
        { Engineer: "Tod 'The Blaster' McQuinn", EngineerID: 300260, Location: "Wolf 397",
          Modifies: "Weapons (Ballistic)",
          HowToFind: "Available from start",
          HowToGetInvite: "15 bounty vouchers earned",
          HowToUnlock: "100,001 CR of bounty vouchers provided",
          HowToGainRep: "Modules crafted or Alliance vouchers handed in" },
        { Engineer: "Felicity Farseer", EngineerID: 300100, Location: "Deciat",
          Modifies: "FSD, Thrusters, Sensors",
          HowToFind: "Available from start",
          HowToGetInvite: "Exploration rank Scout or higher reached",
          HowToUnlock: "1 Meta-Alloy provided",
          HowToGainRep: "Modules crafted or exploration data sold" },
        { Engineer: "Elvira Martuuk", EngineerID: 300160, Location: "Khun",
          Modifies: "FSD, Shields, Thrusters",
          HowToFind: "Available from start",
          HowToGetInvite: "300+ ly from starting system traveled",
          HowToUnlock: "3 Soontill Relics provided",
          HowToGainRep: "Modules crafted or exploration data sold" },
        { Engineer: "Liz Ryder", EngineerID: 300080, Location: "Eurybia",
          Modifies: "Explosives, Armor",
          HowToFind: "Available from start",
          HowToGetInvite: "Friendly with Eurybia Blue Mafia achieved",
          HowToUnlock: "200 Landmines provided",
          HowToGainRep: "Modules crafted or commodities sold" },
        { Engineer: "The Dweller", EngineerID: 300180, Location: "Wyrd",
          Modifies: "Power Distributor, Lasers",
          HowToFind: "Available from start",
          HowToGetInvite: "5 Black Markets dealt with",
          HowToUnlock: "500,000 CR paid",
          HowToGainRep: "Modules crafted or commodities sold" },
        { Engineer: "Lei Cheung", EngineerID: 300120, Location: "Laksak",
          Modifies: "Shields, Sensors",
          HowToFind: "Introduced by The Dweller",
          HowToGetInvite: "50 markets traded with",
          HowToUnlock: "200 Gold provided",
          HowToGainRep: "Modules crafted" },
        { Engineer: "Selene Jean", EngineerID: 300210, Location: "Kuk",
          Modifies: "Hull, Armor",
          HowToFind: "Introduced by Tod McQuinn",
          HowToGetInvite: "500 tons of ore mined",
          HowToUnlock: "10 Painite provided",
          HowToGainRep: "Modules crafted or commodities/data sold" },
        { Engineer: "Hera Tani", EngineerID: 300090, Location: "Kuwemaki",
          Modifies: "Power Plant, Sensors",
          HowToFind: "Introduced by Liz Ryder",
          HowToGetInvite: "Imperial Navy rank Outsider achieved",
          HowToUnlock: "50 Kamitra Cigars provided",
          HowToGainRep: "Modules crafted or commodities sold" },
        { Engineer: "Broo Tarquin", EngineerID: 300030, Location: "Muang",
          Modifies: "Lasers",
          HowToFind: "Introduced by Hera Tani",
          HowToGetInvite: "Combat rank Competent or higher achieved",
          HowToUnlock: "50 Fujin Tea provided",
          HowToGainRep: "Modules crafted" },
        { Engineer: "Marco Qwent", EngineerID: 300200, Location: "Sirius (Permit Required)",
          Modifies: "Power Plant, Power Distributor",
          HowToFind: "Introduced by Elvira Martuuk",
          HowToGetInvite: "Sirius Corporation invitation obtained",
          HowToUnlock: "25 Modular Terminals provided",
          HowToGainRep: "Modules crafted or commodities sold" },
        { Engineer: "Zacariah Nemo", EngineerID: 300050, Location: "Yoru",
          Modifies: "Weapons (Varied)",
          HowToFind: "Introduced by Elvira Martuuk",
          HowToGetInvite: "Party of Yoru invitation received",
          HowToUnlock: "25 Xihe Biomorphic Companions provided",
          HowToGainRep: "Modules crafted or commodities sold" },
        { Engineer: "Didi Vatermann", EngineerID: 300000, Location: "Leesti",
          Modifies: "Shields",
          HowToFind: "Introduced by Selene Jean",
          HowToGetInvite: "Trade rank Merchant or higher achieved",
          HowToUnlock: "50 Lavian Brandy provided",
          HowToGainRep: "Modules crafted" },
        { Engineer: "Colonel Bris Dekker", EngineerID: 300140, Location: "Sol (Permit Required)",
          Modifies: "FSD, Interdictor",
          HowToFind: "Introduced by Juri Ishmaak",
          HowToGetInvite: "Federation friendly status achieved",
          HowToUnlock: "1,000,000 CR of combat bonds provided",
          HowToGainRep: "Modules crafted" },
        { Engineer: "Juri Ishmaak", EngineerID: 300250, Location: "Giryak",
          Modifies: "Sensors, Explosives",
          HowToFind: "Introduced by Felicity Farseer",
          HowToGetInvite: "50+ combat bonds earned",
          HowToUnlock: "100,000 CR of combat bonds provided",
          HowToGainRep: "Modules crafted or combat bonds handed in" },
        { Engineer: "Professor Palin", EngineerID: 300220, Location: "Arque",
          Modifies: "Thrusters, FSD",
          HowToFind: "Introduced by Marco Qwent",
          HowToGetInvite: "5,000 ly from start location traveled",
          HowToUnlock: "25 Sensor Fragments provided",
          HowToGainRep: "Modules crafted or exploration data sold" },
        { Engineer: "Bill Turner", EngineerID: 300010, Location: "Alioth (Permit Required)",
          Modifies: "Utility, Scanners, Sensors",
          HowToFind: "Introduced by Selene Jean",
          HowToGetInvite: "Alliance friendly status achieved",
          HowToUnlock: "50 Bromellite provided",
          HowToGainRep: "Modules crafted" },
        { Engineer: "Lori Jameson", EngineerID: 300230, Location: "Shinrarta Dezhra (Permit Required)",
          Modifies: "Support Modules, Scanners",
          HowToFind: "Introduced by Marco Qwent",
          HowToGetInvite: "Combat rank Dangerous or higher achieved",
          HowToUnlock: "25 Konnga Ale provided",
          HowToGainRep: "Modules crafted or exploration data sold" },
        { Engineer: "Ram Tah", EngineerID: 300110, Location: "Meene",
          Modifies: "Utility, Limpets",
          HowToFind: "Introduced by Lei Cheung",
          HowToGetInvite: "Exploration rank Surveyor or higher achieved",
          HowToUnlock: "50 Classified Scan Databanks provided",
          HowToGainRep: "Modules crafted or exploration data sold" },
        { Engineer: "Tiana Fortune", EngineerID: 300270, Location: "Achenar (Permit Required)",
          Modifies: "Scanners, Limpets",
          HowToFind: "Introduced by Hera Tani",
          HowToGetInvite: "Empire friendly status achieved",
          HowToUnlock: "50 Decoded Emission Data provided",
          HowToGainRep: "Modules crafted or commodities sold" },
        { Engineer: "The Sarge", EngineerID: 300040, Location: "Beta-3 Tucani",
          Modifies: "Cannons, Limpets",
          HowToFind: "Introduced by Juri Ishmaak",
          HowToGetInvite: "Federal Navy rank Midshipman achieved",
          HowToUnlock: "50 Aberrant Shield Pattern Analysis provided",
          HowToGainRep: "Modules crafted or exploration data sold" },
        { Engineer: "Etienne Dorn", EngineerID: 300290, Location: "Los",
          Modifies: "Core Modules, Weapons",
          HowToFind: "Introduced by Liz Ryder",
          HowToGetInvite: "Trade rank Dealer or higher achieved",
          HowToUnlock: "25 Occupied Escape Pods provided",
          HowToGainRep: "Modules crafted" },
        { Engineer: "Marsha Hicks", EngineerID: 300150, Location: "Tir",
          Modifies: "Weapons, Support Modules",
          HowToFind: "Introduced by The Dweller",
          HowToGetInvite: "Exploration rank Surveyor or higher achieved",
          HowToUnlock: "10 Osmium mined",
          HowToGainRep: "Modules crafted" },
        { Engineer: "Mel Brandon", EngineerID: 300280, Location: "Luchtaine",
          Modifies: "Core Modules, Weapons",
          HowToFind: "Introduced by Elvira Martuuk",
          HowToGetInvite: "Colonia Council invitation received",
          HowToUnlock: "100,000 CR of bounty vouchers provided",
          HowToGainRep: "Modules crafted" },
        { Engineer: "Petra Olmanova", EngineerID: 300130, Location: "Asura",
          Modifies: "Armor, Weapons",
          HowToFind: "Introduced by Tod McQuinn",
          HowToGetInvite: "Combat rank Expert or higher achieved",
          HowToUnlock: "200 Progenitor Cells provided",
          HowToGainRep: "Modules crafted" },
        { Engineer: "Chloe Sedesi", EngineerID: 300300, Location: "Shenve",
          Modifies: "Thrusters, FSD",
          HowToFind: "Introduced by Marco Qwent",
          HowToGetInvite: "5,000 ly from start location traveled",
          HowToUnlock: "25 Sensor Fragments provided",
          HowToGainRep: "Modules crafted or exploration data sold" }
    ];

    // On-foot Engineers data
    private onFootEngineers = [
        { Engineer: "Domino Green", EngineerID: 400002, Location: "Orishis",
          Modifies: "Suits, Tools",
          HowToFind: "Available from start",
          HowToGetInvite: "100ly in Apex Transport traveled",
          HowToUnlock: "5 Push provided",
          HowToReferral: "5 Push required" },
        { Engineer: "Hero Ferrari", EngineerID: 400003, Location: "Siris",
          Modifies: "Suit Mobility",
          HowToFind: "Available from start",
          HowToGetInvite: "10 Conflict Zones completed",
          HowToUnlock: "15 Settlement Defence Plans provided",
          HowToReferral: "15 Settlement Defence Plans required" },
        { Engineer: "Jude Navarro", EngineerID: 400001, Location: "Aurai",
          Modifies: "Weapons, Armor",
          HowToFind: "Available from start",
          HowToGetInvite: "10 Restore/Reactivation missions completed",
          HowToUnlock: "5 Genetic Repair Meds provided",
          HowToReferral: "5 Genetic Repair Meds required" },
        { Engineer: "Kit Fowler", EngineerID: 400004, Location: "Capoya",
          Modifies: "Weapons, Shields",
          HowToFind: "Introduced by Domino Green",
          HowToGetInvite: "10 Opinion Polls sold to Bartenders",
          HowToUnlock: "5 Surveillance Equipment provided",
          HowToReferral: "5 Surveillance Equipment required" },
        { Engineer: "Oden Geiger", EngineerID: 400008, Location: "Candiaei",
          Modifies: "Vision, Tools",
          HowToFind: "Introduced by Terra Velasquez",
          HowToGetInvite: "20 Biological/Genetic items sold to Bartenders",
          HowToUnlock: "No referral needed",
          HowToReferral: "N/A" },
        { Engineer: "Terra Velasquez", EngineerID: 400006, Location: "Shou Xing",
          Modifies: "Suit Mobility, Stealth",
          HowToFind: "Introduced by Jude Navarro",
          HowToGetInvite: "12 Covert missions completed",
          HowToUnlock: "15 Financial Projections provided",
          HowToReferral: "15 Financial Projections required" },
        { Engineer: "Uma Laszlo", EngineerID: 400007, Location: "Xuane",
          Modifies: "Weapons, Defense",
          HowToFind: "Introduced by Wellington Beck",
          HowToGetInvite: "Sirius Corp unfriendly status reached",
          HowToUnlock: "No referral needed",
          HowToReferral: "N/A" },
        { Engineer: "Wellington Beck", EngineerID: 400005, Location: "Jolapa",
          Modifies: "Tools, Backpack",
          HowToFind: "Introduced by Hero Ferrari",
          HowToGetInvite: "25 Entertainment items sold to Bartenders",
          HowToUnlock: "5 InSight Entertainment Suites provided",
          HowToReferral: "5 InSight Entertainment Suites required" },
        { Engineer: "Yarden Bond", EngineerID: 400009, Location: "Bayan",
          Modifies: "Stealth, Mobility",
          HowToFind: "Introduced by Kit Fowler",
          HowToGetInvite: "8 Smear Campaign Plans sold to Bartenders",
          HowToUnlock: "No referral needed",
          HowToReferral: "N/A" },
        { Engineer: "Baltanos", EngineerID: 400010, Location: "Deriso",
          Modifies: "Suit Mobility, Stealth",
          HowToFind: "Available in Colonia",
          HowToGetInvite: "Colonia Council friendly status achieved",
          HowToUnlock: "10 Faction Associates provided",
          HowToReferral: "10 Faction Associates required" },
        { Engineer: "Eleanor Bresa", EngineerID: 400011, Location: "Desy",
          Modifies: "Weapons, Defense",
          HowToFind: "Available in Colonia",
          HowToGetInvite: "5 Settlements in Colonia visited",
          HowToUnlock: "10 Digital Designs provided",
          HowToReferral: "10 Digital Designs required" },
        { Engineer: "Rosa Dayette", EngineerID: 400012, Location: "Kojeara",
          Modifies: "Tools, Backpack",
          HowToFind: "Available in Colonia",
          HowToGetInvite: "10 Recipe items sold to Bartenders in Colonia",
          HowToUnlock: "10 Manufacturing Instructions provided",
          HowToReferral: "10 Manufacturing Instructions required" },
        { Engineer: "Yi Shen", EngineerID: 400013, Location: "Einheriar",
          Modifies: "Stealth, Weapons",
          HowToFind: "Introduced by Colonia engineers",
          HowToGetInvite: "All Colonia engineers' referral tasks completed",
          HowToUnlock: "No referral needed",
          HowToReferral: "N/A" }
    ];

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
        if (!colonisation) return false;
        
        const hasActiveSystem = colonisation.StarSystem && colonisation.StarSystem !== 'Unknown';
        const hasResources = colonisation.ResourcesRequired && colonisation.ResourcesRequired.length > 0;
        
        return hasActiveSystem && hasResources;
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
        return `In Progress`;
    }
    
    formatPercentage(value: number | undefined | null): string {
        if (value === undefined || value === null) return '0%';
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
        const rawName = suitLoadout?.SuitName_Localised || suitLoadout?.SuitName || 'Unknown';
        
        // Map localization keys to readable names
        if (rawName === "$UtilitySuit_Class1_Name;" || rawName.toLowerCase().includes('utilitysuit')) {
            const className = this.getSuitClass();
            return `Maverick Suit Mk${className}`;
        } else if (rawName === "$ExplorationSuit_Class1_Name;" || rawName.toLowerCase().includes('explorationsuit')) {
            const className = this.getSuitClass();
            return `Artemis Suit Mk${className}`;
        } else if (rawName === "$TacticalSuit_Class1_Name;" || rawName.toLowerCase().includes('tacticalsuit')) {
            const className = this.getSuitClass();
            return `Dominator Suit Mk${className}`;
        } else if (rawName === "Flight Suit" || rawName.toLowerCase().includes('flightsuit')) {
            return "Flight Suit";
        }
        
        // If we couldn't map it, clean up the original name as best we can
        if (rawName.startsWith('$') && rawName.endsWith(';')) {
            // Remove the $ and ; and replace underscores with spaces
            return rawName.substring(1, rawName.length - 1).replace(/_/g, ' ');
        }
        
        return rawName;
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
        // If there's no ship name (or empty string), fallback to the formatted ship type
        if (!shipInfo?.Name || shipInfo.Name.trim() === '' || shipInfo.Name.trim() === ' ') {
            return this.formatShipType(shipInfo?.Type || '');
        }
        return shipInfo.Name;
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
        const cargo = this.getProjection('Cargo');
        return cargo?.TotalItems || 0;
    }
    
    getCargoCapacity(): number {
        const cargo = this.getProjection('Cargo');
        return cargo?.Capacity || 0;
    }
    
    getCargoPercentage(): number {
        const amount = this.getCargoAmount();
        const capacity = this.getCargoCapacity();
        return capacity > 0 ? (amount / capacity) * 100 : 0;
    }
    
    getCargoTooltip(): string {
        const amount = this.getCargoAmount();
        const capacity = this.getCargoCapacity();
        return `${amount} / ${capacity} tons`;
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
        
        // Convert the progress value to a percentage (0-100)
        // The value from Progress is already a percentage (0-100), not a decimal
        return progress[type] || 0;
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
        const location = this.getProjection('Location');
        
        // Check both Status.Docked flag and Location.Station
        return (status && status.Docked) || (location && location.Station && location.Docked);
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
                return `${match[1]}: Size ${match[2]}`;
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
        // Return only actual weapons (hardpoints)
        return this.getShipModules().filter(module => {
            // Ensure item is a weapon by checking both slot name and item name
            return module.Slot && module.Slot.includes('Hardpoint') && 
                  // Exclude shield boosters, chaff launchers, heat sinks, etc. that might be in hardpoints
                  !(module.Item && (
                      module.Item.toLowerCase().includes('shieldbooster') ||
                      module.Item.toLowerCase().includes('chafflauncher') ||
                      module.Item.toLowerCase().includes('heatsinklauncher') ||
                      module.Item.toLowerCase().includes('ecm') ||
                      module.Item.toLowerCase().includes('killwarrant') ||
                      module.Item.toLowerCase().includes('cargoscanner') ||
                      module.Item.toLowerCase().includes('cloudscanner') ||
                      module.Item.toLowerCase().includes('crimescanner') ||
                      module.Item.toLowerCase().includes('mrascanner') ||
                      module.Item.toLowerCase().includes('electroniccountermeasure') ||
                      module.Item.toLowerCase().includes('plasmapointdefence') ||
                      module.Item.toLowerCase().includes('antiunknown') ||
                      module.Item.toLowerCase().includes('shutdown')
                  ));
        });
    }
    
    getUtilityModules(): any[] {
        // Include both utility slots and other utility-type modules
        return this.getShipModules().filter(module => {
            // Include traditional utility slot modules
            const isUtilitySlot = module.Slot && module.Slot.includes('Utility');
            
            // Include utility-type modules that might be in hardpoints
            const isUtilityModule = module.Item && (
                module.Item.toLowerCase().includes('shieldbooster') ||
                module.Item.toLowerCase().includes('chafflauncher') ||
                module.Item.toLowerCase().includes('heatsinklauncher') ||
                module.Item.toLowerCase().includes('ecm') ||
                module.Item.toLowerCase().includes('killwarrant') ||
                module.Item.toLowerCase().includes('cargoscanner') ||
                module.Item.toLowerCase().includes('cloudscanner') ||
                module.Item.toLowerCase().includes('crimescanner') ||
                module.Item.toLowerCase().includes('mrascanner') ||
                module.Item.toLowerCase().includes('electroniccountermeasure') ||
                module.Item.toLowerCase().includes('plasmapointdefence') ||
                module.Item.toLowerCase().includes('antiunknown') ||
                module.Item.toLowerCase().includes('shutdown')
            );
            
            return isUtilitySlot || isUtilityModule;
        });
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
        
        // Handle special case material names
        const specialNames: {[key: string]: string} = {
            // Guardian materials
            'guardiantechcomponent': 'Guardian Technology Component',
            'guardianwreckagecomponents': 'Guardian Wreckage Components',
            'guardianpowercell': 'Guardian Power Cell',
            'guardianpowerconduit': 'Guardian Power Conduit',
            'guardiansentinelweaponparts': 'Guardian Sentinel Weapon Parts',
            'vesselblueprint': 'Guardian Vessel Blueprint Fragment',
            'techcomponent': 'Guardian Technology Component',
            
            // Guardian Data
            'ancientbiologicaldata': 'Pattern Alpha Obelisk Data',
            'ancientculturaldata': 'Pattern Beta Obelisk Data',
            'ancienthistoricaldata': 'Pattern Gamma Obelisk Data',
            'ancienttechnologicaldata': 'Pattern Epsilon Obelisk Data',
            
            // Thargoid data
            'interdictiondata': 'Thargoid Interdiction Telemetry',
            'shipflightdata': 'Ship Flight Data',
            'shipsystemsdata': 'Ship Systems Data',
            'shutdowndata': 'Massive Energy Surge Analytics',
            'shipsignature': 'Thargoid Ship Signature',
            
            // Thargoid materials
            'wreckagecomponents': 'Wreckage Components',
            'biomechanicalconduits': 'Bio-Mechanical Conduits',
            'weaponparts': 'Weapon Parts',
            'propulsionelement': 'Propulsion Elements',
            'causticgeneratorparts': 'Corrosive Mechanisms',
            'tgcausticcrystal': 'Caustic Crystal',
            'tgcausticshard': 'Caustic Shard',
            'unknowncarapace': 'Thargoid Carapace',
            'tgabrasion02': 'Phasing Membrane Residue',
            'tgabrasion03': 'Hardened Surface Fragments',
            'unknownenergycell': 'Thargoid Energy Cell',
            'unknowncorechip': 'Tactical Core Chip',
            'unknowntechnologycomponents': 'Thargoid Technological Components',
            
            // Standard engineering materials that were broken
            'eccentrichyperspace': 'Eccentric Hyperspace Trajectories',
            'conductiveceramics': 'Conductive Ceramics',
            'improvisedcomponents': 'Improvised Components',
            'refinedfocuscrystals': 'Refined Focus Crystals',
            'phasealloys': 'Phase Alloys',
            'protolightalloys': 'Proto Light Alloys',
            'protoradiolicalloys': 'Proto Radiolic Alloys'
        };
        
        // Check if it's a special material first
        const normalized = name.toLowerCase().replace(/[^a-zA-Z0-9]/g, '');
        if (specialNames[normalized]) {
            return specialNames[normalized];
        }
        
        // Otherwise, proceed with standard formatting
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
     * Format ship type names by converting internal names to readable ones
     */
    formatShipType(shipType: string): string {
        if (!shipType) return 'Unknown Ship';
        
        // Map of internal ship IDs to display names
        const shipNames: Record<string, string> = {
            'adder': 'Adder',
            'anaconda': 'Anaconda',
            'asp': 'Asp Explorer',
            'asp_scout': 'Asp Scout',
            'belugaliner': 'Beluga Liner',
            'cobramkiii': 'Cobra Mk III',
            'cobramkiv': 'Cobra Mk IV',
            'diamondback': 'Diamondback Scout',
            'diamondbackxl': 'Diamondback Explorer',
            'eagle': 'Eagle',
            'federation_corvette': 'Federal Corvette',
            'federation_dropship': 'Federal Dropship',
            'federation_dropship_mkii': 'Federal Assault Ship',
            'federation_gunship': 'Federal Gunship',
            'fer_de_lance': 'Fer-de-Lance',
            'hauler': 'Hauler',
            'independant_trader': 'Keelback',
            'empire_courier': 'Imperial Courier',
            'empire_eagle': 'Imperial Eagle',
            'empire_fighter': 'Imperial Fighter',
            'empire_trader': 'Imperial Clipper',
            'empire_cutter': 'Imperial Cutter',
            'krait_light': 'Krait Phantom',
            'krait_mkii': 'Krait Mk II',
            'mamba': 'Mamba',
            'orca': 'Orca',
            'python': 'Python',
            'sidewinder': 'Sidewinder',
            'type6': 'Type-6 Transporter',
            'type7': 'Type-7 Transporter',
            'type9': 'Type-9 Heavy',
            'type9_military': 'Type-10 Defender',
            'typex': 'Alliance Chieftain',
            'typex_2': 'Alliance Crusader',
            'typex_3': 'Alliance Challenger',
            'viper': 'Viper Mk III',
            'viper_mkiv': 'Viper Mk IV',
            'vulture': 'Vulture'
        };
        
        // Return the formatted name if found, or capitalize the internal name as fallback
        return shipNames[shipType] || 
            shipType.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
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
        },
        'Guardian Technology': {
            1: ['guardianwreckagecomponents'],
            2: ['guardianpowercell'],
            3: ['guardianpowerconduit'],
            4: ['guardiansentinelweaponparts'],
            5: ['techcomponent']
        },
        'Thargoid Technology': {
            1: ['wreckagecomponents', 'tgabrasion02'],
            2: ['biomechanicalconduits', 'tgabrasion03'],
            3: ['weaponparts', 'unknowncarapace', 'tgcausticshard'],
            4: ['propulsionelement', 'unknownenergycell', 'unknowncorechip'],
            5: ['causticgeneratorparts', 'tgcausticcrystal', 'unknowntechnologycomponents']
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
        },
        'Guardian Data': {
            1: ['ancientbiologicaldata'],
            2: ['ancientculturaldata'],
            3: ['ancienthistoricaldata'],
            4: ['ancienttechnologicaldata'],
            5: ['vesselblueprint']
        },
        'Thargoid Data': {
            1: ['interdictiondata'],
            2: ['shipflightdata'],
            3: ['shipsystemsdata'],
            4: ['shutdowndata'],
            5: ['shipsignature']
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
        // Remove prefixes like 'tg_', 'guardian_', etc. and convert to lowercase
        let normalized = name.toLowerCase();
        
        // First check for direct matches to handle the more complex cases
        // Map external names to internal keys
        const directMappings: {[key: string]: string} = {
            // Guardian materials
            'guardian_sentinel_wreckagecomponents': 'guardianwreckagecomponents',
            'guardian_powercell': 'guardianpowercell',
            'guardian_powerconduit': 'guardianpowerconduit',
            'guardian_sentinel_weaponparts': 'guardiansentinelweaponparts',
            'guardian_techcomponent': 'techcomponent',
            'guardian_vesselblueprint': 'vesselblueprint',
            
            // Ancient data (Guardian)
            'ancientbiologicaldata': 'ancientbiologicaldata',
            'ancientculturaldata': 'ancientculturaldata',
            'ancienthistoricaldata': 'ancienthistoricaldata',
            'ancienttechnologicaldata': 'ancienttechnologicaldata',
            'pattern alpha obelisk data': 'ancientbiologicaldata',
            'pattern beta obelisk data': 'ancientculturaldata', 
            'pattern gamma obelisk data': 'ancienthistoricaldata',
            'pattern epsilon obelisk data': 'ancienttechnologicaldata',
            
            // Thargoid materials
            'tg_wreckagecomponents': 'wreckagecomponents',
            'tg_biomechanicalconduits': 'biomechanicalconduits',
            'tg_weaponparts': 'weaponparts',
            'tg_propulsionelement': 'propulsionelement',
            'tg_causticgeneratorparts': 'causticgeneratorparts',
            'tg_causticcrystal': 'tgcausticcrystal',
            'tg_causticshard': 'tgcausticshard',
            'tg_abrasion02': 'tgabrasion02',
            'tg_abrasion03': 'tgabrasion03',
            'unknowncarapace': 'unknowncarapace',
            'unknownenergycell': 'unknownenergycell',
            'unknowncorechip': 'unknowncorechip',
            'unknowntechnologycomponents': 'unknowntechnologycomponents',
            
            // Thargoid data
            'tg_interdictiondata': 'interdictiondata',
            'tg_shipflightdata': 'shipflightdata', 
            'tg_shipsystemsdata': 'shipsystemsdata',
            'tg_shutdowndata': 'shutdowndata',
            'unknownshipsignature': 'shipsignature',
            'thargoid interdiction telemetry': 'interdictiondata',
            'ship flight data': 'shipflightdata',
            'ship systems data': 'shipsystemsdata',
            'massive energy surge analytics': 'shutdowndata',
            'thargoid ship signature': 'shipsignature',
            
            // Engineering materials that were broken
            'eccentric hyperspace trajectories': 'eccentrichyperspace',
            'conductive ceramics': 'conductiveceramics',
            'improvised components': 'improvisedcomponents',
            'refined focus crystals': 'refinedfocuscrystals',
            'phase alloys': 'phasealloys',
            'proto light alloys': 'protolightalloys',
            'proto radiolic alloys': 'protoradiolicalloys',
            
            // Special cases with different names
            'sensor fragment': 'unknownenergysource',
            'thargoid carapace': 'unknowncarapace',
            'thargoid energy cell': 'unknownenergycell', 
            'tactical core chip': 'unknowncorechip',
            'thargoid technological components': 'unknowntechnologycomponents'
        };
        
        // Check for direct mappings first
        for (const [key, value] of Object.entries(directMappings)) {
            if (normalized === key || normalized.includes(key)) {
                return value;
            }
        }
        
        // If no direct mapping found, normalize by removing all non-alphanumeric characters
        normalized = normalized
            .replace(/^tg_/, '')
            .replace(/^guardian_/, '')
            .replace(/^guardian_sentinel_/, 'guardian')
            .replace(/[^a-z0-9]/g, '');
            
        return normalized;
    }

    // Return the category name for raw materials
    getRawMaterialCategoryName(category: number): string {
        switch(category) {
            case 1: return "Carbon-based";
            case 2: return "Metals";
            case 3: return "Non-Metals";
            case 4: return "Crystalline Structures";
            case 5: return "Thermic";
            case 6: return "Organics";
            case 7: return "Xenobiologicals";
            default: return `Category ${category}`;
        }
    }

    // Return a list of all manufactured material sections
    getManufacturedSections(): string[] {
        return Object.keys(this.manufacturedMaterialsMap);
    }

    // Return a list of all encoded material sections
    getEncodedSections(): string[] {
        return Object.keys(this.encodedMaterialsMap);
    }

    // Return placeholder names for empty material slots
    getEmptyRawMaterialName(grade: number, category: number): string {
        if (this.rawMaterialsMap[category] && this.rawMaterialsMap[category][grade] && this.rawMaterialsMap[category][grade].length > 0) {
            return this.formatMaterialName(this.rawMaterialsMap[category][grade][0]);
        }
        return `Grade ${grade} Material`;
    }

    getEmptyManufacturedMaterialName(section: string, grade: number): string {
        if (this.manufacturedMaterialsMap[section] && this.manufacturedMaterialsMap[section][grade] && this.manufacturedMaterialsMap[section][grade].length > 0) {
            return this.formatMaterialName(this.manufacturedMaterialsMap[section][grade][0]);
        }
        return `${section} G${grade}`;
    }

    getEmptyEncodedMaterialName(section: string, grade: number): string {
        if (this.encodedMaterialsMap[section] && this.encodedMaterialsMap[section][grade] && this.encodedMaterialsMap[section][grade].length > 0) {
            return this.formatMaterialName(this.encodedMaterialsMap[section][grade][0]);
        }
        return `${section} G${grade}`;
    }

    // Filter methods for station services
    getFilteredMarketItems(): any[] {
        const items = this.getProjection('Market')?.Items || [];
        if (!this.marketSearchTerm) return items;
        
        const searchTerm = this.marketSearchTerm.toLowerCase();
        return items.filter((item: any) => {
            const name = (item.Name_Localised || item.Name || '').toLowerCase();
            const category = (item.Category_Localised || item.Category || '').toLowerCase();
            return name.includes(searchTerm) || category.includes(searchTerm);
        });
    }
    
    getFilteredOutfittingItems(): any[] {
        const items = this.getProjection('Outfitting')?.Items || [];
        if (!this.outfittingSearchTerm) return items;
        
        const searchTerm = this.outfittingSearchTerm.toLowerCase();
        return items.filter((item: any) => {
            const name = this.formatModuleName(item.Name || '').toLowerCase();
            return name.includes(searchTerm);
        });
    }
    
    getFilteredShipyardItems(): any[] {
        const items = this.getProjection('Shipyard')?.PriceList || [];
        if (!this.shipyardSearchTerm) return items;
        
        const searchTerm = this.shipyardSearchTerm.toLowerCase();
        return items.filter((ship: any) => {
            const name = (ship.ShipType_Localised || ship.ShipType || '').toLowerCase();
            return name.includes(searchTerm);
        });
    }

    setViewType(viewType: string): void {
        this.viewType = viewType;
        // Reset any panels that might be open
        this.showFriendsPanel = false;
        this.showColonisationPanel = false;
        this.showBackpackDetails = false;
        this.showCargoDetails = false;
        this.showNavDetails = false;
        this.showAllModules = false;
    }

    // Helper for getting credit balance directly from CurrentStatus
    getCurrentBalance(): number {
        // Return current balance from Credits or -1 if not available
        const credits = this.getProjection('CurrentStatus')?.Balance;
        return credits !== undefined ? credits : -1;
    }

    // Engineers helper methods
    getUnlockedEngineers(): any[] {
        const engineers = this.getProjection('EngineerProgress')?.Engineers || [];
        return engineers.filter((e: any) => e.Progress === 'Unlocked');
    }

    getInvitedEngineers(): any[] {
        const engineers = this.getProjection('EngineerProgress')?.Engineers || [];
        return engineers.filter((e: any) => e.Progress === 'Invited');
    }

    getKnownEngineers(): any[] {
        const engineers = this.getProjection('EngineerProgress')?.Engineers || [];
        return engineers.filter((e: any) => e.Progress === 'Known');
    }

    getArray(length: number): any[] {
        return new Array(length);
    }

    // New engineer helper methods
    getFilteredShipEngineers(): any[] {
        const knownEngineers = this.getProjection('EngineerProgress')?.Engineers || [];

        // Merge known engineers with our ship engineers database
        const mergedEngineers = this.shipEngineers.map(staticEngineer => {
            const knownEngineer = knownEngineers.find((e: any) => e.Engineer === staticEngineer.Engineer);
            return knownEngineer ? { ...staticEngineer, ...knownEngineer } : staticEngineer;
        });

        // Apply filter
        if (this.engineerFilter === 'all') {
            return mergedEngineers;
        } else if (this.engineerFilter === 'locked') {
            return mergedEngineers.filter(e => !e.Progress);
        } else {
            return mergedEngineers.filter(e => e.Progress === this.engineerFilter.charAt(0).toUpperCase() + this.engineerFilter.slice(1));
        }
    }

    getFilteredOnFootEngineers(): any[] {
        const knownEngineers = this.getProjection('EngineerProgress')?.Engineers || [];

        // Merge known engineers with our on-foot engineers database
        const mergedEngineers = this.onFootEngineers.map(staticEngineer => {
            const knownEngineer = knownEngineers.find((e: any) => e.Engineer === staticEngineer.Engineer);
            return knownEngineer ? { ...staticEngineer, ...knownEngineer } : staticEngineer;
        });

        // Apply filter
        if (this.onFootEngineerFilter === 'all') {
            return mergedEngineers;
        } else if (this.onFootEngineerFilter === 'locked') {
            return mergedEngineers.filter(e => !e.Progress);
        } else {
            return mergedEngineers.filter(e => e.Progress === this.onFootEngineerFilter.charAt(0).toUpperCase() + this.onFootEngineerFilter.slice(1));
        }
    }

    getEngineerModules(engineerName: string): string {
        const engineer = this.shipEngineers.find(e => e.Engineer === engineerName);
        return engineer?.Modifies || '-';
    }

    getOnFootEngineerModules(engineerName: string): string {
        const engineer = this.onFootEngineers.find(e => e.Engineer === engineerName);
        return engineer?.Modifies || '-';
    }

    getEngineerLocation(engineerName: string): string {
        const shipEngineer = this.shipEngineers.find(e => e.Engineer === engineerName);
        if (shipEngineer) return shipEngineer.Location;

        const onFootEngineer = this.onFootEngineers.find(e => e.Engineer === engineerName);
        return onFootEngineer?.Location || '-';
    }

    getEngineerUnlock(engineerName: string): string {
        const shipEngineer = this.shipEngineers.find(e => e.Engineer === engineerName);
        if (shipEngineer) return shipEngineer.HowToUnlock;

        const onFootEngineer = this.onFootEngineers.find(e => e.Engineer === engineerName);
        return onFootEngineer?.HowToUnlock || '-';
    }

    getEngineerReputationMethod(engineerName: string): string {
        const engineer = this.shipEngineers.find(e => e.Engineer === engineerName);
        return engineer?.HowToGainRep || '-';
    }

    getEngineerReferral(engineerName: string): string {
        const engineer = this.onFootEngineers.find(e => e.Engineer === engineerName);
        return engineer?.HowToReferral || '-';
    }

    // Get engineer information based on their status
    getEngineerInfoBasedOnStatus(engineer: any): string {
        if (!engineer.Progress) {
            return engineer.HowToFind || '-';
        } else if (engineer.Progress === 'Known') {
            return engineer.HowToGetInvite || '-';
        } else if (engineer.Progress === 'Invited') {
            return engineer.HowToUnlock || '-';
        } else if (engineer.Progress === 'Unlocked') {
            return engineer.HowToGainRep || '-';
        }
        return '-';
    }

    // Get on-foot engineer information based on their status
    getOnFootEngineerInfoBasedOnStatus(engineer: any): string {
        if (!engineer.Progress) {
            return engineer.HowToFind || '-';
        } else if (engineer.Progress === 'Known') {
            return engineer.HowToGetInvite || '-';
        } else if (engineer.Progress === 'Invited') {
            return engineer.HowToUnlock || '-';
        } else if (engineer.Progress === 'Unlocked') {
            return engineer.HowToReferral || '-';
        }
        return '-';
    }
}