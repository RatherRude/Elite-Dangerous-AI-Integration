/** Bounded renderer teardown. Kept independent of Electron for focused testing. */
export function installWindowCloseHandshake(window, ipc, beforeClose, timeoutMillis = 6000) {
  window.once('close', (event) => {
    event.preventDefault();
    let finished = false;
    const cleanup = () => {
      clearTimeout(timeout);
      ipc.removeHandler('window-close-ready');
    };
    const finish = () => {
      if (finished) return;
      finished = true;
      cleanup();
      if (!window.isDestroyed()) window.close();
    };
    const timeout = setTimeout(finish, timeoutMillis);
    ipc.handle('window-close-ready', (event) => {
      if (event.sender === window.webContents) finish();
    });
    window.once('closed', cleanup);
    beforeClose();
    window.webContents.send('window-close');
  });
}
