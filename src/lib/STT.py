import io
import queue
import threading
from sys import platform
from time import sleep, time
import traceback
from typing import final
import pyaudio

import openai
import speech_recognition as sr
from pysilero_vad import SileroVoiceActivityDetector

from .Logger import log

@final
class STTResult:
    def __init__(self, text: str, audio: sr.AudioData, timestamp: float):
        self.text = text
        self.audio = audio
        self.timestamp = timestamp

    def __str__(self):
        return self.text

    def __repr__(self):
        return self.text

@final
class STT:
    listening = False
    recording = False
    resultQueue = queue.Queue()

    prompt = "COVAS, give me a status update... and throw in something inspiring, would you?"

    def __init__(self, openai_client: openai.OpenAI, input_device_name, model='whisper-1', language=None):
        self.openai_client = openai_client
        self.vad = SileroVoiceActivityDetector()
        self.input_device_name = input_device_name
        self.model = model
        self.language = language

        self.rate=16000
        self.frames_per_buffer=1600

        self.vad_threshold = 0.2
        self.phrase_end_pause = 1.0

    def listen_once_start(self):
        if self.listening:
            return
        self.listening = True
        threading.Thread(target=self._listen_once_thread, daemon=True).start()

    def listen_once_end(self):
        self.listening = False

    def _listen_once_thread(self):
        """
        Push to talk like functionality, immediately records audio and sends it to the OpenAI API, bypassing the VAD.
        """
        # print('Running STT in PTT mode')
        source = self._get_microphone()
        self.recording = True
        timestamp = time()
        frames = []
        while self.listening:
            buffer = source.read(self.frames_per_buffer)
            if len(buffer) == 0: break  # reached end of the stream
            frames.append(buffer)
        source.close()

        audio_raw = b''.join(frames)
        audio_data = sr.AudioData(audio_raw, self.rate, pyaudio.get_sample_size(pyaudio.paInt16))
        text = self._transcribe(audio_data)
        self.recording = False
        
        if not text:
            return
        
        self.resultQueue.put(STTResult(text, audio_data, timestamp))

    def listen_continuous(self):
        # print('Running STT in continuous mode')
        self.listening = True
        threading.Thread(target=self._listen_continuous_thread, daemon=True).start()
                        
    def _listen_continuous_thread(self):
        backoff = 1
        while self.listening:
            try: 
                self._listen_continuous_loop()
            except Exception as e:
                log('error', 'An error occurred during speech recognition', e, traceback.format_exc())
                sleep(backoff)
                log('info', 'Attempting to restart speech recognition after failure')
                backoff *= 2

    def _listen_continuous_loop(self):
        source: pyaudio.Stream = self._get_microphone()
        timestamp = time()
        frames = []
        while self.listening:
            buffer = source.read(self.frames_per_buffer)
            if len(buffer) == 0: break  # reached end of the stream
            frames.append(buffer)
            frames_duration = len(frames) * self.frames_per_buffer / self.rate
            if frames_duration > 0.5:
                #log('debug','checking for voice activity in', frames_duration, 'seconds of audio')
                audio_raw = b''.join(frames)
                if self.vad(audio_raw) < self.vad_threshold:
                    # no voice detected in the recording so far, so clear the buffer
                    # and keep only last 0.1 seconds of audio for the next iteration
                    #log('debug','no voice detected, clearing buffer')
                    frames = frames[-int(0.1 * self.rate / self.frames_per_buffer):]
                    timestamp = time()
                    continue
                else:
                    self.recording = True
                    # we have voice activity in current recording
                    # check if there is voice in the last phrase_end_pause seconds
                    #log('debug','voice detected, checking for pause in the last phrase_end_pause seconds')
                    audio_end_slice = b''.join(frames[-int(self.phrase_end_pause * self.rate / self.frames_per_buffer):])
                    if self.vad(audio_end_slice) < self.vad_threshold:
                        # no voice in the last 0.5 seconds, so we know the user has stopped speaking
                        # so we can transcribe the audio
                        #log('debug','no voice detected in the last 0.5 seconds, transcribing')
                        audio_data = sr.AudioData(audio_raw, self.rate, pyaudio.get_sample_size(pyaudio.paInt16))
                        text = self._transcribe(audio_data)
                        frames = []
                        if text:
                            self.resultQueue.put(STTResult(text, audio_data, timestamp))
                        self.recording = False
        source.close()

    def _get_microphone(self) -> pyaudio.Stream:
        audio = pyaudio.PyAudio()

        host_api = audio.get_default_host_api_info()

        try:
            device_index = 0
            for i in range(host_api.get('deviceCount')):
                device = audio.get_device_info_by_host_api_device_index(host_api.get('index'), i)
                if device['name'] == self.input_device_name:
                    device_index = device.get('index')
                    break

            source = audio.open(
                input_device_index=device_index,
                format=pyaudio.paInt16,
                channels=1,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.frames_per_buffer
            )
        except Exception as e:
            log('error', 'Failed to open microphone', e, traceback.format_exc())
            log('error', 'Fallback to default microphone')
            source = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.frames_per_buffer
            )
        return source

    def _transcribe(self, audio: sr.AudioData) -> str:
        print('audio data received')
        audio_raw = audio.get_raw_data(convert_rate=16000, convert_width=2)
        audio_length = len(audio_raw) / 2 / 16000
        if audio_length < 0.2:
            # print('skipping short audio')
            return ''
        if self.vad(audio_raw) <= self.vad_threshold:
            # print('skipping audio without voice')
            return ''

        # Grab the wav bytes and convert it into a valid file format for openai.
        audio_wav = audio.get_wav_data(convert_rate=16000, convert_width=2)
        audio_wav = io.BytesIO(audio_wav)
        audio_wav.name = "audio.wav"

        text = None
        transcription = self.openai_client.audio.transcriptions.create(
            model=self.model,
            file=audio_wav,
            language=self.language,
            prompt=self.prompt
        )
        text = transcription.text

        filter = ['', 'COVAS, give me a status update... and throw in something inspiring, would you?']
        if not text or text.strip() in filter:
            return ''

        # print("transcription received", text)
        return text

if __name__ == "__main__":
    openai_audio = openai.OpenAI()

    stt = STT(openai_client=openai_audio)

    stt.listen_once_start()
    sleep(5)
    stt.listen_once_end()

    stt.listen_continuous()

    while True:
        sleep(0.25)
        while not stt.resultQueue.empty():
            result = stt.resultQueue.get()
            print(result)
