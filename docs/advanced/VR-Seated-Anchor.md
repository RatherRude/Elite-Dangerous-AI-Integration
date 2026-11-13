# Seated VR Anchor

The VR Anchor setting offers Head Locked, World Locked, and Seated Anchor. Existing
profiles and the default Head Locked behavior are unchanged.

Seated Anchor follows the VR runtime's seated origin rather than its standing
room origin. With stock Elite on SteamVR, this means normal cockpit recentering
moves the overlay with the cockpit. Ordinary head motion does not move it.
EDVR is not required. Native OpenVR curvature is retained. EDVR's private OpenXR
recenter does not update SteamVR's seated origin and is not followed by this mode.

COVAS preserves the World Locked visual position on entry by converting the
configured pose into seat-local coordinates. Position/angle edits reuse that
conversion basis; size and curvature updates do not recreate the overlay.
Leaving/reentering seated mode or recreating the overlay establishes a fresh basis.

This requires matching electron-vr JavaScript and native binaries with the generic
`seat` mode and origin-transform getter. Direct OpenVR is supported; OpenXR rendering,
macOS backends, and Linux host relay are not. Native Linux OpenVR needs headset
validation. Games that only recenter an internal camera may not move the runtime origin.

The simplified standalone has passed the user's stock Elite recenter test.
A controlled EDVR test confirmed its private origin moves while SteamVR's does
not. Supporting that separate origin requires an additional optional adapter.
Test movement without recenter, recenter, offset edits, curvature, anchor-mode
switches, and game/overlay restart in an isolated profile.

See the [maintainer handoff](../../SEATED_ANCHOR_HANDOFF.md) for API boundaries,
coordinate maths, test evidence, and integration requirements. No observer, polling
timer, game modification, or OpenXR layer registration is needed for this path.
