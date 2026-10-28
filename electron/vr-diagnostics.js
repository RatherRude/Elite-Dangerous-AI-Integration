export function gameEvidence(info, probe = {}) {
  const hostPid = info.openxrHostProcessId || info.openvrSceneProcessId || info.libovrHostProcessId;
  // Never attribute modules from another game's process to the connected host.
  const game = hostPid
    ? probe.processes?.find(process => process.pid === hostPid)
    : probe.processes?.length === 1 ? probe.processes[0] : undefined;
  const candidates = game?.runtimeCandidates || [];
  const openxr = info.openxrHostDetected || info.openxrCompanionConnected ||
    (!info.openvrSceneProcessId && game?.openxrLoaded);
  const relevant = candidates.map(candidate => openxr && candidate.name === 'Oculus/OVR'
    ? { ...candidate, name: 'Meta/Oculus' } : candidate);
  const runtime = relevant.length === 1 ? relevant[0] : null;
  const tools = new Set(game?.tools || []);
  if (/\bedvr\b/i.test(info.openxrHostApplicationName || '')) tools.add('EDVR');
  if (/opencomposite/i.test(info.openxrHostApplicationName || '')) tools.add('OpenComposite');
  return { game, runtime, tools: [...tools], openxr: Boolean(openxr) };
}

export function assessRestart(info, probe, integrationChange) {
  if (!integrationChange || !['install', 'enable'].includes(integrationChange.action)) return false;
  if ((info.openxrHostDetected || info.openxrCompanionConnected) && info.openxrHostSessionStartedAtMs > 0) {
    return info.openxrHostSessionStartedAtMs < integrationChange.changedAt;
  }
  const { game, openxr } = gameEvidence(info, probe);
  // A SteamVR/OpenVR game does not need our OpenXR layer. Unknown start time
  // or API is not sufficient evidence to ask the user to restart.
  if (!game?.startedAt || !openxr) return false;
  return game.startedAt < integrationChange.changedAt;
}

export function createSceneTracker() {
  const knownElitePids = new Set();
  return function reconcile(report, probe) {
    // Host and Flatpak PIDs can be from different namespaces. The authenticated
    // game-side discovery endpoint is authoritative on Linux.
    if (!probe.available || report.diagnostics.platform === 'linux') return report;
    for (const game of probe.processes || []) knownElitePids.add(game.pid);
    const alive = pid => probe.processes?.some(game => game.pid === pid);
    const info = { ...report.diagnostics };
    let stale = false;
    for (const [pidKey, nameKey, fields] of [
      ['openxrHostProcessId', 'openxrHostApplicationName', {
        openxrHostDetected: false, openxrCompanionConnected: false, openxrHostProcessId: 0,
        openxrHostApplicationName: '', openxrHostGraphicsApi: '',
        openxrSubmittedFrameSequence: 0, openxrConsumedFrameSequence: 0,
      }],
      ['openvrSceneProcessId', 'openvrSceneApplicationName', {
        openvrSceneProcessId: 0, openvrSceneApplicationName: '', openvrSceneApplicationKey: '',
      }],
      ['libovrHostProcessId', 'libovrHostApplicationName', {
        libovrHostDetected: false, libovrHostProcessId: 0, libovrHostApplicationName: '',
      }],
    ]) {
      const pid = info[pidKey];
      if (pid && (knownElitePids.has(pid) || /elite\s*dangerous/i.test(info[nameKey] || '')) && !alive(pid)) {
        Object.assign(info, fields);
        stale = true;
      }
    }
    if (!stale) return report;
    info.staleSceneDiscarded = true;
    const waiting = info.selectedBackend === 'openxr' && info.openxrMode === 'api-layer' &&
      info.openxrApiLayerEnabled && report.readiness !== 'setup-required' &&
      !info.openxrHostDetected && !info.openxrCompanionConnected;
    return { ...report, diagnostics: info, ...(waiting ? {
      readiness: 'waiting-for-host',
      launch: { ...report.launch, verdict: 'action-required', wouldWorkNow: false, canStartNow: true,
        message: 'VR support is listening for a game scene.', requiredActions: ['start-openxr-app'] },
    } : {}) };
  };
}

export function createFrameHealthTracker({ now = Date.now } = {}) {
  let previous;
  return function sample(info, { overlayInitialized = false } = {}) {
    const relay = info.selectedBackend === 'openvr' && (info.openvrHostRelayActive || info.openvrHostRelayAvailable);
    if (!relay && (info.selectedBackend !== 'openxr' || info.openxrMode !== 'api-layer')) {
      previous = undefined;
      return { state: 'unavailable', message: overlayInitialized
        ? 'Overlay initialized. Frame-delivery counters are not available for this overlay path.'
        : 'Overlay is not initialized. Frame-delivery counters are not available for this overlay path.' };
    }
    const connected = relay ? info.openvrHostRelayConnected : info.openxrCompanionConnected;
    if (!connected) {
      previous = undefined;
      return { state: 'disconnected', message: relay ? (info.openvrSceneProcessId
        ? 'SteamVR scene detected. Connecting to the host overlay companion.'
        : 'Host overlay disconnected. Waiting for SteamVR or a game scene.') : info.openxrHostDetected
        ? 'Game scene detected. Overlay is not connected yet.'
        : 'Overlay is listening for a game scene.' };
    }
    const time = now();
    const submitted = Number((relay ? info.openvrSubmittedFrameSequence : info.openxrSubmittedFrameSequence) || 0);
    const consumed = Number((relay ? info.openvrConsumedFrameSequence : info.openxrConsumedFrameSequence) || 0);
    const key = relay ? `openvr:${info.openvrSceneProcessId}`
      : `openxr:${info.openxrHostProcessId}:${info.openxrProtocolVersion}:${info.openxrHostSessionStartedAtMs || 0}`;
    if (!previous || previous.key !== key || consumed < previous.consumed || submitted < previous.submitted) {
      previous = { key, consumed, submitted, changedAt: time };
    } else {
      if (consumed > previous.consumed) previous.changedAt = time;
      previous.consumed = consumed;
      previous.submitted = submitted;
    }
    if (consumed === 0) return { state: 'waiting', message: relay
      ? 'Host overlay connected. Waiting for the companion to acknowledge its first frame.'
      : 'Overlay connected. Waiting for the game to consume its first frame.' };
    if (submitted > consumed && time - previous.changedAt >= 10000) {
      return { state: 'stalled', message: relay
        ? 'Host overlay connected, but the companion has not acknowledged newer frames for at least 10 seconds.'
        : 'Overlay connected, but the game has not consumed newer frames for at least 10 seconds.' };
    }
    return { state: 'delivering', message: relay
      ? `Host companion received overlay frames. SteamVR texture submissions: ${info.openvrTextureSubmissionCount || 0}.`
      : 'The game has consumed overlay frames. This does not confirm visible content in the headset.' };
  };
}

export function buildVrDiagnostics({ info, probe, integrationChange, health, appVersion, packageVersion, sampledAt = Date.now() }) {
  return {
    schemaVersion: 1,
    sampledAt: new Date(sampledAt).toISOString(),
    appVersion,
    electronVrVersion: packageVersion,
    platform: info.platform,
    probeMode: info.probeMode,
    selectedBackend: info.selectedBackend,
    openxrMode: info.openxrMode,
    configuredOpenxrRuntime: info.openxrRuntimeName || null,
    gameProcessProbe: probe,
    scene: {
      openxrHostDetected: Boolean(info.openxrHostDetected),
      openxrHostProcessId: info.openxrHostProcessId || 0,
      openxrHostApplicationName: info.openxrHostApplicationName || '',
      openxrHostRuntimeName: info.openxrHostRuntimeName || '',
      openxrHostRuntimeVersion: info.openxrHostRuntimeVersion || '',
      openxrHostSessionStartedAtMs: info.openxrHostSessionStartedAtMs || 0,
      openvrSceneProcessId: info.openvrSceneProcessId || 0,
      openvrSceneApplicationName: info.openvrSceneApplicationName || '',
      libovrHostDetected: Boolean(info.libovrHostDetected),
      libovrHostProcessId: info.libovrHostProcessId || 0,
      libovrHostApplicationName: info.libovrHostApplicationName || '',
      staleSceneDiscarded: Boolean(info.staleSceneDiscarded),
    },
    integration: {
      installed: info.openxrApiLayerInstalled,
      enabled: info.openxrApiLayerEnabled,
      lastChange: integrationChange || null,
      restartRequired: assessRestart(info, probe, integrationChange),
    },
    overlay: {
      companionConnected: Boolean(info.openxrCompanionConnected),
      protocolVersion: info.openxrProtocolVersion,
      submittedFrames: info.openxrSubmittedFrameSequence,
      consumedFrames: info.openxrConsumedFrameSequence,
      openvrHostRelayAvailable: Boolean(info.openvrHostRelayAvailable),
      openvrHostRelayActive: Boolean(info.openvrHostRelayActive),
      openvrHostRelayConnected: Boolean(info.openvrHostRelayConnected),
      openvrSubmittedFrames: info.openvrSubmittedFrameSequence || 0,
      openvrConsumedFrames: info.openvrConsumedFrameSequence || 0,
      openvrTextureSubmissions: info.openvrTextureSubmissionCount || 0,
      health,
    },
  };
}
