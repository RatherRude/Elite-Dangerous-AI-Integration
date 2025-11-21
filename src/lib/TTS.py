import queue
import re
import threading
import traceback
from time import sleep, time
from typing import Generator, Literal, Optional, Union, final

import edge_tts
import miniaudio
import openai
import pyaudio
import strip_markdown
from num2words import num2words

from .Logger import log, observe, show_chat_message


@final
class Mp3Stream(miniaudio.StreamableSource):
    def __init__(self, gen: Generator, prebuffer_size=4, initial_timeout: float = 10.0, chunk_timeout: float = 5.0) -> None:
        super().__init__()
        self.gen = gen
        self.prebuffer_size = prebuffer_size
        self.initial_timeout = initial_timeout
        self.chunk_timeout = chunk_timeout
        self.buffer = bytearray()
        self._done = False
        self._closed = False
        self._first_chunk = False
        self._last_chunk_time = time()
        threading.Thread(target=self._produce, daemon=True).start()

    def _produce(self):
        try:
            for ev in self.gen:
                if self._closed:
                    break
                if isinstance(ev, dict) and ev.get('type') == 'audio':
                    self.buffer.extend(ev['data'])
                    self._first_chunk = True
                    self._last_chunk_time = time()
        except Exception as e:
            log('error', 'Mp3Stream producer exception', e, traceback.format_exc())
            raise e
        finally:
            self._done = True

    def close(self):  # type: ignore[override]
        self._closed = True
        return super().close()

    def read(self, num_bytes: int) -> bytes:
        if self._closed:
            return b''
        out = bytearray()
        need = max(self.prebuffer_size * 720, num_bytes)
        while len(out) < need:
            # timeout checks
            timeout = self.initial_timeout if not self._first_chunk else self.chunk_timeout
            if (not self._done) and (time() - self._last_chunk_time > timeout):
                log('warn', 'TTS Stream timeout (initial)' if not self._first_chunk else 'TTS Stream timeout (gap)')
                self.close()
                raise IOError('TTS Stream timeout')
            if self.buffer:
                take = min(len(self.buffer), need - len(out))
                out.extend(self.buffer[:take])
                del self.buffer[:take]
            else:
                if self._done:
                    break
                sleep(0.01)
        return bytes(out)

@final
class TTS:
    def __init__(self, openai_client: Optional[openai.OpenAI] = None, provider: Literal['openai', 'edge-tts', 'custom', 'none', 'local-ai-server'] | str ='openai', voice="nova", voice_instructions="", model='tts-1',  speed: Union[str,float]=1, output_device: Optional[str] = None, character_voices: Optional[dict[str, str]] = None):
        self.openai_client = openai_client
        self.provider = provider
        self.model = model
        self.voice = voice
        self.voice_instructions = voice_instructions

        self.speed = speed
        self.character_voices = {
            k.lower(): v
            for k, v in (character_voices or {}).items()
            if k and v
        }
        
        self.p = pyaudio.PyAudio()
        self.output_device = output_device
        self.read_queue = queue.Queue()
        self.is_aborted = False
        self._is_playing = False
        self.prebuffer_size = 4
        self.output_format = pyaudio.paInt16
        self.frames_per_buffer = 1024
        self.sample_size = self.p.get_sample_size(self.output_format)

        thread = threading.Thread(target=self._playback_thread)
        thread.daemon = True
        thread.start()

    def _get_output_device_index(self) -> Optional[int]: #Rewert from String to Index 
        for i in range(self.p.get_device_count()):
            dev_info = self.p.get_device_info_by_index(i)
            if self.output_device in dev_info.get('name', ''):
                return i
        return None

    def _playback_thread(self):
        backoff = 1
        while True:
            try:
                self._playback_loop()
            except Exception as e:
                log('error', 'An error occurred during speech synthesis', e, traceback.format_exc())
                show_chat_message('error', 'An error occurred during speech synthesis:', e)
                sleep(backoff)
                log('info', 'Attempting to restart audio playback after failure')
                backoff *= 2

    def _playback_loop(self):
        output_index = self._get_output_device_index()
        stream = self.p.open(
            format=self.output_format,
            channels=1,
            rate=24_000,
            frames_per_buffer=self.frames_per_buffer,
            output=True,
            output_device_index=output_index  
        )
        while True:
            self.is_aborted = False
            stream.start_stream()
            while not self.is_aborted:
                if not self.read_queue.empty():
                    self._is_playing = True
                    voice, text = self.read_queue.get()
                    try:
                        self._playback_one(text, stream, voice)
                    except Exception as e:
                        self.read_queue.put((voice, text))
                        raise e

                self._is_playing = False

                sleep(0.1)
            self._is_playing = False
            stream.stop_stream()

    @observe()
    def _playback_one(self, text: str, stream: pyaudio.Stream, voice: Optional[str] = None):
        # Fix numberformatting for different providers
        text = re.sub(r"\d+(,\d{3})*(\.\d+)?", self._number_to_text, text)
        text = strip_markdown.strip_markdown(text)
        # print('reading:', text)
        start_time = time()
        end_time = None
        first_chunk = True
        underflow_count = 0
        empty_buffer_available = stream.get_write_available()
        for chunk in self._stream_audio(text, voice):
            if not end_time:
                end_time = time()
                log('debug', f'Response time TTS', end_time - start_time)
            if self.is_aborted:
                break
            try:
                if not first_chunk:
                    available = stream.get_write_available()
                    # log('debug', 'tts write available', available)
                    if available == empty_buffer_available:
                        raise IOError('underflow')
                stream.write(chunk, exception_on_underflow=False) # this may throw for various system reasons
                first_chunk = False
            except IOError as e:
                if not first_chunk:
                    underflow_count += 1
                    # log('debug', 'tts underflow detected', underflow_count)
                stream.write(chunk, exception_on_underflow=False)
        
        if underflow_count > 0:
            self.prebuffer_size *= 2
            log('debug', 'tts underflow detected, total', underflow_count, 'increasing prebuffer size to', self.prebuffer_size)
                
        

    @observe()
    def _stream_audio(self, text: str, voice: Optional[str] = None):
        selected_voice = voice or self.voice
        if self.provider == 'none':
            word_count = len(text.split())
            words_per_minute = 150 * float(self.speed)
            audio_duration = word_count / words_per_minute * 60
            # generate silent audio for the duration of the text
            for _ in range(int(audio_duration * 24_000 / 1024)):
                yield b"\x00" * 1024
        elif self.provider == "edge-tts":
            rate = f"+{int((float(self.speed) - 1) * 100)}%" if float(self.speed) > 1 else f"-{int((1 - float(self.speed)) * 100)}%"
            response = edge_tts.Communicate(text, voice=selected_voice, rate=rate)
            pcm_stream = miniaudio.stream_any(
                source=Mp3Stream(response.stream_sync(), self.prebuffer_size),
                source_format=miniaudio.FileFormat.MP3,
                output_format=miniaudio.SampleFormat.SIGNED16,
                nchannels=1,
                sample_rate=24000,
                frames_to_read=1024 // self.p.get_sample_size(pyaudio.paInt16) # 1024 bytes
            )

            for i in pcm_stream:
                yield i.tobytes()
        elif self.openai_client:
            try:
                with self.openai_client.audio.speech.with_streaming_response.create(
                        model=self.model,
                        voice=selected_voice,
                        input=text,
                        response_format="pcm",
                        # raw samples in 24kHz (16-bit signed, low-endian), without the header.
                        instructions = self.voice_instructions,
                        speed=float(self.speed)
                ) as response:
                    for chunk in response.iter_bytes(1024):
                        yield chunk
            except openai.APIStatusError as e:
                log("debug", "TTS error request:", e.request.method, e.request.url, e.request.headers, e.request.read().decode('utf-8', errors='replace'))
                log("debug", "TTS error response:", e.response.status_code, e.response.headers, e.response.read().decode('utf-8', errors='replace'))
                
                try:
                    error: dict = e.body[0] if hasattr(e, 'body') and e.body and isinstance(e.body, list) else e.body # pyright: ignore[reportAssignmentType]
                    message = error.get('error', {}).get('message', e.body if e.body else 'Unknown error')
                except:
                    message = e.message
                
                show_chat_message('error', f'TTS {e.response.reason_phrase}:', message)
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
        for segment in self._segment_text(text):
            self.read_queue.put(segment)

    def abort(self):
        while not self.read_queue.empty():
            self.read_queue.get()

        self.is_aborted = True

    def get_is_playing(self):
        return self._is_playing or not self.read_queue.empty()

    @observe()
    def wait_for_completion(self):
        while self.get_is_playing():
            sleep(0.2)

    def _strip(self, text: str) -> str:
        cleaned = re.sub(r"\([^)]*\)", "", text)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    def _segment_text(self, text: str) -> list[tuple[str, str]]:
        segments: list[tuple[str, str]] = []
        current_voice = self.voice
        pattern = re.compile(r"\(([^)]+)\)")
        last_idx = 0
        for match in pattern.finditer(text):
            chunk = text[last_idx:match.start()]
            cleaned_chunk = self._strip(chunk)
            if cleaned_chunk:
                segments.append((current_voice, cleaned_chunk))
            label = match.group(1).strip()
            current_voice = self._voice_for_label(label)
            last_idx = match.end()
        tail = self._strip(text[last_idx:])
        if tail:
            segments.append((current_voice, tail))
        if not segments:
            segments.append((self.voice, self._strip(text)))
        return segments

    def _voice_for_label(self, label: str) -> str:
        key = label.lower()
        if key in self.character_voices:
            return self.character_voices[key]
        return self.voice

    def quit(self):
        pass


if __name__ == "__main__":
    openai_audio = openai.OpenAI(base_url="http://localhost:8080/v1", api_key='x')

    tts = TTS(openai_audio, provider="openai", model="tts-1", voice="nova", voice_instructions="", speed=1, output_device="Speakers")


    text = """The missile knows where it is at all times. It knows this because it knows where it isn't. By subtracting where it is from where it isn't, or where it isn't from where it is (whichever is greater), it obtains a difference, or deviation. The guidance subsystem uses deviations to generate corrective commands to drive the missile from a position where it is to a position where it isn't, and arriving at a position where it wasn't, it now is. Consequently, the position where it is, is now the position that it wasn't, and it follows that the position that it was, is now the position that it isn't.
In the event that the position that it is in is not the position that it wasn't, the system has acquired a variation, the variation being the difference between where the missile is, and where it wasn't. If variation is considered to be a significant factor, it too may be corrected by the GEA. However, the missile must also know where it was.
The missile guidance computer scenario works as follows. Because a variation has modified some of the information the missile has obtained, it is not sure just where it is. However, it is sure where it isn't, within reason, and it knows where it was. It now subtracts where it should be from where it wasn't, or vice-versa, and by differentiating this from the algebraic sum of where it shouldn't be, and where it was, it is able to obtain the deviation and its variation, which is called error."""

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
