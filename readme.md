# AI Integration

We are integrating advanced AI features including Whisper for Speech-to-Text (STT), OpenAI or OpenRouter Language Models (LLMs) for natural language processing, and existing Text-to-Speech (TTS) functionality. This integration aims to provide a more intuitive and hands-free experience for commanders, making interactions with the game more seamless and efficient.

## Overview

The AI integration comprises three main components:
1. **How to install**
   1. Prerequisites
2. **How to run**
3. **Whisper Speech-to-Text (STT)**
4. **OpenAI/OpenRouter Language Models (LLMs)**
   1. **Pricing Information**
5. **Text-to-Speech (TTS)**
6. **Web Lookups for Detailed Information (EDSM)**
7. **Event-Driven Interaction**
8. **Function Calling**
9. **Vision Capabilities**

### 1. How to install

#### Prerequisites

You will need to install Python. Due to compatibility of the used libraries only Python version 3.7-3.11 are currently supported. I currently run 3.8.10 without issues.

#### Installation

* Run EDAIIInstaller.bat (right click, "Run as administrator")

*This will run a pip install with our requirements.txt*

### 2. How to run

* Run EDAII.bat

![GUI-start](screen/GUI_start.png?raw=true)
Enter OpenAI API key and your commander name. Edit AI character according to your desired roleplay. *AI Geek section is not required for regular use.*

Click "Start AI" when ready:
![GUI-ai](screen/GUI_AI.png?raw=true)

### 3. Whisper Speech-to-Text (STT)

Whisper by OpenAI converts spoken language into text, allowing commanders to issue voice commands to the autopilot with high accuracy.

We are currently using CPU for recognition, this can be changed by swapping the dependencies

### 4. OpenAI/OpenRouter/Local Language Models (LLMs)

LLMs from OpenAI or OpenRouter process natural language commands, providing intelligent responses and actions, enabling the autopilot to understand complex instructions.

The program will ask for your API Key. It is saved locally in `config.json` and reused on next program start.

The program is designed to be used with default model and OpenAI services. It's possible to connect to any OpenAI-compatible API.

#### 4.1. Pricing Information

* **OpenAI**: Generally, access to OpenAI models requires a payment. For more information on pricing, please visit: https://openai.com/api/pricing/
* **OpenRouter**: OpenRouter offers a variety of models, some of which are **free** to use. Detailed pricing information for each model can be found here: https://openrouter.ai/docs/models
* **Local**: **Free** to use, although there are associated costs for hardware and electricity. Note that running larger models might require significant hardware resources, such as multi-GPU setups or dedicated machines.


### 5. Text-to-Speech (TTS)

The TTS functionality delivers auditory feedback based on the actions and responses from the LLM. We currently use the default voices from the operating system.

### 6. Web Lookups for Detailed Information (EDSM)

The system performs web lookups using EDSM's API to fetch detailed information about the current and next star systems, enhancing situational awareness.
The AI is able to fetch station and faction data via function calling aswell, you simply have to ask about it.

### 7. Event-Driven Interaction

The system dynamically responds to game events such as ship type changes, new jump destinations, shield status updates, attacks, and more, keeping the commander informed of critical events and statuses.

Here is a list of the currently supported event types:

#### Startup Events:
- Cargo
- Materials
- Missions
- Progress
- Rank
- Reputation
- Statistics

#### Powerplay Events:
- PowerplayCollect
- PowerplayDefect
- PowerplayDeliver
- PowerplayFastTrack
- PowerplayJoin
- PowerplayLeave
- PowerplaySalary
- PowerplayVote
- PowerplayVoucher

#### Squadron Events:
- AppliedToSquadron
- DisbandedSquadron
- InvitedToSquadron
- JoinedSquadron
- KickedFromSquadron
- LeftSquadron
- SharedBookmarkToSquadron
- SquadronCreated
- SquadronDemotion
- SquadronPromotion
- SquadronStartup
- WonATrophyForSquadron

#### Exploration Events:
- CodexEntry
- DiscoveryScan
- Scan

#### Trade Events:
- Trade
- AsteroidCracked
- BuyTradeData
- CollectCargo
- EjectCargo
- MarketBuy
- MarketSell
- MiningRefined

#### Station Services Events:
- StationServices
- BuyAmmo
- BuyDrones
- CargoDepot
- CommunityGoal
- CommunityGoalDiscard
- CommunityGoalJoin
- CommunityGoalReward
- CrewAssign
- CrewFire
- CrewHire
- EngineerContribution
- EngineerCraft
- EngineerLegacyConvert
- EngineerProgress
- FetchRemoteModule
- Market
- MassModuleStore
- MaterialTrade
- MissionAbandoned
- MissionAccepted
- MissionCompleted
- MissionFailed
- MissionRedirected
- ModuleBuy
- ModuleRetrieve
- ModuleSell
- ModuleSellRemote
- ModuleStore
- ModuleSwap
- Outfitting
- PayBounties
- PayFines
- PayLegacyFines
- RedeemVoucher
- RefuelAll
- RefuelPartial
- Repair
- RepairAll
- RestockVehicle
- ScientificResearch
- Shipyard
- ShipyardBuy
- ShipyardNew
- ShipyardSell
- ShipyardTransfer
- ShipyardSwap
- StoredModules
- StoredShips
- TechnologyBroker
- ClearImpound

#### Fleet Carrier Events:
- CarrierJump
- CarrierBuy
- CarrierStats
- CarrierJumpRequest
- CarrierDecommission
- CarrierCancelDecommission
- CarrierBankTransfer
- CarrierDepositFuel
- CarrierCrewServices
- CarrierFinance
- CarrierShipPack
- CarrierModulePack
- CarrierTradeOrder
- CarrierDockingPermission
- CarrierNameChanged
- CarrierJumpCancelled

#### Odyssey Events:
- Backpack
- BackpackChange
- BookDropship
- BookTaxi
- BuyMicroResources
- BuySuit
- BuyWeapon
- CancelDropship
- CancelTaxi
- CollectItems
- CreateSuitLoadout
- DeleteSuitLoadout
- Disembark
- DropItems
- DropShipDeploy
- Embark
- FCMaterials
- LoadoutEquipModule
- LoadoutRemoveModule
- RenameSuitLoadout
- ScanOrganic
- SellMicroResources
- SellOrganicData
- SellWeapon
- SwitchSuitLoadout
- TransferMicroResources
- TradeMicroResources
- UpgradeSuit
- UpgradeWeapon
- UseConsumable

#### Other Events:
- AfmuRepairs
- ApproachSettlement
- ChangeCrewRole
- CockpitBreached
- CommitCrime
- Continued
- CrewLaunchFighter
- CrewMemberJoins
- CrewMemberQuits
- CrewMemberRoleChange
- CrimeVictim
- DatalinkScan
- DatalinkVoucher
- DataScanned
- DockFighter
- DockSRV
- EndCrewSession
- FighterRebuilt
- FuelScoop
- Friends
- JetConeBoost
- JetConeDamage
- JoinACrew
- KickCrewMember
- LaunchDrone
- LaunchFighter
- LaunchSRV
- ModuleInfo
- NpcCrewPaidWage
- NpcCrewRank
- Promotion
- ProspectedAsteroid
- QuitACrew
- RebootRepair
- ReceiveText
- RepairDrone
- ReservoirReplenished
- Resurrect
- Scanned
- SelfDestruct
- SendText
- Shutdown
- Synthesis
- SystemsShutdown
- USSDrop
- VehicleSwitch
- WingAdd
- WingInvite
- WingJoin
- WingLeave
- CargoTransfer
- SupercruiseDestinationDrop

These event-driven interactions are designed to enhance safety, decision-making, and overall user engagement throughout the journey in Elite Dangerous.

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
* Join Discord Server: https://discord.gg/9c58jxVuAT
* Rarely, I also check mails: tremendouslyrude@yandex.com

# ToDo
* Faster whisper implementation for Speech-to-Text
* more quality models for Text-to-Speech
