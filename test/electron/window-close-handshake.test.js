import { EventEmitter } from 'node:events';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { installWindowCloseHandshake } from '../../electron/window-close-handshake.js';

function fixture(timeout = 1000) {
  const window = new EventEmitter();
  const handlers = new Map();
  const sent = [];
  let destroyed = false;
  window.webContents = { send: channel => sent.push(channel) };
  window.isDestroyed = () => destroyed;
  window.close = () => {
    const event = { prevented: false, preventDefault() { this.prevented = true; } };
    window.emit('close', event);
    if (!event.prevented) { destroyed = true; window.emit('closed'); }
  };
  const ipc = { handle: (name, handler) => handlers.set(name, handler), removeHandler: name => handlers.delete(name) };
  installWindowCloseHandshake(window, ipc, () => {}, timeout);
  return { window, handlers, sent };
}

test('waits for the owning renderer, ignores another window, and removes handlers', () => {
  const { window, handlers, sent } = fixture();
  window.close();
  assert.deepEqual(sent, ['window-close']);
  assert.equal(window.isDestroyed(), false);
  handlers.get('window-close-ready')({ sender: {} });
  assert.equal(window.isDestroyed(), false);
  handlers.get('window-close-ready')({ sender: window.webContents });
  assert.equal(window.isDestroyed(), true);
  assert.equal(handlers.size, 0);
});

test('closes after a bounded timeout if the renderer does not respond', async () => {
  const { window, handlers } = fixture(10);
  window.close();
  await new Promise(resolve => setTimeout(resolve, 30));
  assert.equal(window.isDestroyed(), true);
  assert.equal(handlers.size, 0);
});
