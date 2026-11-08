import { Labels, metadataLabel, Observation } from "./telemetry";

const record = (value: unknown): Record<string, unknown> => value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown> : {};

/** Current setup only. Configuration values are measurements, never event counts. */
export class SetupTelemetry {
    private current: Observation[] = [];
    private revision = 0;
    constructor(private platform: string) {}

    update(message: Record<string, unknown>): void {
        if (!["config", "running_config"].includes(String(message["type"]))) return;
        if (!message["config"] || typeof message["config"] !== "object") return;
        const config = record(message["config"]);
        this.revision = Math.max(Date.now(), this.revision + 1);
        const identity: Labels = { "os.type": this.platform,
            "input.mode": metadataLabel(config["ptt_var"]), "overlay.mode": metadataLabel(config["overlay_mode"]) };
        for (const kind of ["llm", "agent_llm", "vision", "stt", "tts", "embedding"])
            identity[`configured.${kind}.provider`] = metadataLabel(config[`${kind}_provider`]);
        const points: Observation[] = [{ name: "covas_setup_snapshot", value: this.revision, attributes: identity }];
        const addFeature = (feature: string, value: unknown) => {
            if (typeof value === "boolean") points.push({ name: "covas_setup_feature_enabled", value: Number(value), attributes: { feature } });
        };
        for (const [key, feature] of Object.entries({
            vision_var: "vision", game_actions_var: "game_actions", web_search_actions_var: "web_search",
            ui_actions_var: "ui_actions", use_action_cache_var: "action_cache", pngtuber: "avatar_animation",
            cn_autostart: "autostart", enable_remote_tracing: "remote_tracing", in_system_navigation: "in_system_navigation",
            linux_edcp: "linux_edcopilot", qol_autobrake: "auto_brake", qol_autoscan: "auto_scan", qol_autoboost: "auto_boost",
            mute_during_response_var: "mute_during_response", overlay_show_avatar: "overlay_avatar",
            overlay_show_hud: "overlay_hud", overlay_show_chat: "overlay_chat",
        })) addFeature(feature, config[key]);
        if (Array.isArray(config["characters"])) {
            const characters = config["characters"];
            const builtin = record(characters[0])["name"] === "Default" ? 1 : 0;
            for (const [kind, value] of [["total", characters.length], ["user_defined", characters.length - builtin]] as const)
                points.push({ name: "covas_setup_characters", value, attributes: { kind } });
            const index = config["active_character_index"];
            const active = record(typeof index === "number" && Number.isInteger(index) ? characters[index] : null);
            for (const key of ["event_reaction_enabled_var", "tts_environment_damage_effects_var",
                "tts_environment_helmet_effects_var", "tts_environment_srv_effects_var", "react_to_text_local_var",
                "react_to_text_starsystem_var", "react_to_text_npc_var", "react_to_text_squadron_var"])
                addFeature(`character.${key.replace(/_var$/, "")}`, active[key]);
            for (const [effect, options] of Object.entries(record(record(active["tts_postprocessing"])["effects"])))
                addFeature(`tts.effect.${effect}`, record(options)["enabled"]);
        }
        this.current = [...points, ...points.filter(point => point.name !== "covas_setup_snapshot").map(point => ({
            name: point.name === "covas_setup_feature_enabled" ? "covas_setup_feature_observed_at" : "covas_setup_characters_observed_at",
            value: this.revision, attributes: { ...point.attributes },
        }))];
    }

    observations(name?: string): Observation[] {
        return this.current.filter(point => !name || point.name === name).map(point => ({ ...point, attributes: { ...point.attributes } }));
    }
}
