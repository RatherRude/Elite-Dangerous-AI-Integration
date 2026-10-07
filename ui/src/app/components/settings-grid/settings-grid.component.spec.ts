import { TestBed } from "@angular/core/testing";
import { SettingsGridComponent } from "./settings-grid.component";
import { SettingsFieldComponent } from "../settings-field/settings-field.component";
import { By } from "@angular/platform-browser";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import {
    matchesSettingCondition, providerVoiceSettingsValues, providerVoiceDisplayValue,
    SettingsGrid, SettingCondition, ModelProviderDefinition,
} from "../../services/plugin-settings";

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
        await TestBed.configureTestingModule({ imports: [SettingsGridComponent, NoopAnimationsModule] }).compileComponents();
    });

    it("reacts to default visibility and saved values, preserving hidden inputs and forwarding callbacks", () => {
        const fixture = TestBed.createComponent(SettingsGridComponent);
        const values: Record<string, unknown> = {};
        const component = fixture.componentInstance;
        component.grid = grid;
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
        expect(values["voice"]).toBe("saved voice");
        values["enabled"] = true;
        fixture.detectChanges();
        expect(fixture.debugElement.query(By.directive(SettingsFieldComponent)).componentInstance.value).toBe("saved voice");
    });

    it("collects nested voice defaults and preserves stored values without storing containers", () => {
        const provider = {
            plugin_guid: "example", id: "tts", kind: "tts", label: "Example", is_builtin: false,
            settings_config: [], voice_settings_config: [grid],
        } as ModelProviderDefinition;
        const ref = "plugin:example:tts";
        expect(providerVoiceSettingsValues(ref, [provider], undefined)).toEqual({ voice: "default voice" });
        const stored = { [ref]: { voice: "saved voice", advanced_options: true, unknown: 1 } };
        expect(providerVoiceSettingsValues(ref, [provider], stored)).toEqual({ voice: "saved voice" });
        expect(providerVoiceDisplayValue(ref, [provider], stored, "legacy")).toBe("saved voice");
    });
});
