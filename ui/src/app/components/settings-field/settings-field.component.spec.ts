import { TestBed } from "@angular/core/testing";
import { TranslateModule, TranslateService } from "@ngx-translate/core";
import { SettingsFieldComponent } from "./settings-field.component";
import { ListSetting } from "../../services/plugin-settings";

describe("generic list settings", () => {
    beforeEach(async () => {
        await TestBed.configureTestingModule({
            imports: [SettingsFieldComponent, TranslateModule.forRoot()],
        }).compileComponents();
        const translate = TestBed.inject(TranslateService);
        translate.setTranslation("en", { library: { title: "Library", count: "{{count}} entries" } });
        translate.use("en");
    });

    function createList() {
        const fixture = TestBed.createComponent(SettingsFieldComponent);
        fixture.componentRef.setInput("field", {
            key: "library", type: "list", label: "library.title", readonly: false,
            items: [{ key: "one", title: "First", group: "Category", suffix: "v2",
                details: [{ type: "action", action: "inspect", text: { text: "Inspect" }, payload: { id: "one" } }] },
                { key: "two", title: "Second", group: "Category" }],
            count_labels: { one: "library.count", many: "library.count" },
            row_actions: [{ action: "rename", icon: "edit", label: "Rename", inline_edit: true }],
        } as ListSetting);
        fixture.detectChanges();
        return fixture;
    }

    it("renders translated groups and generic details, and collapses their rows", () => {
        const fixture = createList();
        const root: HTMLElement = fixture.nativeElement;
        const actions: unknown[] = [];
        fixture.componentInstance.uiAction.subscribe(action => actions.push(action));
        expect(root.textContent).toContain("Library");
        expect(root.querySelector(".list-group-count")!.textContent).toContain("2 entries");
        expect(root.querySelector(".list-row-title")!.textContent).toContain("First v2");
        (root.querySelector("app-plugin-content button") as HTMLButtonElement).click();
        expect(actions).toEqual([{ action: "inspect", payload: { id: "one" } }]);
        (root.querySelector(".list-group") as HTMLButtonElement).click();
        fixture.detectChanges();
        expect(root.querySelectorAll(".list-row").length).toBe(0);
    });

    it("passes the edited title and row identity to the owner action", () => {
        const fixture = createList();
        const root: HTMLElement = fixture.nativeElement;
        const actions: unknown[] = [];
        fixture.componentInstance.listAction.subscribe(action => actions.push(action));
        (root.querySelector(".list-row-actions button") as HTMLButtonElement).click();
        fixture.detectChanges();
        const input = root.querySelector(".rename-input") as HTMLInputElement;
        input.value = "Renamed";
        input.dispatchEvent(new Event("input"));
        input.dispatchEvent(new KeyboardEvent("keyup", { key: "Enter" }));
        expect(actions).toEqual([{ action: "rename", rowKey: "one", value: "Renamed" }]);
    });
});
