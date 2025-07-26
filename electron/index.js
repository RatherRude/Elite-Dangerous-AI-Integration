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
if (!isDevelopment) {
  transport.targets.push({
    target: 'pino-roll',
    options: { 
      file: path.join(app.getPath('logs'), 'com.covas-next.ui.log'), 
      size: '50m', 
      mkdir: true, 
      limit: { removeOtherLogFiles: true, count: 1 } 
    }
  });
}
const logger = pino({
  level: 'debug',
  transport: transport,
  hooks: {logMethod}
});

// delete old tauri log files
if (process.platform === 'win32') {
  const logsPath = path.join(process.env.APPDATA, 'com.covas-next.ui', 'logs');
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
const files = require('fs').readdirSync(config.backend_cwd);
logger.info('Backend files:', files);

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
      this.#currentProcess.kill();
    }
    logger.info('Starting process:', config.backend);

    this.#currentProcess = spawn(config.backend, config.backend_args, {
      stdio: ['pipe', 'pipe', 'pipe'],
      cwd: config.backend_cwd
    });

    app.on('before-quit', () => {
      if (this.#currentProcess && !this.#currentProcess.killed) {
        this.#currentProcess.kill();
      }
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
          //logger.info('Sending stdout to', this.#windows.length, 'windows');
          if (!line.includes('"type": "config"')) {
            logger.info('[stdout]', line);
          } else {
            logger.debug('[stdout]', "[config redacted]");
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
      const lines = data.split('\n');
      const lastLine = lines.pop() ?? '';
      if (lastLine.trim() !== '') {
        partialStderr = lastLine;
      }
      for (const line of lines) {
        if (line.trim()) {
          //logger.error('Sending stderr to', this.#windows.length, 'windows');
          if (!line.includes('"type": "config"')) {
            logger.info('[stderr]', line);
          } else {
            logger.debug('[stderr]', "[config redacted]");
          }
          for (const window of this.#windows) {
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
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
    }
  });
  overlayWindow.loadURL(config.overlay);
  overlayWindow.setIgnoreMouseEvents(true);
  
  if (opts.fullscreen) {
    overlayWindow.setFullScreen(true);
  }
  if (opts.maximized) {
    overlayWindow.maximize();
  } else {
    const primaryDisplay = screen.getPrimaryDisplay()
    const { width, height } = primaryDisplay.workAreaSize
    overlayWindow.setBounds({ x: 0, y: 0, width, height });
  }
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
    if (floatingOverlay) return true;
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