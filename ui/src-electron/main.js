const { app, BrowserWindow, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const contextMenu = require('electron-context-menu');

contextMenu.default({
  showSpellCheck: false,
  showLearnSpelling: false,
  showSeparator: false,
  showLookUpSelection: false,
  showSearchWithGoogle: false,
  showCut: true,
  showCopy: true,
  showPaste: true,
  showSelectAll: false,
  showSaveImage: false,
  showSaveImageAs: false,
  showSaveVideo: false,
  showSaveVideoAs: false,
  showCopyImage: false,
  showCopyImageAddress: false,
  showCopyVideoAddress: false,
  showCopyLink: false,
  showSaveLinkAs: false,
  //showInspectElement: true,
  showServices: false,
  prepend: (defaultActions,parameters,browserWindow,event)=>[{
    click: (menuItem, window, event) => {
      if (window) {
        window.reload();
      }
    },
    label: 'Reload'
  }]
});

class BackendService {
  #currentProcess = null;
  #windows = [];
  sendJsonLine(event, {jsonLine}) {
    if (!this.#currentProcess || this.#currentProcess.killed) {
      throw new Error('No active process to send JSON line to');
    }
    console.log('[stdin]', jsonLine);
    this.#currentProcess.stdin.write(jsonLine + '\n');
    return true;
  }
  attachWindow(subWindow) {
    this.#windows.push(subWindow);
  }
  detachWindow(subWindow) {
    this.#windows = this.#windows.filter((w) => w !== subWindow);
  }
  startProcess(mainWindow) {
    this.attachWindow(mainWindow);
    if (this.#currentProcess && !this.#currentProcess.killed) {
      console.warn('Process is already running, stopping it first');
      this.#currentProcess.kill();
    }
    this.#currentProcess = spawn('python3', ['./src/Chat.py'], {
      stdio: ['pipe', 'pipe', 'pipe'],
      cwd: path.join(__dirname, '../..')
    });

    this.#currentProcess.stdout.setEncoding('utf8');
    let partialStdout = '';
    this.#currentProcess.stdout.on('data', (data) => {
      if (!data) return;
      data = partialStdout + data;
      const lines = data.split('\n');
      const lastLine = lines.pop() ?? '';
      if (lastLine.trim() !== '') {
        partialStdout = lastLine;
      }
      for (const line of lines) {
        if (line.trim()) {
          //console.log('Sending stdout to', this.#windows.length, 'windows');
          for (const window of this.#windows) {
            console.log('[stdout]', line);
            window.webContents.send('stdout', { payload: line });
          }
        }
      }
    });

    this.#currentProcess.stderr.setEncoding('utf8');
    let partialStderr = '';
    this.#currentProcess.stderr.on('data', (data) => {
      if (!data) return;
      data = partialStderr + data;
      const lines = data.split('\n');
      const lastLine = lines.pop() ?? '';
      if (lastLine.trim() !== '') {
        partialStderr = lastLine;
      }
      for (const line of lines) {
        if (line.trim()) {
          //console.error('Sending stderr to', this.#windows.length, 'windows');
          for (const window of this.#windows) {
            console.error('[stderr]', line);
            window.webContents.send('stderr', { payload: line });
          }
        }
      }
    });
  }
  stopProcess(mainWindow) {
    this.detachWindow(mainWindow);
    if (this.#currentProcess && !this.#currentProcess.killed) {
      this.#currentProcess.kill();
    }
  } 
}


function createMainWindow() {
  const mainWindow = new BrowserWindow({
    width: 1024,
    height: 768,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js')
    }
  });
  mainWindow.setMenuBarVisibility(false);

  mainWindow.loadURL('http://localhost:1420'); // Adjust the URL as needed

  return mainWindow;
}

/**
 * 
 * @param {Object} opts - Options for the overlay window
 * @param {boolean} opts.fullscreen - Whether the overlay should be fullscreen
 * @param {boolean} opts.maximized - Whether the overlay should be maximized
 * @param {boolean} opts.alwaysOnTop - Whether the overlay should always be on
 */
function createOverlayWindow(opts) {
  const overlayWindow = new BrowserWindow({
    width: 800,
    height: 600,
    frame: false, // No frame for the overlay
    transparent: true, // Make it transparent
    alwaysOnTop: opts.alwaysOnTop, // Keep it on top of other windows
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
    }
  });
  overlayWindow.loadURL('http://localhost:1420#/overlay'); // Adjust the URL as needed
  overlayWindow.setIgnoreMouseEvents(true); // Ignore mouse events if needed
  if (opts.fullscreen) {
    overlayWindow.setFullScreen(true);
  }
  if (opts.maximized) {
    overlayWindow.maximize();
  }
  return overlayWindow;
}
app.whenReady().then(async ()=>{
  const backend = new BackendService();
  const mainWindow = createMainWindow();
  let floatingOverlay = null;
  ipcMain.handle('get_commit_hash', (...args)=>'development');
  ipcMain.handle('send_json_line', (...args)=>backend.sendJsonLine(...args));
  ipcMain.handle('start_process', (...args)=>backend.startProcess(mainWindow, ...args));
  ipcMain.handle('stop_process', (...args)=>backend.stopProcess(mainWindow, ...args));
  ipcMain.handle('create_floating_overlay', async (event, opts) => {
    if (floatingOverlay) return true;
    floatingOverlay = createOverlayWindow(opts);
    backend.attachWindow(floatingOverlay);
  });
  ipcMain.handle('destroy_floating_overlay', async (event) => {
    if (floatingOverlay) {
      backend.detachWindow(floatingOverlay);
      floatingOverlay.close();
      floatingOverlay = null;
    }
  });

  mainWindow.on('closed', () => {
    backend.stopProcess(mainWindow);
    mainWindow = null;
    if (floatingOverlay) {
      backend.detachWindow(floatingOverlay);
      floatingOverlay.close();
      floatingOverlay = null;
    }
  });
});