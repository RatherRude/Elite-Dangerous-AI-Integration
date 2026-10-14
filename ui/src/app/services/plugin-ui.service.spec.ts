import { TestBed } from "@angular/core/testing";
import { TranslateModule, TranslateService } from "@ngx-translate/core";
import { Subject } from "rxjs";
import { BaseMessage, TauriService } from "./tauri.service";
import { PluginUIService } from "./plugin-ui.service";
import { RegisteredUIView } from "./plugin-ui";

describe("generic plugin UI transport", () => {
  let output: Subject<BaseMessage>;
  let tauri: jasmine.SpyObj<TauriService>;
  let service: PluginUIService;
  let translate: TranslateService;

  beforeEach(() => {
    TestBed.configureTestingModule({imports: [TranslateModule.forRoot()]});
    translate = TestBed.inject(TranslateService);
    output = new Subject<BaseMessage>();
    tauri = jasmine.createSpyObj<TauriService>("TauriService", ["send_command"]);
    Object.defineProperty(tauri, "output$", {value: output});
    tauri.send_command.and.resolveTo();
    service = new PluginUIService(tauri, translate);
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
  });

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
});
