export function normalizeVrPlacementOptions(opts = {}) {
  return Object.fromEntries([
    'vrHorizontalOffset',
    'vrVerticalOffset',
    'vrDistanceOffset',
    'vrTiltDegrees',
    'vrYawDegrees',
  ].map(key => [key, Number.isFinite(opts[key]) ? opts[key] : 0]));
}

function getOverlayRotation(tiltDegrees = 0, yawDegrees = 0) {
  const halfPitch = (tiltDegrees % 360) * Math.PI / 360;
  const halfYaw = (yawDegrees % 360) * Math.PI / 360;
  const sinPitch = Math.sin(halfPitch);
  const cosPitch = Math.cos(halfPitch);
  const sinYaw = Math.sin(halfYaw);
  const cosYaw = Math.cos(halfYaw);
  return {
    x: cosYaw * sinPitch,
    y: sinYaw * cosPitch,
    z: -sinYaw * sinPitch,
    w: cosYaw * cosPitch,
  };
}

export function getOverlayPlacement(vrAnchor, vrSizeMeters, horizontalOffset = 0, verticalOffset = 0, distanceOffset = 0, tiltDegrees = 0, yawDegrees = 0) {
  const rotation = getOverlayRotation(tiltDegrees, yawDegrees);
  if (vrAnchor === 'world') {
    const distance = Math.max(0.1, 2.0 + distanceOffset);
    const widthOffset = 0.5;
    const heightOffset = (720 / 1280) / 2;
    return {
      mode: 'world',
      position: { x: horizontalOffset - widthOffset, y: 1.4 + verticalOffset - heightOffset, z: -distance },
      rotation,
    };
  }
  const distance = Math.max(0.1, 1.1 + distanceOffset);
  return {
    mode: 'head',
    position: { x: horizontalOffset, y: verticalOffset, z: -distance },
    rotation,
  };
}
