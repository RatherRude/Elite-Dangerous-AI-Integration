function validateBasis(transform) {
  const m = transform?.matrix;
  if (transform?.from !== 'seated' || transform?.to !== 'standing' ||
      !Array.isArray(m) || m.length !== 12 || !m.every(Number.isFinite)) {
    throw new Error('Seated anchoring requires an initialized OpenVR backend and matching electron-vr native addon.');
  }
  for (let r = 0; r < 3; r++) {
    for (let s = 0; s < 3; s++) {
      let dot = 0;
      for (let c = 0; c < 3; c++) dot += m[r * 4 + c] * m[s * 4 + c];
      if (Math.abs(dot - Number(r === s)) > 0.005) throw new Error('Invalid seated tracking-origin transform.');
    }
  }
  const determinant = m[0] * (m[5] * m[10] - m[6] * m[9]) -
    m[1] * (m[4] * m[10] - m[6] * m[8]) + m[2] * (m[4] * m[9] - m[5] * m[8]);
  if (Math.abs(determinant - 1) > 0.005) throw new Error('Invalid seated tracking-origin rotation.');
  return [...m];
}

function rotationQuaternion(m) {
  const trace = m[0] + m[5] + m[10];
  let x, y, z, w;
  if (trace > 0) {
    const s = Math.sqrt(trace + 1) * 2;
    w = s / 4; x = (m[9] - m[6]) / s; y = (m[2] - m[8]) / s; z = (m[4] - m[1]) / s;
  } else if (m[0] > m[5] && m[0] > m[10]) {
    const s = Math.sqrt(1 + m[0] - m[5] - m[10]) * 2;
    w = (m[9] - m[6]) / s; x = s / 4; y = (m[1] + m[4]) / s; z = (m[2] + m[8]) / s;
  } else if (m[5] > m[10]) {
    const s = Math.sqrt(1 + m[5] - m[0] - m[10]) * 2;
    w = (m[2] - m[8]) / s; x = (m[1] + m[4]) / s; y = s / 4; z = (m[6] + m[9]) / s;
  } else {
    const s = Math.sqrt(1 + m[10] - m[0] - m[5]) * 2;
    w = (m[4] - m[1]) / s; x = (m[2] + m[8]) / s; y = (m[6] + m[9]) / s; z = s / 4;
  }
  const length = Math.hypot(x, y, z, w);
  return { x: x / length, y: y / length, z: z / length, w: w / length };
}

function toSeatPlacement(world, basis) {
  const p = [world.position.x - basis[3], world.position.y - basis[7], world.position.z - basis[11]];
  const position = {};
  for (const [c, axis] of ['x', 'y', 'z'].entries()) {
    position[axis] = basis[c] * p[0] + basis[4 + c] * p[1] + basis[8 + c] * p[2];
  }
  const q = rotationQuaternion(basis);
  const a = { x: -q.x, y: -q.y, z: -q.z, w: q.w };
  const b = world.rotation;
  const rotation = {
    x: a.w * b.x + a.x * b.w + a.y * b.z - a.z * b.y,
    y: a.w * b.y - a.x * b.z + a.y * b.w + a.z * b.x,
    z: a.w * b.z + a.x * b.y - a.y * b.x + a.z * b.w,
    w: a.w * b.w - a.x * b.x - a.y * b.y - a.z * b.z,
  };
  return { mode: 'seat', position, rotation };
}

// COVAS offsets retain their legacy world convention; electron-vr receives seat-local coordinates.
export function createSeatController(overlay, anchor, placement) {
  let basis = null;
  let destroyed = false;
  const controller = {
    setConfiguredPlacement(nextAnchor, nextPlacement) {
      if (destroyed) return false;
      const nextBasis = nextAnchor === 'seated'
        ? basis ?? validateBasis(overlay.getTrackingOriginTransform?.('seated', 'standing')) : null;
      const nativePlacement = nextBasis ? toSeatPlacement(nextPlacement, nextBasis) : nextPlacement;
      if (!overlay.setPlacement(nativePlacement)) return false;
      basis = nextBasis;
      return true;
    },
    setSizeMeters: value => overlay.setSizeMeters(value),
    setCurvature: value => overlay.setCurvature(value),
    getRuntimeInfo: () => overlay.getRuntimeInfo(),
    getSelectedBackend: () => overlay.getSelectedBackend(),
    isInitialized: () => overlay.isInitialized(),
    destroy() {
      if (!destroyed) {
        destroyed = true;
        overlay.destroy();
      }
    },
  };
  if (!controller.setConfiguredPlacement(anchor, placement)) throw new Error('Could not initialize VR anchor placement.');
  return controller;
}
