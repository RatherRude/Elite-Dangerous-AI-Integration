import { Injectable } from "@angular/core";
import { TranslateService } from "@ngx-translate/core";
import { TauriService } from "./tauri.service";
import { MatSnackBar } from "@angular/material/snack-bar";
import { resolveSettingText } from "./setting-text";

function isNotificationParams(value: unknown): value is Record<string, string | number> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    && Object.values(value).every(item => typeof item === "string" || typeof item === "number");
}

@Injectable({providedIn: "root"})
export class PluginUIService {
  private readonly pending = new Map<string, {resolve: (result: unknown) => void; reject: (error: Error) => void; timer: ReturnType<typeof setTimeout>}>();
  private states: Record<string, Record<string, unknown>> = {};
  private readonly edits = new Map<string, Map<string, {value: unknown}>>();

  constructor(private readonly tauri: TauriService, private readonly translate: TranslateService,
    private readonly snackBar: MatSnackBar) {
    tauri.output$.subscribe(message => {
      if (message.type === "ready") {
        this.states = {};
        this.edits.clear();
        for (const pending of this.pending.values()) {
          clearTimeout(pending.timer);
          pending.reject(new Error("common.actionError"));
        }
        this.pending.clear();
      } else if (message.type === "plugin_ui") {
        const states: Record<string, Record<string, unknown>> = {};
        for (const [guid, contribution] of Object.entries(message["plugins"] ?? {}) as [string, {state?: Record<string, unknown>}][]) {
          states[guid] = contribution.state ?? {};
        }
        this.states = states;
      } else if (message.type === "plugin_ui_result") {
        const pending = this.pending.get(message["request_id"]);
        if (!pending) return;
        clearTimeout(pending.timer);
        this.pending.delete(message["request_id"]);
        if (message["success"]) {
          this.notify(message["result"]);
          pending.resolve(message["result"]);
        }
        else pending.reject(new Error(message["error"] || "common.actionError"));
      }
    });
  }

  private notify(result: unknown): void {
    if (!result || typeof result !== "object" || !("notification" in result)) return;
    const params = "params" in result ? result.params : {};
    if (typeof result.notification !== "string" || !result.notification.trim() || !isNotificationParams(params)) {
      console.error("Invalid plugin action notification", result);
      this.snackBar.open(this.translate.instant("common.actionError"), undefined, {duration: 5000});
      return;
    }
    this.snackBar.open(resolveSettingText(this.translate, result.notification, params), undefined, {duration: 4000});
  }

  getValue(pluginGuid: string, key: string, fallback: unknown): unknown {
    const edit = this.edits.get(pluginGuid)?.get(key);
    if (edit) return edit.value;
    const state = this.states[pluginGuid];
    return state && Object.prototype.hasOwnProperty.call(state, key) ? state[key] : fallback;
  }

  async change(pluginGuid: string, key: string, value: unknown): Promise<void> {
    let edits = this.edits.get(pluginGuid);
    if (!edits) {
      edits = new Map();
      this.edits.set(pluginGuid, edits);
    }
    const edit = {value};
    edits.set(key, edit);
    try {
      await this.invoke(pluginGuid, "ui_changed", {key, value});
    } finally {
      if (edits.get(key) === edit) edits.delete(key);
      if (!edits.size && this.edits.get(pluginGuid) === edits) this.edits.delete(pluginGuid);
    }
  }

  invoke(pluginGuid: string, action: string, payload: Record<string, unknown> = {}): Promise<unknown> {
    const requestId = `plugin-ui-${crypto.randomUUID()}`;
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
