import { TestBed } from "@angular/core/testing";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { TranslateModule } from "@ngx-translate/core";
import { BehaviorSubject } from "rxjs";
import { MatSnackBar } from "@angular/material/snack-bar";
import { PluginViewComponent } from "./plugin-view.component";
import { ConfigService } from "../../services/config.service";
import { PluginUIService } from "../../services/plugin-ui.service";
import { UIService } from "../../services/ui.service";
import { RegisteredUIView } from "../../services/plugin-ui";

describe("plugin view host", () => {
  it("handles navigation before mounting, renders declared sections and preserves user selection on refresh", async () => {
    const messages = new BehaviorSubject({type: "ui", show: "plugin:example:dashboard", submenu: "detail"});
    const invoke = jasmine.createSpy("invoke").and.resolveTo();
    await TestBed.configureTestingModule({
      imports: [PluginViewComponent, TranslateModule.forRoot(), NoopAnimationsModule],
      providers: [
        {provide: ConfigService, useValue: {getPluginSettingsConfig: () => ({grids: [
          {key: "shared", label: "", fields: [], content: [{type: "heading", tone: "info", text: {text: "Live data"}}]},
        ]}), getCurrentConfig: () => null}},
        {provide: PluginUIService, useValue: {invoke}},
        {provide: UIService, useValue: {changeUI$: messages}},
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
});
