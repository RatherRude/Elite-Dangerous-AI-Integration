const { contextBridge, ipcRenderer } = require('electron/renderer')

let stdoutCallback = null;
let stderrCallback = null;
let windowCloseCallback = [];

ipcRenderer.on('stdout', (_event, value) => {
  if (stdoutCallback) {
    stdoutCallback(value);
  } else {
    console.warn('No stdout callback set, received:', value);
  }
});
ipcRenderer.on('stderr', (_event, value) => {
  if (stderrCallback) {
    stderrCallback(value);
  } else {
    console.warn('No stderr callback set, received:', value);
  }
});
ipcRenderer.on('window-close', (e) => {
  windowCloseCallback.forEach(callback => callback(e));
});

contextBridge.exposeInMainWorld('electronAPI', {
  onStdout: (callback) => stdoutCallback = callback,
  onStderr: (callback) => stderrCallback = callback,
  onWindowClose: (callback) => windowCloseCallback.push(callback),
  confirmWindowClose: () => ipcRenderer.invoke('window-close-ready'),
  userAssets: {
    writeFile: (opts) => ipcRenderer.invoke('write_user_asset_file', opts),
    readFile: (opts) => ipcRenderer.invoke('read_user_asset_file', opts),
    listFiles: () => ipcRenderer.invoke('list_user_asset_files'),
    deleteFile: (opts) => ipcRenderer.invoke('delete_user_asset_file', opts),
  },
  invoke: (call, opts) => ipcRenderer.invoke(call, opts)
})
