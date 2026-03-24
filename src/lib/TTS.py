import queue
import math
import re
import random
import threading
import traceback
from collections import deque
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from time import sleep, time
from typing import Any, Callable, Generator, Optional, final
import wave

from audiostretchy.stretch import AudioStretch
import miniaudio
import numpy as np
import pyaudio
import samplerate
import strip_markdown
from numpy.typing import NDArray
from num2words import num2words

from .Config import (
    CharacterTTSChorusConfig,
    CharacterTTSDistortionConfig,
    CharacterTTSGlitchConfig,
    CharacterTTSPostprocessingConfig,
    CharacterTTSReverbConfig,
    CharacterTTSTimePitchConfig,
    get_default_character_tts_postprocessing,
    map_character_tts_postprocessing,
)
from .Logger import log, observe, show_chat_message
from .Models import TTSModel, OpenAITTSModel


@dataclass
class LowpassState:
    y_prev: float = 0.0


@dataclass
class HighpassState:
    y_prev: float = 0.0
    x_prev: float = 0.0


@dataclass
class ChorusState:
    buffer: NDArray[np.float32]
    phase: float = 0.0


@dataclass
class ReverbState:
    impulse_response: NDArray[np.float32]
    overlap: NDArray[np.float32]
    ir_fft: NDArray[np.complex128] | None = None
    fft_size: int = 0
    chunk_length: int = 0
    mix: float = 0.0
    tail: float = 0.0
    hp_y_prev: float = 0.0
    hp_x_prev: float = 0.0


@dataclass
class GlitchState:
    history: deque[bytes]


GLITCH_BASE_DETUNE_SEMITONES = 4.0
GLITCH_BURST_DETUNE_SEMITONES = 12.0
REVERB_TAIL_HIGHPASS_HZ = 160.0


@final
class TTS:
    def __init__(
        self,
        tts_model: Optional[TTSModel] = None,
        voice: str = "nova",
        speed: float = 1.0,
        postprocessing_config: CharacterTTSPostprocessingConfig | None = None,
        output_device: Optional[str] = None,
    ):
        self.tts_model = tts_model
        self.voice = voice
        self.speed = speed
        self.postprocessing_config = map_character_tts_postprocessing(
            postprocessing_config or get_default_character_tts_postprocessing(),
        )
        
        self.p = pyaudio.PyAudio()
        self.output_device = output_device
        self.read_queue = queue.Queue()
        self.is_aborted = False
        self._is_playing = False
        self.prebuffer_size = 4
        self.output_format = pyaudio.paInt16
        self.frames_per_buffer = 1024
        self.sample_size = self.p.get_sample_size(self.output_format)
        self._lp_state = LowpassState()
        self._hp_state = HighpassState()
        self._chorus_state = ChorusState(buffer=np.zeros(int(24_000 * 0.1), dtype=np.float32))
        self._reverb_state = ReverbState(
            impulse_response=np.zeros(0, dtype=np.float32),
            overlap=np.zeros(0, dtype=np.float32),
        )
        self._glitch_state = GlitchState(history=deque(maxlen=64))

        thread = threading.Thread(target=self._playback_thread)
        thread.daemon = True
        thread.start()

    def _normalize_queue_item(self, item: Any) -> dict[str, Any]:
        if isinstance(item, str):
            return {
                "type": "text",
                "text": item,
                "file_path": None,
                "voice": None,
                "postprocessing": None,
                "on_start": None,
                "on_complete": None,
                "drop_if": None,
            }
        if isinstance(item, dict):
            return {
                "type": item.get("type", "text"),
                "text": item.get("text", ""),
                "file_path": item.get("file_path"),
                "voice": item.get("voice"),
                "postprocessing": item.get("postprocessing"),
                "on_start": item.get("on_start"),
                "on_complete": item.get("on_complete"),
                "drop_if": item.get("drop_if"),
            }
        return {
            "type": "text",
            "text": "",
            "file_path": None,
            "voice": None,
            "postprocessing": None,
            "on_start": None,
            "on_complete": None,
            "drop_if": None,
        }

    def _get_output_device_index(self) -> Optional[int]: #Rewert from String to Index 
        for i in range(self.p.get_device_count()):
            dev_info = self.p.get_device_info_by_index(i)
            if self.output_device in dev_info.get('name', ''):
                return i
        return None

    def _playback_thread(self):
        backoff = 1
        while True:
            try:
                self._playback_loop()
            except Exception as e:
                log('error', 'An error occurred during speech synthesis', e, traceback.format_exc())
                show_chat_message('error', 'An error occurred during speech synthesis:', e)
                sleep(backoff)
                log('info', 'Attempting to restart audio playback after failure')
                backoff *= 2

    def _playback_loop(self):
        output_index = self._get_output_device_index()
        stream = self.p.open(
            format=self.output_format,
            channels=1,
            rate=24_000,
            frames_per_buffer=self.frames_per_buffer,
            output=True,
            output_device_index=output_index  
        )
        while True:
            self.is_aborted = False
            stream.start_stream()
            while not self.is_aborted:
                if not self.read_queue.empty():
                    self._is_playing = True
                    item = self._normalize_queue_item(self.read_queue.get())
                    item_type = item.get("type")
                    text = item.get("text")
                    file_path = item.get("file_path")
                    voice = item.get("voice")
                    postprocessing = item.get("postprocessing")
                    on_start = item.get("on_start")
                    on_complete = item.get("on_complete")
                    drop_if = item.get("drop_if")
                    if callable(drop_if) and drop_if():
                        continue
                    try:
                        if callable(on_start):
                            try:
                                on_start()
                            except Exception as callback_error:
                                log('warn', 'TTS on_start callback failed', callback_error)
                        if item_type == "audio_file":
                            if not isinstance(file_path, str) or not file_path:
                                continue
                            self._playback_audio_file(file_path, stream)
                        else:
                            if not isinstance(text, str) or not text:
                                continue
                            self._playback_one(
                                text,
                                stream,
                                voice if isinstance(voice, str) else None,
                                postprocessing if isinstance(postprocessing, dict) else None,
                            )
                    except Exception as e:
                        self.read_queue.put(item)
                        raise e
                    finally:
                        if callable(on_complete):
                            try:
                                on_complete()
                            except Exception as callback_error:
                                log('warn', 'TTS on_complete callback failed', callback_error)

                self._is_playing = False

                sleep(0.1)
            self._is_playing = False
            stream.stop_stream()

    @observe()
    def _playback_one(
        self,
        text: str,
        stream: pyaudio.Stream,
        voice_override: str | None = None,
        postprocessing_override: CharacterTTSPostprocessingConfig | None = None,
    ):
        # Fix numberformatting for different providers
        text = re.sub(r"\d+(,\d{3})*(\.\d+)?", self._number_to_text, text)
        text = strip_markdown.strip_markdown(text)
        # print('reading:', text)
        start_time = time()
        end_time = None
        first_chunk = True
        underflow_count = 0
        empty_buffer_available = stream.get_write_available()
        self._reset_postprocessing_state()
        postprocessing = self._get_effective_postprocessing_config(postprocessing_override)
        audio_stream = self._stream_audio(text, voice_override)
        if postprocessing:
            audio_stream = self._postprocess_audio(audio_stream, postprocessing)

        for chunk in audio_stream:
            if not end_time:
                end_time = time()
                log('debug', f'Response time TTS', end_time - start_time)
            if self.is_aborted:
                break
            try:
                if not first_chunk:
                    available = stream.get_write_available()
                    # log('debug', 'tts write available', available)
                    if available == empty_buffer_available:
                        raise IOError('underflow')
                stream.write(chunk, exception_on_underflow=False) # this may throw for various system reasons
                first_chunk = False
            except IOError as e:
                if not first_chunk:
                    underflow_count += 1
                    # log('debug', 'tts underflow detected', underflow_count)
                stream.write(chunk, exception_on_underflow=False)
        
        if underflow_count > 0:
            self.prebuffer_size *= 2
            log('debug', 'tts underflow detected, total', underflow_count, 'increasing prebuffer size to', self.prebuffer_size)


    def _reset_postprocessing_state(self) -> None:
        self._lp_state = LowpassState()
        self._hp_state = HighpassState()
        self._chorus_state = ChorusState(buffer=np.zeros(int(24_000 * 0.1), dtype=np.float32))
        self._reverb_state = ReverbState(
            impulse_response=np.zeros(0, dtype=np.float32),
            overlap=np.zeros(0, dtype=np.float32),
        )
        self._glitch_state = GlitchState(history=deque(maxlen=64))


    def _get_effective_postprocessing_config(
        self,
        postprocessing_override: CharacterTTSPostprocessingConfig | None,
    ) -> CharacterTTSPostprocessingConfig:
        if postprocessing_override is None:
            return self.postprocessing_config
        return map_character_tts_postprocessing(postprocessing_override)

    @observe()
    def _stream_audio(self, text: str, voice_override: str | None = None):
        if self.tts_model is None:
            word_count = len(text.split())
            words_per_minute = 150 * float(self.speed)
            audio_duration = word_count / words_per_minute * 60
            # generate silent audio for the duration of the text
            for _ in range(int(audio_duration * 24_000 / 1024)):
                yield b"\x00" * 1024
        else:
            try:
                selected_voice = voice_override if voice_override else self.voice
                for chunk in self.tts_model.synthesize(text, selected_voice):
                    yield chunk
            except Exception as e:
                log('error', 'TTS synthesis error', e, traceback.format_exc())
                show_chat_message('error', 'TTS synthesis error:', str(e))

    @observe()
    def _playback_audio_file(self, file_path: str, stream: pyaudio.Stream):
        resolved = Path(file_path)
        if not resolved.exists():
            raise FileNotFoundError(f"Audio file not found: {resolved}")
        frames_to_read = max(1, self.frames_per_buffer // self.sample_size)
        pcm_stream = miniaudio.stream_file(
            str(resolved),
            output_format=miniaudio.SampleFormat.SIGNED16,
            nchannels=1,
            sample_rate=24000,
            frames_to_read=frames_to_read,
        )
        for frame in pcm_stream:
            if self.is_aborted:
                break
            stream.write(frame.tobytes(), exception_on_underflow=False)

    def _number_to_text(self, match: re.Match[str]):
        """Converts numbers like 100,203.12 to one hundred thousand two hundred three point one two"""
        if len(match.group()) <= 2:
            return match.group()
        if isinstance(self.tts_model, OpenAITTSModel):
            # OpenAI TTS doesn't read large numbers correctly, so we convert them to words
            return num2words(match.group().replace(",", ""))
        else:
            return match.group()

    def _apply_time_pitch_effect(
        self,
        gen: Generator[bytes, None, None],
        effect_config: CharacterTTSTimePitchConfig,
        sample_rate: int,
    ) -> Generator[bytes, None, None]:
        if not effect_config.get('enabled'):
            yield from gen
            return

        raw_chunks = [chunk for chunk in gen if chunk]
        if not raw_chunks:
            return

        audio_parts = [
            np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
            for chunk in raw_chunks
        ]
        audio_array = np.concatenate(audio_parts)
        try:
            processed_audio = self._transform_time_pitch_audio(
                audio_array,
                effect_config,
                sample_rate,
            )
        except Exception as error:
            log('warn', 'time_pitch effect failed, using original audio', error)
            yield from raw_chunks
            return

        processed_audio = np.clip(processed_audio, -1.0, 1.0)
        processed_bytes = (processed_audio * 32767.0).astype(np.int16).tobytes()
        chunk_size = len(raw_chunks[0])

        for start in range(0, len(processed_bytes), chunk_size):
            yield processed_bytes[start:start + chunk_size]

    def _pitch_shift_chunk(
        self,
        chunk: bytes,
        pitch_shift_semitones: float,
        sample_rate: int,
    ) -> bytes:
        if not chunk or math.isclose(pitch_shift_semitones, 0.0, abs_tol=1e-6):
            return chunk

        audio_array = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
        transformed = self._transform_time_pitch_audio(
            audio_array,
            {
                'enabled': True,
                'pitch_shift_semitones': pitch_shift_semitones,
                'time_stretch': 1.0,
            },
            sample_rate,
        )
        transformed = np.clip(transformed, -1.0, 1.0)
        return (transformed * 32768.0).astype(np.int16).tobytes()

    def _split_processed_bytes(
        self,
        processed_bytes: bytes,
        chunk_lengths: list[int],
    ) -> list[bytes]:
        expected_length = sum(chunk_lengths)
        if len(processed_bytes) != expected_length:
            if len(processed_bytes) > expected_length:
                processed_bytes = processed_bytes[:expected_length]
            else:
                processed_bytes = processed_bytes + (b'\x00' * (expected_length - len(processed_bytes)))

        chunks: list[bytes] = []
        offset = 0
        for chunk_length in chunk_lengths:
            chunks.append(processed_bytes[offset:offset + chunk_length])
            offset += chunk_length
        return chunks

    def _pitch_shift_chunk_group(
        self,
        chunks: list[bytes],
        pitch_shift_semitones: float,
        sample_rate: int,
    ) -> list[bytes]:
        if not chunks:
            return []
        if math.isclose(pitch_shift_semitones, 0.0, abs_tol=1e-6):
            return list(chunks)

        combined = b''.join(chunks)
        shifted = self._pitch_shift_chunk(combined, pitch_shift_semitones, sample_rate)
        return self._split_processed_bytes(shifted, [len(chunk) for chunk in chunks])

    def _get_random_glitch_detune(self, semitone_range: float) -> float:
        return random.uniform(-abs(semitone_range), abs(semitone_range))

    def _get_glitch_pitch_hold_bytes(
        self,
        effect_config: CharacterTTSGlitchConfig,
        sample_rate: int,
    ) -> int:
        min_seconds = max(0.01, min(0.5, float(effect_config.get('min_seconds', 0.05))))
        max_seconds = max(0.01, min(0.5, float(effect_config.get('max_seconds', 0.20))))
        if max_seconds < min_seconds:
            max_seconds = min_seconds
        duration = random.uniform(min_seconds, max_seconds)
        return max(2, int(duration * sample_rate) * 2)

    def _transform_time_pitch_audio(
        self,
        audio_array: NDArray[np.float32],
        effect_config: CharacterTTSTimePitchConfig,
        sample_rate: int,
    ) -> NDArray[np.float32]:
        if audio_array.size == 0:
            return audio_array

        time_stretch = float(effect_config.get('time_stretch', 1.0))
        if time_stretch <= 0:
            time_stretch = 1.0

        pitch_shift_semitones = float(effect_config.get('pitch_shift_semitones', 0.0))
        pitch_ratio = 2.0 ** (pitch_shift_semitones / 12.0)

        if math.isclose(time_stretch, 1.0, rel_tol=1e-6, abs_tol=1e-6) and math.isclose(
            pitch_ratio,
            1.0,
            rel_tol=1e-6,
            abs_tol=1e-6,
        ):
            return audio_array

        transformed = audio_array.astype(np.float32, copy=False)
        if not math.isclose(pitch_ratio, 1.0, rel_tol=1e-6, abs_tol=1e-6):
            transformed = self._resample_audio(transformed, pitch_ratio)

        stretch_factor = time_stretch * pitch_ratio
        if not math.isclose(stretch_factor, 1.0, rel_tol=1e-6, abs_tol=1e-6):
            transformed = self._time_stretch_audio(transformed, stretch_factor, sample_rate)

        target_length = max(1, int(round(audio_array.shape[0] * time_stretch)))
        if transformed.shape[0] != target_length:
            transformed = self._resample_to_length(transformed, target_length)

        return transformed.astype(np.float32, copy=False)

    def _resample_audio(
        self,
        audio_array: NDArray[np.float32],
        rate: float,
    ) -> NDArray[np.float32]:
        if audio_array.size == 0 or rate <= 0:
            return audio_array

        target_length = max(1, int(round(audio_array.shape[0] / rate)))
        return self._resample_to_length(audio_array, target_length)

    def _resample_to_length(
        self,
        audio_array: NDArray[np.float32],
        target_length: int,
    ) -> NDArray[np.float32]:
        if target_length <= 0:
            return np.zeros(0, dtype=np.float32)
        if audio_array.size == 0:
            return np.zeros(target_length, dtype=np.float32)
        if audio_array.shape[0] == target_length:
            return audio_array.astype(np.float32, copy=True)
        if audio_array.shape[0] == 1:
            return np.full(target_length, float(audio_array[0]), dtype=np.float32)

        try:
            resampled = samplerate.resample(
                audio_array.astype(np.float32, copy=False),
                target_length / audio_array.shape[0],
                'sinc_best',
            ).astype(np.float32, copy=False)
            return self._fit_resampled_audio_length(resampled, target_length)
        except Exception as error:
            log('warn', 'Falling back to NumPy resampling for time_pitch', error)

        return self._resample_to_length_numpy(audio_array, target_length)

    def _fit_resampled_audio_length(
        self,
        audio_array: NDArray[np.float32],
        target_length: int,
    ) -> NDArray[np.float32]:
        if audio_array.shape[0] == target_length:
            return audio_array.astype(np.float32, copy=False)
        if abs(audio_array.shape[0] - target_length) <= 8:
            if audio_array.shape[0] > target_length:
                return audio_array[:target_length].astype(np.float32, copy=False)
            return np.pad(audio_array, (0, target_length - audio_array.shape[0])).astype(np.float32, copy=False)
        return self._resample_to_length_numpy(audio_array, target_length)

    def _resample_to_length_numpy(
        self,
        audio_array: NDArray[np.float32],
        target_length: int,
    ) -> NDArray[np.float32]:
        source_positions = np.arange(audio_array.shape[0], dtype=np.float64)
        target_positions = np.linspace(0, audio_array.shape[0] - 1, num=target_length, dtype=np.float64)
        return np.interp(target_positions, source_positions, audio_array).astype(np.float32)

    def _time_stretch_audio(
        self,
        audio_array: NDArray[np.float32],
        stretch_factor: float,
        sample_rate: int,
    ) -> NDArray[np.float32]:
        if audio_array.size == 0 or stretch_factor <= 0:
            return audio_array

        clipped = np.clip(audio_array, -1.0, 1.0)
        pcm_audio = (clipped * 32767.0).astype(np.int16)
        wav_buffer = BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_audio.tobytes())

        wav_buffer.seek(0)
        stretcher = AudioStretch()
        stretcher.open(file=wav_buffer, format='wav')
        stretcher.stretch(
            ratio=stretch_factor,
            double_range=stretch_factor < 0.5 or stretch_factor > 2.0,
            normal_detection=True,
        )

        stretched_audio = np.asarray(stretcher.samples, dtype=np.int16)
        expected_length = max(1, int(round(audio_array.shape[0] * stretch_factor)))
        stretched_audio = self._trim_time_stretch_padding(stretched_audio, expected_length)
        return stretched_audio.astype(np.float32) / 32768.0

    def _trim_time_stretch_padding(
        self,
        audio_array: NDArray[np.int16],
        expected_length: int,
    ) -> NDArray[np.int16]:
        if audio_array.size == 0:
            return audio_array

        peak = int(np.max(np.abs(audio_array)))
        if peak <= 0:
            return audio_array

        threshold = max(4, int(peak * 0.002))
        non_silent = np.flatnonzero(np.abs(audio_array) > threshold)
        if non_silent.size == 0:
            return audio_array

        padding_margin = min(512, max(64, expected_length // 32))
        trimmed_end = min(audio_array.shape[0], int(non_silent[-1]) + 1 + padding_margin)
        trimmed_audio = audio_array[:trimmed_end]

        if abs(trimmed_audio.shape[0] - expected_length) < abs(audio_array.shape[0] - expected_length):
            return trimmed_audio
        return audio_array

    def _apply_one_pole_recursive(
        self,
        audio_array: NDArray[np.float32],
        a: float,
        b: float,
        y_prev: float,
    ) -> tuple[NDArray[np.float32], float]:
        if audio_array.size == 0:
            return audio_array, y_prev

        indices = np.arange(audio_array.shape[0], dtype=np.float64)
        decay = np.power(float(a), indices)
        weighted_input = audio_array.astype(np.float64, copy=False) / decay
        accumulated = np.cumsum(weighted_input, dtype=np.float64)
        output = decay * (a * y_prev + b * accumulated)
        output = output.astype(np.float32, copy=False)
        return output, float(output[-1])

    def _apply_one_pole_lowpass_state(
        self,
        audio_array: NDArray[np.float32],
        sample_rate: int,
        cutoff: float,
        y_prev: float,
    ) -> tuple[NDArray[np.float32], float]:
        if cutoff <= 0 or cutoff >= sample_rate / 2 or audio_array.size == 0:
            return audio_array, y_prev

        rc = 1.0 / (2.0 * math.pi * cutoff)
        dt = 1.0 / sample_rate
        alpha = dt / (rc + dt)
        return self._apply_one_pole_recursive(audio_array, 1.0 - alpha, alpha, y_prev)

    def _apply_one_pole_highpass_state(
        self,
        audio_array: NDArray[np.float32],
        sample_rate: int,
        cutoff: float,
        y_prev: float,
        x_prev: float,
    ) -> tuple[NDArray[np.float32], float, float]:
        if cutoff <= 0 or cutoff >= sample_rate / 2 or audio_array.size == 0:
            return audio_array, y_prev, x_prev

        rc = 1.0 / (2.0 * math.pi * cutoff)
        dt = 1.0 / sample_rate
        alpha = rc / (rc + dt)
        delta = np.empty_like(audio_array)
        delta[0] = audio_array[0] - x_prev
        if audio_array.shape[0] > 1:
            delta[1:] = np.diff(audio_array)
        output, y_last = self._apply_one_pole_recursive(delta, alpha, alpha, y_prev)
        return output, y_last, float(audio_array[-1])

    def _build_reverb_impulse_response(
        self,
        sample_rate: int,
        tail_seconds: float,
    ) -> NDArray[np.float32]:
        tail_seconds = min(1.5, max(0.02, tail_seconds))
        tail_samples = max(1, int(round(tail_seconds * sample_rate)))
        impulse_response = np.zeros(tail_samples, dtype=np.float32)

        for delay_seconds, amplitude in (
            (0.012, 0.52),
            (0.021, 0.36),
            (0.034, 0.24),
            (0.055, 0.16),
        ):
            delay_samples = int(round(delay_seconds * sample_rate))
            if delay_samples < tail_samples:
                impulse_response[delay_samples] += amplitude

        late_start = min(tail_samples - 1, int(round(0.008 * sample_rate)))
        if late_start < tail_samples:
            late_time = np.arange(tail_samples - late_start, dtype=np.float32) / sample_rate
            rng = np.random.default_rng(17)
            late_noise = rng.standard_normal(late_time.shape[0]).astype(np.float32)
            late_noise -= np.convolve(
                np.pad(late_noise, (32, 32), mode='reflect'),
                np.ones(65, dtype=np.float32) / 65.0,
                mode='valid',
            ).astype(np.float32, copy=False)
            late_noise_peak = float(np.max(np.abs(late_noise)))
            if late_noise_peak > 0.0:
                late_noise /= late_noise_peak

            low_tail = np.exp(-9.5 * late_time / max(tail_seconds, 0.02)) * (
                0.018 * np.sin(2.0 * math.pi * 11.0 * late_time + 0.2)
                + 0.012 * np.sin(2.0 * math.pi * 17.0 * late_time + 0.9)
            )
            airy_tail = np.exp(-2.2 * late_time / max(tail_seconds, 0.02)) * 0.16 * late_noise
            impulse_response[late_start:] += (low_tail + airy_tail).astype(np.float32, copy=False)

        peak = float(np.max(np.abs(impulse_response)))
        if peak > 0.0:
            impulse_response /= peak / 0.6
        return impulse_response

    def _ensure_reverb_state(
        self,
        chunk_length: int,
        mix: float,
        tail_seconds: float,
        sample_rate: int,
    ) -> None:
        state = self._reverb_state
        if (
            state.chunk_length == chunk_length
            and math.isclose(state.mix, mix, rel_tol=1e-6, abs_tol=1e-6)
            and math.isclose(state.tail, tail_seconds, rel_tol=1e-6, abs_tol=1e-6)
            and state.ir_fft is not None
            and state.impulse_response.size > 0
        ):
            return

        impulse_response = self._build_reverb_impulse_response(sample_rate, tail_seconds)
        fft_size = 1 << int(math.ceil(math.log2(chunk_length + impulse_response.shape[0] - 1)))
        padded_ir = np.pad(impulse_response, (0, fft_size - impulse_response.shape[0]))
        self._reverb_state = ReverbState(
            impulse_response=impulse_response,
            overlap=np.zeros(max(0, impulse_response.shape[0] - 1), dtype=np.float32),
            ir_fft=np.fft.rfft(padded_ir).astype(np.complex128, copy=False),
            fft_size=fft_size,
            chunk_length=chunk_length,
            mix=mix,
            tail=tail_seconds,
        )

    def _apply_reverb_chunk(
        self,
        audio_array: NDArray[np.float32],
        effect_config: CharacterTTSReverbConfig,
        sample_rate: int,
    ) -> NDArray[np.float32]:
        if not effect_config.get('enabled'):
            return audio_array

        mix = min(1.0, max(0.0, float(effect_config.get('mix', 0.20))))
        tail_seconds = min(1.5, max(0.02, float(effect_config.get('tail', 0.18))))
        if mix <= 0.0 or audio_array.size == 0:
            return audio_array

        self._ensure_reverb_state(audio_array.shape[0], mix, tail_seconds, sample_rate)
        state = self._reverb_state
        if state.ir_fft is None:
            return audio_array

        padded_audio = np.pad(audio_array, (0, state.fft_size - audio_array.shape[0]))
        convolved = np.fft.irfft(
            np.fft.rfft(padded_audio) * state.ir_fft,
            state.fft_size,
        )[:audio_array.shape[0] + state.impulse_response.shape[0] - 1].astype(np.float32, copy=False)

        wet = convolved[:audio_array.shape[0]].copy()
        overlap = state.overlap
        if overlap.size > 0:
            overlap_prefix = min(audio_array.shape[0], overlap.shape[0])
            wet[:overlap_prefix] += self._apply_reverb_tail_highpass(
                overlap[:overlap_prefix].copy(),
                sample_rate,
            )

        new_overlap = convolved[audio_array.shape[0]:].copy()
        if overlap.shape[0] > audio_array.shape[0]:
            spill = overlap[audio_array.shape[0]:]
            new_overlap[:spill.shape[0]] += spill
        state.overlap = new_overlap.astype(np.float32, copy=False)
        return ((1.0 - mix) * audio_array + mix * wet).astype(np.float32, copy=False)

    def _apply_reverb_tail_highpass(
        self,
        audio_array: NDArray[np.float32],
        sample_rate: int,
    ) -> NDArray[np.float32]:
        if audio_array.size == 0:
            return audio_array

        state = self._reverb_state
        output, state.hp_y_prev, state.hp_x_prev = self._apply_one_pole_highpass_state(
            audio_array,
            sample_rate,
            REVERB_TAIL_HIGHPASS_HZ,
            state.hp_y_prev,
            state.hp_x_prev,
        )
        return output

    def _flush_reverb_tail(self) -> list[NDArray[np.float32]]:
        state = self._reverb_state
        if state.overlap.size == 0 or state.chunk_length <= 0 or state.mix <= 0.0:
            return []

        tail_signal = state.overlap * state.mix
        chunks: list[NDArray[np.float32]] = []
        threshold = 1.0 / 32768.0
        for start in range(0, tail_signal.shape[0], state.chunk_length):
            chunk = tail_signal[start:start + state.chunk_length].astype(np.float32, copy=False)
            chunk = self._apply_reverb_tail_highpass(chunk, 24_000)
            if chunk.shape[0] < state.chunk_length:
                chunk = np.pad(chunk, (0, state.chunk_length - chunk.shape[0]))
            if np.max(np.abs(chunk)) <= threshold:
                continue
            chunks.append(chunk.astype(np.float32, copy=False))

        state.overlap = np.zeros(0, dtype=np.float32)
        return chunks

    def _postprocess_audio(
        self,
        gen: Generator[bytes, None, None],
        config: CharacterTTSPostprocessingConfig,
    ) -> Generator[bytes, None, None]:
        sample_rate = 24_000
        effects = config.get('effects', {})
        glitch_config = effects.get('glitch', {})
        glitch_enabled = isinstance(glitch_config, dict) and bool(glitch_config.get('enabled'))
        glitch_detune_base = float(glitch_config.get('detune_base', GLITCH_BASE_DETUNE_SEMITONES)) if isinstance(glitch_config, dict) else GLITCH_BASE_DETUNE_SEMITONES
        glitch_detune_peak = float(glitch_config.get('detune_peak', GLITCH_BURST_DETUNE_SEMITONES)) if isinstance(glitch_config, dict) else GLITCH_BURST_DETUNE_SEMITONES
        base_glitch_detune = 0.0
        base_glitch_detune_bytes_remaining = 0
        base_glitch_chunks: list[bytes] = []

        time_pitch_config = effects.get('time_pitch', {})
        if isinstance(time_pitch_config, dict):
            gen = self._apply_time_pitch_effect(gen, time_pitch_config, sample_rate)

        def one_pole_lowpass(x: NDArray[np.float32], cutoff: float) -> NDArray[np.float32]:
            out, self._lp_state.y_prev = self._apply_one_pole_lowpass_state(
                x,
                sample_rate,
                cutoff,
                self._lp_state.y_prev,
            )
            return out

        def one_pole_highpass(x: NDArray[np.float32], cutoff: float) -> NDArray[np.float32]:
            out, self._hp_state.y_prev, self._hp_state.x_prev = self._apply_one_pole_highpass_state(
                x,
                sample_rate,
                cutoff,
                self._hp_state.y_prev,
                self._hp_state.x_prev,
            )
            return out

        def apply_distortion(
            x: NDArray[np.float32],
            effect_config: CharacterTTSDistortionConfig,
        ) -> NDArray[np.float32]:
            if not effect_config.get('enabled'):
                return x

            drive = float(effect_config.get('drive', 1.0))
            mode = effect_config.get('mode', 'tanh')
            clip_level = float(effect_config.get('clip', 0.95))
            if drive != 1.0:
                x = x * drive
            if mode == 'tanh':
                return np.tanh(x)
            if clip_level <= 0:
                return x
            return np.clip(x, -clip_level, clip_level) / clip_level

        def apply_chorus(
            x: NDArray[np.float32],
            effect_config: CharacterTTSChorusConfig,
        ) -> NDArray[np.float32]:
            if not effect_config.get('enabled'):
                return x

            delay_ms = float(effect_config.get('delay_ms', 25.0))
            depth_ms = float(effect_config.get('depth_ms', 12.0))
            rate_hz = float(effect_config.get('rate_hz', 0.25))
            mix = float(effect_config.get('mix', 0.5))
            max_delay_ms = delay_ms + depth_ms + 5.0
            history_length = int(math.ceil(sample_rate * max_delay_ms / 1000.0)) + 4
            if self._chorus_state.buffer.shape[0] != history_length:
                resized_history = np.zeros(history_length, dtype=np.float32)
                history = self._chorus_state.buffer
                copy_length = min(history_length, history.shape[0])
                if copy_length > 0:
                    resized_history[-copy_length:] = history[-copy_length:]
                self._chorus_state.buffer = resized_history

            history = self._chorus_state.buffer
            phase = self._chorus_state.phase
            sample_indices = np.arange(x.shape[0], dtype=np.float64)
            phase_steps = np.mod(phase + sample_indices * (rate_hz / sample_rate), 1.0)
            current_delay_ms = delay_ms + np.sin(2.0 * math.pi * phase_steps) * depth_ms
            delay_samples = sample_rate * current_delay_ms / 1000.0

            source = np.concatenate((history, x.astype(np.float32, copy=False)))
            read_positions = history.shape[0] + sample_indices - delay_samples
            read_positions = np.clip(read_positions, 0.0, source.shape[0] - 2.0)
            index_0 = np.floor(read_positions).astype(np.int32)
            fraction = read_positions - index_0
            delayed = (
                (1.0 - fraction) * source[index_0]
                + fraction * source[index_0 + 1]
            ).astype(np.float32, copy=False)

            self._chorus_state.buffer = source[-history_length:].astype(np.float32, copy=False)
            self._chorus_state.phase = float(np.mod(phase + x.shape[0] * (rate_hz / sample_rate), 1.0))
            return ((1.0 - mix) * x + mix * delayed).astype(np.float32, copy=False)

        def apply_glitch(
            processed_chunk: bytes,
            effect_config: CharacterTTSGlitchConfig,
        ) -> list[bytes]:
            if not effect_config.get('enabled'):
                return []

            history = self._glitch_state.history
            probability = float(effect_config.get('probability', 0.0))
            if not history or random.random() >= probability:
                history.append(processed_chunk)
                return []

            extras: list[bytes] = []
            use_time_based_glitch = (
                'min_seconds' in effect_config
                or 'max_seconds' in effect_config
            )
            if use_time_based_glitch:
                min_seconds = max(0.01, min(0.5, float(effect_config.get('min_seconds', 0.05))))
                max_seconds = max(0.01, min(0.5, float(effect_config.get('max_seconds', 0.25))))
                if max_seconds < min_seconds:
                    max_seconds = min_seconds
                duration = random.uniform(min_seconds, max_seconds)
                bytes_needed = max(2, int(duration * sample_rate) * 2)
                combined = b''.join(history)
                if len(combined) >= bytes_needed:
                    extra_detune = self._get_random_glitch_detune(glitch_detune_peak)
                    extras.append(
                        self._pitch_shift_chunk(
                            combined[-bytes_needed:],
                            extra_detune,
                            sample_rate,
                        )
                    )
            else:
                repeat_min = int(effect_config.get('repeat_min', 2))
                repeat_max = int(effect_config.get('repeat_max', 4))
                if repeat_max < repeat_min:
                    repeat_max = repeat_min
                repeats = max(1, random.randint(repeat_min, repeat_max))
                last_chunk = history[-1]
                extra_detune = self._get_random_glitch_detune(glitch_detune_peak)
                extras.append(
                    self._pitch_shift_chunk(
                        last_chunk * repeats,
                        extra_detune,
                        sample_rate,
                    )
                )

            history.append(processed_chunk)
            return extras

        def flush_base_glitch_chunks() -> Generator[bytes, None, None]:
            nonlocal base_glitch_chunks
            if not base_glitch_chunks:
                return

            shifted_chunks = self._pitch_shift_chunk_group(
                base_glitch_chunks,
                base_glitch_detune,
                sample_rate,
            )
            base_glitch_chunks = []

            for shifted_chunk in shifted_chunks:
                yield shifted_chunk
                if isinstance(glitch_config, dict):
                    for extra in apply_glitch(shifted_chunk, glitch_config):
                        yield extra

        for chunk in gen:
            if not chunk:
                continue

            audio_array = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
            audio_array *= float(config.get('volume', 1.0))

            lowpass_config = effects.get('lowpass', {})
            if isinstance(lowpass_config, dict) and lowpass_config.get('enabled'):
                audio_array = one_pole_lowpass(
                    audio_array,
                    float(lowpass_config.get('cutoff', 5000.0)),
                )

            highpass_config = effects.get('highpass', {})
            if isinstance(highpass_config, dict) and highpass_config.get('enabled'):
                audio_array = one_pole_highpass(
                    audio_array,
                    float(highpass_config.get('cutoff', 120.0)),
                )

            distortion_config = effects.get('distortion', {})
            if isinstance(distortion_config, dict):
                audio_array = apply_distortion(audio_array, distortion_config)

            chorus_config = effects.get('chorus', {})
            if isinstance(chorus_config, dict):
                audio_array = apply_chorus(audio_array, chorus_config)

            reverb_config = effects.get('reverb', {})
            if isinstance(reverb_config, dict):
                audio_array = self._apply_reverb_chunk(audio_array, reverb_config, sample_rate)

            audio_array = np.clip(audio_array, -1.0, 1.0)
            processed_chunk = (audio_array * 32768).astype(np.int16).tobytes()

            if glitch_enabled:
                if base_glitch_detune_bytes_remaining <= 0:
                    yield from flush_base_glitch_chunks()
                    base_glitch_detune = self._get_random_glitch_detune(glitch_detune_base)
                    base_glitch_detune_bytes_remaining = self._get_glitch_pitch_hold_bytes(
                        glitch_config,
                        sample_rate,
                    )
                base_glitch_chunks.append(processed_chunk)
                base_glitch_detune_bytes_remaining -= len(processed_chunk)
                if base_glitch_detune_bytes_remaining <= 0:
                    yield from flush_base_glitch_chunks()
                continue

            yield processed_chunk

            if isinstance(glitch_config, dict):
                for extra in apply_glitch(processed_chunk, glitch_config):
                    yield extra

        if glitch_enabled:
            yield from flush_base_glitch_chunks()

        for reverb_tail_chunk in self._flush_reverb_tail():
            reverb_tail_chunk = np.clip(reverb_tail_chunk, -1.0, 1.0)
            processed_chunk = (reverb_tail_chunk * 32768).astype(np.int16).tobytes()

            if glitch_enabled:
                if base_glitch_detune_bytes_remaining <= 0:
                    yield from flush_base_glitch_chunks()
                    base_glitch_detune = self._get_random_glitch_detune(glitch_detune_base)
                    base_glitch_detune_bytes_remaining = self._get_glitch_pitch_hold_bytes(
                        glitch_config,
                        sample_rate,
                    )
                base_glitch_chunks.append(processed_chunk)
                base_glitch_detune_bytes_remaining -= len(processed_chunk)
                if base_glitch_detune_bytes_remaining <= 0:
                    yield from flush_base_glitch_chunks()
                continue

            yield processed_chunk

        if glitch_enabled:
            yield from flush_base_glitch_chunks()

    def say(
        self,
        text: str,
        *,
        voice: str | None = None,
        postprocessing: CharacterTTSPostprocessingConfig | None = None,
        on_start: Callable[[], None] | None = None,
        on_complete: Callable[[], None] | None = None,
        drop_if: Callable[[], bool] | None = None,
    ):
        self.read_queue.put(
            {
                "text": text,
                "voice": voice,
                "postprocessing": postprocessing,
                "on_start": on_start,
                "on_complete": on_complete,
                "drop_if": drop_if,
            },
        )

    def play_audio_file(
        self,
        file_path: str,
        *,
        on_start: Callable[[], None] | None = None,
        on_complete: Callable[[], None] | None = None,
        drop_if: Callable[[], bool] | None = None,
    ):
        self.read_queue.put(
            {
                "type": "audio_file",
                "file_path": file_path,
                "text": "",
                "voice": None,
                "on_start": on_start,
                "on_complete": on_complete,
                "drop_if": drop_if,
            },
        )

    def set_postprocessing_config(
        self,
        postprocessing_config: CharacterTTSPostprocessingConfig | None,
    ) -> None:
        self.postprocessing_config = map_character_tts_postprocessing(
            postprocessing_config or get_default_character_tts_postprocessing(),
        )

    def abort(self):
        while not self.read_queue.empty():
            self.read_queue.get()

        self.is_aborted = True

    def get_is_playing(self):
        return self._is_playing or not self.read_queue.empty()

    def has_queued_items(self) -> bool:
        return not self.read_queue.empty()

    @observe()
    def wait_for_completion(self):
        while self.get_is_playing():
            sleep(0.2)

    def quit(self):
        pass


if __name__ == "__main__":
    import os
    model = OpenAITTSModel(base_url='https://api.openai.com/v1', model_name="tts-1", api_key=os.environ.get('OPENAI_API_KEY'))
    tts = TTS(model, "nova", speed=1.0, postprocessing_config=None, output_device="pulse")
    tts.say("Hello, this is a test of the text to speech system.", postprocessing={
        "volume": 1.0,
        "effects": {
            "time_pitch": {
                "enabled": True,
                "pitch_shift_semitones": -4.0,
                "time_stretch": 1
            },
            "reverb": {
                "enabled": True,
                "tail": 0.2,
                "mix": 0.2
            }
        }
    })
    tts.wait_for_completion()
