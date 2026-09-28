import threading
import traceback
from time import sleep, time
from typing import Any, Generator, Iterable, override

import edge_tts
import miniaudio

from lib.Logger import log
from lib.Models import TTSModel
from lib.PluginBase import PluginBase, PluginManifest


EDGE_TTS_PLUGIN_GUID = "e2d57ec0-56f5-45de-88ed-621d4a28d7b5"
EDGE_TTS_MODEL = "edge-tts"
EDGE_TTS_VOICE = "en-US-AvaMultilingualNeural"


class Mp3Stream(miniaudio.StreamableSource):
    def __init__(self, gen: Generator, prebuffer_size=4, initial_timeout: float = 10.0, chunk_timeout: float = 5.0) -> None:
        super().__init__()
        self.gen = gen
        self.prebuffer_size = prebuffer_size
        self.initial_timeout = initial_timeout
        self.chunk_timeout = chunk_timeout
        self.buffer = bytearray()
        self._done = False
        self._closed = False
        self._first_chunk = False
        self._last_chunk_time = time()
        threading.Thread(target=self._produce, daemon=True).start()

    def _produce(self):
        try:
            for ev in self.gen:
                if self._closed:
                    break
                if isinstance(ev, dict) and ev.get('type') == 'audio':
                    self.buffer.extend(ev['data'])
                    self._first_chunk = True
                    self._last_chunk_time = time()
        except Exception as e:
            log('error', 'Mp3Stream producer exception', e, traceback.format_exc())
            raise e
        finally:
            self._done = True

    def close(self):  # type: ignore[override]
        self._closed = True
        return super().close()

    def read(self, num_bytes: int) -> bytes:
        if self._closed:
            return b''
        out = bytearray()
        need = max(self.prebuffer_size * 720, num_bytes)
        while len(out) < need:
            timeout = self.initial_timeout if not self._first_chunk else self.chunk_timeout
            if (not self._done) and (time() - self._last_chunk_time > timeout):
                log('warn', 'TTS Stream timeout (initial)' if not self._first_chunk else 'TTS Stream timeout (gap)')
                self.close()
                raise IOError('TTS Stream timeout')
            if self.buffer:
                take = min(len(self.buffer), need - len(out))
                out.extend(self.buffer[:take])
                del self.buffer[:take]
            elif self._done:
                break
            else:
                sleep(0.01)
        return bytes(out)


class EdgeTTSModel(TTSModel):
    def __init__(self, model_name: str, speed: float = 1.0, provider_name: str | None = None):
        super().__init__(model_name, provider_name=provider_name)
        self.speed = speed
        self.prebuffer_size = 4

    def synthesize(self, text: str, voice: str) -> Iterable[bytes]:
        rate = f"+{int((float(self.speed) - 1) * 100)}%" if float(self.speed) > 1 else f"-{int((1 - float(self.speed)) * 100)}%"
        response = edge_tts.Communicate(text, voice=voice, rate=rate)

        pcm_stream = miniaudio.stream_any(
            source=Mp3Stream(response.stream_sync(), self.prebuffer_size),
            source_format=miniaudio.FileFormat.MP3,
            output_format=miniaudio.SampleFormat.SIGNED16,
            nchannels=1,
            sample_rate=24000,
            frames_to_read=1024 // 2
        )

        for chunk in pcm_stream:
            yield chunk.tobytes()


class EdgeTTSPlugin(PluginBase):
    @override
    def __init__(self, plugin_manifest: PluginManifest):
        super().__init__(plugin_manifest)
        self.model_providers = [{
            "kind": "tts",
            "id": "tts",
            "label": "Edge TTS",
            "slots": ["tts"],
            "settings_config": [],
        }]  # type: ignore[assignment]

    @override
    def create_model(self, provider_id: str, settings: dict[str, Any]):
        if provider_id != "tts":
            raise ValueError(f"Unknown Edge TTS model provider: {provider_id}")
        return EdgeTTSModel(EDGE_TTS_MODEL, provider_name="edge-tts")
