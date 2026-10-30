import {Injectable, NgZone, OnDestroy} from "@angular/core";
import {BaseMessage, TauriService} from "./tauri.service";
import {BehaviorSubject, Subject, Subscription} from "rxjs";

export interface UISectionRequest {
    request_id: string;
    expanded: boolean;
    name?: string;
    index?: number;
}

export interface UIMessage extends BaseMessage {
    type: "ui",
    show?: string,
    submenu?: string,
    scroll?: "top" | "up" | "down" | "bottom",
    section?: UISectionRequest,
}

type UIChange = Pick<UIMessage, "type" | "show" | "submenu" | "scroll">;
type NavigationMessage = { type: "request-current" }
    | { type: "navigation"; navigation: UIChange };

@Injectable({
    providedIn: "root",
})
export class UIService implements OnDestroy {
    private changeUISubject = new BehaviorSubject<UIChange | null>(null);
    private currentNavigation: UIChange | null = null;
    public changeUI$ = this.changeUISubject.asObservable();
    private readonly sectionRequests = new Subject<UISectionRequest>();
    public readonly sectionRequests$ = this.sectionRequests.asObservable();
    private readonly navigation = new BroadcastChannel("covas-ui-navigation");
    private readonly subscription: Subscription;

    constructor(private tauriService: TauriService, zone: NgZone) {
        this.subscription = tauriService.output$.subscribe((message) => {
            if (message.type == 'ui') {
                const msg = message as UIMessage;
                if (msg.section) this.sectionRequests.next(msg.section);
                if (msg.show || msg.scroll) {
                    if (msg.show) this.currentNavigation = msg;
                    this.changeUISubject.next(msg);
                }
            }
        })
        this.navigation.onmessage = (event: MessageEvent<NavigationMessage>) => zone.run(() => {
            if (event.data.type === "request-current") {
                if (this.currentNavigation?.show) {
                    this.navigation.postMessage({
                        type: "navigation", navigation: this.currentNavigation,
                    } satisfies NavigationMessage);
                }
            } else if (event.data.type === "navigation") {
                this.currentNavigation = event.data.navigation;
                this.changeUISubject.next(event.data.navigation);
            }
        });
        this.navigation.postMessage({ type: "request-current" } satisfies NavigationMessage);
    }

    public showTab(tabName: string, submenu?: string) {
        const navigation: UIChange = { type: "ui", show: tabName, submenu };
        this.currentNavigation = navigation;
        this.changeUISubject.next(navigation);
        this.navigation.postMessage({ type: "navigation", navigation } satisfies NavigationMessage);
    }

    ngOnDestroy(): void {
        this.subscription.unsubscribe();
        this.navigation.close();
    }
}
