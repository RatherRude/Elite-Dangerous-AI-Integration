from sys import exc_info
import traceback
from typing import Any, Callable
import numpy as np
from scipy.signal import resample

from lib.Event import Event
from lib.Logger import log
from lib.RollingAudioBuffer import RollingAudioBuffer

class DamageEffectsPostProcessor:
    """
    Post-processor for damage effects.
    This class is responsible for post-processing audio to add damage effects, such as distortion, glitching, crackling, and audio repetition.
    """

    # TODO: Add a way for plugins to modify the damage effects processing logic.
    
    def __init__(self, rolling_buffer: RollingAudioBuffer, get_current_state: Callable[[], tuple[list[Event], dict[str, Any]]]):
        self._rolling_buffer: RollingAudioBuffer = rolling_buffer
        self._get_current_state: Callable[[], tuple[list[Event], dict[str, Any]]] = get_current_state

    def process(self, audio_chunk: bytes) -> bytes:
        """
        Process the damage effects.
        """
        # Placeholder for processing logic
        # TODO: Apply damage effects based on the current state, instead of hardcoded.
        return self.apply_damage_effects(audio_chunk, 0.5)  # Example usage with a damage level of 0.5

    def apply_damage_effects(self, audio_bytes: bytes, dmg_lvl: float, dmg_threshhold: float = 0.10) -> bytes:
        """
        Applies various damage effects to audio data based on the damage level.
        """

        # If damage level is below threshold (default 10%), or random chance exceeds damage level, return original audio.
        if dmg_lvl <= dmg_threshhold or np.random.rand() > dmg_lvl:
            return audio_bytes

        try:
            sample_rate: int = 22050
            distortion: float = 0.3
            glitch_rate: float = 0.01
            chunk_size: int = int(sample_rate * 0.05)  # 50ms chunks
            max_pitch_shift: float = 0.05 * dmg_lvl    # ±5% pitch wobble
            volume_flicker_range: tuple = (0.6, 1.0)
            crackle_probability = 0.0005

            # TODO: Stereo support
            # Convert bytes to numpy array (assuming 16-bit mono PCM)
            audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
            audio_np /= 32768.0  # Normalize

            # --- Effect: Pitch & Volume Modulation ---
            modulated = []
            for i in range(0, len(audio_np), chunk_size):
                chunk = audio_np[i:i + chunk_size]

                # Volume flicker
                volume_scale = np.random.uniform(*volume_flicker_range)
                chunk *= volume_scale

                # Pitch wobble
                if np.random.rand() < 0.5 * dmg_lvl:
                    pitch_factor = 1 + np.random.uniform(-max_pitch_shift, max_pitch_shift)
                    new_len = max(1, int(len(chunk) * pitch_factor))
                    chunk = resample(chunk, new_len)

                modulated.append(chunk)

            # Stitch back and normalize length
            audio_np = np.concatenate(modulated)
            original_len = int(len(audio_bytes) / 2)
            if len(audio_np) > original_len:
                audio_np = audio_np[:original_len]
            else:
                audio_np = np.pad(audio_np, (0, original_len - len(audio_np)))

            # --- Effect 1: Distortion ---
            audio_np = np.clip(audio_np * (1 + distortion * 10) * dmg_lvl, -1.0, 1.0)

            # --- Effect 2: Glitching ---
            glitch_size = int(sample_rate * 0.20)
            for i in range(0, len(audio_np), glitch_size):
                if np.random.rand() < (glitch_rate * dmg_lvl):
                    audio_np[i:i + glitch_size] *= np.random.uniform(0, 0.3)

            # --- Effect 3: Crackling ---
            noise = np.random.uniform(-1.0, 1.0, size=audio_np.shape)
            mask = np.random.rand(len(audio_np)) < (crackle_probability * dmg_lvl)
            audio_np[mask] += noise[mask] * 0.6

            # --- Effect 4: Audio Repetition (Partial or Full) ---
            if np.random.rand() < 0.2 * dmg_lvl:
                repeat_type = np.random.choice(["partial", "full"], p=[0.7, 0.3])
                log('info', f"Applying {'full' if repeat_type == 'full' else 'partial'} audio repetition.")
                if repeat_type == "full":
                    repeated = audio_np.copy()
                else:
                    full_audio_length = len(audio_np)
                    # Repeat a 300–800ms segment
                    seg_len = int(sample_rate * np.random.uniform(0.3, 0.8))
                    if full_audio_length <= seg_len:
                        log('info', "Audio too short for segment length, repeating full audio.")
                        repeated = audio_np.copy()
                    else:
                        start = np.random.randint(0, full_audio_length - seg_len)
                        repeated = audio_np[start:start + seg_len]

                # Scale down the repeated section to avoid overwhelming
                repeated *= np.random.uniform(0.3, 0.6)

                # Inject at random position or append
                insert_at = np.random.randint(0, len(audio_np))
                audio_np = np.concatenate([
                    audio_np[:insert_at],
                    repeated,
                    audio_np[insert_at:]
                ])

                # Trim/pad to original length
                if len(audio_np) > original_len:
                    audio_np = audio_np[:original_len]
                else:
                    audio_np = np.pad(audio_np, (0, original_len - len(audio_np)))

            # Final clip and convert back to int16 bytes
            audio_np = np.clip(audio_np, -1.0, 1.0)
            audio_int16 = (audio_np * 32767.0).astype(np.int16)
            log('info', f"Added damage effects with level {dmg_lvl}.")
            # Log original and final audio length in seconds and milliseconds
            log('info', f"Original audio length: {len(audio_bytes) / 2 / sample_rate:.3f} seconds ({len(audio_bytes) / 2:.0f} ms), ")
            log('info', f"Final audio length: {len(audio_int16) / 2 / sample_rate:.3f} seconds ({len(audio_int16) * 2:.0f} ms).")
            return audio_int16.tobytes()
        except Exception as e:
            log('info', f"Error applying damage sound effects: {e}\n{traceback.format_exc()}")
            return audio_bytes  # Return original if any error occurs
