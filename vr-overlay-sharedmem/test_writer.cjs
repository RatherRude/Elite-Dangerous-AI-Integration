const { SharedMemory } = require('./shared-memory-addon');

const SHARED_MEMORY_NAME = 'CovasVROverlaySharedMemory';
const MAX_TEXTURE_SIZE = 1920 * 1080 * 4;
const HEADER_SIZE = 16; // width, height, frameNumber, ready
const SHARED_MEMORY_SIZE = HEADER_SIZE + MAX_TEXTURE_SIZE;

console.log('Opening shared memory...');

const sharedMem = new SharedMemory(SHARED_MEMORY_NAME, SHARED_MEMORY_SIZE);

console.log('Shared memory created!');

const width = 800;
const height = 600;
let frameNumber = 0;

// Create header buffer
const headerBuffer = Buffer.alloc(HEADER_SIZE);

// Create pixel buffer
const pixelBuffer = Buffer.alloc(width * height * 4);

function writeFrame() {
    // Write header
    headerBuffer.writeUInt32LE(width, 0);
    headerBuffer.writeUInt32LE(height, 4);
    headerBuffer.writeUInt32LE(frameNumber, 8);
    headerBuffer.writeUInt32LE(1, 12); // ready = true
    
    sharedMem.write(headerBuffer, 0);
    
    // Generate rainbow gradient
    const hue = (frameNumber * 2) % 360;
    
    for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x++) {
            const i = (y * width + x) * 4;
            const h = (hue + x / width * 360) % 360;
            
            // Simple HSV to RGB
            const c = 1;
            const xVal = c * (1 - Math.abs((h / 60) % 2 - 1));
            
            let r, g, b;
            if (h < 60) { r = c; g = xVal; b = 0; }
            else if (h < 120) { r = xVal; g = c; b = 0; }
            else if (h < 180) { r = 0; g = c; b = xVal; }
            else if (h < 240) { r = 0; g = xVal; b = c; }
            else if (h < 300) { r = xVal; g = 0; b = c; }
            else { r = c; g = 0; b = xVal; }
            
            pixelBuffer[i + 0] = Math.floor(b * 255); // B
            pixelBuffer[i + 1] = Math.floor(g * 255); // G
            pixelBuffer[i + 2] = Math.floor(r * 255); // R
            pixelBuffer[i + 3] = 255;                  // A
        }
    }
    
    // Write pixel data
    sharedMem.write(pixelBuffer, HEADER_SIZE);
    
    frameNumber++;
    
    if (frameNumber % 60 === 0) {
        console.log('Wrote frame', frameNumber);
    }
}

console.log('\nWriting rainbow animation...');
console.log('Start the VR overlay app in another terminal!');
console.log('Press Ctrl+C to exit\n');

setInterval(writeFrame, 16); // ~60fps