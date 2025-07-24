const { contextBridge, ipcRenderer } = require('electron/renderer')

let stdoutCallback = null;
let stderrCallback = null;

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

contextBridge.exposeInMainWorld('electronAPI', {
  onStdout: (callback) => stdoutCallback = callback,
  onStderr: (callback) => stderrCallback = callback,
  invoke: (call, opts) => ipcRenderer.invoke(call, opts)
})