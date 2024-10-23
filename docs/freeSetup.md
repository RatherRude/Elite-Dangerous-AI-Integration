# Getting started for "free"
**WARNING: This setup is highly experimental and will significantly degrade your experience. We recommend using OpenAI instead.**

There are 3 main components that need to be configured for a free setup: LLM, STT, TTS.

## 1. LLM Configuration
The LLM is the brains of the operation. It is responsible for understanding the context of the conversation and generating the next response or dispatching actions. The LLM is a large model that requires a lot of resources to run, so it requires either using a cloud service or having a really good GPU available.


### 1.1 Using OpenRouter.ai (cloud-based)
The cloud service https://openrouter.ai provides a free tier that can be used to run the LLM. 

*Upsides:*
- Free tier available
- Does not require a powerful GPU
- Good response times

*Downsides:*
- Account creation is required
- Tool use is almost impossible, so the AI will not be able to control your ship or search for information on the web
- The free tier has significant rate-limiting
- The available models are not as powerful as the ones available on OpenAI, they may hallucinate more and be less coherent

To use OpenRouter.ai, you need to sign up for an account and create an API key.
Once you have an account and an API key, you can check the website for the available models in the :free tier. At the time of writing we recommend using ´meta-llama/llama-3.1-70b-instruct:free`.

```
LLM Provider: Custom
LLM Model Name: meta-llama/llama-3.1-70b-instruct:free
LLM Endpoint URL: https://openrouter.ai/v1
LLM API Key: <your API key>
```

### 1.2 Using Ollama (local)
https://ollama.com is a third-party application that can run the LLM locally on your computer. 

*Upsides:*
- Can be used offline
- It is free, except for the cost of the GPU and electricity
- No rate limiting (except for the hardware)

*Downsides:*
- Requires a powerful GPU (RTX 3090 or better recommended)
- High latency, especially on weaker GPUs
- Not trivial to set up
- Tool use is almost difficult, so the AI will not be able to control your ship or search for information on the web in most cases

After installing Ollama, you need to download a model according to the instructions on their website. At the time of writing we recommend using `mistral-nemo`.
Once the download is complete you can configure the LLM as follows:

```
LLM Provider: Custom
LLM Model Name: mistral-nemo
LLM Endpoint URL: http://localhost:11434/v1
LLM API Key: <empty>
```

## 2. STT Configuration
The Speech-to-Text (STT) component is responsible for converting your voice into text that the LLM can understand. No cloud service is available that provides free STT, so you will need to run it locally. Luckily it requires a little less resources and can be run on a weaker GPU or even a CPU.

### 2.1 Using AIServer (local)
See the section on AIServer below.

## 3. TTS Configuration
The Text-to-Speech (TTS) component is responsible for reading out the responses of the LLM. Edge-TTS is a free cloud service that can be used as TTS. Alternatively, you can use the AIServer to run TTS locally.

### 3.1 Using Edge-TTS (cloud-based)
You can simply select Edge-TTS as the TTS provider.

*Upsides:*
- It is free
- (Almost) No rate limiting
- High quality voices

*Downsides:*
- It's a cloud service, so it requires an internet connection


### 3.2 Using AIServer (local)
See the section on AIServer below.


## Using AIServer
**WARNING: This setup is highly experimental and is potentially difficult to set up.**
The AIServer can serve as a local STT or TTS service.
It is included in the download of our software and can be found in the `aiserver` folder. You can run it by double-clicking the `AIServer.exe` file.

*Upsides:*
- Can be used offline
- It is free, except for the cost of the GPU and electricity
- No rate limiting (except for the hardware)

*Downsides:*
- Tricky to set up, as it is still highly experimental
- May struggle with multilingual input/output
- Higher latency than cloud services

Upon starting the AIServer, need to configure it using the window that pops up. 

You will first need to select a TTS Model. At the time of writing we recommend using `vits-piper-en_US-libritts-high.tar.bz2`. 

Secondly, you will need to configure the STT model. At the time of writing we recommend using `distil-medium.en` or `distil-small.en`.

Third, you will need to configure the network access. Confirm the defaults as 127.0.0.0 and port 8080 if you are unsure.

The AIServer window will then download the selected models and show a message when done: `* Running on http://127.0.0.1:8080`.

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
TTS API Key: <empty>
```
