# Seated VR Anchor

Maintainers: start with the [paired-repository handoff](../../SEATED_ANCHOR_HANDOFF.md)
for implementation details, dependencies, verified behavior, and Linux gaps.

The VR Anchor setting offers Head Locked, World Locked, and Seated Anchor.
Existing configurations continue to use their saved mode; the default remains
Head Locked. Selecting Seated Anchor does not alter existing position settings.

On the OpenVR path, Seated Anchor starts at exactly the same room-space pose as
World Locked with the same settings. It then applies recenter deltas to that
pose. The existing horizontal/height translation and two-metre distance baseline
are retained, so copying an existing profile does not reposition the overlay.

This feature requires the matching electron-vr seated-placement implementation
and native prebuilt packages. The COVAS changes alone are insufficient with the
previous bridge release; coordinate the dependency update with the bridge release
before merging or distributing this feature.

OpenVR follows changes in the runtime's seated origin. The Windows prototype can
also receive application-space poses from the matching OpenXR API layer when
SteamVR is the OpenXR runtime. Rendering and curvature remain native OpenVR;
the layer only observes the projection reference space relative to STAGE.
It does not alter the game's composition or reset SteamVR's tracking origin.
The Windows IPC adapter is implemented; a Linux adapter and Linux/Proton live
validation remain outstanding, so this bridge is not cross-platform PR-ready.

The standalone OpenXR API-layer rendering path captures a
stable seated pose and refreshes it on runtime reference-space changes or an
application projection-reference replacement. It is not tied to Elite, EDVR,
keyboard bindings, or vision services.

The observer requires an application projection space that actually moves on
recenter. Applications that bake their camera changes into pose/view maths may
not expose this information, even if older versions did. It is not inferred from
key presses, game-specific log strings, or ordinary head motion.
Automatic synchronization is not possible when a game changes only its internal
camera without exposing an origin/reference change. Direct OpenXR uses LOCAL
origin semantics. Runtime and game combinations need physical-headset testing.

## Verification

Automated checks cover placement offsets, preserved head/world modes, both
settings views, native anchor stability, effective-time recentering, yaw-only
orientation, reference replacement, and invalid-tracking recovery.

Before a live rollout, test in a separate profile and a controlled VR session:

1. Sit normally, select Seated Anchor, and position the overlay.
2. Turn, lean, and look up/down. The overlay must remain fixed and level.
3. Move the chair, recenter, and verify the overlay returns to the intended
   seated-relative position.
4. Adjust offsets without recentering; these must not move the anchor itself.
5. Switch to Head Locked and World Locked and verify their existing behavior.
6. Stop and restart the game/session, and verify a fresh anchor is established.

Do not install or register a test OpenXR layer over a working installation as
part of unit testing. The native registration test changes layer registration
and should only be run in an appropriately isolated test environment.
