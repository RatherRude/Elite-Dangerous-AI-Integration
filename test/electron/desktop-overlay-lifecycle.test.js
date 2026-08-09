import assert from 'node:assert/strict';
import test from 'node:test';

import {
  createDesktopOverlayLifecycle,
  normalizeDesktopOverlayScreen,
  selectOverlayDisplay,
} from '../../electron/desktop-overlay-lifecycle.js';

const primaryDisplay = {
  id: 1,
  bounds: { x: 0, y: 0, width: 1920, height: 1080 },
};
const secondaryDisplay = {
  id: 0,
  bounds: { x: 1920, y: 0, width: 2560, height: 1440 },
};

function createHarness(overrides = {}) {
  const calls = [];
  const overlayWindow = {
    isDestroyed: () => false,
    setBounds: bounds => calls.push(['electronBounds', bounds]),
    setIgnoreMouseEvents: enabled => calls.push(['clickThrough', enabled]),
    setAlwaysOnTop: (...args) => calls.push(['alwaysOnTop', ...args]),
  };
  const logger = {
    info: (...args) => calls.push(['info', ...args]),
    warn: (...args) => calls.push(['warn', ...args]),
  };
  const controller = {
    getCapabilities: () => ({ backend: 'x11', parentDiscovery: true }),
    getState: () => ({ parent: null }),
    setBounds: bounds => calls.push(['nativeBounds', bounds]),
    attachParent: query => {
      calls.push(['attach', query]);
      return null;
    },
    detachParent: () => calls.push(['detach']),
    useParentBounds: () => false,
    reapply: () => calls.push(['reapply']),
    close: () => calls.push(['close']),
    ...overrides.controller,
  };
  const lifecycle = createDesktopOverlayLifecycle({
    overlayWindow,
    nativeController: overrides.nativeController === null ? null : controller,
    options: {
      desktopTarget: 'elite-window',
      parentWindowName: 'Elite - Dangerous',
      alwaysOnTop: true,
      ...overrides.options,
    },
    getTargetDisplay: () => secondaryDisplay,
    getOverlayBounds: display => display.bounds,
    logger,
    setIntervalFn: () => ({ unref() {} }),
    clearIntervalFn: () => {},
  });
  return { calls, controller, lifecycle };
}

test('selectOverlayDisplay accepts display ID zero and falls back to primary', () => {
  const displays = [primaryDisplay, secondaryDisplay];
  assert.equal(selectOverlayDisplay(displays, primaryDisplay, 0), secondaryDisplay);
  assert.equal(selectOverlayDisplay(displays, primaryDisplay, 999), primaryDisplay);
  assert.equal(selectOverlayDisplay(displays, primaryDisplay, -1), primaryDisplay);
});

test('follow game selection enables tracking with primary-screen fallback', () => {
  assert.deepEqual(normalizeDesktopOverlayScreen(-2), {
    screenId: -1,
    desktopTarget: 'elite-window',
  });
  assert.deepEqual(normalizeDesktopOverlayScreen(0), {
    screenId: 0,
    desktopTarget: 'monitor',
  });
});

test('uses monitor bounds until a delayed Elite window appears', () => {
  let attempt = 0;
  const parent = {
    title: 'Elite - Dangerous (CLIENT)',
    className: 'EliteDangerous64',
    bounds: { x: 30, y: 40, width: 1600, height: 900 },
  };
  const { calls, lifecycle } = createHarness({
    controller: {
      attachParent: query => {
        calls.push(['attach', query]);
        attempt += 1;
        return attempt === 1 ? null : parent;
      },
      useParentBounds: () => true,
    },
  });

  lifecycle.refresh();
  assert.deepEqual(calls[0], ['nativeBounds', secondaryDisplay.bounds]);
  assert.equal(calls.filter(call => call[0] === 'attach').length, 1);

  lifecycle.refresh();
  assert.equal(calls.filter(call => call[0] === 'attach').length, 2);
  assert.equal(calls.filter(call => call[0] === 'info' && call[1].startsWith('Tracking Elite')).length, 1);
});

test('retries parent discovery after a transient lookup error', () => {
  let attempt = 0;
  const parent = {
    title: 'Elite - Dangerous',
    className: 'EliteDangerous64',
    bounds: { x: 30, y: 40, width: 1600, height: 900 },
  };
  const { calls, lifecycle } = createHarness({
    controller: {
      attachParent: () => {
        attempt += 1;
        if (attempt === 1) {
          throw new Error('temporary lookup failure');
        }
        return parent;
      },
      useParentBounds: () => true,
    },
  });

  lifecycle.refresh();
  lifecycle.refresh();

  assert.equal(attempt, 2);
  assert.equal(calls.filter(call => call[0] === 'warn' && call[1].startsWith('Elite window tracking failed')).length, 1);
  assert.equal(calls.filter(call => call[0] === 'info' && call[1].startsWith('Tracking Elite')).length, 1);
});

test('detaches a lost parent, applies monitor fallback, and attaches its replacement', () => {
  let parentPresent = true;
  const replacement = {
    title: 'Elite - Dangerous',
    className: 'EliteDangerous64',
    bounds: { x: 50, y: 60, width: 1280, height: 720 },
  };
  const { calls, lifecycle } = createHarness({
    controller: {
      getState: () => ({ parent: { title: 'old parent' } }),
      useParentBounds: () => {
        if (parentPresent) {
          parentPresent = false;
          return true;
        }
        return calls.some(call => call[0] === 'attach');
      },
      attachParent: query => {
        calls.push(['attach', query]);
        return replacement;
      },
    },
  });

  lifecycle.refresh();
  lifecycle.refresh();

  assert.equal(calls.filter(call => call[0] === 'detach').length, 1);
  assert.equal(calls.filter(call => call[0] === 'nativeBounds').length, 1);
  assert.equal(calls.filter(call => call[0] === 'attach').length, 1);
});

test('falls back to Electron policy when the native controller fails', () => {
  const { calls, lifecycle } = createHarness({
    controller: {
      getCapabilities: () => {
        throw new Error('native failure');
      },
    },
  });

  lifecycle.refresh();

  assert.equal(calls.filter(call => call[0] === 'close').length, 1);
  assert.deepEqual(calls.find(call => call[0] === 'electronBounds'), ['electronBounds', secondaryDisplay.bounds]);
  assert.deepEqual(calls.find(call => call[0] === 'clickThrough'), ['clickThrough', true]);
  assert.deepEqual(calls.find(call => call[0] === 'alwaysOnTop'), ['alwaysOnTop', true, 'screen-saver', 2]);
});
