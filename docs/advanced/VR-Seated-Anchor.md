# Seated VR Anchor

Select **Seated Anchor** to keep the overlay in the same cockpit-relative
position when recentering. Head Locked and World Locked are unchanged.

Stock Elite uses OpenVR's seated origin directly. EDVR uses the COVAS
[logfile adapter](VR-EDVR-Log-Adapter.md) because its recenter changes a separate
OpenXR origin. Both paths use the same seat-local placement and retain native
curvature. Offset edits do not recreate the overlay or reset its anchor.

Requires matching electron-vr JavaScript/native binaries with `seat` placement
and `getTrackingOriginTransform`. See [implementation changes](../../SEATED_ANCHOR_HANDOFF.md).

Cockpit checks passed with and without EDVR, including offset edits and recenters
while looking up/down or turned 90 degrees.
