import { TestBed } from "@angular/core/testing";
import { TranslateModule, TranslateService } from "@ngx-translate/core";
import { PluginContentComponent } from "./plugin-content.component";
import { UINode } from "../../services/plugin-ui";
import { Component, CUSTOM_ELEMENTS_SCHEMA } from "@angular/core";

@Component({
  selector: "app-themed-content-test",
  standalone: true,
  imports: [PluginContentComponent],
  schemas: [CUSTOM_ELEMENTS_SCHEMA],
  styleUrls: ["../../main-view/main-view.component.css"],
  template: `<app-settings-menu><h3 class="menu-heading">Settings</h3><app-plugin-content [nodes]="nodes" /></app-settings-menu>`,
})
class SettingsMenuTestHost {
  nodes: UINode[] = [
    {type: "heading", tone: "info", text: {text: "Destination"}},
    {type: "heading", level: 4, text: {text: "Module"}},
    {type: "heading", level: 4, tone: "warning", text: {text: "Purchase required"}},
    {type: "text", tone: "warning", text: {text: "12 ly · 1 jump"}},
    {type: "text", text: {text: "Beam laser"}},
  ];
}

describe("generic plugin content", () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({imports: [PluginContentComponent, SettingsMenuTestHost, TranslateModule.forRoot()]}).compileComponents();
  });

  it("preserves blue, orange and white on visible content inside the themed settings menu", () => {
    const fixture = TestBed.createComponent(SettingsMenuTestHost);
    fixture.nativeElement.style.setProperty("--hud-orange", "#ff8800");
    fixture.detectChanges();
    const root: HTMLElement = fixture.nativeElement;
    expect(getComputedStyle(root.querySelector(".menu-heading")!).color).toBe("rgb(255, 136, 0)");
    expect(getComputedStyle(root.querySelector(".tone-info h3")!).color).toBe("rgb(117, 186, 255)");
    expect(getComputedStyle(root.querySelector(".tone-default h4")!).color).toBe("rgb(255, 255, 255)");
    expect(getComputedStyle(root.querySelector(".tone-warning h4")!).color).toBe("rgb(255, 180, 84)");
    expect(getComputedStyle(root.querySelector(".tone-warning span")!).color).toBe("rgb(255, 180, 84)");
    expect(getComputedStyle(root.querySelector(".tone-default span")!).color).toBe("rgb(255, 255, 255)");
  });

  it("renders nested localized content, progress, tones and action payloads", () => {
    const translate = TestBed.inject(TranslateService);
    translate.setTranslation("en", {plugin: {example: {need: "{{resource}}: {{count}} missing"}}});
    translate.setTranslation("fr", {plugin: {example: {need: "{{resource}} : {{count}} manquants"}}});
    translate.use("en");
    const fixture = TestBed.createComponent(PluginContentComponent);
    fixture.componentRef.setInput("nodes", [{type: "section", outlined: true, children: [
      {type: "heading", tone: "info", text: {text: "Inventory"}},
      {type: "list", children: [{type: "text", tone: "warning", text: {key: "plugin.example.need", params: {
        resource: {localized: {en: "Iron", fr: "Fer"}}, count: 2,
      }}}]},
      {type: "progress", value: 1, maximum: 4},
      {type: "action", action: "collect", payload: {resource: "iron"}, text: {text: "Collect"}},
    ]}] as UINode[]);
    const clicked = jasmine.createSpy("action");
    fixture.componentInstance.action.subscribe(clicked);
    fixture.detectChanges();
    const root: HTMLElement = fixture.nativeElement;
    expect(root.textContent).toContain("Iron: 2 missing");
    expect(root.querySelector(".outlined")).not.toBeNull();
    expect(getComputedStyle(root.querySelector(".tone-warning")!).color).toBe("rgb(255, 180, 84)");
    expect(root.querySelector("mat-progress-bar")!.getAttribute("aria-valuenow")).toBe("25");
    root.querySelector("button")!.click();
    expect(clicked).toHaveBeenCalledWith({action: "collect", payload: {resource: "iron"}});
    translate.use("fr");
    fixture.detectChanges();
    expect(root.textContent).toContain("Fer : 2 manquants");
  });
});
