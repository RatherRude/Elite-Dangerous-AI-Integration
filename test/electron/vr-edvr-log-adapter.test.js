import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, appendFile, rm, stat } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { createEdvrLogAdapter, parseEdvrLine } from '../../electron/vr-edvr-log-adapter.js';

const stamp = time => new Date(time).toISOString().slice(0, 23).replace('T', ' ');
const line = (time, text, pid = 42) => `${stamp(time)} UTC pid=${pid} tid=17 ${text}\n`;
const reset = (time, from = '0/0/0/0', to = '1/2/3/90', extra = '') =>
  line(time, `seat_reset,n=2,from=${from},to=${to},result=0,ok=1${extra}`);

async function fixture(t, { frame = 'STAGE', runtime = 'SteamVR/OpenXR', tools = ['EDVR'] } = {}) {
  const root = await mkdtemp(path.join(os.tmpdir(), 'covas-edvr-'));
  t.after(async () => {
    assert.equal(path.dirname(root), path.resolve(os.tmpdir()));
    assert.ok(path.basename(root).startsWith('covas-edvr-'));
    await rm(root, { recursive: true, force: true });
  });
  await mkdir(path.join(root, 'edvr_logs'));
  const file = path.join(root, 'edvr_logs/edvr_openxr_20261113_120000_001_42.log');
  let time = Date.now();
  const startedAt = time - 1000;
  await writeFile(file, line(time - 100, `runtime,${runtime},1`) +
    line(time - 100, `natural_reference_space,type=${frame},reason=test`) + reset(time - 50));
  const calls = [], statuses = [];
  const result = { available: true, processes: [{ pid: 42, startedAt, tools,
    modulesAvailable: true, executablePath: path.join(root, 'EliteDangerous64.exe') }] };
  const adapter = createEdvrLogAdapter({ platform: 'win32', autoStart: false, probe: async () => result,
    now: () => time, onOrigin: (session, matrix) => { calls.push({ session, matrix }); return true; },
    onStatus: message => statuses.push(message) });
  t.after(() => adapter.stop());
  return { file, calls, statuses, adapter, result, advance() { time += 100; return time; } };
}

test('parses full EDVR poses in metres/degrees, and position-only recenter radians', () => {
  const parsed = parseEdvrLine(reset(Date.now()).trim());
  assert.deepEqual(parsed.to.slice(3, 8), [1, 0, 1, 0, 2]);
  assert.ok(Math.abs(parsed.to[2] - 1) < 1e-12);
  const positional = parseEdvrLine(line(Date.now(), 'position_recentre,ok=1,from=0/0/0/0,to=1/2/3/1.5708').trim());
  assert.ok(Math.abs(positional.to[2] - 1) < 1e-8);
  for (const text of [reset(Date.now()).replace('ok=1', 'ok=0'), reset(Date.now()).replace('result=0', 'result=-1'),
    reset(Date.now()).replace('1/2/3/90', 'NaN/2/3/90'), 'seat_reset,ok=1']) {
    assert.equal(parseEdvrLine(text.trim()), null);
  }
});

test('attachment seeds current origin once without replay; appends update only when complete', async t => {
  const f = await fixture(t);
  await f.adapter.poll();
  assert.equal(f.calls.length, 1);
  await f.adapter.poll();
  assert.equal(f.calls.length, 1);
  const fresh = reset(f.advance(), '1/2/3/90', '4/5/6/30');
  await appendFile(f.file, fresh.slice(0, -8));
  await f.adapter.poll();
  assert.equal(f.calls.length, 1);
  await appendFile(f.file, fresh.slice(-8));
  await f.adapter.poll();
  assert.equal(f.calls.length, 2);
  assert.equal(f.calls[1].matrix[3], 4);
  assert.equal(f.calls[1].session, f.calls[0].session);
});

test('ignores old entries, wrong PIDs, failures and future timestamps', async t => {
  const f = await fixture(t);
  await f.adapter.poll();
  const now = f.advance();
  await appendFile(f.file, reset(now - 60000) + reset(now).replace('pid=42', 'pid=43') +
    reset(now).replace('ok=1', 'ok=0') + reset(now + 60000));
  await f.adapter.poll();
  assert.equal(f.calls.length, 1);
});

test('only a unique live verified EDVR process with SteamVR/STAGE may activate', async t => {
  for (const options of [{ frame: 'LOCAL' }, { runtime: 'VDXR' }, { tools: [] }]) {
    const f = await fixture(t, options);
    await f.adapter.poll();
    assert.equal(f.calls.length, 0);
  }
  const f = await fixture(t);
  f.result.processes.push({ ...f.result.processes[0], pid: 43 });
  await f.adapter.poll();
  assert.equal(f.calls.length, 0);
});

test('game exit and frame changes clear compensation; stop prevents further updates', async t => {
  const f = await fixture(t);
  await f.adapter.poll();
  await appendFile(f.file, line(f.advance(), 'natural_reference_space,type=LOCAL,reason=fallback'));
  await f.adapter.poll();
  assert.equal(f.calls.at(-1).session, null);
  const disabledCount = f.calls.length;
  await f.adapter.poll();
  assert.equal(f.calls.length, disabledCount);
  f.result.processes = [];
  await f.adapter.poll();
  f.adapter.stop();
  const count = f.calls.length;
  await appendFile(f.file, reset(f.advance()));
  await f.adapter.poll();
  assert.equal(f.calls.length, count);
});

test('truncated logs rebaseline without replaying their resets', async t => {
  const f = await fixture(t);
  await f.adapter.poll();
  const time = f.advance();
  await writeFile(f.file, line(time, 'runtime,SteamVR/OpenXR,1') +
    line(time, 'natural_reference_space,type=STAGE,reason=test'));
  await f.adapter.poll();
  assert.equal(f.calls.at(-1).session, null);
  await appendFile(f.file, reset(f.advance(), '0/0/0/0', '7/8/9/0'));
  await f.adapter.poll();
  assert.equal(f.calls.at(-1).matrix[3], 7);
  assert.ok((await stat(f.file)).size > 0);
});

test('a rejected native application is retried without accumulating transforms', async t => {
  const f = await fixture(t);
  let calls = 0;
  const adapter = createEdvrLogAdapter({ platform: 'win32', autoStart: false, probe: async () => f.result,
    onOrigin: () => ++calls > 1 });
  t.after(() => adapter.stop());
  await adapter.poll();
  await adapter.poll();
  await adapter.poll();
  assert.equal(calls, 2);
});

test('baseline scan finds a reset buried under performance records without replaying it', async t => {
  const f = await fixture(t);
  await appendFile(f.file, 'performance,not_an_origin\n'.repeat(20000));
  await f.adapter.poll();
  assert.equal(f.calls.length, 1);
  assert.equal(f.calls[0].matrix[3], 1);
  await f.adapter.poll();
  assert.equal(f.calls.length, 1);
});
