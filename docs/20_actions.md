# Actions

Actions (also called Tools, Commands, or Functions) are the actions that COVAS:NEXT can perform in Elite: Dangerous or outside. There is no need to remember specific commands, as the AI will understand your intent and perform the action accordingly.
Primarily, these actions can be used to control various ship/srv/suit operations, such as firing weapons, adjusting speed, deploying heat sinks, and more.
Additionally, the AI can fetch internet data if it deems it relevant for the conversation, by either your inquiry or game events happening.

## Keyboard Bindings

In order to perform actions in Elite: Dangerous, COVAS:NEXT requires assigned keyboard buttons to be set up in the game. These keybindings are used to emulate button presses, allowing the AI to control various ship/srv/suit operations.
If there are multiple keyboard buttons assigned for one game action, COVAS:NEXT will prefer the secondary binding.

*If you run out of keyboard buttons* keep in mind that you can not only assign a button as press, but also as hold. Keys are also combinable in Elite: Dangerous, so each key can be combined with one or multiple other keys.

## Usage with HOTAS or other Controllers

A common workaround is to assign keyboard bindings alongside your controller bindings, even if you don't use a keyboard. This allows COVAS:NEXT to use these keybindings for its commands, while you continue to use your controller for the game.

## Available Game Actions

This is a list of all currently supported actions the AI can perform. Just talk to it naturally and it will understand your intent.

### Main Ship Actions

1. **Fire weapons** (primary, secondary, discovery scanner)

    - `weaponType`: String (options: "primary", "secondary", "discovery_scanner")
    - `action`: String (options: "fire", "start", "stop")
    - `duration`: Number (optional, seconds)
    - `repetitions`: Integer (optional, 0-10)

    <details>
    <summary>Examples</summary>
    
    - fire primary weapon
    - fire
    - fire secondary
    - fire missiles
    - start firing
    - open fire
    - stop firing
    - cease fire
    - weapons fire
    - engage weapons
    - discovery scanner
    - honk
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - PlayerHUDModeToggle
    - CycleFireGroupNext
    - PrimaryFire
    - SecondaryFire
    </details>

2. **Set flight thrust speed**

    - `speed`: String (options: "Minus100", "Minus75", "Minus50", "Minus25", "Zero", "25", "50", "75", "100")

    <details>
    <summary>Examples</summary>
    
    - full stop
    - half speed
    - full speed
    - reverse
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - SetSpeedMinus100
    - SetSpeedMinus75
    - SetSpeedMinus50
    - SetSpeedMinus25
    - SetSpeedZero
    - SetSpeed25
    - SetSpeed50
    - SetSpeed75
    - SetSpeed100
    </details>

3. **Deploy heat sink**

    <details>
    <summary>Examples</summary>
    
    - heat sink
    - deploy heat sink
    - use heat sink
    - activate heat sink
    - heatsink
    - deploy heatsink
    - cooling
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - DeployHeatSink
    </details>

4. **Toggle hardpoints**

    <details>
    <summary>Examples</summary>
    
    - hardpoints
    - deploy hardpoints
    - retract hardpoints
    - toggle hardpoints
    - hardpoints up
    - hardpoints down
    - weapons out
    - weapons away
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - DeployHardpointToggle
    </details>

5. **Manage power distribution**

    - `power_category`: Array of strings (options: "Engines", "Weapons", "Systems")
    - `balance_power`: Boolean (whether to balance power)
    - `pips`: Array of integers (1-4, number of pips per category)

    <details>
    <summary>Examples</summary>
    
    - balance power
    - reset power
    - four pips to engines
    - four pips to weapons
    - four pips to systems
    - max engines
    - max weapons
    - max systems
    - pips to engines
    - pips to weapons
    - pips to systems
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - ResetPowerDistribution
    - IncreaseEnginesPower
    - IncreaseWeaponsPower
    - IncreaseSystemsPower
    </details>

6. **Open galaxy map**

    - `system_name`: String (optional)
    - `start_navigation`: Boolean (optional)

    <details>
    <summary>Examples</summary>
    
    - galaxy map
    - open galaxy map
    - galmap
    - navigation
    - star map
    - show galaxy map
    - nav map
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - GalaxyMapOpen
    - CamZoomIn
    - UI_Up
    - UI_Left
    - UI_Right
    - UI_Select
    - UI_Back
    - CamZoomOut
    - Key_Enter
    </details>

7. **Close galaxy map**

    <details>
    <summary>Examples</summary>
    
    - close galaxy map
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - GalaxyMapOpen
    </details>

8. **Toggle system map**

    - `desired_state`: String (options: "open", "close")

    <details>
    <summary>Examples</summary>
    
    - system map
    - open system map
    - close system map
    - orrery
    - local map
    - sysmap
    - show system map
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - SystemMapOpen
    - UI_Back
    </details>

9. **Target ship**

    - `mode`: String (options: "next", "previous", "highest_threat", "next_hostile", "previous_hostile", "wingman_1", "wingman_2", "wingman_3", "wingman_1_target", "wingman_2_target", "wingman_3_target")

    <details>
    <summary>Examples</summary>
    
    - next target
    - previous target
    - highest threat
    - target highest threat
    - target biggest threat
    - next hostile
    - next enemy
    - cycle hostile
    - hostile target
    - previous hostile
    - previous enemy
    - first wingman
    - target first wingman
    - first wingmate
    - target first wingmate
    - first teammate
    - target first teammate
    - second wingman
    - target second wingman
    - second wingmate
    - target second wingmate
    - second teammate
    - target second teammate
    - third wingman
    - target third wingman
    - third wingmate
    - target third wingmate
    - third teammate
    - target third teammate
    - first wingman target
    - target first wingman's target
    - first wingmate target
    - target first wingmate's target
    - first teammate target
    - target first teammate's target
    - second wingman target
    - target second wingman's target
    - second wingmate target
    - target second wingmate's target
    - second teammate target
    - target second teammate's target
    - third wingman target
    - target third wingman's target
    - third wingmate target
    - target third wingmate's target
    - third teammate target
    - target third teammate's target
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - CycleNextTarget
    - CyclePreviousTarget
    - SelectHighestThreat
    - CycleNextHostileTarget
    - CyclePreviousHostileTarget
    - TargetWingman0
    - TargetWingman1
    - TargetWingman2
    - SelectTargetsTarget
    </details>

10. **Toggle wing nav lock**

    <details>
    <summary>Examples</summary>
    
    - wing nav lock
    - toggle wing nav lock
    - wing navigation lock
    - wing nav
    - nav lock
    - navigation lock
    - wing follow
    - follow wing
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - WingNavLock
    </details>

11. **Cycle fire group**

    - `direction`: String (options: "next", "previous")

    <details>
    <summary>Examples</summary>
    
    - next fire group
    - previous fire group
    - select next fire group
    - select previous fire group
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - CycleFireGroupNext
    - CycleFireGroupPrevious
    </details>

12. **Switch HUD mode**

    - `hud mode`: String (options: "combat", "analysis", "toggle")

    <details>
    <summary>Examples</summary>
    
    - combat mode
    - analysis mode
    - switch to combat
    - switch to analysis
    - toggle hud mode
    - hud mode
    - change hud
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - PlayerHUDModeToggle
    </details>

13. **Toggle ship spotlight**

    <details>
    <summary>Examples</summary>
    
    - ship light
    - lights
    - lights on
    - turn on lights
    - lights off
    - toggle lights
    - toggle the lights
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - ShipSpotLightToggle
    </details>

14. **Fire chaff launcher**

    <details>
    <summary>Examples</summary>
    
    - chaff
    - fire chaff
    - launch chaff
    - deploy chaff
    - countermeasures
    - evade
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - FireChaffLauncher
    </details>

15. **Toggle night vision**

    <details>
    <summary>Examples</summary>
    
    - nightvision
    - night vision
    - toggle nightvision
    - thermal vision
    - enhanced vision
    - infrared
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - NightVisionToggle
    </details>

16. **Target subsystem on locked ship**

    - `subsystem`: String (options: "Drive", "Shield Generator", "Power Distributor", "Life Support", "FSD", "Point Defence Turret", "Power Plant")

    <details>
    <summary>Examples</summary>
    
    - target drive
    - target drives
    - target power distributor
    - target distributor
    - target shields
    - target shield generator
    - target life support
    - target frame shift drive
    - target fsd
    - target power
    - target power plant
    - target the drive
    - target the drives
    - target the power distributor
    - target the distributor
    - target the shields
    - target the shield generator
    - target the life support
    - target the frame shift drive
    - target the fsd
    - target the power
    - target the power plant
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - CycleNextSubsystem
    </details>

17. **Charge ECM**

    <details>
    <summary>Examples</summary>
    
    - ecm
    - charge ecm
    - electronic countermeasures
    - activate ecm
    - ecm blast
    - disrupt
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - ChargeECM
    </details>

18. **NPC crew orders**

    - `orders`: Array of strings (options: "DefensiveBehaviour", "AggressiveBehaviour", "FocusTarget", "HoldFire", "HoldPosition", "Follow", "ReturnToShip", "LaunchFighter1", "LaunchFighter2")

    <details>
    <summary>Examples</summary>
    
    - launch fighter
    - deploy fighter
    - recall fighter
    - attack my target
    - engage target
    - defend me
    - be aggressive
    - hold fire
    - cease fire
    - hold position
    - follow me
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - FocusRadarPanel
    - UI_Left
    - UI_Right
    - UI_Up
    - UI_Down
    - UI_Select
    - UIFocus
    - OrderDefensiveBehaviour
    - OrderAggressiveBehaviour
    - OrderFocusTarget
    - OrderHoldFire
    - OrderHoldPosition
    - OrderFollow
    - OrderRequestDock
    </details>

### Main Ship Operations

1. **Initiate FSD jump**

    - `jump_type`: String (options: "next_system", "supercruise", "auto")

    <details>
    <summary>Examples</summary>
    
    - jump
    - engage fsd
    - frame shift drive
    - jump to next system
    - hyperspace jump
    - supercruise
    - enter supercruise
    - punch it
    - let's go
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - Hyperspace (if NextJumpTarget set)
    - Supercruise (if jump_type == supercruise)
    - HyperSuperCombination (auto)
    - SetSpeed100
    - LandingGearToggle (auto retract when down)
    - ToggleCargoScoop (auto retract when deployed)
    - DeployHardpointToggle (auto retract when deployed)
    </details>

2. **Target next system in route**

    <details>
    <summary>Examples</summary>
    
    - next system
    - target next system
    - next destination
    - next waypoint
    - continue route
    - next in route
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - TargetNextRouteSystem
    </details>

3. **Toggle cargo scoop**

    <details>
    <summary>Examples</summary>
    
    - cargo scoop
    - scoop
    - deploy scoop
    - retract scoop
    - toggle scoop
    - open cargo scoop
    - close cargo scoop
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - ToggleCargoScoop
    </details>

4. **Eject all cargo**

    <details>
    <summary>Examples</summary>
    
    - eject cargo
    - dump cargo
    - jettison cargo
    - drop cargo
    - emergency cargo drop
    - purge cargo
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - EjectAllCargo
    </details>

5. **Toggle landing gear**

    <details>
    <summary>Examples</summary>
    
    - landing gear
    - gear
    - deploy gear
    - retract gear
    - landing gear up
    - landing gear down
    - gear up
    - gear down
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - LandingGearToggle
    </details>

6. **Use shield cell**

    <details>
    <summary>Examples</summary>
    
    - shield cell
    - use shield cell
    - scb
    - activate scb
    - shield boost
    - repair shields
    - restore shields
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - UseShieldCell
    </details>

7. **Request docking**

    <details>
    <summary>Examples</summary>
    
    - request docking
    - dock
    - docking request
    - permission to dock
    - requesting docking
    - docking permission
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - FocusLeftPanel
    - CyclePreviousPanel
    - UI_Left
    - UI_Right
    - UI_Up
    - UI_Select
    - UIFocus
    </details>

8. **Undock ship**

    <details>
    <summary>Examples</summary>
    
    - undock
    - launch
    - depart
    - leave station
    - takeoff
    - disengage
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - UI_Down
    - UI_Up
    - UI_Select
    </details>

### Ship Launched Fighter (SLF) Actions

1. **Request docking with main ship**

    <details>
    <summary>Examples</summary>
    
    - request docking
    - dock
    - docking request
    - permission to dock
    - requesting docking
    - docking permission
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - OrderRequestDock
    </details>

### Surface Reconnaissance Vehicle (SRV) Actions

1. **Toggle Drive Assist**

    <details>
    <summary>Examples</summary>
    
    - drive assist
    - toggle drive assist
    - assistance
    - auto drive
    - driving assistance
    - stability
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - ToggleDriveAssist
    </details>

2. **Fire SRV weapons**

    - `weaponType`: String (options: "primary", "secondary")
    - `action`: String (options: "fire", "start", "stop")
    - `duration`: Number (optional, seconds)
    - `repetitions`: Integer (optional, 0-10)

    <details>
    <summary>Examples</summary>
    
    - fire srv weapons
    - shoot
    - fire plasma
    - fire missiles
    - srv weapons
    - engage weapons
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - BuggyPrimaryFireButton
    - BuggySecondaryFireButton
    </details>

3. **Toggle Auto-Brake**

    <details>
    <summary>Examples</summary>
    
    - auto brake
    - toggle brake
    - automatic braking
    - brake assist
    - handbrake
    - parking brake
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - AutoBreakBuggyButton
    </details>

4. **Toggle Headlights**

    - `desired_state`: String (options: "off", "low", "high", "toggle")

    <details>
    <summary>Examples</summary>
    
    - lights
    - headlights
    - toggle lights
    - lights on
    - lights off
    - bright lights
    - dim lights
    - full beam
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - HeadlightsBuggyButton
    </details>

5. **Toggle Night Vision**

    <details>
    <summary>Examples</summary>
    
    - nightvision
    - night vision
    - toggle nightvision
    - thermal vision
    - enhanced vision
    - infrared
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - NightVisionToggle
    </details>

6. **Toggle Turret Mode**

    <details>
    <summary>Examples</summary>
    
    - turret
    - toggle turret
    - turret mode
    - gun turret
    - deploy turret
    - retract turret
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - ToggleBuggyTurretButton
    </details>

7. **Select Target**

    <details>
    <summary>Examples</summary>
    
    - target
    - select target
    - lock target
    - acquire target
    - scan
    - focus
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - SelectTarget_Buggy
    </details>

8. **Manage Power Distribution**

    - `power_category`: Array of strings (options: "Engines", "Weapons", "Systems")
    - `balance_power`: Boolean (whether to balance power)
    - `pips`: Array of integers (1-4, number of pips per category)

    <details>
    <summary>Examples</summary>
    
    - balance power
    - reset power
    - four pips to engines
    - four pips to weapons
    - four pips to systems
    - max engines
    - max weapons
    - max systems
    - pips to engines
    - pips to weapons
    - pips to systems
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - ResetPowerDistribution_Buggy
    - IncreaseEnginesPower_Buggy
    - IncreaseWeaponsPower_Buggy
    - IncreaseSystemsPower_Buggy
    </details>

9. **Toggle Cargo Scoop**

    <details>
    <summary>Examples</summary>
    
    - cargo scoop
    - scoop
    - deploy scoop
    - retract scoop
    - toggle scoop
    - collect materials
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - ToggleCargoScoop_Buggy
    </details>

10. **Eject All Cargo**

    <details>
    <summary>Examples</summary>
    
    - eject cargo
    - dump cargo
    - jettison cargo
    - drop cargo
    - purge cargo
    - drop materials
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - EjectAllCargo_Buggy
    </details>

11. **Recall/Dismiss Ship**

    <details>
    <summary>Examples</summary>
    
    - recall ship
    - dismiss ship
    - call ship
    - send ship away
    - summon ship
    - ship pickup
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - HumanoidOpenAccessPanelButton
    - UI_Left
    - UI_Up
    - UI_Select
    </details>

12. **Open/Close Galaxy Map**

    - `desired_state`: String (options: "open", "close")
    - `system_name`: String (optional)
    - `start_navigation`: Boolean (optional)

    <details>
    <summary>Examples</summary>
    
    - galaxy map
    - open galaxy map
    - close galaxy map
    - galmap
    - navigation
    - star map
    - nav map
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - GalaxyMapOpen_Buggy
    - CamZoomIn
    - UI_Up
    - UI_Left
    - UI_Right
    - UI_Select
    - UI_Back
    - CamZoomOut
    - Key_Enter
    </details>

13. **Open/Close System Map**

    - `desired_state`: String (options: "open", "close")

    <details>
    <summary>Examples</summary>
    
    - system map
    - open system map
    - close system map
    - orrery
    - local map
    - sysmap
    - show system map
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - SystemMapOpen_Buggy
    </details>

### On-Foot (Suits) Actions

1. **Primary Interaction**

    <details>
    <summary>Examples</summary>
    
    - interact
    - primary interact
    - use
    - activate
    - press
    - engage
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - HumanoidPrimaryInteractButton
    </details>

2. **Secondary Interaction**

    <details>
    <summary>Examples</summary>
    
    - secondary interact
    - alternate use
    - secondary action
    - hold interact
    - long press
    - alternative
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - HumanoidSecondaryInteractButton
    </details>

3. **Equip Gear**

    - `equipment`: String (options: "HumanoidSelectPrimaryWeaponButton", "HumanoidSelectSecondaryWeaponButton", "HumanoidSelectUtilityWeaponButton", "HumanoidSwitchToRechargeTool", "HumanoidSwitchToCompAnalyser", "HumanoidSwitchToSuitTool", "HumanoidHideWeaponButton", "HumanoidSelectFragGrenade", "HumanoidSelectEMPGrenade", "HumanoidSelectShieldGrenade")

    <details>
    <summary>Examples</summary>
    
    - primary weapon
    - secondary weapon
    - utility weapon
    - recharge tool
    - comp analyser
    - composition scanner
    - suit tool
    - hide weapon
    - holster
    - frag grenade
    - emp grenade
    - shield grenade
    - scanner
    - energylink
    - profile analyser
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - HumanoidSelectPrimaryWeaponButton
    - HumanoidSelectSecondaryWeaponButton
    - HumanoidSelectUtilityWeaponButton
    - HumanoidSwitchToRechargeTool
    - HumanoidSwitchToCompAnalyser
    - HumanoidSwitchToSuitTool
    - HumanoidHideWeaponButton
    - HumanoidSelectFragGrenade
    - HumanoidSelectEMPGrenade
    - HumanoidSelectShieldGrenade
    </details>

4. **Toggle Flashlight**

    <details>
    <summary>Examples</summary>
    
    - flashlight
    - torch
    - lights
    - toggle lights
    - illumination
    - helmet light
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - HumanoidToggleFlashlightButton
    </details>

5. **Toggle Night Vision**

    <details>
    <summary>Examples</summary>
    
    - nightvision
    - night vision
    - toggle nightvision
    - thermal vision
    - enhanced vision
    - infrared
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - HumanoidToggleNightVisionButton
    </details>

6. **Toggle Shields**

    <details>
    <summary>Examples</summary>
    
    - suit shields
    - personal shields
    - toggle shields
    - energy shield
    - shield generator
    - protective field
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - HumanoidToggleShieldsButton
    </details>

7. **Clear Authority Level**

    <details>
    <summary>Examples</summary>
    
    - clear authority
    - reset authority
    - clear wanted level
    - clear notoriety
    - authority reset
    - clean record
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - HumanoidClearAuthorityLevel
    </details>

8. **Use Health Pack**

    <details>
    <summary>Examples</summary>
    
    - health pack
    - medkit
    - heal
    - use medkit
    - medical
    - first aid
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - HumanoidHealthPack
    </details>

9. **Use Battery Pack**

    <details>
    <summary>Examples</summary>
    
    - battery
    - energy cell
    - recharge
    - power up
    - restore power
    - charge suit
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - HumanoidBattery
    </details>

10. **Open/Close Galaxy Map**

    <details>
    <summary>Examples</summary>
    
    - galaxy map
    - open galaxy map
    - galmap
    - navigation
    - star map
    - nav map
    - show galaxy map
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - GalaxyMapOpen_Humanoid
    </details>

11. **Open/Close System Map**

    <details>
    <summary>Examples</summary>
    
    - system map
    - open system map
    - close system map
    - orrery
    - local map
    - sysmap
    - show system map
    </details>

    <details>
    <summary>Required Keyboard Binds</summary>

    - SystemMapOpen_Humanoid
    </details>

12. **Recall/Dismiss Ship**

    <details>
    <summary>Examples</summary>
    
    - recall ship
    - dismiss ship
    - call ship
    - send ship away
    - summon ship
    - ship pickup
    </details>

## Available Online-Lookup Actions

1. Galnet News

    - `query`: String

    Retrieves current interstellar news from Galnet. Answers the question that lead to tool usage.

2. System Finder (utilizes [Spansh API](https://spansh.co.uk/systems))

    - `reference_system`: String (required)
    - `name`: String (optional)
    - `distance`: Number (optional, default: 50000)
    - `allegiance`: Array of strings (options: "Alliance", "Empire", "Federation", "Guardian", "Independent", "Pilots Federation", "Player Pilots", "Thargoid")
    - `state`: Array of strings
    - `government`: Array of strings
    - `power`: Array of strings
    - `primary_economy`: Array of strings
    - `security`: Array of strings
    - `thargoid_war_state`: Array of strings
    - `population`: Object with `comparison` ("<" or ">") and `value` (Number)

    Find a star system based on various filters.

3. Station Finder (utilizes [Spansh API](https://spansh.co.uk/stations))

    - `reference_system`: String (required)
    - `name`: String (optional)
    - `distance`: Number (optional, default: 50000)
    - `has_large_pad`: Boolean (optional)
    - `material_trader`: Array of strings (options: "Encoded", "Manufactured", "Raw")
    - `technology_broker`: Array of strings (options: "Guardian", "Human")
    - `modules`: Array of objects with `name` (String), `class` (Array), `rating` (Array)
    - `commodities`: Array of objects with `name` (String), `amount` (Integer), `transaction` ("Buy" or "Sell")
    - `ships`: Array of objects with `name` (String)
    - `services`: Array of objects with `name` (String, options: "Black Market", "Interstellar Factors Contact")

    Find a station based on various filters.

4. Body Finder (utilizes [Spansh API](https://spansh.co.uk/bodies))

    - `reference_system`: String (required)
    - `name`: String (optional)
    - `distance`: Number (optional, default: 50000)
    - `subtype`: Array of strings
    - `landmark_subtype`: Array of strings

    Find a celestial body based on various filters.

## UI Actions

1. **Show UI**

    - `tab`: String (options: "chat", "status", "storage", "station")

    <details>
    <summary>Examples</summary>
    
    - display chat
    - show status
    - open storage
    - open station tab
    </details>

## Miscellaneous Actions

1. Get Visuals

    - `query`: String

    Describe what's currently visible to the Commander. Answers the question that lead to tool usage.

2. Engineer Finder

    - `name`: String (optional)
    - `system`: String (optional)
    - `modifications`: String (optional)
    - `progress`: String (optional, options: "Unknown", "Known", "Invited", "Unlocked")

    Get information about engineers' location, standing and modifications.

3. Blueprint Finder

    - `modifications`: Array of strings (optional)
    - `engineer`: String (optional)
    - `module`: String (optional)
    - `grade`: Integer (optional)

    Find engineer blueprints based on search criteria. Returns material costs with grade calculations.

4. Material Finder

    - `name`: Array of strings (optional)
    - `grade`: Integer (optional, 1-5)
    - `type`: String (optional, options: "raw", "manufactured", "encoded", "items", "components", "data", "consumables", "ship", "suit")

    Find and search a list of materials for both ship and suit engineering from the commander's inventory and where to source them from.

5. Send Message

   - `message`: String (required)
   - `channel`: String (required, options: "local", "system", "wing", "squadron", "commander")
   - `recipient`: String (optional, only used if channel is "commander")

    Send a direct message to another commander. Can also send to system, local, wing and squadron chat.

    <details>
    <summary>Required Keyboard Binds</summary>

    - QuickCommsPanel (ship)
    - QuickCommsPanel_Buggy (SRV)
    - QuickCommsPanel_Humanoid (on-foot)
    - UI_Down (for system channel selection)
    - UI_Select
    - Key_Enter
    </details>

