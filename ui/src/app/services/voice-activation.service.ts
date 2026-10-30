import { Injectable } from "@angular/core";
import { BehaviorSubject } from "rxjs";
import { Config } from "./config.service";
import { ModelProviderDefinition } from "./plugin-settings";
import { BaseMessage, TauriService } from "./tauri.service";

export const PARAKEET_GUID = "b77dec4f-8993-4213-8d44-caf902dabc6d";
export const PARAKEET_PROVIDER = `plugin:${PARAKEET_GUID}:parakeet-stt`;
export type VoiceActivationConfig = Pick<Config,
    "stt_provider" | "wake_word_timeout" | "wake_word_source" | "wake_word_first_command"
>;

export interface VoiceActivationMessage extends BaseMessage {
    type: "voice_activation";
    state: "disabled" | "preparing" | "standby" | "active" | "error";
    name: string;
    activation_provider?: string;
    warning?: string;
}

export function parakeetAvailable(providers: ModelProviderDefinition[]): boolean {
    return providers.some(provider =>
        provider.kind === "stt" && provider.plugin_guid === PARAKEET_GUID && provider.id === "parakeet-stt"
    );
}

export function voiceActivationPrivacy(config: Pick<VoiceActivationConfig, "stt_provider" | "wake_word_source">, providers: ModelProviderDefinition[]): string {
    if (config.stt_provider === PARAKEET_PROVIDER) return "voice.local";
    if (config.wake_word_source === "parakeet") {
        return parakeetAvailable(providers) ? "voice.hybrid" : "voice.fallback";
    }
    return "voice.mainPrivacy";
}

@Injectable({ providedIn: "root" })
export class VoiceActivationService {
    private readonly subject = new BehaviorSubject<VoiceActivationMessage | null>(null);
    readonly state$ = this.subject.asObservable();

    constructor(tauri: TauriService) {
        tauri.output$.subscribe(message => {
            if (this.isVoiceMessage(message)) {
                this.subject.next(message);
            } else if (["ready", "startup_error", "backend_process_state"].includes(message.type)) {
                this.subject.next(null);
            }
        });
    }

    private isVoiceMessage(message: BaseMessage): message is VoiceActivationMessage {
        return message.type === "voice_activation";
    }
}
