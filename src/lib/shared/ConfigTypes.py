from typing import Literal
from pydantic import BaseModel

class Character(BaseModel):
    name: str
    character: str
    personality_preset: str
    personality_verbosity: int
    personality_vulgarity: int
    personality_empathy: int
    personality_formality: int
    personality_confidence: int
    personality_ethical_alignment: str
    personality_moral_alignment: str
    personality_tone: str
    personality_character_inspiration: str
    personality_language: str
    personality_knowledge_pop_culture: bool
    personality_knowledge_scifi: bool
    personality_knowledge_history: bool
    tts_voice: str | None
    tts_speed: str | None
    tts_prompt: str | None

class Config(BaseModel):
    config_version: int
    api_key: str
    llm_api_key: str
    llm_endpoint: str
    commander_name: str
    # Active character properties (kept for backward compatibility)
    character: str
    personality_preset: str
    personality_verbosity: int
    personality_vulgarity: int
    personality_empathy: int
    personality_formality: int
    personality_confidence: int
    personality_ethical_alignment: str
    personality_moral_alignment: str
    personality_tone: str
    personality_character_inspiration: str
    personality_language: str
    personality_name: str
    personality_knowledge_pop_culture: bool
    personality_knowledge_scifi: bool
    personality_knowledge_history: bool
    # Stored characters
    characters: list[Character]
    active_character_index: int
    # Other config settings
    llm_provider: Literal['openai', 'openrouter','google-ai-studio', 'custom', 'local-ai-server']
    llm_model_name: str
    llm_custom: dict[str, str]
    vision_provider: Literal['openai', 'google-ai-studio', 'custom', 'none']
    vision_model_name: str
    vision_endpoint: str
    vision_api_key: str
    stt_provider: Literal['openai', 'custom', 'custom-multi-modal', 'google-ai-studio', 'none', 'local-ai-server']
    stt_model_name: str
    stt_api_key: str
    stt_endpoint: str
    stt_custom_prompt: str
    stt_required_word: str
    tts_provider: Literal['openai', 'edge-tts', 'custom', 'none', 'local-ai-server']
    tts_model_name: str
    tts_api_key: str
    tts_endpoint: str
    tts_prompt: str | None
    tools_var: bool
    vision_var: bool
    ptt_var: bool
    mute_during_response_var: bool
    continue_conversation_var: bool
    event_reaction_enabled_var: bool
    game_actions_var: bool
    web_search_actions_var: bool
    use_action_cache_var: bool
    react_to_text_local_var: bool
    react_to_text_starsystem_var: bool
    react_to_text_npc_var: bool
    react_to_text_squadron_var: bool
    react_to_material: str
    react_to_danger_mining_var: bool
    react_to_danger_onfoot_var: bool
    react_to_danger_supercruise_var: bool
    edcopilot: bool
    edcopilot_dominant: bool
    tts_voice: str | None
    tts_speed: str | None
    ptt_key: str
    input_device_name: str
    output_device_name: str
    game_events: dict[str, bool] = {}
    cn_autostart: bool
    ed_journal_path: str
    ed_appdata_path: str
    reset_game_events: bool = False
