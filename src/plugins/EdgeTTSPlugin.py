import asyncio
import threading
import traceback
from contextlib import aclosing
from time import monotonic
from typing import Any, AsyncGenerator, Generator, override

import edge_tts
import miniaudio
from edge_tts.typing import TTSChunk

from lib.Logger import log
from lib.Models import TTSModel
from lib.PluginBase import PluginBase, PluginManifest


EDGE_TTS_PLUGIN_GUID = "e2d57ec0-56f5-45de-88ed-621d4a28d7b5"
EDGE_TTS_MODEL = "edge-tts"
EDGE_TTS_VOICE = "en-US-AvaMultilingualNeural"

EDGE_TTS_VOICES = [
    ("en-US-AvaMultilingualNeural", "Ava Multilingual (Female)"),
    ("en-US-AndrewMultilingualNeural", "Andrew Multilingual (Male)"),
    ("en-US-EmmaMultilingualNeural", "Emma Multilingual (Female)"),
    ("en-US-BrianMultilingualNeural", "Brian Multilingual (Male)"),
    ("en-US-JennyMultilingualNeural", "Jenny Multilingual (Female)"),
    ("en-US-RyanMultilingualNeural", "Ryan Multilingual (Male)"),
    ("en-US-EvelynMultilingualNeural", "Evelyn Multilingual (Female)"),
    ("en-US-AriaNeural", "Aria (Female) - Positive, Confident"),
    ("en-US-AnaNeural", "Ana (Female) - Cute"),
    ("en-US-ChristopherNeural", "Christopher (Male) - Reliable, Authority"),
    ("en-US-EricNeural", "Eric (Male) - Rational"),
    ("en-US-GuyNeural", "Guy (Male) - Passion"),
    ("en-US-JennyNeural", "Jenny (Female) - Friendly, Considerate"),
    ("en-US-MichelleNeural", "Michelle (Female) - Friendly, Pleasant"),
    ("en-US-RogerNeural", "Roger (Male) - Lively"),
    ("en-US-SteffanNeural", "Steffan (Male) - Rational"),
    ("en-GB-LibbyNeural", "Libby (Female)"),
    ("en-GB-MaisieNeural", "Maisie (Female)"),
    ("en-GB-RyanNeural", "Ryan (Male)"),
    ("en-GB-SoniaNeural", "Sonia (Female)"),
    ("en-GB-ThomasNeural", "Thomas (Male)"),
    ("en-AU-NatashaNeural", "Natasha (Female)"),
    ("en-AU-WilliamNeural", "William (Male)"),
    ("en-CA-ClaraNeural", "Clara (Female)"),
    ("en-CA-LiamNeural", "Liam (Male)"),
    ("en-IE-ConnorNeural", "Connor (Male)"),
    ("en-IE-EmilyNeural", "Emily (Female)"),
    ("en-IN-NeerjaNeural", "Neerja (Female)"),
    ("en-IN-PrabhatNeural", "Prabhat (Male)"),
    ("en-NZ-MitchellNeural", "Mitchell (Male)"),
    ("en-NZ-MollyNeural", "Molly (Female)"),
    ("en-ZA-LeahNeural", "Leah (Female)"),
    ("en-ZA-LukeNeural", "Luke (Male)"),
    ("fr-FR-VivienneMultilingualNeural", "Vivienne Multilingual (Female)"),
    ("fr-FR-RemyMultilingualNeural", "Remy Multilingual (Male)"),
    ("fr-FR-LucienMultilingualNeural", "Lucien Multilingual (Male)"),
    ("fr-FR-DeniseNeural", "Denise (Female)"),
    ("fr-FR-EloiseNeural", "Eloise (Female)"),
    ("fr-FR-HenriNeural", "Henri (Male)"),
    ("fr-CA-AntoineNeural", "Antoine (Male)"),
    ("fr-CA-JeanNeural", "Jean (Male)"),
    ("fr-CA-SylvieNeural", "Sylvie (Female)"),
    ("de-DE-SeraphinaMultilingualNeural", "Seraphina Multilingual (Female)"),
    ("de-DE-FlorianMultilingualNeural", "Florian Multilingual (Male)"),
    ("de-DE-AmalaNeural", "Amala (Female)"),
    ("de-DE-ConradNeural", "Conrad (Male)"),
    ("de-DE-KatjaNeural", "Katja (Female)"),
    ("de-DE-KillianNeural", "Killian (Male)"),
    ("es-ES-ArabellaMultilingualNeural", "Arabella Multilingual (Female)"),
    ("es-ES-IsidoraMultilingualNeural", "Isidora Multilingual (Female)"),
    ("es-ES-TristanMultilingualNeural", "Tristan Multilingual (Male)"),
    ("es-ES-XimenaMultilingualNeural", "Ximena Multilingual (Female)"),
    ("es-ES-AlvaroNeural", "Alvaro (Male)"),
    ("es-ES-ElviraNeural", "Elvira (Female)"),
    ("es-MX-DaliaNeural", "Dalia (Female)"),
    ("es-MX-JorgeNeural", "Jorge (Male)"),
    ("ru-RU-DmitryNeural", "Dmitry (Male)"),
    ("ru-RU-SvetlanaNeural", "Svetlana (Female)"),
    ("it-IT-AlessioMultilingualNeural", "Alessio Multilingual (Male)"),
    ("it-IT-IsabellaMultilingualNeural", "Isabella Multilingual (Female)"),
    ("it-IT-GiuseppeMultilingualNeural", "Giuseppe Multilingual (Male)"),
    ("it-IT-MarcelloMultilingualNeural", "Marcello Multilingual (Male)"),
    ("it-IT-DiegoNeural", "Diego (Male)"),
    ("it-IT-ElsaNeural", "Elsa (Female)"),
    ("it-IT-IsabellaNeural", "Isabella (Female)"),
    ("ja-JP-KeitaNeural", "Keita (Male)"),
    ("ja-JP-NanamiNeural", "Nanami (Female)"),
    ("pt-BR-MacerioMultilingualNeural", "Macerio Multilingual (Male)"),
    ("pt-BR-ThalitaMultilingualNeural", "Thalita Multilingual (Female)"),
    ("pt-BR-AntonioNeural", "Antonio (Male)"),
    ("pt-BR-FranciscaNeural", "Francisca (Female)"),
    ("pt-PT-DuarteNeural", "Duarte (Male)"),
    ("pt-PT-RaquelNeural", "Raquel (Female)"),
    ("zh-CN-XiaoxiaoMultilingualNeural", "Xiaoxiao Multilingual (Female)"),
    ("zh-CN-XiaochenMultilingualNeural", "Xiaochen Multilingual (Female)"),
    ("zh-CN-XiaoyuMultilingualNeural", "Xiaoyu Multilingual (Female)"),
    ("zh-CN-YunyiMultilingualNeural", "Yunyi Multilingual (Female)"),
    ("zh-CN-YunfanMultilingualNeural", "Yunfan Multilingual (Male)"),
    ("zh-CN-YunxiaoMultilingualNeural", "Yunxiao Multilingual (Male)"),
    ("zh-CN-XiaoxiaoNeural", "Xiaoxiao (Female) - Warm"),
    ("zh-CN-YunyangNeural", "Yunyang (Male) - Professional"),
    ("zh-TW-HsiaoChenNeural", "HsiaoChen (Female)"),
    ("zh-TW-YunJheNeural", "YunJhe (Male)"),
    ("ar-SA-HamedNeural", "Hamed (Male)"),
    ("ar-SA-ZariyahNeural", "Zariyah (Female)"),
    ("hi-IN-MadhurNeural", "Madhur (Male)"),
    ("hi-IN-SwaraNeural", "Swara (Female)"),
    ("ko-KR-HyunsuMultilingualNeural", "Hyunsu Multilingual (Male)"),
    ("ko-KR-InJoonNeural", "InJoon (Male)"),
    ("ko-KR-SunHiNeural", "SunHi (Female)"),
]


class Mp3Stream(miniaudio.StreamableSource):
    def __init__(self, gen: AsyncGenerator[TTSChunk, None], prebuffer_size=4, initial_timeout: float = 10.0, chunk_timeout: float = 5.0) -> None:
        super().__init__()
        self.gen = gen
        self.prebuffer_size = prebuffer_size
        self.initial_timeout = initial_timeout
        self.chunk_timeout = chunk_timeout
        self.buffer = bytearray()
        self._done = False
        self._closed = False
        self._first_chunk = False
        self._started = False
        self._error: Exception | None = None
        self._condition = threading.Condition()
        self._last_chunk_time = monotonic()
        threading.Thread(target=self._produce, daemon=True).start()

    def _produce(self):
        try:
            # stream_sync() can leave its queue blocked when the async request fails.
            asyncio.run(self._produce_async())
        except Exception as e:
            with self._condition:
                self._error = e
            log('error', 'Mp3Stream producer exception', e, traceback.format_exc())
        finally:
            with self._condition:
                self._done = True
                self._condition.notify_all()

    async def _produce_async(self) -> None:
        async with aclosing(self.gen):
            async for ev in self.gen:
                with self._condition:
                    if self._closed:
                        break
                    data = ev.get('data')
                    if ev.get('type') == 'audio' and data:
                        self.buffer.extend(data)
                        self._first_chunk = True
                        self._last_chunk_time = monotonic()
                        self._condition.notify_all()

    def raise_if_error(self) -> None:
        error = self._error or self.error_in_readcallback
        if error is not None:
            raise error

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()
        return super().close()

    def read(self, num_bytes: int) -> bytes:
        if num_bytes <= 0:
            return b''
        with self._condition:
            if self._closed:
                return b''
            target = max(self.prebuffer_size * 720, num_bytes) if not self._started else num_bytes
            while len(self.buffer) < target and not self._done:
                if self._closed:
                    return b''
                self.raise_if_error()
                timeout = self.initial_timeout if not self._first_chunk else self.chunk_timeout
                remaining = timeout - (monotonic() - self._last_chunk_time)
                if remaining <= 0:
                    phase = 'initial' if not self._first_chunk else 'gap'
                    log('warn', f'TTS Stream timeout ({phase})')
                    self.close()
                    raise TimeoutError(f'Edge TTS audio stream timeout ({phase}, {timeout:g}s)')
                self._condition.wait(remaining)
            if self._closed:
                return b''
            self.raise_if_error()
            if not self._first_chunk:
                raise RuntimeError('Edge TTS returned no audio. Check the selected voice and the connection to the Edge TTS service.')
            self._started = True
            # Prebuffering must never increase the size of a decoder callback's read.
            out = bytes(self.buffer[:num_bytes])
            del self.buffer[:num_bytes]
            return out


class EdgeTTSModel(TTSModel):
    def __init__(self, model_name: str, speed: float = 1.0, provider_name: str | None = None):
        super().__init__(model_name, provider_name=provider_name)
        self.speed = speed
        self.prebuffer_size = 4

    def synthesize(self, text: str, voice: str) -> Generator[bytes, None, None]:
        rate = f"+{int((float(self.speed) - 1) * 100)}%" if float(self.speed) > 1 else f"-{int((1 - float(self.speed)) * 100)}%"
        response = edge_tts.Communicate(text, voice=voice, rate=rate)

        source = Mp3Stream(response.stream(), self.prebuffer_size)
        with source:
            try:
                pcm_stream = miniaudio.stream_any(
                    source=source,
                    source_format=miniaudio.FileFormat.MP3,
                    output_format=miniaudio.SampleFormat.SIGNED16,
                    nchannels=1,
                    sample_rate=24000,
                    frames_to_read=1024 // 2
                )
                try:
                    for chunk in pcm_stream:
                        source.raise_if_error()
                        yield chunk.tobytes()
                    source.raise_if_error()
                finally:
                    pcm_stream.close()
            except miniaudio.DecodeError as e:
                source.raise_if_error()
                raise miniaudio.DecodeError(f'Edge TTS could not decode the MP3 audio stream: {e}') from e


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
            "voice_settings_config": [{
                "key": "voice",
                "label": "Edge TTS Voice",
                "fields": [{
                    "key": "voice",
                    "label": "Voice",
                    "type": "select",
                    "readonly": False,
                    "placeholder": None,
                    "default_value": EDGE_TTS_VOICE,
                    "select_options": [
                        {"key": value, "label": label, "value": value, "disabled": False}
                        for value, label in EDGE_TTS_VOICES
                    ],
                    "multi_select": False,
                }],
            }],
        }]  # type: ignore[assignment]

    @override
    def create_model(self, provider_id: str, settings: dict[str, Any]):
        if provider_id != "tts":
            raise ValueError(f"Unknown Edge TTS model provider: {provider_id}")
        return EdgeTTSModel(EDGE_TTS_MODEL, provider_name="edge-tts")
