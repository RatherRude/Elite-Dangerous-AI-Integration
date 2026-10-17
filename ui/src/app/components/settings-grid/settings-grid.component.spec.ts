import { TestBed } from "@angular/core/testing";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { TranslateModule } from "@ngx-translate/core";
import { SettingsGridComponent } from "./settings-grid.component";
import { SettingsGrid } from "../../services/plugin-settings";
import { UIComponent } from "../../services/plugin-ui";
import { By } from "@angular/platform-browser";
import { MatSelect } from "@angular/material/select";

describe("settings grid content", () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SettingsGridComponent, TranslateModule.forRoot(), NoopAnimationsModule],
    }).compileComponents();
  });

  for (const collapsible of [false, true]) {
    it(`renders structured content and forwards actions with collapsible=${collapsible}`, () => {
      const fixture = TestBed.createComponent(SettingsGridComponent);
      const grid: SettingsGrid = {key: "itinerary", label: collapsible ? "Itinerary" : "", collapsible, fields: [], content: [
        {type: "section", children: [
          {type: "heading", tone: "info", text: {text: "Destination"}},
          {type: "inline", children: [{type: "text", tone: "warning", text: {text: "12 ly · 1 jump"}}]},
          {type: "action", text: {text: "Inspect"}, action: "inspect", payload: {stop: 1}},
        ]},
      ]};
      fixture.componentRef.setInput("grid", grid);
      const action = jasmine.createSpy("uiAction");
      fixture.componentInstance.uiAction.subscribe(action);
      fixture.detectChanges();
      const root: HTMLElement = fixture.nativeElement;
      expect(root.querySelector("app-plugin-content h3")?.textContent).toBe("Destination");
      expect(root.querySelector(".inline .tone-warning")?.textContent).toContain("12 ly · 1 jump");
      const inline = root.querySelector<HTMLElement>(".inline > app-plugin-content")!;
      expect(getComputedStyle(inline).display).toBe("flex");
      expect(inline.firstElementChild!.getBoundingClientRect().width).toBeLessThan(inline.getBoundingClientRect().width);
      expect(getComputedStyle(root.querySelector(".tone-info")!).color).toBe("rgb(117, 186, 255)");
      if (!collapsible) expect(root.querySelector(".grid-header")).toBeNull();
      root.querySelector<HTMLButtonElement>("app-plugin-content button")!.click();
      expect(action).toHaveBeenCalledWith({action: "inspect", payload: {stop: 1}});
      fixture.componentRef.setInput("grid", {...grid, content: [{type: "text", text: {text: "Updated destination"}}]});
      fixture.detectChanges();
      expect(root.textContent).toContain("Updated destination");
      expect(root.textContent).not.toContain("12 ly");
    });
  }

  for (const placement of ["fields", "content"] as const) {
    it(`renders inputs, buttons and progress in ${placement}, including dynamic replacements`, async () => {
      const fixture = TestBed.createComponent(SettingsGridComponent);
      const components: UIComponent[] = [
        {key: "search", type: "text", label: "Search", default_value: ""},
        {key: "refresh", type: "button", label: "Refresh"},
        {type: "progress", value: 2, maximum: 10, text: {text: "Loading"}},
        {key: "choice", type: "select", label: "Choice", select_options: [
          {key: "one", label: "First", value: "one", disabled: false},
        ]},
      ];
      const values: Record<string, unknown> = {search: "initial", choice: "one"};
      const setValue = jasmine.createSpy("setValue").and.callFake((key, value) => values[key] = value);
      const button = jasmine.createSpy("button");
      const grid: SettingsGrid = {key: "shared", label: "", fields: [], [placement]: components};
      fixture.componentRef.setInput("grid", grid);
      fixture.componentRef.setInput("getValue", (key: string, fallback: unknown) => values[key] ?? fallback);
      fixture.componentRef.setInput("setValue", setValue);
      fixture.componentRef.setInput("onButtonClick", button);
      fixture.detectChanges();
      await fixture.whenStable();
      const root: HTMLElement = fixture.nativeElement;
      const input = root.querySelector("input")!;
      expect(input.value).toBe("initial");
      input.value = "filter";
      input.dispatchEvent(new Event("input"));
      root.querySelector("button")!.click();
      expect(setValue).toHaveBeenCalledWith("search", "filter");
      expect(button).toHaveBeenCalledWith("refresh");
      expect(root.querySelector("mat-progress-bar")?.getAttribute("aria-valuenow")).toBe("20");
      const updated = components.map(node => node.type === "progress"
        ? {...node, value: 8, text: {text: "Ready"}}
        : node.type === "select" ? {...node, select_options: [
          ...node.select_options ?? [], {key: "two", label: "Second", value: "two", disabled: false},
        ]} : {...node});
      fixture.componentRef.setInput("grid", {...grid, [placement]: updated});
      fixture.detectChanges();
      await fixture.whenStable();
      expect(root.querySelector("input")?.value).toBe("filter");
      expect(root.querySelector("mat-progress-bar")?.getAttribute("aria-valuenow")).toBe("80");
      expect(root.textContent).toContain("Ready");
      const select: MatSelect = fixture.debugElement.query(By.directive(MatSelect)).componentInstance;
      expect(select.options.map(option => option.viewValue)).toEqual(["First", "Second"]);
    });
  }
});
