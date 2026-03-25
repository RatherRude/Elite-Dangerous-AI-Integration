import { Component } from "@angular/core";
import { CommonModule } from "@angular/common";
import {
    MatFormField,
    MatFormFieldModule,
    MatLabel,
} from "@angular/material/form-field";
import { MatIcon } from "@angular/material/icon";
import { MatOptgroup, MatOption, MatSelect } from "@angular/material/select";
import { Subscription } from "rxjs";
import {
    Config,
    ConfigService,
} from "../../services/config.service.js";
import { MatSnackBar } from "@angular/material/snack-bar";
import { FormsModule } from "@angular/forms";
import { ConfirmationDialogService } from "../../services/confirmation-dialog.service.js";
import { MatDialog } from "@angular/material/dialog";
import { EdgeTtsVoicesDialogComponent } from "../edge-tts-voices-dialog/edge-tts-voices-dialog.component.js";
import { ConfirmationDialogComponent } from "../confirmation-dialog/confirmation-dialog.component.js";
import { AvatarCatalogDialogComponent, AvatarCatalogResult } from "../avatar-catalog-dialog/avatar-catalog-dialog.component.js";
import { MatTooltipModule } from "@angular/material/tooltip";
import { MatDivider } from "@angular/material/divider";
import { MatInputModule } from "@angular/material/input";
import { MatButtonModule } from "@angular/material/button";
import {
    CharacterService,
    ConfigWithCharacters,
    Character,
    CharacterTTSFilterConfig,
    CharacterTTSDistortionConfig,
    CharacterTTSChorusConfig,
    CharacterTTSReverbConfig,
    CharacterTTSGlitchConfig,
    CharacterTTSTimePitchConfig,
    CharacterTTSEffectsConfig,
    CharacterTTSPostprocessingConfig,
} from "../../services/character.service";
import { MatCheckboxModule } from "@angular/material/checkbox";
import { CharacterPresets } from "./character-presets";

interface PromptSettings {
    // Existing settings
    verbosity: number;
    tone: "serious" | "humorous" | "sarcastic";
    knowledge: {
        popCulture: boolean;
        scifi: boolean;
        history: boolean;
    };
    characterInspiration: string;
    vulgarity: number;

    // New settings
    empathy: number;
    formality: number;
    confidence: number;
    // Replacing culture with D&D alignment
    ethicalAlignment: "lawful" | "neutral" | "chaotic";
    moralAlignment: "good" | "neutral" | "evil";
}

type VoiceEffectPresetKey = "distortion" | "chorus" | "reverb" | "glitch" | "time_pitch";
type VoiceEffectConfig =
    | CharacterTTSDistortionConfig
    | CharacterTTSChorusConfig
    | CharacterTTSReverbConfig
    | CharacterTTSGlitchConfig
    | CharacterTTSTimePitchConfig;

interface VoiceEffectPresetOption<TConfig extends VoiceEffectConfig> {
    id: string;
    label: string;
    config: TConfig | null;
}

interface LowHighPassPresetOption {
    id: string;
    label: string;
    lowpass: CharacterTTSFilterConfig | null;
    highpass: CharacterTTSFilterConfig | null;
}

@Component({
    selector: "app-character-settings",
    standalone: true,
    imports: [
        CommonModule,
        MatInputModule,
        MatFormFieldModule,
        FormsModule,
        MatButtonModule,
        MatCheckboxModule,
        MatFormField,
        MatLabel,
        MatIcon,
        MatSelect,
        MatOption,
        MatDivider,
        MatOptgroup,
        MatTooltipModule,
    ],
    templateUrl: "./character-settings.component.html",
    styleUrl: "./character-settings.component.scss",
})
export class CharacterSettingsComponent {
    config: ConfigWithCharacters | null = null;
    configSubscription: Subscription;
    characterSubscription: Subscription;
    private avatarMimeSubscription: Subscription;
    activeCharacter: Character | null = null;
    selectedCharacterIndex: number | null = null;
    editMode = false;
    showVoiceMoreSettings = false;
    initializing: boolean = true;
    /** Primary MIME from CharacterService (blob avatars); null when no file or unknown. */
    private avatarMimePrimary: string | null = null;
    private localCharacterCopy: Character | null = null;
    isApplyingChange: boolean = false;
    voiceInstructionSupportedModels: string[] = this.characterService.voiceInstructionSupportedModels;
    readonly lowHighPassPresets: LowHighPassPresetOption[] = [
        { id: "off", label: "Off", lowpass: null, highpass: null },
        {
            id: "subtle-comms",
            label: "Subtle Comms",
            lowpass: { enabled: true, cutoff: 8000 },
            highpass: { enabled: true, cutoff: 120 },
        },
        {
            id: "cockpit-intercom",
            label: "Cockpit Intercom",
            lowpass: { enabled: true, cutoff: 6200 },
            highpass: { enabled: true, cutoff: 180 },
        },
        {
            id: "helmet-radio",
            label: "Helmet Radio",
            lowpass: { enabled: true, cutoff: 4300 },
            highpass: { enabled: true, cutoff: 260 },
        },
        {
            id: "ship-pa",
            label: "Ship PA",
            lowpass: { enabled: true, cutoff: 5200 },
            highpass: { enabled: true, cutoff: 220 },
        },
        {
            id: "tactical-uplink",
            label: "Tactical Uplink",
            lowpass: { enabled: true, cutoff: 5600 },
            highpass: { enabled: true, cutoff: 320 },
        },
        {
            id: "walkie-talkie",
            label: "Walkie Talkie",
            lowpass: { enabled: true, cutoff: 3000 },
            highpass: { enabled: true, cutoff: 420 },
        },
        {
            id: "tinny-speaker",
            label: "Tinny Speaker",
            lowpass: { enabled: true, cutoff: 3600 },
            highpass: { enabled: true, cutoff: 520 },
        },
        {
            id: "surveillance-mic",
            label: "Surveillance Mic",
            lowpass: { enabled: true, cutoff: 2700 },
            highpass: { enabled: true, cutoff: 380 },
        },
        {
            id: "emergency-broadcast",
            label: "Emergency Broadcast",
            lowpass: { enabled: true, cutoff: 4100 },
            highpass: { enabled: true, cutoff: 460 },
        },
        {
            id: "distress-beacon",
            label: "Distress Beacon",
            lowpass: { enabled: true, cutoff: 2500 },
            highpass: { enabled: true, cutoff: 560 },
        },
        {
            id: "old-analog-radio",
            label: "Old Analog Radio",
            lowpass: { enabled: true, cutoff: 2400 },
            highpass: { enabled: true, cutoff: 320 },
        },
        {
            id: "encrypted-channel",
            label: "Encrypted Channel",
            lowpass: { enabled: true, cutoff: 3100 },
            highpass: { enabled: true, cutoff: 650 },
        },
        {
            id: "remote-drone-feed",
            label: "Remote Drone Feed",
            lowpass: { enabled: true, cutoff: 3700 },
            highpass: { enabled: true, cutoff: 760 },
        },
        {
            id: "station-announcement",
            label: "Station Announcement",
            lowpass: { enabled: true, cutoff: 6500 },
            highpass: { enabled: true, cutoff: 140 },
        },
    ];
    readonly distortionPresets: VoiceEffectPresetOption<CharacterTTSDistortionConfig>[] = [
        { id: "off", label: "Off", config: null },
        {
            id: "subtle-warmth",
            label: "Subtle Warmth",
            config: { enabled: true, drive: 1.1, clip: 0.98, mode: "tanh" },
        },
        {
            id: "soft-grit",
            label: "Soft Grit",
            config: { enabled: true, drive: 1.35, clip: 0.92, mode: "tanh" },
        },
        {
            id: "light-crunch",
            label: "Light Crunch",
            config: { enabled: true, drive: 1.8, clip: 0.82, mode: "tanh" },
        },
        {
            id: "crunch",
            label: "Crunch",
            config: { enabled: true, drive: 2.4, clip: 0.72, mode: "hard" },
        },
        {
            id: "harsh",
            label: "Harsh",
            config: { enabled: true, drive: 2.9, clip: 0.62, mode: "hard" },
        },
        {
            id: "clipped",
            label: "Clipped",
            config: { enabled: true, drive: 3.3, clip: 0.52, mode: "hard" },
        },
        {
            id: "broken-speaker",
            label: "Broken Speaker",
            config: { enabled: true, drive: 3.8, clip: 0.45, mode: "hard" },
        },
        {
            id: "overloaded",
            label: "Overloaded",
            config: { enabled: true, drive: 4.4, clip: 0.38, mode: "hard" },
        },
    ];
    readonly chorusPresets: VoiceEffectPresetOption<CharacterTTSChorusConfig>[] = [
        { id: "off", label: "Off", config: null },
        {
            id: "subtle-width",
            label: "Subtle Width",
            config: { enabled: true, delay_ms: 16, depth_ms: 3, rate_hz: 0.12, mix: 0.1 },
        },
        {
            id: "soft-double",
            label: "Soft Double",
            config: { enabled: true, delay_ms: 20, depth_ms: 5, rate_hz: 0.18, mix: 0.18 },
        },
        {
            id: "double",
            label: "Double",
            config: { enabled: true, delay_ms: 24, depth_ms: 8, rate_hz: 0.24, mix: 0.28 },
        },
        {
            id: "shimmer",
            label: "Shimmer",
            config: { enabled: true, delay_ms: 18, depth_ms: 9, rate_hz: 0.42, mix: 0.22 },
        },
        {
            id: "hologram",
            label: "Hologram",
            config: { enabled: true, delay_ms: 22, depth_ms: 11, rate_hz: 0.32, mix: 0.35 },
        },
        {
            id: "dreamlike",
            label: "Dreamlike",
            config: { enabled: true, delay_ms: 28, depth_ms: 14, rate_hz: 0.2, mix: 0.4 },
        },
        {
            id: "alien-resonance",
            label: "Alien Resonance",
            config: { enabled: true, delay_ms: 32, depth_ms: 18, rate_hz: 0.48, mix: 0.5 },
        },
    ];
    readonly reverbPresets: VoiceEffectPresetOption<CharacterTTSReverbConfig>[] = [
        { id: "off", label: "Off", config: null },
        {
            id: "studio-booth",
            label: "Studio Booth",
            config: { enabled: true, mix: 0.08, tail: 0.08 },
        },
        {
            id: "small-room",
            label: "Small Room",
            config: { enabled: true, mix: 0.12, tail: 0.12 },
        },
        {
            id: "control-room",
            label: "Control Room",
            config: { enabled: true, mix: 0.14, tail: 0.16 },
        },
        {
            id: "hallway",
            label: "Hallway",
            config: { enabled: true, mix: 0.18, tail: 0.24 },
        },
        {
            id: "metal-corridor",
            label: "Metal Corridor",
            config: { enabled: true, mix: 0.22, tail: 0.28 },
        },
        {
            id: "cockpit-cabin",
            label: "Cockpit Cabin",
            config: { enabled: true, mix: 0.16, tail: 0.18 },
        },
        {
            id: "cargo-bay",
            label: "Cargo Bay",
            config: { enabled: true, mix: 0.26, tail: 0.34 },
        },
        {
            id: "station-concourse",
            label: "Station Concourse",
            config: { enabled: true, mix: 0.3, tail: 0.4 },
        },
        {
            id: "ship-hangar",
            label: "Ship Hangar",
            config: { enabled: true, mix: 0.34, tail: 0.46 },
        },
        {
            id: "cathedral",
            label: "Cathedral",
            config: { enabled: true, mix: 0.38, tail: 0.5 },
        },
        {
            id: "cave",
            label: "Cave",
            config: { enabled: true, mix: 0.42, tail: 0.5 },
        },
        {
            id: "distant-pa",
            label: "Distant PA",
            config: { enabled: true, mix: 0.28, tail: 0.3 },
        },
        {
            id: "dream-space",
            label: "Dream Space",
            config: { enabled: true, mix: 0.32, tail: 0.44 },
        },
    ];
    readonly glitchPresets: VoiceEffectPresetOption<CharacterTTSGlitchConfig>[] = [
        { id: "off", label: "Off", config: null },
        {
            id: "minor-dropouts",
            label: "Minor Dropouts",
            config: { enabled: true, probability: 0.03, repeat_min: 2, repeat_max: 2, detune_base: 0.5, detune_peak: 2.0 },
        },
        {
            id: "packet-loss",
            label: "Packet Loss",
            config: { enabled: true, probability: 0.06, repeat_min: 2, repeat_max: 3, detune_base: 1.0, detune_peak: 4.0 },
        },
        {
            id: "signal-jitter",
            label: "Signal Jitter",
            config: { enabled: true, probability: 0.08, min_seconds: 0.03, max_seconds: 0.08, detune_base: 1.5, detune_peak: 4.5 },
        },
        {
            id: "stutter",
            label: "Stutter",
            config: { enabled: true, probability: 0.1, repeat_min: 2, repeat_max: 4, detune_base: 0.75, detune_peak: 3.0 },
        },
        {
            id: "fragment-repeats",
            label: "Fragment Repeats",
            config: { enabled: true, probability: 0.12, min_seconds: 0.04, max_seconds: 0.1, detune_base: 1.5, detune_peak: 5.0 },
        },
        {
            id: "pitch-drift",
            label: "Pitch Drift",
            config: { enabled: true, probability: 0.11, min_seconds: 0.06, max_seconds: 0.14, detune_base: 2.5, detune_peak: 6.5 },
        },
        {
            id: "corrupted-signal",
            label: "Corrupted Signal",
            config: { enabled: true, probability: 0.15, repeat_min: 2, repeat_max: 4, min_seconds: 0.05, max_seconds: 0.14, detune_base: 3.0, detune_peak: 8.0 },
        },
        {
            id: "broken-broadcast",
            label: "Broken Broadcast",
            config: { enabled: true, probability: 0.18, repeat_min: 3, repeat_max: 5, min_seconds: 0.06, max_seconds: 0.18, detune_base: 3.5, detune_peak: 10.0 },
        },
        {
            id: "severe-malfunction",
            label: "Severe Malfunction",
            config: { enabled: true, probability: 0.22, repeat_min: 3, repeat_max: 6, min_seconds: 0.08, max_seconds: 0.2, detune_base: 4.0, detune_peak: 12.0 },
        },
    ];
    readonly timePitchPresets: VoiceEffectPresetOption<CharacterTTSTimePitchConfig>[] = [
        { id: "natural", label: "Natural", config: null },
        {
            id: "slightly-deeper",
            label: "Slightly Deeper",
            config: { enabled: true, pitch_shift_semitones: -2.0, time_stretch: 1.0 },
        },
        {
            id: "deep",
            label: "Deep",
            config: { enabled: true, pitch_shift_semitones: -4.0, time_stretch: 1.0 },
        },
        {
            id: "very-deep",
            label: "Very Deep",
            config: { enabled: true, pitch_shift_semitones: -6.0, time_stretch: 1.0 },
        },
        {
            id: "slightly-higher",
            label: "Slightly Higher",
            config: { enabled: true, pitch_shift_semitones: 1.5, time_stretch: 1.0 },
        },
        {
            id: "high",
            label: "High",
            config: { enabled: true, pitch_shift_semitones: 3.5, time_stretch: 1.0 },
        },
        {
            id: "slow-and-heavy",
            label: "Slow and Heavy",
            config: { enabled: true, pitch_shift_semitones: 0.0, time_stretch: 1.14 },
        },
        {
            id: "slow-and-deep",
            label: "Slow and Deep",
            config: { enabled: true, pitch_shift_semitones: -3.0, time_stretch: 1.12 },
        },
        {
            id: "fast-and-tight",
            label: "Fast and Tight",
            config: { enabled: true, pitch_shift_semitones: 0.0, time_stretch: 0.92 },
        },
        {
            id: "fast-and-nervous",
            label: "Fast and Nervous",
            config: { enabled: true, pitch_shift_semitones: 2.0, time_stretch: 0.9 },
        },
    ];

    edgeTtsVoices = [
        // English voices - US
        {
            value: "en-US-AvaMultilingualNeural",
            label: "Ava Multilingual (Female)",
            locale: "en-US",
        },
        {
            value: "en-US-AndrewMultilingualNeural",
            label: "Andrew Multilingual (Male)",
            locale: "en-US",
        },
        {
            value: "en-US-EmmaMultilingualNeural",
            label: "Emma Multilingual (Female)",
            locale: "en-US",
        },
        {
            value: "en-US-BrianMultilingualNeural",
            label: "Brian Multilingual (Male)",
            locale: "en-US",
        },
        {
            value: "en-US-JennyMultilingualNeural",
            label: "Jenny Multilingual (Female)",
            locale: "en-US",
        },
        {
            value: "en-US-RyanMultilingualNeural",
            label: "Ryan Multilingual (Male)",
            locale: "en-US",
        },
        {
            value: "en-US-EvelynMultilingualNeural",
            label: "Evelyn Multilingual (Female)",
            locale: "en-US",
        },
        {
            value: "en-US-AriaNeural",
            label: "Aria (Female) - Positive, Confident",
            locale: "en-US",
        },
        {
            value: "en-US-AnaNeural",
            label: "Ana (Female) - Cute",
            locale: "en-US",
        },
        {
            value: "en-US-ChristopherNeural",
            label: "Christopher (Male) - Reliable, Authority",
            locale: "en-US",
        },
        {
            value: "en-US-EricNeural",
            label: "Eric (Male) - Rational",
            locale: "en-US",
        },
        {
            value: "en-US-GuyNeural",
            label: "Guy (Male) - Passion",
            locale: "en-US",
        },
        {
            value: "en-US-JennyNeural",
            label: "Jenny (Female) - Friendly, Considerate",
            locale: "en-US",
        },
        {
            value: "en-US-MichelleNeural",
            label: "Michelle (Female) - Friendly, Pleasant",
            locale: "en-US",
        },
        {
            value: "en-US-RogerNeural",
            label: "Roger (Male) - Lively",
            locale: "en-US",
        },
        {
            value: "en-US-SteffanNeural",
            label: "Steffan (Male) - Rational",
            locale: "en-US",
        },

        // English voices - UK
        {
            value: "en-GB-LibbyNeural",
            label: "Libby (Female)",
            locale: "en-GB",
        },
        {
            value: "en-GB-MaisieNeural",
            label: "Maisie (Female)",
            locale: "en-GB",
        },
        { value: "en-GB-RyanNeural", label: "Ryan (Male)", locale: "en-GB" },
        {
            value: "en-GB-SoniaNeural",
            label: "Sonia (Female)",
            locale: "en-GB",
        },
        {
            value: "en-GB-ThomasNeural",
            label: "Thomas (Male)",
            locale: "en-GB",
        },

        // English voices - Australia
        {
            value: "en-AU-NatashaNeural",
            label: "Natasha (Female)",
            locale: "en-AU",
        },
        {
            value: "en-AU-WilliamNeural",
            label: "William (Male)",
            locale: "en-AU",
        },
        {
            value: "en-CA-ClaraNeural",
            label: "Clara (Female)",
            locale: "en-CA",
        },
        { value: "en-CA-LiamNeural", label: "Liam (Male)", locale: "en-CA" },
        {
            value: "en-IE-ConnorNeural",
            label: "Connor (Male)",
            locale: "en-IE",
        },
        {
            value: "en-IE-EmilyNeural",
            label: "Emily (Female)",
            locale: "en-IE",
        },
        {
            value: "en-IN-NeerjaNeural",
            label: "Neerja (Female)",
            locale: "en-IN",
        },
        {
            value: "en-IN-PrabhatNeural",
            label: "Prabhat (Male)",
            locale: "en-IN",
        },
        {
            value: "en-NZ-MitchellNeural",
            label: "Mitchell (Male)",
            locale: "en-NZ",
        },
        {
            value: "en-NZ-MollyNeural",
            label: "Molly (Female)",
            locale: "en-NZ",
        },
        { value: "en-ZA-LeahNeural", label: "Leah (Female)", locale: "en-ZA" },
        { value: "en-ZA-LukeNeural", label: "Luke (Male)", locale: "en-ZA" },

        // French voices
        {
            value: "fr-FR-VivienneMultilingualNeural",
            label: "Vivienne Multilingual (Female)",
            locale: "fr-FR",
        },
        {
            value: "fr-FR-RemyMultilingualNeural",
            label: "Remy Multilingual (Male)",
            locale: "fr-FR",
        },
        {
            value: "fr-FR-LucienMultilingualNeural",
            label: "Lucien Multilingual (Male)",
            locale: "fr-FR",
        },
        {
            value: "fr-FR-DeniseNeural",
            label: "Denise (Female)",
            locale: "fr-FR",
        },
        {
            value: "fr-FR-EloiseNeural",
            label: "Eloise (Female)",
            locale: "fr-FR",
        },
        { value: "fr-FR-HenriNeural", label: "Henri (Male)", locale: "fr-FR" },
        {
            value: "fr-CA-AntoineNeural",
            label: "Antoine (Male)",
            locale: "fr-CA",
        },
        { value: "fr-CA-JeanNeural", label: "Jean (Male)", locale: "fr-CA" },
        {
            value: "fr-CA-SylvieNeural",
            label: "Sylvie (Female)",
            locale: "fr-CA",
        },

        // German voices
        {
            value: "de-DE-SeraphinaMultilingualNeural",
            label: "Seraphina Multilingual (Female)",
            locale: "de-DE",
        },
        {
            value: "de-DE-FlorianMultilingualNeural",
            label: "Florian Multilingual (Male)",
            locale: "de-DE",
        },
        {
            value: "de-DE-AmalaNeural",
            label: "Amala (Female)",
            locale: "de-DE",
        },
        {
            value: "de-DE-ConradNeural",
            label: "Conrad (Male)",
            locale: "de-DE",
        },
        {
            value: "de-DE-KatjaNeural",
            label: "Katja (Female)",
            locale: "de-DE",
        },
        {
            value: "de-DE-KillianNeural",
            label: "Killian (Male)",
            locale: "de-DE",
        },

        // Spanish voices
        {
            value: "es-ES-ArabellaMultilingualNeural",
            label: "Arabella Multilingual (Female)",
            locale: "es-ES",
        },
        {
            value: "es-ES-IsidoraMultilingualNeural",
            label: "Isidora Multilingual (Female)",
            locale: "es-ES",
        },
        {
            value: "es-ES-TristanMultilingualNeural",
            label: "Tristan Multilingual (Male)",
            locale: "es-ES",
        },
        {
            value: "es-ES-XimenaMultilingualNeural",
            label: "Ximena Multilingual (Female)",
            locale: "es-ES",
        },
        {
            value: "es-ES-AlvaroNeural",
            label: "Alvaro (Male)",
            locale: "es-ES",
        },
        {
            value: "es-ES-ElviraNeural",
            label: "Elvira (Female)",
            locale: "es-ES",
        },
        {
            value: "es-MX-DaliaNeural",
            label: "Dalia (Female)",
            locale: "es-MX",
        },
        { value: "es-MX-JorgeNeural", label: "Jorge (Male)", locale: "es-MX" },

        // Russian voices
        {
            value: "ru-RU-DmitryNeural",
            label: "Dmitry (Male)",
            locale: "ru-RU",
        },
        {
            value: "ru-RU-SvetlanaNeural",
            label: "Svetlana (Female)",
            locale: "ru-RU",
        },

        // Italian voices
        {
            value: "it-IT-AlessioMultilingualNeural",
            label: "Alessio Multilingual (Male)",
            locale: "it-IT",
        },
        {
            value: "it-IT-IsabellaMultilingualNeural",
            label: "Isabella Multilingual (Female)",
            locale: "it-IT",
        },
        {
            value: "it-IT-GiuseppeMultilingualNeural",
            label: "Giuseppe Multilingual (Male)",
            locale: "it-IT",
        },
        {
            value: "it-IT-MarcelloMultilingualNeural",
            label: "Marcello Multilingual (Male)",
            locale: "it-IT",
        },
        { value: "it-IT-DiegoNeural", label: "Diego (Male)", locale: "it-IT" },
        { value: "it-IT-ElsaNeural", label: "Elsa (Female)", locale: "it-IT" },
        {
            value: "it-IT-IsabellaNeural",
            label: "Isabella (Female)",
            locale: "it-IT",
        },

        // Japanese voices
        { value: "ja-JP-KeitaNeural", label: "Keita (Male)", locale: "ja-JP" },
        {
            value: "ja-JP-NanamiNeural",
            label: "Nanami (Female)",
            locale: "ja-JP",
        },

        // Portuguese voices
        {
            value: "pt-BR-MacerioMultilingualNeural",
            label: "Macerio Multilingual (Male)",
            locale: "pt-BR",
        },
        {
            value: "pt-BR-ThalitaMultilingualNeural",
            label: "Thalita Multilingual (Female)",
            locale: "pt-BR",
        },
        {
            value: "pt-BR-AntonioNeural",
            label: "Antonio (Male)",
            locale: "pt-BR",
        },
        {
            value: "pt-BR-FranciscaNeural",
            label: "Francisca (Female)",
            locale: "pt-BR",
        },
        {
            value: "pt-PT-DuarteNeural",
            label: "Duarte (Male)",
            locale: "pt-PT",
        },
        {
            value: "pt-PT-RaquelNeural",
            label: "Raquel (Female)",
            locale: "pt-PT",
        },

        // Chinese voices
        {
            value: "zh-CN-XiaoxiaoMultilingualNeural",
            label: "Xiaoxiao Multilingual (Female)",
            locale: "zh-CN",
        },
        {
            value: "zh-CN-XiaochenMultilingualNeural",
            label: "Xiaochen Multilingual (Female)",
            locale: "zh-CN",
        },
        {
            value: "zh-CN-XiaoyuMultilingualNeural",
            label: "Xiaoyu Multilingual (Female)",
            locale: "zh-CN",
        },
        {
            value: "zh-CN-YunyiMultilingualNeural",
            label: "Yunyi Multilingual (Female)",
            locale: "zh-CN",
        },
        {
            value: "zh-CN-YunfanMultilingualNeural",
            label: "Yunfan Multilingual (Male)",
            locale: "zh-CN",
        },
        {
            value: "zh-CN-YunxiaoMultilingualNeural",
            label: "Yunxiao Multilingual (Male)",
            locale: "zh-CN",
        },
        {
            value: "zh-CN-XiaoxiaoNeural",
            label: "Xiaoxiao (Female) - Warm",
            locale: "zh-CN",
        },
        {
            value: "zh-CN-YunyangNeural",
            label: "Yunyang (Male) - Professional",
            locale: "zh-CN",
        },
        {
            value: "zh-TW-HsiaoChenNeural",
            label: "HsiaoChen (Female)",
            locale: "zh-TW",
        },
        {
            value: "zh-TW-YunJheNeural",
            label: "YunJhe (Male)",
            locale: "zh-TW",
        },

        // Arabic voices
        { value: "ar-SA-HamedNeural", label: "Hamed (Male)", locale: "ar-SA" },
        {
            value: "ar-SA-ZariyahNeural",
            label: "Zariyah (Female)",
            locale: "ar-SA",
        },

        // Hindi voices
        {
            value: "hi-IN-MadhurNeural",
            label: "Madhur (Male)",
            locale: "hi-IN",
        },
        {
            value: "hi-IN-SwaraNeural",
            label: "Swara (Female)",
            locale: "hi-IN",
        },

        // Korean voices
        {
            value: "ko-KR-HyunsuMultilingualNeural",
            label: "Hyunsu Multilingual (Male)",
            locale: "ko-KR",
        },
        {
            value: "ko-KR-InJoonNeural",
            label: "InJoon (Male)",
            locale: "ko-KR",
        },
        {
            value: "ko-KR-SunHiNeural",
            label: "SunHi (Female)",
            locale: "ko-KR",
        },
    ];

    constructor(
        private configService: ConfigService,
        private characterService: CharacterService,
        private snackBar: MatSnackBar,
        private confirmationDialog: ConfirmationDialogService,
        private dialog: MatDialog,
    ) {
        this.configSubscription = this.configService.config$.subscribe(
            (config) => {
                this.config = config as ConfigWithCharacters;
                this.selectedCharacterIndex = config?.active_character_index ?? null;
            },
        );
        this.characterSubscription = this.characterService.character$.subscribe(
            (character) => {
                this.activeCharacter = character;
            }
        );
        this.avatarMimeSubscription = this.characterService.avatarMime$.subscribe(
            (mime) => {
                this.avatarMimePrimary = mime;
            },
        );
    }
    ngOnDestroy() {
        // Unsubscribe from the config observable to prevent memory leaks
        if (this.configSubscription) {
            this.configSubscription.unsubscribe();
        }
        if (this.characterSubscription) {
            this.characterSubscription.unsubscribe();
        }
        if (this.avatarMimeSubscription) {
            this.avatarMimeSubscription.unsubscribe();
        }
    }

    /** PNG/WebP sprite sheet preview uses 200% + clip; SVG is one graphic. */
    get avatarPreviewUsesSpriteSheet(): boolean {
        if (!this.activeCharacter?.avatar) {
            return true;
        }
        const mime = this.avatarMimePrimary;
        if (!mime) {
            return true;
        }
        const primary = mime.trim().toLowerCase().split(";")[0]?.trim() ?? "";
        return primary !== "image/svg+xml";
    }

    // Modify applySettingsFromPreset to work with the new approach
    applySettingsFromPreset(preset: string): void {
        if (!this.activeCharacter) return;
        if (!this.selectedCharacterIndex) return;
        console.log("Applying settings from preset:", preset);

        const changes = CharacterPresets[preset];
        
        const newChar: Character = {
            ...this.activeCharacter,
            ...changes,
            personality_preset: preset,
        };

        console.log('newChar', newChar)

        newChar.character = this.buildCharacterPrompt(newChar);

        this.characterService.updateCharacter(this.selectedCharacterIndex, newChar)
    }

    
    public async setCharacterProperty<T extends keyof Character>(
        propName: T,
        value: Character[T],
    ): Promise<void> {
        return this.characterService.setCharacterProperty(propName, value);
    }

    getSelectedLowHighPassPreset(): string {
        const effects = this.activeCharacter?.tts_postprocessing?.effects;
        for (const preset of this.lowHighPassPresets) {
            if (
                this.effectConfigsMatch(effects?.lowpass, preset.lowpass)
                && this.effectConfigsMatch(effects?.highpass, preset.highpass)
            ) {
                return preset.id;
            }
        }
        return this.hasEnabledEffect(effects?.lowpass) || this.hasEnabledEffect(effects?.highpass)
            ? "custom"
            : "off";
    }

    getSelectedVoiceEffectPreset(effectKey: VoiceEffectPresetKey): string {
        const actualConfig = this.activeCharacter?.tts_postprocessing?.effects?.[effectKey];
        const presets = this.getVoiceEffectPresets(effectKey);
        for (const preset of presets) {
            if (this.effectConfigsMatch(actualConfig, this.getNormalizedPresetConfig(effectKey, preset.config))) {
                return preset.id;
            }
        }
        return this.hasEnabledEffect(actualConfig)
            ? "custom"
            : this.getDefaultVoiceEffectPresetId(effectKey);
    }

    async applyLowHighPassPreset(presetId: string): Promise<void> {
        const preset = this.lowHighPassPresets.find((option) => option.id === presetId);
        if (!preset) return;

        await this.updateVoiceEffects((effects) => {
            if (preset.lowpass) {
                effects.lowpass = structuredClone(preset.lowpass);
            } else {
                delete effects.lowpass;
            }

            if (preset.highpass) {
                effects.highpass = structuredClone(preset.highpass);
            } else {
                delete effects.highpass;
            }
        });
    }

    async applyVoiceEffectPreset(
        effectKey: VoiceEffectPresetKey,
        presetId: string,
    ): Promise<void> {
        const preset = this.getVoiceEffectPresets(effectKey).find((option) => option.id === presetId);
        if (!preset) return;

        await this.updateVoiceEffects((effects) => {
            switch (effectKey) {
                case "distortion":
                    if (preset.config) {
                        effects.distortion = structuredClone(preset.config as CharacterTTSDistortionConfig);
                    } else {
                        delete effects.distortion;
                    }
                    break;
                case "chorus":
                    if (preset.config) {
                        effects.chorus = structuredClone(preset.config as CharacterTTSChorusConfig);
                    } else {
                        delete effects.chorus;
                    }
                    break;
                case "reverb":
                    if (preset.config) {
                        effects.reverb = structuredClone(preset.config as CharacterTTSReverbConfig);
                    } else {
                        delete effects.reverb;
                    }
                    break;
                case "glitch":
                    if (preset.config) {
                        effects.glitch = structuredClone(preset.config as CharacterTTSGlitchConfig);
                    } else {
                        delete effects.glitch;
                    }
                    break;
                case "time_pitch":
                    if (preset.config) {
                        effects.time_pitch = structuredClone(preset.config as CharacterTTSTimePitchConfig);
                    } else {
                        delete effects.time_pitch;
                    }
                    break;
            }
        });
    }

    public async setCharacterPropertyAndUpdatePrompt<T extends keyof Character>(
        propName: T,
        value: Character[T],
    ): Promise<void> {
        if (!this.activeCharacter) return;

        const char = structuredClone(this.activeCharacter);
        char[propName] = value;
        const newPrompt = this.buildCharacterPrompt(char);
        await this.characterService.setCharacterProperty(propName, value);
        await this.characterService.setCharacterProperty('character', newPrompt);
    }

    private getVoiceEffectPresets(
        effectKey: VoiceEffectPresetKey,
    ): ReadonlyArray<VoiceEffectPresetOption<VoiceEffectConfig>> {
        switch (effectKey) {
            case "distortion":
                return this.distortionPresets;
            case "chorus":
                return this.chorusPresets;
            case "reverb":
                return this.reverbPresets;
            case "glitch":
                return this.glitchPresets;
            case "time_pitch":
                return this.timePitchPresets;
        }
    }

    private getDefaultVoiceEffectPresetId(effectKey: VoiceEffectPresetKey): string {
        return effectKey === "time_pitch" ? "natural" : "off";
    }

    private hasEnabledEffect(
        config: { enabled?: boolean } | null | undefined,
    ): boolean {
        return Boolean(config?.enabled);
    }

    private effectConfigsMatch(
        actualConfig: { enabled?: boolean } | null | undefined,
        presetConfig: { enabled?: boolean } | null | undefined,
    ): boolean {
        return JSON.stringify(this.normalizeEffectConfig(actualConfig))
            === JSON.stringify(this.normalizeEffectConfig(presetConfig));
    }

    private getNormalizedPresetConfig(
        effectKey: VoiceEffectPresetKey,
        presetConfig: VoiceEffectConfig | null,
    ): VoiceEffectConfig | null {
        if (!presetConfig?.enabled) {
            return null;
        }

        switch (effectKey) {
            case "distortion":
                return {
                    enabled: true,
                    drive: 2.0,
                    clip: 0.2,
                    mode: "tanh",
                    ...presetConfig as CharacterTTSDistortionConfig,
                };
            case "chorus":
                return {
                    enabled: true,
                    delay_ms: 25.0,
                    depth_ms: 12.0,
                    rate_hz: 0.25,
                    mix: 0.5,
                    ...presetConfig as CharacterTTSChorusConfig,
                };
            case "reverb":
                return {
                    enabled: true,
                    mix: 0.2,
                    tail: 0.18,
                    ...presetConfig as CharacterTTSReverbConfig,
                };
            case "glitch":
                return {
                    enabled: true,
                    probability: 0.04,
                    repeat_min: 2,
                    repeat_max: 4,
                    min_seconds: 0.05,
                    max_seconds: 0.2,
                    detune_base: 4.0,
                    detune_peak: 12.0,
                    ...presetConfig as CharacterTTSGlitchConfig,
                };
            case "time_pitch":
                return {
                    enabled: true,
                    pitch_shift_semitones: 0.0,
                    time_stretch: 1.0,
                    ...presetConfig as CharacterTTSTimePitchConfig,
                };
        }
    }

    private normalizeEffectConfig(
        config: { [key: string]: unknown } | null | undefined,
    ): Record<string, unknown> | null {
        if (!config?.["enabled"]) {
            return null;
        }

        const entries = Object.entries(config)
            .filter(([, value]) => value !== undefined)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([key, value]) => [
                key,
                typeof value === "number" ? Number(value.toFixed(6)) : value,
            ]);

        return Object.fromEntries(entries);
    }

    private async updateVoiceEffects(
        mutateEffects: (effects: CharacterTTSEffectsConfig) => void,
    ): Promise<void> {
        if (!this.activeCharacter) return;

        const nextPostprocessing: CharacterTTSPostprocessingConfig = structuredClone(
            this.activeCharacter.tts_postprocessing ?? {},
        );
        const nextEffects: CharacterTTSEffectsConfig = structuredClone(
            nextPostprocessing.effects ?? {},
        );

        mutateEffects(nextEffects);

        if (Object.keys(nextEffects).length > 0) {
            nextPostprocessing.effects = nextEffects;
        } else {
            delete nextPostprocessing.effects;
        }

        if (nextPostprocessing.volume === undefined && !nextPostprocessing.effects) {
            await this.setCharacterProperty("tts_postprocessing", undefined);
            return;
        }

        await this.setCharacterProperty("tts_postprocessing", nextPostprocessing);
    }

    buildCharacterPrompt(activeChar: Character): string {
        const personalityPreset = activeChar?.personality_preset || "default";

        console.log("Updating prompt for preset:", personalityPreset);

        // For custom mode, don't overwrite the existing character text unless it's empty
        if (personalityPreset === "custom") {
            return activeChar.character || "";
        }

        // Generate prompt based on active character values
        const promptParts: string[] = [];

        // Add prompt parts using active character properties
        promptParts.push(this.generateVerbosityTextFromConfig(activeChar));
        promptParts.push(this.generateToneTextFromConfig(activeChar));
        promptParts.push(this.generateKnowledgeTextFromConfig(activeChar));

        const charInspiration = activeChar?.personality_character_inspiration ||
            "";
        if (charInspiration) {
            promptParts.push(this.generateCharacterInspirationTextFromConfig(activeChar));
        }

        const charName = activeChar?.name || "COVAS:NEXT";
        if (charName) {
            promptParts.push(`Your name is ${charName}.`);
        }

        const language = activeChar?.personality_language || "english";
        if (language) {
            promptParts.push(
                `Always respond in ${language} regardless of the language spoken to you.`,
            );
        }

        // Add character traits
        promptParts.push(this.generateEmpathyTextFromConfig(activeChar));
        promptParts.push(this.generateFormalityTextFromConfig(activeChar));
        promptParts.push(this.generateConfidenceTextFromConfig(activeChar));
        promptParts.push(this.generateEthicalAlignmentTextFromConfig(activeChar));
        promptParts.push(this.generateMoralAlignmentTextFromConfig(activeChar));

        // Add vulgarity with randomization
        const vulgarity = activeChar?.personality_vulgarity ?? 0;
        if (vulgarity > 0) {
            promptParts.push(this.generateVulgarityTextFromConfig(activeChar));
        }

        // Combine all parts
        const character = promptParts.join(" ");

        // Ensure the commander_name format variable is preserved
        const finalCharacter = !character.includes("{commander_name}")
            ? character + " I am {commander_name}, pilot of this ship."
            : character;

        return finalCharacter;
    }

    generateVerbosityTextFromConfig(activeChar: Character): string {
        const options = [
            "Keep your responses extremely brief and minimal.",
            "Keep your responses brief and to the point.",
            "Provide concise answers that address the main points.",
            "Offer moderately detailed responses.",
            "Be comprehensive in your explanations and provide abundant details.",
        ];

        const verbosity = activeChar?.personality_verbosity ?? 0;

        const index = Math.min(Math.floor(verbosity / 25), options.length - 1);
        return options[index];
    }

    generateToneTextFromConfig(activeChar: Character): string {
        const tone = activeChar?.personality_tone || "serious";

        switch (tone) {
            case "serious":
                return "Maintain a professional and serious tone in all responses.";
            case "humorous":
                return "Include humor and light-hearted elements in your responses when appropriate.";
            case "sarcastic":
                return "Use sarcasm and wit in your responses, especially when pointing out ironies or contradictions.";
            default:
                return "";
        }
    }

    generateKnowledgeTextFromConfig(activeChar: Character): string {
        const knowledgeAreas = [];

        if (activeChar?.personality_knowledge_pop_culture) {
            knowledgeAreas.push(
                "pop culture references, movies, music, and celebrities",
            );
        }

        if (activeChar?.personality_knowledge_scifi) {
            knowledgeAreas.push(
                "science fiction concepts, popular sci-fi franchises, and futuristic ideas",
            );
        }

        if (activeChar?.personality_knowledge_history) {
            knowledgeAreas.push(
                "historical events, figures, and their significance",
            );
        }

        if (knowledgeAreas.length === 0) {
            return "Stick to factual information.";
        }

        return `Incorporate knowledge of ${
            knowledgeAreas.join(", ")
        } when relevant to the conversation.`;
    }

    generateCharacterInspirationTextFromConfig(activeChar: Character): string {
        const inspiration = activeChar?.personality_character_inspiration || "";
        return `Your responses should be inspired by the character or persona of ${inspiration}. Adopt their speech patterns, mannerisms, and viewpoints.`;
    }

    generateVulgarityTextFromConfig(activeChar: Character): string {
        const options = [
            "Maintain completely clean language with no vulgarity.",
            "You may occasionally use mild language when appropriate.",
            "Feel free to use moderate language including some swear words when it fits the context.",
            "Don't hesitate to use strong language and swear words regularly.",
            "Use explicit language and profanity freely in your responses.",
        ];

        const vulgarity = activeChar?.personality_vulgarity ?? 0;

        const index = Math.min(Math.floor(vulgarity / 25), options.length - 1);
        return options[index];
    }

    generateEmpathyTextFromConfig(activeChar: Character): string {
        const options = [
            [
                "Focus exclusively on facts and logic, with no emotional considerations.",
                "Maintain a strictly analytical approach without emotional engagement.",
            ],
            [
                "Focus on facts and logic, with minimal emotional considerations.",
                "Prioritize objective information over emotional concerns.",
            ],
            [
                "Show some consideration for emotions while maintaining focus on information.",
                "Balance emotional understanding with factual presentation.",
            ],
            [
                "Demonstrate emotional intelligence and understanding in your responses.",
                "Show genuine concern for the emotional well-being of the user.",
            ],
            [
                "Prioritize empathy and emotional support in all interactions.",
                "Respond with deep emotional understanding and compassion.",
            ],
        ];

        const empathy = activeChar?.personality_empathy ?? 0;

        const index = Math.min(Math.floor(empathy / 25), options.length - 1);
        return options[index][
            Math.floor(Math.random() * options[index].length)
        ];
    }

    generateFormalityTextFromConfig(activeChar: Character): string {
        const options = [
            [
                "Use extremely casual language with slang and informal expressions.",
                "Speak in a very relaxed, informal tone as if talking to a close friend.",
            ],
            [
                "Use casual, conversational language with contractions and informal expressions.",
                "Speak in a relaxed, casual tone as if talking to a friend.",
            ],
            [
                "Use everyday language that balances casual and professional tones.",
                "Maintain a friendly yet respectful conversational style.",
            ],
            [
                "Communicate in a professional manner with proper language and structure.",
                "Present information with clarity and a professional demeanor.",
            ],
            [
                "Use highly formal language with sophisticated vocabulary and complete sentences.",
                "Maintain maximum formality and proper etiquette in all communications.",
            ],
        ];

        const formality = activeChar?.personality_formality ?? 0;

        const index = Math.min(Math.floor(formality / 25), options.length - 1);
        return options[index][
            Math.floor(Math.random() * options[index].length)
        ];
    }

    generateConfidenceTextFromConfig(activeChar: Character): string {
        const options = [
            [
                "Express thoughts with extreme caution and frequent uncertainty.",
                "Present information with many qualifiers and a very humble approach.",
            ],
            [
                "Express thoughts tentatively, acknowledging uncertainty where appropriate.",
                "Present information with qualifiers and a humble approach, acknowledging limitations.",
            ],
            [
                "Balance confidence with appropriate caution in your responses.",
                "Express moderate confidence in your knowledge while remaining open to correction.",
            ],
            [
                "Speak with confidence and conviction in your responses.",
                "Project an air of expertise and certainty when providing information.",
            ],
            [
                "Communicate with unwavering confidence and authority.",
                "Assert information decisively and with complete conviction.",
            ],
        ];

        const confidence = activeChar?.personality_confidence ?? 0;

        const index = Math.min(Math.floor(confidence / 25), options.length - 1);
        return options[index][
            Math.floor(Math.random() * options[index].length)
        ];
    }

    generateEthicalAlignmentTextFromConfig(activeChar: Character): string {
        const alignment = activeChar?.personality_ethical_alignment ||
            "neutral";

        switch (alignment) {
            case "lawful":
                return "Adhere strictly to rules, regulations, and established protocols.";
            case "neutral":
                return "Balance adherence to rules with flexibility when the situation calls for it.";
            case "chaotic":
                return "Prioritize freedom and flexibility over strict adherence to rules or traditions.";
            default:
                return "Balance adherence to rules with flexibility when the situation calls for it.";
        }
    }

    generateMoralAlignmentTextFromConfig(activeChar: Character): string {
        const alignment = activeChar?.personality_moral_alignment || "neutral";

        switch (alignment) {
            case "good":
                return "Prioritize helping others and promoting positive outcomes in all situations.";
            case "neutral":
                return "Maintain a balanced approach between self-interest and helping others.";
            case "evil":
                return "Focus on practical outcomes and personal advantage in your advice and responses.";
            default:
                return "Maintain a balanced approach between self-interest and helping others.";
        }
    }

    // Generate text for the name field
    generateNameTextFromConfig(activeChar: Character): string {
        return `Your name is ${
            activeChar.name
        }.`;
    }

    // Generate text for the language field
    generateLanguageTextFromConfig(activeChar: Character): string {
        return `Always respond in ${
            activeChar.personality_language || "english"
        } regardless of the language spoken to you.`;
    }

    onVoiceSelectionChange(value: any) {
        if (value === "show-all-voices") {
            this.openEdgeTtsVoicesDialog();
        } else {
            this.setCharacterProperty("tts_voice", value);
        }
    }

    openEdgeTtsVoicesDialog() {
        const currentVoice = this.activeCharacter?.tts_voice ?? "en-US-AvaMultilingualNeural";

        const dialogRef = this.dialog.open(EdgeTtsVoicesDialogComponent, {
            width: "800px",
            data: {
                voices: this.edgeTtsVoices,
                selectedVoice: currentVoice,
            },
        });

        dialogRef.afterClosed().subscribe((result) => {
            if (result) {
                this.setCharacterProperty("tts_voice", result);
            }
        });
    }

    /**
     * Check if the voice is not in the predefined list of common voices
     */
    isCustomVoice(voice: string | undefined): boolean {
        if (!voice) return false;

        // Get the list of voices in the dropdowns
        const predefinedVoices = [
            "en-US-AriaNeural",
            "en-US-AnaNeural",
            "en-US-ChristopherNeural",
            "en-US-EricNeural",
            "en-US-GuyNeural",
            "en-US-JennyNeural",
            "en-US-MichelleNeural",
            "en-US-RogerNeural",
            "en-US-SteffanNeural",
            "en-GB-LibbyNeural",
            "en-GB-MaisieNeural",
            "en-GB-RyanNeural",
            "en-GB-SoniaNeural",
            "en-GB-ThomasNeural",
            "en-AU-NatashaNeural",
            "en-AU-WilliamNeural",
        ];

        return !predefinedVoices.includes(voice);
    }

    /**
     * Get a readable display name for a voice ID
     */
    getVoiceDisplayName(voice: string): string {
        // First check if it's in our full list of voices
        const foundVoice = this.edgeTtsVoices.find((v) => v.value === voice);
        if (foundVoice) {
            return `${foundVoice.label} (${foundVoice.locale})`;
        }

        // If not found in our list, try to format it nicely
        if (voice.includes("-")) {
            // Format like "en-US-JaneNeural" to "Jane (en-US)"
            const parts = voice.split("-");
            if (parts.length >= 3) {
                const locale = `${parts[0]}-${parts[1]}`;
                // Extract the name (remove "Neural" suffix if present)
                let name = parts.slice(2).join("-");
                if (name.endsWith("Neural")) {
                    name = name.substring(0, name.length - 6);
                }
                return `${name} (${locale})`;
            }
        }

        // If all else fails, just return the voice ID
        return voice;
    }

    // Character Management Methods
    onCharacterSelect(index: number) {
        if (!this.config) return;

        // Check if we're in edit mode with unsaved changes
        if (this.editMode) {
            this.confirmationDialog.openConfirmationDialog({
                title: "Unsaved Changes",
                message:
                    "You have unsaved changes. Do you want to discard them?",
                confirmButtonText: "Discard Changes",
                cancelButtonText: "Keep Editing",
            }).subscribe((result) => {
                if (result) {
                    // User chose to discard changes, proceed with character selection
                    this.characterService.setActiveCharacter(index);
                }
                // If false, stay in edit mode with current character
            });
        } else {
            // Not in edit mode, proceed directly
            this.characterService.setActiveCharacter(index);
        }
    }

    toggleEditMode() {
        if (!this.config) return;
        if (this.selectedCharacterIndex === null) return;

        // If not in edit mode, enter edit mode
        if (!this.editMode) {
            // Store a copy of the current character state before entering edit mode
            this.localCharacterCopy = JSON.parse(
                JSON.stringify(
                    this.config.characters[this.selectedCharacterIndex],
                ),
            );
            this.showVoiceMoreSettings = false;
            this.editMode = true;
        } else {
            // If already in edit mode, exit with confirmation for unsaved changes
            this.confirmationDialog.openConfirmationDialog({
                title: "Unsaved Changes",
                message:
                    "You have unsaved changes. Do you want to discard them?",
                confirmButtonText: "Discard Changes",
                cancelButtonText: "Keep Editing",
            }).subscribe((result) => {
                if (result) {
                    // User chose to discard changes - cancel edit mode
                    this.cancelEditMode();
                }
                // If false, stay in edit mode
            });
        }
    }

    // Helper method to save characters
    public saveCharacters() {
        if (!this.config || !this.config.characters) return;
        if (this.selectedCharacterIndex === null) return;

        // actually its all saved already, all we need it to clear the local backup

        this.localCharacterCopy = null;
        this.showVoiceMoreSettings = false;
        this.editMode = false;
    }

    cancelEditMode(): void {
        if (!this.config) return;
        if (this.selectedCharacterIndex===null) return;

        // If we were editing an existing character, restore it from the local copy
        if (
            this.localCharacterCopy
        ) {
            // Update the backend with the restored character
            this.characterService.updateCharacter(
                this.selectedCharacterIndex,
                JSON.parse(
                    JSON.stringify(this.localCharacterCopy),
                )
            );
        }

        // Clear the local copy
        this.localCharacterCopy = null;

        // Always exit edit mode
        this.showVoiceMoreSettings = false;
        this.editMode = false;
    }

    // Update addNewCharacter method to properly initialize with the default preset
    addNewCharacter(): void {
        if (!this.config) return;

        this.characterService.addDefaultCharacter()
    }

    deleteSelectedCharacter(): void {
        if (!this.config || this.selectedCharacterIndex === null) return;

        // default cannot be deleted
        if (this.selectedCharacterIndex === 0) return;

        this.confirmationDialog.openConfirmationDialog({
            title: "Delete Character",
            message: `Are you sure you want to delete "${
                this.config.characters[this.selectedCharacterIndex].name
            }"? This action cannot be undone.`,
            confirmButtonText: "Delete",
            cancelButtonText: "Cancel",
        }).subscribe((confirmed) => {
            if (confirmed && this.config && this.config.characters) {
                if (this.selectedCharacterIndex === null) return;

                this.characterService.deleteCharacter(this.selectedCharacterIndex);

                // Show success message
                this.snackBar.open(
                    `Character deleted successfully`,
                    "Close",
                    { duration: 3000 },
                );
            }
        });
    }

    // Helper to safely get character property with fallback to default
    getCharacterProperty<T extends keyof Character>(
        propName: T,
        defaultValue: Character[T],
    ): Character[T] {
        if (!this.config) return defaultValue;
        if (!this.activeCharacter) return defaultValue;
        // Use optional chaining to safely access the property
        return this.activeCharacter[propName] ?? defaultValue;
    }

    // Helper method to check if personality preset is custom
    isCustomPreset(): boolean {
        // Get the value and convert it to string explicitly for comparison
        const value = this.getCharacterProperty(
            "personality_preset",
            "default",
        );
        // Use String() to ensure we're working with a string type
        return value === "custom";
    }


    // Count the number of active events for a character
    countActiveEvents(character: Character): number {
        if (!character["event_reactions"]) {
            return 0;
        }

        return Object.values(character["event_reactions"]).filter((value) =>
            value === "on"
        ).length;
    }

    duplicateSelectedCharacter(): void {
        if (!this.config || this.selectedCharacterIndex === null) return;

        // Make sure we have a characters array and the selected index is valid
        if (
            !this.config.characters ||
            !this.config.characters[this.selectedCharacterIndex]
        ) {
            this.snackBar.open("Error: Character not found", "OK", {
                duration: 5000,
            });
            return;
        }

        const config = this.config; // Store in local variable
        const originalChar = config.characters[this.selectedCharacterIndex];

        // Create a deep copy of the character
        const duplicatedChar = JSON.parse(JSON.stringify(originalChar));

        // Modify the name to indicate it's a copy
        let newName = `${originalChar.name} (Copy)`;
        let counter = 1;

        // Check if a character with this name already exists
        while (config.characters.some((char) => char.name === newName)) {
            counter++;
            newName = `${originalChar.name} (Copy ${counter})`;
        }

        duplicatedChar.name = newName;

        // Add the duplicated character to the config
        config.characters.push(duplicatedChar);

        // Save the updated characters array
        this.configService.changeConfig({ characters: config.characters }).then(
            () => {
                const newIndex = config.characters.length - 1;
                this.selectedCharacterIndex = newIndex;

                // Set this as the active character
                this.characterService.setActiveCharacter(newIndex);

                // Show success message
                this.snackBar.open(`Character "${newName}" created`, "OK", {
                    duration: 3000,
                });
            },
        ).catch((error) => {
            console.error("Error duplicating character:", error);
            this.snackBar.open("Error duplicating character", "OK", {
                duration: 5000,
            });
        });
    }

    async onClearHistory(): Promise<void> {
        const dialogRef = this.dialog.open(ConfirmationDialogComponent, {
            data: {
                title: "Clear History",
                message:
                    "Are you sure you want to clear the conversation history? This action cannot be undone.",
            },
        });

        dialogRef.afterClosed().subscribe(async (result) => {
            if (result) {
                await this.configService.clearHistory();
            }
        });
    }

    // Avatar-related methods
    async loadCharacterAvatar() {
        // This method is now handled by the character service
        // We can remove this implementation as the service handles it automatically
    }

    getAvatarUrl(): string {
        return this.characterService.getAvatarUrl();
    }

    openAvatarCatalog() {
        const dialogRef = this.dialog.open(AvatarCatalogDialogComponent, {
            width: '850px',
            maxWidth: '95vw',
            data: { currentAvatarPath: this.activeCharacter?.avatar }
        });

        dialogRef.afterClosed().subscribe((result: AvatarCatalogResult) => {
            if (result !== undefined && this.activeCharacter) {
                this.setCharacterProperty('avatar', result.avatarPath);
                // The character service will automatically reload the avatar
            }
        });
    }

    // Enable custom character editor with confirmation
    enableCustomCharacterEditor() {
        if (!this.activeCharacter) return;

        const dialogRef = this.confirmationDialog.openConfirmationDialog({
            title: "Enable Custom Prompt",
            message: "This will allow you to write your own character prompt. This action cannot be undone - you will need to create a new character to use presets again. Are you sure you want to continue?",
            confirmButtonText: "Understood",
            cancelButtonText: "Cancel",
        });

        dialogRef.subscribe((result: boolean) => {
            if (result) {
                // Enable custom character editor mode
                this.applySettingsFromPreset('custom');
                this.snackBar.open('Custom character editor enabled', 'OK', {
                    duration: 3000,
                });
            }
        });
    }

    // Randomize character preset
    randomizePreset() {
        if (!this.activeCharacter) return;

        // Get all available presets except 'custom'
        const availablePresets = Object.keys(CharacterPresets).filter(
            preset => preset !== 'custom'
        );

        if (availablePresets.length === 0) return;

        // Pick a random preset
        const randomIndex = Math.floor(Math.random() * availablePresets.length);
        const randomPreset = availablePresets[randomIndex];

        // Apply the random preset
        this.applySettingsFromPreset(randomPreset);

        // Show notification to user
        this.snackBar.open('Random personality preset applied!', 'OK', {
            duration: 2000,
        });
    }

    // Handle character inspiration contenteditable change
    onCharacterInspirationChange(event: Event) {
        const target = event.target as HTMLElement;
        const newValue = target.textContent || '';
        this.setCharacterPropertyAndUpdatePrompt('personality_character_inspiration', newValue);
    }
}
