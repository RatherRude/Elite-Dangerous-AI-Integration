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
Now as you can see, this format has no idea about what a game event is or what the current ships status is, all of that is custom made by us in order to make the model better "understand" what and how it should generate its next response.

## Tool-Use

Let's consider a tool like this:
```
list_files_in_directory(path: str) -> list[str]
```
We want our LLM to be able to tell use, which files are in a specific directory on our system, which requires us to do 3 things:
1) Tell the model about the available tools and the parameters they require, like the path of the directory
2) Allow the model to somehow indicate to us that it wants to use a tool in its response, which tool it wants to use and what the parameters are
3) Somehow tell the model what the result of the tool is (skipping over this for now, as it is already complicated enough)

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

This whole thing becomes more of a guessing game, hoping that the model outputs exactly what we expect it to and if it doesn't we just have to hope that nothing breaks. OpenAI is insanely reliable at function calling, they even guarantee at 100% success-rate on function parameters (because they use clever technical tricks to double check the models output). Mistral is also pretty reliable, they don't guarantee success, but at least they trained their model on a specific output format, which is easy to detect and process. Llama is in a weird place, their models are good and so they will "most likely" follow the instruction, but there isn't even a specific format they were trained on, so tools like Ollama and LMStudio have to "beg the model" to follow theirs and hope that their processing can somehow deal with the output.