import assert from 'node:assert/strict';
import test from 'node:test';
import { assessRestart, buildVrDiagnostics, createFrameHealthTracker, createSceneTracker, gameEvidence } from '../../electron/vr-diagnostics.js';
import { createGameProbe, identifyVrModules, normalizeGameProbe } from '../../electron/vr-game-probe.js';
import { describeVrStatus } from '../../electron/vr-status.js';

const modules = [
  { name: 'openxr_loader.dll', path: 'C:\\Game\\openxr_loader.dll' },
  { name: 'virtualdesktop-openxr.dll', path: 'C:\\VD\\virtualdesktop-openxr.dll' },
  { name: 'd3d11.dll', product: 'EDVR Direct3D proxy' },
  { name: 'openvr_api.dll', product: 'OpenComposite' },
];
const probe = normalizeGameProbe([{ pid: 10, startedAt: '2026-10-27T12:00:00Z', modulesAvailable: true, modules }]);
const info = { openxrHostDetected: true, openxrHostProcessId: 10, openxrHostApplicationName: 'Elite Dangerous',
  openxrRuntimeName: 'SteamVR', openxrApiLayerEnabled: true,
  selectedBackend: 'openxr', openxrMode: 'api-layer', openxrProtocolVersion: 4 };

test('loaded module evidence overrides the configured default without claiming a session runtime query', () => {
  const summary = describeVrStatus({ readiness: 'ready', diagnostics: info }, { probe });
  assert.match(summary, /VDXR \(Virtual Desktop\) runtime module detected in the game/);
  assert.match(summary, /EDVR detected, OpenComposite detected/);
  assert.doesNotMatch(summary, /configured runtime: SteamVR/);
});

test('generic proxy filenames do not prove EDVR or OpenComposite are installed', () => {
  assert.deepEqual(identifyVrModules([{ name: 'd3d11.dll' }, { name: 'openvr_api.dll' }]).tools, []);
});

test('multiple loaded runtimes and another process do not produce an invented runtime attribution', () => {
  const ambiguous = normalizeGameProbe([{ pid: 10, modulesAvailable: true, modules: [...modules,
    { name: 'vrclient_x64.dll', path: 'C:\\SteamVR\\vrclient_x64.dll' }] }]);
  assert.equal(gameEvidence(info, ambiguous).runtime, null);
  assert.equal(gameEvidence({ ...info, openxrHostProcessId: 20 }, probe).runtime, null);
});

test('restart is required only for a known OpenXR process predating a successful integration change', () => {
  const changedAt = Date.parse('2026-10-27T12:01:00Z');
  assert.equal(assessRestart(info, probe, { changedAt, action: 'install' }), true);
  assert.equal(assessRestart(info, probe, { changedAt: changedAt - 120000, action: 'enable' }), false);
  assert.equal(assessRestart(info, probe, null), false);
  assert.equal(assessRestart(info, probe, { changedAt, action: 'uninstall' }), false);
  const unknown = normalizeGameProbe([{ pid: 10, startedAt: null, modules: [] }]);
  assert.equal(assessRestart(info, unknown, { changedAt, action: 'install' }), false);
  const openvr = normalizeGameProbe([{ pid: 10, startedAt: '2026-10-27T12:00:00Z', modules: [{ name: 'openvr_api.dll' }] }]);
  assert.equal(assessRestart({ openvrSceneProcessId: 10 }, openvr, { changedAt, action: 'install' }), false);
  assert.equal(assessRestart({ openvrSceneProcessId: 10 }, probe, { changedAt, action: 'install' }), false);
});

test('no game, access failure, and partial module access remain distinguishable', async () => {
  assert.equal(normalizeGameProbe([]).running, false);
  const partial = normalizeGameProbe([{ pid: 10, startedAt: null, modulesAvailable: false }]);
  assert.equal(partial.running, true);
  assert.equal(partial.processes[0].modulesAvailable, false);
  const failed = createGameProbe({ platform: 'win32', run: async () => { throw new Error('access denied'); } });
  assert.equal((await failed()).available, false);
});

test('process probe coalesces concurrent requests, caches briefly, and refreshes on demand', async () => {
  let calls = 0;
  let time = 10000;
  const gameProbe = createGameProbe({ platform: 'win32', now: () => time, run: async () => {
    calls++;
    return { stdout: '\uFEFF[]' };
  } });
  await Promise.all([gameProbe(), gameProbe()]);
  assert.equal(calls, 1);
  await gameProbe();
  assert.equal(calls, 1);
  time += 5001;
  await gameProbe();
  assert.equal(calls, 2);
  await gameProbe({ force: true });
  assert.equal(calls, 3);
});

test('health tracks disconnect, first delivery, stalled consumption, recovery, and a restarted game', () => {
  let time = 0;
  const sample = createFrameHealthTracker({ now: () => time });
  assert.equal(sample(info).state, 'disconnected');
  const connected = { ...info, openxrCompanionConnected: true, openxrSubmittedFrameSequence: 1, openxrConsumedFrameSequence: 0 };
  assert.equal(sample(connected).state, 'waiting');
  const delivered = { ...connected, openxrConsumedFrameSequence: 1 };
  assert.equal(sample(delivered).state, 'delivering');
  time = 11000;
  assert.equal(sample({ ...delivered, openxrSubmittedFrameSequence: 10 }).state, 'stalled');
  assert.equal(sample({ ...delivered, openxrSubmittedFrameSequence: 10, openxrConsumedFrameSequence: 10 }).state, 'delivering');
  assert.equal(sample({ ...connected, openxrHostProcessId: 20 }).state, 'waiting');
  assert.equal(sample({ selectedBackend: 'openvr' }).state, 'unavailable');
});

test('diagnostic snapshot contains versions, evidence, counters, and restart timing', () => {
  const snapshot = buildVrDiagnostics({ info: { ...info, openxrSubmittedFrameSequence: 20, openxrConsumedFrameSequence: 19 },
    probe, integrationChange: { action: 'install', changedAt: Date.parse('2026-10-27T12:01:00Z') },
    health: { state: 'delivering' }, appVersion: 'test-app', packageVersion: '0.8.8', sampledAt: 10000 });
  assert.equal(snapshot.electronVrVersion, '0.8.8');
  assert.equal(snapshot.appVersion, 'test-app');
  assert.equal(snapshot.integration.restartRequired, true);
  assert.equal(snapshot.overlay.consumedFrames, 19);
  assert.equal(snapshot.gameProcessProbe.processes[0].pid, 10);
  assert.doesNotThrow(() => JSON.stringify(snapshot));
});

test('live process evidence clears a cached Elite host after exit, but not on a failed probe', () => {
  const reconcile = createSceneTracker();
  const connected = { readiness: 'ready', diagnostics: { ...info, openxrCompanionConnected: true } };
  assert.equal(reconcile(connected, probe).readiness, 'ready');
  assert.equal(reconcile(connected, { available: false, processes: [] }).readiness, 'ready');
  const exited = reconcile(connected, normalizeGameProbe([]));
  assert.equal(exited.readiness, 'waiting-for-host');
  assert.equal(exited.diagnostics.openxrCompanionConnected, false);
  assert.equal(exited.diagnostics.staleSceneDiscarded, true);
  assert.equal(exited.launch.wouldWorkNow, false);
  assert.equal(connected.diagnostics.openxrCompanionConnected, true);
});

test('Linux uses game-reported runtime and session timing without host process visibility', () => {
  const host = { ...info, platform: 'linux', openxrHostRuntimeName: 'Monado',
    openxrHostRuntimeVersion: '25.0.0', openxrHostSessionStartedAtMs: 1000 };
  const hidden = { available: false, running: false, processes: [] };
  const summary = describeVrStatus({ readiness: 'ready', diagnostics: host }, { probe: hidden });
  assert.match(summary, /OpenXR \(Monado, reported by the game\)/);
  assert.doesNotMatch(summary, /configured runtime/);
  assert.equal(assessRestart(host, hidden, { action: 'install', changedAt: 2000 }), true);
  assert.equal(assessRestart(host, hidden, { action: 'install', changedAt: 500 }), false);
  const reconcile = createSceneTracker();
  assert.equal(reconcile({ diagnostics: host, readiness: 'ready' }, normalizeGameProbe([])).readiness, 'ready');
});

test('SteamVR host relay health measures accepted frames separately from game-side OpenXR consumption', () => {
  const sample = createFrameHealthTracker();
  const relay = { selectedBackend: 'openvr', openvrHostRelayAvailable: true, openvrSceneProcessId: 99 };
  assert.equal(sample(relay).state, 'disconnected');
  assert.equal(sample({ ...relay, openvrHostRelayConnected: true }).state, 'waiting');
  const delivered = sample({ ...relay, openvrHostRelayConnected: true,
    openvrSubmittedFrameSequence: 20, openvrConsumedFrameSequence: 20, openvrTextureSubmissionCount: 15 });
  assert.equal(delivered.state, 'delivering');
  assert.match(delivered.message, /SteamVR texture submissions: 15/);
});

test('a new OpenXR session reusing a container PID does not inherit stale frame health', () => {
  let time = 0;
  const sample = createFrameHealthTracker({ now: () => time });
  const sharedPid = { ...info, openxrHostProcessId: 2, openxrCompanionConnected: true,
    openxrSubmittedFrameSequence: 10, openxrConsumedFrameSequence: 9 };
  sample({ ...sharedPid, openxrHostSessionStartedAtMs: 1000 });
  time = 11000;
  assert.equal(sample({ ...sharedPid, openxrHostSessionStartedAtMs: 2000 }).state, 'delivering');
});
