# Getting started for "free"

!!! danger

    This setup is highly experimental and will significantly degrade your experience. We recommend using OpenAI instead.**

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
- Tool use is unreliable and may crash the integration, [see why here](llmInternals.md).
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
- Tool use is unreliable and may crash the integration, [see why here](llmInternals.md).

After installing Ollama, you need to download a model according to the instructions on their website. At the time of writing we recommend using `llama3.1:8b`.
Once the download is complete you can configure the LLM as follows:

```
LLM Provider: Custom
LLM Model Name: llama3.1:8b
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


## Using AIServer (beta)
**WARNING: This setup is highly experimental and is potentially difficult to set up.**

We are currently working on our own local server that can provide all the necessary services locally for free, given that you have a powerful system available.

You can read more about the AIServer [here](./AIServer.md).