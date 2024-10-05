import argparse
import io
import soundfile as sf
from pick import pick

from lib.localSTT import init_stt, stt, stt_models_names
from lib.localTTS import init_tts, tts, tts_model_names


parser = argparse.ArgumentParser()

parser.add_argument("--stt", default=None, help="the stt model to use")
parser.add_argument("--tts", default=None, help="the tts model to use")
args = parser.parse_args()

use_args = args.tts or args.stt

tts_model_name, _ = (args.tts, 0) if use_args else pick(options=tts_model_names, title='Select a TTS model')
stt_model_name, _ = (args.stt, 0) if use_args else pick(options=stt_models_names, title='Select a STT model')

if tts_model_name == 'tts-1':
    tts_model_name = tts_model_names[0]
if stt_model_name == 'whisper-1':
    stt_model_name = stt_models_names[0]

print(f'Selected TTS model: {tts_model_name}')
print(f'Selected STT model: {stt_model_name}')

tts_model = init_tts(tts_model_name) if tts_model_name else None,
stt_model = init_stt(stt_model_name) if tts_model_name else None


# create flask api endpoint
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/v1/audio/speech', methods=['POST'])
def createSpeech():
    if not tts_model:
        return jsonify({'error': 'tts model not available'}), 500
    data = request.json
    
    voice = data.get('voice')
    input = data.get('input')
    if not input:
        return jsonify({'error': 'input is required'}), 400
    speed = float(data.get('speed', 1.0))

    audio = tts(tts_model, input, speed, voice)

    response_format = data.get('response_format', 'wav')
    if response_format == 'pcm':
        # TODO implement streaming response
        
        buffer = io.BytesIO()
        buffer.name = 'audio.pcm'
        sf.write(buffer, audio.samples, audio.sample_rate, subtype="PCM_16", format="RAW")
        buffer.seek(0)
        return buffer.read()

    elif response_format == 'wav':
        buffer = io.BytesIO()
        buffer.name = 'audio.wav'
        sf.write(buffer, audio.samples, audio.sample_rate, subtype="PCM_16", format="WAV")
        buffer.seek(0)
        return buffer.read()

    else:
        # TODO implement other response formats, spec compliance
        return jsonify({'error': 'invalid response_format'}), 400

@app.route('/v1/audio/transcriptions', methods=['POST'])
def createTranscription():
    if not stt_model:
        return jsonify({'error': 'stt model not available'}), 500
    # decode form data
    data = request.form

    language = data.get('language', 'en')
    name, file = next(request.files.items())
    print(name, file)

    segments, info = stt(stt_model, file.stream.read(), language)
    text = ''.join([segment.text for segment in segments])
    return jsonify({'text': text}) # TODO more details, spec compliance

if __name__ == '__main__':
    app.run(port=8080, host='::', threaded=True)

"""
sample curl request to create a speech:
curl -X POST "http://localhost:8080/v1/audio/speech" -H "Content-Type: application/json" -d "{\"input\":\"Hello, world!\", \"response_format\":\"wav\"}" > audio.wav

sample curl request to create a transcription:
curl -X POST "http://localhost:8080/v1/audio/transcriptions" -F "audio=@./audio.wav" -F "language=en-US"
"""