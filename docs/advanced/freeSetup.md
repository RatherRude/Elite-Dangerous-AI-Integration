# Getting started for "free"

**Recommended:** For free local STT, TTS and embedding with the least amount of configuration, use the [official COVAS Labs plugins](../plugins/index.md#first-official-plugins). They provide ready-to-use Parakeet (STT), Supertonic (TTS) and Gemma (embedding) with minimal setup.

---

The main components for a free setup are: LLM, Agent (optional), STT, TTS, and optionally Vision and Embedding.

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
- Does not support STT or TTS, so you need to mix and match with other services

To use OpenRouter.ai, you need to sign up for an account and create an API key.
Once you have an account and an API key, you can check the website for the available models in the :free tier. At the time of writing we recommend using ´meta-llama/llama-3.3-70b-instruct:free`.

```
LLM Provider: OpenRouter
LLM Model Name: meta-llama/llama-3.3-70b-instruct:free
LLM API Key: <your API key>
Allow Actions: Disable (Unless you use a paid model that supports actions)
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
- Does not support STT or TTS, so you need to mix and match with other services

After installing Ollama, you need to download a model according to the instructions on their website. At the time of writing we recommend using `llama3.1:8b`.
Once the download is complete you can configure the LLM as follows:

```
LLM Provider: Custom
LLM Model Name: llama3.1:8b
LLM Endpoint URL: http://localhost:11434/v1
LLM API Key: <empty>
```

### 1.3 Using LMStudio (local)
https://lmstudio.ai is a third-party application that can run the LLM locally on your computer.

*Upsides:*
- Can be used offline
- It is free, except for the cost of the GPU and electricity
- No rate limiting (except for the hardware)

*Downsides:*
- Requires a powerful GPU (RTX 3090 or better recommended)
- High latency, especially on weaker GPUs
- Not trivial to set up
- Tool use is unreliable and may crash the integration, [see why here](llmInternals.md).
- Does not support STT or TTS, so you need to mix and match with other services

Load the model into LMStudio according to the instructions on their website. At the time of writing we recommend using `llama-3.1-8b`.
Next, you need to navigate to the Developer tab and click "Start Server". By default, the server will use port 1234.

Once the server is running, you can configure the Integration as follows:

```
LLM Provider: Custom
LLM Model Name: llama-3.1-8b
LLM Endpoint URL: http://localhost:1234/v1
LLM API Key: <empty>
```

### 1.4 Using AIServer (local)
You can read more about the AIServer [here](./AIServer.md).

*Upsides:*
- Can be used offline
- It is free, except for the cost of the GPU and electricity
- No rate limiting (except for the hardware)
- Supports STT and TTS as well

*Downsides:*
- Tricky to set up, as it is still highly experimental
- May struggle with multilingual input/output
- Higher latency than cloud services

## 2. Agent Configuration
The Agent is a search sub-LLM that answers queries posed by the main LLM. It chains web and knowledge actions in a loop to find answers. Higher accuracy matters more here than for the main chat LLM—consider using an online LLM for the Agent even if the main LLM is local. You can use the same provider as the main LLM (e.g. LM Studio, Ollama), but set the main LLM to no reasoning effort and the Agent LLM to at least Low reasoning effort for better search accuracy. The Agent is served the same way as the main LLM (LM Studio, Ollama, cloud, etc.); configure it in the same style as section 1.

## 3. STT Configuration
The Speech-to-Text (STT) component is responsible for converting your voice into text that the LLM can understand. No cloud service is available that provides free STT, so you will need to run it locally. Luckily it requires a little less resources and can be run on a weaker GPU or even a CPU.

### 3.1 Using Parakeet plugin (local, recommended)
The [Parakeet STT plugin](../plugins/index.md#first-official-plugins) is the official free local STT from COVAS Labs. Download from [Releases](https://github.com/COVAS-Labs/plugin-parakeet-stt/releases), extract to your `plugins` folder, and select it in COVAS:NEXT. Multilingual, minimal configuration.

*Upsides:*
- Free, local, no account required
- Multilingual
- Easiest free STT setup

*Downsides:*
- Requires a GPU or capable CPU for real-time transcription

### 3.2 Using AIServer (local)
You can read more about the AIServer [here](./AIServer.md).

*Upsides:*
- Can be used offline
- It is free, except for the cost of the GPU and electricity
- No rate limiting (except for the hardware)

*Downsides:*
- Tricky to set up, as it is still highly experimental
- May struggle with multilingual input/output
- Higher latency than cloud services

## 4. TTS Configuration
The Text-to-Speech (TTS) component is responsible for reading out the responses of the LLM. Edge-TTS is a free cloud service and is used by default. Alternatively, you can use the official Supertonic plugin or the AIServer to run TTS locally.

### 4.1 Using Supertonic plugin (local, recommended)
The [Supertonic TTS plugin](../plugins/index.md#first-official-plugins) is the official free local TTS from COVAS Labs. Download from [Releases](https://github.com/COVAS-Labs/plugin-supertonic-tts/releases), extract to your `plugins` folder, and select it in COVAS:NEXT. Multilingual, minimal configuration.

*Upsides:*
- Free, local, no account required
- Multilingual
- Easiest free local TTS setup

*Downsides:*
- Requires a GPU or capable CPU for real-time synthesis

### 4.2 Using Edge-TTS (cloud-based)
We recommend using Edge-TTS as it is free and has good latency and quality.

### 4.3 Using AIServer (local)
You can read more about the AIServer [here](./AIServer.md).

*Upsides:*
- Can be used offline
- It is free, except for the cost of the GPU and electricity
- No rate limiting (except for the hardware)

*Downsides:*
- Tricky to set up, as it is still highly experimental
- May struggle with multilingual input/output
- Higher latency than cloud services

## 5. Vision Configuration
Vision requires an LLM that is multimodal or has image-understanding (e.g. text-from-image) capabilities. It can be the same as the main LLM or a smaller model dedicated to vision. Same serving options as the main LLM (LM Studio, Ollama, cloud, etc.).

## 6. Embedding Configuration
Embedding is used to search the logbook—a persistent memory stored in a vector database. Entries are compared via embeddings to find the most relevant ones. For a free setup, use the plugin first; AIServer is the other option.

### 6.1 Using Gemma plugin (local, recommended)
The [Gemma embedding plugin](../plugins/index.md#first-official-plugins) is the official free local embedding from COVAS Labs. Download from [Releases](https://github.com/COVAS-Labs/plugin-gemma-embedding/releases), extract to your `plugins` folder, and select it in COVAS:NEXT. Multilingual, minimal configuration.

*Upsides:*
- Free, local, no account required
- Multilingual
- Easiest free embedding setup

*Downsides:*
- Requires a GPU or capable CPU

### 6.2 Using AIServer (local)
You can read more about the AIServer [here](./AIServer.md). Use the **embeddinggemma-300m** model as the recommended option for embeddings.

*Upsides:*
- Can be used offline
- It is free, except for the cost of the GPU and electricity
- No rate limiting (except for the hardware)

*Downsides:*
- Tricky to set up, as it is still highly experimental
- Higher latency than a dedicated plugin

## Note on Google AI Studio

Google AI Studio (aistudio.google.com) previously offered a daily free quota that made it a viable free option for LLM and multi-modal STT. They have since changed their daily rates and free tier limits; in its current state it is effectively unusable for free use. We have removed it from the recommended options above. If their free tier improves again in the future, you can still select Google AI Studio as LLM or STT provider in COVAS:NEXT if you have an API key.

## Troubleshooting

While we recommend using OpenAI for the best experience, we understand that there are reasons not to use OpenAI. We will try our best to support you. 
If you encounter any issues, please contact us on Discord or open an issue on GitHub.