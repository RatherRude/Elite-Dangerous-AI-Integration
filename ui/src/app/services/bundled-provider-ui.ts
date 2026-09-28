export type BundledVoiceCatalog = "openai" | "edge";

const OPENAI_TTS = "plugin:7f6f8e98-576f-4d1d-9d87-0f8f7f2f3c61:tts";
const EDGE_TTS = "plugin:e2d57ec0-56f5-45de-88ed-621d4a28d7b5:tts";

const voiceCatalogs: Partial<Record<string, BundledVoiceCatalog>> = {
    [OPENAI_TTS]: "openai",
    [EDGE_TTS]: "edge",
};

const defaultVoices: Partial<Record<string, string>> = {
    [OPENAI_TTS]: "nova",
    [EDGE_TTS]: "en-US-AvaMultilingualNeural",
};

export function bundledVoiceCatalog(providerRef: string | undefined): BundledVoiceCatalog | null {
    return providerRef ? voiceCatalogs[providerRef] ?? null : null;
}

export function bundledDefaultVoice(providerRef: string | undefined): string | null {
    return providerRef ? defaultVoices[providerRef] ?? null : null;
}
