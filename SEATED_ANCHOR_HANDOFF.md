# Seated Anchor: COVAS Maintainer Handoff

## Scope and Status

Based on upstream `960be90a283c5d24b8c03ef7f3cb93ef4a486dcd`, without the fork's
older model, focus-mode, and streaming experiments. AI-assisted implementation;
maintainer review expected. 

Requires the matching [electron-vr branch](https://github.com/lag0matic/electron-vr/tree/codex/seated-vr-anchor)
and its [technical handoff](https://github.com/lag0matic/electron-vr/blob/codex/seated-vr-anchor/SEATED_ANCHOR_HANDOFF.md).
Coordinate matching JavaScript/native prebuilts before merging/distributing.
There is no dependency-version or lockfile churn in this proposal.

Luca approved generic `seat` coordinates in electron-vr. The app retains the
saved setting `seated`, but sends raw `seat` placement to the bridge after its
own conversion. No game-specific code is needed in electron-vr.

## Two Frames, Without Two Observers

World Locked uses SteamVR's standing origin. Stock Elite's normal recenter moves
SteamVR's seated origin. They are distinct reference frames, so standing-world
placement does not automatically follow the cockpit. This is not an EDVR-only
behavior. Native seated placement lets SteamVR perform the recenter movement.

Stock testing verified the original OpenVR DLL with EDVR absent. Normal recenter
changed the seated-to-standing matrix by 0.0678 metres and -60.7388 degrees yaw;
ordinary head movement changed none of its twelve elements. The tester confirmed
the previous native-only prototype worked in stock Elite, including offset edits.
The simplified implementation in this revision still needs live regression testing.

## Coordinate Contract

Keep the existing configured world pose, including tilt/yaw:

```text
x = horizontalOffset - 0.5
y = 1.4 + verticalOffset - (720 / 1280) / 2
z = -max(0.1, 2 + distanceOffset)
```

On entering Seated Anchor, capture seated-to-standing transform B once. Convert
the configured world pose W to seat-local pose S = inverse(B) * W. Send S with
`mode: 'seat'`; initial visual position is unchanged. SteamVR then updates the
effective world placement as its seated origin changes, independently of paints.

Retain B during position/angle edits. Re-sampling B on every edit would reset the
anchor and reproduce the original bug. Leaving seated mode clears B after a
successful placement; reentering captures the then-current origin. Recreating an
overlay establishes a new basis. Head/world policies are unchanged.

There is no timer, head-pose inference, paid vision call, input interception,
EDVR observer, shared-memory transport, or OpenXR layer change in the net proposal.
The bridge retains native OpenVR curvature.

## Files and Ownership

- `src/lib/Config.py` and UI config services: accept the app setting `seated`.
- General/advanced settings templates: offer Seated Anchor alongside head/world.
- `electron/vr-placement.js`: keep legacy configuration-space position/rotation.
- `electron/vr-seat-controller.js`: validate/capture B, convert poses, retain basis.
- `electron/vr-overlay-updates.js`: apply position/size/curvature changes in place.
- `electron/index.js`: wrap initialized overlays, clean up failures, serialize lifecycle requests.
- `test/electron/vr-seat-controller.test.js`: conversion, invalid origins, mode changes, basis retention and failed updates.
- Existing placement/lifecycle tests: compatibility and no controller replacement on edits.

No personality, LLM, TTS, STT, or game-control changes are included.

## Limits and Validation

The paired bridge supports seat coordinates on direct OpenVR. OpenXR rendering,
macOS backends, and Linux host relay explicitly reject them; COVAS reports missing
origin support rather than pretending to anchor correctly. Native Linux OpenVR
uses the same API but has not been physically tested. No Linux observer transport
is necessary for stock Elite's demonstrated signal; host relay is separate work.

Games that recenter only their private camera may not expose a seated-origin
change. This feature follows the runtime, not arbitrary game cameras.

Automated checks cover arbitrary origin rotations/translations, unchanged initial
world pose, native seat conversion, offset edits retaining B, failed updates,
head/world pass-through, fresh basis on reentry, and cleanup. Run all tests under
`test/electron` and build the paired bridge/native addon.

This revision passes all 46 Electron tests and the main-process syntax check.
The paired bridge passes its Windows native/TypeScript builds, 38 selected JS
tests, and an invisible SteamVR API check for raw seat placement, origin inversion,
head/world/seat switches, and native curvature. Visible cockpit behavior for the
refactor still needs the live check below; Linux remains untested physically.

Live checks before rollout: static image; ordinary head motion; recenter; offset
edits then recenter; curvature; head/world/seat switching; overlay and game restart.
Use the isolated app/profile. No OpenXR layer swap or EDVR observer is needed.
Earlier experimental observers remain only in branch history, not the base diff.
