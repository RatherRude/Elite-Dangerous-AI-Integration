import io
from faster_whisper import WhisperModel
import samplerate
import soundfile as sf

def init_stt():
    model = WhisperModel("distil-medium.en", device="cpu", compute_type="int8")
    return model

def stt(model: WhisperModel, wav: bytes, language="en-US"):
    # convert wav bytes to 16k S16_LE
    audio, rate = sf.read(io.BytesIO(wav))
    audio = samplerate.resample(audio, 16000 / rate, 'sinc_best')

    gen, info = model.transcribe(audio, language=language)
    
    segments = []
    for segment in gen:
        segments.append(segment)
    
    return segments, info