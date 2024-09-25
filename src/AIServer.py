import io
import soundfile as sf
from pick import pick

from lib.localSTT import init_stt, stt, stt_models_names
from lib.localTTS import init_tts, tts, tts_model_names

tts_model, _ = pick(options=tts_model_names, title='Select a TTS model')
stt_model, _ = pick(options=stt_models_names, title='Select a STT model')

print(f'Selected TTS model: {tts_model}')
print(f'Selected STT model: {stt_model}')

models = {
    'tts-1': init_tts(tts_model),
    'whisper-1': init_stt(stt_model)
}

# create flask api endpoint
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/v1/audio/speech', methods=['POST'])
def createSpeech():
    data = request.json
    
    model = models[data.get('model', 'tts-1')]
    voice = data.get('voice')
    input = data.get('input')
    if not input:
        return jsonify({'error': 'input is required'}), 400
    speed = float(data.get('speed', 1.0))

    audio = tts(model, input, speed, voice)

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
    # decode form data
    data = request.form

    model = models[data.get('model', 'whisper-1')]
    language = data.get('language', 'en')
    name, file = next(request.files.items())
    print(name, file)

    segments, info = stt(model, file.stream.read(), language)
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