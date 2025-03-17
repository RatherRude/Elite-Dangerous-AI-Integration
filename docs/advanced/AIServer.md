# AIServer (beta)

!!! danger

    This setup is highly experimental and is potentially difficult to set up.


The AIServer can serve as a local STT, TTS and LLM provider.
It can be download [here](https://github.com/lucaelin/covas-next-aiserver/releases/). Once you have extracted the Zip, you can run it by double-clicking the `AIServer.exe` file.

*Upsides:*
- Can be used offline
- It is free, except for the cost of the GPU and electricity
- No rate limiting (except for the hardware)

*Downsides:*
- Tricky to set up, as it is still highly experimental
- May struggle with multilingual input/output
- Higher latency than cloud services

Upon starting the AIServer, need to configure it using the window that pops up. You can select the "None" option for the different modalities you don't want to use (e.g. if you only want STT and use the LLM via OpenRouter and TTS via EdgeTTS).

1) Select a TTS Model. At the time of writing we recommend using `vits-piper-en_US-libritts-high.tar.bz2`. 

2) Select a STT model. At the time of writing we recommend using `distil-medium.en` or `distil-small.en`.

3) Select an LLM model. At the time of writing we recommend using `lmstudio-community/Llama-3.2-3B-Instruct-GGUF`.

4) You can choose to enable or disable the LLM Disk Cache. Depending on your system (SSD performance), this my speed up the LLM response time or significantly slow it down. We recommend to disable it, if you are unsure.

5) Configure the network access. Confirm the defaults as 127.0.0.0 and port 8080 if you are unsure.

The AIServer window will then download the selected models and show a message when done: `running on http://127.0.0.1:8080`.

Lastly, you will need to configure the AI Integration itself. 

```
STT Provider: Custom
STT Model Name: whisper-1
STT Endpoint URL: http://localhost:8080/v1
STT API Key: <empty>
``` 
```
TTS Provider: Custom
TTS Model Name: tts-1
TTS Endpoint URL: http://localhost:8080/v1
TTS Voice name: nova
TTS API Key: <empty>
```
```
LLM Provider: Custom
LLM Model Name: gpt-4o-mini
LLM Endpoint URL: http://localhost:8080/v1
LLM API Key: <empty>
```

## Saving configuration

If you don't want to configure every time you start the AIServer, you can place a `aiserver.config.json` file in the same directory as the `AIServer.exe` file. The file should look like this:
```
{
  "host": "127.0.0.1",
  "port": 8080,
  "embedding_model_name": "None",
  "stt_model_name": "distil-medium.en",
  "tts_model_name": "hexgrad/Kokoro-82M",
  "llm_model_name": "None",
  "use_disk_cache": false
}
```

## Troubleshooting

If you encounter any issues, please contact us on Discord or open an issue on GitHub.