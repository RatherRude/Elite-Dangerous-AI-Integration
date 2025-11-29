import time
from typing import Mapping
import pytest
from unittest.mock import MagicMock, patch, ANY
import pyaudio
import io
import queue
from time import sleep
import openai
from src.lib.STT import STT, STTResult

def read_no_voice(x):
    """Return silence"""
    time.sleep(float(x)/160000)
    return b'\x00\x00' * x

def read_voice(x):
    """Return voice"""
    time.sleep(float(x)/160000)
    return b'\xff\xff' * x

@pytest.fixture
def mock_pyaudio(monkeypatch):
    """Mock PyAudio functionality"""
    mock_audio = MagicMock()
    mock_stream = MagicMock()
    
    # Mock audio data that simulates no audio
    mock_stream.read.side_effect = read_no_voice
    
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
    return {
        'audio': mock_audio,
        'stream': mock_stream
    }

@pytest.fixture
def mock_vad():
    """Mock SileroVAD"""
    mock = MagicMock()
    
    # Make the VAD callable - returns voice activity score based on audio content
    # This is used by _listen_continuous_loop which calls self.vad(buffer)
    def vad_call_side_effect(audio_bytes):
        # Check if audio contains voice (non-zero values)
        if audio_bytes and audio_bytes[0] != 0:
            return 1.0  # Voice detected (above threshold)
        return 0.0  # No voice (below threshold)
    mock.side_effect = vad_call_side_effect
    
    # process_chunks is used by _transcribe to filter silent audio
    def process_chunks_side_effect(audio_bytes):
        if audio_bytes and audio_bytes[0] != 0:
            return [1.0]  # Voice detected (above threshold)
        return [0.0]  # No voice (below threshold)
    mock.process_chunks.side_effect = process_chunks_side_effect
    mock.chunk_bytes.return_value = 512 * 2  # frames * sample_size
    return mock

class MockTextResponse:
    """Mock OpenAI response"""
    def __init__(self, text):
        self.text = text

@pytest.fixture
def mock_stt_model():
    mock = MagicMock()
    mock.transcribe.return_value = "Test transcription via API"
    return mock

@pytest.fixture
def mock_vad_detector():
    """Mock SileroVoiceActivityDetector class"""
    mock = MagicMock()
    return mock

@pytest.fixture
def mock_openai():
    """Mock OpenAI client (not used but referenced by test signatures)"""
    mock = MagicMock()
    return mock

@pytest.fixture
def stt(mock_stt_model, mock_vad, mock_vad_detector, mock_pyaudio, monkeypatch):
    """Create STT instance with mocked dependencies"""
    monkeypatch.setattr('pysilero_vad.SileroVoiceActivityDetector', mock_vad_detector)
    stt =  STT(mock_stt_model, "TestDevice")
    stt.vad = mock_vad
    return stt

def test_get_microphone_device_selection(mock_pyaudio, stt):
    """Test microphone device selection"""
    stream = stt._get_microphone()
    
    mock_pyaudio['audio'].open.assert_called_once_with(
        input_device_index=1,
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,
        frames_per_buffer=512
    )
    assert stream == mock_pyaudio['stream']

def test_get_microphone_fallback(mock_pyaudio, stt):
    """Test fallback to default device"""
    mock_pyaudio['audio'].open.side_effect = [Exception("Device error"), mock_pyaudio['stream']]
    
    stream = stt._get_microphone()
    
    assert mock_pyaudio['audio'].open.call_count == 2
    assert stream == mock_pyaudio['stream']
    # Verify second call uses default device
    mock_pyaudio['audio'].open.assert_called_with(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,
        frames_per_buffer=512
    )

def test_continuous_listening(stt, mock_pyaudio: dict[str, MagicMock], mock_vad: MagicMock, mock_openai, monkeypatch):
    """Test continuous listening flow"""
    monkeypatch.setattr('src.lib.STT.STT._transcribe', lambda self, audio: "Test transcription sdf")
    mock_pyaudio['stream'].read.side_effect = read_no_voice
    
    stt.listen_continuous()
    mock_vad.return_value = 0.1
    
    # Wait for audio to be read
    while mock_pyaudio['stream'].read.call_count < 1:
        sleep(0.001)
    
    # Simulate receiving voice
    mock_pyaudio['stream'].read.reset()
    mock_pyaudio['stream'].read.side_effect = read_voice
    while mock_pyaudio['stream'].read.call_count < 16000 * 4 / 1600: # 4 seconds of audio
        sleep(0.001)
    # Voice ends after 4 seconds
    mock_pyaudio['stream'].read.side_effect = read_no_voice
    
    # Wait for transcription
    while stt.resultQueue.empty():
        sleep(0.001)
    
    # Check if transcription was requested
    #assert mock_openai.audio.transcriptions.create.called
    
    # Verify result in queue
    result = stt.resultQueue.get()
    assert isinstance(result, STTResult)
    assert result.text == "Test transcription sdf"

def test_push_to_talk(stt, mock_pyaudio, mock_openai, monkeypatch):
    """Test push-to-talk flow"""
    monkeypatch.setattr('src.lib.STT.STT._transcribe', lambda self, audio: "Test transcription asd")
    mock_pyaudio['stream'].read.side_effect = read_voice
    sleep(0.01)  # Simulate button press duration
    
    # Start listening
    stt.listen_once_start()
    while mock_pyaudio['stream'].read.call_count < 16000 * 4 / 1600: # 4 seconds of audio
        sleep(0.001)
    stt.listen_once_end()
    
    # Wait for transcription
    while stt.resultQueue.empty():
        sleep(0.001)
    
    # Check result
    result = stt.resultQueue.get()
    assert isinstance(result, STTResult)
    assert result.text == "Test transcription asd"

def test_transcribe(stt, mock_openai, mock_vad):
    """Test VAD filtering of silent audio"""  
    import speech_recognition as sr
    import pyaudio
    
    audio = sr.AudioData(b'\x00\x00' * 16000, 16000, pyaudio.get_sample_size(pyaudio.paInt16))
    res = stt._transcribe(audio)
    assert res == ''
    
    audio = sr.AudioData(b'\xff\xff' * 16000, 16000, pyaudio.get_sample_size(pyaudio.paInt16))
    res = stt._transcribe(audio)
    assert res == 'Test transcription via API'
    
