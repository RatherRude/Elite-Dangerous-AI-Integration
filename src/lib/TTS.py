import queue
import re
import threading
import traceback
from time import sleep, time
from typing import Generator, Literal, Optional, Union, final

import pyaudio
import strip_markdown
from num2words import num2words

from .Logger import log, observe, show_chat_message
from .Models import TTSModel, OpenAITTSModel
from .UI import send_message


@final
class TTS:
    def __init__(
        self,
         tts_model: Optional[TTSModel] = None,
         voice="nova",
         speed: float=1.0,
         output_device: Optional[str] = None,
         character_voices: Optional[dict[str, str]] = None,
         primary_character_name: Optional[str] = None):
        self.tts_model = tts_model
        self.voice = voice
        self.speed = speed
        self.primary_character_name = (primary_character_name or "").strip() or "Primary Character"
        self.primary_character_key = self.primary_character_name.lower()
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
        self._last_announced_voice: Optional[str] = None
        self._last_announced_speaker: Optional[str] = None
        self._overlay_refresh_required = False
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
                    voice, text, speaker = self.read_queue.get()
                    try:
                        self._announce_voice_start(speaker, voice)
                        self._playback_one(text, stream, voice)
                    except Exception as e:
                        self.read_queue.put((voice, text, speaker))
                        raise e
                    continue

                if self._is_playing:
                    self._mark_overlay_idle()
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
    def _stream_audio(self, text, voice: Optional[str] = None):
        selected_voice = voice or self.voice
        if self.tts_model is None:
            word_count = len(text.split())
            words_per_minute = 150 * float(self.speed)
            audio_duration = word_count / words_per_minute * 60
            # generate silent audio for the duration of the text
            for _ in range(int(audio_duration * 24_000 / 1024)):
                yield b"\x00" * 1024
        else:
            try:
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

    def say(self, text: str):
        for segment in self._segment_text(text):
            self.read_queue.put(segment)

    def abort(self):
        while not self.read_queue.empty():
            self.read_queue.get()

        self.is_aborted = True
        self._mark_overlay_idle()

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

    def _segment_text(self, text: str) -> list[tuple[str, str, str]]:
        segments: list[tuple[str, str, str]] = []
        current_voice = self.voice
        current_speaker = self.primary_character_name
        pattern = re.compile(r"\(([^)]+)\)")
        last_idx = 0
        for match in pattern.finditer(text):
            chunk = text[last_idx:match.start()]
            cleaned_chunk = self._strip(chunk)
            if cleaned_chunk:
                segments.append((current_voice, cleaned_chunk, current_speaker))
            label = match.group(1).strip()
            if label:
                voice_data = self._match_voice_and_speaker(label)
                if voice_data:
                    current_voice, current_speaker = voice_data
            last_idx = match.end()
        tail = self._strip(text[last_idx:])
        if tail:
            segments.append((current_voice, tail, current_speaker))
        if not segments:
            segments.append((self.voice, self._strip(text), self.primary_character_name))
        return segments

    def _voice_for_label(self, label: str) -> str:
        voice_data = self._match_voice_and_speaker(label)
        if voice_data:
            return voice_data[0]
        return self.voice

    def _match_voice_and_speaker(self, label: str) -> Optional[tuple[str, str]]:
        cleaned = label.strip()
        if not cleaned:
            return None
        key = cleaned.lower()
        if key in self.character_voices:
            return self.character_voices[key], cleaned
        if key == self.primary_character_key:
            return self.voice, self.primary_character_name
        return None

    def _mark_overlay_idle(self) -> None:
        self._overlay_refresh_required = True

    def _announce_voice_start(self, speaker_name: Optional[str], voice: str):
        name = (speaker_name or self.primary_character_name or "").strip()
        if not name:
            return
        if (
            not self._overlay_refresh_required
            and voice == self._last_announced_voice
            and name == self._last_announced_speaker
        ):
            return
        self._last_announced_voice = voice
        self._last_announced_speaker = name
        self._overlay_refresh_required = False
        send_message({
            "type": "overlay_voice",
            "character": {
                "name": name,
                "voice": voice,
            },
        })

    def quit(self):
        pass


if __name__ == "__main__":
    # Mocking for test
    pass

