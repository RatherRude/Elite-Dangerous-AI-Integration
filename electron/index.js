const { app, BrowserWindow, ipcMain, protocol, net, screen, shell } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const url = require('node:url')
const contextMenu = require('electron-context-menu');
const pino = require('pino')

const isDevelopment = process.env.NODE_ENV === 'development';
const isLinux = process.platform === 'linux';

function logMethod (args, method) {
  if (args.length >= 2) {
    for (let i = 1; i < args.length; i++) {
      args[0] = `${args[0]} %j`
    }
  }
  method.apply(this, args)
}

const transport = {
  targets: [{
    target: 'pino-pretty',
    options: { destination: 1 } // use 2 for stderr
  }]
}
transport.targets.push({
  target: 'pino-roll',
  options: { 
    file: isDevelopment ? '../logs/com.covas-next.ui.log' : path.join(app.getPath('logs'), 'com.covas-next.ui.log'), 
    size: '50m', 
    mkdir: true, 
    limit: { removeOtherLogFiles: true, count: 1 } 
  }
});

const logger = pino({
  level: 'debug',
  transport: transport,
  hooks: {logMethod}
});

// delete old tauri log files
if (process.platform === 'win32') {
  const logsPath = path.join(process.env.LOCALAPPDATA, 'com.covas-next.ui', 'logs');
  require('fs').rmSync(logsPath, { recursive: true, force: true });
  logger.info('Deleted logs directory:', logsPath);
} else if (isLinux) {
  const logsPath = path.join(process.env.XDG_DATA_HOME, 'com.covas-next.ui', 'logs');
  require('fs').rmSync(logsPath, { recursive: true, force: true });
  logger.info('Deleted logs directory:', logsPath);
}

for (const x of ["home","userData","temp","appData","sessionData","exe","module","desktop","documents","downloads","music","pictures","videos","logs","crashDumps"]) {
  logger.info(x, app.getPath(x));
}


logger.info('isDevelopment:', isDevelopment);

const config = isDevelopment ? {
  ui: 'http://localhost:1420',
  overlay: 'http://localhost:1420#/overlay',
  backend: 'python',
  backend_cwd: path.join(__dirname, '..'),
  backend_args: [path.join(__dirname, '../src/Chat.py')],
} : {
  ui: 'app://./index.html',
  overlay: 'app://./index.html#/overlay',
  backend: path.resolve(__dirname, '../Chat/Chat'),
  backend_cwd: isLinux ? path.join(process.env.XDG_DATA_HOME, './com.covas-next.ui') || app.getPath('sessionData') : app.getPath('userData'),
  backend_args: [],
}

// list files in the backend directory
try {
  // create backend_cwd if it doesn't exist
  require('fs').mkdirSync(config.backend_cwd, { recursive: true });
  
  const files = require('fs').readdirSync(config.backend_cwd);
  logger.info('Backend files:', files);
} catch (error) {
  logger.error('Error reading backend directory:', error);
}

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
  showInspectElement: true,
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

protocol.registerSchemesAsPrivileged([
  {
    scheme: 'app',
    privileges: {
      secure: true,
      supportFetchAPI: true,
      bypassCSP: true,
      standard: true,
      corsEnabled: false,
    }
  }
]);

class BackendService {
  #currentProcess = null;
  #windows = [];
  sendJsonLine(event, {jsonLine}) {
    if (!this.#currentProcess || this.#currentProcess.killed) {
      throw new Error('No active process to send JSON line to');
    }
    logger.info('[stdin]', jsonLine);
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
      logger.warn('Process is already running, stopping it first');
      this.#currentProcess.kill('SIGINT');
    }
    logger.info('Starting process:', config.backend);

    this.#currentProcess = spawn(config.backend, config.backend_args, {
      stdio: ['pipe', 'pipe', 'pipe'],
      cwd: config.backend_cwd,
      env: {
        ...process.env, // inherit environment variables
        // set unbuffered python
        PYTHONUNBUFFERED: 1,
      }
    });
    logger.info('Process started with PID:', this.#currentProcess.pid);

    app.on('before-quit', () => {
      if (this.#currentProcess && !this.#currentProcess.killed) {
        this.#currentProcess.kill('SIGINT');
      }
    });

    this.#currentProcess.stdout.setEncoding('utf8');
    let partialStdout = '';
    this.#currentProcess.stdout.on('data', (data) => {
      if (!data) return;
      data = partialStdout + data;
      partialStdout = '';
      const lines = data.split('\n');
      const lastLine = lines.pop() ?? '';
      if (lastLine.trim() !== '') {
        partialStdout = lastLine;
      }
      for (const line of lines) {
        if (line.trim()) {
          //logger.info('Sending stdout to', this.#windows.length, 'windows');
          if (!line.includes('"type": "config"') && !line.includes('"type": "running_config"')) {
            logger.info('[stdout]', line);
          } else {
            logger.info('[stdout]', "[config redacted]");
          }
          for (const window of this.#windows) {
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
      partialStderr = '';
      const lines = data.split('\n');
      const lastLine = lines.pop() ?? '';
      if (lastLine.trim() !== '') {
        partialStderr = lastLine;
      }
      for (const line of lines) {
        if (line.trim()) {
          //logger.error('Sending stderr to', this.#windows.length, 'windows');
          if (!line.includes('"type": "config"') && !line.includes('"type": "running_config"')) {
            logger.info('[stderr]', line);
          } else {
            logger.info('[stderr]', "[config redacted]");
          }
          for (const window of this.#windows) {
            window.webContents.send('stderr', { payload: line });
          }
        }
      }
    });
    mainWindow.on('close', () => {
      this.stopProcess(mainWindow);
      // remove all stdin and stdout listeners
      this.#currentProcess.stdout.removeAllListeners('data');
      this.#currentProcess.stderr.removeAllListeners('data');
    });
  }
  stopProcess(mainWindow) {
    this.detachWindow(mainWindow);
    if (this.#currentProcess && !this.#currentProcess.killed) {
      logger.info('Stopping process:', this.#currentProcess.pid);
      const pid = this.#currentProcess.pid;
      this.#currentProcess.kill('SIGINT');
    }
  } 
}


function createMainWindow() {
  const mainWindow = new BrowserWindow({
    width: 1024,
    height: 768,
    title: 'COVAS:NEXT',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js')
    }
  });
  mainWindow.setMenuBarVisibility(false);

  // Handle CORS
  mainWindow.webContents.session.webRequest.onBeforeSendHeaders(
    (details, callback) => {
      callback({ requestHeaders: { Origin: '*', ...details.requestHeaders } });
    },
  );

  mainWindow.webContents.session.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        'access-control-allow-origin': '*',
        'access-control-allow-methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'access-control-allow-headers': 'Authorization, User-Agent, content-type',
        'access-control-allow-credentials': 'true',
        'access-control-max-age': '86400',
        ...details.responseHeaders,
      },
    });
  });

  // Handle opening external links
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
      // config.fileProtocol is my custom file protocol
      if (url.startsWith(config.fileProtocol)) {
          return { action: 'allow' };
      }
      // open url in a browser and prevent default
      shell.openExternal(url);
      return { action: 'deny' };
  });


  mainWindow.loadURL(config.ui);

  // Handle window close
  mainWindow.once('close', (event) => {
    // Prevent the window from closing immediately
    event.preventDefault();
    // If the user confirms, then close the window
    ipcMain.handleOnce('window-close-ready', () => {
      logger.info('Main window close handler done, stopping process');
      mainWindow.close();
    });
    // Call renderer close handler
    mainWindow.webContents.send('window-close');
  });

  return mainWindow;
}

/**
 * 
 * @param {Object} opts - Options for the overlay window
 * @param {boolean} opts.alwaysOnTop - Whether the overlay should always be on top
 * @param {number} opts.screenId - ID of the screen to display on (-1 for primary)
 */
function createOverlayWindow(opts) {
  // Find the target display first
  let targetDisplay;
  const displays = screen.getAllDisplays();
  
  if (opts.screenId && opts.screenId !== -1) {
    targetDisplay = displays.find(display => display.id === opts.screenId);
    if (!targetDisplay) {
      targetDisplay = screen.getPrimaryDisplay();
    }
  } else {
    targetDisplay = screen.getPrimaryDisplay();
  }
  
  // Start with work area to position on correct screen
  const { x, y } = targetDisplay.workArea;
  
  // Create window positioned on the target screen
  const overlayWindow = new BrowserWindow({
    x: x,
    y: y,
    width: 800,
    height: 600,
    title: 'COVAS:NEXT Overlay',
    frame: false,
    transparent: true,
    show: false, // Don't show until positioned and maximized
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
    }
  });
  
  // Now maximize it - should maximize on the screen it's positioned on
  overlayWindow.maximize();
  overlayWindow.show();
  
  overlayWindow.loadURL(config.overlay);
  overlayWindow.setIgnoreMouseEvents(true);
  
  if (opts.alwaysOnTop) {
    overlayWindow.setAlwaysOnTop(true, 'screen-saver', 2);
  }

  return overlayWindow;
}
app.whenReady().then(async ()=>{

  protocol.handle('app', (request) => {
    const requestUrl = new URL(request.url);
    const resolved = url.pathToFileURL(path.join(__dirname, './ui/', requestUrl.pathname)).toString()
    //logger.info(request.url, '->', resolved)
    // if file is directory, return index.html
    if (requestUrl.pathname.endsWith('/')) {
      return net.fetch(url.pathToFileURL(path.join(__dirname, './ui/index.html')).toString())
    }
    return net.fetch(resolved)
  })

  const backend = new BackendService();
  const mainWindow = createMainWindow();
  let floatingOverlay = null;
  ipcMain.handle('send_json_line', (...args)=>backend.sendJsonLine(...args));
  ipcMain.handle('start_process', (...args)=>backend.startProcess(mainWindow, ...args));
  ipcMain.handle('stop_process', (...args)=>backend.stopProcess(mainWindow, ...args));
  ipcMain.handle('create_floating_overlay', async (event, opts) => {
    if (floatingOverlay) {
      // Always destroy existing overlay to apply new settings
      backend.detachWindow(floatingOverlay);
      floatingOverlay.close();
      floatingOverlay = null;
    }
    floatingOverlay = createOverlayWindow(opts);
    backend.attachWindow(floatingOverlay);
    floatingOverlay.on('closed', () => {
      backend.detachWindow(floatingOverlay);
      floatingOverlay = null;
    });
  });
  ipcMain.handle('destroy_floating_overlay', async (event) => {
    if (floatingOverlay) {
      backend.detachWindow(floatingOverlay);
      floatingOverlay.close();
      floatingOverlay = null;
    }
  });
  ipcMain.handle('get_available_screens', async (event) => {
    const displays = screen.getAllDisplays();
    const result = displays.map((display, index) => ({
      id: display.id,
      label: `Screen ${index + 1} (${display.bounds.width}x${display.bounds.height})${display.primary ? ' - Primary' : ''}`,
      bounds: display.bounds,
      primary: display.primary
    }));
    return result;
  });

  mainWindow.on('closed', () => {
    if (floatingOverlay) {
      backend.detachWindow(floatingOverlay);
      if (!floatingOverlay.isDestroyed()) {
        floatingOverlay.close();
        floatingOverlay = null;
      };
    }
    backend.stopProcess(mainWindow);
    process.exit(0);
  });
});