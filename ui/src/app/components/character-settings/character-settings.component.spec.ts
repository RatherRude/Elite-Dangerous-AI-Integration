import { Character } from "../../services/character.service";
import { CharacterSettingsComponent } from "./character-settings.component";

describe("Character prompt identity", () => {
    beforeEach(() => spyOn(Math, "random").and.returnValue(0));

    const character: Character = {
        name: "Default (Copy)",
        first_name: "Simone",
        character: "My custom prompt",
        personality_preset: "default",
        personality_verbosity: 0,
        personality_vulgarity: 0,
        personality_empathy: 50,
        personality_formality: 50,
        personality_confidence: 75,
        personality_ethical_alignment: "lawful",
        personality_moral_alignment: "good",
        personality_tone: "serious",
        personality_character_inspiration: "",
        personality_language: "English",
        personality_knowledge_pop_culture: false,
        personality_knowledge_scifi: false,
        personality_knowledge_history: false,
        tts_voice: "test-voice",
        tts_speed: "1.2",
        tts_prompt: "",
        tts_environment_damage_effects_var: true,
        tts_environment_helmet_effects_var: true,
        tts_environment_srv_effects_var: true,
        event_reaction_enabled_var: true,
        react_to_text_local_var: true,
        react_to_text_starsystem_var: true,
        react_to_text_npc_var: false,
        react_to_text_squadron_var: true,
        react_to_material: "",
        idle_timeout_var: 300,
        bounty_scanned_min_bounty_var: 1,
        react_to_danger_mining_var: false,
        react_to_danger_onfoot_var: false,
        react_to_danger_supercruise_var: false,
        event_reactions: {},
    };

    it("uses the first name in the generated personality, never the technical profile label", () => {
        const prompt = CharacterSettingsComponent.prototype.buildCharacterPrompt(character);
        expect(prompt).toContain("Your name is Simone.");
        expect(prompt).not.toContain("Default (Copy)");
        expect(CharacterSettingsComponent.prototype.buildCharacterPrompt({
            ...character, name: "Explorer (Copy 2)",
        })).toBe(prompt);
        expect(CharacterSettingsComponent.prototype.buildCharacterPrompt({
            ...character, first_name: "Astra",
        })).toContain("Your name is Astra.");
    });

    it("preserves manually authored custom prompts", () => {
        expect(CharacterSettingsComponent.prototype.buildCharacterPrompt({
            ...character, personality_preset: "custom",
        })).toBe("My custom prompt");
    });
});
