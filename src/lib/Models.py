from abc import ABC, abstractmethod
from typing import Any, List, Optional, Generator, Iterable
import io
import base64
import speech_recognition as sr
import soundfile as sf
import numpy as np
import threading
import traceback
from time import sleep, time
import edge_tts
import miniaudio
from openai.types.audio.speech_create_params import SpeechCreateParams
from openai import OpenAI, APIStatusError
from openai.types.chat import ChatCompletion, ChatCompletionMessageToolCall
from openai.types import CreateEmbeddingResponse
from .Logger import log

class LLMError(Exception):
    def __init__(self, message: str, original_error: Exception | None = None):
        super().__init__(message)
        self.original_error = original_error

class LLMModel(ABC):
    model_name: str

    def __init__(self, model_name: str):
        self.model_name = model_name

    @abstractmethod
    def generate(self, messages: List[dict], tools: Optional[List[dict]] = None, tool_choice: Optional[Any] = None) -> tuple[str | None, List[Any] | None]:
        pass

class EmbeddingModel(ABC):
    model_name: str

    def __init__(self, model_name: str):
        self.model_name = model_name

    @abstractmethod
    def create_embedding(self, input_text: str) -> tuple[str, List[float]]:
        pass

class OpenAILLMModel(LLMModel):
    def __init__(self, base_url: str, api_key: str, model_name: str, temperature: float, reasoning_effort: Optional[str] = None, extra_body: Optional[dict] = None, extra_headers: Optional[dict] = None):
        super().__init__(model_name)
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.temperature = temperature
        self.reasoning_effort = reasoning_effort
        self.extra_body = extra_body or {}
        self.extra_headers = extra_headers or {}

    def generate(self, messages: List[dict], tools: Optional[List[dict]] = None, tool_choice: Optional[Any] = None) -> tuple[str | None, List[Any] | None]:
        kwargs = {}
        # Special handling for specific models or providers if needed
        if self.model_name in ['gpt-5', 'gpt-5-mini', 'gpt-5-nano', 'gpt-5.1']:
            kwargs["verbosity"] = "low"
                    
        if self.model_name in ['gemini-3-pro-preview']:
            for m in messages:
                if 'tool_calls' in m and m.get('tool_calls', None):
                    calls = m.get('tool_calls', [{}])
                    if calls:
                        if not isinstance(calls[0], dict):
                            if hasattr(calls[0], 'model_dump'):
                                calls[0] = calls[0].model_dump()
                            elif hasattr(calls[0], 'dict'):
                                calls[0] = calls[0].dict()
                        
                        if isinstance(calls[0], dict):
                            calls[0]['extra_content'] = {"google": {
                                "thought_signature": "skip_thought_signature_validator"
                            }}
        
        params: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.temperature,
            **self.extra_body,
            **kwargs
        }
        if tools:
            params["tools"] = tools
            if tool_choice:
                params["tool_choice"] = tool_choice
        
        if self.reasoning_effort and self.reasoning_effort not in ["disabled", "default", None, ""]:
             params["reasoning_effort"] = self.reasoning_effort

        if self.extra_body:
            params["extra_body"] = self.extra_body
            
        if self.extra_headers:
            params["extra_headers"] = self.extra_headers

        try:
            completion = self.client.chat.completions.create(**params) # pyright: ignore[reportCallIssue]
        except APIStatusError as e:
            log("debug", "LLM error request:", e.request.method, e.request.url, e.request.headers, e.request.read().decode('utf-8', errors='replace'))
            log("debug", "LLM error response:", e.response.status_code, e.response.headers, e.response.read().decode('utf-8', errors='replace'))
            
            try:
                error: dict = e.body[0] if hasattr(e, 'body') and e.body and isinstance(e.body, list) else e.body # pyright: ignore[reportAssignmentType]
                message = error.get('error', {}).get('message', e.body if e.body else 'Unknown error')
            except:
                message = e.message
            
            raise LLMError(f'LLM {e.response.reason_phrase}: {message}', e)
        except Exception as e:
            raise LLMError(f'LLM Error: {str(e)}', e)

        if not isinstance(completion, ChatCompletion) or hasattr(completion, 'error'):
            log("debug", "LLM completion error:", completion)
            raise LLMError("LLM error: No valid completion received")
        
        if not completion.choices:
            log("debug", "LLM completion has no choices:", completion)
            return (None, None) # Treated as "..."

        if not hasattr(completion.choices[0], 'message') or not completion.choices[0].message:
            log("debug", "LLM completion choice has no message:", completion)
            return (None, None) # Treated as "..."
        
        if hasattr(completion, 'usage') and completion.usage:
            log("debug", f'LLM completion usage', completion.usage)
        
        response_text = None
        if hasattr(completion.choices[0].message, 'content'):
            response_text = completion.choices[0].message.content
            if completion.choices[0].message.content is None or completion.choices[0].message.content == "":
                log("debug", "LLM completion no content:", completion)
                response_text = None
        else:
            log("debug", f'LLM completion without text')
            response_text = None

        response_actions = None
        if hasattr(completion.choices[0].message, 'tool_calls'):
            response_actions = completion.choices[0].message.tool_calls

        if response_text is None and response_actions is None:
             return (None, None)

        return (response_text, response_actions)

    def list_models(self) -> List[str]:
        try:
            models = self.client.models.list()
            return [model.id for model in models]
        except Exception as e:
            raise e

class OpenAIEmbeddingModel(EmbeddingModel):
    def __init__(self, base_url: str, api_key: str, model_name: str, extra_headers: Optional[dict] = None, extra_body: Optional[dict] = None):
        super().__init__(model_name)
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.extra_headers = extra_headers or {}
        self.extra_body = extra_body or {}

    def create_embedding(self, input_text: str) -> tuple[str, List[float]]:
        params: dict[str, Any] = {
            "model": self.model_name,
            "input": input_text,
            **self.extra_body
        }
        if self.extra_headers:
            params["extra_headers"] = self.extra_headers
            
        response = self.client.embeddings.create(**params)
        return (response.model, response.data[0].embedding)

class STTModel(ABC):
    model_name: str

    def __init__(self, model_name: str):
        self.model_name = model_name

    @abstractmethod
    def transcribe(self, audio: sr.AudioData) -> str:
        pass

class OpenAISTTModel(STTModel):
    def __init__(self, base_url: str, api_key: str, model_name: str, language: Optional[str] = None, prompt: Optional[str] = None):
        super().__init__(model_name)
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.language = language
        self.prompt = prompt

    def transcribe(self, audio: sr.AudioData) -> str:
        audio_raw = audio.get_raw_data(convert_rate=16000, convert_width=2)
        # Convert raw PCM data to numpy array
        audio_np = np.frombuffer(audio_raw, dtype=np.int16).astype(np.float32) / 32768.0
        
        # Create a BytesIO buffer for the Ogg file
        audio_ogg = io.BytesIO()
        
        # Write as Ogg Vorbis
        sf.write(audio_ogg, audio_np, 16000, format='OGG', subtype='VORBIS')
        audio_ogg.seek(0)
        audio_ogg.name = "audio.ogg"  # OpenAI needs a filename
        
        try:
            transcription = self.client.audio.transcriptions.create(
                model=self.model_name,
                file=audio_ogg,
                language=self.language if self.language else None, # pyright: ignore[reportArgumentType]
                prompt=self.prompt
            )
        except APIStatusError as e:
            log("debug", "STT error request:", e.request.method, e.request.url, e.request.headers)
            log("debug", "STT error response:", e.response.status_code, e.response.headers, e.response.read().decode('utf-8', errors='replace'))
            
            try:
                error: dict = e.body[0] if hasattr(e, 'body') and e.body and isinstance(e.body, list) else e.body # pyright: ignore[reportAssignmentType]
                message = error.get('error', {}).get('message', e.body if e.body else 'Unknown error')
            except:
                message = e.message
            
            raise LLMError(f'STT {e.response.reason_phrase}: {message}', e)
        
        text = transcription.text
        return text

class OpenAIMultiModalSTTModel(STTModel):
    def __init__(self, base_url: str, api_key: str, model_name: str, prompt: Optional[str] = None):
        super().__init__(model_name)
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.prompt = prompt

    def transcribe(self, audio: sr.AudioData) -> str:
        audio_raw = audio.get_raw_data(convert_rate=16000, convert_width=2)
        # Convert raw PCM data to numpy array
        audio_np = np.frombuffer(audio_raw, dtype=np.int16).astype(np.float32) / 32768.0
        
        # Create a BytesIO buffer for the Ogg file
        audio_wav = io.BytesIO()
        
        # Write as Ogg Vorbis
        sf.write(audio_wav, audio_np, 16000, format='WAV', subtype='PCM_16')
        audio_wav.seek(0)
        audio_wav.name = "audio.wav"  # OpenAI needs a filename
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role":"system", "content":
                        "You are a high quality transcription model. You are given audio input from the user, and return the transcribed text from the input. Do NOT add any additional text in your response, only respond with the text given by the user.\n" +
                        "The audio may be related to space sci-fi terminology like systems, equipment, and station names, specifically the game Elite Dangerous.\n" + 
                        #"Here is an example of the type of text you should return: <example>" + self.prompt + "</example>\n" +
                        "Always provide an exact transcription of the audio. If the user is not speaking or inaudible, return only the word 'silence'."
                    },
                    {"role": "user", "content": [{
                        "type": "text",
                        "text": "<input>"
                    },{
                        "type": "input_audio",
                        "input_audio": {
                            "data": base64.b64encode(audio_wav.getvalue()).decode('utf-8'),
                            "format": "wav"
                        }
                    },{
                        "type": "text",
                        "text": "</input>"
                    },]}
                ]
            )
        except APIStatusError as e:
            log("debug", "STT mm error request:", e.request.method, e.request.url, e.request.headers, e.request.read().decode('utf-8', errors='replace'))
            log("debug", "STT mm error response:", e.response.status_code, e.response.headers, e.response.read().decode('utf-8', errors='replace'))
            
            try:
                error: dict = e.body[0] if hasattr(e, 'body') and e.body and isinstance(e.body, list) else e.body # pyright: ignore[reportAssignmentType]
                message = error.get('error', {}).get('message', e.body if e.body else 'Unknown error')
            except:
                message = e.message
            
            raise LLMError(f'STT {e.response.reason_phrase}: {message}', e)
        
        if not response.choices or not hasattr(response.choices[0], 'message') or not hasattr(response.choices[0].message, 'content'):
            log('debug', "STT mm response is incomplete or malformed:", response)
            raise LLMError('STT completion error: Response incomplete or malformed')
        
        text = response.choices[0].message.content
        if not text:
            return ''
        if text.strip() == 'silence' or text.strip() == '':
            return ''
        return text.strip()

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

class TTSModel(ABC):
    model_name: str

    def __init__(self, model_name: str):
        self.model_name = model_name

    @abstractmethod
    def synthesize(self, text: str, voice: str) -> Iterable[bytes]:
        pass

class OpenAITTSModel(TTSModel):
    def __init__(self, base_url: str, api_key: str, model_name: str, speed: float = 1.0, voice_instructions: str | None = None):
        super().__init__(model_name)
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.speed = speed
        self.voice_instructions = voice_instructions

    def synthesize(self, text: str, voice: str) -> Iterable[bytes]:
        try:
            kwargs: SpeechCreateParams = {
                "model": self.model_name,
                "voice": voice, # pyright: ignore[reportArgumentType]
                "input": text,
                "response_format": "pcm",
                "speed": self.speed
            }
            if self.voice_instructions:
                kwargs["instructions"] = self.voice_instructions
            
            with self.client.audio.speech.with_streaming_response.create(**kwargs) as response:
                for chunk in response.iter_bytes(1024):
                    yield chunk
        except APIStatusError as e:
            log("debug", "TTS error request:", e.request.method, e.request.url, e.request.headers, e.request.read().decode('utf-8', errors='replace'))
            log("debug", "TTS error response:", e.response.status_code, e.response.headers, e.response.read().decode('utf-8', errors='replace'))
            
            try:
                error: dict = e.body[0] if hasattr(e, 'body') and e.body and isinstance(e.body, list) else e.body # pyright: ignore[reportAssignmentType]
                message = error.get('error', {}).get('message', e.body if e.body else 'Unknown error')
            except:
                message = e.message
            
            raise LLMError(f'TTS {e.response.reason_phrase}: {message}', e)

class EdgeTTSModel(TTSModel):
    def __init__(self, model_name: str, speed: float = 1.0):
        super().__init__(model_name)
        self.speed = speed
        self.prebuffer_size = 4

    def synthesize(self, text: str, voice: str) -> Iterable[bytes]:
        rate = f"+{int((float(self.speed) - 1) * 100)}%" if float(self.speed) > 1 else f"-{int((1 - float(self.speed)) * 100)}%"
        response = edge_tts.Communicate(text, voice=voice, rate=rate)
        
        pcm_stream = miniaudio.stream_any(
            source=Mp3Stream(response.stream_sync(), self.prebuffer_size),
            source_format=miniaudio.FileFormat.MP3,
            output_format=miniaudio.SampleFormat.SIGNED16,
            nchannels=1,
            sample_rate=24000,
            frames_to_read=1024 // 2
        )

        for i in pcm_stream:
            yield i.tobytes()

def create_llm_model(provider: str, config: dict, prefix: str = "llm") -> LLMModel:
    base_url = str(config.get(f"{prefix}_endpoint", ""))
    api_key = str(config.get("api_key") if config.get(f"{prefix}_api_key", "") == "" else config.get(f"{prefix}_api_key"))
    model_name = str(config.get(f"{prefix}_model_name", ""))
    temperature = float(config.get(f"{prefix}_temperature", 1.0))
    reasoning_effort = config.get(f"{prefix}_reasoning_effort", None)
    if reasoning_effort:
        reasoning_effort = str(reasoning_effort)
    
    if provider == "openai":
        if not base_url:
            base_url = "https://api.openai.com/v1"
    elif provider == "google-ai-studio":
        if not base_url:
            base_url = "https://generativelanguage.googleapis.com/v1beta"
    elif provider == "openrouter":
        if not base_url:
            base_url = "https://openrouter.ai/api/v1"
            
    extra_body = {}
    extra_headers = {}

    return OpenAILLMModel(
        base_url=base_url,
        api_key=api_key,
        model_name=model_name,
        temperature=temperature,
        reasoning_effort=reasoning_effort,
        extra_body=extra_body,
        extra_headers=extra_headers
    )

def create_embedding_model(provider: str, config: dict, prefix: str = "embedding") -> EmbeddingModel:
    base_url = str(config.get(f"{prefix}_endpoint", ""))
    api_key = str(config.get("api_key") if config.get(f"{prefix}_api_key", "") == "" else config.get(f"{prefix}_api_key"))
    model_name = str(config.get(f"{prefix}_model_name", ""))
    
    if provider == "openai":
        if not base_url:
            base_url = "https://api.openai.com/v1"
    elif provider == "google-ai-studio":
        if not base_url:
            base_url = "https://generativelanguage.googleapis.com/v1beta"
    elif provider == "openrouter":
        if not base_url:
            base_url = "https://openrouter.ai/api/v1"
          

    return OpenAIEmbeddingModel(
        base_url=base_url,
        api_key=api_key,
        model_name=model_name,
    )

def create_stt_model(provider: str, config: dict, prefix: str = "stt") -> STTModel | None:
    if provider == 'none':
        return None

    base_url = str(config.get(f"{prefix}_endpoint", ""))
    api_key = str(config.get("api_key") if config.get(f"{prefix}_api_key", "") == "" else config.get(f"{prefix}_api_key"))
    model_name = str(config.get(f"{prefix}_model_name", "whisper-1"))
    language = config.get(f"{prefix}_language", None)
    prompt = config.get(f"{prefix}_prompt", "COVAS, give me a status update... and throw in something inspiring, would you?")

    if provider == "openai" or provider == "custom" or provider == "local-ai-server":
        if provider == "openai" and not base_url:
            base_url = "https://api.openai.com/v1"
        return OpenAISTTModel(base_url, api_key, model_name, language, prompt)
    
    elif provider == "google-ai-studio" or provider == "custom-multi-modal":
        if provider == "google-ai-studio" and not base_url:
            base_url = "https://generativelanguage.googleapis.com/v1beta"
        return OpenAIMultiModalSTTModel(base_url, api_key, model_name, prompt)
    
    return None

def create_tts_model(provider: str, config: dict, prefix: str = "tts") -> TTSModel | None:
    if provider == 'none':
        return None

    base_url = str(config.get(f"{prefix}_endpoint", ""))
    api_key = str(config.get("api_key") if config.get(f"{prefix}_api_key", "") == "" else config.get(f"{prefix}_api_key"))
    model_name = str(config.get(f"{prefix}_model_name", "tts-1"))
    speed = float(config.get(f"{prefix}_speed", 1.0))
    voice_instructions = config.get(f"{prefix}_voice_instructions", "") or None

    if provider == "openai" or provider == "custom" or provider == "local-ai-server":
        if provider == "openai" and not base_url:
            base_url = "https://api.openai.com/v1"
        return OpenAITTSModel(base_url, api_key, model_name, speed, voice_instructions)
    
    elif provider == "edge-tts":
        return EdgeTTSModel(model_name, speed)
    
    return None
