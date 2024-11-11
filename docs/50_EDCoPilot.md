# EDCoPilot Integration

We are excited to work with Razzafrag on integrating **COVAS:NEXT** with **EDCoPilot**!
This currently has two benefits:
1) You can see the COVAS:NEXT dialogue in EDCoPilot Voice Activity
2) You can prevent both applications from talking over each other

## Show dialogue in EDCoPilot
With EDCoPilot installed, COVAS:NEXT will automatically add a new configuration option to enable EDCoPilot.
This option is enabled by default, so it should work without further modification.

## Preventing both applications from talking at the same time
By default, both EDCoPilot and COVAS:NEXT will react to certain events inside your game. 

We provide two different solutions:
1) Let COVAS:NEXT decide what, where and how to comment **(COVAS:NEXT Dominant Mode)**
  
2) Let EDCoPilot decide what, where and how to comment **(EDCoPilot Dominant Mode)**

### 1. COVAS:NEXT Dominant Mode 
This mode lets you talk to COVAS:NEXT as usual, while COVAS:NEXT use EDCoPilot as a source of additional information.

In order to mute EDCoPilot game commentary, you need to // TODO //

This will allow COVAS:NEXT to use information from EDCoPilot in its own responses*.

\* *At the time of writing the amount of information is limited, but this will change in the future*

### 2. EDCoPilot Dominant Mode

This mode also lets you talk to COVAS:NEXT, while certain game commentary is instead handled by EDCoPilot
   
In order to hand control over to EDCoPilot, you need to enable the `EDCoPilot-Dominant` setting inside of COVAS:NEXT.

This setting will mute COVAS:NEXT and instead send all text over to EDCoPilot, where some of it will be read and some of will be muted or replaced**.

\*\* *At the time of writing all game commentary is replaced by EDCoPilot*

## Future Plans
We aim to expand this functionality in the future.

- Let COVAS:NEXT access EDCoPilot UI contents.
- Add functionality to control the EDCoPilot UI using COVAS:NEXT commands.
- Add support for time sensitive messages (like Time Trails) to COVAS:NEXT.
- Make the integration more seemless.
