import queue
import math
import re
import random
import threading
import traceback
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from time import sleep, time
from typing import Any, Callable, Generator, Optional, final

import miniaudio
import numpy as np
import pyaudio
import strip_markdown
from numpy.typing import NDArray
from num2words import num2words

from .Config import (
    CharacterTTSChorusConfig,
    CharacterTTSDistortionConfig,
    CharacterTTSGlitchConfig,
    CharacterTTSPostprocessingConfig,
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
    index: int = 0
    phase: float = 0.0


@dataclass
class GlitchState:
    history: deque[bytes]


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

    def _postprocess_audio(
        self,
        gen: Generator[bytes, None, None],
        config: CharacterTTSPostprocessingConfig,
    ) -> Generator[bytes, None, None]:
        sample_rate = 24_000
        effects = config.get('effects', {})

        def one_pole_lowpass(x: NDArray[np.float32], cutoff: float) -> NDArray[np.float32]:
            if cutoff <= 0 or cutoff >= sample_rate / 2:
                return x
            rc = 1.0 / (2 * math.pi * cutoff)
            dt = 1.0 / sample_rate
            alpha = dt / (rc + dt)
            y_prev = self._lp_state.y_prev
            out = np.empty_like(x)
            for i in range(x.shape[0]):
                sample = float(x[i])
                y_prev = y_prev + alpha * (sample - y_prev)
                out[i] = y_prev
            self._lp_state.y_prev = y_prev
            return out

        def one_pole_highpass(x: NDArray[np.float32], cutoff: float) -> NDArray[np.float32]:
            if cutoff <= 0 or cutoff >= sample_rate / 2:
                return x
            rc = 1.0 / (2 * math.pi * cutoff)
            dt = 1.0 / sample_rate
            alpha = rc / (rc + dt)
            y_prev = self._hp_state.y_prev
            x_prev = self._hp_state.x_prev
            out = np.empty_like(x)
            for i in range(x.shape[0]):
                sample = float(x[i])
                y_prev = alpha * (y_prev + sample - x_prev)
                out[i] = y_prev
                x_prev = sample
            self._hp_state.y_prev = y_prev
            self._hp_state.x_prev = x_prev
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
            needed = int(sample_rate * max_delay_ms / 1000.0) + x.shape[0] + 4
            if self._chorus_state.buffer.shape[0] < needed:
                self._chorus_state.buffer = np.zeros(needed, dtype=np.float32)
                self._chorus_state.index = 0

            buffer = self._chorus_state.buffer
            buffer_index = self._chorus_state.index
            phase = self._chorus_state.phase
            out = np.empty_like(x)

            for i in range(x.shape[0]):
                sample = float(x[i])
                mod = math.sin(2 * math.pi * phase)
                current_delay_ms = delay_ms + mod * depth_ms
                delay_samples = sample_rate * current_delay_ms / 1000.0
                read_pos = buffer_index - delay_samples
                while read_pos < 0:
                    read_pos += buffer.shape[0]
                index_0 = int(read_pos) % buffer.shape[0]
                index_1 = (index_0 + 1) % buffer.shape[0]
                fraction = read_pos - math.floor(read_pos)
                delayed = (1 - fraction) * buffer[index_0] + fraction * buffer[index_1]
                buffer[buffer_index % buffer.shape[0]] = sample
                out[i] = (1 - mix) * sample + mix * delayed
                buffer_index = (buffer_index + 1) % buffer.shape[0]
                phase += rate_hz / sample_rate
                if phase >= 1.0:
                    phase -= 1.0

            self._chorus_state.index = buffer_index
            self._chorus_state.phase = phase
            return out

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
                    extras.append(combined[-bytes_needed:])
            else:
                repeat_min = int(effect_config.get('repeat_min', 2))
                repeat_max = int(effect_config.get('repeat_max', 4))
                if repeat_max < repeat_min:
                    repeat_max = repeat_min
                repeats = max(1, random.randint(repeat_min, repeat_max))
                last_chunk = history[-1]
                extras.extend(last_chunk for _ in range(repeats))

            history.append(processed_chunk)
            return extras

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

            audio_array = np.clip(audio_array, -1.0, 1.0)
            processed_chunk = (audio_array * 32768).astype(np.int16).tobytes()
            yield processed_chunk

            glitch_config = effects.get('glitch', {})
            if isinstance(glitch_config, dict):
                for extra in apply_glitch(processed_chunk, glitch_config):
                    yield extra

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
    # Mocking for test
    pass
