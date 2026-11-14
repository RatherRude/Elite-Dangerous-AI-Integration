"""SoundCard device routing and the application's mono PCM16 boundary."""

import sys
from contextlib import contextmanager
from time import monotonic, sleep

import numpy as np


DEFAULT_DEVICE = "default"
DEFAULT_ALIASES = (None, "", "default", "pulse")


@contextmanager
def audio_session():
    import soundcard

    initialized = False
    if sys.platform == "win32":
        import pythoncom

        try:
            pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
            initialized = True
        except pythoncom.com_error as error:
            if error.hresult != -2147417850:
                raise
    try:
        yield soundcard
    finally:
        if initialized:
            pythoncom.CoUninitialize()


def device_id(device) -> str:
    if sys.platform == "darwin":
        import ctypes
        from soundcard.coreaudio import _CoreAudio, _ffi

        uid = _CoreAudio.get_property(device.id, int.from_bytes(b"uid ", "big"), "CFStringRef")
        try:
            return "coreaudio:" + _CoreAudio.CFString_to_str(uid)
        finally:
            foundation = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
            foundation.CFRelease.argtypes = [ctypes.c_void_p]
            foundation.CFRelease.restype = None
            foundation.CFRelease(int(_ffi.cast("uintptr_t", uid[0])))
    return str(device.id)


def device_labels(direction: str) -> dict[str, str]:
    with audio_session() as soundcard:
        devices = soundcard.all_microphones() if direction == "input" else soundcard.all_speakers()
        labels = {DEFAULT_DEVICE: "System default"}
        for device in devices:
            identifier = device_id(device)
            labels[identifier] = f"{device.name} [{identifier}]"
        return labels


def resolve_device(soundcard, selection, direction: str):
    if selection in DEFAULT_ALIASES:
        device = soundcard.default_microphone() if direction == "input" else soundcard.default_speaker()
        if device is None:
            raise RuntimeError(f"No default audio {direction} device available")
        return device
    devices = soundcard.all_microphones() if direction == "input" else soundcard.all_speakers()
    matches = [device for device in devices if device_id(device) == selection]
    if len(matches) != 1:
        raise ValueError(f"Audio {direction} device {selection!r} is unavailable; select a device again in Settings")
    return matches[0]


class PCMInput:
    def __init__(self, selection, samplerate=16000, blocksize=512):
        self._session = audio_session()
        self._context = None
        soundcard = self._session.__enter__()
        try:
            device = resolve_device(soundcard, selection, "input")
            channels = max(2, device.channels) if sys.platform == "win32" else device.channels
            self._context = device.recorder(samplerate=samplerate, channels=channels, blocksize=blocksize)
            self._recorder = self._context.__enter__()
        except BaseException:
            self._session.__exit__(*sys.exc_info())
            raise

    def read(self, frames: int) -> bytes:
        samples = np.asarray(self._recorder.record(numframes=frames), dtype=np.float32)
        if samples.ndim == 2:
            samples = samples.mean(axis=1)
        samples = np.nan_to_num(samples)
        return np.clip(np.rint(samples * 32768), -32768, 32767).astype("<i2").tobytes()

    def close(self):
        context, self._context = self._context, None
        if context is not None:
            try:
                context.__exit__(None, None, None)
            finally:
                self._session.__exit__(None, None, None)


class PCMOutput:
    """Thread-owned player; abort requests never touch a native stream."""

    def __init__(self, selection, interrupted, samplerate=24000, blocksize=480):
        self.selection = selection
        self.interrupted = interrupted
        self.samplerate = samplerate
        self.blocksize = blocksize
        self._context = None

    def _open(self):
        self._session = audio_session()
        soundcard = self._session.__enter__()
        try:
            device = resolve_device(soundcard, self.selection, "output")
            context = device.player(samplerate=self.samplerate, channels=device.channels, blocksize=self.blocksize)
            self._player = context.__enter__()
            self._context = context
            self._deadline = monotonic()
        except BaseException:
            self._session.__exit__(*sys.exc_info())
            raise

    def write(self, pcm: bytes):
        if not pcm or self.interrupted():
            return
        if self._context is None:
            self._open()
        samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
        for offset in range(0, len(samples), self.blocksize):
            if self.interrupted():
                break
            block = samples[offset:offset + self.blocksize]
            self._deadline = max(self._deadline, monotonic()) + len(block) / self.samplerate
            self._player.play(block)
            self._wait_until(self._deadline - self.blocksize / self.samplerate)

    def _wait_until(self, deadline):
        while not self.interrupted():
            remaining = deadline - monotonic()
            if remaining <= 0:
                break
            sleep(min(remaining, 0.01))

    def finish(self):
        if self._context is not None:
            try:
                if not self.interrupted():
                    self.write(bytes(int(self.samplerate * 0.1) * 2))
                    self._wait_until(max(self._deadline, monotonic()) + 0.1)
            finally:
                self.close()

    def close(self):
        context, self._context = self._context, None
        if context is not None:
            try:
                context.__exit__(None, None, None)
            finally:
                self._session.__exit__(None, None, None)
