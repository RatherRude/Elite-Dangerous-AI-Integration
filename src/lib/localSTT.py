import io
import time
from cached_path import cached_path
from pywhispercpp.model import Model
import samplerate
import soundfile as sf

stt_models_names = [
    'ggerganov/whisper.cpp/ggml-base-q5_1.bin',
    'ggerganov/whisper.cpp/ggml-base.bin',
    'ggerganov/whisper.cpp/ggml-base.en-q5_1.bin',
    'ggerganov/whisper.cpp/ggml-base.en.bin',
    'ggerganov/whisper.cpp/ggml-large-v1.bin',
    'ggerganov/whisper.cpp/ggml-large-v2-q5_0.bin',
    'ggerganov/whisper.cpp/ggml-large-v2.bin',
    'ggerganov/whisper.cpp/ggml-large-v3-q5_0.bin',
    'ggerganov/whisper.cpp/ggml-large-v3-turbo-q5_0.bin',
    'ggerganov/whisper.cpp/ggml-large-v3-turbo.bin',
    'ggerganov/whisper.cpp/ggml-large-v3.bin',
    'ggerganov/whisper.cpp/ggml-medium-q5_0.bin',
    'ggerganov/whisper.cpp/ggml-medium.bin',
    'ggerganov/whisper.cpp/ggml-medium.en-q5_0.bin',
    'ggerganov/whisper.cpp/ggml-medium.en.bin',
    'ggerganov/whisper.cpp/ggml-small-q5_1.bin',
    'ggerganov/whisper.cpp/ggml-small.bin',
    'ggerganov/whisper.cpp/ggml-small.en-q5_1.bin',
    'ggerganov/whisper.cpp/ggml-small.en.bin',
    'ggerganov/whisper.cpp/ggml-tiny-q5_1.bin',
    'ggerganov/whisper.cpp/ggml-tiny.bin',
    'ggerganov/whisper.cpp/ggml-tiny.en-q5_1.bin',
    'ggerganov/whisper.cpp/ggml-tiny.en-q8_0.bin',
    'ggerganov/whisper.cpp/ggml-tiny.en.bin',
    'distil-whisper/distil-medium.en/ggml-medium-32-2.en.bin',
    'distil-whisper/distil-large-v2/ggml-large-32-2.en.bin',
    'distil-whisper/distil-large-v3-ggml/ggml-distil-large-v3.bin'
]

def init_stt(model_name="distil-medium.en"):
    file = cached_path("hf://"+model_name).as_posix()

    model = Model(file)
    return model

def stt(model: Model, wav: bytes, language="en-US"):
    # convert wav bytes to 16k S16_LE

    start = time.time()
    audio, rate = sf.read(io.BytesIO(wav))
    end = time.time()
    print("Read time:", end - start)
    start = time.time()
    audio = samplerate.resample(audio, 16000 / rate, 'sinc_best')
    end = time.time()
    print("Resample time:", end - start)

    start = time.time()
    segments = model.transcribe(audio)
    #gen, info = model.transcribe(audio)
    #
    #segments = []
    #for segment in gen:
    #    segments.append(segment)
    
    end = time.time()
    print("Transcribe time:", end - start)
    
    return segments, None