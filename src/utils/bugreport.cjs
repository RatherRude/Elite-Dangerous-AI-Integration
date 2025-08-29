const fs = require('fs');
const os = require('os');
const path = require('path');
const archiver = require('archiver');

const ROOT = path.resolve(__dirname, '../..');
const BUGREPORTS_DIR = path.join(ROOT, 'bugreports');
const TIMESTAMP = new Date().toISOString().replace(/[:.]/g, '-');
const ZIP_NAME = `BugReport_${TIMESTAMP}.zip`;
const ZIP_PATH = path.join(BUGREPORTS_DIR, ZIP_NAME);

const LOG_CANDIDATES = [
  path.join(ROOT, 'logs', 'com.covas-next.ui.log'),
  path.join(os.homedir(), '.config', 'com.covas-next.ui', 'logs', 'com.covas-next.ui.log'),
  path.join(os.homedir(), 'AppData', 'Roaming', 'com.covas-next.ui', 'logs', 'com.covas-next.ui.log'),
];

const INCLUDE_PATHS = [
  path.join(ROOT, 'logs'),
  path.join(ROOT, 'config.json')
];

function getSystemInfo() {
  return {
    timestamp: new Date().toISOString(),
    os: `${os.platform()} ${os.release()}`,
    arch: os.arch(),
    node: process.version,
    cpu: os.cpus()[0]?.model || 'unknown',
  };
}

function addDirectory(archive, dirPath, prefix = '') {
  if (!fs.existsSync(dirPath)) return;
  for (const entry of fs.readdirSync(dirPath)) {
    if (!entry) continue;
    const full = path.join(dirPath, entry);
    const rel = path.join(prefix, entry).replace(/\\/g, '/');
    if (!rel) continue;

    const stat = fs.statSync(full);
    if (stat.isDirectory()) {
      addDirectory(archive, full, rel);
    } else if (stat.isFile()) {
      archive.file(full, { name: rel });
    }
  }
}

async function createBugReport() {
  fs.mkdirSync(BUGREPORTS_DIR, { recursive: true });
  const output = fs.createWriteStream(ZIP_PATH);
  const archive = archiver('zip', { zlib: { level: 9 } });

  return new Promise((resolve, reject) => {
    output.on('close', () => resolve(ZIP_PATH));
    archive.on('error', reject);
    archive.pipe(output);

    archive.append(JSON.stringify(getSystemInfo(), null, 2), { name: 'system_info.json' });
    archive.append('COVAS:NEXT local bug report\n', { name: 'README.txt' });

    for (const candidate of LOG_CANDIDATES) {
      if (fs.existsSync(candidate)) {
        archive.file(candidate, { name: 'com.covas-next.ui.log' });
        break;
      }
    }

    for (const item of INCLUDE_PATHS) {
      if (!fs.existsSync(item)) continue;
      const stat = fs.statSync(item);
      if (stat.isFile()) {
        const name = path.basename(item);
        if (name) archive.file(item, { name });
      } else if (stat.isDirectory()) {
        const dirName = path.basename(item);
        if (dirName) addDirectory(archive, item, dirName);
      }
    }

    archive.finalize();
  });
}

module.exports = { createBugReport };
