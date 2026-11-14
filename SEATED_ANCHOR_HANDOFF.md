# Seated Anchor

Keeps the overlay fixed relative to the cockpit when the player recenters.
Uses the paired [electron-vr branch](https://github.com/lag0matic/electron-vr/tree/codex/seated-vr-anchor).

## Changes

| Files | Change | Reason |
| --- | --- | --- |
| `src/lib/Config.py`, UI config services, general/advanced settings templates | Add the saved `seated` anchor option. | Select cockpit-relative placement alongside head/world modes. |
| `electron/vr-placement.js` | Retain the existing offset and tilt/yaw calculations. | Preserve saved placement settings. |
| `electron/vr-seat-controller.js` | Convert the configured pose to seat coordinates; apply EDVR's origin when available. | Use the same cockpit-local placement with or without EDVR. |
| `electron/vr-overlay-updates.js`, `electron/index.js` | Update placement, size and curvature in place; serialize overlay lifecycle changes. | Offset edits must not recreate or reset the anchor. |
| `electron/vr-game-probe.js` | Report the running game's executable path alongside loaded-module evidence. | Identify the active EDVR session and its log directory. |
| `electron/vr-edvr-log-adapter.js` | Read successful origin changes from the current EDVR log. | EDVR recenters its own OpenXR space without moving SteamVR's seated origin. |

## Placement

`W` is the configured world pose. `B` is SteamVR's seated-to-standing transform,
captured when entering seated mode. The shared seat-local pose is:

```text
S = inverse(B) * W
Stock Elite: send S using electron-vr mode 'seat'
EDVR: send E * S using mode 'world', where E is EDVR's current STAGE origin
```

Offset edits update W without replacing B. Both paths therefore retain the same
cockpit-local position and rotation. Native curvature is unchanged.

## EDVR Adapter

Activates only for one verified running EDVR process whose current log confirms
`SteamVR/OpenXR` and `STAGE`. Existing records establish the current origin;
historical recenter sequences are not replayed. Fresh successful records update
the pose. The reader polls every 250 ms, buffers partial lines, and stops with the
overlay. Unsupported frames, missing logs or loss of the process disable it.

No EDVR-specific code, observer or IPC was added to electron-vr.

## Verification

55 Electron tests pass. Cockpit checks passed for stock Elite and EDVR, including
offset edits, looking up/down and recentering while turned 90 degrees. The
corrected starting placement was checked with a temporary border, now removed.

Tests: `test/electron/vr-seat-controller.test.js`, `vr-edvr-log-adapter.test.js`,
`vr-placement.test.js` and `vr-overlay-updates.test.js`.
