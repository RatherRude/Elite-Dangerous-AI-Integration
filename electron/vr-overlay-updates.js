import { getOverlayPlacement } from './vr-placement.js';

export function updateExistingVrOverlay(overlay, previous, next) {
  if (!overlay?.controller || overlay.cleanedUp || !previous ||
      !['vr', 'both'].includes(next.mode) || next.mode !== previous.mode) return false;
  const keys = new Set([...Object.keys(previous), ...Object.keys(next)]);
  for (const key of keys) {
    if (!key.startsWith('vr') && previous[key] !== next[key]) return false;
  }
  const controller = overlay.controller;
  if (previous.vrSizeMeters !== next.vrSizeMeters && !controller.setSizeMeters(next.vrSizeMeters)) {
    throw new Error('Could not update VR overlay size.');
  }
  if (previous.vrCurvature !== next.vrCurvature && !controller.setCurvature(next.vrCurvature)) {
    throw new Error('Could not update VR overlay curvature.');
  }
  const placementKeys = ['vrAnchor', 'vrHorizontalOffset', 'vrVerticalOffset', 'vrDistanceOffset', 'vrTiltDegrees', 'vrYawDegrees'];
  if (placementKeys.some(key => previous[key] !== next[key]) && !controller.setPlacement(
      getOverlayPlacement(next.vrAnchor, next.vrSizeMeters, next.vrHorizontalOffset, next.vrVerticalOffset,
        next.vrDistanceOffset, next.vrTiltDegrees, next.vrYawDegrees))) {
    throw new Error('Could not update VR overlay placement.');
  }
  return true;
}
