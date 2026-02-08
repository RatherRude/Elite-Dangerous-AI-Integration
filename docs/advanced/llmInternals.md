# LLM Internals

## Instruction Following

LLMs are just text prediction systems, meaning they receive a sequence of tokens and then output tokens they predict should come next.
So if you input:

```
How do birds fly?
```

They may output:

```
Why do they need to flap their wings? In the following article we will explore this in more detail.
```

Which is a likely continuation of some internet article, but obviously not what you intended to get as an response.

So generally you need to trick the model into answering the question, instead of completing text i.e. like this:

```
Question: How do birds fly?
Answer:
```

And now the prediction by the model is much more likely to be what you desire:

```
Birds fly by flapping their wings and displacing the air around them.
```

This works because the model is trained on a lot of internet text, and it is very likely that it has seen a question followed by an answer in the same format before. But you are not required to use `Question:` and `Answer:` markers, you can use whatever makes the prediction to be the way you want it to be.

These were the early days of LLMs, but researchers soon realized that training the models on specific formats for "instruction following" would make them more reliable and then published the appropriate prompt formatting alongside their instruction-tuned models like:

```
### Instruction:
You are a helpful assistant.

### Input:
How do birds fly?

### Response:
```

But not all models used the same format, others started considering it as more of a conversation:

```
<|im_start|>system
You are a helpful assistant.<|im_end|>
<|im_start|>user
How do birds fly?<|im_end|>
<|im_start|>assistant
```

And this is now true for almost all models, they support some kind of text-formatting that the model is optimized for, but different models, different formats.

So people started abstracting these formats away and instead used a common json structure that would then get translated into the different text-formats for each specific model, the most common one is the OpenAI Chat format:

```
[
  {"role": "system", "content": "You are a helpful assistant."},
  {"role": "user", "content": "How do birds fly?"}
]
```

What almost all models have in common today is that they have some kind of a "system" instruction alongside "user" and "assistant" messages, but the way they indicate to the model which part is "user" and which parts are "assistant" is very different.

As you can see, this format has no idea about what a game event is or what the current ships status is, all of that is custom made by us in order to make the model better "understand" what and how it should generate its next response, see more about how we implement this below.

## Tool-Use

Let's consider a tool like this:

```
list_files_in_directory(path: str) -> list[str]
```

We want our LLM to be able to tell use, which files are in a specific directory on our system, which requires us to do 3 things:

1. Tell the model about the available tools and the parameters they require, like the path of the directory
2. Allow the model to somehow indicate to us that it wants to use a tool in its response, which tool it wants to use and what the parameters are
3. Somehow tell the model what the result of the tool is (skipping over this for now, as it is already complicated enough)

Now lets first look at how Mistral-7b usually formats its prompt:

```
<s>[INST] You are a helpful assistant.
How do birds fly? [/INST]
```

(Note: Mistral does not differentiate between system and user, it's just separated by line-breaks)
And now let's add tools into the mix:

```
<s>[INST] You are a helpful assistant.
What files do I have on my C-drive?
[AVAILABLE_TOOLS] [
  {"name": "list_files_in_directory", "parameters": {"type": "object", "properties": {"path": {"type":"string"}}}}
] [/AVAILABLE_TOOLS]
[/INST]
```

Luckily the Mistral models are specifically trained for function calling, so the model would now predict the following output:

```
[TOOL_CALLS] [{"name":"list_files_in_directory", "arguments": {"path": "C:"}}]
```

This way software like LMStudio or ollama can look out for these special tokens like `[TOOL_CALLS]` and then read what comes next as a tool call, BUT what if the model doesn't follow what we told it to do? What if the model responds with the following?

```
[TOOL_CALLS] [{"name":"list_files", "arguments": {"drive": "C:"}}]
```

(Note: Two things have changed, first it used the wrong function name, and secondly it used an argument called "drive" instead of "path")

This is obviously wrong and may cause errors in an application that attempts to now convert this response into an actual function inside of an application. There is nothing in the model that guarantees that an LLM will respond the way you want it to, but the more advanced a model is, the more likely it is to "do the right thing" especially if it is trained on a specific format, like Mistral.

Now let's look at how Llama models do this:
https://www.llama.com/docs/model-cards-and-prompt-formats/llama3_1/#json-based-tool-calling

```
Given the following functions, please respond with a JSON for a function call with its proper arguments that best answers the given prompt.

Respond in the format {"name": function name, "parameters": dictionary of argument name and its value}. Do not use variables.
```

This is an instruction that you have to add to your prompt in order for the model to even know how it should format the tool-call, unlike Mistral which has a specific format that is trained into the model. The result of using a written instruction to tell the model how it should call tools make it even more unreliably, because the model may ignore these instructions, especially if there is a lot more other instruction that are also given to the model (think Character prompt).

## Provider Compatibility & Nuances

Different providers and runners handle prompts, tool use and chat history differently, which can lead to unexpected behaviors.

### Tool-Use Support

There are three requirements for reliable tool-use:

1. ✅ The model provider has to support tool-use, translating the tool-call into the appropriate format.
2. ✅ The model has to be trained for tool-use and should produce correct tool-calls.
3. ✅ The model provider should verify the tool-calls to ensure that they are correct.

- ✅✅✅ **OpenAI** \
  openai.com checks all three boxes, they support tool-use in their API, they have models that are very well trained for tool-use and they have a verification system in place that checks if the model output is a valid tool-call and even guarantee 100% success rate for tool-use in strict-mode. [Docs.](https://platform.openai.com/docs/guides/function-calling)
- ✅✅❌ **Anthropic** and **Mistral** \
  anthropic.com and mistral.ai are also pretty reliable, they don't guarantee success accoding to their documentation, but it works very reliably in practice. (Note that we do not support these providers directly, as they do not provide an OpenAI-compatible API, but you can use them with OpenRouter or LiteLLM)
- ✅❓❓ **OpenRouter** \
  openrouter.ai has general support for tool-use with some models and providers, if you use OpenAI, Anthropic or Mistral, you can expect the same reliability as with the original tools. Other models and providers may have less reliable tool-use support. [List of supported models.](https://openrouter.ai/models?fmt=cards&order=newest&supported_parameters=tools)
- ✅❓❓ **Ollama** \
  Ollama has support for tool-use in selected models. The reliability of tool-use is not guaranteed and will get worse the smaller the model is. [Docs.](https://ollama.com/blog/tool-support)
- ✅❓❓ **LMStudio** \
  LMStudio has support for tool-use in selected models. The reliability of tool-use is not guaranteed and will get worse the smaller the model is. [Docs.](https://lmstudio.ai/docs/advanced/tool-use)

### Consecutive User Messages

One significant inconsistency is how **consecutive user messages** are handled.
While OpenAI supports them and templates them as individual messages, a raw Mistral model generally strictly requires alternating roles (User -> Assistant -> User) and should fail if two user messages follow each other.

However, providers like OpenRouter and local runners like LM Studio often intervene:

- They modify the input to allow consecutive messages, preventing the error.
- For example, LM Studio is known to flatten consecutive user inputs into a single message using `\n\n` as a delimiter.
- Crucially, LM Studio applies this flattening for **all** models, even for those that would natively support consecutive messages, thereby bypassing the chat template as designed by the model author.

This forced modification often degrades quality, as models trained to understand distinct message turns may interpret the flattened text differently than intended, potentially leading to confusion or loss of context between separate instructions.

### Thinking Tokens

Some modern models (especially "reasoning" models) generate "thinking tokens" or a "chain of thought" before producing the final answer. Correctly handling these require the inference provider to parse the output and separate the reasoning part from the actual response.

- **Standard Behavior:** The provider splits the response, often hiding the reasoning or providing it in a separate field, delivering only the clean answer as the message content.
- **Inconsistent Handling (e.g., LM Studio):** Some runners like LM Studio may treat the entire raw output stream as the message content. This leads to the internal "thinking" process leaking into the final response string, which can break downstream applications expecting clean text, or in case of COVAS:NEXT, leads to long thinking traces being read out loud by the TTS system in addition to the final answer, which causes duplication and a really long response time.

## Game Events and State

In order to make the AI understand the context of a game, we need to provide it with the current state of the game and the events that are happening in the game. This is done by adding a special instruction to the prompt that tells the AI about the game state and the events that are happening in the game. The AI can then use this information to generate responses that are relevant to the game.

_TODO: document how we do this_
