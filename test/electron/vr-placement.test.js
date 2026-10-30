import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

import { getOverlayPlacement, normalizeVrPlacementOptions } from '../../electron/vr-placement.js';

const placementKeys = [
  'vrHorizontalOffset',
  'vrVerticalOffset',
  'vrDistanceOffset',
  'vrTiltDegrees',
  'vrYawDegrees',
];

test('preserves manually configured positions and angles beyond the slider ranges', () => {
  for (const key of placementKeys) {
    for (const value of [-1000, -180, -1.9, -0.75, 0, 1.5, 180, 1000]) {
      assert.equal(normalizeVrPlacementOptions({ [key]: value })[key], value);
    }
  }
});

test('defaults missing and invalid positions and angles to zero', () => {
  assert.deepEqual(normalizeVrPlacementOptions(), Object.fromEntries(placementKeys.map(key => [key, 0])));
  for (const key of placementKeys) {
    for (const value of [undefined, null, NaN, Infinity, -Infinity, '-1.5', true, {}, []]) {
      assert.equal(normalizeVrPlacementOptions({ [key]: value })[key], 0);
    }
  }
});

test('world-locked placement honors offsets below the former minimum', () => {
  const opts = normalizeVrPlacementOptions({ vrDistanceOffset: -1.5 });
  const placement = getOverlayPlacement('world', 0.9, 0, 0, opts.vrDistanceOffset);
  assert.equal(placement.mode, 'world');
  assert.equal(placement.position.z, -0.5);

  const nearest = getOverlayPlacement('world', 0.9, 0, 0, -1.9);
  assert.ok(Math.abs(nearest.position.z + 0.1) < 1e-12);
});

test('both anchors honor manually configured positions and angles outside UI limits', () => {
  const opts = normalizeVrPlacementOptions({
    vrHorizontalOffset: 12,
    vrVerticalOffset: -8,
    vrDistanceOffset: 20,
    vrTiltDegrees: 180,
    vrYawDegrees: 180,
  });
  for (const anchor of ['head', 'world']) {
    const placement = getOverlayPlacement(anchor, 0.9, opts.vrHorizontalOffset, opts.vrVerticalOffset,
      opts.vrDistanceOffset, opts.vrTiltDegrees, opts.vrYawDegrees);
    assert.equal(placement.position.x, anchor === 'world' ? 11.5 : 12);
    assert.equal(placement.position.y, anchor === 'world' ? 1.4 - 8 - (720 / 1280) / 2 : -8);
    assert.equal(placement.position.z, anchor === 'world' ? -22 : -21.1);
    assert.ok(Math.abs(placement.rotation.x) < 1e-12);
    assert.ok(Math.abs(placement.rotation.y) < 1e-12);
    assert.equal(placement.rotation.z, -1);
    assert.ok(Math.abs(placement.rotation.w) < 1e-12);
  }
});

test('both anchors retain the minimum physical distance and default placement', () => {
  for (const anchor of ['head', 'world']) {
    const placement = getOverlayPlacement(anchor, 0.9, 0, 0, -100);
    assert.equal(placement.position.z, -0.1);

    const defaultPlacement = getOverlayPlacement(anchor, 0.9);
    assert.equal(defaultPlacement.position.z, anchor === 'world' ? -2 : -1.1);
  }
});

test('extremely large finite angles produce finite rotations', () => {
  for (const angle of [-Number.MAX_VALUE, Number.MAX_VALUE]) {
    const opts = normalizeVrPlacementOptions({ vrTiltDegrees: angle, vrYawDegrees: angle });
    const placement = getOverlayPlacement('head', 0.9, 0, 0, 0, opts.vrTiltDegrees, opts.vrYawDegrees);
    assert.ok(Object.values(placement.rotation).every(Number.isFinite));
    assert.deepEqual(placement.rotation, getOverlayPlacement('head', 0.9, 0, 0, 0, angle % 360, angle % 360).rotation);
  }
});

for (const settings of ['general-settings', 'advanced-settings']) {
  test(`${settings} distance slider retains the expanded UI range and fine steps`, () => {
    const template = fs.readFileSync(new URL(
      `../../ui/src/app/components/${settings}/${settings}.component.html`, import.meta.url,
    ), 'utf8');
    const slider = template.match(/<mat-slider\b([^>]*)>\s*<input\b[^>]*\[ngModel\]="config\.overlay_vr_distance_offset"/);
    assert.ok(slider, 'VR distance slider must exist');
    const attributes = Object.fromEntries([...slider[1].matchAll(/(min|max|step)="([^"]+)"/g)]
      .map(([, name, value]) => [name, Number(value)]));
    assert.equal(attributes.min, -1.9);
    assert.equal(attributes.max, 1.5);
    assert.equal(attributes.step, 0.01);
    assert.equal(normalizeVrPlacementOptions({ vrDistanceOffset: attributes.min }).vrDistanceOffset, attributes.min);
    assert.equal(normalizeVrPlacementOptions({ vrDistanceOffset: attributes.max }).vrDistanceOffset, attributes.max);
  });
}
