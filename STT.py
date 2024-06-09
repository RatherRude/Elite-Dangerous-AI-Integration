
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

    def listen(self):
        self.recorder.energy_threshold = self.energy_threshold
        # Definitely do this, dynamic energy compensation lowers the energy threshold dramatically to a point where the SpeechRecognizer never stops recording.
        self.recorder.dynamic_energy_threshold = False
    
        # Important for linux users.
        # Prevents permanent application hang and crash by using the wrong Microphone
        if 'linux' in platform:
            for index, name in enumerate(sr.Microphone.list_microphone_names()):
                if self.linux_mic_name in name:
                    source = sr.Microphone(sample_rate=16000, device_index=index)
                    break
            if not source:
                print ("Available microphones:")
                for index, name in enumerate(sr.Microphone.list_microphone_names()):
                    print(f" {index}) {name}")
                raise Exception('Microphone not found')
        else:
            source = sr.Microphone(sample_rate=16000)


        def record_callback(_, audio:sr.AudioData) -> None:
            """
            Threaded callback function to receive audio data when recordings finish.
            audio: An AudioData containing the recorded bytes.
            """
            timestamp = time()
            #printFlush('record callback')
            # Grab the wav bytes and convert it into a valid file format for openai.
            audio_data = audio.get_wav_data()
            audio_wav = io.BytesIO(audio_data)
            audio_wav.name = "audio.wav"
            
            #print("Audio data received")
            transcription = self.openai_client.audio.transcriptions.create(
                model=self.model, 
                file=audio_wav,
                language=self.language,
                prompt=self.prompt
            )
            #print(transcription)
            self.resultQueue.put(STTResult(transcription.text, audio_wav, timestamp))
            
        
        with source:
            self.recorder.adjust_for_ambient_noise(source)

        # Create a background thread that will pass us raw audio bytes.
        # We could do this manually but SpeechRecognizer provides a nice helper.
        self.recorder.listen_in_background(source, record_callback, phrase_time_limit=self.phrase_time_limit)




if __name__ == "__main__":
    import os
    
    openai_audio = openai.OpenAI()

    stt = STT(openai_client=openai_audio)
    stt.listen()

    while True:
        sleep(0.25)
        while stt.resultQueue.qsize() > 0:
            result = stt.resultQueue.get()
            print(result)