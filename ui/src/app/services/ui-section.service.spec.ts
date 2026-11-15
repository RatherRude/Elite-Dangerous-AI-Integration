import { TestBed } from "@angular/core/testing";
import { TranslateModule, TranslateService } from "@ngx-translate/core";
import { UISectionService } from "./ui-section.service";
import { SettingsFieldComponent } from "../components/settings-field/settings-field.component";
import { SettingsGridComponent } from "../components/settings-grid/settings-grid.component";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";

describe("voice section expansion", () => {
    let root: HTMLElement;
    let service: UISectionService;

    beforeEach(() => {
        TestBed.configureTestingModule({imports: [
            TranslateModule.forRoot(), SettingsFieldComponent, SettingsGridComponent, NoopAnimationsModule,
        ]});
        const translate = TestBed.inject(TranslateService);
        translate.setTranslation("en", {category: {core: "Core Internal", weapons: "Hardpoints"}});
        translate.setTranslation("fr", {category: {core: "Compartiments essentiels", weapons: "Emplacements d'armes"}});
        translate.use("en");
        service = TestBed.inject(UISectionService);
        root = document.createElement("div");
        document.body.appendChild(root);
    });

    afterEach(() => root.remove());

    it("matches French names with an English GUI without changing plugin data", () => {
        const fixture = TestBed.createComponent(SettingsFieldComponent);
        const items = [
            {key: "core", title: "Power Plant", group: "category.core"},
            {key: "weapons", title: "Beam Laser", group: "category.weapons"},
        ];
        fixture.componentRef.setInput("field", {key: "modules", type: "list", items});
        fixture.detectChanges();
        const result = service.apply(fixture.nativeElement, {
            request_id: "collapse", expanded: false, name: "Compartiments essentiels",
        }, () => fixture.detectChanges());
        expect(result).toEqual({label: "Core Internal", expanded: false});
        expect(fixture.nativeElement.textContent).not.toContain("Power Plant");
        expect(fixture.nativeElement.textContent).toContain("Beam Laser");
        service.apply(fixture.nativeElement, {request_id: "expand", expanded: true, index: 1}, () => fixture.detectChanges());
        expect(fixture.nativeElement.textContent).toContain("Power Plant");
        expect(items.length).toBe(2);
    });

    it("indexes visible headers and ignores inactive tabs and children of closed parents", () => {
        root.innerHTML = `
            <div class="mat-mdc-tab-body" style="display:none"><details><summary>Inactive</summary></details></div>
            <div class="mat-mdc-tab-body-active">
                <details><summary>First</summary><details><summary>Hidden nested</summary></details></details>
                <details><summary data-ui-section="plan-2" data-ui-section-label="Second plan">Details</summary>Work</details>
            </div>`;
        service.apply(root, {request_id: "expand", expanded: true, index: 2}, () => {});
        const details = root.querySelector<HTMLDetailsElement>(".mat-mdc-tab-body-active > details:last-child")!;
        expect(details.open).toBeTrue();
        service.apply(root, {request_id: "collapse", expanded: false, name: "Second plan"}, () => {});
        expect(details.open).toBeFalse();
    });

    it("controls a real accordion and excludes hidden children until their parent is opened", async () => {
        const fixture = TestBed.createComponent(SettingsGridComponent);
        fixture.componentRef.setInput("grid", {
            key: "core-grid", label: "category.core", collapsible: true, default_collapsed: true,
            fields: [{key: "weapons", type: "list", items: [{key: "beam", title: "Beam Laser", group: "category.weapons"}]}],
        });
        fixture.detectChanges();
        await fixture.whenStable();
        const render = () => fixture.detectChanges();
        expect(() => service.apply(fixture.nativeElement, {
            request_id: "hidden", expanded: true, name: "Emplacements d'armes",
        }, render)).toThrowError(/Section not found/);
        service.apply(fixture.nativeElement, {request_id: "parent", expanded: true, name: "core-grid"}, render);
        await fixture.whenStable();
        render();
        service.apply(fixture.nativeElement, {request_id: "category", expanded: false, index: 2}, render);
        expect(fixture.nativeElement.textContent).not.toContain("Beam Laser");
        service.apply(fixture.nativeElement, {request_id: "parent", expanded: false, index: 1}, render);
        await fixture.whenStable();
        render();
        expect(fixture.nativeElement.querySelector("mat-expansion-panel-header").getAttribute("aria-expanded")).toBe("false");
    });

    it("keeps non-Latin section names distinct", () => {
        root.innerHTML = `<details><summary>\u8239\u4f53</summary></details>
            <details><summary>\u63a8\u8fdb\u5668</summary></details>`;
        service.apply(root, {request_id: "expand", expanded: true, name: "\u63a8\u8fdb\u5668"}, () => {});
        const details = root.querySelectorAll("details");
        expect(details[0].open).toBeFalse();
        expect(details[1].open).toBeTrue();
    });

    it("is idempotent and reports ambiguous, missing, invalid and rejected changes", () => {
        root.innerHTML = `<button data-ui-section="core" aria-expanded="true">Core</button>
            <details><summary>Core</summary></details>`;
        const button = root.querySelector("button")!;
        const click = spyOn(button, "click").and.callThrough();
        service.apply(root, {request_id: "same", expanded: true, index: 1}, () => {});
        expect(click).not.toHaveBeenCalled();
        expect(() => service.apply(root, {request_id: "ambiguous", expanded: false, name: "Core"}, () => {}))
            .toThrowError(/Ambiguous section/);
        expect(() => service.apply(root, {request_id: "missing", expanded: true, index: 3}, () => {}))
            .toThrowError(/Section not found/);
        expect(() => service.apply(root, {request_id: "invalid", expanded: true, index: 0}, () => {}))
            .toThrowError(/starting at 1/);
        expect(() => service.apply(root, JSON.parse('{"request_id":"invalid-name","expanded":true,"name":7}'), () => {}))
            .toThrowError(/starting at 1/);
        expect(() => service.apply(root, {request_id: "rejected", expanded: false, index: 1}, () => {}))
            .toThrowError(/did not change/);
    });
});
