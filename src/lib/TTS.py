import queue
import re
from sys import platform
import threading
from time import sleep
import traceback
from typing import Generator, Literal, Optional, Union, final

from num2words import num2words
import strip_markdown
import openai
import edge_tts
import pyaudio
import miniaudio

from .Logger import log

@final
class Mp3Stream(miniaudio.StreamableSource):
    def __init__(self, gen: Generator) -> None:
        super().__init__()
        self.gen = gen
        self.data = b""
        self.offset = 0
    
    def read(self, num_bytes: int) -> bytes:
        data = b""
        try:
            while True:
                chunk = self.gen.__next__()
                if isinstance(chunk, dict) and chunk["type"] == "audio":
                    data += chunk["data"]
                if len(data) >= 2*720: # TODO: Find a good value here
                    return data
        except StopIteration:
            self.close()
        return data
    
@final
class TTS:
    def __init__(self, openai_client: Optional[openai.OpenAI] = None, provider: Literal["none", "edge-tts", "openai"]='openai', model='tts-1', voice="nova", speed: Union[str,float]=1):
        self.openai_client = openai_client
        self.provider = provider
        self.model = model
        self.voice = voice
        self.speed = speed
        
        self.p = pyaudio.PyAudio()
        self.read_queue = queue.Queue()
        self.is_aborted = False
        self._is_playing = False

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
                    # Fix numberformatting for different providers
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
            pcm_stream = miniaudio.stream_any(
                source = Mp3Stream(response.stream_sync()), 
                source_format = miniaudio.FileFormat.MP3, 
                output_format = miniaudio.SampleFormat.SIGNED16, 
                nchannels = 1, 
                sample_rate = 24000,
                frames_to_read=1024 // self.p.get_sample_size(pyaudio.paInt16) # 1024 bytes
            )
        
            for i in pcm_stream:
                yield i.tobytes()
                
        elif self.openai_client:
            with self.openai_client.audio.speech.with_streaming_response.create(
                    model=self.model,
                    voice=self.voice, # pyright: ignore[reportArgumentType]
                    input=text,
                    response_format="pcm",
                    # raw samples in 24kHz (16-bit signed, low-endian), without the header.
                    speed=float(self.speed)
            ) as response:
                for chunk in response.iter_bytes(1024):
                    yield chunk
        else: 
            raise ValueError('No TTS client provided')

    def _number_to_text(self, match: re.Match[str]):
        """Converts numbers like 100,203.12 to one hundred thousand two hundred three point one two"""
        if len(match.group()) <= 2:
            return match.group()
        if self.provider == "openai":
            # OpenAI TTS doesn't read large numbers correctly, so we convert them to words
            return num2words(match.group().replace(",", ""))
        else:
            return match.group()

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

    tts = TTS(openai_client=None, provider="edge-tts", voice="de-DE-SeraphinaMultilingualNeural")

    text = """ 2 plus 2 ist 100.203,12 insgesamt."""

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
