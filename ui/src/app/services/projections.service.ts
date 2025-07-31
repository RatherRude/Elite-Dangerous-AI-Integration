import { Injectable } from "@angular/core";
import { BehaviorSubject, Observable, filter, map } from "rxjs";
import { BaseMessage, TauriService } from "./tauri.service";

export interface StatesMessage extends BaseMessage {
    type: "states";
    states: Record<string, any>;
}

@Injectable({
    providedIn: "root",
})
export class ProjectionsService {
    private projectionsSubject = new BehaviorSubject<Record<string, any>>({});
    public projections$ = this.projectionsSubject.asObservable();

    // Individual projection subjects
    private currentStatusSubject = new BehaviorSubject<any>(null);
    private locationSubject = new BehaviorSubject<any>(null);
    private missionsSubject = new BehaviorSubject<any>(null);
    private engineerProgressSubject = new BehaviorSubject<any>(null);
    private communityGoalSubject = new BehaviorSubject<any>(null);
    private shipInfoSubject = new BehaviorSubject<any>(null);
    private targetSubject = new BehaviorSubject<any>(null);
    private navInfoSubject = new BehaviorSubject<any>(null);
    private exobiologyScanSubject = new BehaviorSubject<any>(null);
    private cargoSubject = new BehaviorSubject<any>(null);
    private backpackSubject = new BehaviorSubject<any>(null);
    private suitLoadoutSubject = new BehaviorSubject<any>(null);
    private friendsSubject = new BehaviorSubject<any>(null);
    private colonisationConstructionSubject = new BehaviorSubject<any>(null);
    private dockingEventsSubject = new BehaviorSubject<any>(null);
    private inCombatSubject = new BehaviorSubject<any>(null);
    private wingSubject = new BehaviorSubject<any>(null);
    private idleSubject = new BehaviorSubject<any>(null);
    private commanderSubject = new BehaviorSubject<any>(null);
    private materialsSubject = new BehaviorSubject<any>(null);
    private moduleInfoSubject = new BehaviorSubject<any>(null);
    private rankSubject = new BehaviorSubject<any>(null);
    private progressSubject = new BehaviorSubject<any>(null);
    private reputationSubject = new BehaviorSubject<any>(null);
    private squadronStartupSubject = new BehaviorSubject<any>(null);
    private statisticsSubject = new BehaviorSubject<any>(null);
    private powerplaySubject = new BehaviorSubject<any>(null);
    private shipLockerSubject = new BehaviorSubject<any>(null);
    private loadoutSubject = new BehaviorSubject<any>(null);
    private shipyardSubject = new BehaviorSubject<any>(null);
    private storedShipsSubject = new BehaviorSubject<any>(null);
    private marketSubject = new BehaviorSubject<any>(null);
    private outfittingSubject = new BehaviorSubject<any>(null);

    // Individual projection observables
    public currentStatus$ = this.currentStatusSubject.asObservable();
    public location$ = this.locationSubject.asObservable();
    public missions$ = this.missionsSubject.asObservable();
    public engineerProgress$ = this.engineerProgressSubject.asObservable();
    public communityGoal$ = this.communityGoalSubject.asObservable();
    public shipInfo$ = this.shipInfoSubject.asObservable();
    public target$ = this.targetSubject.asObservable();
    public navInfo$ = this.navInfoSubject.asObservable();
    public exobiologyScan$ = this.exobiologyScanSubject.asObservable();
    public cargo$ = this.cargoSubject.asObservable();
    public backpack$ = this.backpackSubject.asObservable();
    public suitLoadout$ = this.suitLoadoutSubject.asObservable();
    public friends$ = this.friendsSubject.asObservable();
    public colonisationConstruction$ = this.colonisationConstructionSubject.asObservable();
    public dockingEvents$ = this.dockingEventsSubject.asObservable();
    public inCombat$ = this.inCombatSubject.asObservable();
    public wing$ = this.wingSubject.asObservable();
    public idle$ = this.idleSubject.asObservable();
    public commander$ = this.commanderSubject.asObservable();
    public materials$ = this.materialsSubject.asObservable();
    public moduleInfo$ = this.moduleInfoSubject.asObservable();
    public rank$ = this.rankSubject.asObservable();
    public progress$ = this.progressSubject.asObservable();
    public reputation$ = this.reputationSubject.asObservable();
    public squadronStartup$ = this.squadronStartupSubject.asObservable();
    public statistics$ = this.statisticsSubject.asObservable();
    public powerplay$ = this.powerplaySubject.asObservable();
    public shipLocker$ = this.shipLockerSubject.asObservable();
    public loadout$ = this.loadoutSubject.asObservable();
    public shipyard$ = this.shipyardSubject.asObservable();
    public storedShips$ = this.storedShipsSubject.asObservable();
    public market$ = this.marketSubject.asObservable();
    public outfitting$ = this.outfittingSubject.asObservable();

    // Map of projection names to their subjects for easier management
    private projectionSubjects: Record<string, BehaviorSubject<any>> = {
        'CurrentStatus': this.currentStatusSubject,
        'Location': this.locationSubject,
        'Missions': this.missionsSubject,
        'EngineerProgress': this.engineerProgressSubject,
        'CommunityGoal': this.communityGoalSubject,
        'ShipInfo': this.shipInfoSubject,
        'Target': this.targetSubject,
        'NavInfo': this.navInfoSubject,
        'ExobiologyScan': this.exobiologyScanSubject,
        'Cargo': this.cargoSubject,
        'Backpack': this.backpackSubject,
        'SuitLoadout': this.suitLoadoutSubject,
        'Friends': this.friendsSubject,
        'ColonisationConstruction': this.colonisationConstructionSubject,
        'DockingEvents': this.dockingEventsSubject,
        'InCombat': this.inCombatSubject,
        'Wing': this.wingSubject,
        'Idle': this.idleSubject,
        'Commander': this.commanderSubject,
        'Materials': this.materialsSubject,
        'ModuleInfo': this.moduleInfoSubject,
        'Rank': this.rankSubject,
        'Progress': this.progressSubject,
        'Reputation': this.reputationSubject,
        'SquadronStartup': this.squadronStartupSubject,
        'Statistics': this.statisticsSubject,
        'Powerplay': this.powerplaySubject,
        'ShipLocker': this.shipLockerSubject,
        'Loadout': this.loadoutSubject,
        'Shipyard': this.shipyardSubject,
        'StoredShips': this.storedShipsSubject,
        'Market': this.marketSubject,
        'Outfitting': this.outfittingSubject,
    };

    constructor(private tauriService: TauriService) {
        // Subscribe to states messages from the TauriService
        this.tauriService.output$.pipe(
            filter((message): message is StatesMessage => message.type === "states")
        ).subscribe((message) => {
            const currentState = this.projectionsSubject.getValue()
            const newState = {...currentState, ...message.states};
            this.projectionsSubject.next(newState);

            // Update individual projection subjects
            Object.entries(message.states).forEach(([key, value]) => {
                const subject = this.projectionSubjects[key];
                if (subject) {
                    subject.next(value);
                }
            });
        });
    }

    public getCurrentProjections(): Record<string, any> | null {
        return this.projectionsSubject.getValue();
    }

    public getProjection(name: string): Observable<any> {
        const subject = this.projectionSubjects[name];
        if (subject) {
            return subject.asObservable().pipe(
                filter(value => value !== null)
            );
        }
        
        // Fallback to the legacy method for unknown projections
        return this.projections$.pipe(
            filter((projections): projections is Record<string, any> => projections !== null),
            filter((projections) => name in projections),
            map(projections => projections[name])
        );
    }

    public getProjectionValue(name: string): any | null {
        const subject = this.projectionSubjects[name];
        if (subject) {
            return subject.getValue();
        }
        
        // Fallback to the legacy method for unknown projections
        const projections = this.getCurrentProjections();
        return projections ? projections[name] || null : null;
    }

    // Individual projection value getters
    public getCurrentStatusValue(): any | null {
        return this.currentStatusSubject.getValue();
    }

    public getLocationValue(): any | null {
        return this.locationSubject.getValue();
    }

    public getMissionsValue(): any | null {
        return this.missionsSubject.getValue();
    }

    public getEngineerProgressValue(): any | null {
        return this.engineerProgressSubject.getValue();
    }

    public getCommunityGoalValue(): any | null {
        return this.communityGoalSubject.getValue();
    }

    public getShipInfoValue(): any | null {
        return this.shipInfoSubject.getValue();
    }

    public getTargetValue(): any | null {
        return this.targetSubject.getValue();
    }

    public getNavInfoValue(): any | null {
        return this.navInfoSubject.getValue();
    }

    public getExobiologyScanValue(): any | null {
        return this.exobiologyScanSubject.getValue();
    }

    public getCargoValue(): any | null {
        return this.cargoSubject.getValue();
    }

    public getBackpackValue(): any | null {
        return this.backpackSubject.getValue();
    }

    public getSuitLoadoutValue(): any | null {
        return this.suitLoadoutSubject.getValue();
    }

    public getFriendsValue(): any | null {
        return this.friendsSubject.getValue();
    }

    public getColonisationConstructionValue(): any | null {
        return this.colonisationConstructionSubject.getValue();
    }

    public getDockingEventsValue(): any | null {
        return this.dockingEventsSubject.getValue();
    }

    public getInCombatValue(): any | null {
        return this.inCombatSubject.getValue();
    }

    public getWingValue(): any | null {
        return this.wingSubject.getValue();
    }

    public getIdleValue(): any | null {
        return this.idleSubject.getValue();
    }

    public getCommanderValue(): any | null {
        return this.commanderSubject.getValue();
    }

    public getMaterialsValue(): any | null {
        return this.materialsSubject.getValue();
    }

    public getModuleInfoValue(): any | null {
        return this.moduleInfoSubject.getValue();
    }

    public getRankValue(): any | null {
        return this.rankSubject.getValue();
    }

    public getProgressValue(): any | null {
        return this.progressSubject.getValue();
    }

    public getReputationValue(): any | null {
        return this.reputationSubject.getValue();
    }

    public getSquadronStartupValue(): any | null {
        return this.squadronStartupSubject.getValue();
    }

    public getStatisticsValue(): any | null {
        return this.statisticsSubject.getValue();
    }

    public getPowerplayValue(): any | null {
        return this.powerplaySubject.getValue();
    }

    public getShipLockerValue(): any | null {
        return this.shipLockerSubject.getValue();
    }

    public getLoadoutValue(): any | null {
        return this.loadoutSubject.getValue();
    }

    public getShipyardValue(): any | null {
        return this.shipyardSubject.getValue();
    }

    public getStoredShipsValue(): any | null {
        return this.storedShipsSubject.getValue();
    }

    public getMarketValue(): any | null {
        return this.marketSubject.getValue();
    }

    public getOutfittingValue(): any | null {
        return this.outfittingSubject.getValue();
    }

    public isProjectionStateTrue(projectionName: string, statePath: string): Observable<boolean> {
        return this.getProjection(projectionName).pipe(
            map(projection => {
                if (!projection) return false;
                
                // Navigate the nested state path (e.g., "flags.InDanger")
                const pathParts = statePath.split('.');
                let current = projection;
                
                for (const part of pathParts) {
                    if (current && typeof current === 'object' && part in current) {
                        current = current[part];
                    } else {
                        return false;
                    }
                }
                
                return Boolean(current);
            })
        );
    }

    // Utility method to get the observable for a specific projection by name
    public getProjectionObservable(name: string): Observable<any> | null {
        const subject = this.projectionSubjects[name];
        return subject ? subject.asObservable().pipe(filter(value => value !== null)) : null;
    }

    // Utility method to check if a projection exists
    public hasProjection(name: string): boolean {
        return name in this.projectionSubjects;
    }
} 