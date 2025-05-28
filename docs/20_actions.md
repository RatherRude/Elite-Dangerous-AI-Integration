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

1. Start firing primary weapons
2. Stop firing primary weapons
3. Start firing secondary weapons
4. Stop firing secondary weapons
5. Initiate FSD jump

    - `jump_type`: String (options: "next_system", "supercruise", "auto")

6. Set flight thrust speed

    - `speed`: String (options: "Minus100", "Minus75", "Minus50", "Minus25", "Zero", "25", "50", "75", "100")

7. Deploy heat sink
8. Toggle hardpoints
9. Manage power distribution

    - `power_category`: Array of strings (options: "Engines", "Weapons", "Systems")
    - `balance_power`: Boolean (whether to balance power)
    - `pips`: Array of integers (1-4, number of pips per category)

10. Open galaxy map and display a system

    - `system_name`: String (optional)
    - `start_navigation`: Boolean (optional)

11. Close galaxy map
12. Toggle system map

    - `desired_state`: String (options: "open", "close")

13. Target next system in route (when nav route is set)
14. Cycle target

    - `direction`: String (options: "next", "previous")

15. Cycle fire group

    - `direction`: String (options: "next", "previous")

16. Toggle ship spotlight
17. Fire chaff launcher
18. Toggle night vision
19. Target highest threat
20. Target subsystem on locked ship

    - `subsystem`: String (options: "Drive", "Shield Generator", "Power Distributor", "Life Support", "FSD", "Point Defence Turret", "Power Plant")

21. Charge ECM

### Main Ship Operations

1. Toggle cargo scoop
2. Eject all cargo
3. Toggle landing gear
4. Use shield cell
5. Request docking
6. Undock ship

### Ship Launched Fighter (SLF) Actions

1. Request docking with main ship

### NPC Orders

1. Defensive Behavior
2. Aggressive Behavior
3. Focus on Target
4. Hold Fire
5. Hold Position
6. Follow Command
7. Recall Fighter

### Surface Reconnaissance Vehicle (SRV) Actions

1. Toggle Drive Assist
2. Primary Fire
3. Secondary Fire
4. Toggle Auto-Brake
5. Toggle Headlights

    - `desired_state`: String (options: "off", "low", "high", "toggle")

6. Toggle Night Vision
7. Toggle Turret Mode
8. Select Target
9. Manage Power Distribution

    - `power_category`: Array of strings (options: "Engines", "Weapons", "Systems")
    - `balance_power`: Boolean (whether to balance power)
    - `pips`: Array of integers (1-4, number of pips per category)

10. Toggle Cargo Scoop
11. Eject All Cargo
12. Recall/Dismiss Ship
13. Open/Close Galaxy Map

    - `desired_state`: String (options: "open", "close")
    - `system_name`: String (optional)
    - `start_navigation`: Boolean (optional)

14. Open/Close System Map

    - `desired_state`: String (options: "open", "close")

### On-Foot (Suits) Actions

1. Primary Interaction
2. Secondary Interaction
3. Equip Gear

    - `equipment`: String (options: "HumanoidSelectPrimaryWeaponButton", "HumanoidSelectSecondaryWeaponButton", "HumanoidSelectUtilityWeaponButton", "HumanoidSwitchToRechargeTool", "HumanoidSwitchToCompAnalyser", "HumanoidSwitchToSuitTool", "HumanoidHideWeaponButton", "HumanoidSelectFragGrenade", "HumanoidSelectEMPGrenade", "HumanoidSelectShieldGrenade")

4. Toggle Flashlight
5. Toggle Night Vision
6. Toggle Shields
7. Clear Authority Level
8. Use Health Pack
9. Use Battery Pack
10. Open/Close Galaxy Map
11. Open/Close System Map
12. Recall/Dismiss Ship

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

## Miscellaneous Actions

1. Get Visuals

    - `query`: String

    Describe what's currently visible to the Commander. Answers the question that lead to tool usage.

2. Send Message

   - `message`: String (required)
   - `channel`: String (required, options: "local", "system", "wing", "squadron", "commander")
   - `recipient`: String (optional, only used if channel is "commander")

    Send a direct message to another commander. Can also send to system, local, wing and squadron chat.