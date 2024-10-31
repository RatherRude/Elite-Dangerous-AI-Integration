from typing import Literal, TypedDict


class Config(TypedDict):
    api_key: str
    llm_api_key: str
    llm_endpoint: str
    commander_name: str
    character: str
    llm_model_name: str
    vision_model_name: str
    vision_endpoint: str
    vision_api_key: str
    stt_provider: Literal['openai', 'custom', 'none']
    stt_model_name: str
    stt_api_key: str
    stt_endpoint: str
    tts_provider: Literal['openai', 'edge-tts', 'custom', 'none']
    tts_model_name: str
    tts_api_key: str
    tts_endpoint: str
    tools_var: bool
    vision_var: bool
    ptt_var: bool
    continue_conversation_var: bool
    edcopilot: bool
    edcopilot_dominant: bool
    tts_voice: str
    tts_speed: str
    ptt_key: str
    input_device_name: str
    game_events: dict[str, dict[str, bool]]