import { TestBed } from "@angular/core/testing";
import { Subject } from "rxjs";
import { BaseMessage, TauriService } from "./tauri.service";
import { UIService } from "./ui.service";

describe("shared interface navigation", () => {
    let output: Subject<BaseMessage>;
    let channel: jasmine.SpyObj<BroadcastChannel>;
    let service: UIService;

    beforeEach(() => {
        output = new Subject<BaseMessage>();
        channel = jasmine.createSpyObj<BroadcastChannel>("BroadcastChannel", ["postMessage", "close"]);
        spyOn(window, "BroadcastChannel").and.returnValue(channel);
        TestBed.configureTestingModule({
            providers: [{ provide: TauriService, useValue: { output$: output } }],
        });
        service = TestBed.inject(UIService);
    });

    function receive(data: object): void {
        channel.onmessage!(new MessageEvent("message", { data }));
    }

    it("requests the current selection and broadcasts tab and subtab changes", () => {
        expect(channel.postMessage).toHaveBeenCalledWith({ type: "request-current" });
        service.showTab("plugin:example:dashboard", "detail");
        expect(channel.postMessage).toHaveBeenCalledWith({
            type: "navigation", navigation: { type: "ui", show: "plugin:example:dashboard", submenu: "detail" },
        });
    });

    it("applies another window's navigation without rebroadcasting it", () => {
        const navigation = { type: "ui", show: "navigation", submenu: "route" };
        const values: unknown[] = [];
        service.changeUI$.subscribe(value => values.push(value));
        channel.postMessage.calls.reset();
        receive({ type: "navigation", navigation });
        expect(values.at(-1)).toEqual(navigation);
        expect(channel.postMessage).not.toHaveBeenCalled();
    });

    it("delivers section requests once without replacing or replaying the current navigation", () => {
        const requests: unknown[] = [];
        service.sectionRequests$.subscribe(request => requests.push(request));
        output.next({type: "ui", timestamp: "", index: 0, show: "plugin:example:dashboard", submenu: "detail"});
        const request = {request_id: "request", expanded: false, index: 2};
        output.next({type: "ui", timestamp: "", index: 1, section: request});
        expect(requests).toEqual([request]);
        const lateRequests: unknown[] = [];
        service.sectionRequests$.subscribe(request => lateRequests.push(request));
        expect(lateRequests).toEqual([]);
        receive({type: "request-current"});
        expect(channel.postMessage).toHaveBeenCalledWith({
            type: "navigation", navigation: jasmine.objectContaining({show: "plugin:example:dashboard", submenu: "detail"}),
        });
    });

    it("keeps the selected view available after scrolling without replaying the scroll", () => {
        const navigation = {type: "ui", show: "plugin:example:dashboard", submenu: "detail", timestamp: "", index: 0};
        output.next(navigation);
        output.next({type: "ui", scroll: "down", timestamp: "", index: 1});
        receive({type: "request-current"});
        expect(channel.postMessage).toHaveBeenCalledWith({type: "navigation", navigation});
    });

    it("does not replay a scroll command when there is no selected view", () => {
        output.next({type: "ui", scroll: "down", timestamp: "", index: 0});
        channel.postMessage.calls.reset();
        receive({type: "request-current"});
        expect(channel.postMessage).not.toHaveBeenCalled();
    });

    it("closes its navigation channel and subscription when destroyed", () => {
        service.ngOnDestroy();
        expect(channel.close).toHaveBeenCalled();
        const values: unknown[] = [];
        service.changeUI$.subscribe(value => values.push(value));
        output.next({type: "ui", show: "chat", timestamp: "", index: 1});
        expect(values).toEqual([null]);
    });
});
