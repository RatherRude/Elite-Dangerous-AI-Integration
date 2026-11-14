import test from 'node:test';
import assert from 'node:assert/strict';
import { createSeatController } from '../../electron/vr-seat-controller.js';
import { getOverlayPlacement } from '../../electron/vr-placement.js';

function matrix({ position: p, rotation: { x, y, z, w } }) {
  return [1 - 2 * (y*y + z*z), 2 * (x*y - z*w), 2 * (x*z + y*w), p.x,
    2 * (x*y + z*w), 1 - 2 * (x*x + z*z), 2 * (y*z - x*w), p.y,
    2 * (x*z - y*w), 2 * (y*z + x*w), 1 - 2 * (x*x + y*y), p.z];
}
function multiply(a, b) {
  return Array.from({ length: 12 }, (_, i) => {
    const r = Math.floor(i / 4), c = i % 4;
    return a[r*4] * b[c] + a[r*4+1] * b[4+c] + a[r*4+2] * b[8+c] + (c === 3 ? a[r*4+3] : 0);
  });
}
function close(actual, expected) {
  actual.forEach((n, i) => assert.ok(Math.abs(n - expected[i]) < 1e-10, `${i}: ${n} != ${expected[i]}`));
}
const pose = getOverlayPlacement('world', 1.5, 0.2, -0.3, 0.4, 17, 38);
const origin = (matrix) => ({ from: 'seated', to: 'standing', matrix });
function fake(basis) {
  return {
    calls: [], reads: 0, destroys: 0, succeeds: true,
    getTrackingOriginTransform(from, to) {
      assert.equal(from, 'seated'); assert.equal(to, 'standing'); this.reads++; return origin(basis);
    },
    setPlacement(value) { this.calls.push(value); return this.succeeds; },
    setSizeMeters: n => n, setCurvature: n => n,
    destroy() { this.destroys++; },
  };
}

test('seat conversion preserves world position and orientation for arbitrary origin rotations', () => {
  for (const [pitch, yaw] of [[0, 63], [27, -100], [180, 0], [0, 180], [90, 180], [0, 0]]) {
    const basis = matrix(getOverlayPlacement('world', 1, 2, -1, 0, pitch, yaw));
    const overlay = fake(basis);
    createSeatController(overlay, 'seated', pose);
    assert.equal(overlay.calls[0].mode, 'seat');
    close(multiply(basis, matrix(overlay.calls[0])), matrix(pose));
  }
});

test('offset edits retain the original conversion basis; runtime recenter needs no JS update', () => {
  const basis = matrix(getOverlayPlacement('world', 1, 2, -1, 0, 0, 63));
  const overlay = fake(basis);
  const controller = createSeatController(overlay, 'seated', pose);
  const changedOrigin = matrix(getOverlayPlacement('world', 1, -3, 1, 0, 0, -44));
  overlay.getTrackingOriginTransform = () => assert.fail('must not resample during offset edits');
  const edited = getOverlayPlacement('world', 1.5, 1, -0.3, 0.4, 5, 10);
  assert.equal(controller.setConfiguredPlacement('seated', edited), true);
  close(multiply(basis, matrix(overlay.calls[1])), matrix(edited));
  assert.notDeepEqual(multiply(changedOrigin, matrix(overlay.calls[1])), matrix(edited));
  assert.equal(overlay.calls.length, 2);
});

test('head/world modes pass through; reentering seat captures a fresh origin', () => {
  const basis = matrix(pose), overlay = fake(basis);
  const controller = createSeatController(overlay, 'world', pose);
  assert.equal(overlay.reads, 0);
  assert.equal(overlay.calls[0], pose);
  controller.setConfiguredPlacement('seated', pose);
  controller.setConfiguredPlacement('head', { ...pose, mode: 'head' });
  assert.equal(overlay.calls.at(-1).mode, 'head');
  controller.setConfiguredPlacement('seated', pose);
  assert.equal(overlay.reads, 2);
  assert.equal(controller.setSizeMeters(2), 2);
  assert.equal(controller.setCurvature(0.4), 0.4);
  controller.destroy(); controller.destroy();
  assert.equal(overlay.destroys, 1);
  assert.equal(controller.setConfiguredPlacement('seated', pose), false);
});

test('missing and invalid origins fail explicitly, with no fake identity fallback', () => {
  for (const transform of [null, origin([]), origin(Array(12).fill(0)), origin(Array(12).fill(NaN)),
    origin([-1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0])]) {
    const overlay = fake([]);
    overlay.getTrackingOriginTransform = () => transform;
    assert.throws(() => createSeatController(overlay, 'seated', pose), /seated|Seated/);
    assert.equal(overlay.calls.length, 0);
  }
  assert.throws(() => createSeatController({ setPlacement() {} }, 'seated', pose), /OpenVR/);
});

test('a failed placement does not commit a new basis or clear an existing one', () => {
  const overlay = fake(matrix(pose));
  const controller = createSeatController(overlay, 'world', pose);
  overlay.succeeds = false;
  assert.equal(controller.setConfiguredPlacement('seated', pose), false);
  overlay.succeeds = true;
  controller.setConfiguredPlacement('seated', pose);
  assert.equal(overlay.reads, 2);
  overlay.succeeds = false;
  controller.setConfiguredPlacement('world', pose);
  overlay.succeeds = true;
  controller.setConfiguredPlacement('seated', pose);
  assert.equal(overlay.reads, 2);
});

test('EDVR and stock use the same cockpit-local pose at startup and after offset edits', () => {
  const basis = matrix(getOverlayPlacement('world', 1, -0.8, 0.6, -0.3, 0, -24));
  const overlay = fake(basis);
  const controller = createSeatController(overlay, 'seated', pose);
  const stockLocal = matrix(overlay.calls.at(-1));
  close(multiply(basis, stockLocal), matrix(pose));
  const first = matrix(getOverlayPlacement('world', 1, 2, 1, 0, 0, 35));
  controller.setApplicationOrigin('edvr-session', first);
  assert.equal(overlay.calls.at(-1).mode, 'world');
  close(matrix(overlay.calls.at(-1)), multiply(first, stockLocal));
  // Different room origins must still use identical cockpit-local placement.
  assert.notDeepEqual(matrix(overlay.calls.at(-1)), matrix(pose));
  const delta = matrix(getOverlayPlacement('world', 1, 1, -1, 0, 0, 60));
  controller.setApplicationOrigin('edvr-session', multiply(delta, first));
  close(matrix(overlay.calls.at(-1)), multiply(multiply(delta, first), stockLocal));
  const edited = getOverlayPlacement('world', 1, -2, 3, 1, 15, -20);
  const stock = fake(basis);
  createSeatController(stock, 'seated', edited);
  const editedLocal = matrix(stock.calls.at(-1));
  controller.setConfiguredPlacement('seated', edited);
  close(matrix(overlay.calls.at(-1)), multiply(multiply(delta, first), editedLocal));
  assert.equal(overlay.reads, 1);
  controller.setConfiguredPlacement('head', { ...pose, mode: 'head' });
  controller.setApplicationOrigin('edvr-session', first);
  assert.equal(overlay.calls.at(-1).mode, 'head');
  controller.setConfiguredPlacement('seated', pose);
  close(matrix(overlay.calls.at(-1)), multiply(first, stockLocal));
  assert.equal(overlay.reads, 2);
  controller.setApplicationOrigin('new-session', first);
  close(matrix(overlay.calls.at(-1)), multiply(first, stockLocal));
  controller.setApplicationOrigin(null, null);
  assert.equal(overlay.calls.at(-1).mode, 'seat');
  close(matrix(overlay.calls.at(-1)), stockLocal);
  let stopped = 0;
  controller.attachAdapter(() => stopped++);
  controller.destroy(); controller.destroy();
  assert.equal(stopped, 1);
});
