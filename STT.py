
import threading
from time import sleep, time
import speech_recognition as sr
import queue
from sys import platform
import openai
import io

class STTResult:
    def __init__(self, text:str, audio:bytes, timestamp:float):
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
    recorder = sr.Recognizer()

    prompt = "Computer, pirates are attacking our ship! Call Wakata Station in HIP 23716 for help and enter supercruise immediately!"

    def __init__(self, openai_client:openai.OpenAI, phrase_time_limit=15, energy_threshold=1000, linux_mic_name='pipewire', model='whisper-1', language=None):
        self.openai_client = openai_client
        self.phrase_time_limit = phrase_time_limit
        self.energy_threshold = energy_threshold
        self.linux_mic_name = linux_mic_name
        self.model = model
        self.language = language

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
        source = self._get_microphone(self.linux_mic_name)
        with source as source:
            timestamp = time()
            frames = []
            while self.listening:
                buffer = source.stream.read(source.CHUNK)
                if len(buffer) == 0: break  # reached end of the stream
                frames.append(buffer)

        audio_raw = b''.join(frames)
        audio_data = sr.AudioData(audio_raw, source.SAMPLE_RATE, source.SAMPLE_WIDTH)
        audio_wav = audio_data.get_wav_data()
        text = self._transcribe(audio_wav)
        if not text:
            return
        self.resultQueue.put(STTResult(text, audio_wav, timestamp))

    def listen_continuous(self):
        self.recorder.energy_threshold = self.energy_threshold
        # Definitely do this, dynamic energy compensation lowers the energy threshold dramatically to a point where the SpeechRecognizer never stops recording.
        self.recorder.dynamic_energy_threshold = False

        source = self._get_microphone(self.linux_mic_name)

        def record_callback(_, audio:sr.AudioData) -> None:
            """
            Threaded callback function to receive audio data when recordings finish.
            audio: An AudioData containing the recorded bytes.
            """
            timestamp = time()
            #printFlush('record callback')
            # Grab the wav bytes and convert it into a valid file format for openai.
            audio_wav = audio.get_wav_data()
            text = self._transcribe(audio_wav)
            if not text:
                return
            self.resultQueue.put(STTResult(text, audio_wav, timestamp))


        with source:
            self.recorder.adjust_for_ambient_noise(source)

        # Create a background thread that will pass us raw audio bytes.
        # We could do this manually but SpeechRecognizer provides a nice helper.
        self.recorder.listen_in_background(source, record_callback, phrase_time_limit=self.phrase_time_limit)

    def _get_microphone(self, linux_mic_name:str) -> sr.Microphone:
        # Important for linux users.
        # Prevents permanent application hang and crash by using the wrong Microphone
        if 'linux' in platform:
            for index, name in enumerate(sr.Microphone.list_microphone_names()):
                if self.linux_mic_name in name:
                    return sr.Microphone(sample_rate=16000, device_index=index)

            #print ("Available microphones:")
            for index, name in enumerate(sr.Microphone.list_microphone_names()):
                print(f" {index}) {name}")
            raise Exception('Microphone not found')
        else:
            return sr.Microphone(sample_rate=16000)

    def _transcribe(self, wav:bytes) -> str:
        audio_wav = io.BytesIO(wav)
        audio_wav.name = "audio.wav"

        #print("Audio data recorded")
        transcription = self.openai_client.audio.transcriptions.create(
            model=self.model,
            file=audio_wav,
            language=self.language,
            prompt=self.prompt
        )
        #print("transcription received", transcription.text)
        return transcription.text


if __name__ == "__main__":
    openai_audio = openai.OpenAI(
        base_url="http://localhost:5000",
    )

    stt = STT(openai_client=openai_audio)

    stt.listen_once_start()
    sleep(5)
    stt.listen_once_end()

    #stt.listen_continuous()

    while True:
        sleep(0.25)
        while not stt.resultQueue.empty():
            result = stt.resultQueue.get()
            print(result)