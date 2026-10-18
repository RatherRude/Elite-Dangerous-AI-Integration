import asyncio
from io import BytesIO
import threading
from time import monotonic
from typing import AsyncGenerator
from unittest.mock import MagicMock

import miniaudio
import numpy as np
import pytest
from av.audio.frame import AudioFrame
from av.audio.stream import AudioStream
from av.container.core import open as open_audio
from edge_tts.exceptions import NoAudioReceived
from edge_tts.typing import TTSChunk

from src.plugins.EdgeTTSPlugin import EdgeTTSModel, Mp3Stream


async def audio_events(data: bytes, chunk_size: int = 720) -> AsyncGenerator[TTSChunk, None]:
    yield {"type": "SentenceBoundary", "text": "Test"}
    yield {"type": "audio", "data": b""}
    for offset in range(0, len(data), chunk_size):
        yield {"type": "audio", "data": data[offset:offset + chunk_size]}


@pytest.fixture
def communicate(monkeypatch):
    response = MagicMock()
    factory = MagicMock(return_value=response)
    monkeypatch.setattr("src.plugins.EdgeTTSPlugin.edge_tts.Communicate", factory)
    return factory, response


@pytest.fixture(scope="module")
def mp3_audio():
    output = BytesIO()
    samples = (np.sin(2 * np.pi * 1000 * np.arange(6000) / 24000) * 12000).astype(np.int16)
    with open_audio(output, mode="w", format="mp3") as container:
        stream = container.add_stream("mp3", rate=24000)
        assert isinstance(stream, AudioStream)
        frame = AudioFrame.from_ndarray(samples[np.newaxis, :], format="s16", layout="mono")
        frame.sample_rate = 24000
        for packet in stream.encode(frame):
            container.mux(packet)
        for packet in stream.encode(None):
            container.mux(packet)
    return output.getvalue()


@pytest.mark.parametrize("read_size", [1, 16, 720, 4096])
def test_mp3_stream_reads_never_exceed_decoder_request(read_size):
    data = bytes(range(256)) * 20
    with Mp3Stream(audio_events(data)) as source:
        assert source.read(0) == b""
        output = bytearray()
        while chunk := source.read(read_size):
            assert len(chunk) <= read_size
            output.extend(chunk)
        assert bytes(output) == data
        assert source.read(read_size) == b""
    assert source.read(read_size) == b""


def test_mp3_stream_prebuffers_without_returning_extra_bytes():
    release = threading.Event()
    waiting = threading.Event()

    async def events() -> AsyncGenerator[TTSChunk, None]:
        yield {"type": "audio", "data": b"a" * 720}
        waiting.set()
        await asyncio.to_thread(release.wait, 2)
        yield {"type": "audio", "data": b"b" * 720}

    result = []
    with Mp3Stream(events(), prebuffer_size=2) as source:
        reader = threading.Thread(target=lambda: result.append(source.read(16)))
        reader.start()
        try:
            assert waiting.wait(1)
            reader.join(0.05)
            assert reader.is_alive()
        finally:
            release.set()
            reader.join(2)
        assert not reader.is_alive()
        assert result == [b"a" * 16]
        assert source.read(1000) == b"a" * 704 + b"b" * 296


@pytest.mark.parametrize("phase", ["initial", "gap"])
def test_mp3_stream_timeout_is_reported(phase):
    release = threading.Event()
    finished = threading.Event()

    async def events() -> AsyncGenerator[TTSChunk, None]:
        try:
            if phase == "gap":
                yield {"type": "audio", "data": b"a"}
            await asyncio.to_thread(release.wait, 2)
        finally:
            finished.set()

    source = Mp3Stream(events(), initial_timeout=0.05, chunk_timeout=0.05)
    try:
        with pytest.raises(TimeoutError, match=f"Edge TTS audio stream timeout \\({phase}"):
            source.read(16)
    finally:
        source.close()
        release.set()
    assert finished.wait(2)


def test_mp3_stream_close_unblocks_reader():
    release = threading.Event()
    waiting = threading.Event()
    finished = threading.Event()

    async def events() -> AsyncGenerator[TTSChunk, None]:
        try:
            waiting.set()
            await asyncio.to_thread(release.wait, 2)
            yield {"type": "audio", "data": b"late audio"}
        finally:
            finished.set()

    source = Mp3Stream(events())
    result = []
    reader = threading.Thread(target=lambda: result.append(source.read(16)))
    reader.start()
    try:
        assert waiting.wait(1)
        source.close()
        reader.join(1)
        assert not reader.is_alive()
        assert result == [b""]
    finally:
        source.close()
        release.set()
        reader.join(2)
    assert finished.wait(2)


@pytest.mark.parametrize("speed, rate", [(0.5, "-50%"), (1.0, "-0%"), (1.5, "+50%")])
def test_edge_tts_decodes_fragmented_mp3(communicate, mp3_audio, speed, rate):
    factory, response = communicate
    response.stream.return_value = audio_events(mp3_audio, chunk_size=137)
    model = EdgeTTSModel("edge-tts", speed=speed)

    chunks = list(model.synthesize("Test", "fr-FR-DeniseNeural"))

    factory.assert_called_once_with("Test", voice="fr-FR-DeniseNeural", rate=rate)
    response.stream_sync.assert_not_called()
    assert chunks
    assert all(0 < len(chunk) <= 1024 and len(chunk) % 2 == 0 for chunk in chunks)
    samples = np.frombuffer(b"".join(chunks), dtype=np.int16)
    assert 6000 <= len(samples) <= 9000
    assert np.sqrt(np.mean(samples.astype(np.float64) ** 2)) > 1000
    frequencies = np.fft.rfftfreq(len(samples), d=1 / 24000)
    assert abs(frequencies[np.argmax(np.abs(np.fft.rfft(samples)))] - 1000) < 10


@pytest.mark.parametrize("error", [NoAudioReceived("No audio was received"), ConnectionError("Edge connection refused")])
def test_edge_tts_propagates_request_failure_instead_of_decoder_error(communicate, error):
    _, response = communicate

    async def events():
        raise error
        yield

    response.stream.return_value = events()
    started = monotonic()
    with pytest.raises(type(error)) as caught:
        list(EdgeTTSModel("edge-tts").synthesize("Test", "fr-FR-DeniseNeural"))
    assert caught.value is error
    assert monotonic() - started < 2


def test_edge_tts_reports_empty_response(communicate):
    _, response = communicate
    response.stream.return_value = audio_events(b"")
    with pytest.raises(RuntimeError, match="Edge TTS returned no audio"):
        list(EdgeTTSModel("edge-tts").synthesize("Test", "fr-FR-DeniseNeural"))


def test_edge_tts_reports_invalid_mp3(communicate):
    _, response = communicate
    response.stream.return_value = audio_events(b"not an MP3 stream")
    with pytest.raises(miniaudio.DecodeError, match="Edge TTS could not decode the MP3 audio stream"):
        list(EdgeTTSModel("edge-tts").synthesize("Test", "fr-FR-DeniseNeural"))


@pytest.mark.parametrize("failure_point", ["initialization", "iteration", "eof"])
def test_edge_tts_restores_callback_errors(communicate, monkeypatch, failure_point):
    _, response = communicate
    response.stream.return_value = audio_events(b"")
    error = TimeoutError("Edge TTS audio stream timeout (gap)")
    sources = []

    def decode(source, **kwargs):
        sources.append(source)
        if failure_point == "initialization":
            source.error_in_readcallback = error
            raise miniaudio.DecodeError("failed to init decoder", -103)

        def chunks():
            source.error_in_readcallback = error
            if failure_point == "iteration":
                yield np.zeros(8, dtype=np.int16)

        return chunks()

    monkeypatch.setattr("src.plugins.EdgeTTSPlugin.miniaudio.stream_any", decode)
    with pytest.raises(TimeoutError) as caught:
        list(EdgeTTSModel("edge-tts").synthesize("Test", "fr-FR-DeniseNeural"))
    assert caught.value is error
    assert sources[0]._closed


def test_edge_tts_closes_decoder_and_source_on_early_stop(communicate, monkeypatch):
    _, response = communicate
    response.stream.return_value = audio_events(b"")
    sources = []
    decoder_closed = threading.Event()

    def decode(source, **kwargs):
        sources.append(source)

        def chunks():
            try:
                yield np.zeros(8, dtype=np.int16)
                yield np.zeros(8, dtype=np.int16)
            finally:
                decoder_closed.set()

        return chunks()

    monkeypatch.setattr("src.plugins.EdgeTTSPlugin.miniaudio.stream_any", decode)
    synthesis = EdgeTTSModel("edge-tts").synthesize("Test", "fr-FR-DeniseNeural")
    assert next(synthesis) == b"\x00" * 16
    synthesis.close()
    assert decoder_closed.is_set()
    assert sources[0]._closed
