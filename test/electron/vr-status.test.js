import assert from 'node:assert/strict';
import test from 'node:test';

import { describeVrStatus } from '../../electron/vr-status.js';

function report(overrides = {}, readiness = 'waiting-for-host', backend = 'openxr') {
  return {
    readiness,
    backend,
    summary: 'OpenXR integration is ready. Start or restart an OpenXR application.',
    diagnostics: {
      openxrApiLayerEnabled: true,
      openvrAvailable: true,
      openvrRuntimeInstalled: true,
      openxrRuntimeName: 'VirtualDesktopXR (Bundled)',
      openxrHostDetected: false,
      openxrCompanionConnected: false,
      openxrHostApplicationName: '',
      openvrSceneProcessId: 0,
      libovrHostDetected: false,
      ...overrides,
    },
  };
}

test('no game running waits for a scene without asking to restart a runtime', () => {
  assert.equal(
    describeVrStatus(report(), { eliteRunning: false, processCheckAvailable: true }),
    'OpenVR and OpenXR support are ready. Waiting for Elite Dangerous to start in VR.',
  );
});

test('a running game with no connected scene does not get an unproven restart instruction', () => {
  const summary = describeVrStatus(report(), { eliteRunning: true, processCheckAvailable: true });
  assert.match(summary, /Elite Dangerous is running, but no VR game scene has connected/);
  assert.match(summary, /Check that Elite launched in VR/);
  assert.doesNotMatch(summary, /restart/i);
  assert.doesNotMatch(summary, /restart.*runtime|DirectX/i);
});

test('SteamVR scene takes precedence over the default VDXR runtime', () => {
  const summary = describeVrStatus(report({
    openvrSceneProcessId: 1234,
    openvrSceneApplicationName: 'Elite Dangerous',
  }, 'ready', 'openvr'));
  assert.equal(summary, 'Elite Dangerous is running in SteamVR. Using the SteamVR/OpenVR overlay.');
});

test('a connected EDVR host shows the configured runtime and EDVR, not the graphics API', () => {
  const summary = describeVrStatus(report({
    openxrHostDetected: true,
    openxrCompanionConnected: true,
    openxrHostApplicationName: 'Elite Dangerous (EDVR)',
    openxrHostGraphicsApi: 'd3d11',
  }, 'ready'));
  assert.equal(summary, 'Connected to Elite Dangerous via OpenXR (configured runtime: VDXR (Virtual Desktop); game runtime not confirmed), EDVR detected.');
  assert.doesNotMatch(summary, /d3d11|DirectX/i);
});

test('an identified OpenComposite host and native Oculus host show their respective paths', () => {
  assert.match(describeVrStatus(report({
    openxrHostDetected: true,
    openxrHostApplicationName: 'Elite Dangerous (OpenComposite)',
    openxrRuntimeName: 'SteamVR/OpenXR',
  }, 'ready')), /configured runtime: SteamVR; game runtime not confirmed\), OpenComposite detected/);
  assert.match(describeVrStatus(report({
    libovrHostDetected: true,
    libovrHostApplicationName: 'EliteDangerous64.exe',
  }, 'unavailable')), /EliteDangerous64\.exe is using native Oculus\/OVR/);
});

test('a configured OpenComposite runtime is not mistaken for proof that Elite uses it', () => {
  const summary = describeVrStatus(report({ openvrRuntimePath: 'C:\\OpenComposite\\runtime' }),
    { eliteRunning: true, processCheckAvailable: true });
  assert.match(summary, /OpenComposite is configured as the OpenVR runtime/);
  assert.match(summary, /the game has not been identified as using it/);
});

test('without process visibility, a missing scene is not mistaken for a stopped game', () => {
  assert.equal(describeVrStatus(report(), { processCheckAvailable: false }),
    'OpenVR and OpenXR support are ready. Waiting for a VR game scene to connect.');
});
