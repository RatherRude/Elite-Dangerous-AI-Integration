import { Injectable } from "@angular/core";
import { TranslateService } from "@ngx-translate/core";
import { UISectionRequest } from "./ui.service";

@Injectable({ providedIn: "root" })
export class UISectionService {
    constructor(private readonly translate: TranslateService) {}

    private normalize(name: string): string {
        return name.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase()
            .replace(/[^\p{L}\p{N}]/gu, "");
    }

    private names(element: HTMLElement): string[] {
        const key = element.dataset["uiSection"];
        const names = [key, element.dataset["uiSectionId"], element.dataset["uiSectionLabel"], element.textContent?.trim() ?? ""]
            .filter((name): name is string => !!name);
        for (const translations of Object.values(this.translate.translations)) {
            if (!key) continue;
            const translated = this.translate.getParsedResult(translations, key);
            if (typeof translated === "string") names.push(translated);
        }
        return names;
    }

    apply(root: HTMLElement, request: UISectionRequest, render: () => void): { label: string; expanded: boolean } {
        if (typeof request.expanded !== "boolean"
            || (request.name === undefined) === (request.index === undefined)
            || (request.name !== undefined && (typeof request.name !== "string" || !this.normalize(request.name)))
            || (request.index !== undefined && (!Number.isInteger(request.index) || request.index < 1))) {
            throw new Error("Specify a section name or an integer index starting at 1.");
        }
        const controls = Array.from(root.querySelectorAll<HTMLElement>(
            "button[data-ui-section], mat-expansion-panel-header, details > summary",
        )).filter(element => {
            const parent = element.parentElement instanceof HTMLDetailsElement
                ? element.parentElement.parentElement : element.parentElement;
            return element.getClientRects().length > 0 && getComputedStyle(element).visibility !== "hidden"
                && !parent?.closest("details:not([open])")
                && !element.closest(".mat-mdc-tab-body:not(.mat-mdc-tab-body-active)")
                && !element.closest('[style*="display: none"], [hidden], [aria-hidden="true"]');
        });
        const matches = request.index !== undefined ? controls.slice(request.index - 1, request.index)
            : controls.filter(element => this.names(element).some(name =>
                this.normalize(name) === this.normalize(request.name!)));
        if (matches.length !== 1) {
            const names = controls.map((element, index) =>
                `${index + 1}: ${element.dataset["uiSectionLabel"] ?? element.textContent?.trim()}`).join("; ");
            throw new Error(`${matches.length ? "Ambiguous section" : "Section not found"}. Available sections: ${names || "none"}.`);
        }
        const control = matches[0];
        const details = control.parentElement instanceof HTMLDetailsElement ? control.parentElement : null;
        const expanded = details ? details.open : control.getAttribute("aria-expanded") === "true";
        if (!details && !control.hasAttribute("aria-expanded")) {
            throw new Error("This section does not expose its expanded state.");
        }
        if (expanded !== request.expanded) {
            if (details) details.open = request.expanded;
            else control.click();
            render();
        }
        const actual = details ? details.open : control.getAttribute("aria-expanded") === "true";
        if (actual !== request.expanded) throw new Error("The requested section did not change its expanded state.");
        return { label: control.dataset["uiSectionLabel"] ?? control.textContent?.trim() ?? "", expanded: actual };
    }
}
