from math import ceil
from httpx import Response
import pytest
from unittest.mock import MagicMock
from time import sleep
from src.lib.Config import map_character_tts_postprocessing
from src.lib.TTS import TTS
from src.lib.Models import OpenAITTSModel, EdgeTTSModel
import numpy as np


def dominant_frequency(samples: np.ndarray, sample_rate: int = 24_000) -> float:
    window = np.hanning(samples.shape[0])
    spectrum = np.fft.rfft(samples * window)
    frequencies = np.fft.rfftfreq(samples.shape[0], d=1.0 / sample_rate)
    return float(frequencies[int(np.argmax(np.abs(spectrum)))])

@pytest.fixture
def mock_pyaudio(monkeypatch):
    """Mock PyAudio functionality"""
    mock_audio = MagicMock()
    mock_stream = MagicMock()
    
    # Mock audio playback
    mock_stream.write = MagicMock()
    
    # Mock device info
    mock_audio.get_default_host_api_info.return_value = {
        'index': 0,
        'deviceCount': 2
    }
    mock_audio.get_device_info_by_host_api_device_index.return_value = {
        'name': 'TestDevice',
        'index': 1
    }
    mock_audio.get_sample_size.return_value = 2
    mock_audio.open.return_value = mock_stream
    
    monkeypatch.setattr('pyaudio.PyAudio', lambda: mock_audio)
    monkeypatch.setattr('src.lib.TTS.pyaudio.PyAudio', lambda: mock_audio)
    return {
        'audio': mock_audio,
        'stream': mock_stream
    }

def gen_audio_response(data: bytes):
    """Generate audio response"""
    yield 


class AudioResponse(object):
    def __init__(self, data):
        self.data = data
    
    def __enter__(self):
        return Response(200, content=self.data)

    def __exit__(self, *args):
        pass

@pytest.fixture
def mock_openai():
    """Mock OpenAI client"""
    mock_client = MagicMock()
    mock_client.audio.speech.with_streaming_response.create.side_effect = lambda **quarks: AudioResponse(b'\x00\x00' * 24_000)
    return mock_client

@pytest.fixture
def mock_edge_tts(monkeypatch):
    """Mock Edge-TTS client"""
    mock_client = MagicMock()
    mock_client.Communicate.side_effect = lambda text, voice, rate: MagicMock(stream_sync=lambda: gen_audio_response(b'\x00\x00' * 24_000))
    
    monkeypatch.setattr('edge_tts', mock_client)
    return mock_client

@pytest.fixture
def mock_miniaudio(monkeypatch):
    """Mock miniaudio"""
    mock_stream = MagicMock()
    mock_stream.stream_any.return_value = [np.int16([0,0]), np.int16([0,0])]
    
    monkeypatch.setattr('miniaudio.stream_any', mock_stream.stream_any)
    return mock_stream

def test_openai_tts_playback(mock_pyaudio, mock_openai):
    """Test OpenAI TTS playback"""
    mock_model = MagicMock(spec=OpenAITTSModel)
    mock_model.client = mock_openai
    mock_model.synthesize.return_value = [b'\x00\x00' * 1024] * ceil(2*24_000/1024)
    
    tts = TTS(mock_model, voice="nova", speed=1.0)
    tts.say("Hello world")
    
    while not mock_model.synthesize.called:
        sleep(0.1)
    
    while not mock_pyaudio['stream'].write.call_count == ceil(2*24_000/1024):
        sleep(0.1)
        
    assert mock_pyaudio['stream'].write.call_count == ceil(2*24_000/1024)


def test_openai_tts_playback_with_voice_instructions(mock_pyaudio, mock_openai):
    """Test OpenAI TTS playback with voice instructions"""
    mock_model = MagicMock(spec=OpenAITTSModel)
    mock_model.client = mock_openai
    mock_model.voice_instructions = "Speak normally..."
    mock_model.synthesize.return_value = [b'\x00\x00' * 1024] * ceil(2*24_000/1024)
    
    tts = TTS(mock_model, voice="nova", speed=1.0)
    tts.say("Hello world")

    while not mock_model.synthesize.called:
        sleep(0.1)

    while not mock_pyaudio['stream'].write.call_count == ceil(2 * 24_000 / 1024):
        sleep(0.1)

    assert mock_pyaudio['stream'].write.call_count == ceil(2 * 24_000 / 1024)

def test_edge_tts_playback(mock_pyaudio, mock_miniaudio, mock_openai):
    """Test Edge-TTS playback"""
    mock_model = MagicMock(spec=EdgeTTSModel)
    mock_model.synthesize.return_value = [b'\x00\x00' * 1024, b'\x00\x00' * 1024]
    
    tts = TTS(mock_model, voice="en-US-AvaMultilingualNeural", speed=1.0)
    tts.say("Hello world")
    
    while not mock_pyaudio['stream'].write.call_count >= 2:
        sleep(0.1)
    
    assert mock_model.synthesize.call_count == 1
    assert mock_pyaudio['stream'].write.call_count == 2


def test_postprocess_audio_applies_volume_and_distortion(mock_pyaudio):
    """Test TTS postprocessing reshapes synthesized audio"""
    tts = TTS(
        None,
        postprocessing_config={
            "volume": 0.5,
            "effects": {
                "distortion": {
                    "enabled": True,
                    "drive": 3.0,
                    "clip": 0.25,
                    "mode": "hard",
                },
            },
        },
    )

    source = np.array([20000, -20000, 4000, -4000], dtype=np.int16)
    processed_chunks = list(tts._postprocess_audio(iter([source.tobytes()]), tts.postprocessing_config))
    processed = np.frombuffer(processed_chunks[0], dtype=np.int16)

    assert processed.dtype == np.int16
    assert processed.shape == source.shape
    assert not np.array_equal(processed, source)
    assert np.max(np.abs(processed)) <= np.iinfo(np.int16).max


def test_postprocess_audio_glitch_repeats_previous_chunk(mock_pyaudio, monkeypatch):
    """Test glitch effect replays recent synthesized audio"""
    monkeypatch.setattr("src.lib.TTS.random.random", lambda: 0.0)
    monkeypatch.setattr("src.lib.TTS.random.randint", lambda _a, _b: 2)
    monkeypatch.setattr("src.lib.TTS.random.uniform", lambda _a, _b: 0.0)

    tts = TTS(None)
    config = {
        "volume": 1.0,
        "effects": {
            "glitch": {
                "enabled": True,
                "probability": 1.0,
                "repeat_min": 2,
                "repeat_max": 2,
            },
        },
    }
    first = np.array([1000, -1000], dtype=np.int16).tobytes()
    second = np.array([2000, -2000], dtype=np.int16).tobytes()

    processed_chunks = list(tts._postprocess_audio(iter([first, second]), config))

    assert len(processed_chunks) == 3
    assert processed_chunks[2] == first + first


def test_glitch_effect_applies_base_and_burst_detune(mock_pyaudio, monkeypatch):
    """Test glitch effect adds subtle base detune and stronger glitch detune"""
    monkeypatch.setattr("src.lib.TTS.random.random", lambda: 0.0)
    monkeypatch.setattr("src.lib.TTS.random.randint", lambda _a, _b: 2)

    tts = TTS(None)
    pitch_shift_calls: list[float] = []
    shifted_lengths: list[int] = []
    detune_ranges: list[float] = []

    def fake_transform(audio_array, effect_config, _sample_rate):
        pitch_shift_calls.append(float(effect_config["pitch_shift_semitones"]))
        shifted_lengths.append(int(audio_array.shape[0]))
        return audio_array

    def fake_random_detune(semitone_range: float) -> float:
        detune_ranges.append(semitone_range)
        return 1.5 if semitone_range < 10 else -9.0

    monkeypatch.setattr(tts, "_transform_time_pitch_audio", fake_transform)
    monkeypatch.setattr(tts, "_get_random_glitch_detune", fake_random_detune)
    monkeypatch.setattr(tts, "_get_glitch_pitch_hold_bytes", lambda _config, _sample_rate: 32)

    config = {
        "volume": 1.0,
        "effects": {
            "glitch": {
                "enabled": True,
                "probability": 1.0,
                "repeat_min": 2,
                "repeat_max": 2,
                "detune_base": 3.0,
                "detune_peak": 7.0,
            },
        },
    }
    first = np.array([1000, -1000], dtype=np.int16).tobytes()
    second = np.array([2000, -2000], dtype=np.int16).tobytes()

    processed_chunks = list(tts._postprocess_audio(iter([first, second]), config))

    assert len(processed_chunks) == 3
    assert detune_ranges == [3.0, 7.0]
    assert pitch_shift_calls == pytest.approx([1.5, 1.5])
    assert shifted_lengths == [4, 4]


def test_glitch_config_maps_detune_ranges():
    """Test glitch config keeps detune range settings"""
    config = map_character_tts_postprocessing({
        "effects": {
            "glitch": {
                "enabled": True,
                "detune_base": 2.5,
                "detune_peak": 9.5,
            },
        },
    })

    assert config["effects"]["glitch"]["detune_base"] == pytest.approx(2.5)
    assert config["effects"]["glitch"]["detune_peak"] == pytest.approx(9.5)


def test_time_pitch_effect_stretches_audio_without_changing_pitch(mock_pyaudio):
    """Test time stretch preserves dominant pitch while changing duration"""
    tts = TTS(None)
    sample_rate = 24_000
    time_axis = np.arange(sample_rate, dtype=np.float32) / sample_rate
    source = (0.4 * np.sin(2 * np.pi * 440.0 * time_axis)).astype(np.float32)

    processed = tts._transform_time_pitch_audio(
        source,
        {
            "enabled": True,
            "pitch_shift_semitones": 0.0,
            "time_stretch": 1.5,
        },
        sample_rate,
    )

    assert abs(processed.shape[0] - int(round(source.shape[0] * 1.5))) <= 8
    assert dominant_frequency(processed, sample_rate) == pytest.approx(440.0, abs=20.0)


def test_time_pitch_effect_shifts_pitch_without_changing_duration(mock_pyaudio):
    """Test pitch shift changes dominant pitch while preserving duration"""
    tts = TTS(None)
    sample_rate = 24_000
    time_axis = np.arange(sample_rate, dtype=np.float32) / sample_rate
    source = (0.4 * np.sin(2 * np.pi * 440.0 * time_axis)).astype(np.float32)

    processed = tts._transform_time_pitch_audio(
        source,
        {
            "enabled": True,
            "pitch_shift_semitones": 12.0,
            "time_stretch": 1.0,
        },
        sample_rate,
    )

    assert abs(processed.shape[0] - source.shape[0]) <= 8
    assert dominant_frequency(processed, sample_rate) == pytest.approx(880.0, abs=35.0)


def test_time_pitch_effect_combines_independent_pitch_and_time(mock_pyaudio):
    """Test combined time-pitch keeps requested duration and pitch targets"""
    tts = TTS(None)
    sample_rate = 24_000
    time_axis = np.arange(sample_rate, dtype=np.float32) / sample_rate
    source = (0.4 * np.sin(2 * np.pi * 440.0 * time_axis)).astype(np.float32)

    processed = tts._transform_time_pitch_audio(
        source,
        {
            "enabled": True,
            "pitch_shift_semitones": 12.0,
            "time_stretch": 1.5,
        },
        sample_rate,
    )

    assert abs(processed.shape[0] - int(round(source.shape[0] * 1.5))) <= 8
    assert dominant_frequency(processed, sample_rate) == pytest.approx(880.0, abs=35.0)
