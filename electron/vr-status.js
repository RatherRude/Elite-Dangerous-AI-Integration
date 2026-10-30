import { gameEvidence } from './vr-diagnostics.js';

function openXrRuntimeLabel(info) {
  const name = info.openxrRuntimeName || '';
  if (/virtual\s*desktop|vdxr/i.test(name)) return 'VDXR (Virtual Desktop)';
  if (/steamvr/i.test(name)) return 'SteamVR';
  if (/oculus|meta quest|meta xr/i.test(name)) return 'Meta/Oculus';
  if (/wivrn/i.test(name)) return 'WiVRn';
  if (/monado/i.test(name)) return 'Monado';
  return name || 'an unspecified OpenXR runtime';
}

export function describeVrStatus(report, options = {}) {
  const { probe = {}, restartRequired = false } = options;
  const eliteRunning = options.eliteRunning ?? probe.running ?? false;
  const processCheckAvailable = options.processCheckAvailable ?? probe.available ?? false;
  const info = report.diagnostics;
  const evidence = gameEvidence(info, probe);
  const application = info.openxrHostApplicationName || '';
  const edvr = evidence.tools.includes('EDVR');
  const openComposite = evidence.tools.includes('OpenComposite');
  const gameName = application.replace(/\s*\((?:EDVR|OpenComposite)\)/gi, '').trim() || 'a VR game';
  const restart = restartRequired ? ' Restart Elite to load the integration changed after this game session started.' : '';

  if (info.libovrHostDetected && !info.openxrHostDetected && !info.openxrCompanionConnected && !info.openvrSceneProcessId) {
    return `${info.libovrHostApplicationName || 'A VR game'} is using native Oculus/OVR. COVAS:NEXT cannot show its overlay in that mode.`;
  }
  if (info.openxrHostDetected || info.openxrCompanionConnected) {
    const path = [
      info.openxrHostRuntimeName
        ? `OpenXR (${openXrRuntimeLabel({ openxrRuntimeName: info.openxrHostRuntimeName })}, reported by the game)`
        : evidence.runtime
        ? `OpenXR (${evidence.runtime.name} runtime module detected in the game)`
        : `OpenXR (configured runtime: ${openXrRuntimeLabel(info)}; game runtime not confirmed)`,
      ...(edvr ? ['EDVR detected'] : []),
      ...(openComposite ? ['OpenComposite detected'] : []),
    ].join(', ');
    return `${info.openxrCompanionConnected ? 'Connected to' : 'Detected'} ${gameName} via ${path}.${restart}`;
  }
  if (info.openvrSceneProcessId) {
    const name = info.openvrSceneApplicationName || info.openvrSceneApplicationKey || 'a VR game';
    return `${name} is running in SteamVR. Using the SteamVR/OpenVR overlay.`;
  }
  if (report.readiness === 'waiting-for-host') {
    const supportsOpenVr = info.openvrAvailable && info.openvrRuntimeInstalled;
    const support = supportsOpenVr ? 'OpenVR and OpenXR support are ready' : 'OpenXR support is ready';
    const configuredOpenComposite = /opencomposite/i.test(info.openvrRuntimePath || '')
      ? ' OpenComposite is configured as the OpenVR runtime; the game has not been identified as using it.'
      : '';
    if (eliteRunning) {
      const detected = evidence.runtime ? ` ${evidence.runtime.name} runtime module detected in Elite.` : '';
      const tools = evidence.tools.length ? ` ${evidence.tools.join(' and ')} detected in Elite.` : '';
      return `${support}. Elite Dangerous is running, but no VR game scene has connected.${detected}${tools}${restart || ' Check that Elite launched in VR.'}${configuredOpenComposite}`;
    }
    return processCheckAvailable
      ? `${support}. Waiting for Elite Dangerous to start in VR.${configuredOpenComposite}`
      : `${support}. Waiting for a VR game scene to connect.${configuredOpenComposite}`;
  }
  if (report.readiness === 'ready' && report.backend === 'openxr') {
    return `${openXrRuntimeLabel(info)} supports direct OpenXR overlays. Waiting for a VR game scene.`;
  }
  if (report.readiness === 'ready' && report.backend === 'openvr') {
    return 'SteamVR/OpenVR overlay support is ready. Waiting for a VR game scene.';
  }
  return report.summary;
}
