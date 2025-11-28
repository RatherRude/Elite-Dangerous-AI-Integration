"""
Google Vertex AI Plugin for COVAS:NEXT
Provides Google Cloud Speech-to-Text and Text-to-Speech capabilities.
"""

from typing import override, Iterable, Any
import io
import numpy as np
import soundfile as sf
import speech_recognition as sr

from lib.PluginHelper import PluginHelper, STTModel, TTSModel, LLMModel, EmbeddingModel
from lib.PluginSettingDefinitions import (
    SettingsGrid,
    TextSetting,
    NumericalSetting,
    ModelProviderDefinition,
)
from lib.PluginBase import PluginBase, PluginManifest
from lib.Logger import log


class GoogleVertexSTTModel(STTModel):
    """Google Cloud Speech-to-Text model implementation."""
    
    def __init__(self, credentials_json: str, language: str = "en-US"):
        super().__init__("google-vertex-stt")
        self.credentials_json = credentials_json
        self.language = language
        self._client: Any = None
    
    def _get_client(self) -> Any:
        """Lazily initialize the Speech client."""
        if self._client is None:
            try:
                from google.cloud import speech
                from google.oauth2 import service_account
                import json
                
                credentials_dict = json.loads(self.credentials_json)
                credentials = service_account.Credentials.from_service_account_info(credentials_dict)
                self._client = speech.SpeechClient(credentials=credentials)
            except ImportError:
                raise ImportError("google-cloud-speech is not installed. Install it with: pip install google-cloud-speech")
            except Exception as e:
                log('error', f"Failed to initialize Google Speech client: {e}")
                raise
        return self._client
    
    def transcribe(self, audio: sr.AudioData) -> str:
        """Transcribe audio using Google Cloud Speech-to-Text."""
        from google.cloud import speech
        
        client = self._get_client()
        
        # Convert audio to the format expected by Google
        audio_raw = audio.get_raw_data(convert_rate=16000, convert_width=2)
        
        # Create recognition config
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code=self.language,
            enable_automatic_punctuation=True,
        )
        
        # Create audio object
        audio_content = speech.RecognitionAudio(content=audio_raw)
        
        try:
            # Perform synchronous recognition
            response = client.recognize(config=config, audio=audio_content)
            
            # Extract transcript
            if response.results:
                transcript = " ".join(
                    result.alternatives[0].transcript 
                    for result in response.results 
                    if result.alternatives
                )
                return transcript.strip()
            
            return ""
        except Exception as e:
            log('error', f"Google STT transcription failed: {e}")
            raise


class GoogleVertexTTSModel(TTSModel):
    """Google Cloud Text-to-Speech model implementation."""
    
    def __init__(
        self, 
        credentials_json: str, 
        language: str = "en-US",
        speaking_rate: float = 1.0,
        pitch: float = 0.0,
    ):
        super().__init__("google-vertex-tts")
        self.credentials_json = credentials_json
        self.language = language
        self.speaking_rate = speaking_rate
        self.pitch = pitch
        self._client: Any = None
    
    def _get_client(self) -> Any:
        """Lazily initialize the TextToSpeech client."""
        if self._client is None:
            try:
                from google.cloud import texttospeech
                from google.oauth2 import service_account
                import json
                
                credentials_dict = json.loads(self.credentials_json)
                credentials = service_account.Credentials.from_service_account_info(credentials_dict)
                self._client = texttospeech.TextToSpeechClient(credentials=credentials)
            except ImportError:
                raise ImportError("google-cloud-texttospeech is not installed. Install it with: pip install google-cloud-texttospeech")
            except Exception as e:
                log('error', f"Failed to initialize Google TTS client: {e}")
                raise
        return self._client
    
    def synthesize(self, text: str, voice: str) -> Iterable[bytes]:
        """Synthesize speech using Google Cloud Text-to-Speech with streaming."""
        from google.cloud import texttospeech
        
        client = self._get_client()
        
        # Set up synthesis input
        synthesis_input = texttospeech.SynthesisInput(text=text)
        
        # Configure voice - voice parameter is the voice name (e.g., "en-US-Neural2-A")
        voice_params = texttospeech.VoiceSelectionParams(
            language_code=self.language,
            name=voice if voice else None,
        )
        
        # Configure audio output - use LINEAR16 (PCM) for streaming playback
        # Note: The existing TTS system expects PCM audio at 24000 Hz
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            sample_rate_hertz=24000,
            speaking_rate=self.speaking_rate,
            pitch=self.pitch,
        )
        
        try:
            # Use streaming synthesis for real-time audio
            config_request = texttospeech.StreamingSynthesizeRequest(
                streaming_config=texttospeech.StreamingSynthesizeConfig(
                    voice=voice_params,
                )
            )
            
            # Generator for streaming requests
            def request_generator():
                # First request contains the config
                yield texttospeech.StreamingSynthesizeRequest(
                    streaming_config=texttospeech.StreamingSynthesizeConfig(
                        voice=voice_params,
                        streaming_audio_config=texttospeech.StreamingAudioConfig(
                            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                            sample_rate_hertz=24000,
                        ),
                    )
                )
                # Second request contains the text input
                yield texttospeech.StreamingSynthesizeRequest(
                    input=texttospeech.StreamingSynthesisInput(text=text)
                )
            
            # Try streaming synthesis first
            try:
                streaming_responses = client.streaming_synthesize(request_generator())
                for response in streaming_responses:
                    if response.audio_content:
                        yield response.audio_content
            except Exception as streaming_error:
                # Fall back to non-streaming if streaming isn't supported
                log('debug', f"Streaming TTS not available, falling back to batch: {streaming_error}")
                response = client.synthesize_speech(
                    input=synthesis_input,
                    voice=voice_params,
                    audio_config=audio_config,
                )
                # Yield audio in chunks for consistency
                chunk_size = 4096
                audio_content = response.audio_content
                for i in range(0, len(audio_content), chunk_size):
                    yield audio_content[i:i + chunk_size]
                    
        except Exception as e:
            log('error', f"Google TTS synthesis failed: {e}")
            raise


class GoogleVertexPlugin(PluginBase):
    """
    Built-in plugin providing Google Cloud Vertex AI Speech services.
    Supports Speech-to-Text and Text-to-Speech via Google Cloud APIs.
    """
    
    def __init__(self, plugin_manifest: PluginManifest):
        super().__init__(plugin_manifest)
        
        # Define model providers for STT and TTS
        self.model_providers: list[ModelProviderDefinition] | None = [
            ModelProviderDefinition(
                kind='stt',
                id='google-vertex-stt',
                label='Google Vertex STT',
                settings_config=[
                    SettingsGrid(
                        key='credentials',
                        label='Credentials',
                        fields=[
                            TextSetting(
                                key='gcp_credentials_json',
                                label='GCP Service Account JSON',
                                type='text',
                                readonly=False,
                                placeholder='Paste your service account JSON here',
                                default_value='',
                                max_length=None,
                                min_length=None,
                                hidden=True,
                            ),
                        ]
                    ),
                    SettingsGrid(
                        key='settings',
                        label='Settings',
                        fields=[
                            TextSetting(
                                key='gcp_stt_language',
                                label='Language Code',
                                type='text',
                                readonly=False,
                                placeholder='en-US',
                                default_value='en-US',
                                max_length=None,
                                min_length=None,
                                hidden=False,
                            ),
                        ]
                    ),
                ],
            ),
            ModelProviderDefinition(
                kind='tts',
                id='google-vertex-tts',
                label='Google Vertex TTS',
                settings_config=[
                    SettingsGrid(
                        key='credentials',
                        label='Credentials',
                        fields=[
                            TextSetting(
                                key='gcp_credentials_json',
                                label='GCP Service Account JSON',
                                type='text',
                                readonly=False,
                                placeholder='Paste your service account JSON here',
                                default_value='',
                                max_length=None,
                                min_length=None,
                                hidden=True,
                            ),
                        ]
                    ),
                    SettingsGrid(
                        key='settings',
                        label='Settings',
                        fields=[
                            TextSetting(
                                key='gcp_tts_language',
                                label='Language Code',
                                type='text',
                                readonly=False,
                                placeholder='en-US',
                                default_value='en-US',
                                max_length=None,
                                min_length=None,
                                hidden=False,
                            ),
                            TextSetting(
                                key='gcp_tts_voice',
                                label='Voice Name',
                                type='text',
                                readonly=False,
                                placeholder='en-US-Neural2-A',
                                default_value='en-US-Neural2-A',
                                max_length=None,
                                min_length=None,
                                hidden=False,
                            ),
                            NumericalSetting(
                                key='gcp_tts_speaking_rate',
                                label='Speaking Rate',
                                type='number',
                                readonly=False,
                                placeholder='1.0',
                                default_value=1.0,
                                min_value=0.25,
                                max_value=4.0,
                                step=0.05,
                            ),
                            NumericalSetting(
                                key='gcp_tts_pitch',
                                label='Pitch',
                                type='number',
                                readonly=False,
                                placeholder='0.0',
                                default_value=0.0,
                                min_value=-20.0,
                                max_value=20.0,
                                step=0.5,
                            ),
                        ]
                    ),
                ],
            ),
        ]
    
    @override
    def create_model(self, provider_id: str, settings: dict[str, Any]) -> LLMModel | STTModel | TTSModel | EmbeddingModel:
        """Create a model instance for the given provider."""
        
        if provider_id == 'google-vertex-stt':
            credentials_json = settings.get('gcp_credentials_json', '')
            if not credentials_json:
                raise ValueError('Google Vertex STT: No credentials provided')
            
            language = settings.get('gcp_stt_language', 'en-US')
            
            return GoogleVertexSTTModel(
                credentials_json=credentials_json,
                language=language,
            )
        
        elif provider_id == 'google-vertex-tts':
            credentials_json = settings.get('gcp_credentials_json', '')
            if not credentials_json:
                raise ValueError('Google Vertex TTS: No credentials provided')
            
            language = settings.get('gcp_tts_language', 'en-US')
            speaking_rate = float(settings.get('gcp_tts_speaking_rate', 1.0))
            pitch = float(settings.get('gcp_tts_pitch', 0.0))
            
            return GoogleVertexTTSModel(
                credentials_json=credentials_json,
                language=language,
                speaking_rate=speaking_rate,
                pitch=pitch,
            )
        
        raise ValueError(f'Unknown Google Vertex provider: {provider_id}')
    