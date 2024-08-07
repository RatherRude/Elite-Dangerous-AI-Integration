
import queue
import threading
from time import sleep

import openai
import pyaudio

from Logger import log


class TTS:
    p = pyaudio.PyAudio()
    read_queue = queue.Queue()
    is_aborted = False
    is_playing = False

    def __init__(self, openai_client: openai.OpenAI, model='tts-1', voice="nova", speed=1.2):
        self.openai_client = openai_client
        self.model = model
        self.voice = voice
        self.speed = speed

        thread = threading.Thread(target=self.playback)
        thread.daemon = True
        thread.start()

    def playback(self):
        stream = self.p.open(
            format=8,
            channels=1,
            rate=24_000,
            output=True
        )
        while True:
            self.is_aborted = False
            stream.start_stream()
            while not self.is_aborted:
                if not self.read_queue.empty():
                    self.is_playing = True
                    try:
                        text = self.read_queue.get()
                        with self.openai_client.audio.speech.with_streaming_response.create(
                            model=self.model,
                            voice=self.voice,
                            input=text,
                            response_format="pcm",  # raw samples in 24kHz (16-bit signed, low-endian), without the header.
                            speed=self.speed
                        ) as response:
                            for chunk in response.iter_bytes(1024):
                                if self.is_aborted:
                                    break
                                stream.write(chunk)
                    except Exception as e:
                        log('error', 'An error occured during speech synthesis', e)
                if not stream.get_read_available() > 0:
                    self.is_playing = False

                sleep(0.1)
            self.is_playing = False
            stream.stop_stream()

    def say(self, text:str):
        self.read_queue.put(text)

    def abort(self):
        while not self.read_queue.empty():
            self.read_queue.get()
        
        self.is_aborted = True

    def quit(self):
        pass

if __name__ == "__main__":
    openai_audio = openai.OpenAI()

    tts = TTS(openai_client=openai_audio)
    print('say1')
    result = tts.say("Hi, how are you doing?")
    print('say2')
    result2 = tts.say("Hi, how are you doing now?")
    print('done')

    sleep(3)
    tts.abort()
    result2 = tts.say("Is this actually working?")
    print('done2')

    while True:
        sleep(0.25)