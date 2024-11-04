# Actions

Actions (also called Tools, Commands, or Functions) are the actions that COVAS:NEXT can perform in Elite: Dangerous or outside. There is no need to remember specific commands, as the AI will understand your intent and perform the action accordingly.
Primarily, these actions can be used to control various ship operations, such as firing weapons, adjusting speed, deploying heat sinks, and more.
Additionally, the AI can fetch internet data if it deems it relevant for the conversation, by either your inquiry or game events happening.

# Keybindings

In order to perform actions in Elite: Dangerous, COVAS:NEXT requires keybindings to be set up in the game. These keybindings are used to emulate button presses, allowing the AI to control various ship operations. At the time of writing, COVAS:NEXT only supports for the following Elite: Dangerous keys:

![Available keys for keybindings](./screen/keybindings.png)

## Usage with HOTAS or other controllers

A common workaround is to assign keyboard bindings alongside your controller bindings, even if you don't use a keyboard. This allows COVAS:NEXT to use these keybindings for its commands, while you continue to use your controller for the game.

## Secondary Keybindings

TODO: check how secondary keybindings can be used

## Available Ship Actions
This is a list of all currently supported actions the AI can perform. Just talk to it naturally and it will understand your intent.

1. **fire**

    Start firing primary weapons.

2. **holdFire**

    Stop firing primary weapons.

3. **fireSecondary**

    Start firing secondary weapons.

4. **holdFireSecondary**

    Stop firing secondary weapons.

5. **hyperSuperCombination**

    Initiate FSD Jump, required to jump to the next system or enter supercruise.

6. **setSpeedZero**

    Set speed to 0%.

7. **setSpeed50**

    Set speed to 50%.

8. **setSpeed100**

    Set speed to 100%.

9. **deployHeatSink**

    Deploy heat sink.

10. **deployHardpointToggle**

     Deploy or retract hardpoints.

11. **increaseEnginesPower**
    - `pips`: Integer (default: 1, maximum: 4).

     Increase engine power.

12. **increaseWeaponsPower**
    - `pips`: Integer (default: 1, maximum: 4).

     Increase weapon power.

13. **increaseSystemsPower**
    - `pips`: Integer (default: 1, maximum: 4).

     Increase systems power.

14. **galaxyMapOpen**
    - `system_name`: String (optional).

     Open galaxy map. Zoom in on system or plot a route.

15. **galaxyMapClose**

     Close galaxy map.

16. **systemMapOpen**

     Open or close system map.

17. **cycleNextTarget**

     Cycle to next target.

18. **cycleFireGroupNext**

     Cycle to next fire group.

19. **shipSpotLightToggle**

     Toggle ship spotlight.

20. **ejectAllCargo**

     Eject all cargo.

21. **landingGearToggle**

     Toggle landing gear.

22. **useShieldCell**

     Use shield cell.

23. **fireChaffLauncher**

     Fire chaff launcher.

24. **nightVisionToggle**

     Toggle night vision.

25. **recallDismissShip**

     Recall or dismiss ship (available on foot and inside SRV).

26. **selectHighestThreat**

     Target lock on the highest threat.

27. **toggleCargoScoop**

     Toggle cargo scoop.

28. **chargeECM**

     Charge ECM.

## Available Online-Lookup Actions

1. **getGalnetNews**
    - `query`: String.

     Retrieve current interstellar news from Galnet. Answers the question that lead to tool usage.

2. **trade_plotter**
    - `system`: String.
    - `station`: String.
    - `max_hops`: Integer.
    - `max_hop_distance`: Number.
    - `starting_capital`: Number.
    - `max_cargo`: Integer.
    - `requires_large_pad`: Boolean.

     Retrieve a trade route from the trade plotter.

3. **system_finder**
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

4. **station_finder**
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

## Miscellaneous Actions

1. **getVisuals**
    - `query`: String.

     Describe what's currently visible to the Commander. Answers the question that lead to tool usage.
