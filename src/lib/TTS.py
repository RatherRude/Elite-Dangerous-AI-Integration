from __future__ import annotations
import queue
import re
import threading
import traceback
from time import sleep, time
from typing import Generator, Iterator, Literal, final, TypedDict, Optional, Dict, Any, cast
import numpy as np
import math
import random
from collections import deque
from dataclasses import dataclass
from numpy.typing import NDArray

import edge_tts
import miniaudio
import openai
import pyaudio
import strip_markdown
from num2words import num2words

from .Logger import log, show_chat_message

# TypedDicts for effect configurations
class DistortionConfig(TypedDict, total=False):
    enabled: bool
    drive: float
    clip: float
    mode: Literal['tanh', 'hard']

class FilterConfig(TypedDict, total=False):
    enabled: bool
    cutoff: float

class ChorusConfig(TypedDict, total=False):
    enabled: bool
    delay_ms: float
    depth_ms: float
    rate_hz: float
    mix: float

class GlitchConfig(TypedDict, total=False):
    enabled: bool
    probability: float
    repeat_min: int  # legacy support (repeat previous chunk N times)
    repeat_max: int  # legacy support
    min_seconds: float  # new: min glitch segment duration (0.01s - 0.5s)
    max_seconds: float  # new: max glitch segment duration (0.01s - 0.5s)

class EffectsConfig(TypedDict, total=False):
    distortion: DistortionConfig
    lowpass: FilterConfig
    highpass: FilterConfig
    chorus: ChorusConfig
    glitch: GlitchConfig

class AudioPostprocessing(TypedDict, total=False):
    """Configuration for audio post-processing with type-safe effect configs."""
    volume: float
    effects: EffectsConfig

class AudioChunk(TypedDict):
    type: Literal['audio']
    data: bytes

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
class Mp3Stream(miniaudio.StreamableSource):
    def __init__(self, gen: Iterator[AudioChunk], prebuffer_size: int = 4) -> None:
        super().__init__()
        self.gen = gen
        self.data = b""
        self.offset = 0
        self.prebuffer_size = prebuffer_size

    def read(self, num_bytes: int) -> bytes:
        data = b""
        try:
            while True:
                chunk = self.gen.__next__()
                if isinstance(chunk, dict) and chunk["type"] == "audio":
                    data += chunk["data"]
                if len(data) >= self.prebuffer_size*720: # TODO: Find a good value here
                    return data
        except StopIteration:
            self.close()
        return data

@final
class TTS:
    def __init__(self, openai_client: openai.OpenAI | None = None, provider: Literal['openai', 'edge-tts', 'custom', 'none', 'local-ai-server'] | str ='openai', voice: str = "nova", voice_instructions: str = "", model: str ='tts-1',  speed: str | float = 1, output_device: str | None = None, postprocess_config: AudioPostprocessing | None = None):
        self.openai_client = openai_client
        self.provider = provider
        self.model = model
        self.voice = voice
        self.voice_instructions = voice_instructions
        self.speed = speed
        self.p = pyaudio.PyAudio()
        self.output_device = output_device
        self.read_queue: queue.Queue[str] = queue.Queue()
        self.is_aborted = False
        self._is_playing = False
        self.prebuffer_size = 4
        self.output_format = pyaudio.paInt16
        self.frames_per_buffer = 1024
        self.sample_size = self.p.get_sample_size(self.output_format)
        self.postprocess_config: AudioPostprocessing = postprocess_config if postprocess_config else AudioPostprocessing(
            volume=1.0, effects=EffectsConfig(
                chorus= ChorusConfig(enabled=True, delay_ms=25.0, depth_ms=12.0, rate_hz=0.25, mix=0.5),
                distortion=DistortionConfig(enabled=True, drive=2.0, clip=0.20, mode='tanh'),
                lowpass=FilterConfig(enabled=False, cutoff=5000.0),
                highpass=FilterConfig(enabled=False, cutoff=120.0),
                glitch=GlitchConfig(
                    enabled=True, probability=0.04, 
                    repeat_min=2, repeat_max=4,
                    min_seconds=0.05, max_seconds=0.20
                )  # updated defaults
            ))
        self._lp_state = LowpassState()
        self._hp_state = HighpassState()
        self._chorus_state = ChorusState(buffer=np.zeros(int(24000 * 0.1), dtype=np.float32))
        self._glitch_state = GlitchState(history=deque(maxlen=64))
        thread = threading.Thread(target=self._playback_thread)
        thread.daemon = True
        thread.start()

    def _get_output_device_index(self) -> int | None:
        for i in range(self.p.get_device_count()):
            dev_info = self.p.get_device_info_by_index(i)
            name = str(dev_info.get('name', ''))
            if self.output_device and self.output_device in name:
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
                    text = self.read_queue.get()
                    # Fix numberformatting for different providers
                    text = re.sub(r"\d+(,\d{3})*(\.\d+)?", self._number_to_text, text)
                    text = strip_markdown.strip_markdown(text)
                    # print('reading:', text)
                    try:
                        start_time = time()
                        end_time = None
                        first_chunk = True
                        underflow_count = 0
                        empty_buffer_available = stream.get_write_available()
                        raw_gen = self._stream_audio(text)
                        processed_gen = self._postprocess_audio(raw_gen, self.postprocess_config)
                        for chunk in processed_gen:
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
                            
                    except Exception as e:
                        self.read_queue.put(text)
                        raise e

                self._is_playing = False

                sleep(0.1)
            self._is_playing = False
            stream.stop_stream()

    def _stream_audio(self, text: str) -> Generator[bytes, None, None]:
        if self.provider == 'none':
            word_count = len(text.split())
            words_per_minute = 150 * float(self.speed)
            audio_duration = word_count / words_per_minute * 60
            for _ in range(int(audio_duration * 24_000 / 1024)):
                yield b"\x00" * 1024
        elif self.provider == "edge-tts":
            rate = f"+{int((float(self.speed) - 1) * 100)}%" if float(self.speed) > 1 else f"-{int((1 - float(self.speed)) * 100)}%"
            response = edge_tts.Communicate(text, voice=self.voice, rate=rate)
            pcm_stream = miniaudio.stream_any(
                source=Mp3Stream(cast(Iterator[AudioChunk], response.stream_sync()), self.prebuffer_size),
                source_format=miniaudio.FileFormat.MP3,
                output_format=miniaudio.SampleFormat.SIGNED16,
                nchannels=1,
                sample_rate=24000,
                frames_to_read=1024 // self.p.get_sample_size(pyaudio.paInt16)
            )
            for i in pcm_stream:
                yield i.tobytes()
        elif self.openai_client:
            try:
                with self.openai_client.audio.speech.with_streaming_response.create(
                        model=self.model,
                        voice=self.voice,
                        input=text,
                        response_format="pcm",
                        instructions=self.voice_instructions,
                        speed=float(self.speed)
                ) as response:
                    for chunk in response.iter_bytes(1024):
                        yield chunk
            except openai.APIStatusError as e:
                log("debug", "TTS error request:", e.request.method, e.request.url, e.request.headers, e.request.read().decode('utf-8', errors='replace'))
                log("debug", "TTS error response:", e.response.status_code, e.response.headers, e.response.read().decode('utf-8', errors='replace'))
                try:
                    error: dict[str, object] = e.body[0] if hasattr(e, 'body') and e.body and isinstance(e.body, list) else e.body  # type: ignore[assignment]
                    message = cast(str, error.get('error', {})).get('message', e.body if e.body else 'Unknown error') if isinstance(error, dict) else 'Unknown error'
                except Exception:
                    message = e.message
                show_chat_message('error', f'TTS {e.response.reason_phrase}:', message)
        else:
            raise ValueError('No TTS client provided')

    def _number_to_text(self, match: re.Match[str]) -> str:
        if len(match.group()) <= 2:
            return match.group()
        if self.provider == "openai":
            return str(num2words(match.group().replace(",", "")))
        return match.group()

    def _postprocess_audio(self, gen: Generator[bytes, None, None], config: AudioPostprocessing):
        sample_rate = 24_000
        effects: EffectsConfig = config.get('effects', {})

        def one_pole_lowpass(x: np.ndarray, cutoff: float) -> np.ndarray:
            if cutoff <= 0 or cutoff >= sample_rate/2:
                return x
            rc = 1.0 / (2 * math.pi * cutoff)
            dt = 1.0 / sample_rate
            alpha = dt / (rc + dt)
            y_prev = self._lp_state.y_prev
            out = np.empty_like(x)
            for i in range(x.shape[0]):
                s = float(x[i])
                y_prev = y_prev + alpha * (s - y_prev)
                out[i] = y_prev
            self._lp_state.y_prev = y_prev
            return out

        def one_pole_highpass(x: np.ndarray, cutoff: float) -> np.ndarray:
            if cutoff <= 0 or cutoff >= sample_rate/2:
                return x
            rc = 1.0 / (2 * math.pi * cutoff)
            dt = 1.0 / sample_rate
            alpha = rc / (rc + dt)
            y_prev = self._hp_state.y_prev
            x_prev = self._hp_state.x_prev
            out = np.empty_like(x)
            for i in range(x.shape[0]):
                s = float(x[i])
                y_prev = alpha * (y_prev + s - x_prev)
                out[i] = y_prev
                x_prev = s
            self._hp_state.y_prev = y_prev
            self._hp_state.x_prev = x_prev
            return out

        def apply_distortion(x: np.ndarray, eff_cfg: DistortionConfig):
            if not eff_cfg.get('enabled'): return x
            drive = float(eff_cfg.get('drive', 1.0))
            mode = eff_cfg.get('mode', 'tanh')
            clip_level = float(eff_cfg.get('clip', 0.95))
            if drive != 1.0:
                x = x * drive
            if mode == 'tanh':
                x = np.tanh(x)
            else:  # hard clip
                x = np.clip(x, -clip_level, clip_level)
                x = x / clip_level  # normalize
            return x

        def apply_chorus(x: np.ndarray, eff_cfg: ChorusConfig):
            if not eff_cfg.get('enabled'): return x
            delay_ms = float(eff_cfg.get('delay_ms', 25.0))
            depth_ms = float(eff_cfg.get('depth_ms', 12.0))
            rate_hz = float(eff_cfg.get('rate_hz', 0.25))
            mix = float(eff_cfg.get('mix', 0.5))
            max_delay_ms = delay_ms + depth_ms + 5.0
            needed = int(sample_rate * max_delay_ms / 1000.0) + x.shape[0] + 4
            if self._chorus_state.buffer.shape[0] < needed:
                self._chorus_state.buffer = np.zeros(needed, dtype=np.float32)
                self._chorus_state.index = 0
            buf = self._chorus_state.buffer
            buf_idx = self._chorus_state.index
            phase = self._chorus_state.phase
            out = np.empty_like(x)
            for i in range(x.shape[0]):
                s = float(x[i])
                mod = math.sin(2 * math.pi * phase)
                current_delay_ms = delay_ms + mod * depth_ms
                delay_samples = sample_rate * current_delay_ms / 1000.0
                read_pos = buf_idx - delay_samples
                while read_pos < 0:
                    read_pos += buf.shape[0]
                i0 = int(read_pos) % buf.shape[0]
                i1 = (i0 + 1) % buf.shape[0]
                frac = read_pos - math.floor(read_pos)
                delayed = (1 - frac) * buf[i0] + frac * buf[i1]
                buf[buf_idx % buf.shape[0]] = s
                out[i] = (1 - mix) * s + mix * delayed
                buf_idx = (buf_idx + 1) % buf.shape[0]
                phase += rate_hz / sample_rate
                if phase >= 1.0:
                    phase -= 1.0
            self._chorus_state.index = buf_idx
            self._chorus_state.phase = phase
            return out

        def apply_glitch(processed_chunk_bytes: bytes, eff_cfg: GlitchConfig):
            if not eff_cfg.get('enabled'):
                return []
            prob = float(eff_cfg.get('probability', 0.0))
            hist = self._glitch_state.history
            if not hist or random.random() >= prob:
                hist.append(processed_chunk_bytes)
                return []
            # Determine if we use new time-based config or legacy repeat counts
            use_time = ('min_seconds' in eff_cfg) or ('max_seconds' in eff_cfg)
            outputs: list[bytes] = []
            if use_time:
                # Time-based glitch: extract a slice of recent audio of random duration
                min_sec = float(eff_cfg.get('min_seconds', 0.05))
                max_sec = float(eff_cfg.get('max_seconds', 0.25))
                # Clamp to allowed range
                min_sec = max(0.01, min(0.5, min_sec))
                max_sec = max(0.01, min(0.5, max_sec))
                if max_sec < min_sec:
                    max_sec = min_sec
                duration = random.uniform(min_sec, max_sec)
                sample_rate = 24_000
                samples_needed = max(1, int(duration * sample_rate))
                bytes_needed = samples_needed * 2  # 16-bit mono
                # Concatenate history (limit to a reasonable size)
                # history holds last up to ~64 chunks (~>1.2s); enough for 0.5s
                combined = b''.join(hist)
                if len(combined) >= bytes_needed:
                    segment = combined[-bytes_needed:]
                    # Ensure even length (already) and append
                    outputs.append(segment)
            else:
                # Legacy behavior: repeat last chunk N times
                rmin = int(eff_cfg.get('repeat_min', 2))
                rmax = int(eff_cfg.get('repeat_max', 4))
                if rmax < rmin:
                    rmax = rmin
                repeats = max(1, random.randint(rmin, rmax))
                last = hist[-1]
                for _ in range(repeats):
                    outputs.append(last)
            hist.append(processed_chunk_bytes)
            return outputs

        # Processing loop
        for chunk in gen:
            if not chunk:
                continue
            audio_array: np.ndarray = cast(np.ndarray, np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0)
            audio_array *= float(config.get('volume', 1.0))
            lp_cfg: FilterConfig = cast(FilterConfig, effects.get('lowpass', {}))
            if lp_cfg.get('enabled'):
                audio_array = one_pole_lowpass(audio_array, float(lp_cfg.get('cutoff', 5000.0)))
            hp_cfg: FilterConfig = cast(FilterConfig, effects.get('highpass', {}))
            if hp_cfg.get('enabled'):
                audio_array = one_pole_highpass(audio_array, float(hp_cfg.get('cutoff', 120.0)))
            audio_array = apply_distortion(audio_array, cast(DistortionConfig, effects.get('distortion', {})))
            audio_array = apply_chorus(audio_array, cast(ChorusConfig, effects.get('chorus', {})))
            audio_array = np.clip(audio_array, -1.0, 1.0)
            processed_chunk = (audio_array * 32768).astype(np.int16).tobytes()
            yield processed_chunk
            for extra in apply_glitch(processed_chunk, cast(GlitchConfig, effects.get('glitch', {}))):
                yield extra

    def set_postprocess_config(self, new_conf: dict[str, object]):
        if not isinstance(new_conf, dict):
            return
        if 'volume' in new_conf:
            try:
                self.postprocess_config['volume'] = float(cast(Any, new_conf['volume']))  # type: ignore[assignment]
            except Exception:
                pass
        if 'effects' in new_conf and isinstance(new_conf['effects'], dict):
            self.postprocess_config.setdefault('effects', cast(EffectsConfig, {})).update(cast(EffectsConfig, new_conf['effects']))  # type: ignore[arg-type]

    def say(self, text: str):
        self.read_queue.put(text)

    def abort(self):
        while not self.read_queue.empty():
            self.read_queue.get()

        self.is_aborted = True

    def get_is_playing(self):
        return self._is_playing or not self.read_queue.empty()

    def wait_for_completion(self):
        while self.get_is_playing():
            sleep(0.2)

    def quit(self):
        pass


if __name__ == "__main__":
    openai_audio = openai.OpenAI(base_url="http://localhost:8080/v1", api_key='x')

    tts = TTS(openai_audio, provider="openai", model="tts-1", voice="nova", voice_instructions="", speed=1, output_device="Speakers", postprocess_config={"volume": 0.9})


    text = """The missile knows where it is at all times. It knows this because it knows where it isn't. By subtracting where it is from where it isn't, or where it isn't from where it is (whichever is greater), it obtains a difference, or deviation. The guidance subsystem uses deviations to generate corrective commands to drive the missile from a position where it is to a position where it isn't, and arriving at a position where it wasn't, it now is. Consequently, the position where it is, is now the position that it wasn't, and it follows that the position that it was, is now the position that it isn't.
In the event that the position that it is in is not the position that it wasn't, the system has acquired a variation, the variation being the difference between where the missile is, and where it wasn't. If variation is considered to be a significant factor, it too may be corrected by the GEA. However, the missile must also know where it was.
The missile guidance computer scenario works as follows. Because a variation has modified some of the information the missile has obtained, it is not sure just where it is. However, it is sure where it isn't, within reason, and it knows where it was. It now subtracts where it should be from where it wasn't, or vice-versa, and by differentiating this from the algebraic sum of where it shouldn't be, and where it was, it is able to obtain the deviation and its variation, which is called error."""

    for line in text.split("\n"):
        if not line or line.isspace():
            sleep(2)
            continue
        print(line)
        tts.say(line.strip())
        while tts.get_is_playing():
            sleep(0.1)

    tts.abort()
    # result2 = tts.say("Is this actually working?")

    while True:
        sleep(0.25)
