import { TestBed } from "@angular/core/testing";
import { TranslateModule, TranslateService } from "@ngx-translate/core";
import { InlineTranslateLoader } from "./inline-translate-loader";
import { resolveModuleName, resolveSettingText } from "./setting-text";

describe("settings internationalization", () => {
    let translate: TranslateService;

    beforeEach(() => {
        TestBed.configureTestingModule({ imports: [TranslateModule.forRoot()] });
        translate = TestBed.inject(TranslateService);
        const loader = new InlineTranslateLoader();
        for (const language of ["en", "fr"]) {
            loader.getTranslation(language).subscribe(table => translate.setTranslation(language, table));
        }
        translate.use("en");
    });

    it("resolves translated keys and parameters in the selected language", () => {
        expect(resolveSettingText(translate, "common.itemsMany", { count: 3 })).toBe("3 items");
        translate.use("fr");
        expect(resolveSettingText(translate, "common.itemsMany", { count: 3 })).toBe("3 éléments");
    });

    it("preserves legacy literal labels, missing keys and data fallbacks", () => {
        expect(resolveSettingText(translate, "Legacy plugin label")).toBe("Legacy plugin label");
        expect(resolveSettingText(translate, "plugin.example.missing")).toBe("plugin.example.missing");
        expect(resolveSettingText(translate, null)).toBe("");
        expect(resolveModuleName(translate, "module.unknown", "Custom item")).toBe("Custom item");
    });

    it("falls back to English for an unavailable bundled language", () => {
        new InlineTranslateLoader().getTranslation("unknown").subscribe(table => {
            translate.setTranslation("unknown", table);
            translate.use("unknown");
            expect(resolveSettingText(translate, "common.cancel")).toBe("Cancel");
        });
    });
});
