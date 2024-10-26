# Note
 You can skip to the bottom if you simply want to use an existing XTTS voice model.

# Preamble
 Hey commanders, welcome back from the black. If you aren't aware, there is this really cool piece of software called Covas Next being developed to make the solitude of being in space a little less lonely. Powered by AI, it aims to give your ship a bit of its own personality. After struggling for an unreasonable amount of time, I have finally managed to get it set up with the specific voice that I want. I figured that with the pain I went through to accomplish that, I would make a bit of a guide documenting my set up and how I accomplished it. It is likely far from ideal, and there are probably easier methods, but this is how I did it.
 
 As a note, we are going to be using WSL and windows for this, but all of the software runs on linux as well, this should work there as well.

 Firstly, we are going to need to set up our environment. We are going to head into control panel, then into programs, then "Turn Windows Features On or Off." In this menu, we want to enable both Virtual Machine Platform and Windows Subsystem for Linux. If this is your first time enabling them, you may need to restart after this step. 

 Next we are going to head over to docker.com and download the installer. As I already have it set up, I wont be running through the install process in detail here. The only thing to note is that, when you are installing it, make certain to have the box checked to use WSL2 as your backend. Once you have it installed, you may need to log out or restart.

 We are now going to set up what you will be using to train your voice model: The [Alltalk V2](https://github.com/erew123/alltalk_tts/wiki/Install-%E2%80%90-Standalone-Installation) beta.

# Training
This section is for if you want to train your own model. Ignore and move on if you have your own model!

<details><summary>Click here to show training instructions. Expect scuff ahead.</summary>

## Setting up Alltalk
 Before installing AllTalk, ensure you have the following:

* Git for cloning GitHub repositories. 
* Microsoft C++ Build Tools and Windows SDK for proper Python functionality. [Installation instructions](https://github.com/erew123/alltalk_tts/wiki/Install-%E2%80%90-WINDOWS-%E2%80%90-Python-C-&-SDK-Requirements)
* Espeak-ng for multiple TTS engines to function. [Installation instructions](https://github.com/erew123/alltalk_tts/wiki/Install-%E2%80%90-WINDOWS-%E2%80%90-Espeak%E2%80%90ng)

 If you already have these installed, you can proceed directly to the Quick Setup instructions.

Open Command Prompt and navigate to your preferred directory:

	cd /d C:\path\to\your\preferred\directory

Clone the AllTalk repository:

  	git clone -b alltalkbeta https://github.com/erew123/alltalk_tts

Navigate to the AllTalk directory:

  	cd alltalk_tts

Run the setup script:

	atsetup.bat

 Follow the on-screen prompts:
  * Select Standalone Installation and then Option 1.
  * Follow any additional instructions to install required files.

# Creating samples for our dataset
 From here we are ready to begin creating our voice model. The first thing you will want to do is get a wav file of the voice you want to clone and place it in the voices folder of your Alltalk installation.
 
 <details><summary>Screenshot</summary>

![](screenshots/voice-sample-dir.png?raw=true)

</details>

 From here, you are going to start the Alltalk server. This can be done by either opening the start_alltalk.bat file in the folder you cloned, or by opening a command prompt, CDing into the directory and running the bat file this way. By default, you will be connecting to http://127.0.0.1:7852/ to access the webui. But what we really want is the TTS generator, which is by default at http://127.0.0.1:7851/static/tts_generator/tts_generator.html

 We will be using this to generate what we need for our dataset. Included in this repository, you will find a collection of prompts in various languages, pulled from the [Piper Recording Studio](https://github.com/rhasspy/piper-recording-studio) repo, leading digits stripped from them. Grab all three files from the language of your choice, English in my case, and drop them in the Text Input section of the generator. Each line should have a single sentence.

 Next, we want to set the chunk size to 1, playback to none, and the Character voice to your choice. In my case, I am using Reed, from Arknights. Our settings set, we hit generate and wait for it to finish. Once it is done, we can go ahead and stop the Alltalk server.

 <details><summary>Screenshot</summary>

![](screenshots/genvoice.png?raw=true)

</details>

## Its time for our Anime Training Arc!
 Now that we have our samples, we are going to move on to training. We now want to go back to our Alltalk directory. Because we have 1150 samples, it is best that we transfer them first, then begin the dataset creation. The TTS generator will have put them in the outputs folder. We want to copy them to the finetune/put-voice-samples-in-here folder, as shown below. 

 <details><summary>Screenshot</summary>

![](screenshots/move.png?raw=true)

</details>

 Next up we want to run the start_finetune.bat file to start the trainer. Once its finished loading, it should automatically open itself in a browser window. If it does not, you can use http://127.0.0.1:7052/ to access it. By default it will open to a status page, show below. You want to make certain all of the boxes are green. If they are not, there are tabs along the top that _should_ will give you more info on how to resolve those issues.

<details><summary>Screenshot</summary>

![](screenshots/finetunestatus.png?raw=true)

</details>

 Next up, we are moving to step one. Because we already moved our audio samples beforehand, all we need to do here is fill in the project name and hit Create Dataset at the bottom.

<details><summary>Screenshot</summary>

![](screenshots/step1.png?raw=true)

</details>

When we move over to step two, the fields should have autopopulated the appropriate data for your dataset, so all we need to do here is make sure our project name is correct, and hit Run the Training. I don't know nearly enough about the underlying nonsense that is AI training to advise on what settings are optimal, so I left them all the same and it turned out quite well. It took me about an hour to train 10 epochs with my setup. 

<details><summary>Screenshot</summary>

![](screenshots/step2.png?raw=true)

</details>

 Once its finished, head over to step three. Put the project name in the top right text box, click Refresh, load, set a prompt and then hit generate to get a sample of your model.

<details><summary>Screenshot</summary>

![](screenshots/step3.png?raw=true)

</details>

 If you aren't quite happy, and want to continue training, you can head back to step two, and in the model option, select the previous model, rather than xtts.

<details><summary>Screenshot</summary>

![](screenshots/unhappy.png?raw=true)

</details>

If you are happy, head over to the final tab. Enter your project name, refresh dropdowns, select the model you are happy with and set your folder name. The compact and move button will move the model to your alltalk/models/xtts folder.

<details><summary>Screenshot</summary>

![](screenshots/happy.png?raw=true)

</details>

</details>

# Setting up an OpenAI compatable TTS server than can use XTTS models

## Preparing for OpenedAI Speech
 The server we will be using here is [OpenedAI Speech](https://github.com/matatonic/openedai-speech). We're gonna gonna start by opening a WSL terminal from the command prompt, cloning the repo and enter the folder:

  	wsl -d Ubuntu
  	git clone https://github.com/matatonic/openedai-speech
  	cd openedai-speech

<details><summary>OpenedAI Speech Dir</summary>

![](screenshots/openedai.png?raw=true)

</details>

 Now we want to make a copy of sample.env and rename it speech.env. It may also a good idea to edit speech.env and uncomment one of the lines to preload XTTS.
 ```
TTS_HOME=voices
HF_HOME=voices
#PRELOAD_MODEL=xtts
PRELOAD_MODEL=xtts_v2.0.2
#EXTRA_ARGS=--log-level DEBUG --unload-timer 300
#USE_ROCM=1
```

 If you have your own model, you will want to copy it into the voices/tts folder. We then want to open the voice_to_speaker.yaml in the config folder and add the model beneath the tts-1-hd heading. You can also place a wav file in the voices folder and map it to one of the default voices. An example of both is included in the screenshot below. 

<details><summary>OpenedAI Speech Dir</summary>

![](screenshots/configyaml.png?raw=true)

</details>

With everything set up, we can run the following command inside the repo folder to start up the OpenedAI Speech server:

```
docker compose up
```
<details><summary>OpenedAI running in docker</summary>

![](screenshots/dockerterm.png?raw=true)

</details>

# Covas
 [Download Covas Here!](https://github.com/RatherRude/Elite-Dangerous-AI-Integration)

 Now that we have the server up and running, we can setup Covas to use it.
 ```
 TTS Model Name: tts-1-hd
 TTS Endpoint: http://127.0.0.1:8000/v1
 ```

 For your TTS voice, it is going to be what is set in the voice_to_speaker.yaml file. As examples:
 
 ```
   shimmer:
    model: xtts
    speaker: voices/shimmer.wav
  reed:
    model: reed # This name is required to be unique
    speaker: voices/tts/reed/sample.wav # voice sample is required
    model_path: voices/tts/reed
```

If I enter shimmer, Covas will use the pre-configured shimmer voice. If I use reed, it will use my custom Reed model.

<details><summary>Covas TTS settings</summary>

![](screenshots/covastts.png?raw=true)

</details>

# Potential issue with Alltalk
 While setting up Alltalk, I ran into an issue with it not finding a DLL, specifically cudnn_cnn64_9.dll, despite it being in the alltalk env. To resolve the issue, I had to add the correct folder to my environment variables. You can do so by going to System > About > Advanced System Settings > Environment Variables > Path > New and then add the correct folder, where ever they may be for you.

 <details><summary>Environment Variable</summary>

![](screenshots/sysvar.png?raw=true)

</details>