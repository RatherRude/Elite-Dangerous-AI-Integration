import { Injectable } from "@angular/core";
import { BehaviorSubject } from "rxjs";
import { TranslateService } from "@ngx-translate/core";
import { TauriService } from "./tauri.service";
import { RegisteredUIView, PluginUIView } from "./plugin-ui";
import { TRANSLATIONS } from "./i18n-translations";

@Injectable({providedIn: "root"})
export class PluginUIService {
  private readonly viewsSubject = new BehaviorSubject<RegisteredUIView[]>([]);
  readonly views$ = this.viewsSubject.asObservable();
  private readonly pending = new Map<string, {resolve: (result: unknown) => void; reject: (error: Error) => void; timer: ReturnType<typeof setTimeout>}>();
  private sequence = 0;
  private languages = new Set<string>();

  constructor(private readonly tauri: TauriService, private readonly translate: TranslateService) {
    tauri.output$.subscribe(message => {
      if (message.type === "ready") {
        this.viewsSubject.next([]);
        for (const lang of this.languages) this.translate.setTranslation(lang, TRANSLATIONS[lang] ?? TRANSLATIONS['en']);
        this.languages.clear();
        for (const pending of this.pending.values()) {
          clearTimeout(pending.timer);
          pending.reject(new Error("common.actionError"));
        }
        this.pending.clear();
      } else if (message.type === "plugin_ui") {
        const views: RegisteredUIView[] = [];
        for (const lang of this.languages) this.translate.setTranslation(lang, TRANSLATIONS[lang] ?? TRANSLATIONS['en']);
        this.languages.clear();
        for (const [guid, contribution] of Object.entries(message["plugins"] ?? {}) as [string, {views: PluginUIView[]; translations: Record<string, object>}][]) {
          for (const [lang, translations] of Object.entries(contribution.translations)) {
            this.languages.add(lang);
            this.translate.setTranslation(lang, translations, true);
          }
          views.push(...contribution.views.map(view => ({...view, pluginGuid: guid, target: `plugin:${guid}:${view.id}`})));
        }
        this.viewsSubject.next(views.sort((a, b) => (a.order ?? 0) - (b.order ?? 0) || a.target.localeCompare(b.target)));
      } else if (message.type === "plugin_ui_result") {
        const pending = this.pending.get(message["request_id"]);
        if (!pending) return;
        clearTimeout(pending.timer);
        this.pending.delete(message["request_id"]);
        if (message["success"]) pending.resolve(message["result"]);
        else pending.reject(new Error(message["error"] || "common.actionError"));
      }
    });
  }

  invoke(pluginGuid: string, action: string, payload: Record<string, unknown> = {}): Promise<unknown> {
    const requestId = `plugin-ui-${++this.sequence}`;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(requestId);
        reject(new Error("common.actionError"));
      }, 120000);
      this.pending.set(requestId, {resolve, reject, timer});
      this.tauri.send_command({type: "plugin_ui_action", timestamp: new Date().toISOString(),
        request_id: requestId, plugin_guid: pluginGuid, action, payload}).catch(error => {
        clearTimeout(timer);
        this.pending.delete(requestId);
        reject(error);
      });
    });
  }
}
