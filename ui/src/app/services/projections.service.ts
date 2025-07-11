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

    constructor(private tauriService: TauriService) {
        // Subscribe to states messages from the TauriService
        this.tauriService.output$.pipe(
            filter((message): message is StatesMessage => message.type === "states")
        ).subscribe((message) => {
            const currentState = this.projectionsSubject.getValue()
            this.projectionsSubject.next({...currentState, ...message.states});
        });
    }

    public getCurrentProjections(): Record<string, any> | null {
        return this.projectionsSubject.getValue();
    }

    public getProjection(name: string): Observable<any> {
        return this.projections$.pipe(
            filter((projections): projections is Record<string, any> => projections !== null),
            filter((projections) => name in projections),
            map(projections => projections[name])
        );
    }

    public getProjectionValue(name: string): any | null {
        const projections = this.getCurrentProjections();
        return projections ? projections[name] || null : null;
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
} 