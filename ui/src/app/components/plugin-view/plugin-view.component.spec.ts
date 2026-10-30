import { TestBed } from "@angular/core/testing";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { TranslateModule } from "@ngx-translate/core";
import { BehaviorSubject, Subject } from "rxjs";
import { MatSnackBar } from "@angular/material/snack-bar";
import { PluginViewComponent } from "./plugin-view.component";
import { ConfigService } from "../../services/config.service";
import { PluginUIService } from "../../services/plugin-ui.service";
import { UIService } from "../../services/ui.service";
import { RegisteredUIView } from "../../services/plugin-ui";
import { BaseMessage, TauriService } from "../../services/tauri.service";

describe("plugin view host", () => {
  it("renders all four upgrade subtabs from voice messages, including progression before mounting and repeated switches", async () => {
    const output = new Subject<BaseMessage>();
    const channel = jasmine.createSpyObj<BroadcastChannel>("BroadcastChannel", ["postMessage", "close"]);
    spyOn(window, "BroadcastChannel").and.returnValue(channel);
    await TestBed.configureTestingModule({
      imports: [PluginViewComponent, TranslateModule.forRoot(), NoopAnimationsModule],
      providers: [
        {provide: ConfigService, useValue: {getPluginSettingsConfig: () => undefined, getCurrentConfig: () => null}},
        {provide: PluginUIService, useValue: {getValue: (_guid: string, _key: string, fallback: unknown) => fallback}},
        {provide: TauriService, useValue: {output$: output}},
        {provide: MatSnackBar, useValue: {open: jasmine.createSpy("open")}},
      ],
    }).compileComponents();
    TestBed.inject(UIService);
    const view: RegisteredUIView = {
      id: "upgrades", target: "plugin:ship:upgrades", pluginGuid: "ship", label: "Améliorations",
      sections: [
        {key: "route", label: "Route"},
        {key: "session", label: "Progression"},
        {key: "broker", label: "Plans à débloquer"},
        {key: "plans", label: "Plans"},
      ].map(section => ({...section, content: [{type: "text", text: {text: `Content: ${section.key}`}}]})),
    };
    output.next({type: "ui", timestamp: "", index: 0, show: view.target, submenu: "session"});
    const fixture = TestBed.createComponent(PluginViewComponent);
    fixture.componentRef.setInput("view", view);
    fixture.detectChanges();
    for (const key of ["session", "broker", "plans", "route", "session"]) {
      output.next({type: "ui", timestamp: "", index: 1, show: view.target, submenu: key});
      fixture.detectChanges();
      await fixture.whenStable();
      fixture.detectChanges();
      const section = view.sections.find(section => section.key === key)!;
      const root: HTMLElement = fixture.nativeElement;
      expect(root.querySelector("[role=tab][aria-selected=true]")?.textContent?.trim()).toBe(section.label);
      expect(root.querySelector(".mat-mdc-tab-body-active")?.textContent).toContain(`Content: ${key}`);
    }
    fixture.componentRef.setInput("view", {...view});
    fixture.detectChanges();
    await fixture.whenStable();
    expect(fixture.componentInstance.selectedIndex).toBe(1);
    expect(channel.postMessage).toHaveBeenCalledOnceWith({type: "request-current"});
  });

  it("handles navigation before mounting, renders declared sections and preserves user selection on refresh", async () => {
    const messages = new BehaviorSubject({type: "ui", show: "plugin:example:dashboard", submenu: "detail"});
    const showTab = jasmine.createSpy("showTab");
    const invoke = jasmine.createSpy("invoke").and.resolveTo();
    await TestBed.configureTestingModule({
      imports: [PluginViewComponent, TranslateModule.forRoot(), NoopAnimationsModule],
      providers: [
        {provide: ConfigService, useValue: {getPluginSettingsConfig: () => ({grids: [
          {key: "shared", label: "", fields: [], content: [{type: "heading", tone: "info", text: {text: "Live data"}}]},
        ]}), getCurrentConfig: () => null}},
        {provide: PluginUIService, useValue: {invoke, getValue: (_guid: string, _key: string, fallback: unknown) => fallback}},
        {provide: UIService, useValue: {changeUI$: messages, showTab}},
        {provide: MatSnackBar, useValue: {open: jasmine.createSpy("open")}},
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(PluginViewComponent);
    const view: RegisteredUIView = {id: "dashboard", target: "plugin:example:dashboard", pluginGuid: "example", label: "Panel", sections: [
      {key: "overview", label: "Overview", content: []},
      {key: "detail", label: "Details", grids: ["shared"]},
    ]};
    fixture.componentRef.setInput("view", view);
    fixture.detectChanges();
    expect(fixture.componentInstance.selectedIndex).toBe(1);
    fixture.componentInstance.onSectionSelected(0);
    expect(showTab).toHaveBeenCalledOnceWith(view.target, "overview");
    expect(fixture.nativeElement.textContent).toContain("Live data");
    expect(fixture.nativeElement.querySelector("app-settings-grid app-plugin-content h3")?.textContent).toBe("Live data");
    fixture.componentInstance.selectedIndex = 0;
    fixture.componentRef.setInput("view", {...view});
    fixture.detectChanges();
    expect(fixture.componentInstance.selectedIndex).toBe(0);
    fixture.componentInstance.onButtonClick("refresh:item", "value");
    expect(invoke).toHaveBeenCalledWith("example", "settings_button", {key: "refresh:item", value: "value"});
    messages.next({type: "ui", show: view.target, submenu: "detail"});
    expect(fixture.componentInstance.selectedIndex).toBe(1);
  });

  it("uses the shared input callback and renderer directly inside a view", async () => {
    const values: Record<string, unknown> = {search: "current"};
    const change = jasmine.createSpy("change").and.callFake((_guid, key, value) => {
      values[key] = value;
      return Promise.resolve();
    });
    const invoke = jasmine.createSpy("invoke").and.resolveTo();
    await TestBed.configureTestingModule({
      imports: [PluginViewComponent, TranslateModule.forRoot(), NoopAnimationsModule],
      providers: [
        {provide: ConfigService, useValue: {getCurrentConfig: () => null, getPluginSettingsConfig: () => undefined}},
        {provide: PluginUIService, useValue: {
          change, invoke, getValue: (_guid: string, key: string, fallback: unknown) => values[key] ?? fallback,
        }},
        {provide: UIService, useValue: {changeUI$: new BehaviorSubject(null)}},
        {provide: MatSnackBar, useValue: {open: jasmine.createSpy("open")}},
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(PluginViewComponent);
    const view: RegisteredUIView = {
      id: "dashboard", target: "plugin:example:dashboard", pluginGuid: "example", label: "Panel",
      sections: [{key: "main", label: "Main", content: [
        {type: "section", children: [
          {type: "text", key: "search", label: "Search", default_value: ""},
          {type: "button", key: "refresh", label: "Refresh"},
          {type: "progress", value: 3, maximum: 4},
        ]},
      ]}],
    };
    fixture.componentRef.setInput("view", view);
    fixture.detectChanges();
    await fixture.whenStable();
    const root: HTMLElement = fixture.nativeElement;
    const input = root.querySelector("input")!;
    expect(input.value).toBe("current");
    input.value = "filter";
    input.dispatchEvent(new Event("input"));
    expect(change).toHaveBeenCalledWith("example", "search", "filter");
    root.querySelector<HTMLButtonElement>("app-plugin-content button")!.click();
    expect(invoke).toHaveBeenCalledWith("example", "settings_button", {key: "refresh", value: undefined});
    expect(root.querySelector("mat-progress-bar")?.getAttribute("aria-valuenow")).toBe("75");
  });
});
