from typing import Any, Callable, final
import numpy as np

from .Event import Event
from .RollingAudioBuffer import RollingAudioBuffer
from .TTSPostProcessors.DamageEffectsPostProcessor import DamageEffectsPostProcessor
from .TTSPostProcessors.VehicleReverbEffectPostProcessor import VehicleReverbEffectPostProcessor

@final
class TTSPostProcessor:
    """
    Post-processor for TTS audio effects.
    This class is responsible for post-processing audio to add various effects, such as damage effects, suit/ship/SRV effects, and more.
    """

    def __init__(self, get_current_state: Callable[[], tuple[list[Event], dict[str, Any]]], damage_effects_enabled: bool, vehicle_reverb_effect_enabled: bool, sample_rate: int = 44100):
        self._damage_effects_enabled: bool = damage_effects_enabled
        self._vehicle_reverb_effect_enabled: bool = vehicle_reverb_effect_enabled
        self.sample_rate: int = sample_rate
        self._rolling_buffer: RollingAudioBuffer = RollingAudioBuffer(max_samples=int(sample_rate * 2))  # 2 seconds of audio
        if self._damage_effects_enabled:
            self._damage_effects_processor: DamageEffectsPostProcessor | None = DamageEffectsPostProcessor(self._rolling_buffer, get_current_state)
        if self._vehicle_reverb_effect_enabled:
            self._vehicle_reverb_effect_processor: VehicleReverbEffectPostProcessor | None = VehicleReverbEffectPostProcessor(self._rolling_buffer, get_current_state)

    def process(self, audio_chunk: bytes):
        """
        Process the audio chunk.
        """
        
        # Add the chunk to the rolling buffer (2 sec. long).
        samples = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32) / 32768.0
        self._rolling_buffer.add_chunk(samples)

        # Copy the audio chunk for processing.
        processed_chunk: bytes = audio_chunk

        # Damage effects post-processing.
        if self._damage_effects_enabled and self._damage_effects_processor is not None:
            processed_chunk = self._damage_effects_processor.process(processed_chunk)

        # Suit/Ship/SRV effects post-processing.
        if self._vehicle_reverb_effect_enabled and self._vehicle_reverb_effect_processor is not None:
            processed_chunk = self._vehicle_reverb_effect_processor.process(processed_chunk)

        # TODO: Add plugin post-processing here.
        
        return processed_chunk if processed_chunk is not None else audio_chunk
