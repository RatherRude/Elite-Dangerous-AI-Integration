from copy import deepcopy
from dataclasses import dataclass
from math import isfinite
from typing import Any, TYPE_CHECKING, cast

from .Config import (
    Character, CharacterTTSPostprocessingConfig, Config, getDefaultCharacter,
    map_character_tts_postprocessing, TTS_ENVIRONMENT_EFFECTS_IN_SRV,
    TTS_ENVIRONMENT_EFFECTS_ON_FOOT, TTS_ENVIRONMENT_EFFECTS_OVERHEATING,
)
from .PluginSettingDefinitions import resolve_voice_settings
from .Projections import get_state_dict, ProjectedStates

if TYPE_CHECKING:
    from .PluginBase import PluginBase
    from .PluginManager import PluginManager


@dataclass(frozen=True)
class ResolvedCharacter:
    name: str | None
    profile: dict[str, Any]
    plugin_guid: str | None = None

    @property
    def prompt(self) -> str:
        return self.profile.get('character') or ''


@dataclass(frozen=True)
class PlaybackSettings:
    voice: str
    voice_settings: dict[str, Any]
    speed: float
    postprocessing_layers: list[CharacterTTSPostprocessingConfig]

    def kwargs(self) -> dict[str, Any]:
        return {
            'voice': self.voice, 'voice_settings': self.voice_settings, 'speed': self.speed,
            'postprocessing_layers': self.postprocessing_layers,
        }


class CharacterManager:
    """Resolve model crew and plugin speakers without sharing their namespaces."""

    def __init__(self, config: Config, plugin_manager: 'PluginManager | None' = None):
        self.config = config
        self.plugin_manager = plugin_manager

    @staticmethod
    def _name(value: object) -> str | None:
        if not isinstance(value, str):
            return None
        return value.strip() or None

    @property
    def active_crew(self) -> tuple[ResolvedCharacter, ...]:
        regular = {
            index: ResolvedCharacter(self._name(profile.get('name')), profile)
            for index, profile in enumerate(self.config.get('characters') or [])
            if isinstance(profile, dict) and not profile.get('plugin_guid') and not profile.get('externally_voiced')
        }
        primary = self.config.get('active_character_index', 0)
        if type(primary) is not int or (primary != -1 and primary not in regular):
            primary = next(iter(regular), -1)
        if primary == -1:
            fallback = cast(dict[str, Any], getDefaultCharacter(self.config))
            leader = ResolvedCharacter(self._name(fallback.get('name')), fallback)
        else:
            leader = regular[primary]

        active = self.config.get('active_characters')
        crew = [leader]
        names = {crew[0].name.casefold()} if crew[0].name else set()
        for index in active if isinstance(active, list) else []:
            if type(index) is not int or index == primary or index not in regular:
                continue
            member = regular[index]
            if member.name and member.name.casefold() not in names:
                crew.append(member)
                names.add(member.name.casefold())
        return tuple(crew)

    @property
    def primary(self) -> ResolvedCharacter:
        return self.active_crew[0]

    @property
    def primary_profile(self) -> Character:
        return cast(Character, self.primary.profile)

    @property
    def active_prompts(self) -> tuple[tuple[str | None, str], ...]:
        return tuple((member.name, member.prompt) for member in self.active_crew)

    def resolve_model(self, name: str | None = None) -> ResolvedCharacter | None:
        """Only unnamed lines default to primary; explicit labels must be active."""
        crew = self.active_crew
        key = self._name(name)
        if key:
            return next((member for member in crew if member.name and member.name.casefold() == key.casefold()), None)
        return crew[0]

    def resolve_plugin(self, plugin: 'PluginBase', overrides: dict[str, Any] | None = None) -> ResolvedCharacter:
        profile = plugin.character or {}
        settings = {**profile, **(overrides or {})}
        if not settings.get('avatar'):
            settings['avatar'] = plugin.character_default_avatar
        name = self._name(profile.get('name')) or self._name(plugin.plugin_manifest.name)
        return ResolvedCharacter(name, settings, plugin_guid=plugin.plugin_manifest.guid)

    def playback(self, character: ResolvedCharacter, states: ProjectedStates | None = None, *,
                 use_profile_voice: bool = True) -> PlaybackSettings:
        profile = character.profile
        speed = 1.0
        try:
            configured_speed = float(profile.get('tts_speed', 1.0))
            if isfinite(configured_speed) and configured_speed > 0:
                speed = configured_speed
        except (TypeError, ValueError):
            pass

        voice_settings = self._voice_settings(profile) if use_profile_voice else {'voice': ''}
        voice = voice_settings.get('voice')
        return PlaybackSettings(
            voice if isinstance(voice, str) else '', voice_settings, speed,
            [map_character_tts_postprocessing(profile.get('tts_postprocessing')),
             *self._environment_layers(character, states or {})],
        )

    def _voice_settings(self, profile: dict[str, Any]) -> dict[str, Any]:
        provider_ref = self.config.get('tts_provider') or ''
        references = profile.get('tts_voice_settings')
        stored = references.get(provider_ref) if isinstance(references, dict) else None
        overrides = dict(stored) if isinstance(stored, dict) else {}
        legacy_voice = self._name(profile.get('tts_voice'))
        if legacy_voice and overrides.get('voice') is None:
            overrides['voice'] = legacy_voice
        parts = provider_ref.split(':', 2)
        if len(parts) == 3 and parts[0] == 'plugin':
            provider = self.plugin_manager.get_plugin_provider(parts[1], parts[2]) if self.plugin_manager else None
            overrides = resolve_voice_settings(
                (provider or {}).get('voice_settings_config') or [],
                self.config.get('plugin_settings', {}).get(parts[1], {}), overrides,
            )
        return deepcopy({'voice': '', **overrides})

    def _environment_layers(self, character: ResolvedCharacter, states: ProjectedStates) -> list[CharacterTTSPostprocessingConfig]:
        status = get_state_dict(states, 'CurrentStatus')
        flags = status.get('flags')
        flags2 = status.get('flags2')
        flags = flags if isinstance(flags, dict) else {}
        flags2 = flags2 if isinstance(flags2, dict) else {}
        hull_health = get_state_dict(states, 'Loadout').get('HullHealth')
        default = character.plugin_guid is None
        profile = character.profile
        layers = []
        if profile.get('tts_environment_damage_effects_var', default):
            if flags.get('OverHeating'):
                layers.append(deepcopy(TTS_ENVIRONMENT_EFFECTS_OVERHEATING))
            elif isinstance(hull_health, (int, float)) and hull_health <= 0.75:
                layers.append(self._get_scaled_damage_tts_postprocessing(float(hull_health)))
        if profile.get('tts_environment_srv_effects_var', default) and flags.get('InSRV'):
            layers.append(deepcopy(TTS_ENVIRONMENT_EFFECTS_IN_SRV))
        if profile.get('tts_environment_helmet_effects_var', default) and flags2.get('OnFoot'):
            layers.append(deepcopy(TTS_ENVIRONMENT_EFFECTS_ON_FOOT))
        return layers

    @staticmethod
    def _get_scaled_damage_tts_postprocessing(
        hull_health: float,
    ) -> CharacterTTSPostprocessingConfig:
        intensity = 1.0 - max(0.0, min(1.0, hull_health))
        scaled = deepcopy(TTS_ENVIRONMENT_EFFECTS_OVERHEATING)
        effects = scaled.get("effects", {})

        distortion = effects.get("distortion") if isinstance(effects, dict) else None
        if isinstance(distortion, dict) and distortion.get("enabled"):
            if isinstance(distortion.get("drive"), (int, float)):
                distortion["drive"] = float(distortion["drive"]) * intensity
            if isinstance(distortion.get("mix"), (int, float)):
                distortion["mix"] = min(1.0, float(distortion["mix"]) * intensity)
            if isinstance(distortion.get("clip"), (int, float)) and float(distortion["clip"]) > 0.0:
                distortion["clip"] = max(0.05, float(distortion["clip"]) / intensity)

        glitch = effects.get("glitch") if isinstance(effects, dict) else None
        if isinstance(glitch, dict) and glitch.get("enabled"):
            if isinstance(glitch.get("probability"), (int, float)):
                glitch["probability"] = min(1.0, float(glitch["probability"]) * intensity)
            if isinstance(glitch.get("repeat_min"), (int, float)):
                glitch["repeat_min"] = max(1, int(round(float(glitch["repeat_min"]) * intensity)))
            if isinstance(glitch.get("repeat_max"), (int, float)):
                glitch["repeat_max"] = max(1, int(round(float(glitch["repeat_max"]) * intensity)))
            if isinstance(glitch.get("min_seconds"), (int, float)):
                glitch["min_seconds"] = float(glitch["min_seconds"]) * intensity
            if isinstance(glitch.get("max_seconds"), (int, float)):
                glitch["max_seconds"] = float(glitch["max_seconds"]) * intensity
            if isinstance(glitch.get("detune_base"), (int, float)):
                glitch["detune_base"] = float(glitch["detune_base"]) * intensity
            if isinstance(glitch.get("detune_peak"), (int, float)):
                glitch["detune_peak"] = float(glitch["detune_peak"]) * intensity

            repeat_min = glitch.get("repeat_min")
            repeat_max = glitch.get("repeat_max")
            if isinstance(repeat_min, int) and isinstance(repeat_max, int) and repeat_max < repeat_min:
                glitch["repeat_max"] = repeat_min

            min_seconds = glitch.get("min_seconds")
            max_seconds = glitch.get("max_seconds")
            if isinstance(min_seconds, (int, float)) and isinstance(max_seconds, (int, float)) and max_seconds < min_seconds:
                glitch["max_seconds"] = min_seconds

        return scaled
