import { TranslateLoader } from "@ngx-translate/core";
import { Observable, of } from "rxjs";

import { TRANSLATIONS } from "./i18n-translations";

/** Serves the bundled translation tables without an HTTP round-trip. */
export class InlineTranslateLoader implements TranslateLoader {
    getTranslation(lang: string): Observable<object> {
        return of(
            (TRANSLATIONS as Record<string, object>)[lang] ??
                (TRANSLATIONS as Record<string, object>)["en"],
        );
    }
}
