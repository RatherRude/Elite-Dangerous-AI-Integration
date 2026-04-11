import { app, BrowserWindow, dialog, ipcMain, protocol, net, screen, shell, systemPreferences } from 'electron';
import { spawn } from 'child_process';
import path from 'path';
import url from 'node:url';
import fs from 'node:fs';
import fsPromises from 'node:fs/promises';
import contextMenu from 'electron-context-menu';
import pino from 'pino';
import {VROverlay} from '@covas-labs/electron-vr';

const isDevelopment = process.env.NODE_ENV === 'development';
const isLinux = process.platform === 'linux';
const overlayPreloadPath = path.join(import.meta.dirname, 'preload.js');
const overlayWindowTitle = 'COVAS:NEXT Overlay';

// electron-vr needs shared image transport for efficient offscreen texture forwarding.
app.commandLine.appendSwitch('enable-features', 'SharedImages');

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
  fs.rmSync(logsPath, { recursive: true, force: true });
  logger.info('Deleted logs directory:', logsPath);
} else if (isLinux) {
  const logsPath = path.join(process.env.XDG_DATA_HOME ?? `${process.env.HOME}/.local/share`, 'com.covas-next.ui', 'logs');
  fs.rmSync(logsPath, { recursive: true, force: true });
  logger.info('Deleted logs directory:', logsPath);
}

for (const x of ["home","userData","temp","appData","sessionData","exe","module","logs","crashDumps"]) {
  try {
    logger.info(x, app.getPath(x));
  } catch (e) {
    logger.error('Error getting path for', x, e);
  }
}

logger.info('isDevelopment:', isDevelopment);

const config = isDevelopment ? {
  ui: 'http://localhost:1420',
  overlay: 'http://localhost:1420#/overlay',
  backend: 'python',
  backend_cwd: path.join(import.meta.dirname, '..'),
  backend_args: [path.join(import.meta.dirname, '../src/Chat.py')],
} : {
  ui: 'app://./index.html',
  overlay: 'app://./index.html#/overlay',
  backend: path.resolve(import.meta.dirname, '../Chat/Chat'),
  backend_cwd: isLinux ? path.join(process.env.XDG_DATA_HOME, './com.covas-next.ui') || app.getPath('sessionData') : app.getPath('userData'),
  backend_args: [],
}

function getOverlayPlacement(vrAnchor) {
  if (vrAnchor === 'world') {
    return {
      mode: 'world',
      position: { x: 0, y: 1.4, z: -2.0 },
      rotation: { x: 0, y: 0, z: 0, w: 1 },
    };
  }
  return {
    mode: 'head',
    position: { x: 0, y: 0, z: -1.1 },
    rotation: { x: 0, y: 0, z: 0, w: 1 },
  };
}

function normalizeOverlayOptions(opts = {}) {
  return {
    alwaysOnTop: Boolean(opts.alwaysOnTop),
    screenId: Number.isInteger(opts.screenId) ? opts.screenId : -1,
    mode: opts.mode === 'vr' ? 'vr' : 'screen',
    vrSizeMeters: Number.isFinite(opts.vrSizeMeters) && opts.vrSizeMeters > 0
      ? opts.vrSizeMeters
      : 0.9,
    vrAnchor: opts.vrAnchor === 'world' ? 'world' : 'head',
  };
}

async function getOverlayRuntimeInfo() {
  try {
    console.log("VROverlay:", VROverlay);

    const runtimeInfo = VROverlay.getRuntimeInfo();
    console.log("runtimeInfo:", runtimeInfo);
    return {
      ...runtimeInfo,
      packageInstalled: true,
      available: VROverlay.isAvailable(runtimeInfo),
      hasRealVRRuntime: VROverlay.hasRealVRRuntime(runtimeInfo),
    };
  } catch (error) {
    return {
      platform: process.platform,
      probeMode: 'module_unavailable',
      openxrAvailable: false,
      openxrOverlayExtensionAvailable: false,
      openvrAvailable: false,
      openvrRuntimeInstalled: false,
      openvrRuntimePath: '',
      selectedBackend: 'none',
      packageInstalled: false,
      available: false,
      hasRealVRRuntime: false,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

// list files in the backend directory
try {
  // create backend_cwd if it doesn't exist
  fs.mkdirSync(config.backend_cwd, { recursive: true });
  
  const files = fs.readdirSync(config.backend_cwd);
  logger.info('Backend files:', files);
} catch (error) {
  logger.error('Error reading backend directory:', error);
}

contextMenu({
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

const userAssetMimeTypes = {
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.bmp': 'image/bmp',
  '.svg': 'image/svg+xml',
};

function getUserAssetsDirectory() {
  return path.join(app.getPath('userData'), 'userAssets');
}

async function ensureUserAssetsDirectory() {
  const userAssetsDir = getUserAssetsDirectory();
  await fsPromises.mkdir(userAssetsDir, { recursive: true });
  return userAssetsDir;
}

function getMimeTypeForUserAsset(filePath) {
  return userAssetMimeTypes[path.extname(filePath).toLowerCase()] || 'application/octet-stream';
}

function sanitizeUserAssetFileName(fileName) {
  const rawName = typeof fileName === 'string' && fileName.trim() ? fileName.trim() : 'asset.png';
  const baseName = path.basename(rawName);
  const sanitized = baseName.replace(/[<>:"/\\|?*\x00-\x1F]/g, '_');
  return sanitized || 'asset.png';
}

async function buildUserAssetDestinationPath(fileName) {
  const userAssetsDir = await ensureUserAssetsDirectory();
  const safeName = sanitizeUserAssetFileName(fileName);
  const extension = path.extname(safeName);
  const baseName = path.basename(safeName, extension) || 'asset';
  let candidatePath = path.join(userAssetsDir, safeName);
  if (!fs.existsSync(candidatePath)) {
    return candidatePath;
  }
  const suffix = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  candidatePath = path.join(userAssetsDir, `${baseName}-${suffix}${extension}`);
  return candidatePath;
}

async function assertUserAssetPath(filePath) {
  if (typeof filePath !== 'string' || !filePath.trim()) {
    throw new Error('Missing user asset file path');
  }
  const userAssetsDir = await ensureUserAssetsDirectory();
  const resolvedPath = path.resolve(filePath);
  const resolvedDir = path.resolve(userAssetsDir);
  const normalizedPath = process.platform === 'win32' ? resolvedPath.toLowerCase() : resolvedPath;
  const normalizedDir = process.platform === 'win32' ? resolvedDir.toLowerCase() : resolvedDir;
  if (normalizedPath !== normalizedDir && !normalizedPath.startsWith(normalizedDir + path.sep)) {
    throw new Error('User asset path is outside the managed directory');
  }
  return resolvedPath;
}

async function resolveManagedUserAssetPath(filePath) {
  if (typeof filePath !== 'string' || !filePath.trim()) {
    throw new Error('Missing user asset file path');
  }
  const userAssetsDir = await ensureUserAssetsDirectory();
  const safeName = sanitizeUserAssetFileName(path.basename(filePath));
  return assertUserAssetPath(path.join(userAssetsDir, safeName));
}

async function openMacAccessibilitySettings() {
  if (process.platform !== 'darwin') {
    return false;
  }

  const settingsUrl = 'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility';
  try {
    await shell.openExternal(settingsUrl);
    return true;
  } catch (error) {
    logger.warn('Failed to open macOS Accessibility settings via deep link:', error);
    return (await shell.openPath('/System/Library/PreferencePanes/Security.prefPane')) === '';
  }
}

async function requestMacAccessibilityPermission() {
  if (process.platform !== 'darwin') {
    return {
      supported: false,
      granted: false,
      prompted: false,
      openedSettings: false,
    };
  }

  const alreadyGranted = systemPreferences.isTrustedAccessibilityClient(false);
  if (alreadyGranted) {
    return {
      supported: true,
      granted: true,
      prompted: false,
      openedSettings: false,
    };
  }

  const grantedAfterPrompt = systemPreferences.isTrustedAccessibilityClient(true);

  return {
    supported: true,
    granted: grantedAfterPrompt,
    prompted: true,
    openedSettings: false,
  };
}

function resolveReadableAssetPath(filePath) {
  if (typeof filePath !== 'string' || !filePath.trim()) {
    throw new Error('Missing asset file path');
  }
  return path.resolve(filePath);
}

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
      preload: overlayPreloadPath
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
function createFloatingOverlayWindow(opts) {
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
    title: overlayWindowTitle,
    frame: false,
    transparent: true,
    show: false, // Don't show until positioned and maximized
    webPreferences: {
      preload: overlayPreloadPath,
    }
  });
  
  // Now maximize it - should maximize on the screen it's positioned on
  overlayWindow.maximize();
  overlayWindow.show();
  
  overlayWindow.loadURL(config.overlay);
  overlayWindow.setIgnoreMouseEvents(true);
  // overlayWindow.webContents.openDevTools({ mode: 'detach' });
  
  if (opts.alwaysOnTop) {
    overlayWindow.setAlwaysOnTop(true, 'screen-saver', 2);
  }

  return overlayWindow;
}

async function createVrOverlayWindow(opts) {
  const runtimeInfo = VROverlay.getRuntimeInfo();
  if (!VROverlay.isAvailable(runtimeInfo)) {
    throw new Error(
      `No compatible VR runtime was detected. Selected backend: ${runtimeInfo.selectedBackend}. OpenVR installed: ${runtimeInfo.openvrRuntimeInstalled}.`,
    );
  }

  const overlayWindow = new BrowserWindow({
    width: 1280,
    height: 720,
    title: overlayWindowTitle,
    show: false,
    frame: false,
    transparent: true,
    backgroundColor: '#00000000',
    webPreferences: {
      preload: overlayPreloadPath,
      offscreen: { useSharedTexture: true },
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false,
    },
  });
  overlayWindow.setMenuBarVisibility(false);
  await overlayWindow.loadURL(config.overlay);

  const vrOverlay = await VROverlay.openWindow(overlayWindow, {
    name: 'COVAS_NEXT_Overlay',
    frameRate: 60,
    sizeMeters: opts.vrSizeMeters,
    visible: true,
    placement: getOverlayPlacement(opts.vrAnchor),
  });

  if (!vrOverlay) {
    if (!overlayWindow.isDestroyed()) {
      overlayWindow.close();
    }
    throw new Error('Failed to attach the overlay window to the VR bridge.');
  }

  return {
    kind: 'vr',
    window: overlayWindow,
    controller: vrOverlay,
    runtimeInfo,
    cleanedUp: false,
  };
}

async function createManagedOverlay(opts) {
  const normalized = normalizeOverlayOptions(opts);
  if (normalized.mode === 'vr') {
    return createVrOverlayWindow(normalized);
  }
  return {
    kind: 'screen',
    window: createFloatingOverlayWindow(normalized),
    controller: null,
    runtimeInfo: null,
    cleanedUp: false,
  };
}

function disposeOverlay(overlay, backend, closeWindow = true) {
  if (!overlay || overlay.cleanedUp) {
    return;
  }
  overlay.cleanedUp = true;
  backend.detachWindow(overlay.window);
  if (overlay.controller) {
    try {
      overlay.controller.destroy();
    } catch (error) {
      logger.warn('Failed to destroy VR overlay controller:', error);
    }
  }
  if (closeWindow && overlay.window && !overlay.window.isDestroyed()) {
    overlay.window.close();
  }
}

app.whenReady().then(async ()=>{

  protocol.handle('app', (request) => {
    const requestUrl = new URL(request.url);
    const resolved = url.pathToFileURL(path.join(import.meta.dirname, './ui/', requestUrl.pathname)).toString()
    //logger.info(request.url, '->', resolved)
    // if file is directory, return index.html
    if (requestUrl.pathname.endsWith('/')) {
      return net.fetch(url.pathToFileURL(path.join(import.meta.dirname, './ui/index.html')).toString())
    }
    return net.fetch(resolved)
  })

  const backend = new BackendService();
  const mainWindow = createMainWindow();
  let floatingOverlay = null;
  ipcMain.handle('send_json_line', (...args)=>backend.sendJsonLine(...args));
  ipcMain.handle('start_process', (...args)=>{
    // Close existing overlay on process start (handles reload scenarios)
    if (floatingOverlay) {
      disposeOverlay(floatingOverlay, backend);
      floatingOverlay = null;
    }
    return backend.startProcess(mainWindow, ...args);
  });
  ipcMain.handle('stop_process', (...args)=>backend.stopProcess(mainWindow, ...args));
  ipcMain.handle('create_floating_overlay', async (event, opts) => {
    if (floatingOverlay) {
      // Always destroy existing overlay to apply new settings
      disposeOverlay(floatingOverlay, backend);
      floatingOverlay = null;
    }
    floatingOverlay = await createManagedOverlay(opts);
    const activeOverlay = floatingOverlay;
    if (floatingOverlay.runtimeInfo) {
      logger.info('VR overlay runtime info:', floatingOverlay.runtimeInfo);
    }
    backend.attachWindow(floatingOverlay.window);
    activeOverlay.window.on('closed', () => {
      disposeOverlay(activeOverlay, backend, false);
      if (floatingOverlay === activeOverlay) {
        floatingOverlay = null;
      }
    });
  });
  ipcMain.handle('destroy_floating_overlay', async (event) => {
    if (floatingOverlay) {
      disposeOverlay(floatingOverlay, backend);
      floatingOverlay = null;
    }
  });
  ipcMain.handle('get_overlay_runtime_info', async () => getOverlayRuntimeInfo());
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
  ipcMain.handle('select_quest_audio_file', async (event, opts) => {
    const catalogPath = opts?.catalogPath;
    if (typeof catalogPath !== 'string' || !catalogPath) {
      throw new Error('Missing catalogPath for audio import');
    }

    const selection = await dialog.showOpenDialog(mainWindow, {
      title: 'Select quest audio file',
      properties: ['openFile'],
      filters: [
        { name: 'Audio', extensions: ['mp3', 'wav'] },
      ],
    });

    if (selection.canceled || !selection.filePaths?.length) {
      return { canceled: true };
    }

    const sourcePath = selection.filePaths[0];
    const extension = path.extname(sourcePath).toLowerCase();
    if (!['.mp3', '.wav'].includes(extension)) {
      throw new Error('Only MP3 and WAV files are supported.');
    }

    const fileName = path.basename(sourcePath);
    const catalogDir = path.dirname(catalogPath);
    const audioDir = path.join(catalogDir, 'audio');
    const destinationPath = path.join(audioDir, fileName);

    await fsPromises.mkdir(audioDir, { recursive: true });

    const destinationExists = fs.existsSync(destinationPath);
    if (!destinationExists) {
      await fsPromises.copyFile(sourcePath, destinationPath);
    }

    return {
      canceled: false,
      fileName,
      copied: !destinationExists,
      reused: destinationExists,
      destinationPath,
    };
  });
  ipcMain.handle('write_user_asset_file', async (event, opts) => {
    const fileName = opts?.fileName;
    const dataBase64 = opts?.dataBase64;
    const mimeType = typeof opts?.mimeType === 'string' ? opts.mimeType : null;
    if (typeof dataBase64 !== 'string' || !dataBase64) {
      throw new Error('Missing user asset image data');
    }
    const destinationPath = await buildUserAssetDestinationPath(fileName);
    const buffer = Buffer.from(dataBase64, 'base64');
    await fsPromises.writeFile(destinationPath, buffer);
    const stats = await fsPromises.stat(destinationPath);
    return {
      path: destinationPath,
      fileName: path.basename(destinationPath),
      mimeType: mimeType || getMimeTypeForUserAsset(destinationPath),
      createdAt: stats.birthtime.toISOString(),
      modifiedAt: stats.mtime.toISOString(),
      size: stats.size,
    };
  });
  ipcMain.handle('read_user_asset_file', async (event, opts) => {
    const assetPath = resolveReadableAssetPath(opts?.path);
    const buffer = await fsPromises.readFile(assetPath);
    return {
      path: assetPath,
      mimeType: getMimeTypeForUserAsset(assetPath),
      dataBase64: buffer.toString('base64'),
    };
  });
  ipcMain.handle('list_user_asset_files', async () => {
    const userAssetsDir = await ensureUserAssetsDirectory();
    const entries = await fsPromises.readdir(userAssetsDir, { withFileTypes: true });
    const files = await Promise.all(entries
      .filter((entry) => entry.isFile())
      .map(async (entry) => {
        const filePath = path.join(userAssetsDir, entry.name);
        const stats = await fsPromises.stat(filePath);
        return {
          path: filePath,
          fileName: entry.name,
          mimeType: getMimeTypeForUserAsset(filePath),
          createdAt: stats.birthtime.toISOString(),
          modifiedAt: stats.mtime.toISOString(),
          size: stats.size,
        };
      }));
    files.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
    return files;
  });
  ipcMain.handle('delete_user_asset_file', async (event, opts) => {
    const assetPath = await resolveManagedUserAssetPath(opts?.path);
    if (!fs.existsSync(assetPath)) {
      return { deleted: false };
    }
    await fsPromises.unlink(assetPath);
    return { deleted: true };
  });
  ipcMain.handle('request_accessibility_permission', async () => {
    return requestMacAccessibilityPermission();
  });
  ipcMain.handle('open_accessibility_settings', async () => {
    return {
      supported: process.platform === 'darwin',
      opened: await openMacAccessibilitySettings(),
    };
  });

  mainWindow.on('closed', () => {
    if (floatingOverlay) {
      disposeOverlay(floatingOverlay, backend);
      floatingOverlay = null;
    }
    backend.stopProcess(mainWindow);
    process.exit(0);
  });
});
