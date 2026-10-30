import { TestBed } from "@angular/core/testing";
import { TranslateModule, TranslateService } from "@ngx-translate/core";
import { Subject } from "rxjs";
import { BaseMessage, TauriService } from "./tauri.service";
import { PluginUIService } from "./plugin-ui.service";
import { RegisteredUIView } from "./plugin-ui";
import { MatSnackBar } from "@angular/material/snack-bar";

describe("generic plugin UI transport", () => {
  let output: Subject<BaseMessage>;
  let tauri: jasmine.SpyObj<TauriService>;
  let service: PluginUIService;
  let translate: TranslateService;
  let snackBar: jasmine.SpyObj<MatSnackBar>;

  beforeEach(() => {
    TestBed.configureTestingModule({imports: [TranslateModule.forRoot()]});
    translate = TestBed.inject(TranslateService);
    output = new Subject<BaseMessage>();
    tauri = jasmine.createSpyObj<TauriService>("TauriService", ["send_command"]);
    Object.defineProperty(tauri, "output$", {value: output});
    tauri.send_command.and.resolveTo();
    snackBar = jasmine.createSpyObj<MatSnackBar>("MatSnackBar", ["open"]);
    service = new PluginUIService(tauri, translate, snackBar);
  });

  const contribution = (guid: string, order: number) => ({views: [{id: "dashboard", label: `plugin.${guid}.title`, order, sections: []}],
    translations: {en: {title: `Panel ${guid}`}, fr: {title: `Panneau ${guid}`}}});

  it("registers unrelated plugins, translates before run and clears removed contributions", () => {
    let views: RegisteredUIView[] = [];
    service.views$.subscribe(value => views = value);
    output.next({type: "plugin_ui", timestamp: "", index: 1, plugins: {alpha: contribution("alpha", 2), beta: contribution("beta", 1)}});
    expect(views.map(view => view.target)).toEqual(["plugin:beta:dashboard", "plugin:alpha:dashboard"]);
    translate.use("fr");
    expect(translate.instant("plugin.alpha.title")).toBe("Panneau alpha");
    output.next({type: "plugin_ui", timestamp: "", index: 2, plugins: {beta: contribution("beta", 1)}});
    expect(views.length).toBe(1);
    expect(translate.instant("plugin.alpha.title")).toBe("plugin.alpha.title");
    output.next({type: "ready", timestamp: "", index: 3});
    expect(views).toEqual([]);
  });

  it("waits for backend results and routes payloads to the owning GUID", async () => {
    const result = service.invoke("alpha", "refresh", {item: "one"});
    const command = tauri.send_command.calls.mostRecent().args[0];
    expect(command).toEqual(jasmine.objectContaining({plugin_guid: "alpha", action: "refresh", payload: {item: "one"}}));
    output.next({type: "plugin_ui_result", timestamp: "", index: 4, request_id: command["request_id"], success: true, result: {ready: true}});
    expect(await result).toEqual({ready: true});
    const failure = service.invoke("beta", "invalid");
    const request = tauri.send_command.calls.mostRecent().args[0];
    output.next({type: "plugin_ui_result", timestamp: "", index: 5, request_id: request["request_id"], success: false, error: "plugin.beta.invalid"});
    await expectAsync(failure).toBeRejectedWithError("plugin.beta.invalid");
    expect(snackBar.open).not.toHaveBeenCalled();
  });

  it("does not confuse independent plugin requests when results are broadcast to both windows", async () => {
    const other = new PluginUIService(tauri, translate, snackBar);
    const desktopResult = service.invoke("alpha", "refresh");
    const desktopRequest = tauri.send_command.calls.mostRecent().args[0]["request_id"];
    const otherResult = other.invoke("alpha", "refresh");
    const otherRequest = tauri.send_command.calls.mostRecent().args[0]["request_id"];
    expect(otherRequest).not.toBe(desktopRequest);
    output.next({type: "plugin_ui_result", timestamp: "", index: 0,
      request_id: desktopRequest, success: true, result: "desktop"});
    output.next({type: "plugin_ui_result", timestamp: "", index: 1,
      request_id: otherRequest, success: true, result: "other"});
    expect(await desktopResult).toBe("desktop");
    expect(await otherResult).toBe("other");
  });

  it("shows a translated action notification once, without replaying publications or duplicate results", async () => {
    translate.use("en");
    output.next({type: "plugin_ui", timestamp: "", index: 1, plugins: {
      alpha: {views: [], translations: {en: {added: "{{name}} added"}}},
    }});
    const result = service.invoke("alpha", "add");
    const request = tauri.send_command.calls.mostRecent().args[0];
    const reply = {type: "plugin_ui_result", timestamp: "", index: 2,
      request_id: request["request_id"], success: true,
      result: {notification: "plugin.alpha.added", params: {name: "Item"}}};
    output.next(reply);
    await result;
    expect(snackBar.open).toHaveBeenCalledOnceWith("Item added", undefined, {duration: 4000});
    output.next({type: "plugin_ui", timestamp: "", index: 3, plugins: {
      alpha: {views: [], translations: {en: {added: "{{name}} added"}}},
    }});
    output.next(reply);
    expect(snackBar.open).toHaveBeenCalledTimes(1);
  });

  for (const malformed of [{notification: 123}, {notification: ""},
    {notification: "added", params: null}, {notification: "added", params: {name: {invalid: true}}}]) {
  it(`reports malformed notification results explicitly: ${JSON.stringify(malformed)}`, async () => {
    const logged = spyOn(console, "error");
    translate.setTranslation("en", {common: {actionError: "Action failed"}});
    translate.use("en");
    const result = service.invoke("alpha", "add");
    const request = tauri.send_command.calls.mostRecent().args[0];
    output.next({type: "plugin_ui_result", timestamp: "", index: 1,
      request_id: request["request_id"], success: true, result: malformed});
    await result;
    expect(logged).toHaveBeenCalled();
    expect(snackBar.open).toHaveBeenCalledOnceWith("Action failed", undefined, {duration: 5000});
  });
  }

  it("contains every translation dictionary inside its registered owner", () => {
    translate.setTranslation("en", {common: {cancel: "Core cancel"}});
    translate.use("en");
    output.next({type: "plugin_ui", timestamp: "", index: 1, plugins: {
      alpha: {views: [], translations: {en: {common: {cancel: "Alpha cancel"}, plugin: {beta: {title: "Forged beta"}}}}},
      beta: contribution("beta", 1),
    }});
    expect(translate.instant("common.cancel")).toBe("Core cancel");
    expect(translate.instant("plugin.beta.title")).toBe("Panel beta");
    expect(translate.instant("plugin.alpha.common.cancel")).toBe("Alpha cancel");
    expect(translate.instant("plugin.alpha.plugin.beta.title")).toBe("Forged beta");
  });

  it("shares input state, sends edits and accepts authoritative dynamic publications", async () => {
    output.next({type: "plugin_ui", timestamp: "", index: 1, plugins: {
      alpha: {...contribution("alpha", 0), state: {search: "", enabled: false, choice: null}},
      beta: {...contribution("beta", 0), state: {search: "other"}},
    }});
    expect(service.getValue("alpha", "enabled", true)).toBeFalse();
    expect(service.getValue("alpha", "choice", "fallback")).toBeNull();
    const changed = service.change("alpha", "search", "filter");
    const command = tauri.send_command.calls.mostRecent().args[0];
    expect(command).toEqual(jasmine.objectContaining({
      plugin_guid: "alpha", action: "ui_changed", payload: {key: "search", value: "filter"},
    }));
    expect(service.getValue("alpha", "search", "")).toBe("filter");
    expect(service.getValue("beta", "search", "")).toBe("other");
    output.next({type: "plugin_ui", timestamp: "", index: 2, plugins: {
      alpha: {...contribution("alpha", 0), state: {search: "filter", enabled: true}},
    }});
    output.next({type: "plugin_ui_result", timestamp: "", index: 3,
      request_id: command["request_id"], success: true});
    await changed;
    expect(service.getValue("alpha", "search", "")).toBe("filter");
    expect(service.getValue("alpha", "enabled", false)).toBeTrue();
    expect(service.getValue("beta", "search", "removed")).toBe("removed");
    output.next({type: "ready", timestamp: "", index: 4});
    expect(service.getValue("alpha", "search", "reset")).toBe("reset");
  });

  it("rolls back rejected inputs without losing a different pending edit", async () => {
    output.next({type: "plugin_ui", timestamp: "", index: 1, plugins: {
      alpha: {...contribution("alpha", 0), state: {search: "before", enabled: false}},
    }});
    const failure = service.change("alpha", "search", "bad");
    const request = tauri.send_command.calls.mostRecent().args[0];
    const success = service.change("alpha", "enabled", true);
    const otherRequest = tauri.send_command.calls.mostRecent().args[0];
    output.next({type: "plugin_ui_result", timestamp: "", index: 2,
      request_id: request["request_id"], success: false, error: "Invalid"});
    await expectAsync(failure).toBeRejectedWithError("Invalid");
    expect(service.getValue("alpha", "search", "")).toBe("before");
    expect(service.getValue("alpha", "enabled", false)).toBeTrue();
    output.next({type: "plugin_ui_result", timestamp: "", index: 3,
      request_id: otherRequest["request_id"], success: true});
    await success;
  });

  it("does not overwrite newer typing when an earlier edit publishes its result", async () => {
    const first = service.change("alpha", "search", "f");
    const firstRequest = tauri.send_command.calls.mostRecent().args[0];
    const second = service.change("alpha", "search", "filter");
    const secondRequest = tauri.send_command.calls.mostRecent().args[0];
    output.next({type: "plugin_ui", timestamp: "", index: 1, plugins: {
      alpha: {...contribution("alpha", 0), state: {search: "f"}},
    }});
    output.next({type: "plugin_ui_result", timestamp: "", index: 2,
      request_id: firstRequest["request_id"], success: true});
    await first;
    expect(service.getValue("alpha", "search", "")).toBe("filter");
    output.next({type: "plugin_ui", timestamp: "", index: 3, plugins: {
      alpha: {...contribution("alpha", 0), state: {search: "normalized"}},
    }});
    output.next({type: "plugin_ui_result", timestamp: "", index: 4,
      request_id: secondRequest["request_id"], success: true});
    await second;
    expect(service.getValue("alpha", "search", "")).toBe("normalized");
  });
});
