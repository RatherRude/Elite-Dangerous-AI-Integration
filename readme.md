# AI Integration

We are integrating advanced AI features including Whisper for Speech-to-Text (STT), OpenAI or OpenRouter Language Models (LLMs) for natural language processing, and existing Text-to-Speech (TTS) functionality. This integration aims to provide a more intuitive and hands-free experience for commanders, making interactions with the autopilot more seamless and efficient.

## Setup and Configuration

1. Install requirements
    ```sh
    > cd EDAPGui
    > pip install -r requirements.txt
    ```
2. Run program
    ```sh
    > python .\Chat.py
    ```
   You will be asked if you use openrouter, for your api key and your commander name. After the selected whisper model downloaded and initiliazed you will be ready to start talking.

   ![CLI Startup](screen/cli_startup.png?raw=true "Screen")

   You can change the used model and backstory in `Chat.py`. (Starting of file, but below imports section)

## AI Integration Overview

The AI integration comprises three main components:
1. **Whisper Speech-to-Text (STT)**
2. **OpenAI/OpenRouter Language Models (LLMs)**
3. **Text-to-Speech (TTS)**
4. **Web Lookups for Detailed Information (EDSM)**
5. **Event-Driven Interaction**
6. **Function Calling(ToDo)**
7. **Vision Capabilities(ToDo)**

### 1. Whisper Speech-to-Text (STT)

Whisper, developed by OpenAI, is a state-of-the-art speech recognition model that converts spoken language into text with high accuracy. By incorporating Whisper STT, commanders can issue voice commands to the autopilot, enhancing the hands-free functionality and overall user experience.
We are currently using CPU for speed recognition, this can be changed by swapping the dependencies

### 2. OpenAI/OpenRouter Language Models (LLMs)

The LLMs from OpenAI or OpenRouter can process natural language commands and provide intelligent responses or actions based on user input. This integration will allow the autopilot to understand complex instructions and provide contextual feedback.

The program will ask if you use Openrouter and for your API Key. It is saved locally in `config.json` and reused on next program start.

*You can use models from either Openrouter or OpenAI, the model is currently changed by swapping out the line in `Chat.py` (Starting of file, but below imports section)*:
* https://openai.com/api/pricing/
* https://openrouter.ai/docs#models

*You can also alter the backstory in `Chat.py`*:


### 3. Text-to-Speech (TTS)

The existing TTS functionality is used to provide auditory feedback to the user based on the autopilot's actions and responses from the LLM.

### 4. Web Lookups for Detailed Information (EDSM)

To enrich the user experience, the autopilot system includes capabilities for web lookups using EDSM (Elite Dangerous Star Map). This feature allows the autopilot to fetch detailed information about the current system and the next jump destination, enhancing situational awareness and decision-making during space travel.

### 5. Event-Driven Interaction

The autopilot system is designed to respond dynamically to certain game events during space operations:
* Ship Type Change: When the ship's type changes, the system notifies Commander about the vessel swap, providing updates on the new vessel type.
* New Jump Destination: Upon locking in a new jump destination, detailed information about the destination system is retrieved from EDSM and presented to Commander.
* Shields Status: Changes in shields status, whether lost or regained, prompt the system to alert Commander accordingly, expressing concern or relief as appropriate.
* Under Attack: Detection of the ship being under attack triggers an immediate warning to Commander, emphasizing the imminent danger.
* Low Fuel Reserves: When the ship's fuel reserves drop below 25%, the system issues a warning to Commander, highlighting the critical fuel situation.
* Fighter Destroyed: If a fighter is destroyed, the system informs Commander about the loss, underscoring the severity of the situation.
* Mission Completed: Successful completion of a mission is acknowledged by the system, informing Commander of the accomplishment.
* Mission Redirected: The system updates Commander when a mission is redirected, ensuring awareness of the new objective.
* Jump Start: Initiation of a jump, whether hyperspace or supercruise, is communicated to Commander, indicating the jump type and any relevant details.
* Supercruise Entry: Entry into supercruise is confirmed to Commander, indicating the ship's current status.
* Docking Granted: When docking permission is granted, the system updates Commander on the successful docking request.
* Docking Denied: In case docking permission is denied, the system notifies Commander of the denial and provides the reason.
* Supercruise Exit: Exiting supercruise prompts the system to inform Commander of the current location and status.
* Docking Cancelled: Cancellation of docking is communicated to Commander, ensuring awareness of the aborted procedure.
* Undocking Started: Beginning of the undocking process is indicated to Commander, confirming the ship's transition.
* Docking Requested: When a docking request is made, the system informs Commander of the request status.
* Docking or Undocking Process: The system tracks the docking or undocking process and informs Commander when these actions are in progress.
* Station Docking: Successful docking at a station is confirmed to Commander, indicating the ship's secured position.
* In-Station Status: The system updates Commander on the ship's status when docked at a station.
* Interdiction: Detection of an interdiction attempt triggers an immediate warning to Commander, advising on possible actions.
* Fuel Scooping: Ongoing fuel scooping is tracked and reported to Commander, ensuring awareness of the process.
* Location Update: Changes in the ship's location, such as entering a new star system, are communicated to Commander with relevant details.
* Target Update: Changes in the ship's target destination are communicated to Commander, providing updates on the new destination.
* Fuel Status: The system continuously monitors and reports on the ship's fuel level, ensuring Commander is aware of fuel capacity and percentages.
* Bounty Earned: When a bounty is earned, the system informs Commander of the reward amount.
* Cockpit Breach: Detection of a cockpit breach triggers an alert to Commander, emphasizing the critical nature of the situation.
* Crime Committed: When a crime is committed, the system notifies Commander of the crime type.
* Fighter Operations: Launching or docking of fighters is tracked and reported to Commander, ensuring awareness of fighter status.
* SRV Operations: Launching or docking of SRVs is tracked and reported to Commander, ensuring awareness of SRV status.
* Landing and Liftoff: The system updates Commander on landing or liftoff status, confirming the ship's current state.
* Datalink Scan: Successful completion of a datalink scan is communicated to Commander.
* Self-Destruct: Initiation of self-destruct sequence is reported to Commander, emphasizing the gravity of the action.
* Cargo Ejection: Ejection of cargo is tracked and reported to Commander.
* Interdiction Escape: Successful escape from an interdiction attempt is communicated to Commander.
* Mission Updates: Acceptance, completion, failure, or abandonment of missions are tracked and reported to Commander, ensuring complete mission awareness.
* These event-driven interactions are designed to enhance safety, decision-making, and overall user engagement throughout the journey in Elite Dangerous.

![Event-driven](screen/event_driven.png?raw=true "Screen")


### 6. Function Calling

We can allow the AI to call functions when using OpenAI models. (This can be generalized using the REACT pattern, currently the solution is OpenAI/Openrouter specific.) 

These functions are callable:
- fire: Start firing primary weapons.
- holdFire: Stop firing primary weapons.
- fireSecondary: Start firing secondary weapons.
- holdFireSecondary: Stop firing secondary weapons.
- hyperSuperCombination: Initiate FSD Jump, required to jump to the next system or enter supercruise.
- setSpeedZero: Set speed to 0%.
- setSpeed50: Set speed to 50%.
- setSpeed100: Set speed to 100%.
- deployHeatSink: Deploy heat sink.
- deployHardpointToggle: Deploy or retract hardpoints.
- increaseEnginesPower: Increase engine power.
- increaseWeaponsPower: Increase weapon power.
- increaseSystemsPower: Increase systems power.
- galaxyMapOpen: Open or close the galaxy map.
- systemMapOpen: Open or close the system map.
- cycleNextTarget: Cycle to the next target.
- cycleFireGroupNext: Cycle to the next fire group.
- shipSpotLightToggle: Toggle ship spotlight.
- ejectAllCargo: Eject all cargo.
- landingGearToggle: Toggle landing gear.
- useShieldCell: Use a shield cell.
- fireChaffLauncher: Fire chaff launcher.
- nightVisionToggle: Toggle night vision.
- recallDismissShip: Recall or dismiss ship, available on foot and inside SRV.

![Function Calling](screen/function_calling.png?raw=true "Screen")

## 7. Vision Capabilities

### ToDo (Vision Capabilities)

* Take screenshot of the game and send it to the LLM as context (only applicable if model has image-to-text cabilities) 
* Take live video feed of the game and send it to the LLM as context (only applicable if model has video-to-text cabilities) 


## Troubleshooting

1.  You can remove `config.json` to be prompted again for name, API key and openrouter usage
2. **If you encounter any issues with dependencies** try to install them by hand
   ```sh
      > pip install torch==2.2.2 torchvision==0.17.2 torchaudio==2.2.2 --index-url https://download.pytorch.org/whl/cpu OpenAI
    ```

## CLI Arguments

Add these flags to the cli call to configure Whisper:

### `--model`

- **Description**: Model to use.
- **Default**: `"small"`
- **Choices**: `["tiny", "base", "small", "medium", "large"]`

### `--non_english`

- **Description**: Don't use the English model.
- **Action**: Store `True` if present.

### `--energy_threshold`

- **Description**: Energy level for microphone to detect.
- **Default**: `1000`
- **Type**: Integer

### `--record_timeout`

- **Description**: How real time the recording is in seconds.
- **Default**: `15`
- **Type**: Float

### `--phrase_timeout`

- **Description**: How much empty space between recordings before we consider it a new line in the transcription.
- **Default**: `5`
- **Type**: Float

### `--default_microphone`

- **Description**: Default microphone name for SpeechRecognition.
- **Default (Linux)**: `'pulse'`
- **Type**: String
- **Note**: Run with `'list'` to view available Microphones.

# Contact
tremendouslyrude@yandex.com

# ToDo
* Faster whisper implementation
* Capture and send image to LLM if compatible (GPT-4, GPT-4-Turbo, GPT-4-O, llava, phi-3, [..])