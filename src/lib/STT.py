import io
import queue
import threading
import traceback
from time import sleep, time
from typing import Literal, final
import base64

import openai
import pyaudio
import speech_recognition as sr
import soundfile as sf
import numpy as np
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

    def __init__(self, openai_client: openai.OpenAI | None, provider: Literal['openai', 'custom', 'custom-multi-modal', 'google-ai-studio', 'none'], input_device_name, model='whisper-1', language=None, custom_prompt=None, required_word=None):
        self.openai_client = openai_client
        self.provider = provider
        self.vad = SileroVoiceActivityDetector()
        self.input_device_name = input_device_name
        self.model = model
        self.language = language
        self.prompt = custom_prompt if custom_prompt else "COVAS, give me a status update... and throw in something inspiring, would you?"
        self.required_word = required_word
        self.continuous_listening_paused = False

        self.rate=16000
        self.frames_per_buffer=self.vad.chunk_bytes() // pyaudio.get_sample_size(pyaudio.paInt16)

        self.vad_threshold = 0.2
        self.phrase_end_pause = 1.0

    def listen_once_start(self):
        if self.provider == 'none':
            return
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
        if self.provider == 'none':
            return
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
        activity = []
        while self.listening:
            buffer = source.read(self.frames_per_buffer)
            if self.continuous_listening_paused:
                continue
            if len(buffer) == 0: break  # reached end of the stream
            frames.append(buffer)
            frames_duration = len(frames) * self.frames_per_buffer / self.rate
            activity.append(self.vad(buffer))
            if frames_duration > 0.5:
                #log('debug','checking for voice activity in', frames_duration, 'seconds of audio')
                audio_raw = b''.join(frames)
                if all([v < self.vad_threshold for v in activity]):
                    # no voice detected in the recording so far, so clear the buffer
                    # and keep only last 0.1 seconds of audio for the next iteration
                    #log('debug','no voice detected, clearing buffer')
                    keep = int(0.1 * self.rate / self.frames_per_buffer)
                    frames = frames[-keep:]
                    activity = activity[-keep:]
                    timestamp = time()
                    continue
                else:
                    self.recording = True
                    # we have voice activity in current recording
                    # check if there is voice in the last phrase_end_pause seconds
                    #log('debug','voice detected, checking for pause in the last phrase_end_pause seconds')
                    end_slice = int(self.phrase_end_pause * self.rate / self.frames_per_buffer)
                    activity_end_slice = activity[-end_slice:]
                    if all([v < self.vad_threshold for v in activity_end_slice]):
                        # no voice in the last 0.5 seconds, so we know the user has stopped speaking
                        # so we can transcribe the audio
                        #log('debug','no voice detected in the last 0.5 seconds, transcribing')
                        audio_data = sr.AudioData(audio_raw, self.rate, pyaudio.get_sample_size(pyaudio.paInt16))
                        text = self._transcribe(audio_data)
                        frames = []
                        activity = []
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
        if self.openai_client is None:
            raise ValueError('Speech recognition is disabled')
        
        audio_raw = audio.get_raw_data(convert_rate=16000, convert_width=2)
        audio_length = len(audio_raw) / 2 / 16000
        if audio_length < 0.2:
            # print('skipping short audio')
            return ''
        if all([a < self.vad_threshold for a in self.vad.process_chunks(audio_raw)]):
            # print('skipping audio without voice')
            return ''


        text = None
        start_time = time()
        
        if self.provider == 'openai' or self.provider == 'custom' or self.provider == 'local-ai-server':
            text = self._transcribe_openai_audio(audio_raw)
        elif self.provider == 'google-ai-studio' or self.provider == 'custom-multi-modal':
            text = self._transcribe_openai_mm(audio_raw)

        end_time = time()
        log('debug', f'Response time STT', end_time - start_time)

        filter = ['', 'COVAS, give me a status update... and throw in something inspiring, would you?']
        if not text or text.strip() in filter:
            return ''
        
        if self.required_word and self.required_word.lower() not in text.lower():
            return ''

        # print("transcription received", text)
        return text
    
    def _transcribe_openai_mm(self, audio: bytes) -> str:
        # Convert raw PCM data to numpy array
        audio_np = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
        
        # Create a BytesIO buffer for the Ogg file
        audio_wav = io.BytesIO()
        
        # Write as Ogg Vorbis
        sf.write(audio_wav, audio_np, 16000, format='WAV', subtype='PCM_16')
        audio_wav.seek(0)
        audio_wav.name = "audio.wav"  # OpenAI needs a filename
        
        try:
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role":"system", "content":
                        "You are a high quality transcription model. You are given audio input from the user, and return the transcribed text from the input. Do NOT add any additional text in your response, only respond with the text given by the user.\n" +
                        "The audio may be related to space sci-fi terminology like systems, equipment, and station names, specifically the game Elite Dangerous.\n" + 
                        #"Here is an example of the type of text you should return: <example>" + self.prompt + "</example>\n" +
                        "Always provide an exact transcription of the audio. If the user is not speaking or inaudible, return only the word 'silence'."
                    },
                    {"role": "user", "content": [{
                        "type": "text",
                        "text": "<input>"
                    },{
                        "type": "input_audio",
                        "input_audio": {
                            "data": base64.b64encode(audio_wav.getvalue()).decode('utf-8'),
                            "format": "wav"
                        }
                    },{
                        "type": "text",
                        "text": "</input>"
                    },]}
                ]
            )
        except openai.APIStatusError as e:
            log("debug", "STT mm error request:", e.request.method, e.request.url, e.request.headers, e.request.content.decode('utf-8', errors='replace'))
            log("debug", "STT mm error response:", e.response.status_code, e.response.headers, e.response.content.decode('utf-8', errors='replace'))
            
            try:
                error: dict = e.body[0] if hasattr(e, 'body') and e.body and isinstance(e.body, list) else e.body # pyright: ignore[reportAssignmentType]
                message = error.get('error', {}).get('message', e.body if e.body else 'Unknown error')
            except:
                message = e.message
            
            log('error', f'STT {e.response.reason_phrase}:', message)
            return ''
        
        if not response.choices or not hasattr(response.choices[0], 'message') or not hasattr(response.choices[0].message, 'content'):
            log('debug', "STT mm response is incomplete or malformed:", response)
            log('error', f'STT completion error: Response incomplete or malformed')
            return ''
        
        text = response.choices[0].message.content
        if not text:
            return ''
        if text.strip() == 'silence' or text.strip() == '':
            return ''
        return text.strip()
    
    def _transcribe_openai_audio(self, audio: bytes) -> str:
        # Convert raw PCM data to numpy array
        audio_np = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
        
        # Create a BytesIO buffer for the Ogg file
        audio_ogg = io.BytesIO()
        
        # Write as Ogg Vorbis
        sf.write(audio_ogg, audio_np, 16000, format='OGG', subtype='VORBIS')
        audio_ogg.seek(0)
        audio_ogg.name = "audio.ogg"  # OpenAI needs a filename
        
        try:
            transcription = self.openai_client.audio.transcriptions.create(
                model=self.model,
                file=audio_ogg,
                language=self.language,
                prompt=self.prompt
            )
        except openai.APIStatusError as e:
            log("debug", "STT error request:", e.request.method, e.request.url, e.request.headers, e.request.content.decode('utf-8', errors='replace'))
            log("debug", "STT error response:", e.response.status_code, e.response.headers, e.response.content.decode('utf-8', errors='replace'))
            
            try:
                error: dict = e.body[0] if hasattr(e, 'body') and e.body and isinstance(e.body, list) else e.body # pyright: ignore[reportAssignmentType]
                message = error.get('error', {}).get('message', e.body if e.body else 'Unknown error')
            except:
                message = e.message
            
            log('error', f'STT {e.response.reason_phrase}:', message)
            return ''
        
        text = transcription.text
        return text

    def pause_continuous_listening(self, pause: bool):
        self.continuous_listening_paused = pause

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
