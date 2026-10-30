import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { readFile, readdir } from 'node:fs/promises';

const execute = promisify(execFile);

// Inspect the running process, not files installed beside the game or the
// system's default runtime. Product metadata identifies renamed proxy DLLs.
const windowsProbe = `
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$games = @(Get-Process -Name EliteDangerous64 -ErrorAction SilentlyContinue)
$result = @($games | ForEach-Object {
  $game = $_
  $startedAt = $null
  try { $startedAt = $game.StartTime.ToUniversalTime().ToString('o') } catch {}
  $modulesAvailable = $true
  $modules = @()
  try {
    $modules = @($game.Modules | ForEach-Object {
      $module = $_
      $product = ''
      try { $product = $module.FileVersionInfo.ProductName + ' ' + $module.FileVersionInfo.FileDescription } catch {}
      @{ name = $module.ModuleName; path = $module.FileName; product = $product }
    })
  } catch { $modulesAvailable = $false }
  @{ pid = $game.Id; startedAt = $startedAt; modulesAvailable = $modulesAvailable; modules = $modules }
})
ConvertTo-Json -InputObject $result -Depth 5 -Compress
`;

export function identifyVrModules(modules = []) {
  const runtimeCandidates = [];
  const tools = [];
  let openxrLoaded = false;
  let openvrLoaded = false;
  for (const module of modules) {
    const name = (module.name || '').toLowerCase();
    const evidence = `${module.path || ''} ${module.product || ''}`;
    if (name === 'openxr_loader.dll' || /wineopenxr/i.test(name)) openxrLoaded = true;
    if (name === 'openvr_api.dll') openvrLoaded = true;
    let runtime;
    if (/virtualdesktop-openxr.*\.dll$/i.test(name)) runtime = 'VDXR (Virtual Desktop)';
    else if (/oculus.*openxr.*\.dll$/i.test(name)) runtime = 'Meta/Oculus OpenXR';
    else if (/libovrrt.*\.dll$/i.test(name)) runtime = 'Oculus/OVR';
    else if (/vrclient(_x64)?\.dll$/i.test(name) && /steamvr/i.test(evidence)) runtime = 'SteamVR';
    if (runtime) runtimeCandidates.push({ name: runtime, module: module.name, evidence: module.path });
    // A generic d3d11/openvr_api filename is not evidence of a proxy.
    if (/\bedvr\b/i.test(evidence)) tools.push('EDVR');
    if (/opencomposite/i.test(evidence)) tools.push('OpenComposite');
  }
  return { runtimeCandidates, tools: [...new Set(tools)], openxrLoaded, openvrLoaded };
}

export function normalizeGameProbe(games, checkedAt = Date.now()) {
  if (!Array.isArray(games)) throw new Error('Unexpected game process response');
  return {
    available: true,
    running: games.length > 0,
    checkedAt,
    processes: games.map(game => ({
      pid: Number(game.pid),
      startedAt: Number.isFinite(Date.parse(game.startedAt)) ? Date.parse(game.startedAt) : null,
      modulesAvailable: Boolean(game.modulesAvailable),
      ...identifyVrModules(game.modules),
    })),
  };
}

async function probeLinux() {
  const games = [];
  for (const entry of await readdir('/proc')) {
    if (!/^\d+$/.test(entry)) continue;
    try {
      const command = await readFile(`/proc/${entry}/cmdline`, 'utf8');
      const executable = command.split('\0')[0].split(/[\\/]/).pop();
      if (!/^EliteDangerous64\.exe$/i.test(executable || '')) continue;
      games.push({ pid: Number(entry), startedAt: null, modulesAvailable: false });
    } catch { /* A process may exit or belong to another user. */ }
  }
  const result = normalizeGameProbe(games);
  // A Flatpak may not see host/Steam processes in its PID namespace.
  if (process.env.FLATPAK_ID && !result.running) result.available = false;
  return result;
}

export function createGameProbe({ platform = process.platform, now = Date.now, run = execute } = {}) {
  let cached;
  let pending;
  return async function probe({ force = false } = {}) {
    if (pending) return pending;
    if (!force && cached && now() - cached.checkedAt < 5000) return cached;
    pending = (async () => {
      try {
        if (platform === 'win32') {
          const encoded = Buffer.from(windowsProbe, 'utf16le').toString('base64');
          const { stdout } = await run('powershell.exe', ['-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
            { windowsHide: true, timeout: 5000, maxBuffer: 2 * 1024 * 1024, encoding: 'utf8' });
          return normalizeGameProbe(JSON.parse(stdout.replace(/^\uFEFF/, '').trim()), now());
        }
        if (platform === 'linux') return await probeLinux();
        return { available: false, running: false, processes: [], checkedAt: now() };
      } catch (error) {
        return { available: false, running: false, processes: [], checkedAt: now(), error: error.message };
      }
    })();
    try { cached = await pending; return cached; } finally { pending = null; }
  };
}
