import io
import queue
import threading
from sys import platform
from time import sleep, time
from typing import Optional

import openai
import speech_recognition as sr
from faster_whisper import WhisperModel
from pysilero_vad import SileroVoiceActivityDetector


class STTResult:
    def __init__(self, text: str, audio: sr.AudioData, timestamp: float):
        self.text = text
        self.audio = audio
        self.timestamp = timestamp

    def __str__(self):
        return self.text

    def __repr__(self):
        return self.text


class STT:
    listening = False
    resultQueue = queue.Queue()

    prompt = "Computer, pirates are attacking our ship! Call Wakata Station in HIP 23716 for help and enter supercruise immediately!"

    def __init__(self, openai_client: Optional[openai.OpenAI], phrase_time_limit=15, energy_threshold=1000,
                 linux_mic_name='pipewire', model='whisper-1', language=None):
        self.openai_client = openai_client
        self.vad = SileroVoiceActivityDetector()
        self.phrase_time_limit = phrase_time_limit
        self.energy_threshold = energy_threshold
        self.linux_mic_name = linux_mic_name
        self.model = model
        self.language = language

        if not self.openai_client:
            self.whisper_model = WhisperModel(self.model, device="cpu", compute_type="int8")

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
        with source as source:
            timestamp = time()
            frames = []
            while self.listening:
                buffer = source.stream.read(source.CHUNK)
                if len(buffer) == 0: break  # reached end of the stream
                frames.append(buffer)

        audio_raw = b''.join(frames)
        audio_data = sr.AudioData(audio_raw, source.SAMPLE_RATE, source.SAMPLE_WIDTH)
        text = self._transcribe(audio_data)
        filter = ['', 'Call Wakata Station in HIP 23716 for help and enter supercruise immediately!',
                  'Call HIP 23716 for help and enter supercruise immediately!']
        if not text or text.strip() in filter:
            return
        self.resultQueue.put(STTResult(text, audio_data, timestamp))

    def listen_continuous(self):
        # print('Running STT in continuous mode')
        recorder = sr.Recognizer()
        recorder.energy_threshold = self.energy_threshold
        # Definitely do this, dynamic energy compensation lowers the energy threshold dramatically to a point where the SpeechRecognizer never stops recording.
        recorder.dynamic_energy_threshold = False

        source = self._get_microphone()

        def record_callback(_, audio: sr.AudioData) -> None:
            """
            Threaded callback function to receive audio data when recordings finish.
            audio: An AudioData containing the recorded bytes.
            """
            timestamp = time()

            text = self._transcribe(audio)
            if not text:
                return
            self.resultQueue.put(STTResult(text, audio, timestamp))

        with source:
            recorder.adjust_for_ambient_noise(source)

        # Create a background thread that will pass us raw audio bytes.
        # We could do this manually but SpeechRecognizer provides a nice helper.
        recorder.listen_in_background(source, record_callback, phrase_time_limit=self.phrase_time_limit)

    def _get_microphone(self) -> sr.Microphone:
        # Important for linux users.
        # Prevents permanent application hang and crash by using the wrong Microphone
        if 'linux' in platform:
            for index, name in enumerate(sr.Microphone.list_microphone_names()):
                if self.linux_mic_name in name:
                    return sr.Microphone(sample_rate=16000, device_index=index)

            # print ("Available microphones:")
            for index, name in enumerate(sr.Microphone.list_microphone_names()):
                print(f" {index}) {name}")
            raise Exception('Microphone not found')
        else:
            return sr.Microphone(sample_rate=16000)

    def _transcribe(self, audio: sr.AudioData) -> str:
        audio_raw = audio.get_raw_data(convert_rate=16000, convert_width=2)
        audio_length = len(audio_raw) / 2 / 16000
        if audio_length < 0.2:
            # print('skipping short audio')
            return ''
        if self.vad(audio_raw) <= 0.2:
            # print('skipping audio without voice')
            return ''

        # Grab the wav bytes and convert it into a valid file format for openai.
        audio_wav = audio.get_wav_data(convert_rate=16000, convert_width=2)
        audio_wav = io.BytesIO(audio_wav)
        audio_wav.name = "audio.wav"

        text = None
        if self.openai_client:
            transcription = self.openai_client.audio.transcriptions.create(
                model=self.model,
                file=audio_wav,
                language=self.language,
                prompt=self.prompt
            )
            text = transcription.text
        else:
            segments, info = self.whisper_model.transcribe(
                audio_wav,
                language=self.language,
                # initial_prompt=self.prompt
            )
            text = '\n'.join([segment.text for segment in segments])
        # print("transcription received", text)
        return text


if __name__ == "__main__":
    openai_audio = openai.OpenAI(
        base_url="http://localhost:5000",
    )

    stt = STT(openai_client=openai_audio)

    stt.listen_once_start()
    sleep(5)
    stt.listen_once_end()

    # stt.listen_continuous()

    while True:
        sleep(0.25)
        while not stt.resultQueue.empty():
            result = stt.resultQueue.get()
            print(result)
