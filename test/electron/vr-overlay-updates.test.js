import test from 'node:test';
import assert from 'node:assert/strict';
import { updateExistingVrOverlay } from '../../electron/vr-overlay-updates.js';

const options = { mode: 'both', screenId: 2, vrAnchor: 'seated', vrSizeMeters: 1.5,
  vrCurvature: 0.32, vrHorizontalOffset: -0.2, vrVerticalOffset: 0.15,
  vrDistanceOffset: -0.42, vrTiltDegrees: 5, vrYawDegrees: 0 };
test('offset edits update the existing controller without replacing its anchor', () => {
  const calls = [];
  const controller = { setConfiguredPlacement: (anchor, value) => { calls.push({ anchor, ...value }); return true; },
    destroy: () => assert.fail('must not destroy the overlay') };
  assert.equal(updateExistingVrOverlay({ controller }, options, { ...options, vrHorizontalOffset: 0.25 }), true);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].anchor, 'seated');
  assert.equal(calls[0].mode, 'world');
  assert.equal(calls[0].position.x, -0.25);
});
test('identical requests retain the controller without resetting any property', () => {
  assert.equal(updateExistingVrOverlay({ controller: {} }, options, { ...options }), true);
});
test('native curvature and size are changed in place', () => {
  const calls = [];
  const controller = { setCurvature: n => { calls.push(['curve', n]); return true; },
    setSizeMeters: n => { calls.push(['size', n]); return true; } };
  assert.equal(updateExistingVrOverlay({ controller }, options, { ...options, vrCurvature: 0.4, vrSizeMeters: 2 }), true);
  assert.deepEqual(calls, [['size', 2], ['curve', 0.4]]);
});
test('window or backend changes still require normal reconstruction', () => {
  for (const change of [{ mode: 'vr' }, { screenId: 3 }]) {
    assert.equal(updateExistingVrOverlay({ controller: {} }, options, { ...options, ...change }), false);
  }
  assert.equal(updateExistingVrOverlay({ controller: {}, cleanedUp: true }, options, options), false);
});
test('failed native updates report failure instead of silently replacing the overlay', () => {
  assert.throws(() => updateExistingVrOverlay({ controller: { setConfiguredPlacement: () => false } }, options,
    { ...options, vrHorizontalOffset: 0.1 }), /placement/);
});
