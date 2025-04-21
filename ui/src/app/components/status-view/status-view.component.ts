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
    template: `
        <div class="status-container">
            <div class="tab-layout">
                <div class="tab-sidebar">
                    <button class="tab-button" [class.active]="selectedTab === INFORMATION_TAB" (click)="setActiveTab(INFORMATION_TAB)">
                        <mat-icon>info</mat-icon>
                        <span>Info</span>
                    </button>
                    <button class="tab-button" [class.active]="selectedTab === COMMANDER_TAB" (click)="setActiveTab(COMMANDER_TAB)">
                        <mat-icon>person</mat-icon>
                        <span>Commander</span>
                    </button>
                    <button class="tab-button" [class.active]="selectedTab === STATION_TAB" 
                            *ngIf="isInStation()" (click)="setActiveTab(STATION_TAB)">
                        <mat-icon>store</mat-icon>
                        <span>Station</span>
                    </button>
                    <button class="tab-button" [class.active]="selectedTab === STORAGE_TAB" (click)="setActiveTab(STORAGE_TAB)">
                        <mat-icon>inventory_2</mat-icon>
                        <span>Storage</span>
                    </button>
                </div>

                <div class="tab-content">
                    <!-- Info Tab Content -->
                    <div *ngIf="selectedTab === INFORMATION_TAB" class="tab-pane">
                        <!-- Current Status Icons (fixed at upper right) -->
                        <div class="status-indicators-fixed">
                            <div class="active-status-icons">
                                <ng-container *ngFor="let flag of statusFlags">
                                    <div *ngIf="getCurrentStatusValue('flags', flag)" class="status-icon">
                                        <mat-icon matTooltip="{{ formatFlagName(flag) }}">{{ getIconForFlag(flag) }}</mat-icon>
                                    </div>
                                </ng-container>
                                <ng-container *ngFor="let flag of odysseyFlags">
                                    <div *ngIf="getCurrentStatusValue('flags2', flag)" class="status-icon">
                                        <mat-icon matTooltip="{{ formatFlagName(flag) }}">{{ getIconForOdysseyFlag(flag) }}</mat-icon>
                                    </div>
                                </ng-container>
                                
                                <!-- Friends counter -->
                                <div class="friends-counter" (click)="toggleFriendsPanel()" *ngIf="getFriendsCount() > 0">
                                    <mat-icon>people</mat-icon>
                                    <span class="badge">{{ getFriendsCount() }}</span>
                                </div>
                                
                                <!-- Colonisation Construction indicator -->
                                <div *ngIf="isColonisationActive(getProjection('ColonisationConstruction'))" 
                                     class="colonisation-indicator" 
                                     (click)="toggleColonisationPanel()">
                                    <mat-icon>construction</mat-icon>
                                    <span class="progress-text">{{ formatPercentage(getColonisationProgress()) }}</span>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Location & Nav info (minimalistic) -->
                        <div class="location-nav-container">
                            <div class="location-info">
                                <mat-icon>public</mat-icon>
                                <div class="location-details">
                                    <div class="system-name">{{ getLocationSystem() }}</div>
                                    <div *ngIf="getLocationDetail()" class="location-detail">
                                        <mat-icon class="small-icon">{{ getLocationDetailIcon() }}</mat-icon>
                                        <span>{{ getLocationDetail() }}</span>
                                    </div>
                                </div>
                            </div>
                            <div *ngIf="hasNavRoute()" class="nav-info" (click)="toggleNavDetails()">
                                <mat-icon>navigation</mat-icon>
                                <span>{{ getNavRouteInfo() }}</span>
                                <mat-icon class="expander">{{ showNavDetails ? 'expand_less' : 'expand_more' }}</mat-icon>
                            </div>
                        </div>
                        
                        <!-- Nav Route Details -->
                        <div *ngIf="showNavDetails" class="nav-details">
                            <div class="nav-route-list">
                                <div *ngFor="let system of getNavRouteDetails(); let i = index" class="nav-route-item">
                                    <div class="nav-index">{{ i + 1 }}</div>
                                    <div class="nav-system">{{ system.StarSystem }}</div>
                                    <div class="nav-star-info" *ngIf="system.StarClass">
                                        <mat-icon class="star-icon" [ngClass]="getStarClassColor(system.StarClass)">
                                            {{ getStarTypeIcon(system.StarClass) }}
                                        </mat-icon>
                                        <span class="star-class">{{ system.StarClass }}</span>
                                    </div>
                                    <div class="nav-distance" *ngIf="system.StarPos && i > 0">
                                        {{ getJumpDistance(i) }} ly
                                    </div>
                                    <div class="star-scoopable" *ngIf="system.Scoopable !== undefined">
                                        <mat-icon class="fuel-icon" [ngClass]="system.Scoopable ? 'scoopable' : 'not-scoopable'">
                                            {{ system.Scoopable ? 'local_gas_station' : 'not_interested' }}
                                        </mat-icon>
                                        <span class="small-text">{{ system.Scoopable ? 'Scoopable' : 'Not scoopable' }}</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Context-dependent content based on active mode -->
                        <div *ngIf="getActiveMode() === 'humanoid'" class="context-content character-sheet">
                            <!-- TOP SECTION - Character Identity -->
                            <div class="character-header">
                                <div class="character-name">
                                    <h2>{{ getSuitName() }}</h2>
                                    <div class="character-subtitle">{{ getSuitLoadoutName() }}</div>
                                </div>
                                <div class="character-class">
                                    <div class="class-circle">
                                        <div class="circle-value">{{getSuitClass()}}</div>
                                    </div>
                                    <div class="class-label">CLASS</div>
                                </div>
                            </div>
                            
                            <!-- CHARACTER SHEET MAIN SECTION -->
                            <div class="character-sheet-body">
                                <!-- LEFT COLUMN - Attributes/Abilities -->
                                <div class="sheet-column attributes-column">
                                    <div class="stat-block suit-mods">
                                        <h3 class="stat-header">SUIT MODIFICATIONS</h3>
                                        <div class="mod-list">
                                            <div *ngFor="let mod of getSuitMods()" class="mod-item">
                                                <div class="mod-icon">
                                                    <mat-icon>{{ getSuitModIcon(mod) }}</mat-icon>
                                                </div>
                                                <div class="mod-name">{{ formatModName(mod) }}</div>
                                            </div>
                                            <div *ngIf="!getSuitMods().length" class="empty-state">No modifications</div>
                                        </div>
                                    </div>
                                    
                                    <div class="proficiencies-block">
                                        <h3 class="stat-header">PROFICIENCIES</h3>
                                        <div class="proficiency-item">
                                            <span class="proficiency-name">Combat</span>
                                            <div class="proficiency-value">Advanced</div>
                                        </div>
                                        <div class="proficiency-item">
                                            <span class="proficiency-name">Engineering</span>
                                            <div class="proficiency-value">Basic</div>
                                        </div>
                                    </div>
                                </div>
                                
                                <!-- MIDDLE COLUMN - Combat Stats -->
                                <div class="sheet-column stats-column">
                                    <div class="combat-stats">
                                        <div class="combat-stat-item">
                                            <div class="combat-stat-circle">
                                                <span class="combat-stat-value">100%</span>
                                            </div>
                                            <div class="combat-stat-label">HEALTH</div>
                                        </div>
                                        
                                        <div class="combat-stat-item">
                                            <div class="combat-stat-circle">
                                                <span class="combat-stat-value">100%</span>
                                            </div>
                                            <div class="combat-stat-label">SHIELDS</div>
                                        </div>
                                        
                                        <div class="combat-stat-item">
                                            <div class="combat-stat-circle">
                                                <span class="combat-stat-value">100%</span>
                                            </div>
                                            <div class="combat-stat-label">OXYGEN</div>
                                        </div>
                                        
                                        <div class="combat-stat-item">
                                            <div class="combat-stat-circle">
                                                <span class="combat-stat-value">100%</span>
                                            </div>
                                            <div class="combat-stat-label">BATTERY</div>
                                        </div>
                                    </div>
                                </div>
                                
                                <!-- RIGHT COLUMN - Weapons/Equipment -->
                                <div class="sheet-column weapons-column">
                                    <h3 class="stat-header">ARMAMENTS</h3>
                                    <div class="weapons-list">
                                        <ng-container *ngFor="let weapon of getSuitWeapons()">
                                            <div class="weapon-card">
                                                <div class="weapon-header">
                                                    <div class="weapon-name">{{ weapon.ModuleName_Localised || weapon.ModuleName }}</div>
                                                    <div class="weapon-class">
                                                        <div class="class-bubble">{{ weapon.Class || '?' }}</div>
                                                    </div>
                                                </div>
                                                <div class="weapon-type">{{ getWeaponType(weapon) }}</div>
                                                <div class="weapon-slot">{{ formatWeaponSlot(weapon.SlotName) }}</div>
                                                <div class="weapon-mods">
                                                    <ng-container *ngIf="weapon.WeaponMods && weapon.WeaponMods.length">
                                                        <div *ngFor="let mod of weapon.WeaponMods" class="weapon-mod-tag">
                                                            {{ formatModName(mod) }}
                                                        </div>
                                                    </ng-container>
                                                    <div *ngIf="!weapon.WeaponMods || !weapon.WeaponMods.length" class="empty-state">
                                                        No modifications
                                                    </div>
                                                </div>
                                            </div>
                                        </ng-container>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- BOTTOM SECTION - Equipment/Inventory -->
                            <div class="character-sheet-footer">
                                <h3 class="section-header">EQUIPMENT & INVENTORY</h3>
                                <div class="backpack-block" (click)="toggleBackpackDetails()">
                                    <div class="backpack-summary">
                                        <div class="backpack-category" *ngIf="getBackpackItems('Items').length > 0">
                                            <span class="category-name">Items:</span>
                                            <span class="category-count">{{ getBackpackItems('Items').length }}</span>
                                        </div>
                                        <div class="backpack-category" *ngIf="getBackpackItems('Components').length > 0">
                                            <span class="category-name">Components:</span>
                                            <span class="category-count">{{ getBackpackItems('Components').length }}</span>
                                        </div>
                                        <div class="backpack-category" *ngIf="getBackpackItems('Consumables').length > 0">
                                            <span class="category-name">Consumables:</span>
                                            <span class="category-count">{{ getBackpackItems('Consumables').length }}</span>
                                        </div>
                                        <div class="backpack-category" *ngIf="getBackpackItems('Data').length > 0">
                                            <span class="category-name">Data:</span>
                                            <span class="category-count">{{ getBackpackItems('Data').length }}</span>
                                        </div>
                                        <mat-icon>{{ showBackpackDetails ? 'expand_less' : 'expand_more' }}</mat-icon>
                                    </div>
                                    
                                    <div *ngIf="showBackpackDetails" class="backpack-details">
                                        <div *ngFor="let category of ['Items', 'Components', 'Consumables', 'Data']">
                                            <div *ngIf="getBackpackItems(category).length > 0" class="backpack-category-section">
                                                <h4>{{ category }}</h4>
                                                <div class="backpack-items">
                                                    <div *ngFor="let item of getBackpackItems(category)" class="backpack-item">
                                                        <span class="item-name">{{ item.Name_Localised || item.Name }}</span>
                                                        <span class="item-count" *ngIf="item.Count">x{{ item.Count }}</span>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <div *ngIf="['mainship', 'fighter', 'buggy'].includes(getActiveMode())" class="context-content character-sheet">
                            <!-- TOP SECTION - Ship Identity -->
                            <div class="character-header">
                                <div class="character-name">
                                    <h2>{{ getShipName() }}</h2>
                                    <div class="character-subtitle">{{ getShipType() }} {{ getActiveMode() !== 'buggy' ? '(' + getShipIdent() + ')' : '' }}</div>
                                </div>
                                <div class="character-class">
                                    <div class="class-circle">
                                        <div class="circle-value">{{ getLandingPadSize() }}</div>
                                    </div>
                                    <div class="class-label">SIZE</div>
                                </div>
                            </div>
                            
                            <!-- SHIP SHEET MAIN SECTION -->
                            <div class="character-sheet-body">
                                <!-- LEFT COLUMN - Core Stats -->
                                <div class="sheet-column attributes-column">
                                    <div class="ship-core-stats">
                                        <div class="ship-stat-item">
                                            <div class="stat-label">MASS</div>
                                            <div class="stat-value-large">{{ getShipMass().toFixed(1) }}</div>
                                            <div class="stat-suffix">TONS</div>
                                        </div>
                                        
                                        <div class="ship-stat-item">
                                            <div class="stat-label">JUMP RANGE</div>
                                            <div class="stat-value-large">{{ getJumpRange().toFixed(1) }}</div>
                                            <div class="stat-suffix">LY</div>
                                        </div>
                                        
                                        <!-- Nav route summary has been moved to the top location section -->
                                    </div>
                                    
                                    <!-- Remove the nav-details section from here -->
                                </div>
                                
                                <!-- MIDDLE COLUMN - Defense Stats -->
                                <div class="sheet-column stats-column">
                                    <div class="ship-defense-stats">
                                        <div class="defense-stat-item">
                                            <div class="stat-label">HULL</div>
                                            <div class="stat-value-with-bar">
                                                <div class="stat-value">{{ getShipHealth() }}</div>
                                                <mat-progress-bar class="stat-bar" mode="determinate" [value]="getShipHealthPercentage()"></mat-progress-bar>
                                            </div>
                                        </div>
                                        
                                        <div class="defense-stat-item">
                                            <div class="stat-label">FUEL</div>
                                            <div class="stat-value-with-bar">
                                                <div class="stat-value">{{ getFuelAmount() }}/{{ getFuelCapacity() }}</div>
                                                <mat-progress-bar class="stat-bar" mode="determinate" [value]="getFuelPercentage()"></mat-progress-bar>
                                            </div>
                                        </div>
                                        
                                        <div class="defense-stat-item cargo-box" (click)="toggleCargoDetails()">
                                            <div class="stat-label">CARGO <mat-icon class="tiny-icon">{{ showCargoDetails ? 'expand_less' : 'expand_more' }}</mat-icon></div>
                                            <div class="stat-value-with-bar">
                                                <div class="stat-value">{{ getCargoAmount() }}/{{ getCargoCapacity() }}</div>
                                                <mat-progress-bar class="stat-bar" mode="determinate" [value]="getCargoPercentage()"></mat-progress-bar>
                                            </div>
                                        </div>
                                        
                                        <div class="defense-stat-item">
                                            <div class="stat-label">REBUY</div>
                                            <div class="stat-value-large cr">{{ getShipRebuy() | number }}</div>
                                        </div>
                                    </div>
                                </div>
                                
                                <!-- RIGHT COLUMN - Weapons/Hardpoints -->
                                <div class="sheet-column weapons-column">
                                    <h3 class="stat-header">ARMAMENTS</h3>
                                    <div class="hardpoints-list">
                                        <ng-container *ngFor="let module of getWeaponModules()">
                                            <div class="hardpoint-item">
                                                <div class="hardpoint-details weapon-display">
                                                    <span class="hardpoint-name">{{ formatModuleName(module.Item) }}</span>
                                                </div>
                                                <div class="hardpoint-engineering" *ngIf="module.Engineering">
                                                    <mat-icon class="engineering-icon" [matTooltip]="getEngineeringTooltip(module)">build</mat-icon>
                                                </div>
                                            </div>
                                        </ng-container>
                                        <div *ngIf="!getWeaponModules().length" class="empty-state">No weapons equipped</div>
                                    </div>
                                    
                                    <h3 class="stat-header">UTILITY</h3>
                                    <div class="utility-list">
                                        <ng-container *ngFor="let module of getUtilityModules()">
                                            <div class="utility-item">
                                                <div class="utility-details">
                                                    <span class="utility-name">{{ formatModuleName(module.Item) }}</span>
                                                </div>
                                                <div class="utility-engineering" *ngIf="module.Engineering">
                                                    <mat-icon class="engineering-icon" [matTooltip]="getEngineeringTooltip(module)">build</mat-icon>
                                                </div>
                                            </div>
                                        </ng-container>
                                        <div *ngIf="!getUtilityModules().length" class="empty-state">No utility modules equipped</div>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- SHIP CARGO DISPLAY -->
                            <div *ngIf="showCargoDetails" class="cargo-details">
                                <h3 class="section-header">CARGO MANIFEST</h3>
                                <div class="cargo-list">
                                    <div *ngFor="let item of getCargoItems()" class="cargo-item">
                                        <span class="cargo-item-name">{{ item.Name_Localised || item.Name }}</span>
                                        <span class="cargo-item-count">x{{ item.Count }}</span>
                                    </div>
                                    <div *ngIf="!hasCargoItems()" class="empty-state">Cargo hold empty</div>
                                </div>
                            </div>
                            
                            <!-- BOTTOM SECTION - Core & Optional Modules -->
                            <div class="character-sheet-footer">
                                <div class="modules-section">
                                    <h3 class="section-header">CORE INTERNALS</h3>
                                    <div class="module-list core-modules">
                                        <ng-container *ngFor="let module of getCoreModules()">
                                            <div class="module-item">
                                                <div class="module-slot">{{ formatSlotName(module.Slot) }}</div>
                                                <div class="module-details">
                                                    <span class="module-name">{{ formatModuleName(module.Item) }}</span>
                                                    <span class="module-class" *ngIf="getModuleClassAndRating(module.Item).length > 0">
                                                        {{ getModuleClassAndRating(module.Item) }}
                                                    </span>
                                                </div>
                                                <div class="module-engineering" *ngIf="module.Engineering">
                                                    <mat-icon class="engineering-icon" [matTooltip]="getEngineeringTooltip(module)">build</mat-icon>
                                                </div>
                                            </div>
                                        </ng-container>
                                    </div>
                                </div>
                                
                                <div class="modules-section">
                                    <h3 class="section-header">OPTIONAL INTERNALS</h3>
                                    <div class="module-list optional-modules">
                                        <ng-container *ngFor="let module of getOptionalModules()">
                                            <div class="module-item">
                                                <div class="module-slot">{{ formatSlotName(module.Slot) }}</div>
                                                <div class="module-details">
                                                    <span class="module-name">{{ formatModuleName(module.Item) }}</span>
                                                    <span class="module-class" *ngIf="getModuleClassAndRating(module.Item).length > 0">
                                                        {{ getModuleClassAndRating(module.Item) }}
                                                    </span>
                                                </div>
                                                <div class="module-engineering" *ngIf="module.Engineering">
                                                    <mat-icon class="engineering-icon" [matTooltip]="getEngineeringTooltip(module)">build</mat-icon>
                                                </div>
                                            </div>
                                        </ng-container>
                                    </div>
                                    
                                    <div *ngIf="getShipModules().length > getVisibleModulesCount() && !showAllModules" 
                                         class="show-more" (click)="toggleAllModules()">
                                        Show All Modules ({{ getShipModules().length }})
                                    </div>
                                    
                                    <div *ngIf="showAllModules" class="show-less" (click)="toggleAllModules()">
                                        Show Less
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- ExobiologyScan (if active) -->
                        <mat-card *ngIf="hasActiveBioScan()">
                            <mat-card-header>
                                <mat-card-title>Exobiology Scan</mat-card-title>
                            </mat-card-header>
                            <mat-card-content>
                                <div class="scan-progress">
                                    <div class="scan-header">
                                        <h4>Scan Progress</h4>
                                        <div class="scan-status-indicator" 
                                            [class.scan-too-close]="!isWithinScanRadius()"
                                            [class.scan-good-distance]="isWithinScanRadius()">
                                            {{ isWithinScanRadius() ? 'Good sampling distance' : 'Too close to previous sample' }}
                                        </div>
                                    </div>
                                    
                                    <div class="scan-summary">
                                        <span class="detail-label">Samples:</span>
                                        <span class="detail-value">{{ getBioScanCount() }}/3</span>
                                    </div>
                                </div>
                            </mat-card-content>
                        </mat-card>
                        
                        <!-- Expandable panels -->
                        <div *ngIf="showFriendsPanel" class="expandable-panel friends-panel">
                            <h3>Friends Online</h3>
                            <mat-list>
                                <mat-list-item *ngFor="let friend of getOnlineFriends()" class="friend-item">
                                    <mat-icon>person</mat-icon>
                                    <span class="friend-name">CMDR {{ friend }}</span>
                                </mat-list-item>
                            </mat-list>
                            <div *ngIf="!getOnlineFriends().length" class="empty-message">
                                No friends currently online
                            </div>
                        </div>
                        
                        <div *ngIf="showColonisationPanel" class="expandable-panel colonisation-panel">
                            <h3>Colony Construction</h3>
                            <div class="colony-header">
                                <h4>{{ getColonisationSystem() }}</h4>
                                <div class="colony-status" [ngClass]="getColonisationStatusClass()">
                                    {{ getColonisationStatusText() }}
                                </div>
                            </div>
                            
                            <div class="progress-container">
                                <h4>Construction Progress</h4>
                                <div class="stat-bar">
                                    <mat-progress-bar 
                                        mode="determinate" 
                                        [value]="getColonisationProgressValue()"
                                    ></mat-progress-bar>
                                    <span>{{ formatPercentage(getColonisationProgress()) }}</span>
                                </div>
                            </div>
                            
                            <div *ngIf="getColonisationResources().length > 0" class="resources-needed">
                                <h4>Resources Needed</h4>
                                <mat-list>
                                    <mat-list-item *ngFor="let resource of getColonisationResources()" class="resource-item">
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
                    </div>
                    
                    <!-- Commander Tab Content -->
                    <div *ngIf="selectedTab === COMMANDER_TAB" class="tab-pane">
                        <h2>Commander Profile</h2>
                        <div class="commander-info">
                            <!-- Basic Commander Info Card -->
                            <mat-card>
                                <mat-card-header>
                                    <mat-card-title>CMDR {{ getCommanderName() }}</mat-card-title>
                                    <mat-card-subtitle *ngIf="getProjection('Commander')?.FID">ID: {{ getProjection('Commander')?.FID }}</mat-card-subtitle>
                                </mat-card-header>
                                <mat-card-content>
                                    <div class="commander-basic">
                                        <div *ngIf="getBalance()">
                                            <span class="detail-label">Credits:</span>
                                            <span class="detail-value">{{ formatNumber(getBalance()) }}</span>
                                        </div>
                                        <div *ngIf="getActiveMode()">
                                            <span class="detail-label">Active Mode:</span>
                                            <span class="detail-value">{{ getActiveMode() }}</span>
                                        </div>
                                    </div>
                                </mat-card-content>
                            </mat-card>
                            
                            <!-- Ranks & Progress Card -->
                            <mat-card>
                                <mat-card-header>
                                    <mat-card-title>Ranks & Progress</mat-card-title>
                                </mat-card-header>
                                <mat-card-content>
                                    <div class="ranks-container">
                                        <!-- Combat rank -->
                                        <div class="rank-item">
                                            <span class="rank-name">Combat</span>
                                            <div class="rank-value">{{ getRank('Combat') }}</div>
                                            <mat-progress-bar 
                                                mode="determinate" 
                                                [value]="getRankProgress('Combat')"
                                                matTooltip="Progress: {{getProjection('Progress')?.Combat}}%"
                                            ></mat-progress-bar>
                                        </div>
                                        <!-- Trade rank -->
                                        <div class="rank-item">
                                            <span class="rank-name">Trade</span>
                                            <div class="rank-value">{{ getRank('Trade') }}</div>
                                            <mat-progress-bar 
                                                mode="determinate" 
                                                [value]="getRankProgress('Trade')"
                                                matTooltip="Progress: {{getProjection('Progress')?.Trade}}%"
                                            ></mat-progress-bar>
                                        </div>
                                        <!-- Explore rank -->
                                        <div class="rank-item">
                                            <span class="rank-name">Explore</span>
                                            <div class="rank-value">{{ getRank('Explore') }}</div>
                                            <mat-progress-bar 
                                                mode="determinate" 
                                                [value]="getRankProgress('Explore')"
                                                matTooltip="Progress: {{getProjection('Progress')?.Explore}}%"
                                            ></mat-progress-bar>
                                        </div>
                                        <!-- Soldier rank (Odyssey) -->
                                        <div class="rank-item">
                                            <span class="rank-name">Soldier</span>
                                            <div class="rank-value">{{ getRank('Soldier') }}</div>
                                            <mat-progress-bar 
                                                mode="determinate" 
                                                [value]="getRankProgress('Soldier')"
                                                matTooltip="Progress: {{getProjection('Progress')?.Soldier}}%"
                                            ></mat-progress-bar>
                                        </div>
                                        <!-- Exobiologist rank (Odyssey) -->
                                        <div class="rank-item">
                                            <span class="rank-name">Exobiologist</span>
                                            <div class="rank-value">{{ getRank('Exobiologist') }}</div>
                                            <mat-progress-bar 
                                                mode="determinate" 
                                                [value]="getRankProgress('Exobiologist')"
                                                matTooltip="Progress: {{getProjection('Progress')?.Exobiologist}}%"
                                            ></mat-progress-bar>
                                        </div>
                                        <!-- CQC rank -->
                                        <div class="rank-item">
                                            <span class="rank-name">CQC</span>
                                            <div class="rank-value">{{ getRank('CQC') }}</div>
                                            <mat-progress-bar 
                                                mode="determinate" 
                                                [value]="getRankProgress('CQC')"
                                                matTooltip="Progress: {{getProjection('Progress')?.CQC}}%"
                                            ></mat-progress-bar>
                                        </div>
                                        <!-- Federation rank -->
                                        <div class="rank-item">
                                            <span class="rank-name">Federation</span>
                                            <div class="rank-value">{{ getRank('Federation') }}</div>
                                            <mat-progress-bar 
                                                mode="determinate" 
                                                [value]="getRankProgress('Federation')"
                                                matTooltip="Progress: {{getProjection('Progress')?.Federation}}%"
                                            ></mat-progress-bar>
                                        </div>
                                        <!-- Empire rank -->
                                        <div class="rank-item">
                                            <span class="rank-name">Empire</span>
                                            <div class="rank-value">{{ getRank('Empire') }}</div>
                                            <mat-progress-bar 
                                                mode="determinate" 
                                                [value]="getRankProgress('Empire')"
                                                matTooltip="Progress: {{getProjection('Progress')?.Empire}}%"
                                            ></mat-progress-bar>
                                        </div>
                                    </div>
                                </mat-card-content>
                            </mat-card>
                            
                            <!-- Reputation Card -->
                            <mat-card>
                                <mat-card-header>
                                    <mat-card-title>Reputation</mat-card-title>
                                </mat-card-header>
                                <mat-card-content>
                                    <div class="reputation-container">
                                        <!-- Federation reputation -->
                                        <div class="reputation-item">
                                            <span class="reputation-name">Federation</span>
                                            <mat-progress-bar 
                                                mode="determinate" 
                                                [value]="getProjection('Reputation')?.Federation || 0"
                                                [matTooltip]="formatPercentage(getProjection('Reputation')?.Federation)"
                                            ></mat-progress-bar>
                                            <span class="reputation-value">{{ formatPercentage(getProjection('Reputation')?.Federation) }}</span>
                                        </div>
                                        <!-- Empire reputation -->
                                        <div class="reputation-item">
                                            <span class="reputation-name">Empire</span>
                                            <mat-progress-bar 
                                                mode="determinate" 
                                                [value]="getProjection('Reputation')?.Empire || 0"
                                                [matTooltip]="formatPercentage(getProjection('Reputation')?.Empire)"
                                            ></mat-progress-bar>
                                            <span class="reputation-value">{{ formatPercentage(getProjection('Reputation')?.Empire) }}</span>
                                        </div>
                                        <!-- Alliance reputation -->
                                        <div class="reputation-item">
                                            <span class="reputation-name">Alliance</span>
                                            <mat-progress-bar 
                                                mode="determinate" 
                                                [value]="getProjection('Reputation')?.Alliance || 0"
                                                [matTooltip]="formatPercentage(getProjection('Reputation')?.Alliance)"
                                            ></mat-progress-bar>
                                            <span class="reputation-value">{{ formatPercentage(getProjection('Reputation')?.Alliance) }}</span>
                                        </div>
                                        <!-- Independent reputation -->
                                        <div class="reputation-item">
                                            <span class="reputation-name">Independent</span>
                                            <mat-progress-bar 
                                                mode="determinate" 
                                                [value]="getProjection('Reputation')?.Independent || 0"
                                                [matTooltip]="formatPercentage(getProjection('Reputation')?.Independent)"
                                            ></mat-progress-bar>
                                            <span class="reputation-value">{{ formatPercentage(getProjection('Reputation')?.Independent) }}</span>
                                        </div>
                                    </div>
                                </mat-card-content>
                            </mat-card>
                            
                            <!-- Statistics Overview Card -->
                            <mat-card *ngIf="getProjection('Statistics')">
                                <mat-card-header>
                                    <mat-card-title>Commander Statistics</mat-card-title>
                                </mat-card-header>
                                <mat-card-content>
                                    <mat-tab-group>
                                        <!-- Bank Account -->
                                        <mat-tab label="Banking">
                                            <div class="stats-container">
                                                <div class="stats-item" *ngIf="getProjection('Statistics')?.Bank_Account">
                                                    <div class="stats-row">
                                                        <span class="stats-label">Current Wealth:</span>
                                                        <span class="stats-value">{{ formatNumber(getProjection('Statistics')?.Bank_Account?.Current_Wealth) }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Spent on Ships:</span>
                                                        <span class="stats-value">{{ formatNumber(getProjection('Statistics')?.Bank_Account?.Spent_On_Ships) }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Spent on Outfitting:</span>
                                                        <span class="stats-value">{{ formatNumber(getProjection('Statistics')?.Bank_Account?.Spent_On_Outfitting) }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Insurance Claims:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Bank_Account?.Insurance_Claims }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Spent on Insurance:</span>
                                                        <span class="stats-value">{{ formatNumber(getProjection('Statistics')?.Bank_Account?.Spent_On_Insurance) }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Owned Ships:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Bank_Account?.Owned_Ship_Count }}</span>
                                                    </div>
                                                </div>
                                            </div>
                                        </mat-tab>
                                        
                                        <!-- Combat Stats -->
                                        <mat-tab label="Combat">
                                            <div class="stats-container">
                                                <div class="stats-item" *ngIf="getProjection('Statistics')?.Combat">
                                                    <div class="stats-row">
                                                        <span class="stats-label">Bounties Claimed:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Combat?.Bounties_Claimed }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Bounty Hunting Profit:</span>
                                                        <span class="stats-value">{{ formatNumber(getProjection('Statistics')?.Combat?.Bounty_Hunting_Profit) }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Combat Bonds:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Combat?.Combat_Bonds }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Combat Bond Profits:</span>
                                                        <span class="stats-value">{{ formatNumber(getProjection('Statistics')?.Combat?.Combat_Bond_Profits) }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Assassinations:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Combat?.Assassinations }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Assassination Profits:</span>
                                                        <span class="stats-value">{{ formatNumber(getProjection('Statistics')?.Combat?.Assassination_Profits) }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Highest Single Reward:</span>
                                                        <span class="stats-value">{{ formatNumber(getProjection('Statistics')?.Combat?.Highest_Single_Reward) }}</span>
                                                    </div>
                                                    
                                                    <h4>Conflict Zones</h4>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Total Battles:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Combat?.ConflictZone_Total }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Total Victories:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Combat?.ConflictZone_Total_Wins }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">High Intensity:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Combat?.ConflictZone_High }} ({{ getProjection('Statistics')?.Combat?.ConflictZone_High_Wins }} wins)</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Medium Intensity:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Combat?.ConflictZone_Medium }} ({{ getProjection('Statistics')?.Combat?.ConflictZone_Medium_Wins }} wins)</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Low Intensity:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Combat?.ConflictZone_Low }} ({{ getProjection('Statistics')?.Combat?.ConflictZone_Low_Wins }} wins)</span>
                                                    </div>
                                                    
                                                    <h4>On-Foot Combat</h4>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Combat Bonds:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Combat?.OnFoot_Combat_Bonds }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Combat Bond Profits:</span>
                                                        <span class="stats-value">{{ formatNumber(getProjection('Statistics')?.Combat?.OnFoot_Combat_Bonds_Profits) }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Settlements Defended:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Combat?.Settlement_Defended }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Settlements Conquered:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Combat?.Settlement_Conquered }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Skimmers Killed:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Combat?.OnFoot_Skimmers_Killed }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Scavengers Killed:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Combat?.OnFoot_Scavs_Killed }}</span>
                                                    </div>
                                                </div>
                                            </div>
                                        </mat-tab>
                                        
                                        <!-- Exploration Stats -->
                                        <mat-tab label="Exploration">
                                            <div class="stats-container">
                                                <div class="stats-item" *ngIf="getProjection('Statistics')?.Exploration">
                                                    <div class="stats-row">
                                                        <span class="stats-label">Systems Visited:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Exploration?.Systems_Visited }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Exploration Profits:</span>
                                                        <span class="stats-value">{{ formatNumber(getProjection('Statistics')?.Exploration?.Exploration_Profits) }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Highest Payout:</span>
                                                        <span class="stats-value">{{ formatNumber(getProjection('Statistics')?.Exploration?.Highest_Payout) }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Planets Scanned (FSS):</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Exploration?.Planets_Scanned_To_Level_2 }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Planets Scanned (DSS):</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Exploration?.Planets_Scanned_To_Level_3 }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Efficient Scans:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Exploration?.Efficient_Scans }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Total Jumps:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Exploration?.Total_Hyperspace_Jumps }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Total Distance:</span>
                                                        <span class="stats-value">{{ formatDistance(getProjection('Statistics')?.Exploration?.Total_Hyperspace_Distance) }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Greatest Distance From Start:</span>
                                                        <span class="stats-value">{{ formatDistance(getProjection('Statistics')?.Exploration?.Greatest_Distance_From_Start) }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Time Played:</span>
                                                        <span class="stats-value">{{ getHoursFromSeconds(getProjection('Statistics')?.Exploration?.Time_Played) }} hours</span>
                                                    </div>
                                                    
                                                    <h4>On-Foot Exploration</h4>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Distance Travelled:</span>
                                                        <span class="stats-value">{{ formatNumber(getProjection('Statistics')?.Exploration?.OnFoot_Distance_Travelled) }} m</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Planet Footfalls:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Exploration?.Planet_Footfalls }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">First Footfalls:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Exploration?.First_Footfalls }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Settlements Visited:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Exploration?.Settlements_Visited }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Shuttle Journeys:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Exploration?.Shuttle_Journeys }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Shuttle Distance:</span>
                                                        <span class="stats-value">{{ formatNumber(getProjection('Statistics')?.Exploration?.Shuttle_Distance_Travelled) }} ls</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Spent on Shuttles:</span>
                                                        <span class="stats-value">{{ formatNumber(getProjection('Statistics')?.Exploration?.Spent_On_Shuttles) }}</span>
                                                    </div>
                                                </div>
                                            </div>
                                        </mat-tab>
                                        
                                        <!-- Trading Stats -->
                                        <mat-tab label="Trading">
                                            <div class="stats-container">
                                                <div class="stats-item" *ngIf="getProjection('Statistics')?.Trading">
                                                    <div class="stats-row">
                                                        <span class="stats-label">Markets Traded With:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Trading?.Markets_Traded_With }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Market Profits:</span>
                                                        <span class="stats-value">{{ formatNumber(getProjection('Statistics')?.Trading?.Market_Profits) }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Resources Traded:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Trading?.Resources_Traded }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Average Profit:</span>
                                                        <span class="stats-value">{{ formatNumber(getProjection('Statistics')?.Trading?.Average_Profit) }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Highest Transaction:</span>
                                                        <span class="stats-value">{{ formatNumber(getProjection('Statistics')?.Trading?.Highest_Single_Transaction) }}</span>
                                                    </div>
                                                </div>
                                            </div>
                                        </mat-tab>
                                        
                                        <!-- Odyssey Stats -->
                                        <mat-tab label="Odyssey">
                                            <div class="stats-container">
                                                <div class="stats-item" *ngIf="getProjection('Statistics')?.Bank_Account">
                                                    <div class="stats-row">
                                                        <span class="stats-label">Suits Owned:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Bank_Account?.Suits_Owned }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Weapons Owned:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Bank_Account?.Weapons_Owned }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Spent on Suits:</span>
                                                        <span class="stats-value">{{ formatNumber(getProjection('Statistics')?.Bank_Account?.Spent_On_Suits) }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Spent on Weapons:</span>
                                                        <span class="stats-value">{{ formatNumber(getProjection('Statistics')?.Bank_Account?.Spent_On_Weapons) }}</span>
                                                    </div>
                                                </div>
                                                <div class="stats-item" *ngIf="getProjection('Statistics')?.Exobiology">
                                                    <h4>Exobiology</h4>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Organic Species:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Exobiology?.Organic_Species_Encountered }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Profits:</span>
                                                        <span class="stats-value">{{ formatNumber(getProjection('Statistics')?.Exobiology?.Organic_Data_Profits) }}</span>
                                                    </div>
                                                </div>
                                            </div>
                                        </mat-tab>
                                        
                                        <!-- Mining Stats -->
                                        <mat-tab label="Mining">
                                            <div class="stats-container">
                                                <div class="stats-item" *ngIf="getProjection('Statistics')?.Mining">
                                                    <div class="stats-row">
                                                        <span class="stats-label">Mining Profits:</span>
                                                        <span class="stats-value">{{ formatNumber(getProjection('Statistics')?.Mining?.Mining_Profits) }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Quantity Mined:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Mining?.Quantity_Mined }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Materials Collected:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Mining?.Materials_Collected }}</span>
                                                    </div>
                                                </div>
                                            </div>
                                        </mat-tab>

                                        <!-- Crime Stats -->
                                        <mat-tab label="Crime">
                                            <div class="stats-container">
                                                <div class="stats-item" *ngIf="getProjection('Statistics')?.Crime">
                                                    <div class="stats-row">
                                                        <span class="stats-label">Notoriety:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Crime?.Notoriety }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Fines:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Crime?.Fines }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Total Fines:</span>
                                                        <span class="stats-value">{{ formatNumber(getProjection('Statistics')?.Crime?.Total_Fines) }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Bounties Received:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Crime?.Bounties_Received }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Total Bounties:</span>
                                                        <span class="stats-value">{{ formatNumber(getProjection('Statistics')?.Crime?.Total_Bounties) }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Highest Bounty:</span>
                                                        <span class="stats-value">{{ formatNumber(getProjection('Statistics')?.Crime?.Highest_Bounty) }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Total Murders:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Crime?.Total_Murders }}</span>
                                                    </div>
                                                </div>
                                            </div>
                                        </mat-tab>

                                        <!-- Engineering Stats -->
                                        <mat-tab label="Engineering">
                                            <div class="stats-container">
                                                <div class="stats-item" *ngIf="getProjection('Statistics')?.Crafting">
                                                    <div class="stats-row">
                                                        <span class="stats-label">Engineers Used:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Crafting?.Count_Of_Used_Engineers }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Recipes Generated:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Crafting?.Recipes_Generated }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Grade 1 Recipes:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Crafting?.Recipes_Generated_Rank_1 }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Grade 2 Recipes:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Crafting?.Recipes_Generated_Rank_2 }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Grade 3 Recipes:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Crafting?.Recipes_Generated_Rank_3 }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Grade 4 Recipes:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Crafting?.Recipes_Generated_Rank_4 }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Grade 5 Recipes:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Crafting?.Recipes_Generated_Rank_5 }}</span>
                                                    </div>
                                                </div>
                                                <div class="stats-item" *ngIf="getProjection('Statistics')?.Material_Trader_Stats">
                                                    <h4>Material Trading</h4>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Trades Completed:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Material_Trader_Stats?.Trades_Completed }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Materials Traded:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Material_Trader_Stats?.Materials_Traded }}</span>
                                                    </div>
                                                </div>
                                            </div>
                                        </mat-tab>

                                        <!-- Smuggling Stats -->
                                        <mat-tab label="Smuggling">
                                            <div class="stats-container">
                                                <div class="stats-item" *ngIf="getProjection('Statistics')?.Smuggling">
                                                    <div class="stats-row">
                                                        <span class="stats-label">Black Markets Traded With:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Smuggling?.Black_Markets_Traded_With }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Black Markets Profits:</span>
                                                        <span class="stats-value">{{ formatNumber(getProjection('Statistics')?.Smuggling?.Black_Markets_Profits) }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Resources Smuggled:</span>
                                                        <span class="stats-value">{{ getProjection('Statistics')?.Smuggling?.Resources_Smuggled }}</span>
                                                    </div>
                                                    <div class="stats-row">
                                                        <span class="stats-label">Highest Transaction:</span>
                                                        <span class="stats-value">{{ formatNumber(getProjection('Statistics')?.Smuggling?.Highest_Single_Transaction) }}</span>
                                                    </div>
                                                </div>
                                            </div>
                                        </mat-tab>
                                        
                                        <!-- More Stats Tabs as needed -->
                                    </mat-tab-group>
                                </mat-card-content>
                            </mat-card>
                            
                            <!-- Squadron Information Card (if available) -->
                            <mat-card *ngIf="getProjection('SquadronStartup')">
                                <mat-card-header>
                                    <mat-card-title>Squadron</mat-card-title>
                                </mat-card-header>
                                <mat-card-content>
                                    <div class="squadron-container">
                                        <div class="stats-row">
                                            <span class="stats-label">Squadron:</span>
                                            <span class="stats-value">{{ getProjection('SquadronStartup')?.SquadronName }}</span>
                                        </div>
                                        <div class="stats-row" *ngIf="getProjection('SquadronStartup')?.CurrentRank">
                                            <span class="stats-label">Rank:</span>
                                            <span class="stats-value">{{ getProjection('SquadronStartup')?.CurrentRank }}</span>
                                        </div>
                                        <!-- Add more squadron info as needed -->
                                    </div>
                                </mat-card-content>
                            </mat-card>
                            
                            <!-- Powerplay Information Card (if available) -->
                            <mat-card *ngIf="getProjection('Powerplay')">
                                <mat-card-header>
                                    <mat-card-title>Powerplay</mat-card-title>
                                </mat-card-header>
                                <mat-card-content>
                                    <div class="powerplay-container">
                                        <div class="stats-row">
                                            <span class="stats-label">Power:</span>
                                            <span class="stats-value">{{ getProjection('Powerplay')?.Power }}</span>
                                        </div>
                                        <div class="stats-row" *ngIf="getProjection('Powerplay')?.Rank !== undefined">
                                            <span class="stats-label">Rank:</span>
                                            <span class="stats-value">{{ getProjection('Powerplay')?.Rank }}</span>
                                        </div>
                                        <div class="stats-row" *ngIf="getProjection('Powerplay')?.Merits !== undefined">
                                            <span class="stats-label">Merits:</span>
                                            <span class="stats-value">{{ getProjection('Powerplay')?.Merits }}</span>
                                        </div>
                                        <div class="stats-row" *ngIf="getProjection('Powerplay')?.Votes !== undefined">
                                            <span class="stats-label">Votes:</span>
                                            <span class="stats-value">{{ getProjection('Powerplay')?.Votes }}</span>
                                        </div>
                                        <!-- Add more powerplay info as needed -->
                                    </div>
                                </mat-card-content>
                            </mat-card>
                        </div>
                    </div>
                    
                    <!-- Station Tab Content -->
                    <div *ngIf="selectedTab === STATION_TAB" class="tab-pane">
                        <h2>Station Services</h2>
                        <mat-card>
                            <mat-card-header>
                                <mat-card-title>{{ getStationName() }}</mat-card-title>
                            </mat-card-header>
                            <mat-card-content>
                                <!-- Station content will go here -->
                                <div class="station-services">
                                    <button mat-button (click)="showStationService('market')">
                                        <mat-icon>shopping_cart</mat-icon>
                                        Market
                                    </button>
                                    <button mat-button (click)="showStationService('outfitting')">
                                        <mat-icon>build</mat-icon>
                                        Outfitting
                                    </button>
                                    <button mat-button (click)="showStationService('shipyard')">
                                        <mat-icon>directions_boat</mat-icon>
                                        Shipyard
                                    </button>
                                </div>
                                
                                <!-- Selected service display -->
                                <div *ngIf="selectedStationService" class="station-service-display">
                                    <!-- Service content based on selection -->
                                </div>
                            </mat-card-content>
                        </mat-card>
                    </div>
                    
                    <!-- Storage Tab Content -->
                    <div *ngIf="selectedTab === STORAGE_TAB" class="tab-pane">
                        <h2>Storage & Materials</h2>
                        
                        <!-- Materials Card -->
                        <mat-card>
                            <mat-card-header>
                                <mat-card-title>Materials</mat-card-title>
                            </mat-card-header>
                            <mat-card-content>
                                <div class="materials-container">
                                    <mat-tab-group>
                                        <!-- Raw Materials -->
                                        <mat-tab label="Raw">
                                            <div class="materials-table" *ngIf="getProjection('Materials')?.Raw">
                                                <table class="material-table">
                                                    <thead>
                                                        <tr>
                                                            <th>Section</th>
                                                            <th>Grade 1</th>
                                                            <th>Grade 2</th>
                                                            <th>Grade 3</th>
                                                            <th>Grade 4</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        <tr>
                                                            <td>Raw Material Category 1</td>
                                                            <td *ngFor="let grade of [1,2,3,4]">
                                                                <div class="material-cell" *ngFor="let material of getRawMaterialByGradeAndCategory(grade, 1)">
                                                                    <span class="material-name">{{ formatMaterialName(material.Name_Localised || material.Name) }}</span>
                                                                    <span class="material-count">{{ material.Count }}</span>
                                                                </div>
                                                            </td>
                                                        </tr>
                                                        <tr>
                                                            <td>Raw Material Category 2</td>
                                                            <td *ngFor="let grade of [1,2,3,4]">
                                                                <div class="material-cell" *ngFor="let material of getRawMaterialByGradeAndCategory(grade, 2)">
                                                                    <span class="material-name">{{ formatMaterialName(material.Name_Localised || material.Name) }}</span>
                                                                    <span class="material-count">{{ material.Count }}</span>
                                                                </div>
                                                            </td>
                                                        </tr>
                                                        <tr>
                                                            <td>Raw Material Category 3</td>
                                                            <td *ngFor="let grade of [1,2,3,4]">
                                                                <div class="material-cell" *ngFor="let material of getRawMaterialByGradeAndCategory(grade, 3)">
                                                                    <span class="material-name">{{ formatMaterialName(material.Name_Localised || material.Name) }}</span>
                                                                    <span class="material-count">{{ material.Count }}</span>
                                                                </div>
                                                            </td>
                                                        </tr>
                                                        <tr>
                                                            <td>Raw Material Category 4</td>
                                                            <td *ngFor="let grade of [1,2,3,4]">
                                                                <div class="material-cell" *ngFor="let material of getRawMaterialByGradeAndCategory(grade, 4)">
                                                                    <span class="material-name">{{ formatMaterialName(material.Name_Localised || material.Name) }}</span>
                                                                    <span class="material-count">{{ material.Count }}</span>
                                                                </div>
                                                            </td>
                                                        </tr>
                                                        <tr>
                                                            <td>Raw Material Category 5</td>
                                                            <td *ngFor="let grade of [1,2,3,4]">
                                                                <div class="material-cell" *ngFor="let material of getRawMaterialByGradeAndCategory(grade, 5)">
                                                                    <span class="material-name">{{ formatMaterialName(material.Name_Localised || material.Name) }}</span>
                                                                    <span class="material-count">{{ material.Count }}</span>
                                                                </div>
                                                            </td>
                                                        </tr>
                                                        <tr>
                                                            <td>Raw Material Category 6</td>
                                                            <td *ngFor="let grade of [1,2,3,4]">
                                                                <div class="material-cell" *ngFor="let material of getRawMaterialByGradeAndCategory(grade, 6)">
                                                                    <span class="material-name">{{ formatMaterialName(material.Name_Localised || material.Name) }}</span>
                                                                    <span class="material-count">{{ material.Count }}</span>
                                                                </div>
                                                            </td>
                                                        </tr>
                                                        <tr>
                                                            <td>Raw Material Category 7</td>
                                                            <td *ngFor="let grade of [1,2,3,4]">
                                                                <div class="material-cell" *ngFor="let material of getRawMaterialByGradeAndCategory(grade, 7)">
                                                                    <span class="material-name">{{ formatMaterialName(material.Name_Localised || material.Name) }}</span>
                                                                    <span class="material-count">{{ material.Count }}</span>
                                                                </div>
                                                            </td>
                                                        </tr>
                                                    </tbody>
                                                </table>
                                            </div>
                                            <div class="no-materials" *ngIf="!getProjection('Materials')?.Raw">
                                                No raw materials stored.
                                            </div>
                                        </mat-tab>
                                        
                                        <!-- Manufactured Materials -->
                                        <mat-tab label="Manufactured">
                                            <div class="materials-table" *ngIf="getProjection('Materials')?.Manufactured">
                                                <table class="material-table">
                                                    <thead>
                                                        <tr>
                                                            <th>Section</th>
                                                            <th>Grade 1</th>
                                                            <th>Grade 2</th>
                                                            <th>Grade 3</th>
                                                            <th>Grade 4</th>
                                                            <th>Grade 5</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        <tr>
                                                            <td>Chemical</td>
                                                            <td *ngFor="let grade of [1,2,3,4,5]">
                                                                <div class="material-cell" *ngFor="let material of getManufacturedMaterialByGradeAndSection('Chemical', grade)">
                                                                    <span class="material-name">{{ formatMaterialName(material.Name_Localised || material.Name) }}</span>
                                                                    <span class="material-count">{{ material.Count }}</span>
                                                                </div>
                                                            </td>
                                                        </tr>
                                                        <tr>
                                                            <td>Thermic</td>
                                                            <td *ngFor="let grade of [1,2,3,4,5]">
                                                                <div class="material-cell" *ngFor="let material of getManufacturedMaterialByGradeAndSection('Thermic', grade)">
                                                                    <span class="material-name">{{ formatMaterialName(material.Name_Localised || material.Name) }}</span>
                                                                    <span class="material-count">{{ material.Count }}</span>
                                                                </div>
                                                            </td>
                                                        </tr>
                                                        <tr>
                                                            <td>Heat</td>
                                                            <td *ngFor="let grade of [1,2,3,4,5]">
                                                                <div class="material-cell" *ngFor="let material of getManufacturedMaterialByGradeAndSection('Heat', grade)">
                                                                    <span class="material-name">{{ formatMaterialName(material.Name_Localised || material.Name) }}</span>
                                                                    <span class="material-count">{{ material.Count }}</span>
                                                                </div>
                                                            </td>
                                                        </tr>
                                                        <tr>
                                                            <td>Conductive</td>
                                                            <td *ngFor="let grade of [1,2,3,4,5]">
                                                                <div class="material-cell" *ngFor="let material of getManufacturedMaterialByGradeAndSection('Conductive', grade)">
                                                                    <span class="material-name">{{ formatMaterialName(material.Name_Localised || material.Name) }}</span>
                                                                    <span class="material-count">{{ material.Count }}</span>
                                                                </div>
                                                            </td>
                                                        </tr>
                                                        <tr>
                                                            <td>Mechanical Components</td>
                                                            <td *ngFor="let grade of [1,2,3,4,5]">
                                                                <div class="material-cell" *ngFor="let material of getManufacturedMaterialByGradeAndSection('Mechanical Components', grade)">
                                                                    <span class="material-name">{{ formatMaterialName(material.Name_Localised || material.Name) }}</span>
                                                                    <span class="material-count">{{ material.Count }}</span>
                                                                </div>
                                                            </td>
                                                        </tr>
                                                        <tr>
                                                            <td>Capacitors</td>
                                                            <td *ngFor="let grade of [1,2,3,4,5]">
                                                                <div class="material-cell" *ngFor="let material of getManufacturedMaterialByGradeAndSection('Capacitors', grade)">
                                                                    <span class="material-name">{{ formatMaterialName(material.Name_Localised || material.Name) }}</span>
                                                                    <span class="material-count">{{ material.Count }}</span>
                                                                </div>
                                                            </td>
                                                        </tr>
                                                        <tr>
                                                            <td>Shielding</td>
                                                            <td *ngFor="let grade of [1,2,3,4,5]">
                                                                <div class="material-cell" *ngFor="let material of getManufacturedMaterialByGradeAndSection('Shielding', grade)">
                                                                    <span class="material-name">{{ formatMaterialName(material.Name_Localised || material.Name) }}</span>
                                                                    <span class="material-count">{{ material.Count }}</span>
                                                                </div>
                                                            </td>
                                                        </tr>
                                                        <tr>
                                                            <td>Composite</td>
                                                            <td *ngFor="let grade of [1,2,3,4,5]">
                                                                <div class="material-cell" *ngFor="let material of getManufacturedMaterialByGradeAndSection('Composite', grade)">
                                                                    <span class="material-name">{{ formatMaterialName(material.Name_Localised || material.Name) }}</span>
                                                                    <span class="material-count">{{ material.Count }}</span>
                                                                </div>
                                                            </td>
                                                        </tr>
                                                        <tr>
                                                            <td>Crystals</td>
                                                            <td *ngFor="let grade of [1,2,3,4,5]">
                                                                <div class="material-cell" *ngFor="let material of getManufacturedMaterialByGradeAndSection('Crystals', grade)">
                                                                    <span class="material-name">{{ formatMaterialName(material.Name_Localised || material.Name) }}</span>
                                                                    <span class="material-count">{{ material.Count }}</span>
                                                                </div>
                                                            </td>
                                                        </tr>
                                                        <tr>
                                                            <td>Alloys</td>
                                                            <td *ngFor="let grade of [1,2,3,4,5]">
                                                                <div class="material-cell" *ngFor="let material of getManufacturedMaterialByGradeAndSection('Alloys', grade)">
                                                                    <span class="material-name">{{ formatMaterialName(material.Name_Localised || material.Name) }}</span>
                                                                    <span class="material-count">{{ material.Count }}</span>
                                                                </div>
                                                            </td>
                                                        </tr>
                                                    </tbody>
                                                </table>
                                            </div>
                                            <div class="no-materials" *ngIf="!getProjection('Materials')?.Manufactured">
                                                No manufactured materials stored.
                                            </div>
                                        </mat-tab>
                                        
                                        <!-- Encoded Materials -->
                                        <mat-tab label="Encoded">
                                            <div class="materials-table" *ngIf="getProjection('Materials')?.Encoded">
                                                <table class="material-table">
                                                    <thead>
                                                        <tr>
                                                            <th>Section</th>
                                                            <th>Grade 1</th>
                                                            <th>Grade 2</th>
                                                            <th>Grade 3</th>
                                                            <th>Grade 4</th>
                                                            <th>Grade 5</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        <tr>
                                                            <td>Emission Data</td>
                                                            <td *ngFor="let grade of [1,2,3,4,5]">
                                                                <div class="material-cell" *ngFor="let material of getEncodedMaterialByGradeAndSection('Emission Data', grade)">
                                                                    <span class="material-name">{{ formatMaterialName(material.Name_Localised || material.Name) }}</span>
                                                                    <span class="material-count">{{ material.Count }}</span>
                                                                </div>
                                                            </td>
                                                        </tr>
                                                        <tr>
                                                            <td>Wake Scans</td>
                                                            <td *ngFor="let grade of [1,2,3,4,5]">
                                                                <div class="material-cell" *ngFor="let material of getEncodedMaterialByGradeAndSection('Wake Scans', grade)">
                                                                    <span class="material-name">{{ formatMaterialName(material.Name_Localised || material.Name) }}</span>
                                                                    <span class="material-count">{{ material.Count }}</span>
                                                                </div>
                                                            </td>
                                                        </tr>
                                                        <tr>
                                                            <td>Shield Data</td>
                                                            <td *ngFor="let grade of [1,2,3,4,5]">
                                                                <div class="material-cell" *ngFor="let material of getEncodedMaterialByGradeAndSection('Shield Data', grade)">
                                                                    <span class="material-name">{{ formatMaterialName(material.Name_Localised || material.Name) }}</span>
                                                                    <span class="material-count">{{ material.Count }}</span>
                                                                </div>
                                                            </td>
                                                        </tr>
                                                        <tr>
                                                            <td>Encryption Files</td>
                                                            <td *ngFor="let grade of [1,2,3,4,5]">
                                                                <div class="material-cell" *ngFor="let material of getEncodedMaterialByGradeAndSection('Encryption Files', grade)">
                                                                    <span class="material-name">{{ formatMaterialName(material.Name_Localised || material.Name) }}</span>
                                                                    <span class="material-count">{{ material.Count }}</span>
                                                                </div>
                                                            </td>
                                                        </tr>
                                                        <tr>
                                                            <td>Data Archives</td>
                                                            <td *ngFor="let grade of [1,2,3,4,5]">
                                                                <div class="material-cell" *ngFor="let material of getEncodedMaterialByGradeAndSection('Data Archives', grade)">
                                                                    <span class="material-name">{{ formatMaterialName(material.Name_Localised || material.Name) }}</span>
                                                                    <span class="material-count">{{ material.Count }}</span>
                                                                </div>
                                                            </td>
                                                        </tr>
                                                        <tr>
                                                            <td>Encoded Firmware</td>
                                                            <td *ngFor="let grade of [1,2,3,4,5]">
                                                                <div class="material-cell" *ngFor="let material of getEncodedMaterialByGradeAndSection('Encoded Firmware', grade)">
                                                                    <span class="material-name">{{ formatMaterialName(material.Name_Localised || material.Name) }}</span>
                                                                    <span class="material-count">{{ material.Count }}</span>
                                                                </div>
                                                            </td>
                                                        </tr>
                                                    </tbody>
                                                </table>
                                            </div>
                                            <div class="no-materials" *ngIf="!getProjection('Materials')?.Encoded">
                                                No encoded materials stored.
                                            </div>
                                        </mat-tab>
                                    </mat-tab-group>
                                </div>
                            </mat-card-content>
                        </mat-card>
                        
                        <!-- Stored Ships Card -->
                        <mat-card>
                            <mat-card-header>
                                <mat-card-title>Stored Ships</mat-card-title>
                                <mat-card-subtitle *ngIf="getProjection('StoredShips')?.StationName">
                                    {{ getProjection('StoredShips')?.StationName }}, {{ getProjection('StoredShips')?.StarSystem }}
                                </mat-card-subtitle>
                            </mat-card-header>
                            <mat-card-content>
                                <mat-tab-group>
                                    <!-- Ships at Current Location -->
                                    <mat-tab label="Ships Here">
                                        <div class="ships-list" *ngIf="getProjection('StoredShips')?.ShipsHere?.length">
                                            <div class="ship-item" *ngFor="let ship of getProjection('StoredShips')?.ShipsHere">
                                                <div class="ship-icon">
                                                    <mat-icon>directions_boat</mat-icon>
                                                </div>
                                                <div class="ship-details">
                                                    <div class="ship-name">{{ ship.Name || ship.ShipType_Localised || ship.ShipType }}</div>
                                                    <div class="ship-type" *ngIf="ship.Name">{{ ship.ShipType_Localised || ship.ShipType }}</div>
                                                    <div class="ship-value">{{ formatNumber(ship.Value) }} Cr</div>
                                                    <div class="ship-hot" *ngIf="ship.Hot">HOT</div>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="no-ships" *ngIf="!getProjection('StoredShips')?.ShipsHere?.length">
                                            No ships stored at this location.
                                        </div>
                                    </mat-tab>
                                    
                                    <!-- Remote Ships -->
                                    <mat-tab label="Remote Ships">
                                        <div class="ships-list" *ngIf="getProjection('StoredShips')?.ShipsRemote?.length">
                                            <div class="ship-item" *ngFor="let ship of getProjection('StoredShips')?.ShipsRemote">
                                                <div class="ship-icon">
                                                    <mat-icon>directions_boat</mat-icon>
                                                </div>
                                                <div class="ship-details">
                                                    <div class="ship-name">{{ ship.Name || ship.ShipType_Localised || ship.ShipType }}</div>
                                                    <div class="ship-type" *ngIf="ship.Name">{{ ship.ShipType_Localised || ship.ShipType }}</div>
                                                    <div class="ship-location">{{ ship.StarSystem }}</div>
                                                    <div class="ship-value">{{ formatNumber(ship.Value) }} Cr</div>
                                                    <div class="ship-transfer">
                                                        <div>Transfer: {{ formatNumber(ship.TransferPrice) }} Cr</div>
                                                        <div>Time: {{ formatTransferTime(ship.TransferTime) }}</div>
                                                    </div>
                                                    <div class="ship-hot" *ngIf="ship.Hot">HOT</div>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="no-ships" *ngIf="!getProjection('StoredShips')?.ShipsRemote?.length">
                                            No ships stored remotely.
                                        </div>
                                    </mat-tab>
                                </mat-tab-group>
                            </mat-card-content>
                        </mat-card>
                        
                        <!-- Ship Locker Card -->
                        <mat-card>
                            <mat-card-header>
                                <mat-card-title>Ship Locker</mat-card-title>
                            </mat-card-header>
                            <mat-card-content>
                                <div class="locker-container">
                                    <mat-tab-group>
                                        <!-- General Items -->
                                        <mat-tab label="Items">
                                            <div class="items-grid" *ngIf="getProjection('ShipLocker')?.Items?.length">
                                                <div class="locker-item" *ngFor="let item of getProjection('ShipLocker')?.Items">
                                                    <div class="item-count">{{ item.Count }}</div>
                                                    <div class="item-name">
                                                        {{ formatItemName(item.Name_Localised || item.Name) }}
                                                        <span class="mission-tag" *ngIf="item.MissionID">[Mission]</span>
                                                    </div>
                                                </div>
                                            </div>
                                            <div class="no-items" *ngIf="!getProjection('ShipLocker')?.Items?.length">
                                                No items stored.
                                            </div>
                                        </mat-tab>
                                        
                                        <!-- Components -->
                                        <mat-tab label="Components">
                                            <div class="items-grid" *ngIf="getProjection('ShipLocker')?.Components?.length">
                                                <div class="locker-item" *ngFor="let item of getProjection('ShipLocker')?.Components">
                                                    <div class="item-count">{{ item.Count }}</div>
                                                    <div class="item-name">{{ formatItemName(item.Name_Localised || item.Name) }}</div>
                                                </div>
                                            </div>
                                            <div class="no-items" *ngIf="!getProjection('ShipLocker')?.Components?.length">
                                                No components stored.
                                            </div>
                                        </mat-tab>
                                        
                                        <!-- Consumables -->
                                        <mat-tab label="Consumables">
                                            <div class="items-grid" *ngIf="getProjection('ShipLocker')?.Consumables?.length">
                                                <div class="locker-item" *ngFor="let item of getProjection('ShipLocker')?.Consumables">
                                                    <div class="item-count">{{ item.Count }}</div>
                                                    <div class="item-name">{{ formatItemName(item.Name_Localised || item.Name) }}</div>
                                                </div>
                                            </div>
                                            <div class="no-items" *ngIf="!getProjection('ShipLocker')?.Consumables?.length">
                                                No consumables stored.
                                            </div>
                                        </mat-tab>
                                        
                                        <!-- Data -->
                                        <mat-tab label="Data">
                                            <div class="items-grid" *ngIf="getProjection('ShipLocker')?.Data?.length">
                                                <div class="locker-item" *ngFor="let item of getProjection('ShipLocker')?.Data">
                                                    <div class="item-count">{{ item.Count }}</div>
                                                    <div class="item-name">
                                                        {{ formatItemName(item.Name_Localised || item.Name) }}
                                                        <span class="owner-tag" *ngIf="item.OwnerID && item.OwnerID !== 0">[External]</span>
                                                    </div>
                                                </div>
                                            </div>
                                            <div class="no-items" *ngIf="!getProjection('ShipLocker')?.Data?.length">
                                                No data stored.
                                            </div>
                                        </mat-tab>
                                    </mat-tab-group>
                                </div>
                            </mat-card-content>
                        </mat-card>
                    </div>
                </div>
            </div>
            
            <div class="no-data" *ngIf="!isProjectionsLoaded">
                Waiting for status data...
            </div>
        </div>
    `,
    styles: [`
        .status-container {
            height: 100%;
            overflow-y: auto;
            padding: 0;
            display: flex;
            flex-direction: column;
        }
        
        .tab-layout {
            display: flex;
            height: 100%;
        }
        
        .tab-sidebar {
            width: 80px;
            background-color: #1e1e1e;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding-top: 10px;
        }
        
        .tab-button {
            width: 70px;
            height: 70px;
            background: none;
            border: none;
            color: rgba(255, 255, 255, 0.6);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            margin-bottom: 5px;
            border-radius: 5px;
        }
        
        .tab-button mat-icon {
            font-size: 24px;
            height: 24px;
            width: 24px;
        }
        
        .tab-button span {
            font-size: 12px;
            margin-top: 5px;
        }
        
        .tab-button.active {
            background-color: rgba(255, 255, 255, 0.1);
            color: white;
        }
        
        .tab-content {
            flex-grow: 1;
            padding: 15px;
            overflow-y: auto;
            position: relative;
        }
        
        .tab-pane {
            height: 100%;
        }
        
        .status-indicators-fixed {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 100;
        }
        
        .active-status-icons {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        
        .status-icon, .friends-counter, .colonisation-indicator {
            width: 36px;
            height: 36px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            margin-bottom: 8px;
        }
        
        .status-icon {
            color: #4caf50;
            background-color: rgba(76, 175, 80, 0.2);
        }
        
        .friends-counter, .colonisation-indicator {
            position: relative;
            background-color: rgba(33, 150, 243, 0.2);
            color: #2196F3;
            cursor: pointer;
        }
        
        .badge {
            position: absolute;
            top: -5px;
            right: -5px;
            background-color: #f44336;
            color: white;
            border-radius: 10px;
            padding: 2px 5px;
            font-size: 10px;
            min-width: 15px;
            text-align: center;
        }
        
        .progress-text {
            position: absolute;
            bottom: -12px;
            font-size: 9px;
            white-space: nowrap;
        }
        
        .location-nav-container {
            margin: 15px 0;
            display: flex;
            justify-content: space-between;
            background: rgba(0, 0, 0, 0.2);
            border-radius: 5px;
            padding: 15px;
        }
        
        .location-info {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .location-details {
            display: flex;
            flex-direction: column;
        }
        
        .system-name {
            font-size: 18px;
            font-weight: 500;
            color: #d0a85c;
        }
        
        .location-detail {
            display: flex;
            align-items: center;
            gap: 5px;
            font-size: 14px;
            color: rgba(255, 255, 255, 0.8);
        }
        
        .small-icon {
            font-size: 16px;
            width: 16px;
            height: 16px;
            line-height: 16px;
        }
        
        .nav-info {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 5px 10px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 4px;
            cursor: pointer;
            transition: background-color 0.2s;
        }
        
        .nav-info:hover {
            background: rgba(255, 255, 255, 0.1);
        }
        
        .expander {
            font-size: 18px;
            opacity: 0.7;
        }
        
        .context-content {
            display: flex;
            flex-direction: column;
            gap: 15px;
            margin-bottom: 15px;
        }
        
        .ship-header, .suit-header {
            margin-bottom: 10px;
        }
        
        .ship-header h3, .suit-header h3 {
            margin-bottom: 0;
        }
        
        .ship-type, .suit-loadout {
            color: rgba(255, 255, 255, 0.7);
            margin-top: 0;
        }
        
        .ship-stats {
            margin-bottom: 10px;
        }
        
        .stat-group {
            margin-bottom: 10px;
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
        
        .weapons-summary {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }
        
        .weapon-item {
            display: flex;
            align-items: center;
            gap: 5px;
            padding: 5px 10px;
            background-color: rgba(255, 255, 255, 0.05);
            border-radius: 20px;
        }
        
        .backpack-summary {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
        }
        
        .backpack-category {
            display: flex;
            align-items: center;
            gap: 5px;
        }
        
        .category-name {
            font-weight: 500;
        }
        
        .category-count {
            background-color: rgba(255, 255, 255, 0.1);
            padding: 2px 8px;
            border-radius: 10px;
        }
        
        .scan-progress {
            margin-top: 10px;
        }
        
        .scan-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        
        .scan-status-indicator {
            font-size: 12px;
            padding: 3px 8px;
            border-radius: 12px;
        }
        
        .scan-too-close {
            background-color: rgba(244, 67, 54, 0.2);
            color: #f44336;
        }
        
        .scan-good-distance {
            background-color: rgba(76, 175, 80, 0.2);
            color: #4caf50;
        }
        
        .scan-summary {
            display: flex;
            gap: 10px;
        }
        
        .detail-label {
            font-weight: 500;
            color: rgba(255, 255, 255, 0.7);
        }
        
        .expandable-panel {
            background-color: rgba(0, 0, 0, 0.2);
            border-radius: 5px;
            padding: 15px;
            margin-top: 15px;
        }
        
        .colony-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        
        .colony-status {
            font-size: 12px;
            padding: 3px 8px;
            border-radius: 12px;
        }
        
        .commander-info {
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        
        .commander-basic {
            margin-bottom: 10px;
        }
        
        .ranks-container {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            gap: 15px;
        }
        
        .rank-item {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }
        
        .rank-name {
            font-weight: 500;
        }
        
        .rank-value {
            font-size: 18px;
            margin-bottom: 5px;
        }
        
        .station-services {
            display: flex;
            gap: 10px;
            margin-bottom: 15px;
        }
        
        .materials-container {
            width: 100%;
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
        
        .empty-message {
            color: rgba(255, 255, 255, 0.6);
            text-align: center;
            padding: 20px;
        }
        
        .no-data {
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100%;
            color: rgba(255, 255, 255, 0.6);
        }
        
        /* Character Sheet Styles (D&D 5E Inspired) */
        .character-sheet {
            background-color: rgba(245, 240, 230, 0.05);
            border-radius: 8px;
            padding: 20px;
            position: relative;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
        }
        
        .character-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid rgba(255, 255, 255, 0.1);
            padding-bottom: 15px;
            margin-bottom: 20px;
        }
        
        .character-name h2 {
            margin: 0;
            font-size: 24px;
            font-weight: 600;
            color: #d0a85c;
        }
        
        .character-subtitle {
            font-size: 16px;
            color: rgba(255, 255, 255, 0.7);
            margin-top: 5px;
        }
        
        .character-class {
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        
        .class-circle {
            width: 50px;
            height: 50px;
            border: 2px solid #d0a85c;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            background-color: rgba(208, 168, 92, 0.1);
        }
        
        .circle-value {
            font-size: 20px;
            font-weight: bold;
            color: #d0a85c;
        }
        
        .class-label {
            margin-top: 5px;
            font-size: 12px;
            color: rgba(255, 255, 255, 0.6);
            letter-spacing: 1px;
        }
        
        .character-stats {
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        
        .stat-column {
            flex: 1;
            min-width: 120px;
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        
        .stat-box {
            background-color: rgba(0, 0, 0, 0.2);
            border-radius: 8px;
            padding: 10px;
            text-align: center;
            border: 1px solid rgba(208, 168, 92, 0.3);
            position: relative;
        }
        
        .cargo-box, .nav-box {
            cursor: pointer;
        }
        
        .cargo-box:hover, .nav-box:hover {
            background-color: rgba(0, 0, 0, 0.3);
        }
        
        .stat-value {
            font-size: 22px;
            font-weight: bold;
            color: white;
        }
        
        .stat-label {
            font-size: 12px;
            color: #d0a85c;
            margin-top: 5px;
            letter-spacing: 1px;
        }
        
        .stat-bar {
            margin-top: 8px;
        }
        
        .section-header {
            font-size: 16px;
            font-weight: 600;
            color: #d0a85c;
            margin: 25px 0 15px;
            padding-bottom: 5px;
            border-bottom: 1px solid rgba(208, 168, 92, 0.3);
            letter-spacing: 1px;
        }
        
        /* Ship Modules styles */
        .modules-block {
            background-color: rgba(0, 0, 0, 0.2);
            border-radius: 8px;
            padding: 10px;
            margin-bottom: 20px;
        }
        
        .module-list {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }
        
        .module-item {
            display: flex;
            padding: 8px;
            border-radius: 4px;
            background-color: rgba(255, 255, 255, 0.05);
            align-items: center;
        }
        
        .module-slot {
            flex: 0 0 80px;
            font-weight: 500;
            color: rgba(255, 255, 255, 0.7);
            font-size: 13px;
        }
        
        .module-details {
            flex: 1;
            display: flex;
            justify-content: space-between;
        }
        
        .module-name {
            font-size: 14px;
        }
        
        .module-class {
            font-size: 14px;
            color: #d0a85c;
            font-weight: 500;
        }
        
        .module-engineering {
            margin-left: 10px;
            color: #5cadff;
        }
        
        .engineering-icon {
            font-size: 18px;
            height: 18px;
            width: 18px;
        }
        
        .show-more, .show-less {
            text-align: center;
            padding: 8px;
            background-color: rgba(255, 255, 255, 0.05);
            border-radius: 4px;
            margin-top: 5px;
            cursor: pointer;
            color: #d0a85c;
        }
        
        .show-more:hover, .show-less:hover {
            background-color: rgba(255, 255, 255, 0.1);
        }
        
        /* Navigation styles */
        .nav-box {
            background-color: rgba(0, 0, 0, 0.2);
            border-radius: 8px;
            padding: 15px;
            margin: 20px 0;
            border: 1px solid rgba(208, 168, 92, 0.3);
        }
        
        .nav-summary {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .nav-summary .expander {
            margin-left: auto;
        }
        
        .nav-details {
            margin-top: 10px;
            background: rgba(0, 0, 0, 0.2);
            border-radius: 5px;
            padding: 10px;
        }
        
        .nav-route-list {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        
        .nav-route-item {
            display: grid;
            grid-template-columns: 30px 1fr auto auto;
            align-items: center;
            padding: 8px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 4px;
            gap: 10px;
        }
        
        .nav-index {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 50%;
            width: 24px;
            height: 24px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 500;
        }
        
        .nav-system {
            font-weight: 500;
        }
        
        .nav-star-info {
            display: flex;
            align-items: center;
            gap: 5px;
        }
        
        .star-icon {
            width: 20px;
            height: 20px;
            font-size: 20px;
        }
        
        .small-text {
            font-size: 12px;
            color: rgba(255, 255, 255, 0.6);
        }
        
        .jumps-remaining {
            text-align: right;
        }
        
        /* Cargo details */
        .cargo-details {
            background-color: rgba(0, 0, 0, 0.2);
            border-radius: 8px;
            padding: 15px;
            margin: 20px 0;
        }
        
        .cargo-list {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }
        
        .cargo-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 15px;
            background-color: rgba(255, 255, 255, 0.05);
            border-radius: 4px;
        }
        
        .cargo-item-count {
            font-weight: 500;
            color: #d0a85c;
        }
        
        /* Weapons style for suit */
        .weapons-block {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            margin-bottom: 20px;
        }
        
        .weapon-card {
            flex: 1;
            min-width: 250px;
            background-color: rgba(0, 0, 0, 0.2);
            border-radius: 8px;
            padding: 15px;
            border: 1px solid rgba(208, 168, 92, 0.3);
        }
        
        .weapon-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        
        .weapon-name {
            font-weight: 600;
            font-size: 16px;
        }
        
        .class-bubble {
            width: 30px;
            height: 30px;
            background-color: rgba(208, 168, 92, 0.2);
            color: #d0a85c;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
        }
        
        .weapon-type {
            color: rgba(255, 255, 255, 0.7);
            font-size: 14px;
            margin-bottom: 15px;
        }
        
        .weapon-mods {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }
        
        .weapon-mod-tag {
            background-color: rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 4px 10px;
            font-size: 12px;
            color: rgba(255, 255, 255, 0.9);
        }
        
        /* Suit mods */
        .stat-block {
            background-color: rgba(0, 0, 0, 0.2);
            border-radius: 8px;
            padding: 15px;
            width: 100%;
            margin-bottom: 20px;
            border: 1px solid rgba(208, 168, 92, 0.3);
        }
        
        .stat-header {
            font-size: 14px;
            color: #d0a85c;
            margin: 0 0 15px;
            letter-spacing: 1px;
            text-align: center;
        }
        
        .mod-list {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }
        
        .mod-item {
            display: flex;
            align-items: center;
            gap: 8px;
            background-color: rgba(255, 255, 255, 0.05);
            border-radius: 4px;
            padding: 8px 12px;
        }
        
        .mod-icon {
            color: #d0a85c;
        }
        
        .mod-name {
            font-size: 14px;
        }
        
        /* Backpack */
        .backpack-block {
            background-color: rgba(0, 0, 0, 0.2);
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
            cursor: pointer;
            border: 1px solid rgba(208, 168, 92, 0.3);
        }
        
        .backpack-block:hover {
            background-color: rgba(0, 0, 0, 0.3);
        }
        
        .backpack-summary {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            align-items: center;
        }
        
        .backpack-summary mat-icon {
            margin-left: auto;
        }
        
        .backpack-details {
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .backpack-category-section {
            margin-bottom: 15px;
        }
        
        .backpack-category-section h4 {
            color: #d0a85c;
            margin: 0 0 10px;
            font-size: 14px;
        }
        
        .backpack-items {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }
        
        .backpack-item {
            display: flex;
            justify-content: space-between;
            padding: 8px 12px;
            background-color: rgba(255, 255, 255, 0.05);
            border-radius: 4px;
        }
        
        .item-count {
            color: #d0a85c;
            font-weight: 500;
        }
        
        .empty-state {
            color: rgba(255, 255, 255, 0.5);
            text-align: center;
            padding: 10px;
            font-style: italic;
        }
        
        .tiny-icon {
            font-size: 16px;
            height: 16px;
            width: 16px;
            vertical-align: middle;
        }
        
        /* Character Sheet Layout Styles */
        .character-sheet-body {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .sheet-column {
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        
        .attributes-column {
            border-right: 1px solid rgba(208, 168, 92, 0.2);
            padding-right: 15px;
        }
        
        .weapons-column {
            border-left: 1px solid rgba(208, 168, 92, 0.2);
            padding-left: 15px;
        }
        
        .character-sheet-footer {
            border-top: 1px solid rgba(208, 168, 92, 0.3);
            padding-top: 20px;
            margin-top: 10px;
        }
        
        /* Ship Stats Styles */
        .ship-core-stats, .ship-defense-stats {
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        
        .ship-stat-item, .defense-stat-item {
            background-color: rgba(0, 0, 0, 0.2);
            border-radius: 8px;
            padding: 10px;
            border: 1px solid rgba(208, 168, 92, 0.3);
        }
        
        .stat-value-large {
            font-size: 28px;
            font-weight: bold;
            text-align: center;
            margin: 5px 0;
        }
        
        .stat-suffix {
            text-align: center;
            font-size: 12px;
            color: rgba(255, 255, 255, 0.6);
            letter-spacing: 1px;
        }
        
        .cr:after {
            content: " CR";
            font-size: 14px;
            opacity: 0.7;
        }
        
        .stat-value-with-bar {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }
        
        /* Navigation Items */
        .nav-route-summary {
            background-color: rgba(0, 0, 0, 0.2);
            border-radius: 8px;
            padding: 10px;
            border: 1px solid rgba(208, 168, 92, 0.3);
            cursor: pointer;
        }
        
        .nav-route-summary:hover {
            background-color: rgba(0, 0, 0, 0.3);
        }
        
        /* Combat Stats for Suit */
        .combat-stats {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        
        .combat-stat-item {
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        
        .combat-stat-circle {
            width: 60px;
            height: 60px;
            border-radius: 50%;
            border: 2px solid #d0a85c;
            display: flex;
            align-items: center;
            justify-content: center;
            background-color: rgba(208, 168, 92, 0.1);
            margin-bottom: 5px;
        }
        
        .combat-stat-value {
            font-size: 16px;
            font-weight: bold;
            color: white;
        }
        
        .combat-stat-label {
            font-size: 12px;
            color: #d0a85c;
            letter-spacing: 1px;
        }
        
        /* Modules Lists */
        .modules-section {
            margin-bottom: 25px;
        }
        
        .hardpoints-list, .utility-list {
            display: flex;
            flex-direction: column;
            gap: 4px;
            margin-bottom: 12px;
            width: 100%;
        }
        
        .weapons-column {
            display: flex;
            flex-direction: column;
            width: 100%;
        }
        
        .hardpoint-item, .utility-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 4px;
            padding: 8px 12px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 4px;
            font-size: 14px;
            width: 100%;
        }
        
        .hardpoint-details, .utility-details {
            flex: 1;
        }
        
        .weapon-display {
            display: flex;
            flex-direction: column;
            padding: 2px 0;
        }
        
        .hardpoint-name {
            font-weight: 500;
            color: #d0a85c;
        }
        
        .utility-name {
            font-weight: 500;
        }
        
        .engineering-icon {
            color: #50a5e6;
        }
        
        .show-more, .show-less {
            text-align: center;
            padding: 8px;
            background-color: rgba(255, 255, 255, 0.05);
            border-radius: 4px;
            margin-top: 5px;
            cursor: pointer;
            color: #d0a85c;
        }
        
        .show-more:hover, .show-less:hover {
            background-color: rgba(255, 255, 255, 0.1);
        }
        
        /* Star Class Colors */
        .star-o { color: #9db4ff; }      /* Blue */
        .star-b { color: #aabfff; }      /* Blue-white */
        .star-a { color: #cad7ff; }      /* White */
        .star-f { color: #f8f7ff; }      /* Yellow-white */
        .star-g { color: #fff4ea; }      /* Yellow (Sun-like) */
        .star-k { color: #ffd2a1; }      /* Orange */
        .star-m { color: #ffbd6f; }      /* Red */
        .star-brown { color: #a66c3c; }  /* Brown dwarf */
        .star-w { color: #70b7ff; }      /* Wolf-Rayet */
        .star-carbon { color: #ff7c7c; } /* Carbon star */
        .star-black-hole { color: #440a5c; } /* Black hole */
        .star-exotic { color: #7f18ff; }   /* Exotic */
        .star-default { color: #ffffff; }  /* Default white */
        
        /* New CSS classes */
        .star-scoopable {
            display: flex;
            align-items: center;
            gap: 5px;
        }
        
        .fuel-icon {
            font-size: 16px;
            width: 16px;
            height: 16px;
        }
        
        .scoopable {
            color: #4caf50;
        }
        
        .not-scoopable {
            color: #f44336;
        }
    `]
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