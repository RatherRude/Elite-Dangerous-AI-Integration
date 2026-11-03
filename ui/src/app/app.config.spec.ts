import { TestBed } from "@angular/core/testing";
import { TranslateLoader, TranslateModule, TranslateService } from "@ngx-translate/core";
import { initializeTranslations } from "./app.config";
import { InlineTranslateLoader } from "./services/inline-translate-loader";

describe("UI language initialization", () => {
    beforeEach(() => {
        TestBed.configureTestingModule({
            imports: [TranslateModule.forRoot({
                loader: { provide: TranslateLoader, useClass: InlineTranslateLoader },
            })],
        });
    });

    for (const [locale, label] of [
        ["fr-FR", "Veille"], ["fr-CA", "Veille"], ["en-GB", "Standby"], ["de-DE", "Standby"],
    ]) {
        it(`uses the supported UI language for ${locale}`, async () => {
            spyOnProperty(navigator, "language", "get").and.returnValue(locale);
            const translate = TestBed.inject(TranslateService);
            await initializeTranslations(translate)();
            expect(translate.instant("voice.state.standby")).toBe(label);
        });
    }
});
