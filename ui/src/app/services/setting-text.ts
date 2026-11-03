import { TranslateService } from "@ngx-translate/core";

/**
 * Pattern used to distinguish i18n keys from literal strings sent by plugins.
 * A key is dot-separated segments, e.g. "plugin.example.title". Segment
 * casing is not restricted so camelCase names resolve as well. Literal
 * labels do not match and are shown as-is.
 */
const I18N_KEY_PATTERN = /^[a-zA-Z][a-zA-Z0-9_-]*(?:\.[a-zA-Z0-9_-]+)+$/;

export function looksLikeI18nKey(value: string | null | undefined): boolean {
    return typeof value === "string" && I18N_KEY_PATTERN.test(value);
}

/**
 * Resolves a plugin-provided settings string.
 * Keys are translated; literal strings pass through untouched so plugins
 * that have not been migrated to i18n keep working.
 */
export function resolveSettingText(
    translate: TranslateService,
    value: string | null | undefined,
    params?: { [name: string]: string | number },
): string {
    if (!value) {
        return "";
    }
    if (!looksLikeI18nKey(value)) {
        return value;
    }
    const translated = translate.instant(value, params);
    return typeof translated === "string" ? translated : value;
}

/**
 * Resolves a module name key (e.g. "module.beamlaser") against the
 * translations; when the key is unknown the provided fallback (the humanized
 * backend name) is shown instead of the raw key.
 */
export function resolveModuleName(
    translate: TranslateService,
    key: string | null | undefined,
    fallback: string,
): string {
    if (!key) {
        return fallback;
    }
    const translated = translate.instant(key);
    return typeof translated === "string" && translated !== key ? translated : fallback;
}
