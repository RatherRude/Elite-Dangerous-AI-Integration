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
import { FormsModule } from "@angular/forms";
import { ProjectionsService } from "../../services/projections.service";
import { Subscription } from "rxjs";

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
        FormsModule
    ],
    template: `
        <div class="status-container">
            <div class="projection-selector">
                <mat-form-field appearance="fill">
                    <mat-label>Select Projection</mat-label>
                    <mat-select [(ngModel)]="selectedProjection" (selectionChange)="formatSelectedProjection()">
                        <mat-option *ngFor="let name of projectionNames" [value]="name">
                            {{ name }}
                        </mat-option>
                    </mat-select>
                </mat-form-field>
            </div>

            <div class="projection-content" *ngIf="selectedProjection && formattedData">
                <mat-card class="status-card">
                    <mat-card-header>
                        <mat-card-title>{{ selectedProjection }}</mat-card-title>
                    </mat-card-header>
                    <mat-card-content>
                        <!-- Ship Info -->
                        <div *ngIf="selectedProjection === 'ShipInfo'">
                            <div class="ship-header">
                                <h3>{{ formattedData.Name || 'Unknown Ship' }}</h3>
                                <p class="ship-id">{{ formattedData.Type }} ({{ formattedData.ShipIdent }})</p>
                            </div>
                            
                            <div class="ship-stats">
                                <div class="stat-group">
                                    <h4>Cargo</h4>
                                    <div class="stat-bar">
                                        <mat-progress-bar 
                                            mode="determinate" 
                                            [value]="(formattedData.Cargo / formattedData.CargoCapacity) * 100"
                                            [matTooltip]="formattedData.Cargo + ' / ' + formattedData.CargoCapacity + ' tons'"
                                        ></mat-progress-bar>
                                        <span>{{ formattedData.Cargo }}/{{ formattedData.CargoCapacity }} t</span>
                                    </div>
                                </div>
                                
                                <div class="stat-group">
                                    <h4>Fuel</h4>
                                    <div class="stat-bar">
                                        <mat-progress-bar 
                                            mode="determinate" 
                                            [value]="(formattedData.FuelMain / formattedData.FuelMainCapacity) * 100"
                                            [matTooltip]="formattedData.FuelMain + ' / ' + formattedData.FuelMainCapacity + ' tons'"
                                        ></mat-progress-bar>
                                        <span>{{ formattedData.FuelMain.toFixed(1) }}/{{ formattedData.FuelMainCapacity }} t</span>
                                    </div>
                                </div>
                                
                                <div class="ship-details">
                                    <div>
                                        <span class="detail-label">Max Jump:</span>
                                        <span class="detail-value">{{ formattedData.MaximumJumpRange.toFixed(1) }} ly</span>
                                    </div>
                                    <div>
                                        <span class="detail-label">Landing Pad:</span>
                                        <span class="detail-value">{{ formattedData.LandingPadSize }}</span>
                                    </div>
                                    <div>
                                        <span class="detail-label">Unladen Mass:</span>
                                        <span class="detail-value">{{ formattedData.UnladenMass.toFixed(1) }} t</span>
                                    </div>
                                    <div>
                                        <span class="detail-label">Mining Ship:</span>
                                        <span class="detail-value">{{ formattedData.IsMiningShip ? 'Yes' : 'No' }}</span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Location Info -->
                        <div *ngIf="selectedProjection === 'Location'">
                            <h3>Current Location</h3>
                            <div class="location-details">
                                <div>
                                    <span class="detail-label">System:</span>
                                    <span class="detail-value">{{ formattedData.StarSystem }}</span>
                                </div>
                                
                                <div *ngIf="formattedData.Star">
                                    <span class="detail-label">Star:</span>
                                    <span class="detail-value">{{ formattedData.Star }}</span>
                                </div>
                                
                                <div *ngIf="formattedData.Planet">
                                    <span class="detail-label">Planet:</span>
                                    <span class="detail-value">{{ formattedData.Planet }}</span>
                                </div>
                                
                                <div *ngIf="formattedData.Station">
                                    <span class="detail-label">Station:</span>
                                    <span class="detail-value">{{ formattedData.Station }}</span>
                                </div>
                                
                                <div *ngIf="formattedData.Docked">
                                    <span class="detail-label">Status:</span>
                                    <span class="detail-value">Docked</span>
                                </div>
                                
                                <div *ngIf="formattedData.Landed">
                                    <span class="detail-label">Status:</span>
                                    <span class="detail-value">Landed</span>
                                </div>
                            </div>
                        </div>

                        <!-- Current Status -->
                        <div *ngIf="selectedProjection === 'CurrentStatus'">
                            <mat-accordion>
                                <mat-expansion-panel>
                                    <mat-expansion-panel-header>
                                        <mat-panel-title>
                                            Flight Status
                                        </mat-panel-title>
                                    </mat-expansion-panel-header>
                                    <div class="status-flags">
                                        <div *ngFor="let flag of statusFlags" class="status-flag" 
                                             [class.active]="formattedData.flags[flag]">
                                            <mat-icon>{{ getIconForFlag(flag) }}</mat-icon>
                                            <span>{{ formatFlagName(flag) }}</span>
                                        </div>
                                    </div>
                                </mat-expansion-panel>
                                
                                <mat-expansion-panel *ngIf="formattedData.flags2">
                                    <mat-expansion-panel-header>
                                        <mat-panel-title>
                                            On-Foot Status
                                        </mat-panel-title>
                                    </mat-expansion-panel-header>
                                    <div class="status-flags">
                                        <div *ngFor="let flag of odysseyFlags" class="status-flag" 
                                             [class.active]="formattedData.flags2[flag]">
                                            <mat-icon>{{ getIconForOdysseyFlag(flag) }}</mat-icon>
                                            <span>{{ formatFlagName(flag) }}</span>
                                        </div>
                                    </div>
                                </mat-expansion-panel>
                                
                                <mat-expansion-panel *ngIf="formattedData.Fuel">
                                    <mat-expansion-panel-header>
                                        <mat-panel-title>
                                            Ship Resources
                                        </mat-panel-title>
                                    </mat-expansion-panel-header>
                                    <div class="resource-bars">
                                        <div class="stat-group">
                                            <h4>Main Fuel</h4>
                                            <div class="stat-bar">
                                                <mat-progress-bar 
                                                    mode="determinate" 
                                                    [value]="(formattedData.Fuel.FuelMain / formattedData.Fuel.FuelCapacity) * 100"
                                                ></mat-progress-bar>
                                                <span>{{ formattedData.Fuel.FuelMain.toFixed(1) }}/{{ formattedData.Fuel.FuelCapacity }} t</span>
                                            </div>
                                        </div>
                                        
                                        <div class="stat-group">
                                            <h4>Reservoir</h4>
                                            <div class="stat-bar">
                                                <mat-progress-bar 
                                                    mode="determinate" 
                                                    [value]="(formattedData.Fuel.FuelReservoir / 0.5) * 100"
                                                ></mat-progress-bar>
                                                <span>{{ formattedData.Fuel.FuelReservoir.toFixed(2) }} t</span>
                                            </div>
                                        </div>
                                    </div>
                                </mat-expansion-panel>
                            </mat-accordion>
                        </div>

                        <!-- Navigation Info -->
                        <div *ngIf="selectedProjection === 'NavInfo'">
                            <h3>Navigation Information</h3>
                            
                            <div *ngIf="formattedData.NextJumpTarget && formattedData.NextJumpTarget !== 'Unknown'">
                                <div class="nav-target">
                                    <span class="detail-label">Next Jump Target:</span>
                                    <span class="detail-value">{{ formattedData.NextJumpTarget }}</span>
                                </div>
                            </div>
                            
                            <div *ngIf="formattedData.NavRoute && formattedData.NavRoute.length > 0">
                                <h4>Navigation Route ({{ formattedData.NavRoute.length }} jumps)</h4>
                                <mat-list>
                                    <mat-list-item *ngFor="let system of formattedData.NavRoute; let i = index">
                                        <div class="route-item">
                                            <span class="route-index">{{ i + 1 }}.</span>
                                            <span class="route-system">{{ system.StarSystem }}</span>
                                            <span class="route-scoopable" *ngIf="system.Scoopable" matTooltip="Fuel Scoopable Star">
                                                <mat-icon>local_gas_station</mat-icon>
                                            </span>
                                        </div>
                                    </mat-list-item>
                                </mat-list>
                            </div>
                            
                            <div *ngIf="!formattedData.NavRoute || formattedData.NavRoute.length === 0" class="no-route">
                                No navigation route plotted.
                            </div>
                        </div>

                        <!-- Default display for other projections -->
                        <div *ngIf="!isCustomFormatted(selectedProjection)">
                            <pre>{{ formattedData | json }}</pre>
                        </div>
                    </mat-card-content>
                </mat-card>
            </div>

            <div class="no-data" *ngIf="!projections || !selectedProjection">
                Waiting for status data...
            </div>
        </div>
    `,
    styles: [`
        .status-container {
            height: 100%;
            overflow-y: auto;
            padding: 10px;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        
        .projection-selector {
            padding: 10px;
        }
        
        mat-form-field {
            width: 100%;
        }
        
        .status-card {
            margin-bottom: 10px;
        }
        
        .no-data {
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100%;
            color: rgba(255, 255, 255, 0.6);
        }
        
        pre {
            white-space: pre-wrap;
            word-break: break-word;
            font-family: monospace;
        }
        
        .ship-header {
            margin-bottom: 20px;
        }
        
        .ship-header h3 {
            margin-bottom: 0;
        }
        
        .ship-id {
            color: rgba(255, 255, 255, 0.7);
            margin-top: 0;
        }
        
        .ship-stats {
            margin-bottom: 10px;
        }
        
        .stat-group {
            margin-bottom: 15px;
        }
        
        .stat-group h4 {
            margin-bottom: 5px;
            font-weight: 500;
        }
        
        .stat-bar {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .stat-bar mat-progress-bar {
            flex-grow: 1;
        }
        
        .ship-details, .location-details {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 10px;
            margin-top: 20px;
        }
        
        .detail-label {
            font-weight: 500;
            margin-right: 5px;
            color: rgba(255, 255, 255, 0.7);
        }
        
        .detail-value {
            color: white;
        }
        
        .status-flags {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            gap: 10px;
        }
        
        .status-flag {
            display: flex;
            align-items: center;
            gap: 5px;
            color: rgba(255, 255, 255, 0.5);
        }
        
        .status-flag.active {
            color: #4caf50;
            font-weight: 500;
        }
        
        .route-item {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .route-index {
            min-width: 25px;
            color: rgba(255, 255, 255, 0.7);
        }
        
        .route-system {
            flex-grow: 1;
        }
        
        .route-scoopable {
            color: #2196F3;
        }
        
        .no-route {
            color: rgba(255, 255, 255, 0.6);
            text-align: center;
            padding: 20px;
        }
        
        mat-list-item {
            height: auto !important;
            margin-bottom: 8px;
        }
        
        .nav-target {
            margin-bottom: 20px;
        }
    `]
})
export class StatusViewComponent implements OnInit, OnDestroy {
    projections: Record<string, any> | null = null;
    projectionNames: string[] = [];
    selectedProjection: string | null = null;
    formattedData: any = null;
    
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
    
    private subscription: Subscription | null = null;

    constructor(private projectionsService: ProjectionsService) {}

    ngOnInit(): void {
        this.subscription = this.projectionsService.projections$.subscribe(projections => {
            this.projections = projections;
            if (projections) {
                this.projectionNames = Object.keys(projections).sort();
                
                // Set default selected projection if not already set
                if (!this.selectedProjection && this.projectionNames.includes('CurrentStatus')) {
                    this.selectedProjection = 'CurrentStatus';
                    this.formatSelectedProjection();
                } else if (this.selectedProjection) {
                    this.formatSelectedProjection();
                }
            } else {
                this.projectionNames = [];
                this.formattedData = null;
            }
        });
    }

    ngOnDestroy(): void {
        if (this.subscription) {
            this.subscription.unsubscribe();
        }
    }
    
    formatSelectedProjection(): void {
        if (!this.selectedProjection || !this.projections) {
            this.formattedData = null;
            return;
        }
        
        // Get the raw data for the selected projection
        const rawData = this.projections[this.selectedProjection];
        
        // Use the default JSON for now
        this.formattedData = rawData;
    }
    
    isCustomFormatted(projectionName: string): boolean {
        // Return true for projections that have custom formatting
        return ['ShipInfo', 'Location', 'CurrentStatus', 'NavInfo'].includes(projectionName);
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
} 