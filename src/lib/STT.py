import queue
import threading
import traceback
from time import sleep, time
from typing import Literal, final

import pyaudio
import speech_recognition as sr
from pysilero_vad import SileroVoiceActivityDetector

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
from .VoiceActivation import VoiceActivation, VoiceInput, VoiceTicket


@final
class STTResult:
    def __init__(self, text: str, audio: sr.AudioData, timestamp: float, voice_input: VoiceInput | None = None) -> None:
        self.text = text
        self.audio = audio
        self.timestamp = timestamp
        self.voice_input = voice_input

    def __str__(self):
        return self.text

    def __repr__(self):
        return self.text

@final
class STT:
    def __init__(
        self,
        stt_model: STTModel | None,
        input_device_name: str,
        required_word: str | None = None,
        voice_activation: VoiceActivation | None = None,
    ) -> None:
        self.stt_model = stt_model
        self.vad = SileroVoiceActivityDetector()
        self.input_device_name = input_device_name
        self.required_word = required_word
        self.voice_activation = voice_activation
        self.listening = False
        self.recording = False
        self.processing = False
        self.resultQueue: queue.Queue[STTResult] = queue.Queue(maxsize=8 if voice_activation else 0)
        self.continuous_listening_paused = False

        self.rate=16000
        self.sample_width = pyaudio.get_sample_size(pyaudio.paInt16)
        self.frames_per_buffer=self.vad.chunk_bytes() // pyaudio.get_sample_size(pyaudio.paInt16)

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
        source = self._get_microphone()
        self.recording = True
        text = None
        try:
            timestamp = time()
            frames = []
            while self.listening:
                buffer = self._read_stream_buffer(source)
                if len(buffer) == 0: break  # reached end of the stream
                frames.append(buffer)
            source.close()

            audio_raw = b''.join(frames)
            audio_data = sr.AudioData(audio_raw, self.rate, self.sample_width)
            text = self._transcribe(audio_data)
        finally:
            self.recording = False
        
        if text:
            self.resultQueue.put(STTResult(text, audio_data, timestamp))
        
        log('debug', 'listen_once_thread end')

    def listen_continuous(self):
        if self.stt_model is None:
            return
        self.listening = True
        threading.Thread(target=self._listen_continuous_thread, daemon=True).start()

    def stop(self) -> None:
        self.listening = False
        if self.voice_activation:
            self.voice_activation.stop()
                        
    def _listen_continuous_thread(self):
        backoff = 1
        while self.listening:
            try: 
                self._listen_continuous_loop()
            except Exception as e:
                self.recording = False
                self.processing = False
                if self.voice_activation:
                    self.voice_activation.end_audio()
                    self.voice_activation.fail()
                log('error', 'An error occurred during speech recognition', e, traceback.format_exc())
                show_chat_message('error', 'Speech recognition error:', e)
                sleep(backoff)
                log('info', 'Attempting to restart speech recognition after failure')
                backoff *= 2

    def _listen_continuous_loop(self):
        source: pyaudio.Stream = self._get_microphone()
        timestamp = time()
        frames = []
        activity = []
        ticket: VoiceTicket | None = None
        dropping = False
        session = self.voice_activation
        end_slice = max(1, int(self.phrase_end_pause * self.rate / self.frames_per_buffer))
        try:
            while self.listening:
                buffer = self._read_stream_buffer(source)
                if len(buffer) == 0:
                    break
                if self.continuous_listening_paused or (session and session.suppressed):
                    self.recording = False
                    frames = []
                    activity = []
                    ticket = None
                    dropping = False
                    timestamp = time()
                    if session:
                        session.end_audio()
                    continue
                score = self.vad(buffer)
                if session and ticket is None and score >= self.vad_threshold:
                    ticket = session.begin_audio()
                activity.append(score)
                if dropping:
                    activity = activity[-end_slice:]
                    if len(activity) == end_slice and all(v < self.vad_threshold for v in activity):
                        dropping = False
                        activity = []
                        ticket = None
                        timestamp = time()
                        if session:
                            session.end_audio()
                    continue
                frames.append(buffer)
                frames_duration = len(frames) * self.frames_per_buffer / self.rate
                if session and frames_duration > 30:
                    show_chat_message("warning", "Voice input exceeded 30 seconds and was discarded.")
                    frames = []
                    dropping = True
                    self.recording = False
                    continue
                if frames_duration <= 0.5:
                    continue
                if all(v < self.vad_threshold for v in activity):
                    keep = max(1, int(0.1 * self.rate / self.frames_per_buffer))
                    frames = frames[-keep:]
                    activity = activity[-keep:]
                    timestamp = time()
                    continue
                self.recording = not session or (ticket is not None and ticket.active)
                if all(v < self.vad_threshold for v in activity[-end_slice:]):
                    audio_data = sr.AudioData(b"".join(frames), self.rate, self.sample_width)
                    self.processing = True
                    try:
                        self._process_audio(audio_data, timestamp, ticket)
                    finally:
                        self.processing = False
                        self.recording = False
                        if session:
                            session.end_audio()
                    frames = []
                    activity = []
                    ticket = None
                    timestamp = time()
                    if session:
                        # Audio accumulated during inference predates the next dialogue turn.
                        available = source.get_read_available()
                        if isinstance(available, int) and available > 0:
                            source.read(available, exception_on_overflow=False)
        finally:
            source.close()
            self.recording = False
            if session:
                session.end_audio()

    def _process_audio(self, audio: sr.AudioData, timestamp: float, ticket: VoiceTicket | None = None) -> None:
        session = self.voice_activation
        if session is None:
            text = self._transcribe(audio)
            if text:
                self.resultQueue.put(STTResult(text, audio, timestamp))
            return
        if ticket is None:
            return
        audio_raw = audio.get_raw_data(convert_rate=16000, convert_width=2)
        audio_length = len(audio_raw) / 2 / 16000
        if audio_length < 0.2 or all(a < self.vad_threshold for a in self.vad.process_chunks(audio_raw)):
            return
        usage: list[tuple[STTModel, float, int]] = []

        def transcribe(model: STTModel) -> str:
            start = time()
            text = model.transcribe(audio)
            usage.append((model, time() - start, len(text)))
            return text

        try:
            result = session.recognize(ticket, transcribe)
        except Exception:
            session.fail()
            raise
        if result is None:
            return
        for model, duration, chars in usage:
            log_stt_usage(
                "voice_activation" if not ticket.active else "speech",
                provider=getattr(model, "provider_name", None),
                model_name=model.model_name,
                latency_usage=LatencyUsageStats(response_ms=duration * 1000),
                audio_usage=AudioUsageStats(input_audio_duration_ms=audio_length * 1000),
                text_usage=TextUsageStats(output_chars=chars),
            )
        try:
            self.resultQueue.put_nowait(STTResult(result.text, audio, timestamp, result))
        except queue.Full:
            session.fail()
            show_chat_message("error", "Too many pending voice commands. The dialogue session was closed.")

    def _read_stream_buffer(self, source: pyaudio.Stream) -> bytes:
        try:
            return source.read(self.frames_per_buffer, exception_on_overflow=False)
        except TypeError:
            return source.read(self.frames_per_buffer)
        except OSError as e:
            if getattr(e, 'errno', None) == -9981:
                log('warn', 'Audio input overflow detected, dropping one microphone chunk')
                return b'\x00' * self.frames_per_buffer * self.sample_width
            raise

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
