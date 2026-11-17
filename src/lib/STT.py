import queue
import threading
import traceback
from time import sleep, time
from typing import Literal, final

import speech_recognition as sr
from pysilero_vad import SileroVoiceActivityDetector

from .Audio import PCMInput
from .Logger import (
    AudioUsageStats,
    LatencyUsageStats,
    TextUsageStats,
    log,
    log_stt_usage,
    observe,
    show_chat_message,
)
from .Models import STTModel, LLMError


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

    def __init__(self, stt_model: STTModel | None, input_device_name, required_word=None):
        self.stt_model = stt_model
        self.vad = SileroVoiceActivityDetector()
        self.input_device_name = input_device_name
        self.required_word = required_word
        self.continuous_listening_paused = False
        self.continuous_listening_paused_for_response = False

        self.rate=16000
        self.sample_width = 2
        self.frames_per_buffer=self.vad.chunk_bytes() // 2

        self.vad_threshold = 0.2
        self.phrase_end_pause = 1.0

    def listen_once_start(self):
        log('debug', 'listen_once_start')
        if self.stt_model is None:
            return
        if self.listening:
            return
        self.listening = True
        threading.Thread(target=self._listen_once_thread, daemon=True).start()

    def listen_once_end(self):
        log('debug', 'listen_once_end')
        self.listening = False

    def _listen_once_thread(self):
        """
        Push to talk like functionality, immediately records audio and sends it to the OpenAI API, bypassing the VAD.
        """
        # print('Running STT in PTT mode')
        log('debug', 'listen_once_thread start')
        source = None
        self.recording = True
        text = None
        try:
            source = self._get_microphone()
            timestamp = time()
            frames = []
            while self.listening:
                buffer = self._read_stream_buffer(source)
                if len(buffer) == 0: break  # reached end of the stream
                frames.append(buffer)
            source.close()
            source = None

            audio_raw = b''.join(frames)
            audio_data = sr.AudioData(audio_raw, self.rate, self.sample_width)
            text = self._transcribe(audio_data)
        except Exception as error:
            log('error', 'Speech recognition error', error, traceback.format_exc())
            show_chat_message('error', 'Speech recognition error:', error)
        finally:
            try:
                if source is not None:
                    source.close()
            finally:
                self.listening = False
                self.recording = False
        
        if text:
            self.resultQueue.put(STTResult(text, audio_data, timestamp))
        
        log('debug', 'listen_once_thread end')

    def listen_continuous(self):
        if self.stt_model is None:
            return
        self.listening = True
        threading.Thread(target=self._listen_continuous_thread, daemon=True).start()
                        
    def _listen_continuous_thread(self):
        backoff = 1
        while self.listening:
            try: 
                self._listen_continuous_loop()
            except Exception as e:
                self.recording = False
                log('error', 'An error occurred during speech recognition', e, traceback.format_exc())
                show_chat_message('error', 'Speech recognition error:', e)
                sleep(backoff)
                log('info', 'Attempting to restart speech recognition after failure')
                backoff *= 2

    def _listen_continuous_loop(self):
        source: PCMInput = self._get_microphone()
        try:
            timestamp = time()
            frames = []
            activity = []
            while self.listening:
                buffer = self._read_stream_buffer(source)
                if self.continuous_listening_paused or self.continuous_listening_paused_for_response:
                    self.recording = False
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
                            audio_data = sr.AudioData(audio_raw, self.rate, self.sample_width)
                            text = self._transcribe(audio_data)
                            frames = []
                            activity = []
                            if text:
                                self.resultQueue.put(STTResult(text, audio_data, timestamp))
                            self.recording = False
        finally:
            try:
                source.close()
            finally:
                self.recording = False

    def _read_stream_buffer(self, source: PCMInput) -> bytes:
        return source.read(self.frames_per_buffer)

    def _get_microphone(self) -> PCMInput:
        return PCMInput(self.input_device_name, samplerate=self.rate, blocksize=self.frames_per_buffer)

    @observe()
    def _transcribe(self, audio: sr.AudioData) -> str:
        log('debug', 'Transcribing audio...')
        if self.stt_model is None:
            raise ValueError('Speech recognition is disabled')
        
        audio_raw = audio.get_raw_data(convert_rate=16000, convert_width=2)
        audio_length = len(audio_raw) / 2 / 16000
        if audio_length < 0.2:
            log('debug', 'skipping short audio')
            return ''
        if all([a < self.vad_threshold for a in self.vad.process_chunks(audio_raw)]):
            log('debug', 'skipping audio without voice')
            return ''


        text = None
        start_time = time()
        
        try:
            text = self.stt_model.transcribe(audio)
        except LLMError as e:
            log('error', 'STT Error:', e)
            show_chat_message('error', 'STT Error:', str(e))
            return ''
        except Exception as e:
            log('error', 'STT Error:', e, traceback.format_exc())
            return ''

        end_time = time()
        log('debug', f'Response time STT', end_time - start_time)

        filter = ['', 'COVAS, give me a status update... and throw in something inspiring, would you?']
        if not text or text.strip() in filter:
            return ''
        
        if self.required_word and self.required_word.lower() not in text.lower():
            return ''

        log_stt_usage(
            "speech",
            provider=getattr(self.stt_model, "provider_name", None),
            model_name=getattr(self.stt_model, "model_name", None),
            latency_usage=LatencyUsageStats(response_ms=(end_time - start_time) * 1000),
            audio_usage=AudioUsageStats(input_audio_duration_ms=audio_length * 1000),
            text_usage=TextUsageStats(output_chars=len(text)),
        )

        # print("transcription received", text)
        return text

    def pause_continuous_listening(self, pause: bool):
        self.continuous_listening_paused = pause

    def pause_continuous_listening_for_response(self, pause: bool):
        self.continuous_listening_paused_for_response = pause

# if __name__ == "__main__":
#     openai_audio = openai.OpenAI()

#     stt = STT(openai_client=openai_audio)

#     stt.listen_once_start()
#     sleep(5)
#     stt.listen_once_end()

#     stt.listen_continuous()

#     while True:
#         sleep(0.25)
#         while not stt.resultQueue.empty():
#             result = stt.resultQueue.get()
#             print(result)
