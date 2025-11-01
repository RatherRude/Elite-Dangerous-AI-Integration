# AIServer (beta)

!!! danger

    This setup is highly experimental and is potentially difficult to set up.

The AIServer can serve as a local STT, TTS and LLM provider.
It can be download [here](https://github.com/lucaelin/covas-next-aiserver/releases/). Once you have extracted the Zip, you can run it by double-clicking the `AIServer.exe` file.

_Upsides:_

- Can be used offline
- It is free, except for the cost of the GPU and electricity
- No rate limiting (except for the hardware)

_Downsides:_

- Tricky to set up, as it is still highly experimental
- Struggle with multilingual input/output
- Higher latency than cloud services for LLMs
- Requires a powerful GPU when working with LLMs

Upon starting the AIServer, need to configure it using the window that pops up. You can select the "None" option for the different modalities you don't want to use (e.g. if you only want STT and use the LLM via OpenRouter and TTS via EdgeTTS).

1. Select a TTS Model. At the time of writing we recommend using `hexgrad/Kokoro-82M`.

2. Select a STT model. At the time of writing we recommend using `sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8.tar.bz2`. Note that `sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2` can be better for non-English inputs, but v2 is generally better for English.

3. Select an LLM model. For LLM functionality, we recommend using LM Studio instead of the built-in AIServer LLM support, as LM Studio offers a bigger catalogue of models and better support (e.g. multi-GPU). You can select "None" here if using LM Studio.

4. Select an embedding model. At the time of writing we recommend using `onnx-community/embeddinggemma-300m-ONNX`.

5. You can choose to enable or disable the LLM Disk Cache. Depending on your system (SSD performance), this my speed up the LLM response time or significantly slow it down. We recommend to disable it, if you are unsure.

6. Configure the network access. Confirm the defaults as 127.0.0.0 and port 8080 if you are unsure.

The AIServer window will then download the selected models and show a message when done: `running on http://127.0.0.1:8080`.

7. Lastly, you will need to configure the COVAS:NEXT itself:

- Open the COVAS:NEXT "Advances settings"

- Depending on the modalities you selected, you will need to change LLM, STT and TTS settings to "Local AIServer".

- When using a separate computer to run AIServer, you can adjust the host and port in the endpoint settings.

## Saving configuration

If you don't want to configure every time you start the AIServer, you can place a `aiserver.config.json` file in the same directory as the `AIServer.exe` file. The file should look like this:

```
{
  "host": "127.0.0.1",
  "port": 8080,
  "embed_model_name": "onnx-community/embeddinggemma-300m-ONNX",
  "stt_model_name": "sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8.tar.bz2",
  "tts_model_name": "hexgrad/Kokoro-82M",
  "llm_model_name": "None",
  "use_disk_cache": false
}
```

## Troubleshooting

If you encounter any issues, please contact us on Discord or open an issue on GitHub.
