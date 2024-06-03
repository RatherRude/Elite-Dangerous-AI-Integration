# AI Integration

We are integrating advanced AI features including Whisper for Speech-to-Text (STT), OpenAI or OpenRouter Language Models (LLMs) for natural language processing, and existing Text-to-Speech (TTS) functionality. This integration aims to provide a more intuitive and hands-free experience for commanders, making interactions with the game more seamless and efficient.

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
   You will be asked if you use openrouter, for your api key and your commander name. After the selected whisper model downloaded and initialized you will be ready to start talking.

   ![CLI Startup](screen/cli_startup.png?raw=true "Screen")

   You can change the used model and backstory in `Chat.py`. (Starting of file, but below imports section)

## AI Integration Overview

The AI integration comprises three main components:
1. **How to install**
2. **How to run**
3. **Whisper Speech-to-Text (STT)**
4. **OpenAI/OpenRouter Language Models (LLMs)**
5. **Text-to-Speech (TTS)**
6. **Web Lookups for Detailed Information (EDSM)**
7. **Event-Driven Interaction**
8. **Function Calling**
9. **Vision Capabilities**

### 1. How to install

#### Prerequisites

You will need to install Python. Due to compatibility of the used libraries only Python version 3.7-3.11 are currently supported. I currently run 3.8.10 without issues.

#### Installation

* Download latest version
* Open Powershell and change directory to where you downloaded the latest version (Example for folder location S:\Elite-Dangerous-AI-Integration\)
  ```sh
   >   cd S:\Elite-Dangerous-AI-Integration\
   ```
* install dependencies using pip 
  ```sh
   >   pip install -r requirements.txt
   ```

### 2. How to run

* Open Powershell and change directory to where you downloaded the latest version (Example for folder location S:\Elite-Dangerous-AI-Integration\)
  ```sh
   >   cd S:\Elite-Dangerous-AI-Integration\
   ```
* Start the integration
  ```sh
   >   python .\Chat.py
   ```

### 3. Whisper Speech-to-Text (STT)

Whisper by OpenAI converts spoken language into text, allowing commanders to issue voice commands to the autopilot with high accuracy.

We are currently using CPU for speed recognition, this can be changed by swapping the dependencies

### 4. OpenAI/OpenRouter Language Models (LLMs)

LLMs from OpenAI or OpenRouter process natural language commands, providing intelligent responses and actions, enabling the autopilot to understand complex instructions.

The program will ask if you use Openrouter and for your API Key. It is saved locally in `config.json` and reused on next program start.

*You can use models from either Openrouter or OpenAI, the model is currently changed by swapping out the line in `Chat.py` (Starting of file, but below imports section)*:
* https://openai.com/api/pricing/
* https://openrouter.ai/docs#models

*You can also alter the backstory in `Chat.py`*:


### 5. Text-to-Speech (TTS)

The TTS functionality delivers auditory feedback based on the actions and responses from the LLM.

### 6. Web Lookups for Detailed Information (EDSM)

The system performs web lookups using EDSM's API to fetch detailed information about the current and next star systems, enhancing situational awareness.

### 7. Event-Driven Interaction

The system dynamically responds to game events such as ship type changes, new jump destinations, shield status updates, attacks, and more, keeping the commander informed of critical events and statuses.

Here is a list of the currently supported event types:

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


### 8. Function Calling

The AI can call specific functions (e.g., firing weapons, adjusting speed, deploying heat sinks) using OpenAI models, enabling direct control over various ship operations.

(This can be generalized using the REACT pattern, currently the solution is OpenAI/Openrouter specific.) 

These functions are currently callable:

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

## 9. Vision Capabilities

The AI can take screenshots and analyze their content to provide visual confirmations and insights based on the commander's queries.

## Troubleshooting

1.  You can remove `config.json` to be prompted again for name, API key and openrouter usage
2.  You need to set certain key bindings so the AI is able to trigger the corresponding action. In case you forgot a key a log file will be created which tells you which keys are missing. (EDAI.log)
3. **If you encounter any issues with dependencies** try to install them by hand
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
* Faster whisper implementation for Speech-to-Text
* more quality models for Text-to-Speech