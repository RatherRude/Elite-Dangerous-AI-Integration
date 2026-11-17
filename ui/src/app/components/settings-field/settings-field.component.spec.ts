import { TestBed } from "@angular/core/testing";
import { TranslateModule, TranslateService } from "@ngx-translate/core";
import { SettingsFieldComponent } from "./settings-field.component";
import { ListSetting } from "../../services/plugin-settings";
import { UISectionService } from "../../services/ui-section.service";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { ConfirmationDialogService } from "../../services/confirmation-dialog.service";
import { of } from "rxjs";

describe("generic list settings", () => {
    beforeEach(async () => {
        await TestBed.configureTestingModule({
            imports: [SettingsFieldComponent, TranslateModule.forRoot(), NoopAnimationsModule],
        }).compileComponents();
        const translate = TestBed.inject(TranslateService);
        translate.setTranslation("en", {
            library: {title: "Library", count: "{{count}} entries", confirmDelete: 'Delete {{title}} and {{sessions}} sessions?'},
            common: {moreActions: "More actions", details: "Details", confirm: "Confirm", cancel: "Cancel"},
        });
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

    it("keeps the compact summary visible with details initially closed", () => {
        const fixture = createList();
        fixture.componentRef.setInput("field", {...fixture.componentInstance.field,
            details_collapsible: true,
            items: [{key: "one", title: "First",
                summary: [{type: "text", text: {text: "Modules 75%"}}],
                details: [{type: "text", text: {text: "Full progress"}}]}],
        });
        fixture.detectChanges();
        const root: HTMLElement = fixture.nativeElement;
        expect(root.querySelector(".list-row-text")!.textContent).toContain("Modules 75%");
        const details = root.querySelector("details")!;
        expect(details.open).toBeFalse();
        expect(details.textContent).toContain("Full progress");
        details.querySelector("summary")!.click();
        expect(details.open).toBeTrue();
        const sections = TestBed.inject(UISectionService);
        sections.apply(root, {request_id: "collapse-row", expanded: false, name: "First"},
            () => fixture.detectChanges());
        expect(details.open).toBeFalse();
        sections.apply(root, {request_id: "expand-row", expanded: true, name: "one"},
            () => fixture.detectChanges());
        expect(details.open).toBeTrue();
    });

    it("reveals a newly highlighted row in a collapsed group, then allows collapsing it again", () => {
        const fixture = createList();
        const root: HTMLElement = fixture.nativeElement;
        root.querySelector<HTMLButtonElement>(".list-group")!.click();
        fixture.detectChanges();
        expect(root.querySelectorAll(".list-row").length).toBe(0);
        const field = fixture.componentInstance.field;
        fixture.componentRef.setInput("field", {...field,
            items: field.items?.map(row => ({...row, highlighted: row.key === "one"})),
        });
        fixture.detectChanges();
        expect(root.querySelector(".list-row.highlighted .list-row-title")!.textContent).toContain("First");
        root.querySelector<HTMLButtonElement>(".list-group")!.click();
        fixture.detectChanges();
        expect(root.querySelectorAll(".list-row").length).toBe(0);
    });

    it("keeps secondary actions in a menu and requires confirmation before deletion", async () => {
        const fixture = createList();
        const row = {key: "one", title: "First", params: {sessions: 2}};
        const remove = {action: "delete", icon: "delete", label: "Delete", secondary: true,
            danger: true, confirmation: "library.confirmDelete"};
        fixture.componentRef.setInput("field", {...fixture.componentInstance.field,
            items: [row], row_actions: [
                {action: "activate", icon: "play_arrow", label: "Activate"},
                {action: "rename", icon: "edit", label: "Rename", inline_edit: true, secondary: true},
                remove,
            ],
        });
        fixture.detectChanges();
        const root: HTMLElement = fixture.nativeElement;
        expect(root.querySelectorAll(".list-row-actions > button").length).toBe(2);
        const confirm = spyOn(TestBed.inject(ConfirmationDialogService), "openConfirmationDialog").and.returnValue(of(false));
        const emitted: unknown[] = [];
        fixture.componentInstance.listAction.subscribe(action => emitted.push(action));
        root.querySelector<HTMLButtonElement>('button[aria-label="More actions"]')!.click();
        fixture.detectChanges();
        await fixture.whenStable();
        const deleteButton = Array.from(document.querySelectorAll<HTMLButtonElement>("button[mat-menu-item]"))
            .find(button => button.textContent?.includes("Delete"))!;
        deleteButton.click();
        expect(confirm).toHaveBeenCalledWith(jasmine.objectContaining({message: "Delete First and 2 sessions?"}));
        expect(emitted).toEqual([]);
        confirm.and.returnValue(of(true));
        fixture.componentInstance.onListAction(remove, row);
        expect(emitted).toEqual([{action: "delete", rowKey: "one"}]);
    });
});
