import { open, readdir, stat } from 'node:fs/promises';
import path from 'node:path';

const MAX_READ = 256 * 1024;
const MAX_BASELINE_SCAN = 8 * 1024 * 1024;

export function parseEdvrLine(line) {
  const match = /^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3}) UTC pid=(\d+) tid=\d+ (.*)$/.exec(line);
  if (!match) return null;
  const time = Date.parse(match[1].replace(' ', 'T') + 'Z');
  const fields = new Map(match[3].split(',').slice(1).map(field => {
    const split = field.indexOf('=');
    return [field.slice(0, split), field.slice(split + 1)];
  }));
  const kind = match[3].split(',')[0];
  const base = { pid: Number(match[2]), time, kind };
  if (kind === 'runtime') return { ...base, runtime: match[3].split(',')[1] };
  if (kind === 'natural_reference_space') return { ...base, frame: fields.get('type') };
  if (!['seat_reset', 'position_recentre'].includes(kind) || fields.get('ok') !== '1' ||
      (kind === 'seat_reset' && fields.get('result') !== '0')) return null;
  const pose = key => {
    const text = fields.get(key);
    if (!text || !/^-?\d+(?:\.\d+)?\/-?\d+(?:\.\d+)?\/-?\d+(?:\.\d+)?\/-?\d+(?:\.\d+)?$/.test(text)) return null;
    const values = text.split('/').map(Number);
    if (!values.every(Number.isFinite) || values.slice(0, 3).some(n => Math.abs(n) > 1000)) return null;
    const [x, y, z, angle] = values;
    const yaw = kind === 'seat_reset' ? angle * Math.PI / 180 : angle;
    return [Math.cos(yaw), 0, Math.sin(yaw), x, 0, 1, 0, y, -Math.sin(yaw), 0, Math.cos(yaw), z];
  };
  const from = pose('from'), to = pose('to');
  return from && to ? { ...base, from, to } : null;
}

async function readRange(file, position, length) {
  const handle = await open(file, 'r');
  try {
    const buffer = Buffer.alloc(length);
    const { bytesRead } = await handle.read(buffer, 0, length, position);
    return { text: buffer.subarray(0, bytesRead).toString('utf8'), bytesRead };
  } finally { await handle.close(); }
}

// Logs are a prototype transport. Follow only one positively identified live EDVR process.
export function createEdvrLogAdapter({ probe, onOrigin, onStatus = () => {}, platform = process.platform,
  now = Date.now, intervalMs = 250, autoStart = true } = {}) {
  let state = null, stopped = false, busy = false, lastStatus, blockedKey;
  function status(message) { if (message !== lastStatus) { lastStatus = message; onStatus(message); } }
  function clear(message) {
    if (state) onOrigin(null, null);
    state = null;
    status(message);
  }
  function publish() {
    if (state?.current && !state.published) {
      if (onOrigin(state.key, state.current) !== false) state.published = true;
    }
  }
  async function poll() {
    if (stopped || busy || platform !== 'win32') return;
    busy = true;
    try {
      const result = await probe();
      if (stopped) return;
      const games = result.available ? result.processes.filter(game => game.modulesAvailable &&
        game.tools.includes('EDVR') && game.executablePath && Number.isFinite(game.startedAt)) : [];
      if (games.length !== 1 || result.processes.length !== 1) { clear('inactive: no unique verified EDVR process'); return; }
      const game = games[0];
      const folder = path.join(path.dirname(game.executablePath), 'edvr_logs');
      const names = (await readdir(folder)).filter(name =>
        new RegExp(`^edvr_openxr_\\d{8}_\\d{6}_\\d{3}_${game.pid}\\.log$`).test(name));
      const files = await Promise.all(names.map(async name => ({ file: path.join(folder, name), info: await stat(path.join(folder, name)) })));
      const selected = files.filter(item => item.info.isFile() && item.info.birthtimeMs >= game.startedAt - 5000)
        .sort((a, b) => b.info.birthtimeMs - a.info.birthtimeMs)[0];
      if (stopped) return;
      if (!selected) { clear('waiting: current EDVR log'); return; }
      const { file, info } = selected;
      const key = `${game.pid}:${game.startedAt}:${file}:${info.birthtimeMs}`;
      if (key === blockedKey) { status('inactive: session changed to unsupported coordinates'); return; }
      if (state?.key !== key || info.size < state.offset) {
        clear('waiting: verify current EDVR session header');
        const { text: header } = await readRange(file, 0, Math.min(info.size, MAX_READ));
        const records = header.split(/\r?\n/).map(parseEdvrLine).filter(record => record?.pid === game.pid && record.time >= game.startedAt - 5000);
        const runtime = records.filter(record => record.kind === 'runtime').at(-1)?.runtime;
        const frame = records.filter(record => record.kind === 'natural_reference_space').at(-1)?.frame;
        if (runtime !== 'SteamVR/OpenXR' || frame !== 'STAGE') {
          status('inactive: EDVR must confirm SteamVR/OpenXR and STAGE coordinates'); return;
        }
        let latest, end = info.size;
        // Performance records can bury the last reset. Scan backwards once, with a hard byte cap.
        while (!latest && end > Math.max(0, info.size - MAX_BASELINE_SCAN)) {
          const start = Math.max(0, end - MAX_READ);
          const tail = (await readRange(file, start, end - start)).text;
          if (stopped) return;
          const lines = tail.split(/\r?\n/);
          if (start) lines.shift();
          lines.pop(); // Partial records are not a trustworthy baseline.
          latest = lines.map(parseEdvrLine).filter(record => record?.pid === game.pid && record.to &&
            record.time >= game.startedAt - 5000 && record.time <= now() + 2000).at(-1);
          end = start;
        }
        if (stopped) return;
        state = { key, file, pid: game.pid, offset: info.size, carry: '', attachedAt: now(),
          current: latest?.to ?? null, lastTime: latest?.time ?? 0, published: false };
        publish();
        status('active: EDVR log attached; historical resets not replayed');
        return;
      }
      const length = info.size - state.offset;
      if (length > MAX_READ) { clear('paused: EDVR log advanced too far; rebaseline next poll'); return; }
      if (length) {
        const chunk = await readRange(file, state.offset, length);
        if (stopped) return;
        state.offset += chunk.bytesRead;
        const lines = (state.carry + chunk.text).split(/\r?\n/);
        state.carry = lines.pop();
        if (state.carry.length > 16384) { clear('paused: oversized EDVR log line'); return; }
        for (const line of lines) {
          const record = parseEdvrLine(line);
          if (!record || record.pid !== state.pid) continue;
          if (record.kind === 'natural_reference_space' && record.frame !== 'STAGE') {
            blockedKey = state.key;
            clear('inactive: EDVR coordinate frame changed'); return;
          }
          if (!record.to || record.time < state.attachedAt || record.time < state.lastTime ||
              record.time > now() + 2000 || now() - record.time > 10000) continue;
          if (!state.current) {
            state.current = record.from;
            publish();
            if (!state.published) continue;
          }
          state.current = record.to;
          state.lastTime = record.time;
          state.published = false;
        }
      }
      publish();
    } catch (error) {
      if (!stopped) clear(`inactive: EDVR log unavailable (${error.code || error.message})`);
    } finally { busy = false; }
  }
  const timer = autoStart && platform === 'win32' ? setInterval(() => { void poll(); }, intervalMs) : null;
  timer?.unref();
  if (autoStart) void poll();
  return { poll, stop() { stopped = true; if (timer) clearInterval(timer); state = null; } };
}
