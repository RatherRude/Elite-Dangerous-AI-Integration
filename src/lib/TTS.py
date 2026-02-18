import queue
import re
import threading
import traceback
from time import sleep, time
from typing import Any, Callable, Generator, Literal, Optional, Union, final

import pyaudio
import strip_markdown
from num2words import num2words

from .Logger import log, observe, show_chat_message
from .Models import TTSModel, OpenAITTSModel


@final
class TTS:
    def __init__(self, tts_model: Optional[TTSModel] = None, voice="nova", speed: float=1.0, output_device: Optional[str] = None):
        self.tts_model = tts_model
        self.voice = voice
        self.speed = speed
        
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

    def _normalize_queue_item(self, item: Any) -> dict[str, Any]:
        if isinstance(item, str):
            return {
                "text": item,
                "voice": None,
                "on_start": None,
                "on_complete": None,
                "drop_if": None,
            }
        if isinstance(item, dict):
            return {
                "text": item.get("text", ""),
                "voice": item.get("voice"),
                "on_start": item.get("on_start"),
                "on_complete": item.get("on_complete"),
                "drop_if": item.get("drop_if"),
            }
        return {
            "text": "",
            "voice": None,
            "on_start": None,
            "on_complete": None,
            "drop_if": None,
        }

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
                    item = self._normalize_queue_item(self.read_queue.get())
                    text = item.get("text")
                    voice = item.get("voice")
                    on_start = item.get("on_start")
                    on_complete = item.get("on_complete")
                    drop_if = item.get("drop_if")
                    if not isinstance(text, str) or not text:
                        continue
                    if callable(drop_if) and drop_if():
                        continue
                    try:
                        if callable(on_start):
                            try:
                                on_start()
                            except Exception as callback_error:
                                log('warn', 'TTS on_start callback failed', callback_error)
                        self._playback_one(text, stream, voice if isinstance(voice, str) else None)
                    except Exception as e:
                        self.read_queue.put(item)
                        raise e
                    finally:
                        if callable(on_complete):
                            try:
                                on_complete()
                            except Exception as callback_error:
                                log('warn', 'TTS on_complete callback failed', callback_error)

                self._is_playing = False

                sleep(0.1)
            self._is_playing = False
            stream.stop_stream()

    @observe()
    def _playback_one(self, text: str, stream: pyaudio.Stream, voice_override: str | None = None):
        # Fix numberformatting for different providers
        text = re.sub(r"\d+(,\d{3})*(\.\d+)?", self._number_to_text, text)
        text = strip_markdown.strip_markdown(text)
        # print('reading:', text)
        start_time = time()
        end_time = None
        first_chunk = True
        underflow_count = 0
        empty_buffer_available = stream.get_write_available()
        for chunk in self._stream_audio(text, voice_override):
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
    def _stream_audio(self, text: str, voice_override: str | None = None):
        if self.tts_model is None:
            word_count = len(text.split())
            words_per_minute = 150 * float(self.speed)
            audio_duration = word_count / words_per_minute * 60
            # generate silent audio for the duration of the text
            for _ in range(int(audio_duration * 24_000 / 1024)):
                yield b"\x00" * 1024
        else:
            try:
                selected_voice = voice_override if voice_override else self.voice
                for chunk in self.tts_model.synthesize(text, selected_voice):
                    yield chunk
            except Exception as e:
                log('error', 'TTS synthesis error', e, traceback.format_exc())
                show_chat_message('error', 'TTS synthesis error:', str(e))

    def _number_to_text(self, match: re.Match[str]):
        """Converts numbers like 100,203.12 to one hundred thousand two hundred three point one two"""
        if len(match.group()) <= 2:
            return match.group()
        if isinstance(self.tts_model, OpenAITTSModel):
            # OpenAI TTS doesn't read large numbers correctly, so we convert them to words
            return num2words(match.group().replace(",", ""))
        else:
            return match.group()

    def say(
        self,
        text: str,
        *,
        voice: str | None = None,
        on_start: Callable[[], None] | None = None,
        on_complete: Callable[[], None] | None = None,
        drop_if: Callable[[], bool] | None = None,
    ):
        self.read_queue.put(
            {
                "text": text,
                "voice": voice,
                "on_start": on_start,
                "on_complete": on_complete,
                "drop_if": drop_if,
            },
        )

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

    def quit(self):
        pass


if __name__ == "__main__":
    # Mocking for test
    pass

