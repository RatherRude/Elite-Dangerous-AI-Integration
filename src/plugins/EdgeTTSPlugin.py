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
