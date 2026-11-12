# Seated VR Anchor

The VR Anchor setting offers Head Locked, World Locked, and Seated Anchor.
Existing configurations continue to use their saved mode; the default remains
Head Locked. Selecting Seated Anchor does not alter existing position settings.

Seated offsets are measured from seated eye level rather than a room-floor
height. The default distance is two metres. Horizontal, vertical, distance,
tilt and yaw adjustments remain available.

This feature requires the matching electron-vr seated-placement implementation
and native prebuilt packages. The COVAS changes alone are insufficient with the
previous bridge release; coordinate the dependency update with the bridge release
before merging or distributing this feature.

OpenVR uses the runtime's seated origin. The OpenXR API-layer path captures a
stable seated pose and refreshes it on runtime reference-space changes or an
application projection-reference replacement. It is not tied to Elite, EDVR,
keyboard bindings, or vision services.

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
