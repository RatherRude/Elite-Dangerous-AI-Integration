import { app, BrowserWindow, dialog, ipcMain, protocol, net, screen, shell, systemPreferences } from 'electron';
import { spawn } from 'child_process';
import http from 'node:http';
import crypto from 'node:crypto';
import os from 'node:os';
import path from 'path';
import url from 'node:url';
import fs from 'node:fs';
import fsPromises from 'node:fs/promises';
import contextMenu from 'electron-context-menu';
import pino from 'pino';
import { WebSocketServer } from 'ws';
import {VROverlay} from '@covas-labs/electron-vr';
import {
  configure as configureNativeOverlay,
  displayToOverlayRect,
  getBackendSelection as getOverlayBackendSelection,
  getCapabilities as getOverlayCapabilities,
} from '@covas-labs/electron-overlay';
import {
  createDesktopOverlayLifecycle,
  normalizeDesktopOverlayScreen,
  selectOverlayDisplay,
} from './desktop-overlay-lifecycle.js';

const isDevelopment = process.env.NODE_ENV === 'development';
const isLinux = process.platform === 'linux';
const overlayPreloadPath = path.join(import.meta.dirname, 'preload.js');
const overlayWindowTitle = 'COVAS:NEXT Overlay';
let loggerShuttingDown = false;
let remoteInterface = null;

// electron-vr needs shared image transport for efficient offscreen texture forwarding.
app.commandLine.appendSwitch('enable-features', 'SharedImages');

function logMethod (args, method) {
  if (loggerShuttingDown) {
    return;
  }
  if (args.length >= 2) {
    for (let i = 1; i < args.length; i++) {
      args[0] = `${args[0]} %j`
    }
  }
  method.apply(this, args)
}

function disableLoggerForShutdown() {
  loggerShuttingDown = true;
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

app.on('before-quit', () => {
  disableLoggerForShutdown();
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

function getOverlayUrl(opts = {}) {
  const overlayUrl = new URL(config.overlay);
  if (overlayUrl.hash) {
    const [hashPath, hashQuery = ''] = overlayUrl.hash.split('?');
    const hashParams = new URLSearchParams(hashQuery);
    for (const [key, value] of Object.entries(opts)) {
      hashParams.set(key, String(value));
    }
    overlayUrl.hash = `${hashPath}?${hashParams.toString()}`;
  } else {
    for (const [key, value] of Object.entries(opts)) {
      overlayUrl.searchParams.set(key, String(value));
    }
  }
  return overlayUrl.toString();
}

function getPitchRotation(tiltDegrees = 0) {
  const radians = tiltDegrees * Math.PI / 180;
  const halfRadians = radians / 2;
  return { x: Math.sin(halfRadians), y: 0, z: 0, w: Math.cos(halfRadians) };
}

function getOverlayPlacement(vrAnchor, vrSizeMeters, horizontalOffset = 0, verticalOffset = 0, distanceOffset = 0, tiltDegrees = 0) {
  const rotation = getPitchRotation(tiltDegrees);
  if (vrAnchor === 'world') {
    const distance = Math.max(0.1, 2.0 + distanceOffset);
    const widthOffset = 0.5;
    const heightOffset = (720 / 1280) / 2;
    return {
      mode: 'world',
      position: { x: horizontalOffset - widthOffset, y: 1.4 + verticalOffset - heightOffset, z: -distance },
      rotation,
    };
  }
  const distance = Math.max(0.1, 1.1 + distanceOffset);
  return {
    mode: 'head',
    position: { x: horizontalOffset, y: verticalOffset, z: -distance },
    rotation,
  };
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function normalizeOverlayOptions(opts = {}) {
  const desktopPlacement = normalizeDesktopOverlayScreen(opts.screenId);
  const mode = opts.mode === 'screen'
    ? 'desktop'
    : ['disabled', 'desktop', 'vr', 'both'].includes(opts.mode)
      ? opts.mode
      : 'desktop';
  const vrHorizontalOffset = Number.isFinite(opts.vrHorizontalOffset)
    ? clamp(opts.vrHorizontalOffset, -2.0, 2.0)
    : 0;
  const vrVerticalOffset = Number.isFinite(opts.vrVerticalOffset)
    ? clamp(opts.vrVerticalOffset, -1.5, 1.5)
    : 0;
  const vrDistanceOffset = Number.isFinite(opts.vrDistanceOffset)
    ? clamp(opts.vrDistanceOffset, -0.75, 1.5)
    : 0;
  const vrTiltDegrees = Number.isFinite(opts.vrTiltDegrees)
    ? clamp(opts.vrTiltDegrees, -90, 90)
    : 0;
  const vrCurvature = Number.isFinite(opts.vrCurvature)
    ? clamp(opts.vrCurvature, 0, 0.5)
    : 0;

  return {
    alwaysOnTop: Boolean(opts.alwaysOnTop),
    ...desktopPlacement,
    parentWindowName: 'Elite - Dangerous',
    mode,
    vrSizeMeters: Number.isFinite(opts.vrSizeMeters) && opts.vrSizeMeters > 0
      ? opts.vrSizeMeters
      : 0.9,
    vrAnchor: opts.vrAnchor === 'world' ? 'world' : 'head',
    vrHorizontalOffset,
    vrVerticalOffset,
    vrDistanceOffset,
    vrTiltDegrees,
    vrCurvature,
  };
}

async function getOverlayRuntimeInfo() {
  let desktopOverlay;
  try {
    const selection = getOverlayBackendSelection(undefined, 'auto');
    desktopOverlay = {
      ...selection,
      capabilities: getOverlayCapabilities(undefined, 'auto'),
    };
  } catch (error) {
    desktopOverlay = {
      backend: 'unknown',
      source: 'platform-default',
      confidence: 'inferred',
      evidence: '',
      capabilities: null,
      error: error instanceof Error ? error.message : String(error),
    };
  }

  try {
    console.log("VROverlay:", VROverlay);

    const runtimeInfo = VROverlay.getRuntimeInfo();
    console.log("runtimeInfo:", runtimeInfo);
    return {
      ...runtimeInfo,
      packageInstalled: true,
      available: VROverlay.isAvailable(runtimeInfo),
      hasRealVRRuntime: VROverlay.hasRealVRRuntime(runtimeInfo),
      desktopOverlay,
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
      desktopOverlay,
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

const remoteUiMimeTypes = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.map': 'application/json; charset=utf-8',
};

function getRemoteUiDirectory() {
  const packagedUiDir = path.join(import.meta.dirname, './ui');
  if (fs.existsSync(path.join(packagedUiDir, 'index.html'))) {
    return packagedUiDir;
  }

  return path.join(import.meta.dirname, '../ui/dist/covas-next-ui/browser');
}

function getMimeTypeForRemoteUi(filePath) {
  return remoteUiMimeTypes[path.extname(filePath).toLowerCase()] || 'application/octet-stream';
}

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
  #remoteClients = new Set();
  #recentMessages = [];
  #stopRequestedPid = null;
  #beforeQuitRegistered = false;
  #appQuitting = false;
  #notifyWindows(channel, payload) {
    for (const window of this.#windows) {
      window.webContents.send(channel, { payload });
    }
  }
  #notifyRemoteClients(channel, payload) {
    const message = JSON.stringify({ channel, payload: { payload } });
    for (const client of this.#remoteClients) {
      if (client.readyState === 1) {
        client.send(message);
      }
    }
  }
  #notifyListeners(channel, payload) {
    this.#recentMessages.push({ channel, payload });
    if (this.#recentMessages.length > 200) {
      this.#recentMessages.shift();
    }
    this.#notifyWindows(channel, payload);
    this.#notifyRemoteClients(channel, payload);
  }
  #hasActiveProcess() {
    return Boolean(this.#currentProcess && this.#currentProcess.exitCode === null && this.#currentProcess.signalCode === null);
  }
  sendJsonLine(event, {jsonLine}) {
    const childProcess = this.#currentProcess;
    if (!this.#hasActiveProcess() || !childProcess?.stdin?.writable) {
      throw new Error('No active process to send JSON line to');
    }
    logger.info('[stdin]', jsonLine);
    try {
      const written = childProcess.stdin.write(jsonLine + '\n');
      if (!written && childProcess.stdin.destroyed) {
        throw new Error('Backend stdin is closed');
      }
    } catch (error) {
      logger.warn('Failed to write to backend stdin:', error);
      if (this.#currentProcess === childProcess) {
        this.#currentProcess = null;
      }
      throw new Error('Backend process is no longer accepting input');
    }
    return true;
  }
  attachWindow(subWindow) {
    this.#windows.push(subWindow);
  }
  detachWindow(subWindow) {
    this.#windows = this.#windows.filter((w) => w !== subWindow);
  }
  attachRemoteClient(client) {
    this.#remoteClients.add(client);
    for (const message of this.#recentMessages) {
      client.send(JSON.stringify({ channel: message.channel, payload: { payload: message.payload } }));
    }
  }
  detachRemoteClient(client) {
    this.#remoteClients.delete(client);
  }
  startProcess(mainWindow) {
    this.attachWindow(mainWindow);
    if (this.#hasActiveProcess()) {
      logger.warn('Process is already running, stopping it first');
      this.#stopRequestedPid = this.#currentProcess.pid ?? null;
      this.#currentProcess.kill('SIGINT');
    }
    logger.info('Starting process:', config.backend);

    const childProcess = spawn(config.backend, config.backend_args, {
      stdio: ['pipe', 'pipe', 'pipe'],
      cwd: config.backend_cwd,
      env: {
        ...process.env, // inherit environment variables
        // set unbuffered python
        PYTHONUNBUFFERED: 1,
      }
    });
    this.#currentProcess = childProcess;
    logger.info('Process started with PID:', childProcess.pid);

    if (!this.#beforeQuitRegistered) {
      app.on('before-quit', () => {
        this.#appQuitting = true;
        if (this.#hasActiveProcess()) {
          this.#stopRequestedPid = this.#currentProcess.pid ?? null;
          this.#currentProcess.kill('SIGINT');
        }
      });
      this.#beforeQuitRegistered = true;
    }

    let terminationNotified = false;
    const notifyTermination = (payload) => {
      if (terminationNotified) {
        return;
      }
      terminationNotified = true;

      const expected = this.#stopRequestedPid === childProcess.pid || this.#appQuitting;
      if (expected && this.#stopRequestedPid === childProcess.pid) {
        this.#stopRequestedPid = null;
      }
      if (this.#currentProcess === childProcess) {
        this.#currentProcess = null;
      }

      this.#notifyListeners('backend-lifecycle', {
        ...payload,
        expected,
        pid: childProcess.pid ?? null,
        timestamp: new Date().toISOString(),
      });
    };

    childProcess.once('error', (error) => {
      logger.error('Backend process failed:', error);
      notifyTermination({
        status: 'error',
        message: error instanceof Error ? error.message : String(error),
      });
    });

    childProcess.once('close', (code, signal) => {
      logger.info('Backend process closed:', { pid: childProcess.pid, code, signal });
      notifyTermination({
        status: 'exited',
        code,
        signal,
      });
    });

    childProcess.stdin.once('error', (error) => {
      logger.warn('Backend stdin failed:', error);
    });

    childProcess.stdout.setEncoding('utf8');
    let partialStdout = '';
    childProcess.stdout.on('data', (data) => {
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
          this.#notifyListeners('stdout', line);
        }
      }
    });

    childProcess.stderr.setEncoding('utf8');
    let partialStderr = '';
    childProcess.stderr.on('data', (data) => {
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
          this.#notifyListeners('stderr', line);
        }
      }
    });

    mainWindow.on('close', () => {
      this.stopProcess(mainWindow);
      // remove all stdin and stdout listeners
      childProcess.stdout.removeAllListeners('data');
      childProcess.stderr.removeAllListeners('data');
    });
  }
  stopProcess(mainWindow) {
    this.detachWindow(mainWindow);
    if (this.#hasActiveProcess()) {
      logger.info('Stopping process:', this.#currentProcess.pid);
      this.#stopRequestedPid = this.#currentProcess.pid ?? null;
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
    disableLoggerForShutdown();
    // Prevent the window from closing immediately
    event.preventDefault();
    // If the user confirms, then close the window
    ipcMain.handleOnce('window-close-ready', () => {
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
 * @param {'monitor'|'elite-window'} opts.desktopTarget - Normalized desktop placement policy
 */
async function createFloatingOverlayWindow(opts) {
  const getTargetDisplay = () => {
    const displays = screen.getAllDisplays();
    return selectOverlayDisplay(displays, screen.getPrimaryDisplay(), opts.screenId);
  };
  const targetDisplay = getTargetDisplay();
  const overlayWindow = new BrowserWindow({
    x: targetDisplay.bounds.x,
    y: targetDisplay.bounds.y,
    width: 1,
    height: 1,
    title: overlayWindowTitle,
    frame: false,
    transparent: true,
    backgroundColor: '#00000000',
    focusable: false,
    show: false,
    webPreferences: {
      preload: overlayPreloadPath,
    }
  });

  const backend = 'auto';
  let nativeController;
  let lifecycle;
  try {
    nativeController = configureNativeOverlay(overlayWindow, {
      backend,
      bounds: displayToOverlayRect(targetDisplay, overlayWindow, backend),
      position: 'bounds',
      clickThrough: true,
      alwaysOnTop: opts.alwaysOnTop,
      preserveCompositing: true,
    });
  } catch (error) {
    logger.warn('Native desktop overlay initialization failed; using Electron fallback:', error);
  }

  lifecycle = createDesktopOverlayLifecycle({
    overlayWindow,
    nativeController,
    options: opts,
    getTargetDisplay,
    getOverlayBounds: display => displayToOverlayRect(display, overlayWindow, backend),
    logger,
  });

  try {
    lifecycle.refresh();

    await overlayWindow.loadURL(config.overlay);
    lifecycle.reapply();
    overlayWindow.showInactive();
    lifecycle.reapply();
    lifecycle.start();
  } catch (error) {
    lifecycle.close();
    if (!overlayWindow.isDestroyed()) {
      overlayWindow.destroy();
    }
    throw error;
  }

  return {
    window: overlayWindow,
    nativeController: lifecycle,
  };
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
    curvature: opts.vrCurvature,
    visible: true,
    placement: getOverlayPlacement(opts.vrAnchor, opts.vrSizeMeters, opts.vrHorizontalOffset, opts.vrVerticalOffset, opts.vrDistanceOffset, opts.vrTiltDegrees),
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
    windows: [overlayWindow],
    controller: vrOverlay,
    runtimeInfo,
    cleanedUp: false,
  };
}

async function createManagedOverlay(opts) {
  const normalized = normalizeOverlayOptions(opts);
  if (normalized.mode === 'disabled') {
    return {
      kind: 'disabled',
      window: null,
      windows: [],
      controller: null,
      runtimeInfo: null,
      cleanedUp: false,
    };
  }
  if (normalized.mode === 'vr') {
    return await createVrOverlayWindow(normalized);
  }
  if (normalized.mode === 'both') {
    const vrOverlay = await createVrOverlayWindow(normalized);
    let desktopOverlay;
    try {
      desktopOverlay = await createFloatingOverlayWindow(normalized);
    } catch (error) {
      try {
        vrOverlay.controller.destroy();
      } catch (cleanupError) {
        logger.warn('Failed to clean up VR overlay after desktop overlay initialization failed:', cleanupError);
      }
      if (!vrOverlay.window.isDestroyed()) {
        vrOverlay.window.destroy();
      }
      throw error;
    }
    return {
      kind: 'both',
      window: desktopOverlay.window,
      windows: [desktopOverlay.window, vrOverlay.window],
      controller: vrOverlay.controller,
      nativeControllers: [desktopOverlay.nativeController],
      runtimeInfo: vrOverlay.runtimeInfo,
      cleanedUp: false,
    };
  }
  const desktopOverlay = await createFloatingOverlayWindow(normalized);
  return {
    kind: 'screen',
    window: desktopOverlay.window,
    windows: [desktopOverlay.window],
    controller: null,
    nativeControllers: [desktopOverlay.nativeController],
    runtimeInfo: null,
    cleanedUp: false,
  };
}

function disposeOverlay(overlay, backend, closeWindow = true) {
  if (!overlay || overlay.cleanedUp) {
    return;
  }
  overlay.cleanedUp = true;
  for (const controller of overlay.nativeControllers ?? []) {
    try {
      controller.close();
    } catch (error) {
      logger.warn('Failed to close native overlay controller:', error);
    }
  }
  for (const window of overlay.windows ?? [overlay.window]) {
    backend.detachWindow(window);
  }
  if (overlay.controller) {
    try {
      overlay.controller.destroy();
    } catch (error) {
      logger.warn('Failed to destroy VR overlay controller:', error);
    }
  }
  if (closeWindow) {
    for (const window of overlay.windows ?? [overlay.window]) {
      if (window && !window.isDestroyed()) {
        window.close();
      }
    }
  }
}

async function serveRemoteUiRequest(request, response) {
  const uiDir = getRemoteUiDirectory();
  const requestUrl = new URL(request.url, 'http://127.0.0.1');
  let pathname = decodeURIComponent(requestUrl.pathname);

  if (pathname === '/ws') {
    response.writeHead(404);
    response.end('Not found');
    return;
  }

  if (pathname === '/') {
    pathname = '/index.html';
  }

  let filePath = path.resolve(uiDir, `.${pathname}`);
  const resolvedUiDir = path.resolve(uiDir);
  if (filePath !== resolvedUiDir && !filePath.startsWith(resolvedUiDir + path.sep)) {
    response.writeHead(403);
    response.end('Forbidden');
    return;
  }

  try {
    const stats = await fsPromises.stat(filePath);
    if (stats.isDirectory()) {
      filePath = path.join(filePath, 'index.html');
    }
  } catch {
    filePath = path.join(uiDir, 'index.html');
  }

  try {
    const data = await fsPromises.readFile(filePath);
    response.writeHead(200, {
      'Content-Type': getMimeTypeForRemoteUi(filePath),
      'Cache-Control': path.basename(filePath) === 'index.html' ? 'no-cache' : 'public, max-age=31536000',
    });
    response.end(data);
  } catch (error) {
    logger.warn('Failed to serve remote UI request:', { url: request.url, filePath, error });
    response.writeHead(500);
    response.end('Remote UI is not available. Build the Angular UI first.');
  }
}

function getRemoteInterfaceBindAddresses() {
  const addresses = new Set(['127.0.0.1', '0.0.0.0']);
  for (const network of Object.values(os.networkInterfaces())) {
    for (const address of network ?? []) {
      if (address.family === 'IPv4' && !address.internal) {
        addresses.add(address.address);
      }
    }
  }
  return [...addresses];
}

function getRemoteInterfaceUrl(host, port) {
  const displayHost = host === '0.0.0.0'
    ? getRemoteInterfaceBindAddresses().find((address) => address !== '127.0.0.1' && address !== '0.0.0.0') ?? '127.0.0.1'
    : host;
  return `http://${displayHost}:${port}/`;
}

function parseCookies(request) {
  return Object.fromEntries((request.headers.cookie ?? '')
    .split(';')
    .map((cookie) => cookie.trim().split(/=(.*)/s, 2))
    .filter(([name]) => name));
}

function tokensMatch(value, expected) {
  if (typeof value !== 'string' || value.length !== expected.length) {
    return false;
  }
  const valueBuffer = Buffer.from(value);
  const expectedBuffer = Buffer.from(expected);
  return valueBuffer.length === expectedBuffer.length && crypto.timingSafeEqual(valueBuffer, expectedBuffer);
}

function remoteInterfaceLoginPage(error = false) {
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>COVAS:NEXT Remote Interface</title><style>
body { align-items: center; background: #121212; color: #f2f2f2; display: flex; font: 1rem system-ui, sans-serif; justify-content: center; margin: 0; min-height: 100vh; }
main { background: #202020; border-radius: 10px; box-shadow: 0 12px 32px #0008; max-width: 22rem; padding: 2rem; width: calc(100% - 4rem); }
h1 { font-size: 1.25rem; margin-top: 0; } p { color: #c7c7c7; } input, button { box-sizing: border-box; font: inherit; width: 100%; } input { border: 1px solid #777; border-radius: 4px; letter-spacing: .2em; margin: 1rem 0; padding: .75rem; } button { background: #3f51b5; border: 0; border-radius: 4px; color: white; cursor: pointer; padding: .75rem; } .error { color: #ff8a80; }
</style></head><body><main><h1>COVAS:NEXT Remote Interface</h1><p>Enter the four-digit PIN shown in the desktop app.</p>${error ? '<p class="error">Incorrect PIN. Please try again.</p>' : ''}<form method="post" action="/auth"><input aria-label="PIN" autocomplete="one-time-code" inputmode="numeric" maxlength="4" name="pin" pattern="[0-9]{4}" required type="password"><button type="submit">Open interface</button></form></main><script>const pin = new URLSearchParams(location.hash.slice(1)).get('pin'); if (/^\\d{4}$/.test(pin ?? '')) { document.querySelector('input[name="pin"]').value = pin; document.querySelector('form').requestSubmit(); }</script></body></html>`;
}

function sendRemoteInterfaceLogin(response, statusCode, error = false) {
  response.writeHead(statusCode, {
    'Content-Type': 'text/html; charset=utf-8',
    'Cache-Control': 'no-store',
  });
  response.end(remoteInterfaceLoginPage(error));
}

async function handleRemoteInterfaceRequest(request, response, interfaceState) {
  const requestUrl = new URL(request.url, `http://${interfaceState.host}:${interfaceState.port}`);
  if (requestUrl.pathname === '/auth') {
    if (request.method !== 'POST') {
      response.writeHead(405, { Allow: 'POST' });
      response.end('Method not allowed');
      return;
    }

    let body = '';
    for await (const chunk of request) {
      body += chunk;
      if (body.length > 1024) {
        response.writeHead(413);
        response.end('Request too large');
        return;
      }
    }
    const pin = new URLSearchParams(body).get('pin') ?? '';
    if (!tokensMatch(pin, interfaceState.pin)) {
      interfaceState.failedPinAttempts += 1;
      const delayMilliseconds = interfaceState.failedPinAttempts * 1000;
      await new Promise((resolve) => setTimeout(resolve, delayMilliseconds));
      sendRemoteInterfaceLogin(response, 401, true);
      return;
    }

    interfaceState.failedPinAttempts = 0;
    response.writeHead(303, {
      Location: '/',
      'Cache-Control': 'no-store',
      'Set-Cookie': `covas_remote_session=${interfaceState.sessionToken}; HttpOnly; Path=/; SameSite=Strict`,
    });
    response.end();
    return;
  }

  if (!tokensMatch(parseCookies(request).covas_remote_session, interfaceState.sessionToken)) {
    sendRemoteInterfaceLogin(response, 401);
    return;
  }
  await serveRemoteUiRequest(request, response);
}

function createRemoteInterface(backend, opts = {}) {
  const availableHosts = getRemoteInterfaceBindAddresses();
  const host = availableHosts.includes(opts.host) ? opts.host : '127.0.0.1';
  const port = Number.isInteger(opts.port) && opts.port >= 1 && opts.port <= 65535 ? opts.port : 4048;
  const interfaceState = {
    host,
    port,
    pin: crypto.randomInt(0, 10000).toString().padStart(4, '0'),
    sessionToken: crypto.randomBytes(32).toString('base64url'),
    failedPinAttempts: 0,
  };
  const server = http.createServer((request, response) => {
    void handleRemoteInterfaceRequest(request, response, interfaceState);
  });
  const webSocketServer = new WebSocketServer({ noServer: true });

  webSocketServer.on('connection', (socket) => {
    logger.info('Remote web interface WebSocket client connected');
    backend.attachRemoteClient(socket);
    socket.send(JSON.stringify({ channel: 'remote-interface', payload: { payload: { status: 'connected' } } }));

    socket.on('message', (rawMessage) => {
      let message;
      try {
        message = JSON.parse(rawMessage.toString());
      } catch (error) {
        socket.send(JSON.stringify({ id: null, error: 'Invalid JSON message' }));
        return;
      }

      const id = message?.id ?? null;
      if (message?.call !== 'send_json_line') {
        socket.send(JSON.stringify({ id, error: 'Remote interface only supports send_json_line' }));
        return;
      }

      try {
        const result = backend.sendJsonLine(null, message.opts ?? {});
        socket.send(JSON.stringify({ id, result }));
      } catch (error) {
        socket.send(JSON.stringify({
          id,
          error: error instanceof Error ? error.message : String(error),
        }));
      }
    });

    socket.on('close', () => {
      logger.info('Remote web interface WebSocket client disconnected');
      backend.detachRemoteClient(socket);
    });
    socket.on('error', (error) => {
      logger.warn('Remote WebSocket client error:', error);
      backend.detachRemoteClient(socket);
    });
  });

  server.on('upgrade', (request, socket, head) => {
    const requestUrl = new URL(request.url, `http://${host}:${port}`);
    if (requestUrl.pathname !== '/ws' || !tokensMatch(parseCookies(request).covas_remote_session, interfaceState.sessionToken)) {
      logger.warn('Rejected remote web interface WebSocket upgrade:', requestUrl.pathname);
      socket.write('HTTP/1.1 401 Unauthorized\r\nConnection: close\r\n\r\n');
      socket.destroy();
      return;
    }

    logger.info('Accepted remote web interface WebSocket upgrade');
    webSocketServer.handleUpgrade(request, socket, head, (ws) => {
      webSocketServer.emit('connection', ws, request);
    });
  });

  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, host, () => {
      server.off('error', reject);
      const state = {
        running: true,
        host,
        port,
        url: getRemoteInterfaceUrl(host, port),
        server,
        webSocketServer,
        ...interfaceState,
      };
      logger.info('Remote web interface started:', state.url);
      resolve(state);
    });
  });
}

async function stopRemoteInterface() {
  if (!remoteInterface) {
    return { running: false, host: '127.0.0.1', port: 4048, url: null };
  }

  const current = remoteInterface;
  remoteInterface = null;
  for (const client of current.webSocketServer.clients) {
    client.close();
  }
  current.webSocketServer.close();
  await new Promise((resolve) => current.server.close(resolve));
  logger.info('Remote web interface stopped');
  return { running: false, host: current.host, port: current.port, url: null };
}

function getRemoteInterfaceState() {
  if (!remoteInterface) {
    return { running: false, host: '127.0.0.1', port: 4048, url: null };
  }
  return {
    running: true,
    host: remoteInterface.host,
    port: remoteInterface.port,
    url: remoteInterface.url,
    pin: remoteInterface.pin,
  };
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
    for (const window of floatingOverlay.windows ?? [floatingOverlay.window]) {
      backend.attachWindow(window);
      window.on('closed', () => {
        disposeOverlay(activeOverlay, backend);
        if (floatingOverlay === activeOverlay) {
          floatingOverlay = null;
        }
      });
    }
  });
  ipcMain.handle('destroy_floating_overlay', async (event) => {
    if (floatingOverlay) {
      disposeOverlay(floatingOverlay, backend);
      floatingOverlay = null;
    }
  });
  ipcMain.handle('start_remote_interface', async (event, opts = {}) => {
    if (remoteInterface) {
      return getRemoteInterfaceState();
    }

    remoteInterface = await createRemoteInterface(backend, {
      host: opts?.host,
      port: opts?.port,
    });
    return getRemoteInterfaceState();
  });
  ipcMain.handle('stop_remote_interface', async () => stopRemoteInterface());
  ipcMain.handle('get_remote_interface_state', async () => getRemoteInterfaceState());
  ipcMain.handle('get_remote_interface_bind_addresses', async () => getRemoteInterfaceBindAddresses());
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
    void stopRemoteInterface();
    if (process.platform !== 'darwin') {
      app.quit();
    }
  });
});
