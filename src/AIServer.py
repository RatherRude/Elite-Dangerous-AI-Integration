import io
import json
from typing import TypedDict
import soundfile as sf
from pick import pick

from lib.localSTT import init_stt, stt, stt_models_names
from lib.localTTS import init_tts, tts, tts_model_names
from lib.localLLM import init_llm, llm, llm_model_names

class Config(TypedDict):
    tts_model_name: str
    stt_model_name: str
    llm_model_name: str
    host: str
    port: int
    
def load_config() -> Config:
    config: Config = {}
    try:
        with open('aiserver.config.json', 'r') as f:
            config = Config(**json.load(f))
    except FileNotFoundError:
        pass
    except json.JSONDecodeError:
        pass
    
    if not 'tts_model_name' in config:
        config['tts_model_name'] = pick(options=tts_model_names, title='Select a TTS model')[0]

    if not 'stt_model_name' in config:
        config['stt_model_name'] = pick(options=stt_models_names, title='Select a STT model')[0]
        
    if not 'llm_model_name' in config:
        config['llm_model_name'] = pick(options=llm_model_names, title='Select a LLM model')[0]
    
    if not 'host' in config:
        config['host'] = input('Enter the IP to bind or leave empty for default [127.0.0.1]: ') or '127.0.0.1'
        
    if not 'port' in config:
        config['port'] = int(input('Enter the port number or leave empty for default port [8080]: ') or '8080')

    if config['port'] < 1025 or config['port'] > 65535:
        raise ValueError('Port number must be between 1025 and 65535')

    print(f'Selected STT model: {config["stt_model_name"]}')
    print(f'Selected LLM model: {config["llm_model_name"]}')
    print(f'Selected TTS model: {config["tts_model_name"]}')
    return config

config = load_config()

llm_model = init_llm(config['llm_model_name'])
tts_model = init_tts(config['tts_model_name'])
stt_model = init_stt(config['stt_model_name'])

# create flask api endpoint
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/v1/chat/completions', methods=['POST'])
def createChatCompletion():
    chat = request.json
    if not llm_model:
        return jsonify({'error': 'model not found'}), 400
    if 'messages' not in chat:
        return jsonify({'error': 'messages is required'}), 400
    
    print(chat)

    completion = llm(llm_model, chat)
    return jsonify(completion)

@app.route('/v1/audio/speech', methods=['POST'])
def createSpeech():
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
    # decode form data
    data = request.form

    language = data.get('language', 'en')
    name, file = next(request.files.items())
    print(name, file)

    segments, info = stt(stt_model, file.stream.read(), language)
    text = ''.join([segment.text for segment in segments])
    return jsonify({'text': text}) # TODO more details, spec compliance

if __name__ == '__main__':
    app.run(port=config['port'], host=config['host'], threaded=True)

"""
sample curl request to create a speech:
curl -X POST "http://localhost:8080/v1/audio/speech" -H "Content-Type: application/json" -d "{\"input\":\"Hello, world!\", \"response_format\":\"wav\"}" > audio.wav

sample curl request to create a transcription:
curl -X POST "http://localhost:8080/v1/audio/transcriptions" -F "audio=@./audio.wav" -F "language=en-US"
"""