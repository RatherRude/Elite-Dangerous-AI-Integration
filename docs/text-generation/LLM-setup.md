This is a pretty straight forward and easy to setup guide on setting up Oobabooga text generation in a docker container, running with WSL. 

# Acquiring necessary files
 First up, we are going to grab everything we need to get the server up and running.
  * You can find the repository for the [container here](https://github.com/Atinoda/text-generation-webui-docker)
  * We will also need a model to run. These can typically be found on [huggingface](https://huggingface.co/). Some suggestions if you don't know what to look for (Top to bottom for my preferences):
    * [openhermes-2.5-mistral-7b.Q4_K_M](https://huggingface.co/TheBloke/OpenHermes-2.5-Mistral-7B-GGUF/blob/main/openhermes-2.5-mistral-7b.Q4_K_M.gguf)
    * [OpenChat-3.5 i1-Q4_K_M](https://huggingface.co/mradermacher/openchat-3.5-1210-i1-GGUF/resolve/main/openchat-3.5-1210.i1-Q4_K_M.gguf)
    
 
 We want to start out by cloning the repo in a WSL terminal.
 ```
 wsl -d Ubuntu
 cd /some/folder/you/want
 git clone https://github.com/Atinoda/text-generation-webui-docker
 cd text-generation-webui-docker
 ```

<details><summary></summary>

![](screens/.png?raw=true)

</details>  

 From here we want to put our downloaded models into the config/models folder.

<details><summary>Models</summary>

![](screens/models.png?raw=true)

</details>  

# Configuring the container
 Now that we have those set up docker config file to load our desired settings. Open the docker-compose.yml in your editor of choice and we can begin. Our first change will be to line 3 of the compose file, the image. 

```
image: atinoda/text-generation-webui:{VARIANT}-{PLATFORM} # Specify variant as the :tag
```

| Variant | Description | 
|---|---|
| `default-*` | Standard deployment with all default bundled extensions installed. Normal image intended for everyday usage. |
| `base-*` | Basic deployment with no extensions installed. Slimmer image intended for customisation or lightweight deployment.  |


| Platform | Description | 
|---|---|
| `*-nvidia` | CUDA 12.1 inference acceleration. |
| `*-nvidia-noavx2` | CUDA 12.1 inference acceleration with no AVX2 CPU instructions. *Typical use-case is legacy CPU with modern GPU.* |
| `*-nvidia-tenssorrtllm` | CUDA 12.1 inference acceleration with additional TensorRT-LLM library pre-installed. |
| `*-cpu` | CPU-only inference. *Has become surprisingly fast since the early days!* |
| `*-rocm` | ROCM 5.6 inference acceleration. *Experimental and unstable.* |
| `*-arc` | Intel Arc XPU and oneAPI inference acceleration.  **Not compatible with Intel integrated GPU (iGPU).** *Experimental and unstable.* |


 * If you have an Nvidia card, my recommended setting is:
    * image: atinoda/text-generation-webui:default-nvidia-tensorrtllm
 * The above uses TensorRT to increase performance, but requires newer cards. If you aren't certain you can handle this, you can drop that portion as in the example below.
    * image: atinoda/text-generation-webui:default-nvidia

Next we are going to jump down to ports, and uncomment the API port by removing the # at the beginning of the line.

 ```
 #      - 5000:5000  # Default API port
 ```

 to

 ```
      - 5000:5000  # Default API port
 ```

 We now want to skip down to the volumes portion. We are going to make our extensions persistent, as well as our settings. To do this, head down to line 24 and make the following alterations. 

 ```
 #      - ./config/extensions:/app/extensions  # Persist all extensions
 ```

 to

 ```
       - ./config/extensions:/app/extensions  
       - ./config/settings.yaml:/app/settings.yaml
 ```

 The settings file will _not_ be present when you first clone or launch the container, and this is fine. This will be generated after we launch the server. 

 Finally, we are going to jump down to the Hardware acceleration section. If you do _not_ an nvidia card, you will want to comment out  all of the nvidia section. Do this by adding a # to the beginning of each line. If you have an Intel or AMD card, uncomment the appropriate section by deleting the # at the beginning of the lines, as exampled below.

<details><summary>AMD/Intel hardware</summary>

![](screens/amd.png?raw=true)

</details>  

With our changes complete, we can now start the server by running the following command:

```
docker compose up
```

# Setting up the server for Covas
<details><summary>Session Settings</summary>
 
 ![](screens/session.png?raw=true)
 
 </details>     
With the container running, we can now access the server by heading to a browser and opening http://127.0.0.1:7860 Here our first top is going to be the session tab to set up our extensions. Listen and verbose should already by checked. The only thing of importance here is the openai extension on the left. Make certain the box is checked, then press Save UI defaults and Apply Flags/extensions. 

<details><summary>Model</summary>

![](screens/modelsui.png?raw=true)

</details>    

 Next we are going to set up the model you are using for text generation. Use the above image and the below table to configure as you need in the order they are numbered. Notes will be below.

 | # | setting |Description | 
|---|---| ---|
| 1 | Model | Select your prefered model |
| 2 | n-gpu-layers | How much of the model to offload to your GPU. |
| 3 | n-ctx | Context. |
| 4 | tensorcores | Whether or not to use tensors. |
| 5 | streaming_llm  | Experimental setting to help generation |
| 6 | numa | Numa memory support |
| 7 | Save | Load/Unload model and save settings |

The model is self explanatory, but the rest require a bit of info. Lets start with GPU layers.

## n-gpu-layers
<details><summary>n-gpu-layers</summary>

![](screens/gpulayers.png?raw=true)

</details>    

 This setting is going to tell the server how much of th model to load into your GPU. Loading into GPU will make text generation faster, but also uses more Vram. Typically, if you want faster and smoother generations, you want to load most of or all of the model into gpu. Example outputs of both full and no offload are below, to help decide how much you wish to offload. The below screenshots were talking with tensorcores off.

<details><summary>Full Offload</summary>

![](screens/fullload.png?raw=true)

</details>    
<details><summary>No Offload</summary>

![](screens/noload.png?raw=true)

</details>    

## n-ctx
This is context. Or in simpler terms: How much of previous responses and prompts to keep each time you ask the model to generate a response. This is what gives the bot its ability to remember your conversation. The larger the number here, the more the model "remembers" form your conversations, but this also increases the amount of memory used. Common values tend to be 4096/8192/16384. In our case, I would not suggest going beyond this, but it is technically possible for it to be higher. 

## tensorcores
If you are using the default-nvidia-tensorrtllm container, you can enable this setting to help performance on newer nvidia cards. Below are examples of generations done with this  setting on. You can judge for yourself the value of this setting.

<details><summary>Full Offload</summary>

![](screens/fullload-tensors.png?raw=true)

</details>    
<details><summary>No Offload</summary>

![](screens/noload-tensors.png?raw=true)

</details> 

## streaming_llm
This setting is meant to help when older messages get removed. Typically this happens when you hit the token limit for context, or in the case of something like SillyTavern roleplaying, you delete other messages. I tend to recomment turning this on.

## NUMA
I tend to turn this on, but .... Imma be honest and say I have no idea what this is actually for. I havent noticed any negatives for using it vs not using it. You can check out the [wikipedia](https://en.wikipedia.org/wiki/Non-uniform_memory_access) page on NUMA if you are curious.

## Load/Unload/Save
Once you have your settings in place you can hit load model. If you don't want to fill this out every time, you can hit Save Settings, and next time you select the model, it will preload your configuration. When you finish using the model, you can hit unload and close the server.

# Covas Settings

<details><summary>Covas API settings</summary>

![](screens/covas.png?raw=true)

</details>    

<details><summary>Covas nagging about model provider.</summary>

![](screens/nag.png?raw=true)

</details>    

```
LLM Model Name: gpt-3.5-turbo
LLM Endpoint: http://127.0.0.1:5000/v1
LLM API Key: Can be blank, or anything at all.
```
So here is where things get a bit scuffed. Regardless of the model name you have loaded, you want to enter gpt-3.5-turbo because covas doesn't like anything else here. Also, when you click Start AI, Covas is going to complain about your model provider not servering gpt-4o-mini. Ignore it and continue anyway. It will still work fine, even with this nag. I don't understand it either.

# Afterthoughts

Sitting here and rereading what I wrote to make sure its easy to understand and follow, I realized the above screenshots contain some other models. Namely ones including LimaRP in the file names. This leaves me with a bit of advice: Those models are desiged for Roleplay (if the RP didn't make that clear.) While this does mean they are a bit better at being characters, they can also add responses for _you_ in the responses as well. You can decide for yourself if you want to take that chance, but if you do, I suggest you add something to your prompt to prevent this. Things like "Do not speak or act for {{user}}" and "You may only speak for {{char}}". Note the double brackets, which differs from {commander_name} in the default prompt. This is the required syntax for the user and char variables in the LLM server software. 