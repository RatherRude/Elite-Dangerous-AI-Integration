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

                        <!-- Cargo Info -->
                        <div *ngIf="selectedProjection === 'Cargo'">
                            <div class="cargo-header">
                                <h3>Cargo Hold</h3>
                                <div class="stat-group">
                                    <div class="stat-bar">
                                        <mat-progress-bar 
                                            mode="determinate" 
                                            [value]="(formattedData.TotalItems / formattedData.Capacity) * 100"
                                            [matTooltip]="formattedData.TotalItems + ' / ' + formattedData.Capacity + ' tons'"
                                        ></mat-progress-bar>
                                        <span>{{ formattedData.TotalItems }}/{{ formattedData.Capacity }} t</span>
                                    </div>
                                </div>
                            </div>
                            
                            <div *ngIf="formattedData.Inventory && formattedData.Inventory.length > 0">
                                <h4>Inventory</h4>
                                <mat-list>
                                    <mat-list-item *ngFor="let item of formattedData.Inventory" class="cargo-item">
                                        <mat-icon *ngIf="item.Stolen" matTooltip="Stolen" color="warn">warning</mat-icon>
                                        <span class="cargo-count">{{ item.Count }}×</span>
                                        <span class="cargo-name">{{ item.Name }}</span>
                                    </mat-list-item>
                                </mat-list>
                            </div>
                            
                            <div *ngIf="!formattedData.Inventory || formattedData.Inventory.length === 0" class="empty-message">
                                No cargo in hold
                            </div>
                        </div>

                        <!-- Backpack Info -->
                        <div *ngIf="selectedProjection === 'Backpack'">
                            <h3>On-Foot Inventory</h3>
                            
                            <mat-accordion>
                                <mat-expansion-panel *ngIf="formattedData.Items && formattedData.Items.length > 0">
                                    <mat-expansion-panel-header>
                                        <mat-panel-title>
                                            Equipment ({{ formattedData.Items.length }})
                                        </mat-panel-title>
                                    </mat-expansion-panel-header>
                                    
                                    <mat-list>
                                        <mat-list-item *ngFor="let item of formattedData.Items" class="backpack-item">
                                            <span class="item-count">{{ item.Count }}×</span>
                                            <span class="item-name">{{ item.Name_Localised || item.Name }}</span>
                                        </mat-list-item>
                                    </mat-list>
                                </mat-expansion-panel>
                                
                                <mat-expansion-panel *ngIf="formattedData.Components && formattedData.Components.length > 0">
                                    <mat-expansion-panel-header>
                                        <mat-panel-title>
                                            Engineering Components ({{ formattedData.Components.length }})
                                        </mat-panel-title>
                                    </mat-expansion-panel-header>
                                    
                                    <mat-list>
                                        <mat-list-item *ngFor="let item of formattedData.Components" class="backpack-item">
                                            <span class="item-count">{{ item.Count }}×</span>
                                            <span class="item-name">{{ item.Name_Localised || item.Name }}</span>
                                        </mat-list-item>
                                    </mat-list>
                                </mat-expansion-panel>
                                
                                <mat-expansion-panel *ngIf="formattedData.Consumables && formattedData.Consumables.length > 0">
                                    <mat-expansion-panel-header>
                                        <mat-panel-title>
                                            Consumable Items ({{ formattedData.Consumables.length }})
                                        </mat-panel-title>
                                    </mat-expansion-panel-header>
                                    
                                    <mat-list>
                                        <mat-list-item *ngFor="let item of formattedData.Consumables" class="backpack-item">
                                            <span class="item-count">{{ item.Count }}×</span>
                                            <span class="item-name">{{ item.Name_Localised || item.Name }}</span>
                                        </mat-list-item>
                                    </mat-list>
                                </mat-expansion-panel>
                                
                                <mat-expansion-panel *ngIf="formattedData.Data && formattedData.Data.length > 0">
                                    <mat-expansion-panel-header>
                                        <mat-panel-title>
                                            Data Storage ({{ formattedData.Data.length }})
                                        </mat-panel-title>
                                    </mat-expansion-panel-header>
                                    
                                    <mat-list>
                                        <mat-list-item *ngFor="let item of formattedData.Data" class="backpack-item">
                                            <span class="item-count">{{ item.Count }}×</span>
                                            <span class="item-name">{{ item.Name_Localised || item.Name }}</span>
                                        </mat-list-item>
                                    </mat-list>
                                </mat-expansion-panel>
                            </mat-accordion>
                            
                            <div *ngIf="isBackpackEmpty(formattedData)" class="empty-message">
                                Backpack is empty
                            </div>
                        </div>

                        <!-- Suit Loadout -->
                        <div *ngIf="selectedProjection === 'SuitLoadout'">
                            <div class="suit-header">
                                <h3>{{ formattedData.SuitName_Localised || formattedData.SuitName }}</h3>
                                <p class="suit-loadout">Loadout: {{ formattedData.LoadoutName }}</p>
                            </div>
                            
                            <div *ngIf="formattedData.SuitMods && formattedData.SuitMods.length > 0" class="suit-mods">
                                <h4>Suit Modifications</h4>
                                <div class="mod-chips">
                                    <mat-chip-set>
                                        <mat-chip *ngFor="let mod of formattedData.SuitMods">
                                            {{ formatModName(mod) }}
                                        </mat-chip>
                                    </mat-chip-set>
                                </div>
                            </div>
                            
                            <div *ngIf="formattedData.Modules && formattedData.Modules.length > 0">
                                <h4>Equipped Weapons</h4>
                                <mat-list>
                                    <ng-container *ngFor="let weapon of formattedData.Modules">
                                        <mat-list-item class="weapon-item">
                                            <div class="weapon-header">
                                                <span class="weapon-name">{{ weapon.ModuleName_Localised || weapon.ModuleName }}</span>
                                                <span class="weapon-slot">({{ weapon.SlotName }})</span>
                                                <span class="weapon-class">Class {{ weapon.Class }}</span>
                                            </div>
                                        </mat-list-item>
                                        
                                        <div *ngIf="weapon.WeaponMods && weapon.WeaponMods.length > 0" class="weapon-mods">
                                            <mat-chip-set>
                                                <mat-chip *ngFor="let mod of weapon.WeaponMods" color="accent">
                                                    {{ formatModName(mod) }}
                                                </mat-chip>
                                            </mat-chip-set>
                                        </div>
                                        
                                        <mat-divider></mat-divider>
                                    </ng-container>
                                </mat-list>
                            </div>
                            
                            <div *ngIf="!formattedData.Modules || formattedData.Modules.length === 0" class="empty-message">
                                No weapons equipped
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

                        <!-- Target Info -->
                        <div *ngIf="selectedProjection === 'Target'">
                            <div *ngIf="formattedData.Ship">
                                <h3>Target Information</h3>
                                
                                <div class="target-header">
                                    <span class="target-ship">{{ formattedData.Ship }}</span>
                                    <span class="scan-status" 
                                         [ngClass]="{'scan-complete': formattedData.Scanned, 'scan-pending': !formattedData.Scanned}">
                                        {{ formattedData.Scanned ? 'Scan Complete' : 'Scanning...' }}
                                    </span>
                                </div>
                                
                                <div *ngIf="formattedData.Scanned" class="target-details">
                                    <div>
                                        <span class="detail-label">Pilot:</span>
                                        <span class="detail-value">{{ formattedData.PilotName || 'Unknown' }}</span>
                                    </div>
                                    
                                    <div *ngIf="formattedData.PilotRank">
                                        <span class="detail-label">Rank:</span>
                                        <span class="detail-value">{{ formattedData.PilotRank }}</span>
                                    </div>
                                    
                                    <div *ngIf="formattedData.Faction">
                                        <span class="detail-label">Faction:</span>
                                        <span class="detail-value">{{ formattedData.Faction }}</span>
                                    </div>
                                    
                                    <div *ngIf="formattedData.LegalStatus">
                                        <span class="detail-label">Legal Status:</span>
                                        <span class="detail-value" 
                                             [ngClass]="{'status-wanted': formattedData.LegalStatus === 'Wanted', 
                                                       'status-clean': formattedData.LegalStatus === 'Clean'}">
                                            {{ formattedData.LegalStatus }}
                                        </span>
                                    </div>
                                    
                                    <div *ngIf="formattedData.Bounty">
                                        <span class="detail-label">Bounty:</span>
                                        <span class="detail-value">{{ formattedData.Bounty.toLocaleString() }} Cr</span>
                                    </div>
                                    
                                    <div *ngIf="formattedData.Subsystem">
                                        <span class="detail-label">Target Subsystem:</span>
                                        <span class="detail-value">{{ formattedData.Subsystem }}</span>
                                    </div>
                                </div>
                            </div>
                            <div *ngIf="!formattedData.Ship" class="empty-message">
                                No ship targeted
                            </div>
                        </div>

                        <!-- Missions Info -->
                        <div *ngIf="selectedProjection === 'Missions'">
                            <h3>Active Missions</h3>
                            
                            <div *ngIf="formattedData.Active && formattedData.Active.length > 0">
                                <mat-accordion>
                                    <mat-expansion-panel *ngFor="let mission of formattedData.Active">
                                        <mat-expansion-panel-header>
                                            <mat-panel-title>
                                                {{ mission.LocalisedName || mission.Name }}
                                            </mat-panel-title>
                                            <mat-panel-description>
                                                {{ mission.Faction }}
                                                <span *ngIf="mission.Wing" class="wing-mission" matTooltip="Wing Mission">
                                                    <mat-icon>group</mat-icon>
                                                </span>
                                            </mat-panel-description>
                                        </mat-expansion-panel-header>
                                        
                                        <div class="mission-details">
                                            <div class="mission-info-row" *ngIf="mission.DestinationSystem">
                                                <span class="detail-label">Destination:</span>
                                                <span class="detail-value">{{ mission.DestinationSystem }}</span>
                                            </div>
                                            
                                            <div class="mission-info-row" *ngIf="mission.DestinationStation">
                                                <span class="detail-label">Station:</span>
                                                <span class="detail-value">{{ mission.DestinationStation }}</span>
                                            </div>
                                            
                                            <div class="mission-info-row" *ngIf="mission.DestinationSettlement">
                                                <span class="detail-label">Settlement:</span>
                                                <span class="detail-value">{{ mission.DestinationSettlement }}</span>
                                            </div>
                                            
                                            <div class="mission-info-row" *ngIf="mission.Reward">
                                                <span class="detail-label">Reward:</span>
                                                <span class="detail-value">{{ mission.Reward.toLocaleString() }} Cr</span>
                                            </div>
                                            
                                            <div class="mission-info-row" *ngIf="mission.Commodity">
                                                <span class="detail-label">Cargo:</span>
                                                <span class="detail-value">{{ mission.Count }}× {{ mission.Commodity }}</span>
                                            </div>
                                            
                                            <div class="mission-info-row" *ngIf="mission.PassengerCount">
                                                <span class="detail-label">Passengers:</span>
                                                <span class="detail-value">
                                                    {{ mission.PassengerCount }}× {{ mission.PassengerType || 'Passengers' }}
                                                    <span *ngIf="mission.PassengerVIPs" class="vip-badge">VIP</span>
                                                    <span *ngIf="mission.PassengerWanted" class="wanted-badge">Wanted</span>
                                                </span>
                                            </div>
                                            
                                            <div class="mission-info-row">
                                                <span class="detail-label">Influence:</span>
                                                <span class="detail-value">{{ mission.Influence }}</span>
                                            </div>
                                            
                                            <div class="mission-info-row">
                                                <span class="detail-label">Reputation:</span>
                                                <span class="detail-value">{{ mission.Reputation }}</span>
                                            </div>
                                            
                                            <div class="mission-info-row">
                                                <span class="detail-label">Expires:</span>
                                                <span class="detail-value">{{ formatExpiryTime(mission.Expiry) }}</span>
                                            </div>
                                        </div>
                                    </mat-expansion-panel>
                                </mat-accordion>
                            </div>
                            
                            <div *ngIf="!formattedData.Active || formattedData.Active.length === 0" class="empty-message">
                                No active missions
                            </div>
                        </div>

                        <!-- Friends Info -->
                        <div *ngIf="selectedProjection === 'Friends'">
                            <h3>Friends Status</h3>
                            
                            <div *ngIf="formattedData.Online && formattedData.Online.length > 0">
                                <p>{{ formattedData.Online.length }} commander{{ formattedData.Online.length > 1 ? 's' : '' }} online</p>
                                
                                <mat-list>
                                    <mat-list-item *ngFor="let friend of formattedData.Online" class="friend-item">
                                        <mat-icon>person</mat-icon>
                                        <span class="friend-name">CMDR {{ friend }}</span>
                                    </mat-list-item>
                                </mat-list>
                            </div>
                            
                            <div *ngIf="!formattedData.Online || formattedData.Online.length === 0" class="empty-message">
                                No friends currently online
                            </div>
                        </div>

                        <!-- ExobiologyScan -->
                        <div *ngIf="selectedProjection === 'ExobiologyScan'">
                            <h3>Exobiology Scanning</h3>
                            
                            <div *ngIf="formattedData.scans && formattedData.scans.length > 0">
                                <div class="scan-progress">
                                    <div class="scan-header">
                                        <h4>Scan Progress</h4>
                                        <div class="scan-status-indicator" 
                                             [class.scan-too-close]="!formattedData.within_scan_radius"
                                             [class.scan-good-distance]="formattedData.within_scan_radius">
                                            {{ formattedData.within_scan_radius ? 'Good sampling distance' : 'Too close to previous sample' }}
                                        </div>
                                    </div>
                                    
                                    <div class="scan-details">
                                        <div class="scan-count">
                                            <span class="detail-label">Samples:</span>
                                            <span class="detail-value">{{ formattedData.scans.length }}/3</span>
                                        </div>
                                        
                                        <div *ngIf="formattedData.scan_radius">
                                            <span class="detail-label">Sample radius:</span>
                                            <span class="detail-value">{{ formattedData.scan_radius }}m</span>
                                        </div>
                                        
                                        <div *ngIf="formattedData.lat !== undefined && formattedData.long !== undefined">
                                            <span class="detail-label">Current position:</span>
                                            <span class="detail-value">{{ formatCoordinate(formattedData.lat) }}° / {{ formatCoordinate(formattedData.long) }}°</span>
                                        </div>
                                    </div>
                                    
                                    <div class="sample-list">
                                        <h4>Sample Locations</h4>
                                        <mat-list>
                                            <mat-list-item *ngFor="let sample of formattedData.scans; let i = index" class="sample-item">
                                                <div class="sample-location">
                                                    <span class="sample-index">Sample {{ i+1 }}:</span>
                                                    <span class="sample-coordinates">{{ formatCoordinate(sample.lat) }}° / {{ formatCoordinate(sample.long) }}°</span>
                                                </div>
                                            </mat-list-item>
                                        </mat-list>
                                    </div>
                                </div>
                            </div>
                            
                            <div *ngIf="!formattedData.scans || formattedData.scans.length === 0" class="empty-message">
                                No active exobiology scan in progress
                            </div>
                        </div>

                        <!-- ColonisationConstruction -->
                        <div *ngIf="selectedProjection === 'ColonisationConstruction'">
                            <h3>Colony Construction</h3>
                            
                            <div *ngIf="isColonisationActive(formattedData)">
                                <div class="colony-header">
                                    <h4>{{ formattedData.StarSystem || 'Unknown system' }}</h4>
                                    <div class="colony-status" 
                                         [ngClass]="getColonisationStatusClass(formattedData)">
                                        {{ getColonisationStatusText(formattedData) }}
                                    </div>
                                </div>
                                
                                <div class="progress-container">
                                    <h4>Construction Progress</h4>
                                    <div class="stat-bar">
                                        <mat-progress-bar 
                                            mode="determinate" 
                                            [value]="(formattedData.ConstructionProgress || 0) * 100"
                                        ></mat-progress-bar>
                                        <span>{{ formatPercentage(formattedData.ConstructionProgress) }}</span>
                                    </div>
                                </div>
                                
                                <div *ngIf="formattedData.ResourcesRequired && formattedData.ResourcesRequired.length > 0" class="resources-needed">
                                    <h4>Resources Needed</h4>
                                    <mat-list>
                                        <mat-list-item *ngFor="let resource of formattedData.ResourcesRequired" class="resource-item">
                                            <div class="resource-details">
                                                <span class="resource-name">{{ resource.Name_Localised || resource.Name }}</span>
                                                <div class="resource-progress">
                                                    <mat-progress-bar 
                                                        mode="determinate" 
                                                        [value]="(resource.ProvidedAmount / resource.RequiredAmount) * 100"
                                                    ></mat-progress-bar>
                                                    <span class="resource-count">
                                                        {{ resource.ProvidedAmount }}/{{ resource.RequiredAmount }}
                                                    </span>
                                                </div>
                                            </div>
                                        </mat-list-item>
                                    </mat-list>
                                </div>
                            </div>
                            
                            <div *ngIf="!isColonisationActive(formattedData)" class="empty-message">
                                No active colonisation construction
                            </div>
                        </div>

                        <!-- SystemInfo -->
                        <div *ngIf="selectedProjection === 'SystemInfo'">
                            <h3>Star System Information</h3>
                            
                            <div *ngIf="!isEmptyObject(formattedData)">
                                <mat-accordion>
                                    <ng-container *ngFor="let system of getSystemEntries(formattedData)">
                                        <mat-expansion-panel>
                                            <mat-expansion-panel-header>
                                                <mat-panel-title>
                                                    {{ system.name }}
                                                </mat-panel-title>
                                                <mat-panel-description *ngIf="system.data.SystemAddress">
                                                    ID: {{ system.data.SystemAddress }}
                                                </mat-panel-description>
                                            </mat-expansion-panel-header>
                                            
                                            <div class="system-info">
                                                <div *ngIf="system.data.SystemInfo" class="system-details">
                                                    <div *ngIf="system.data.SystemInfo.primaryStar" class="star-info">
                                                        <h4>Primary Star</h4>
                                                        <div class="detail-row">
                                                            <span class="detail-label">Type:</span>
                                                            <span class="detail-value">{{ system.data.SystemInfo.primaryStar.type || 'Unknown' }}</span>
                                                        </div>
                                                        <div class="detail-row">
                                                            <span class="detail-label">Class:</span>
                                                            <span class="detail-value star-class">{{ system.data.StarClass || system.data.SystemInfo.primaryStar.subType || 'Unknown' }}</span>
                                                        </div>
                                                        <div class="detail-row" *ngIf="system.data.SystemInfo.primaryStar.isScoopable">
                                                            <span class="detail-label">Scoopable:</span>
                                                            <span class="detail-value scoopable-star">Yes</span>
                                                        </div>
                                                    </div>
                                                    
                                                    <div *ngIf="system.data.SystemInfo.information" class="system-details-grid">
                                                        <div *ngIf="system.data.SystemInfo.information.population">
                                                            <span class="detail-label">Population:</span>
                                                            <span class="detail-value">{{ formatNumber(system.data.SystemInfo.information.population) }}</span>
                                                        </div>
                                                        
                                                        <div *ngIf="system.data.SystemInfo.information.economy">
                                                            <span class="detail-label">Economy:</span>
                                                            <span class="detail-value">{{ system.data.SystemInfo.information.economy }}</span>
                                                        </div>
                                                        
                                                        <div *ngIf="system.data.SystemInfo.information.government">
                                                            <span class="detail-label">Government:</span>
                                                            <span class="detail-value">{{ system.data.SystemInfo.information.government }}</span>
                                                        </div>
                                                        
                                                        <div *ngIf="system.data.SystemInfo.information.allegiance">
                                                            <span class="detail-label">Allegiance:</span>
                                                            <span class="detail-value">{{ system.data.SystemInfo.information.allegiance }}</span>
                                                        </div>
                                                        
                                                        <div *ngIf="system.data.SystemInfo.information.security">
                                                            <span class="detail-label">Security:</span>
                                                            <span class="detail-value">{{ system.data.SystemInfo.information.security }}</span>
                                                        </div>
                                                        
                                                        <div *ngIf="system.data.SystemInfo.information.faction">
                                                            <span class="detail-label">Controlling Faction:</span>
                                                            <span class="detail-value">{{ system.data.SystemInfo.information.faction }}</span>
                                                        </div>
                                                    </div>
                                                </div>
                                                
                                                <div *ngIf="system.data.Stations && system.data.Stations.length > 0" class="station-list">
                                                    <h4>Stations ({{ system.data.Stations.length }})</h4>
                                                    <mat-list>
                                                        <mat-list-item *ngFor="let station of system.data.Stations" class="station-item">
                                                            <div class="station-details">
                                                                <span class="station-name">{{ station.name }}</span>
                                                                <span class="station-type">{{ station.type }} - {{ formatDistance(station.orbit) }}</span>
                                                                <div class="station-info">
                                                                    <span class="station-economy">{{ station.economy }}</span>
                                                                    <span *ngIf="station.secondEconomy && station.secondEconomy !== 'None'" class="station-economy-secondary">/ {{ station.secondEconomy }}</span>
                                                                    <span class="station-faction">{{ station.controllingFaction }}</span>
                                                                </div>
                                                                <div class="station-services" *ngIf="station.services && station.services.length > 0">
                                                                    <mat-chip-set>
                                                                        <mat-chip *ngFor="let service of station.services" color="accent" selected="true">
                                                                            {{ formatServiceName(service) }}
                                                                        </mat-chip>
                                                                    </mat-chip-set>
                                                                </div>
                                                            </div>
                                                        </mat-list-item>
                                                    </mat-list>
                                                </div>
                                            </div>
                                        </mat-expansion-panel>
                                    </ng-container>
                                </mat-accordion>
                            </div>
                            
                            <div *ngIf="isEmptyObject(formattedData)" class="empty-message">
                                No system information available
                            </div>
                        </div>

                        <!-- EventCounter -->
                        <div *ngIf="selectedProjection === 'EventCounter'" class="content-section event-counter">
                          <h3>Event Counter</h3>
                          <div class="event-counter-grid">
                            <ng-container *ngIf="formattedData && formattedData.data; else noEvents">
                              <div *ngFor="let event of getEventEntries()" class="event-card">
                                <div class="event-name">{{ event.event }}</div>
                                <div class="event-count">{{ event.count }}</div>
                              </div>
                            </ng-container>
                            <ng-template #noEvents>
                              <div class="no-data">No event data available</div>
                            </ng-template>
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
        
        .ship-header, .cargo-header, .suit-header {
            margin-bottom: 20px;
        }
        
        .ship-header h3, .cargo-header h3, .suit-header h3 {
            margin-bottom: 0;
        }
        
        .ship-id, .suit-loadout {
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
        
        .route-item, .cargo-item, .backpack-item {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .route-index {
            min-width: 25px;
            color: rgba(255, 255, 255, 0.7);
        }
        
        .route-system, .cargo-name, .item-name {
            flex-grow: 1;
        }
        
        .cargo-count, .item-count {
            min-width: 40px;
            font-weight: 500;
            color: rgba(255, 255, 255, 0.8);
        }
        
        .route-scoopable {
            color: #2196F3;
        }
        
        .no-route, .empty-message {
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
        
        .mod-chips {
            margin: 10px 0;
        }
        
        .weapon-header {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .weapon-name {
            font-weight: 500;
        }
        
        .weapon-slot {
            color: rgba(255, 255, 255, 0.6);
        }
        
        .weapon-class {
            margin-left: auto;
            color: rgba(255, 255, 255, 0.8);
        }
        
        .weapon-mods {
            margin-left: 40px;
            margin-bottom: 10px;
        }
        
        .suit-mods {
            margin-bottom: 20px;
        }
        
        .target-header {
            display: flex;
            align-items: center;
            margin-bottom: 15px;
        }
        
        .target-ship {
            font-size: 18px;
            font-weight: 500;
            margin-right: 10px;
        }
        
        .scan-status {
            font-size: 12px;
            padding: 3px 8px;
            border-radius: 12px;
        }
        
        .scan-pending {
            background-color: rgba(255, 152, 0, 0.2);
            color: #ff9800;
        }
        
        .scan-complete {
            background-color: rgba(76, 175, 80, 0.2);
            color: #4caf50;
        }
        
        .status-wanted {
            color: #f44336;
            font-weight: 500;
        }
        
        .status-clean {
            color: #4caf50;
        }
        
        .wing-mission {
            margin-left: 8px;
            color: #2196F3;
        }
        
        .mission-details {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        
        .mission-info-row {
            display: flex;
            align-items: center;
        }
        
        .vip-badge, .wanted-badge {
            font-size: 10px;
            padding: 2px 6px;
            border-radius: 10px;
            margin-left: 6px;
            font-weight: 500;
        }
        
        .vip-badge {
            background-color: rgba(33, 150, 243, 0.2);
            color: #2196F3;
        }
        
        .wanted-badge {
            background-color: rgba(244, 67, 54, 0.2);
            color: #f44336;
        }
        
        .friend-item {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .scan-progress {
            margin-top: 15px;
        }
        
        .scan-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        
        .scan-status-indicator {
            font-size: 12px;
            padding: 3px 8px;
            border-radius: 12px;
            font-weight: 500;
        }
        
        .scan-too-close {
            background-color: rgba(244, 67, 54, 0.2);
            color: #f44336;
        }
        
        .scan-good-distance {
            background-color: rgba(76, 175, 80, 0.2);
            color: #4caf50;
        }
        
        .scan-details {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 10px;
            margin-bottom: 20px;
        }
        
        .sample-location {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .sample-index {
            font-weight: 500;
            min-width: 80px;
        }
        
        .sample-coordinates {
            color: rgba(255, 255, 255, 0.8);
        }
        
        .colony-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        
        .colony-status {
            font-size: 12px;
            padding: 3px 8px;
            border-radius: 12px;
            font-weight: 500;
        }
        
        .status-complete {
            background-color: rgba(76, 175, 80, 0.2);
            color: #4caf50;
        }
        
        .status-failed {
            background-color: rgba(244, 67, 54, 0.2);
            color: #f44336;
        }
        
        .status-in-progress {
            background-color: rgba(33, 150, 243, 0.2);
            color: #2196F3;
        }
        
        .progress-container {
            margin-bottom: 20px;
        }
        
        .resource-details {
            display: flex;
            flex-direction: column;
            width: 100%;
        }
        
        .resource-name {
            margin-bottom: 5px;
        }
        
        .resource-progress {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .resource-progress mat-progress-bar {
            flex-grow: 1;
        }
        
        .resource-count {
            white-space: nowrap;
        }
        
        .system-info {
            margin-top: 10px;
        }
        
        .system-details {
            display: flex;
            flex-direction: column;
            gap: 15px;
            margin-bottom: 20px;
        }
        
        .star-info {
            display: flex;
            flex-direction: column;
            gap: 5px;
            margin-bottom: 10px;
        }
        
        .detail-row {
            display: flex;
            gap: 10px;
        }
        
        .system-details-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 10px;
        }
        
        .star-class {
            font-weight: 500;
        }
        
        .scoopable-star {
            color: #2196F3;
        }
        
        .station-details {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }
        
        .station-name {
            font-weight: 500;
            font-size: 16px;
        }
        
        .station-type {
            color: rgba(255, 255, 255, 0.7);
            font-size: 12px;
        }
        
        .station-info {
            display: flex;
            gap: 5px;
            font-size: 14px;
            color: rgba(255, 255, 255, 0.8);
        }
        
        .station-economy {
            font-weight: 500;
        }
        
        .station-faction {
            margin-left: auto;
        }
        
        .station-services {
            margin-top: 5px;
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
        return ['ShipInfo', 'Location', 'CurrentStatus', 'NavInfo', 'Cargo', 'Backpack', 'SuitLoadout', 
                'Target', 'Missions', 'Friends', 'ExobiologyScan', 'ColonisationConstruction', 'SystemInfo'].includes(projectionName);
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
    isColonisationActive(colonisation: any): boolean {
        return colonisation && 
              (colonisation.StarSystem || 
               colonisation.ResourcesRequired?.length > 0 || 
               colonisation.ConstructionProgress > 0);
    }
    
    getColonisationStatusClass(colonisation: any): string {
        if (colonisation.ConstructionComplete) return 'status-complete';
        if (colonisation.ConstructionFailed) return 'status-failed';
        return 'status-in-progress';
    }
    
    getColonisationStatusText(colonisation: any): string {
        if (colonisation.ConstructionComplete) return 'Complete';
        if (colonisation.ConstructionFailed) return 'Failed';
        return 'In Progress';
    }
    
    formatPercentage(value: number | undefined): string {
        if (value === undefined) return '0%';
        return `${(value * 100).toFixed(1)}%`;
    }
    
    // Helper methods for SystemInfo
    isEmptyObject(obj: any): boolean {
        return !obj || Object.keys(obj).length === 0;
    }
    
    getSystemEntries(systemInfo: any): {name: string, data: any}[] {
        if (!systemInfo) return [];
        return Object.entries(systemInfo).map(([name, data]) => ({name, data: data as any}));
    }
    
    formatNumber(value: number): string {
        return value.toLocaleString();
    }
    
    formatDistance(distance: number): string {
        if (distance < 1) {
            return `${(distance * 1000).toFixed(0)} km`;
        }
        return `${distance.toFixed(0)} ls`;
    }
    
    formatServiceName(service: string): string {
        // Capitalize the service name
        return service.charAt(0).toUpperCase() + service.slice(1);
    }

    getEventEntries(): { event: string, count: number }[] {
        if (!this.formattedData || !this.formattedData.data) {
            return [];
        }
        
        const eventEntries: { event: string, count: number }[] = [];
        for (const [event, count] of Object.entries(this.formattedData.data)) {
            if (event !== 'timestamp') {
                eventEntries.push({ event, count: Number(count) });
            }
        }
        return eventEntries;
    }
} 