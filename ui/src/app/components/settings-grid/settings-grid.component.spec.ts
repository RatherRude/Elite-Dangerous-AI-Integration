import { TestBed } from "@angular/core/testing";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { TranslateModule } from "@ngx-translate/core";
import { SettingsGridComponent } from "./settings-grid.component";
import { SettingsGrid, SettingCondition, ModelProviderDefinition, matchesSettingCondition,
  providerVoiceSettingsValues, providerVoiceDisplayValue } from "../../services/plugin-settings";
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

import { SettingsFieldComponent } from "../settings-field/settings-field.component";

describe("setting condition comparisons", () => {
    const cases: [SettingCondition["operator"], unknown, unknown, boolean][] = [
        ["eq", false, false, true], ["eq", "1", 1, false],
        ["neq", 1, "1", true], ["neq", 1, 1, false],
        ["gt", 2, 1, true], ["gt", 1, 1, false],
        ["geq", 1, 1, true], ["geq", 0, 1, false],
        ["lt", 0, 1, true], ["lt", 1, 1, false],
        ["leq", 1, 1, true], ["leq", 2, 1, false],
        ["gt", "2", 1, false], ["lt", null, 1, false],
        ["leq", NaN, 1, false], ["geq", Infinity, 1, false],
        ["in", "expert", ["custom", "expert"], true],
        ["in", 1, ["1"], false], ["not_in", "simple", ["expert"], true],
        ["not_in", "expert", ["expert"], false], ["not_in", "x", null, false],
        ["contains", ["a", "b"], "b", true], ["contains", "abc", "bc", true],
        ["contains", [1], "1", false], ["not_contains", "abc", "z", true],
        ["not_contains", [1], 1, false], ["not_contains", null, "x", false],
        ["contains", "123", 1, false], ["eq", undefined, true, false],
    ];
    for (const [operator, actual, value, expected] of cases) {
        it(`${operator}: ${JSON.stringify(actual)} against ${JSON.stringify(value)} -> ${expected}`, () => {
            expect(matchesSettingCondition({ key: "test", operator, value }, actual)).toBe(expected);
        });
    }

    it("uses default_show as the result only when the key is unset", () => {
        const condition: SettingCondition = { key: "test", operator: "eq", value: true, default_show: true };
        expect(matchesSettingCondition(condition, undefined)).toBeTrue();
        expect(matchesSettingCondition(condition, null)).toBeTrue();
        expect(matchesSettingCondition(condition, false)).toBeFalse();
        expect(matchesSettingCondition(condition, 0)).toBeFalse();
        expect(matchesSettingCondition(condition, "")).toBeFalse();
        expect(matchesSettingCondition({ ...condition, default_show: false }, undefined)).toBeFalse();
        expect(matchesSettingCondition({ key: "test", operator: "neq", value: true }, undefined)).toBeFalse();
    });

    it("tests presence without treating false, zero, or empty strings as unset", () => {
        for (const value of [undefined, null]) {
            expect(matchesSettingCondition({ key: "test", operator: "is_unset", default_show: false }, value)).toBeTrue();
            expect(matchesSettingCondition({ key: "test", operator: "is_set", default_show: true }, value)).toBeFalse();
        }
        for (const value of [false, 0, "", [], "model"]) {
            expect(matchesSettingCondition({ key: "test", operator: "is_unset" }, value)).toBeFalse();
            expect(matchesSettingCondition({ key: "test", operator: "is_set" }, value)).toBeTrue();
        }
    });
});

describe("nested conditional settings", () => {
    const grid = {
        key: "general", label: "General", fields: [{
            key: "advanced_options", type: "condition",
            condition: { key: "enabled", operator: "eq", value: true, default_show: true },
            fields: [{
                key: "voice", label: "Voice", type: "text", default_value: "default voice",
            }, {
                key: "inner", type: "condition",
                condition: { key: "level", operator: "geq", value: 2, default_show: false },
                fields: [{ key: "refresh", label: "Refresh", type: "button" }],
            }],
        }],
    } as SettingsGrid;

    beforeEach(async () => {
        await TestBed.configureTestingModule({ imports: [SettingsGridComponent, TranslateModule.forRoot(), NoopAnimationsModule] }).compileComponents();
    });

    for (const collapsible of [false, true]) {
    it(`preserves conditional fields and callbacks with collapsible=${collapsible}`, () => {
        const fixture = TestBed.createComponent(SettingsGridComponent);
        const values: Record<string, unknown> = {};
        const component = fixture.componentInstance;
        component.grid = {...grid, collapsible};
        component.getValue = (key, fallback) => values[key] ?? fallback;
        component.setValue = (key, value) => { values[key] = value; };
        component.onButtonClick = jasmine.createSpy("button");
        fixture.detectChanges();
        expect(fixture.debugElement.queryAll(By.directive(SettingsFieldComponent)).length).toBe(1);
        const input = fixture.debugElement.query(By.directive(SettingsFieldComponent));
        input.componentInstance.valueChange.emit("saved voice");
        expect(values["voice"]).toBe("saved voice");

        values["level"] = 2;
        fixture.detectChanges();
        const fields = fixture.debugElement.queryAll(By.directive(SettingsFieldComponent));
        expect(fields.length).toBe(2);
        fields[1].componentInstance.buttonClick.emit();
        expect(component.onButtonClick).toHaveBeenCalledWith("refresh");

        values["enabled"] = false;
        fixture.detectChanges();
        expect(fixture.debugElement.queryAll(By.directive(SettingsFieldComponent)).length).toBe(0);
        const button = component.onButtonClick as jasmine.Spy;
        button.calls.reset();
        component.handleEnterSubmit();
        expect(button).not.toHaveBeenCalled();
        expect(values["voice"]).toBe("saved voice");
        values["enabled"] = true;
        fixture.detectChanges();
        expect(fixture.debugElement.query(By.directive(SettingsFieldComponent)).componentInstance.value).toBe("saved voice");
        component.handleEnterSubmit();
        expect(button).toHaveBeenCalledOnceWith("refresh");
    });
    }

    it("collects nested voice defaults and preserves stored values without storing containers", () => {
        const provider = {
            plugin_guid: "example", id: "tts", kind: "tts", label: "Example", is_builtin: false,
            settings_config: [], voice_settings_config: [grid],
        } as ModelProviderDefinition;
        const ref = "plugin:example:tts";
        expect(providerVoiceSettingsValues(ref, [provider], undefined)).toEqual({ voice: "default voice" });
        const stored = { [ref]: { voice: "saved voice", advanced_options: true, unknown: 1 } };
        expect(providerVoiceSettingsValues(ref, [provider], stored)).toEqual({ voice: "saved voice", advanced_options: true, unknown: 1 });
        expect(providerVoiceDisplayValue(ref, [provider], stored)).toBe("saved voice");
    });
});

describe("notification settings", () => {
    beforeEach(async () => {
        await TestBed.configureTestingModule({ imports: [SettingsGridComponent, SettingsFieldComponent, TranslateModule.forRoot(), NoopAnimationsModule] }).compileComponents();
    });

    it("renders plugin-provided notification content and level", () => {
        const fixture = TestBed.createComponent(SettingsFieldComponent);
        fixture.componentInstance.field = {
            key: "notice", label: "Plugin notice", type: "notification", level: "warning",
            content: "Choose a replacement.",
        } as any;
        fixture.detectChanges();

        const notification = fixture.nativeElement.querySelector(".notification-field.warning");
        expect(notification.textContent).toContain("Plugin notice");
        expect(notification.textContent).toContain("Choose a replacement.");
    });

    it("lets the plugin condition decide when and where to show a notification", () => {
        const fixture = TestBed.createComponent(SettingsGridComponent);
        const values: Record<string, unknown> = { model: "legacy-model" };
        fixture.componentInstance.grid = {
            key: "models", label: "Models", fields: [{
                key: "model", label: "Model", type: "select", default_value: "supported-model",
                select_options: [{ key: "supported-model", label: "Supported", value: "supported-model", disabled: false }],
                multi_select: false,
            }, {
                key: "legacy-model-notice", type: "condition",
                condition: { key: "model", operator: "not_in", value: ["supported-model"] },
                fields: [{
                    key: "notice", label: null, type: "notification", level: "warning",
                    content: "Plugin-selected warning.",
                }],
            }],
        } as any;
        fixture.componentInstance.getValue = (key, fallback) => values[key] ?? fallback;
        fixture.componentInstance.setValue = (key, value) => { values[key] = value; };
        fixture.detectChanges();
        expect(fixture.nativeElement.querySelector(".notification-field")).not.toBeNull();

        values["model"] = "supported-model";
        fixture.detectChanges();
        expect(fixture.nativeElement.querySelector(".notification-field")).toBeNull();
    });
});
