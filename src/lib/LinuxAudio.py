"""PulseAudio client streams (also supported by pipewire-pulse).

Only the public libpulse ABI is used. Each stream owns a context and a
nonblocking mainloop; no audio thread or server-wide settings are shared.
"""

import ctypes as ct
import threading
from time import monotonic, sleep


class AudioError(OSError):
    pass


class SampleSpec(ct.Structure):
    _fields_ = [("format", ct.c_int), ("rate", ct.c_uint32), ("channels", ct.c_uint8)]


class BufferAttr(ct.Structure):
    _fields_ = [(name, ct.c_uint32) for name in ("maxlength", "tlength", "prebuf", "minreq", "fragsize")]


class DeviceInfo(ct.Structure):
    """Common leading fields of pa_sink_info and pa_source_info."""

    _fields_ = [("name", ct.c_char_p), ("index", ct.c_uint32), ("description", ct.c_char_p)]


DeviceCallback = ct.CFUNCTYPE(None, ct.c_void_p, ct.POINTER(DeviceInfo), ct.c_int, ct.c_void_p)
SuccessCallback = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_int, ct.c_void_p)
PA_STREAM_DONT_MOVE = 0x200
PA_CONTEXT_NOAUTOSPAWN = 1
PA_SAMPLE_S16LE = 3
PA_CONTEXT_READY = 4
PA_STREAM_READY = 2
TIMEOUT = 5.0


def _load_library():
    try:
        library = ct.CDLL("libpulse.so.0")
    except OSError as error:
        raise AudioError("Linux audio requires libpulse.so.0 and a running PulseAudio or pipewire-pulse server") from error
    pointer = ct.c_void_p
    integer = ct.c_int
    size = ct.c_size_t
    signatures = {
        "pa_mainloop_new": (pointer, []),
        "pa_mainloop_get_api": (pointer, [pointer]),
        "pa_mainloop_iterate": (integer, [pointer, integer, pointer]),
        "pa_mainloop_free": (None, [pointer]),
        "pa_context_new": (pointer, [pointer, ct.c_char_p]),
        "pa_context_connect": (integer, [pointer, ct.c_char_p, integer, pointer]),
        "pa_context_get_state": (integer, [pointer]),
        "pa_context_errno": (integer, [pointer]),
        "pa_strerror": (ct.c_char_p, [integer]),
        "pa_context_disconnect": (None, [pointer]),
        "pa_context_unref": (None, [pointer]),
        "pa_context_get_sink_info_list": (pointer, [pointer, DeviceCallback, pointer]),
        "pa_context_get_source_info_list": (pointer, [pointer, DeviceCallback, pointer]),
        "pa_operation_get_state": (integer, [pointer]),
        "pa_operation_cancel": (None, [pointer]),
        "pa_operation_unref": (None, [pointer]),
        "pa_stream_new": (pointer, [pointer, ct.c_char_p, ct.POINTER(SampleSpec), pointer]),
        "pa_stream_connect_playback": (integer, [pointer, ct.c_char_p, ct.POINTER(BufferAttr), integer, pointer, pointer]),
        "pa_stream_connect_record": (integer, [pointer, ct.c_char_p, ct.POINTER(BufferAttr), integer]),
        "pa_stream_get_state": (integer, [pointer]),
        "pa_stream_get_device_name": (ct.c_char_p, [pointer]),
        "pa_stream_writable_size": (size, [pointer]),
        "pa_stream_write": (integer, [pointer, pointer, size, pointer, ct.c_int64, integer]),
        "pa_stream_peek": (integer, [pointer, ct.POINTER(pointer), ct.POINTER(size)]),
        "pa_stream_drop": (integer, [pointer]),
        "pa_stream_drain": (pointer, [pointer, SuccessCallback, pointer]),
        "pa_stream_cork": (pointer, [pointer, integer, SuccessCallback, pointer]),
        "pa_stream_flush": (pointer, [pointer, SuccessCallback, pointer]),
        "pa_stream_disconnect": (integer, [pointer]),
        "pa_stream_unref": (None, [pointer]),
    }
    for name, (result, arguments) in signatures.items():
        function = getattr(library, name)
        function.restype = result
        function.argtypes = arguments
    return library


class PulseConnection:
    def __init__(self):
        self.closed = threading.Event()
        self.lock = threading.RLock()
        self.library = _load_library()
        self.mainloop = None
        self.context = None
        self.stream = None
        try:
            self.mainloop = self.library.pa_mainloop_new()
            if not self.mainloop:
                raise AudioError("Unable to allocate PulseAudio mainloop")
            self.context = self.library.pa_context_new(self.library.pa_mainloop_get_api(self.mainloop), b"COVAS:NEXT")
            if not self.context:
                raise AudioError("Unable to allocate PulseAudio context")
            self.check(self.library.pa_context_connect(self.context, None, PA_CONTEXT_NOAUTOSPAWN, None))
            self.wait(lambda: self.library.pa_context_get_state(self.context) == PA_CONTEXT_READY)
        except BaseException:
            self.close()
            raise

    def error(self):
        message = self.library.pa_strerror(self.library.pa_context_errno(self.context))
        return AudioError(f"PulseAudio: {message.decode(errors='replace')}; check the audio server and selected device")

    def check(self, result):
        if result < 0:
            raise self.error()
        return result

    def pump(self):
        if self.closed.is_set():
            raise AudioError("Audio stream is closed")
        self.check(self.library.pa_mainloop_iterate(self.mainloop, 0, None))
        if self.library.pa_context_get_state(self.context) in (5, 6):
            raise self.error()
        if self.stream and self.library.pa_stream_get_state(self.stream) in (3, 4):
            raise self.error()

    def wait(self, ready):
        deadline = monotonic() + TIMEOUT
        while True:
            self.pump()
            if ready():
                return
            if monotonic() >= deadline:
                raise AudioError("PulseAudio timed out; check the audio server and selected device")
            sleep(0.005)

    def operation(self, operation):
        if not operation:
            raise self.error()
        try:
            self.wait(lambda: self.library.pa_operation_get_state(operation) != 0)
        finally:
            self.library.pa_operation_cancel(operation)
            self.library.pa_operation_unref(operation)

    def devices(self, recording):
        devices = {}
        result = []

        @DeviceCallback
        def callback(context, info, end, userdata):
            if end:
                result.append(end)
            elif info and info.contents.name:
                name = info.contents.name.decode("utf-8", errors="replace")
                description = (info.contents.description or info.contents.name).decode("utf-8", errors="replace")
                devices[name] = description

        function = self.library.pa_context_get_source_info_list if recording else self.library.pa_context_get_sink_info_list
        self.operation(function(self.context, callback, None))
        if result != [1]:
            raise self.error()
        return devices

    def close(self):
        self.closed.set()
        with self.lock:
            if self.stream:
                self.library.pa_stream_disconnect(self.stream)
                self.library.pa_stream_unref(self.stream)
                self.stream = None
            if self.context:
                self.library.pa_context_disconnect(self.context)
                self.library.pa_context_unref(self.context)
                self.context = None
            if self.mainloop:
                self.library.pa_mainloop_free(self.mainloop)
                self.mainloop = None


def get_device_names(recording: bool) -> list[str]:
    connection = PulseConnection()
    try:
        return ["pulse", *[f"pulse:{name}" for name in connection.devices(recording)]]
    finally:
        connection.close()


def resolve_device(selection: str | None, devices: dict[str, str]) -> bytes | None:
    if selection in (None, "", "pulse", "default"):
        return None
    name = selection.removeprefix("pulse:")
    if name in devices:
        return name.encode()
    matches = [] if selection.startswith("pulse:") else [name for name, description in devices.items() if description == selection]
    if len(matches) == 1:
        return matches[0].encode()
    raise AudioError(f"Selected Linux audio device {selection!r} is unavailable or ambiguous. Reselect a PulseAudio device in Settings.")


class PulseStream(PulseConnection):
    def __init__(self, selection: str | None, rate: int, recording: bool = False, frames_per_buffer: int = 1024):
        super().__init__()
        self.recording = recording
        self.pending = bytearray()
        try:
            device = resolve_device(selection, self.devices(recording))
            spec = SampleSpec(PA_SAMPLE_S16LE, rate, 1)
            self.stream = self.library.pa_stream_new(self.context, b"Microphone" if recording else b"Speech", ct.byref(spec), None)
            if not self.stream:
                raise self.error()
            size = frames_per_buffer * 2
            attributes = BufferAttr(0xFFFFFFFF, max(size * 4, rate // 5 * 2), 0, 0xFFFFFFFF, size)
            if recording:
                self.check(self.library.pa_stream_connect_record(self.stream, device, ct.byref(attributes), PA_STREAM_DONT_MOVE))
            else:
                self.check(self.library.pa_stream_connect_playback(self.stream, device, ct.byref(attributes), PA_STREAM_DONT_MOVE, None, None))
            self.wait(lambda: self.library.pa_stream_get_state(self.stream) == PA_STREAM_READY)
            if device and self.library.pa_stream_get_device_name(self.stream) != device:
                raise AudioError("PulseAudio did not route to the selected device")
        except BaseException:
            self.close()
            raise

    def get_write_available(self):
        with self.lock:
            self.pump()
            available = self.library.pa_stream_writable_size(self.stream)
            if available == ct.c_size_t(-1).value:
                raise self.error()
            return available // 2

    def write(self, data: bytes, exception_on_underflow=False):
        with self.lock:
            offset = 0
            while offset < len(data):
                self.wait(lambda: self.get_write_available() > 0)
                count = min(self.get_write_available() * 2, len(data) - offset)
                buffer = ct.create_string_buffer(data[offset:offset + count])
                self.check(self.library.pa_stream_write(self.stream, buffer, count, None, 0, 0))
                offset += count

    def read(self, frames: int, exception_on_overflow=False) -> bytes:
        with self.lock:
            size = frames * 2

            def receive():
                if len(self.pending) >= size:
                    return True
                pointer = ct.c_void_p()
                length = ct.c_size_t()
                self.check(self.library.pa_stream_peek(self.stream, ct.byref(pointer), ct.byref(length)))
                if length.value:
                    self.pending.extend(ct.string_at(pointer, length.value) if pointer.value else bytes(length.value))
                    self.check(self.library.pa_stream_drop(self.stream))
                return len(self.pending) >= size

            self.wait(receive)
            data = bytes(self.pending[:size])
            del self.pending[:size]
            return data

    def drain(self):
        with self.lock:
            succeeded = []

            @SuccessCallback
            def callback(stream, success, userdata):
                succeeded.append(success)

            self.operation(self.library.pa_stream_drain(self.stream, callback, None))
            if succeeded != [1]:
                raise self.error()

    def _control(self, corked):
        with self.lock:
            succeeded = []

            @SuccessCallback
            def callback(stream, success, userdata):
                succeeded.append(success)

            self.operation(self.library.pa_stream_cork(self.stream, corked, callback, None))
            if not corked:
                if succeeded != [1]:
                    raise self.error()
                return
            self.operation(self.library.pa_stream_flush(self.stream, callback, None))
            if succeeded != [1, 1]:
                raise self.error()

    def start_stream(self):
        self._control(0)

    def stop_stream(self):
        self._control(1)
