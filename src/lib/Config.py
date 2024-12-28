from typing import Literal, TypedDict
import os
import platform


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
    event_reaction_enabled_var: bool
    edcopilot: bool
    edcopilot_dominant: bool
    tts_voice: str
    tts_speed: str
    ptt_key: str
    input_device_name: str
    game_events: dict[str, dict[str, bool]]
    ed_journal_path: str
    ed_appdata_path: str


def get_cn_appdata_path() -> str:
    return os.getcwd()
    

def get_ed_journals_path(config: Config) -> str:
    """Returns the path of the Elite Dangerous journal and state files"""
    if config.get('ed_journal_path'):
        return config['ed_journal_path']
        
    from . import WindowsKnownPaths as winpaths
    saved_games = winpaths.get_path(winpaths.FOLDERID.SavedGames, winpaths.UserHandle.current) 
    if saved_games is None:
        raise FileNotFoundError("Saved Games folder not found")
    return saved_games + "\\Frontier Developments\\Elite Dangerous"
    
def get_ed_appdata_path(config: Config) -> str:
    """Returns the path of the Elite Dangerous appdata folder"""
    if config.get('ed_appdata_path'):
        return config['ed_appdata_path']
        
    from os import environ
    return environ['LOCALAPPDATA'] + "\\Frontier Developments\\Elite Dangerous"
    