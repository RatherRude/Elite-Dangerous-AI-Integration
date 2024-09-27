import queue
import re
from sys import platform
import threading
from time import sleep

from num2words import num2words
import openai
import pyaudio

from .Logger import log


class TTS:
    p = pyaudio.PyAudio()
    read_queue = queue.Queue()
    is_aborted = False
    _is_playing = False

    def __init__(self, openai_client: openai.OpenAI, model='tts-1', voice="nova", speed=1.2):
        self.openai_client = openai_client
        self.model = model
        self.voice = voice
        self.speed = speed

        thread = threading.Thread(target=self._playback_thread)
        thread.daemon = True
        thread.start()

    def _playback_thread(self):
        backoff = 1
        while True:
            try: 
                self._playback_loop()
            except Exception as e:
                log('error', 'An error occurred during speech synthesis', e)
                sleep(backoff)
                log('debug', 'Attempting to restart audio playback after failure')
                backoff *= 2
    
    def _playback_loop(self):
        stream = self.p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=24_000,
            output=True
        )
        while True:
            self.is_aborted = False
            stream.start_stream()
            while not self.is_aborted:
                if not self.read_queue.empty():
                    self._is_playing = True
                    text = self.read_queue.get()
                    # Remove commas from numbers to fix OpenAI TTS
                    text = re.sub(r"\d+(,\d{3})*(\.\d+)?", self._number_to_text, text)
                    print('reading:', text)
                    try:
                        with self.openai_client.audio.speech.with_streaming_response.create(
                                model=self.model,
                                voice=self.voice,
                                input=text,
                                response_format="pcm",
                                # raw samples in 24kHz (16-bit signed, low-endian), without the header.
                                speed=self.speed
                        ) as response:
                            for chunk in response.iter_bytes(1024):
                                if self.is_aborted:
                                    break
                                stream.write(chunk) # this may throw for various system reasons
                    except Exception as e:
                        self.read_queue.put(text)
                        raise e
                
                if platform == "win32":
                    if stream.is_active() and not stream.get_read_available() > 0:
                        self._is_playing = False
                else:
                    # Ubuntu was throwing a segfault on stream.get_read_available, but stream.write was blocking the thread, so this should be fine
                    self._is_playing = False

                sleep(0.1)
            self._is_playing = False
            stream.stop_stream()

    def _number_to_text(self, match: re.Match):
        """Converts numbers like 100,203.12 to one hundred thousand two hundred three point one two"""
        if len(match.group()) <= 2:
            return match.group()
        return num2words(match.group().replace(",", ""))

    def say(self, text: str):
        self.read_queue.put(text)

    def abort(self):
        while not self.read_queue.empty():
            self.read_queue.get()

        self.is_aborted = True

    def get_is_playing(self):
        return self._is_playing or not self.read_queue.empty()

    def quit(self):
        pass


if __name__ == "__main__":
    openai_audio = openai.OpenAI()

    tts = TTS(openai_client=openai_audio)

    text = """
input: thats 94.010212!
input: only 2. in the whole universe.
input: this is 100,000.12
input: no, it's 102010221120!
    """

    for line in text.split("\n"):
        if not line or line.isspace():
            sleep(2)
            continue
        print(line)
        tts.say(line.strip())
        while tts.get_is_playing():
            sleep(0.1)

    tts.abort()
    # result2 = tts.say("Is this actually working?")

    while True:
        sleep(0.25)
