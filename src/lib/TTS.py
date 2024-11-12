from io import BytesIO
import queue
import re
from sys import platform
import threading
from time import sleep
import traceback
from typing import Optional

from num2words import num2words
import strip_markdown
import openai
import edge_tts
import pyaudio
import miniaudio

from .Logger import log


class TTS:
    p = pyaudio.PyAudio()
    read_queue = queue.Queue()
    is_aborted = False
    _is_playing = False

    def __init__(self, openai_client: Optional[openai.OpenAI] = None, provider='openai', model='tts-1', voice="nova", speed=1):
        self.openai_client = openai_client
        self.provider = provider
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
                log('error', 'An error occurred during speech synthesis', e, traceback.format_exc())
                sleep(backoff)
                log('info', 'Attempting to restart audio playback after failure')
                backoff *= 2
    
    def _playback_loop(self):
        stream = self.p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=24_000,
            output=True,
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
                    text = strip_markdown.strip_markdown(text)
                    # print('reading:', text)
                    try:                            
                        for chunk in self._stream_audio(text):
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
    
    def _stream_audio(self, text):
        if self.provider == 'none':
            word_count = len(text.split())
            words_per_minute = 150 * float(self.speed)
            audio_duration = word_count / words_per_minute * 60
            # generate silent audio for 
            for _ in range(int(audio_duration * 24_000 / 1024)):
                yield b"\x00" * 1024
        elif self.provider == "edge-tts":
            rate = f"+{int((float(self.speed) - 1) * 100)}%" if float(self.speed) > 1 else f"-{int((1 - float(self.speed)) * 100)}%"
            response = edge_tts.Communicate(text, voice=self.voice, rate=rate)
            chunks = []
            for chunk in response.stream_sync():
                if chunk["type"] == "audio":
                    chunks.append(chunk["data"])
            audio_mp3 = b"".join(chunks)
            audio = miniaudio.decode(audio_mp3, output_format=miniaudio.SampleFormat.SIGNED16, nchannels=1, sample_rate=24000)
            data = audio.samples.tobytes()
            # iterate over the data in chunks of 1024 bytes
            for i in range(0, len(data), 1024):
                yield data[i:i + 1024]
        else:
            with self.openai_client.audio.speech.with_streaming_response.create(
                    model=self.model,
                    voice=self.voice,
                    input=text,
                    response_format="pcm",
                    # raw samples in 24kHz (16-bit signed, low-endian), without the header.
                    speed=self.speed
            ) as response:
                for chunk in response.iter_bytes(1024):
                    yield chunk

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
    openai_audio = openai.OpenAI(base_url="http://localhost:8080/v1")

    tts = TTS(openai_client=openai_audio)

    text = """
The missile knows where it is at all times. It knows this because it knows where it isn't. By subtracting where it is from where it isn't, or where it isn't from where it is (whichever is greater), it obtains a difference, or deviation. The guidance subsystem uses deviations to generate corrective commands to drive the missile from a position where it is to a position where it isn't, and arriving at a position where it wasn't, it now is. Consequently, the position where it is, is now the position that it wasn't, and it follows that the position that it was, is now the position that it isn't.
In the event that the position that it is in is not the position that it wasn't, the system has acquired a variation, the variation being the difference between where the missile is, and where it wasn't. If variation is considered to be a significant factor, it too may be corrected by the GEA. However, the missile must also know where it was.
The missile guidance computer scenario works as follows. Because a variation has modified some of the information the missile has obtained, it is not sure just where it is. However, it is sure where it isn't, within reason, and it knows where it was. It now subtracts where it should be from where it wasn't, or vice-versa, and by differentiating this from the algebraic sum of where it shouldn't be, and where it was, it is able to obtain the deviation and its variation, which is called error.

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
