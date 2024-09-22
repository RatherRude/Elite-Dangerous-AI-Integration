import time
from cached_path import cached_path
import numpy as np
import sherpa_onnx
import samplerate

tts_model_names = [
  'vits-cantonese-hf-xiaomaiiwn.tar.bz2',
  'vits-coqui-bg-cv.tar.bz2',
  'vits-coqui-bn-custom_female.tar.bz2',
  'vits-coqui-cs-cv.tar.bz2',
  'vits-coqui-da-cv.tar.bz2',
  'vits-coqui-de-css10.tar.bz2',
  'vits-coqui-en-ljspeech-neon.tar.bz2',
  'vits-coqui-en-ljspeech.tar.bz2',
  'vits-coqui-en-vctk.tar.bz2',
  'vits-coqui-es-css10.tar.bz2',
  'vits-coqui-et-cv.tar.bz2',
  'vits-coqui-fi-css10.tar.bz2',
  'vits-coqui-fr-css10.tar.bz2',
  'vits-coqui-ga-cv.tar.bz2',
  'vits-coqui-hr-cv.tar.bz2',
  'vits-coqui-lt-cv.tar.bz2',
  'vits-coqui-lv-cv.tar.bz2',
  'vits-coqui-mt-cv.tar.bz2',
  'vits-coqui-nl-css10.tar.bz2',
  'vits-coqui-pl-mai_female.tar.bz2',
  'vits-coqui-pt-cv.tar.bz2',
  'vits-coqui-ro-cv.tar.bz2',
  'vits-coqui-sk-cv.tar.bz2',
  'vits-coqui-sl-cv.tar.bz2',
  'vits-coqui-sv-cv.tar.bz2',
  'vits-coqui-uk-mai.tar.bz2',
  'vits-icefall-en_US-ljspeech-low.tar.bz2',
  'vits-icefall-en_US-ljspeech-medium.tar.bz2',
  'vits-icefall-zh-aishell3.tar.bz2',
  'vits-ljs.tar.bz2',
  'vits-melo-tts-zh_en.tar.bz2',
  'vits-mimic3-af_ZA-google-nwu_low.tar.bz2',
  'vits-mimic3-bn-multi_low.tar.bz2',
  'vits-mimic3-el_GR-rapunzelina_low.tar.bz2',
  'vits-mimic3-es_ES-m-ailabs_low.tar.bz2',
  'vits-mimic3-fa-haaniye_low.tar.bz2',
  'vits-mimic3-fi_FI-harri-tapani-ylilammi_low.tar.bz2',
  'vits-mimic3-gu_IN-cmu-indic_low.tar.bz2',
  'vits-mimic3-hu_HU-diana-majlinger_low.tar.bz2',
  'vits-mimic3-ko_KO-kss_low.tar.bz2',
  'vits-mimic3-ne_NP-ne-google_low.tar.bz2',
  'vits-mimic3-pl_PL-m-ailabs_low.tar.bz2',
  'vits-mimic3-tn_ZA-google-nwu_low.tar.bz2',
  'vits-mimic3-vi_VN-vais1000_low.tar.bz2',
  'vits-mms-deu.tar.bz2',
  'vits-mms-eng.tar.bz2',
  'vits-mms-fra.tar.bz2',
  'vits-mms-nan.tar.bz2',
  'vits-mms-rus.tar.bz2',
  'vits-mms-spa.tar.bz2',
  'vits-mms-tha.tar.bz2',
  'vits-mms-ukr.tar.bz2',
  'vits-piper-ar_JO-kareem-low.tar.bz2',
  'vits-piper-ar_JO-kareem-medium.tar.bz2',
  'vits-piper-ca_ES-upc_ona-medium.tar.bz2',
  'vits-piper-ca_ES-upc_ona-x_low.tar.bz2',
  'vits-piper-ca_ES-upc_pau-x_low.tar.bz2',
  'vits-piper-cs_CZ-jirka-low.tar.bz2',
  'vits-piper-cs_CZ-jirka-medium.tar.bz2',
  'vits-piper-cy_GB-gwryw_gogleddol-medium.tar.bz2',
  'vits-piper-da_DK-talesyntese-medium.tar.bz2',
  'vits-piper-de_DE-eva_k-x_low.tar.bz2',
  'vits-piper-de_DE-karlsson-low.tar.bz2',
  'vits-piper-de_DE-kerstin-low.tar.bz2',
  'vits-piper-de_DE-pavoque-low.tar.bz2',
  'vits-piper-de_DE-ramona-low.tar.bz2',
  'vits-piper-de_DE-thorsten-high.tar.bz2',
  'vits-piper-de_DE-thorsten-low.tar.bz2',
  'vits-piper-de_DE-thorsten-medium.tar.bz2',
  'vits-piper-de_DE-thorsten_emotional-medium.tar.bz2',
  'vits-piper-el_GR-rapunzelina-low.tar.bz2',
  'vits-piper-en_GB-alan-low.tar.bz2',
  'vits-piper-en_GB-alan-medium.tar.bz2',
  'vits-piper-en_GB-alba-medium.tar.bz2',
  'vits-piper-en_GB-aru-medium.tar.bz2',
  'vits-piper-en_GB-cori-high.tar.bz2',
  'vits-piper-en_GB-cori-medium.tar.bz2',
  'vits-piper-en_GB-jenny_dioco-medium.tar.bz2',
  'vits-piper-en_GB-northern_english_male-medium.tar.bz2',
  'vits-piper-en_GB-semaine-medium.tar.bz2',
  'vits-piper-en_GB-southern_english_female-low.tar.bz2',
  'vits-piper-en_GB-southern_english_female-medium.tar.bz2',
  'vits-piper-en_GB-southern_english_female_medium.tar.bz2',
  'vits-piper-en_GB-southern_english_male-medium.tar.bz2',
  'vits-piper-en_GB-sweetbbak-amy.tar.bz2',
  'vits-piper-en_GB-vctk-medium.tar.bz2',
  'vits-piper-en_US-amy-low.tar.bz2',
  'vits-piper-en_US-amy-medium.tar.bz2',
  'vits-piper-en_US-arctic-medium.tar.bz2',
  'vits-piper-en_US-bryce-medium.tar.bz2',
  'vits-piper-en_US-danny-low.tar.bz2',
  'vits-piper-en_US-glados.tar.bz2',
  'vits-piper-en_US-hfc_female-medium.tar.bz2',
  'vits-piper-en_US-hfc_male-medium.tar.bz2',
  'vits-piper-en_US-joe-medium.tar.bz2',
  'vits-piper-en_US-john-medium.tar.bz2',
  'vits-piper-en_US-kathleen-low.tar.bz2',
  'vits-piper-en_US-kristin-medium.tar.bz2',
  'vits-piper-en_US-kusal-medium.tar.bz2',
  'vits-piper-en_US-l2arctic-medium.tar.bz2',
  'vits-piper-en_US-lessac-high.tar.bz2',
  'vits-piper-en_US-lessac-low.tar.bz2',
  'vits-piper-en_US-lessac-medium.tar.bz2',
  'vits-piper-en_US-libritts-high.tar.bz2',
  'vits-piper-en_US-libritts_r-medium.tar.bz2',
  'vits-piper-en_US-ljspeech-high.tar.bz2',
  'vits-piper-en_US-ljspeech-medium.tar.bz2',
  'vits-piper-en_US-norman-medium.tar.bz2',
  'vits-piper-en_US-ryan-high.tar.bz2',
  'vits-piper-en_US-ryan-low.tar.bz2',
  'vits-piper-en_US-ryan-medium.tar.bz2',
  'vits-piper-es-glados-medium.tar.bz2',
  'vits-piper-es_ES-carlfm-x_low.tar.bz2',
  'vits-piper-es_ES-davefx-medium.tar.bz2',
  'vits-piper-es_ES-sharvard-medium.tar.bz2',
  'vits-piper-es_MX-ald-medium.tar.bz2',
  'vits-piper-es_MX-claude-high.tar.bz2',
  'vits-piper-fa-haaniye_low.tar.bz2',
  'vits-piper-fa_IR-amir-medium.tar.bz2',
  'vits-piper-fa_IR-gyro-medium.tar.bz2',
  'vits-piper-fi_FI-harri-low.tar.bz2',
  'vits-piper-fi_FI-harri-medium.tar.bz2',
  'vits-piper-fr_FR-gilles-low.tar.bz2',
  'vits-piper-fr_FR-siwis-low.tar.bz2',
  'vits-piper-fr_FR-siwis-medium.tar.bz2',
  'vits-piper-fr_FR-tjiho-model1.tar.bz2',
  'vits-piper-fr_FR-tjiho-model2.tar.bz2',
  'vits-piper-fr_FR-tjiho-model3.tar.bz2',
  'vits-piper-fr_FR-tom-medium.tar.bz2',
  'vits-piper-fr_FR-upmc-medium.tar.bz2',
  'vits-piper-hu_HU-anna-medium.tar.bz2',
  'vits-piper-hu_HU-berta-medium.tar.bz2',
  'vits-piper-hu_HU-imre-medium.tar.bz2',
  'vits-piper-is_IS-bui-medium.tar.bz2',
  'vits-piper-is_IS-salka-medium.tar.bz2',
  'vits-piper-is_IS-steinn-medium.tar.bz2',
  'vits-piper-is_IS-ugla-medium.tar.bz2',
  'vits-piper-it_IT-paola-medium.tar.bz2',
  'vits-piper-it_IT-riccardo-x_low.tar.bz2',
  'vits-piper-ka_GE-natia-medium.tar.bz2',
  'vits-piper-kk_KZ-iseke-x_low.tar.bz2',
  'vits-piper-kk_KZ-issai-high.tar.bz2',
  'vits-piper-kk_KZ-raya-x_low.tar.bz2',
  'vits-piper-lb_LU-marylux-medium.tar.bz2',
  'vits-piper-ne_NP-google-medium.tar.bz2',
  'vits-piper-ne_NP-google-x_low.tar.bz2',
  'vits-piper-nl_BE-nathalie-medium.tar.bz2',
  'vits-piper-nl_BE-nathalie-x_low.tar.bz2',
  'vits-piper-nl_BE-rdh-medium.tar.bz2',
  'vits-piper-nl_BE-rdh-x_low.tar.bz2',
  'vits-piper-no_NO-talesyntese-medium.tar.bz2',
  'vits-piper-pl_PL-darkman-medium.tar.bz2',
  'vits-piper-pl_PL-gosia-medium.tar.bz2',
  'vits-piper-pl_PL-mc_speech-medium.tar.bz2',
  'vits-piper-pt_BR-edresson-low.tar.bz2',
  'vits-piper-pt_BR-faber-medium.tar.bz2',
  'vits-piper-pt_PT-tugao-medium.tar.bz2',
  'vits-piper-ro_RO-mihai-medium.tar.bz2',
  'vits-piper-ru_RU-denis-medium.tar.bz2',
  'vits-piper-ru_RU-dmitri-medium.tar.bz2',
  'vits-piper-ru_RU-irina-medium.tar.bz2',
  'vits-piper-ru_RU-ruslan-medium.tar.bz2',
  'vits-piper-sk_SK-lili-medium.tar.bz2',
  'vits-piper-sl_SI-artur-medium.tar.bz2',
  'vits-piper-sr_RS-serbski_institut-medium.tar.bz2',
  'vits-piper-sv_SE-nst-medium.tar.bz2',
  'vits-piper-sw_CD-lanfrica-medium.tar.bz2',
  'vits-piper-tr_TR-dfki-medium.tar.bz2',
  'vits-piper-tr_TR-fahrettin-medium.tar.bz2',
  'vits-piper-tr_TR-fettah-medium.tar.bz2',
  'vits-piper-uk_UA-lada-x_low.tar.bz2',
  'vits-piper-uk_UA-ukrainian_tts-medium.tar.bz2',
  'vits-piper-vi_VN-25hours_single-low.tar.bz2',
  'vits-piper-vi_VN-vais1000-medium.tar.bz2',
  'vits-piper-vi_VN-vivos-x_low.tar.bz2',
  'vits-piper-zh_CN-huayan-medium.tar.bz2',
  'vits-vctk.tar.bz2',
  'vits-zh-aishell3.tar.bz2',
  'vits-zh-hf-abyssinvoker.tar.bz2',
  'vits-zh-hf-bronya.tar.bz2',
  'vits-zh-hf-doom.tar.bz2',
  'vits-zh-hf-echo.tar.bz2',
  'vits-zh-hf-eula.tar.bz2',
  'vits-zh-hf-fanchen-C.tar.bz2',
  'vits-zh-hf-fanchen-unity.tar.bz2',
  'vits-zh-hf-fanchen-wnj.tar.bz2',
  'vits-zh-hf-fanchen-ZhiHuiLaoZhe.tar.bz2',
  'vits-zh-hf-fanchen-ZhiHuiLaoZhe_new.tar.bz2',
  'vits-zh-hf-keqing.tar.bz2',
  'vits-zh-hf-theresa.tar.bz2',
  'vits-zh-hf-zenyatta.tar.bz2',
]


def init_tts(asset: str = "vits-piper-en_US-ljspeech-high.tar.bz2"):
    path = cached_path("https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/"+asset, extract_archive=True)
    files = [file for file in path.glob("*/*")]

    model = next((file for file in files if file.suffix == ".onnx"), None)
    lexicon = next((file for file in files if file.suffix == ".txt" and "lexicon" in file.name), None)
    data = next((file for file in files if "espeak" in file.name and file.is_dir()), None)
    dict = next((file for file in files if "dict" in file.name and file.is_dir()), None)
    tokens = next((file for file in files if file.suffix == ".txt" and "token" in file.name), None)
    tts_config = sherpa_onnx.OfflineTtsConfig(
        model=sherpa_onnx.OfflineTtsModelConfig(
            vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                model=model.as_posix(),
                lexicon=lexicon.as_posix() if lexicon else '',
                data_dir=data.as_posix() if data else '',
                dict_dir=dict.as_posix() if dict else '',
                tokens=tokens.as_posix() if tokens else '',
            ),
            provider="cpu",
            debug=False,
            num_threads=4,
        ),
        rule_fsts="",
        max_num_sentences=2,
    )
    print(tts_config)
    if not tts_config.validate():
        raise ValueError("Please check your config")

    tts = sherpa_onnx.OfflineTts(tts_config)
    return tts

def tts(model: sherpa_onnx.OfflineTts, text: str, speed: float = 1.0, voice: str = "nova"):
    def generated_audio_callback(samples: np.ndarray, progress: float):
        print(f"Generated audio with {len(samples)} samples, progress: {progress:.2f}")
        # 1 means to keep generating
        # 0 means to stop generating
        return 1
    
    start = time.time()
    sid = {'': 0, 'nova': 0}[voice]
    if sid is None:
        raise ValueError(f"Unknown voice: {voice}")
    audio = model.generate(text, sid=0, speed=speed, callback=generated_audio_callback)
    end = time.time()

    if len(audio.samples) == 0:
        print("Error in generating audios. Please read previous error messages.")
        exit(1)

    elapsed_seconds = end - start
    audio_duration = len(audio.samples) / audio.sample_rate
    real_time_factor = elapsed_seconds / audio_duration
    
    print(f"The text is '{text}'")
    print(f"Elapsed seconds: {elapsed_seconds:.3f}")
    print(f"Audio duration in seconds: {audio_duration:.3f}")
    print(f"RTF: {elapsed_seconds:.3f}/{audio_duration:.3f} = {real_time_factor:.3f}")

    # resample audio.samples to 24kHz to match openai
    audio.samples = samplerate.resample(audio.samples, 24000 / audio.sample_rate, 'sinc_best')
    audio.sample_rate = 24000

    return audio
