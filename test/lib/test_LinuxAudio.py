import ctypes as ct
import importlib
import queue
import threading
from unittest.mock import MagicMock

import pytest

from src.lib import LinuxAudio as audio


@pytest.fixture
def library(monkeypatch):
    library = MagicMock()
    library.pa_mainloop_new.return_value = 1
    library.pa_context_new.return_value = 2
    library.pa_context_connect.return_value = 0
    library.pa_context_get_state.return_value = audio.PA_CONTEXT_READY
    library.pa_mainloop_iterate.return_value = 0
    library.pa_operation_get_state.return_value = 1
    library.pa_stream_get_state.return_value = audio.PA_STREAM_READY
    library.pa_stream_new.side_effect = range(10, 100)
    library.pa_stream_writable_size.return_value = 4096
    library.pa_stream_write.return_value = 0
    library.pa_stream_peek.return_value = 0
    library.pa_stream_drop.return_value = 0
    library.pa_strerror.return_value = b"test server error"
    routes = {}

    def enumerate_devices(context, callback, userdata):
        for index, name in enumerate((b"usb.headset", b"usb.other")):
            info = audio.DeviceInfo(name, index, b"Identical description")
            callback(context, ct.pointer(info), 0, userdata)
        callback(context, None, 1, userdata)
        return 3

    def connect(stream, device, *arguments):
        routes[stream] = device or b"server.default"
        return 0

    def control(stream, *arguments):
        callback, userdata = arguments[-2:]
        callback(stream, 1, userdata)
        return 4

    library.pa_context_get_sink_info_list.side_effect = enumerate_devices
    library.pa_context_get_source_info_list.side_effect = enumerate_devices
    library.pa_stream_connect_playback.side_effect = connect
    library.pa_stream_connect_record.side_effect = connect
    library.pa_stream_get_device_name.side_effect = routes.__getitem__
    library.pa_stream_cork.side_effect = control
    library.pa_stream_flush.side_effect = control
    library.pa_stream_drain.side_effect = control
    monkeypatch.setattr(audio, '_load_library', lambda: library)
    return library


@pytest.mark.parametrize('recording', [True, False])
def test_enumeration_uses_server_and_stable_unique_names(library, recording):
    assert audio.get_device_names(recording) == ['pulse', 'pulse:usb.headset', 'pulse:usb.other']
    function = library.pa_context_get_source_info_list if recording else library.pa_context_get_sink_info_list
    function.assert_called_once()
    library.pa_context_disconnect.assert_called_once_with(2)
    library.pa_context_unref.assert_called_once_with(2)
    library.pa_mainloop_free.assert_called_once_with(1)


def test_independent_sink_source_and_sample_rates(library):
    specifications = []

    def create(context, name, spec, channel_map):
        value = ct.cast(spec, ct.POINTER(audio.SampleSpec)).contents
        specifications.append((value.format, value.rate, value.channels))
        return len(specifications) + 10

    library.pa_stream_new.side_effect = create
    output = audio.PulseStream('pulse:usb.other', 24000)
    microphone = audio.PulseStream('pulse:usb.headset', 16000, recording=True)
    assert specifications == [(audio.PA_SAMPLE_S16LE, 24000, 1), (audio.PA_SAMPLE_S16LE, 16000, 1)]
    playback = library.pa_stream_connect_playback.call_args.args
    capture = library.pa_stream_connect_record.call_args.args
    assert playback[1] == b'usb.other'
    assert capture[1] == b'usb.headset'
    assert playback[3] == capture[3] == audio.PA_STREAM_DONT_MOVE
    attributes = ct.cast(playback[2], ct.POINTER(audio.BufferAttr)).contents
    assert attributes.prebuf == 0
    assert library.pa_stream_get_device_name.call_count == 2
    output.close()
    microphone.close()
    assert library.pa_context_unref.call_count == 2


@pytest.mark.parametrize('selection', [None, '', 'pulse', 'default'])
def test_default_aliases_are_not_global_default_changes(library, selection):
    stream = audio.PulseStream(selection, 24000)
    assert library.pa_stream_connect_playback.call_args.args[1] is None
    stream.close()


def test_legacy_selection_requires_exact_unambiguous_match():
    devices = {'sink.one': 'Speaker', 'sink.two': 'Duplicate', 'sink.three': 'Duplicate'}
    assert audio.resolve_device('sink.one', devices) == b'sink.one'
    assert audio.resolve_device('Speaker', devices) == b'sink.one'
    for selection in ('Duplicate', 'sink', 'hw:0', 'pulse:missing'):
        with pytest.raises(audio.AudioError, match='Reselect'):
            audio.resolve_device(selection, devices)
    with pytest.raises(audio.AudioError, match='Reselect'):
        audio.resolve_device('pulse:missing', {'other': 'pulse:missing'})


def test_missing_selection_does_not_open_default(library):
    with pytest.raises(audio.AudioError, match='unavailable'):
        audio.PulseStream('pulse:missing', 24000)
    library.pa_stream_new.assert_not_called()
    library.pa_context_unref.assert_called_once()


def test_route_mismatch_fails_and_releases_stream(library):
    library.pa_stream_get_device_name.side_effect = None
    library.pa_stream_get_device_name.return_value = b'wrong.sink'
    with pytest.raises(audio.AudioError, match='did not route'):
        audio.PulseStream('pulse:usb.other', 24000)
    library.pa_stream_disconnect.assert_called_once()
    library.pa_stream_unref.assert_called_once()
    library.pa_context_unref.assert_called_once()


def test_playback_partial_writes_and_frame_units(library):
    stream = audio.PulseStream('pulse', 24000)
    library.pa_stream_writable_size.return_value = 4
    assert stream.get_write_available() == 2
    chunks = []
    library.pa_stream_write.side_effect = lambda handle, data, size, *args: chunks.append(ct.string_at(data, size)) or 0
    stream.write(b'abcdefghij')
    assert chunks == [b'abcd', b'efgh', b'ij']
    stream.close()


def test_capture_buffers_fragments_and_silence_holes(library):
    stream = audio.PulseStream('pulse', 16000, recording=True)
    buffer = ct.create_string_buffer(b'abcdef')
    fragments = iter([(ct.cast(buffer, ct.c_void_p).value, 6), (None, 4)])

    def peek(handle, pointer, length):
        address, size = next(fragments)
        ct.cast(pointer, ct.POINTER(ct.c_void_p))[0] = address
        ct.cast(length, ct.POINTER(ct.c_size_t))[0] = size
        return 0

    library.pa_stream_peek.side_effect = peek
    assert stream.read(2) == b'abcd'
    assert stream.read(3) == b'ef\x00\x00\x00\x00'
    assert library.pa_stream_drop.call_count == 2
    stream.close()


def test_capture_returns_pending_frames_without_waiting_for_more(library):
    stream = audio.PulseStream('pulse', 16000, recording=True)
    stream.pending.extend(b'abcd')
    assert stream.read(2) == b'abcd'
    library.pa_stream_peek.assert_not_called()
    stream.close()


def test_cork_flush_and_idempotent_cleanup(library):
    stream = audio.PulseStream('pulse', 24000)
    stream.stop_stream()
    stream.start_stream()
    assert [call.args[1] for call in library.pa_stream_cork.call_args_list] == [1, 0]
    library.pa_stream_flush.assert_called_once()
    stream.close()
    stream.close()
    library.pa_stream_unref.assert_called_once()
    library.pa_context_unref.assert_called_once()
    with pytest.raises(audio.AudioError, match='closed'):
        stream.write(b'xx')


@pytest.mark.parametrize('failure', ['server', 'stream', 'timeout', 'write'])
def test_io_failures_are_not_device_fallbacks(library, monkeypatch, failure):
    stream = audio.PulseStream('pulse:usb.headset', 24000)
    if failure == 'server':
        library.pa_context_get_state.return_value = 5
    elif failure == 'stream':
        library.pa_stream_get_state.return_value = 3
    elif failure == 'timeout':
        library.pa_stream_writable_size.return_value = 0
        monkeypatch.setattr(audio, 'TIMEOUT', 0)
    else:
        library.pa_stream_write.return_value = -1
    with pytest.raises(audio.AudioError):
        stream.write(b'xx')
    assert library.pa_stream_connect_playback.call_count == 1
    stream.close()
    library.pa_stream_unref.assert_called_once()


def test_failed_connection_and_absent_library(library, monkeypatch):
    library.pa_context_connect.return_value = -1
    with pytest.raises(audio.AudioError, match='test server error'):
        audio.PulseConnection()
    library.pa_context_unref.assert_called_once()
    library.pa_mainloop_free.assert_called_once()
    monkeypatch.undo()
    monkeypatch.setattr(ct, 'CDLL', MagicMock(side_effect=OSError('missing')))
    with pytest.raises(audio.AudioError, match='libpulse.so.0'):
        audio.PulseConnection()


def test_failed_enumeration_cancels_operation_and_closes_context(library, monkeypatch):
    library.pa_context_get_sink_info_list.side_effect = lambda context, callback, userdata: 3
    library.pa_operation_get_state.return_value = 0
    monkeypatch.setattr(audio, 'TIMEOUT', 0)
    with pytest.raises(audio.AudioError, match='timed out'):
        audio.get_device_names(False)
    library.pa_operation_cancel.assert_called_once_with(3)
    library.pa_operation_unref.assert_called_once_with(3)
    library.pa_context_unref.assert_called_once()


def test_failed_stream_connection_releases_all_resources(library):
    library.pa_stream_connect_record.side_effect = None
    library.pa_stream_connect_record.return_value = -1
    with pytest.raises(audio.AudioError, match='test server error'):
        audio.PulseStream('pulse:usb.headset', 16000, recording=True)
    library.pa_stream_unref.assert_called_once()
    library.pa_context_unref.assert_called_once()
    library.pa_mainloop_free.assert_called_once()


def test_close_interrupts_blocked_read(library):
    stream = audio.PulseStream('pulse', 16000, recording=True)
    entered = threading.Event()
    errors = []

    def peek(*args):
        entered.set()
        return 0

    def read():
        try:
            stream.read(512)
        except audio.AudioError as error:
            errors.append(error)

    library.pa_stream_peek.side_effect = peek
    worker = threading.Thread(target=read)
    worker.start()
    assert entered.wait(1)
    stream.close()
    worker.join(1)
    assert not worker.is_alive()
    assert len(errors) == 1
    library.pa_stream_unref.assert_called_once()


@pytest.mark.parametrize('platform', ['linux', 'darwin', 'win32'])
def test_config_and_stream_dispatch(monkeypatch, platform):
    config = importlib.import_module('src.lib.Config')
    tts_module = importlib.import_module('src.lib.TTS')
    stt_module = importlib.import_module('src.lib.STT')
    monkeypatch.setattr('sys.platform', platform)
    names = MagicMock(side_effect=lambda recording: ['pulse', 'pulse:source' if recording else 'pulse:sink'])
    monkeypatch.setattr(audio, 'get_device_names', names)
    factory = MagicMock()
    monkeypatch.setattr(tts_module, 'PulseStream', factory)
    monkeypatch.setattr(stt_module, 'PulseStream', factory)
    portaudio = MagicMock()
    portaudio.get_default_host_api_info.return_value = {'deviceCount': 0}
    portaudio.get_default_input_device_info.return_value = {'name': 'Native microphone'}
    portaudio.get_default_output_device_info.return_value = {'name': 'Native speaker'}
    monkeypatch.setattr('pyaudio.PyAudio', lambda: portaudio)
    tts = object.__new__(tts_module.TTS)
    tts.p = portaudio
    tts.output_device = 'pulse:sink'
    tts.output_format = 8
    tts.frames_per_buffer = 1024
    stt = object.__new__(stt_module.STT)
    stt.input_device_name = 'pulse:source'
    stt.rate = 16000
    stt.frames_per_buffer = 512
    tts._open_output_stream()
    stt._get_microphone()
    if platform == 'linux':
        assert config.get_input_device_names() == ['pulse', 'pulse:source']
        assert config.get_output_device_names() == ['pulse', 'pulse:sink']
        assert factory.call_args_list[0].args == ('pulse:sink',)
        assert factory.call_args_list[0].kwargs['rate'] == 24000
        assert factory.call_args_list[1].args == ('pulse:source',)
        assert factory.call_args_list[1].kwargs['recording'] is True
        assert factory.call_args_list[1].kwargs['rate'] == 16000
        portaudio.open.assert_not_called()
    else:
        assert config.get_input_device_names() == ['Native microphone']
        assert config.get_output_device_names() == ['Native speaker']
        factory.assert_not_called()
        names.assert_not_called()
        assert portaudio.open.call_count == 2


def test_config_server_failure_does_not_enumerate_alsa(monkeypatch):
    config = importlib.import_module('src.lib.Config')
    monkeypatch.setattr('sys.platform', 'linux')
    monkeypatch.setattr(audio, 'get_device_names', MagicMock(side_effect=audio.AudioError('offline')))
    portaudio = MagicMock()
    monkeypatch.setattr('pyaudio.PyAudio', portaudio)
    assert config.get_input_device_names() == []
    assert config.get_output_device_names() == []
    portaudio.assert_not_called()


def test_linux_device_open_errors_do_not_fall_back(monkeypatch):
    tts_module = importlib.import_module('src.lib.TTS')
    stt_module = importlib.import_module('src.lib.STT')
    monkeypatch.setattr('sys.platform', 'linux')
    factory = MagicMock(side_effect=audio.AudioError('selected device unavailable'))
    monkeypatch.setattr(tts_module, 'PulseStream', factory)
    monkeypatch.setattr(stt_module, 'PulseStream', factory)
    portaudio = MagicMock()
    monkeypatch.setattr('pyaudio.PyAudio', portaudio)
    tts = object.__new__(tts_module.TTS)
    tts.output_device = 'pulse:missing'
    tts.frames_per_buffer = 1024
    stt = object.__new__(stt_module.STT)
    stt.input_device_name = 'pulse:missing'
    stt.rate = 16000
    stt.frames_per_buffer = 512
    with pytest.raises(audio.AudioError, match='selected device unavailable'):
        tts._open_output_stream()
    with pytest.raises(audio.AudioError, match='selected device unavailable'):
        stt._get_microphone()
    assert factory.call_count == 2
    portaudio.assert_not_called()


def test_capture_closes_on_processing_error(monkeypatch):
    module = importlib.import_module('src.lib.STT')
    stt = object.__new__(module.STT)
    source = MagicMock()
    monkeypatch.setattr(module.STT, '_get_microphone', lambda self: source)
    monkeypatch.setattr(module.STT, '_capture_continuous', MagicMock(side_effect=RuntimeError('vad')))
    with pytest.raises(RuntimeError, match='vad'):
        stt._listen_continuous_loop()
    source.close.assert_called_once()
    assert not stt.recording


def test_playback_closes_on_processing_error(monkeypatch):
    module = importlib.import_module('src.lib.TTS')
    tts = object.__new__(module.TTS)
    tts._shutdown = threading.Event()
    stream = MagicMock()
    monkeypatch.setattr(module.TTS, '_open_output_stream', lambda self: stream)
    monkeypatch.setattr(module.TTS, '_run_playback', MagicMock(side_effect=RuntimeError('playback')))
    with pytest.raises(RuntimeError, match='playback'):
        tts._playback_loop()
    stream.close.assert_called_once()
    assert tts._stream is None
    assert not tts._is_playing


def test_linux_tts_does_not_initialize_portaudio_and_quits(monkeypatch):
    module = importlib.import_module('src.lib.TTS')
    monkeypatch.setattr('sys.platform', 'linux')
    thread = MagicMock()
    monkeypatch.setattr(module.threading, 'Thread', MagicMock(return_value=thread))
    portaudio = MagicMock()
    monkeypatch.setattr('pyaudio.PyAudio', portaudio)
    tts = module.TTS(output_device='pulse:usb.other')
    assert tts.sample_size == 2
    assert tts.p is None
    portaudio.assert_not_called()
    stream = MagicMock()
    tts._stream = stream
    tts.quit()
    assert tts._shutdown.is_set()
    stream.close.assert_called_once()
    thread.join.assert_called_once_with(timeout=6)


def test_stt_quit_closes_linux_source_and_wakes_retry(monkeypatch):
    module = importlib.import_module('src.lib.STT')
    monkeypatch.setattr('sys.platform', 'linux')
    stt = object.__new__(module.STT)
    stt._shutdown = threading.Event()
    stt._source = MagicMock()
    stt._thread = MagicMock()
    stt.listening = True
    stt.quit()
    assert not stt.listening
    assert stt._shutdown.is_set()
    stt._source.close.assert_called_once()
    stt._thread.join.assert_called_once_with(timeout=6)


def test_playback_drain_pumps_until_buffered_audio_completes(library):
    stream = audio.PulseStream('pulse', 24000)
    stream.write(b'last chunk')
    callbacks = []

    def drain(handle, callback, userdata):
        callbacks.append(callback)
        library.pa_operation_get_state.return_value = 0
        return 5

    def pump(*args):
        callbacks.pop()(stream.stream, 1, None)
        library.pa_operation_get_state.return_value = 1
        return 0

    library.pa_stream_drain.side_effect = drain
    library.pa_mainloop_iterate.side_effect = pump
    stream.drain()

    library.pa_stream_drain.assert_called_once()
    library.pa_operation_unref.assert_called_with(5)
    stream.close()


def test_playback_drain_failure_is_reported(library):
    stream = audio.PulseStream('pulse', 24000)

    def drain(handle, callback, userdata):
        callback(handle, 0, userdata)
        return 5

    library.pa_stream_drain.side_effect = drain
    with pytest.raises(audio.AudioError, match='test server error'):
        stream.drain()
    stream.close()


@pytest.mark.parametrize('item_type', ['speech', 'audio_file'])
def test_linux_playback_drains_before_completion(monkeypatch, item_type):
    module = importlib.import_module('src.lib.TTS')
    monkeypatch.setattr('sys.platform', 'linux')
    tts = object.__new__(module.TTS)
    tts._shutdown = threading.Event()
    tts.read_queue = queue.Queue()
    events = []
    tts.read_queue.put({
        'type': item_type,
        'text': 'Hello',
        'file_path': 'clip.wav',
        'on_complete': lambda: events.append('complete'),
    })
    monkeypatch.setattr(tts, '_normalize_queue_item', lambda item: item)
    monkeypatch.setattr(tts, '_playback_one', lambda *args: events.append('write'))
    monkeypatch.setattr(tts, '_playback_audio_file', lambda *args: events.append('write'))
    monkeypatch.setattr(module, 'sleep', lambda seconds: tts._shutdown.set())
    stream = MagicMock()
    stream.drain.side_effect = lambda: events.append('drain')

    tts._run_playback(stream)

    assert events == ['write', 'drain', 'complete']
