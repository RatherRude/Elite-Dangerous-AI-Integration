from math import ceil
from httpx import Response
import pytest
from unittest.mock import MagicMock
from time import sleep
from src.lib.TTS import TTS
import numpy as np

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
    tts =  TTS(mock_openai, provider="openai", model="tts-1", voice="nova", speed=1)
    tts.say("Hello world")
    
    while not mock_openai.audio.speech.with_streaming_response.create.called:
        sleep(0.1)
    
    while not mock_pyaudio['stream'].write.call_count == ceil(2*24_000/1024):
        sleep(0.1)
        
    assert mock_pyaudio['stream'].write.call_count == ceil(2*24_000/1024)


def test_openai_tts_playback_with_voice_instructions(mock_pyaudio, mock_openai):
    """Test OpenAI TTS playback"""
    tts = TTS(mock_openai, provider="openai", model="tts-1", voice="nova", voice_instructions="Speak normally...", speed=1)
    tts.say("Hello world")

    while not mock_openai.audio.speech.with_streaming_response.create.called:
        sleep(0.1)

    while not mock_pyaudio['stream'].write.call_count == ceil(2 * 24_000 / 1024):
        sleep(0.1)

    assert mock_pyaudio['stream'].write.call_count == ceil(2 * 24_000 / 1024)
    
def test_edge_tts_playback(mock_pyaudio, mock_miniaudio, mock_openai):
    """Test Edge-TTS playback"""
    tts =  TTS(None, provider="edge-tts", model="edge-tts", voice="en-GB-SoniaNeural", speed=1)
    tts.say("Hello world")
    
    while not mock_pyaudio['stream'].write.call_count >= 2:
        sleep(0.1)
    
    assert mock_miniaudio.stream_any.call_count == 1
    assert mock_pyaudio['stream'].write.call_count == 2