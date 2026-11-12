# Seated Anchor: Maintainer Handoff

## Status and scope

This branch is for review by the COVAS:Next and electron-vr maintainers. It is
based on upstream `960be90a283c5d24b8c03ef7f3cb93ef4a486dcd`, without the fork's
older Gemini, Qwen, focus-mode, or streaming experiments.

The Windows prototype was tested in a separate COVAS profile with SteamVR,
Elite Dangerous, and EDVR v0.21.1. The tester confirmed visibility, native OpenVR
curvature, and recentering. Testing also exposed failures after offset edits;
the final build adds independent anchor polling and in-place overlay updates.
After that update, the tester reported that recentering worked.

**Linux/Proton recenter transport is not implemented or validated.** This is a
working Windows prototype, not a claim of cross-platform production readiness.
AI-assisted implementation; maintainer review is expected.

The feature requires the paired bridge branch:
[lag0matic/electron-vr: codex/seated-vr-anchor](https://github.com/lag0matic/electron-vr/tree/codex/seated-vr-anchor).
Start with its [technical handoff](https://github.com/lag0matic/electron-vr/blob/codex/seated-vr-anchor/SEATED_ANCHOR_HANDOFF.md).

## What changed here

| Area | Files | Purpose |
| --- | --- | --- |
| Setting | `src/lib/Config.py`, `ui/src/app/services/config.service.ts`, `ui/src/app/services/tauri.service.ts` | Accept `seated` alongside existing `head` and `world` modes. |
| Settings UI | General/advanced settings component HTML | Add Seated Anchor to the existing selector. |
| Placement | `electron/vr-placement.js` | Preserve existing World Locked translation for the initial seated pose. |
| Overlay lifecycle | `electron/index.js`, `electron/vr-overlay-updates.js` | Serialize lifecycle requests; update offsets, size, and curvature without replacing the native overlay. |
| Verification | `test/electron/vr-placement.test.js`, `test/electron/vr-overlay-updates.test.js` | Cover placement compatibility and in-place updates. |

There is no personality, LLM, TTS, STT, game-control, or EDVR binary change here.

## Coordinate contract

OpenVR Seated Anchor starts at the same room-space pose as World Locked with
the same saved settings. The existing translation is retained:

```text
x = horizontalOffset - 0.5
y = 1.4 + verticalOffset - (720 / 1280) / 2
z = -max(0.1, 2 + distanceOffset)
```

Existing tilt/yaw quaternion calculation is retained. The bridge applies
subsequent reference-space deltas to this configured pose. It must not treat
these coordinates as raw eye-relative offsets or add seated head height again.
That mismatch caused a visible initial-position regression during development.

Changing only offset/size/curvature values must reuse the existing controller.
Changing window mode or desktop-display settings may still rebuild the overlay.
Failed native property updates are reported rather than silently rebuilding and
losing the anchor. Lifecycle requests are serialized to prevent overlapping
initialization/destruction of the native singleton.

## Building the complete feature

The package manifests retain their upstream dependency versions. They do not
automatically install this unreleased bridge branch. A COVAS-only build against
the old native package is insufficient.

1. Build the paired electron-vr TypeScript package and platform native addon.
2. Supply that JS package and its matching native prebuilt assets to the COVAS
   Electron build. Follow the existing native unpacking rules.
3. For the Windows OpenXR-game/OpenVR-overlay combination, register the matching
   observer layer through the normal explicit integration setup. The game must
   restart after a layer update; restarting COVAS alone cannot replace a DLL
   already loaded in the game.
4. Select OpenVR for presentation during this prototype. The isolated test
   launcher used process-local `ELECTRON_VR_DISABLE_OPENXR=1`; the game still
   used OpenXR. Backend-selection UX/policy remains a maintainer decision.
5. Select Seated Anchor. Native OpenVR curvature remains available.

Do not silently register layers during package installation. Back up the prior
registration and retain a recovery path when testing an experimental native DLL.
If isolating `LOCALAPPDATA`, preserve access to the real SteamVR registry file
using process-local `VR_PATHREG_OVERRIDE`; hiding that file makes OpenVR appear
unavailable. No global environment change is needed.

Local standalone launchers, copied user settings, credentials, plugin data,
media, binaries, and recovery snapshots are intentionally not included here.

## Tests and live checks

Run the COVAS Electron tests from this repository root:

```powershell
$tests = Get-ChildItem test/electron -Filter '*.test.js' | Select-Object -ExpandProperty FullName
node --test @tests
```

The final local Electron suite passed 41 tests. The paired bridge has its own
native and JS tests. A hidden live OpenVR test removed all image-paint listeners
and still observed anchor polling, retained an edited offset, and verified timer
cleanup after destruction. This caught a gap that frame-driven tests missed.

Recommended manual checks:

1. Match the initial pose against an existing World Locked configuration.
2. Turn/lean without recentering: the overlay must not follow ordinary head motion.
3. Move/turn the seated position, then use the game's recenter control.
4. Edit offsets, size, and curvature; repeat recentering without restarting.
5. Repeat with a static avatar/image and no new chat or HUD content.
6. Restart COVAS, restart the game, and exercise missing/recovered tracking.
7. Confirm Head Locked and World Locked retain existing behavior.

## Limits and maintainer decisions

- The application-space observer currently uses Windows shared memory and a
  named mutex. Linux needs a transport adapter and actual native/Proton testing.
- It observes an OpenXR projection reference space relative to SteamVR STAGE,
  not arbitrary private camera matrices. A game can recenter without exposing
  that change through an observable reference space.
- EDVR v0.21.1 was inspected specifically. Later EDVR source uses different
  internal pose handling; do not assume compatibility from the game name alone.
- Native OpenVR games can use their runtime's seated-origin changes without the
  OpenXR observer. That does not expose application-private camera changes.
- The prototype's original standalone OpenXR renderer and direct OpenXR paths
  are not equivalent to the validated OpenVR-rendering/application-observer path.
  Their initial-placement semantics need review before advertising parity.
- No custom curved mesh or segmented-panel approximation was installed. The
  validated curvature comes from OpenVR's `SetOverlayCurvature`.

See [VR-Seated-Anchor.md](docs/advanced/VR-Seated-Anchor.md) for the user-facing
feature notes. The paired bridge handoff explains the transform and IPC details.
