# Actions

Actions (also called Tools, Commands, or Functions) are the actions that COVAS:NEXT can perform in Elite: Dangerous or outside. There is no need to remember specific commands, as the AI will understand your intent and perform the action accordingly.
Primarily, these actions can be used to control various ship/srv/suit operations, such as firing weapons, adjusting speed, deploying heat sinks, and more.
Additionally, the AI can fetch internet data if it deems it relevant for the conversation, by either your inquiry or game events happening.

## Keyboard Bindings

In order to perform actions in Elite: Dangerous, COVAS:NEXT requires assigned keyboard buttons to be set up in the game. These keybindings are used to emulate button presses, allowing the AI to control various ship/srv/suit operations.
The game's keyboard bindings are automatically read on COVAS:NEXT's start-up, if you change a setting you will have to restart the integration for it to be registered.
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
6. Set speed to 0%
7. Set speed to 50%
8. Set speed to 100%
9. Deploy heat sink
10. Toggle hardpoints
11. Increase engine power.

    - `pips`: Integer (default: 1, maximum: 4)

12. Increase weapon power

    - `pips`: Integer (default: 1, maximum: 4)

13. Increase systems power

    - `pips`: Integer (default: 1, maximum: 4)

14. Open galaxy map and display a system

    - `system_name`: String (optional)

15. Plot route macro
16. Close galaxy map
16. Toggle system map
17. Cycle next target
18. Cycle fire group
19. Toggle ship spotlight
20. Eject all cargo
21. Toggle landing gear
22. Use shield cell
23. Fire chaff launcher
24. Toggle night vision
25. Recall or dismiss ship
26. Target highest threat
27. Toggle cargo scoop
28. Charge ECM
29. Request docking macro
30. Undock macro

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
6. Toggle Turret Mode
7. Select Target
8. Increase Power to Engines
9. Increase Power to Weapons
10. Increase Power to Systems
11. Reset Power Distribution
12. Toggle Cargo Scoop
13. Eject All Cargo
14. Recall/Dismiss Ship
15. Open Galaxy Map
16. Open System Map

### On-Foot (Suits) Actions

1. Primary Interaction
2. Secondary Interaction
3. Weapon and Tool Management:

   - Equip Primary Weapon
   - Equip Secondary Weapon
   - Equip Utility Weapon
   - Switch to Recharge Tool
   - Switch to Comp Analyzer
   - Switch to Suit Tool
   - Holster Weapon
   - Equip Frag Grenade
   - Equip EMP Grenade
   - Equip Shield Grenade

4. Toggle Flashlight
5. Toggle Night Vision
6. Toggle Shields
7. Clear Authority Level
8. Use Health Pack
9. Use Battery Pack
10. Open Galaxy Map
11. Open System Map
12. Dismiss/Recall Ship Macro

## Available Online-Lookup Actions

1. Galnet News

    - `query`: String.
   
     Retrieves current interstellar news from Galnet. Answers the question that lead to tool usage.

2. Trade Plotter

    - `system`: String.
    - `station`: String.
    - `max_hops`: Integer.
    - `max_hop_distance`: Number.
    - `starting_capital`: Number.
    - `max_cargo`: Integer.
    - `requires_large_pad`: Boolean.

     Retrieves a trade route from the trade plotter.

3. System Finder

    - `name`: String.
    - `reference_system`: String.
    - `distance`: Number (default: 50000).
    - `allegiance`: Array of strings.
    - `state`: Array of strings.
    - `government`: Array of strings.
    - `power`: Array of strings.
    - `primary_economy`: Array of strings.
    - `security`: Array of strings.
    - `thargoid_war_state`: Array of strings.
    - `population`: Object.

      - `comparison`: String ("<" or ">").
      - `value`: Number.

     Find a star system based on various filters.

4. Station Finder

    - `name`: String.
    - `reference_system`: String.
    - `has_large_pad`: Boolean.
    - `distance`: Number (optional).
    - `material_trader`: Array of strings.
    - `technology_broker`: Array of strings.
    - `modules`: Array of objects.

      - `name`: String.
      - `class`: Array of strings.
      - `rating`: Array of strings.

    - `market`: Array of objects.

      - `name`: String.
      - `amount`: Integer.
      - `transaction`: String ("Buy" or "Sell").

    - `ships`: Array of objects.

      - `name`: String.

    - `services`: Array of objects.

      - `name`: String.

     Find a station based on various filters.

5. Body Finder

    - `name`: String.
    - `reference_system`: String.
    - `distance`: Number (optional).
    - `subtype`: Array of strings.
    - `landmark_subtype`: Array of strings.

     Find a celestial body based on various filters.

## Miscellaneous Actions

1. Get Visuals

    - `query`: String.

     Describe what's currently visible to the Commander. Answers the question that lead to tool usage.

2. Send Message

   - `message`: String.
   - `recipient`: String.

    Send a direct message to another commander. Can also send to local, wing and squadron chat.