This is a pretty straight forward and easy to setup guide on setting up Oobabooga text generation in a docker container, running with WSL. 

# Acquiring necessary files
 First up, we are going to grab everything we need to get the server up and running.
  * You can find the repository for the [container here](https://github.com/Atinoda/text-generation-webui-docker)
  * We will also need a model to run. These can typically be found on [huggingface](https://huggingface.co/). Some suggestions if you don't know what to look for:
    * [OpenChat-3.5 i1-Q4_K_M](https://huggingface.co/mradermacher/openchat-3.5-1210-i1-GGUF/resolve/main/openchat-3.5-1210.i1-Q4_K_M.gguf)
    * [openhermes-2.5-mistral-7b.Q4_K_M](https://huggingface.co/TheBloke/OpenHermes-2.5-Mistral-7B-GGUF/blob/main/openhermes-2.5-mistral-7b.Q4_K_M.gguf)
 
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
image: atinoda/text-generation-webui:{VARIANT-{PLATFORM} # Specify variant as the :tag
```

| Variant | Description | 
|---|---|
| `default-*` | Standard deployment with all default bundled extensions installed. Normal image intended for everyday usage. |
| `base-*` | Basic deployment with no extensions installed. Slimmer image intended for customisation or lightweight deployment.  |
|---|---|

| Platform | Description | 
|---|---|
| `*-nvidia` | CUDA 12.1 inference acceleration. |
| `*-nvidia-noavx2` | CUDA 12.1 inference acceleration with no AVX2 CPU instructions. *Typical use-case is legacy CPU with modern GPU.* |
| `*-nvidia-tenssorrtllm` | CUDA 12.1 inference acceleration with additional TensorRT-LLM library pre-installed. |
| `*-cpu` | CPU-only inference. *Has become surprisingly fast since the early days!* |
| `*-rocm` | ROCM 5.6 inference acceleration. *Experimental and unstable.* |
| `*-arc` | Intel Arc XPU and oneAPI inference acceleration.  **Not compatible with Intel integrated GPU (iGPU).** *Experimental and unstable.* |
|---|---| ---|

 * If you have an Nvidia card, my recommended setting is:
    * image: atinoda/text-generation-webui:default-nvidia-tensorrtllm
 * The above uses TensorRT to increase performance, but requires newer cards. If you aren't certain you can handle this, you can drop that portion as in the example below.
    * image: atinoda/text-generation-webui:default-nvidia
 Next we are going to jump down to ports, and uncomment the API port.

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

 Next we are going to set up the model you are using for text generation. Use the above image and the below table to configure as you need. Notes will be below.

 | # | setting |Description | 
|---|---| ---|
| 1 | Model | Select your prefered model |
| 2 | n-gpu-layers | How much of the model to offload to your GPU. |
| 3 | n-ctx | Context. |
| 4 | tensorcores | Whether or not to use tensors. |
| 5 | streaming_llm  | Experimental setting to help generation |
| 6 | numa | Numa memory support |
| 7 | Save | Load/Unload model and save settings |
|---|---| ---|