import { Injectable } from "@angular/core";
import { BehaviorSubject } from "rxjs";

@Injectable({
    providedIn: "root",
})
export class PolicyService {
    public usageDisclaimerSubject = new BehaviorSubject<boolean>(
        window.localStorage.getItem("usageDisclaimerAccepted") === "true",
    );
    public usageDisclaimerAccepted$ = this.usageDisclaimerSubject
        .asObservable();

    public acceptUsageDisclaimer(): void {
        this.usageDisclaimerSubject.next(true);
        window.localStorage.setItem("usageDisclaimerAccepted", "true");
    }
}
