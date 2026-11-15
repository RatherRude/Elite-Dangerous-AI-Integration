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

function inverse(m) {
  return Array.from({ length: 12 }, (_, i) => {
    const r = Math.floor(i / 4), c = i % 4;
    return c === 3 ? -(m[r] * m[3] + m[4+r] * m[7] + m[8+r] * m[11]) : m[c*4+r];
  });
}

function multiply(a, b) {
  return Array.from({ length: 12 }, (_, i) => {
    const r = Math.floor(i / 4), c = i % 4;
    return a[r*4] * b[c] + a[r*4+1] * b[4+c] + a[r*4+2] * b[8+c] + (c === 3 ? a[r*4+3] : 0);
  });
}

function transformPlacement(world, matrix, mode) {
  const p = [world.position.x, world.position.y, world.position.z];
  const position = {};
  for (const [r, axis] of ['x', 'y', 'z'].entries()) {
    position[axis] = matrix[r*4] * p[0] + matrix[r*4+1] * p[1] + matrix[r*4+2] * p[2] + matrix[r*4+3];
  }
  const a = rotationQuaternion(matrix);
  const b = world.rotation;
  const rotation = {
    x: a.w * b.x + a.x * b.w + a.y * b.z - a.z * b.y,
    y: a.w * b.y - a.x * b.z + a.y * b.w + a.z * b.x,
    z: a.w * b.z + a.x * b.y - a.y * b.x + a.z * b.w,
    w: a.w * b.w - a.x * b.x - a.y * b.y - a.z * b.z,
  };
  return { mode, position, rotation };
}

// COVAS offsets retain their legacy world convention; electron-vr receives seat-local coordinates.
export function createSeatController(overlay, anchor, placement) {
  let basis = null;
  let destroyed = false;
  let configuredAnchor, configuredPlacement, application = null;
  let stopAdapter;
  function nativePlacement(anchor, placement, seatBasis, app) {
    if (anchor !== 'seated') return placement;
    // Both paths place the same seat-local pose; only the seat-to-world origin differs.
    if (app) return transformPlacement(placement, multiply(app.current, inverse(seatBasis)), 'world');
    return transformPlacement(placement, inverse(seatBasis), 'seat');
  }
  const controller = {
    setConfiguredPlacement(nextAnchor, nextPlacement) {
      if (destroyed) return false;
      const nextBasis = nextAnchor === 'seated'
        ? basis ?? validateBasis(overlay.getTrackingOriginTransform?.('seated', 'standing')) : null;
      if (!overlay.setPlacement(nativePlacement(nextAnchor, nextPlacement, nextBasis, application))) return false;
      basis = nextBasis;
      configuredAnchor = nextAnchor;
      configuredPlacement = nextPlacement;
      return true;
    },
    setApplicationOrigin(session, matrix) {
      if (destroyed) return false;
      let next = null;
      if (session && matrix) {
        const current = validateBasis({ from: 'seated', to: 'standing', matrix });
        next = { session, current };
      }
      if (!overlay.setPlacement(nativePlacement(configuredAnchor, configuredPlacement, basis, next))) return false;
      application = next;
      return true;
    },
    attachAdapter(stop) { stopAdapter?.(); stopAdapter = stop; },
    setSizeMeters: value => overlay.setSizeMeters(value),
    setCurvature: value => overlay.setCurvature(value),
    getRuntimeInfo: () => overlay.getRuntimeInfo(),
    getSelectedBackend: () => overlay.getSelectedBackend(),
    isInitialized: () => overlay.isInitialized(),
    destroy() {
      if (!destroyed) {
        destroyed = true;
        stopAdapter?.();
        overlay.destroy();
      }
    },
  };
  if (!controller.setConfiguredPlacement(anchor, placement)) throw new Error('Could not initialize VR anchor placement.');
  return controller;
}
