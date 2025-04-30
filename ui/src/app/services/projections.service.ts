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
    private projectionsSubject = new BehaviorSubject<Record<string, any> | null>(null);
    public projections$ = this.projectionsSubject.asObservable();

    constructor(private tauriService: TauriService) {
        // Subscribe to states messages from the TauriService
        this.tauriService.output$.pipe(
            filter((message): message is StatesMessage => message.type === "states")
        ).subscribe((message) => {
            this.projectionsSubject.next(message.states);
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
} 