import { Subject } from "rxjs";
import { ModelProviderDefinition } from "./plugin-settings";
import { BaseMessage, TauriService } from "./tauri.service";
import {
    PARAKEET_GUID,
    PARAKEET_PROVIDER,
    parakeetAvailable,
    VoiceActivationMessage,
    VoiceActivationService,
    voiceActivationPrivacy,
} from "./voice-activation.service";

export const parakeetProvider: ModelProviderDefinition = {
    plugin_guid: PARAKEET_GUID, id: "parakeet-stt", kind: "stt",
    label: "Parakeet (Local)", is_builtin: false, settings_config: [],
};

describe("voice activation provider selection", () => {
    it("requires a registered STT provider, not merely a matching plugin GUID", () => {
        expect(parakeetAvailable([])).toBeFalse();
        expect(parakeetAvailable([{ ...parakeetProvider, kind: "tts" }])).toBeFalse();
        expect(parakeetAvailable([parakeetProvider])).toBeTrue();
    });

    it("describes local, hybrid, main-only and missing-plugin privacy accurately", () => {
        expect(voiceActivationPrivacy({ stt_provider: PARAKEET_PROVIDER, wake_word_source: "main" }, []))
            .toBe("voice.local");
        expect(voiceActivationPrivacy({ stt_provider: PARAKEET_PROVIDER, wake_word_source: "parakeet" }, []))
            .toBe("voice.local");
        expect(voiceActivationPrivacy({ stt_provider: "remote", wake_word_source: "main" }, [parakeetProvider]))
            .toBe("voice.mainPrivacy");
        expect(voiceActivationPrivacy({ stt_provider: "remote", wake_word_source: "parakeet" }, [parakeetProvider]))
            .toBe("voice.hybrid");
        expect(voiceActivationPrivacy({ stt_provider: "remote", wake_word_source: "parakeet" }, []))
            .toBe("voice.fallback");
    });
});

describe("VoiceActivationService", () => {
    it("receives runtime snapshots and clears stale state on backend restart", () => {
        const output = new Subject<BaseMessage>();
        const tauri = jasmine.createSpyObj<TauriService>("TauriService", ["send_command"]);
        Object.defineProperty(tauri, "output$", { value: output });
        const service = new VoiceActivationService(tauri);
        const received: (VoiceActivationMessage | null)[] = [];
        service.state$.subscribe(state => received.push(state));
        const snapshot: VoiceActivationMessage = {
            type: "voice_activation", state: "active", name: "Simone", timestamp: "", index: 0,
        };
        output.next(snapshot);
        expect(received.at(-1)?.state).toBe("active");
        output.next({ type: "ready", timestamp: "", index: 1 });
        expect(received.at(-1)).toBeNull();
        const standby: VoiceActivationMessage = { ...snapshot, state: "standby" };
        output.next(standby);
        expect(received.at(-1)?.state).toBe("standby");
        output.next({ type: "backend_process_state", timestamp: "", index: 2 });
        expect(received.at(-1)).toBeNull();
    });
});
