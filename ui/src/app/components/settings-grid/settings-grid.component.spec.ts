import { TestBed } from "@angular/core/testing";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { TranslateModule } from "@ngx-translate/core";
import { SettingsGridComponent } from "./settings-grid.component";
import { SettingsGrid } from "../../services/plugin-settings";

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
});
