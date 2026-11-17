import ast
import sys
from contextlib import contextmanager
from importlib.metadata import distribution
from itertools import chain, repeat
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from src.lib import Audio


@pytest.fixture
def backend(monkeypatch):
    microphone = MagicMock(id="source-usb", name="USB", channels=2)
    speaker = MagicMock(id="sink-usb", name="USB", channels=2)
    microphone.name = speaker.name = 'USB'
    soundcard = MagicMock()
    soundcard.all_microphones.return_value = [microphone]
    soundcard.all_speakers.return_value = [speaker]
    soundcard.default_microphone.return_value = microphone
    soundcard.default_speaker.return_value = speaker
    session = MagicMock()

    @contextmanager
    def audio_session():
        session.enter()
        try:
            yield soundcard
        finally:
            session.exit()

    monkeypatch.setattr(Audio, 'audio_session', audio_session)
    monkeypatch.setattr(Audio.sys, 'platform', 'linux')
    return SimpleNamespace(soundcard=soundcard, microphone=microphone, speaker=speaker, session=session)


@pytest.mark.parametrize('direction,identifier', [('input', 'source-usb'), ('output', 'sink-usb')])
def test_exact_independent_device_routing(backend, direction, identifier):
    device = Audio.resolve_device(backend.soundcard, identifier, direction)
    assert device.id == identifier
    backend.soundcard.get_microphone.assert_not_called()
    backend.soundcard.get_speaker.assert_not_called()
    backend.soundcard.default_speaker.assert_not_called()
    backend.soundcard.default_microphone.assert_not_called()


@pytest.mark.parametrize('selection', ['USB', 'usb', 'sink', 'removed-device', 'source-usb'])
def test_invalid_output_selection_uses_default_without_fuzzy_matching(backend, selection):
    default = MagicMock(id='system-default')
    backend.soundcard.default_speaker.return_value = default
    assert Audio.resolve_device(backend.soundcard, selection, 'output') is default
    backend.soundcard.default_speaker.assert_called_once()
    backend.soundcard.get_speaker.assert_not_called()
    backend.soundcard.default_microphone.assert_not_called()


def test_invalid_input_selection_uses_default_and_warns(backend, monkeypatch):
    from src.lib import Logger

    warning = MagicMock()
    monkeypatch.setattr(Logger, 'log', warning)
    assert Audio.resolve_device(backend.soundcard, 'old microphone name', 'input') is backend.microphone
    backend.soundcard.default_microphone.assert_called_once()
    backend.soundcard.default_speaker.assert_not_called()
    assert warning.call_args.args[0] == 'warn'
    assert 'system default' in warning.call_args.args[1]


@pytest.mark.parametrize('direction', ['input', 'output'])
def test_invalid_selection_without_default_reports_error(backend, direction):
    backend.soundcard.default_microphone.return_value = None
    backend.soundcard.default_speaker.return_value = None
    with pytest.raises(RuntimeError, match=f'No default audio {direction}'):
        Audio.resolve_device(backend.soundcard, 'removed-device', direction)


@pytest.mark.parametrize('selection', Audio.DEFAULT_ALIASES)
@pytest.mark.parametrize('direction', ['input', 'output'])
def test_intentional_default_aliases(backend, selection, direction):
    expected = backend.microphone if direction == 'input' else backend.speaker
    assert Audio.resolve_device(backend.soundcard, selection, direction) is expected


def test_duplicate_names_remain_distinct(backend):
    other = MagicMock(id='sink-other')
    other.name = 'USB'
    backend.soundcard.all_speakers.return_value.append(other)
    labels = Audio.device_labels('output')
    assert list(labels) == ['default', 'sink-usb', 'sink-other']
    assert labels['sink-usb'] == labels['sink-other'] == 'USB'
    assert Audio.resolve_device(backend.soundcard, 'sink-other', 'output').id == 'sink-other'


def test_invalid_device_fallback_opens_streams_on_default(backend):
    source = Audio.PCMInput('legacy microphone')
    backend.microphone.recorder.assert_called_once()
    source.close()
    output = Audio.PCMOutput('legacy speaker', lambda: False)
    output._open()
    backend.speaker.player.assert_called_once()
    output.close()


def test_mac_persistent_uid_not_transient_object_id(monkeypatch):
    monkeypatch.setattr(Audio.sys, 'platform', 'darwin')
    coreaudio = MagicMock()
    coreaudio._CoreAudio.CFString_to_str.return_value = 'persistent-usb-uid'
    coreaudio._ffi.cast.return_value = 123
    monkeypatch.setitem(sys.modules, 'soundcard.coreaudio', coreaudio)
    import ctypes
    library = MagicMock()
    monkeypatch.setattr(ctypes, 'CDLL', lambda path: library)
    assert Audio.device_id(SimpleNamespace(id=42)) == 'coreaudio:persistent-usb-uid'
    coreaudio._CoreAudio.get_property.assert_called_once_with(42, int.from_bytes(b'uid ', 'big'), 'CFStringRef')
    library.CFRelease.assert_called_once_with(123)


@pytest.mark.parametrize('platform,channels,expected', [('linux', 1, 1), ('darwin', 2, 2), ('win32', 1, 2), ('win32', 6, 6)])
def test_capture_channels_and_downmix(backend, monkeypatch, platform, channels, expected):
    monkeypatch.setattr(Audio.sys, 'platform', platform)
    backend.microphone.channels = channels
    recorder = backend.microphone.recorder.return_value.__enter__.return_value
    recorder.record.return_value = np.array([[1, 1], [-1, -1], [0.5, -0.5], [2, 2]], np.float32)
    source = Audio.PCMInput('default')
    backend.microphone.recorder.assert_called_once_with(samplerate=16000, channels=expected, blocksize=512)
    assert np.frombuffer(source.read(4), dtype='<i2').tolist() == [32767, -32768, 0, 32767]
    recorder.record.assert_called_once_with(numframes=4)
    source.close()
    source.close()
    backend.microphone.recorder.return_value.__exit__.assert_called_once()
    backend.session.exit.assert_called_once()


def test_capture_failure_releases_session(backend):
    backend.microphone.recorder.side_effect = RuntimeError('Device disconnected')
    with pytest.raises(RuntimeError, match='disconnected'):
        Audio.PCMInput('source-usb')
    backend.session.exit.assert_called_once()


@pytest.fixture
def clock(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(Audio, 'monotonic', lambda: now[0])
    monkeypatch.setattr(Audio, 'sleep', lambda duration: now.__setitem__(0, now[0] + duration))
    return now


def test_output_conversion_short_clip_completion_and_cleanup(backend, clock):
    output = Audio.PCMOutput('sink-usb', lambda: False)
    samples = np.array([-32768, 0, 32767], dtype='<i2')
    output.write(samples.tobytes())
    player = backend.speaker.player.return_value.__enter__.return_value
    np.testing.assert_allclose(player.play.call_args.args[0], [-1, 0, 32767 / 32768])
    assert player.play.call_args.args[0].dtype == np.float32
    backend.speaker.player.assert_called_once_with(samplerate=24000, channels=2, blocksize=480)
    output.finish()
    assert clock[0] >= 0.2
    assert player.play.call_count > 1
    backend.speaker.player.return_value.__exit__.assert_called_once()
    output.close()
    backend.session.exit.assert_called_once()


@pytest.mark.parametrize('platform,module', [('linux', 'pulseaudio'), ('darwin', 'coreaudio'), ('win32', 'mediafoundation')])
def test_playback_wait_option_matches_pinned_backend_signature(backend, clock, monkeypatch, platform, module):
    source = distribution('SoundCard').locate_file(f'soundcard/{module}.py').read_text()
    player_class = next(node for node in ast.parse(source).body if isinstance(node, ast.ClassDef) and node.name == '_Player')
    play = next(node for node in player_class.body if isinstance(node, ast.FunctionDef) and node.name == 'play')
    parameters = [argument.arg for argument in play.args.args]
    assert parameters == (['self', 'data', 'wait'] if module == 'coreaudio' else ['self', 'data'])

    calls = []

    def play_without_wait(data):
        calls.append({})

    def play_with_wait(data, wait=True):
        calls.append({'wait': wait})

    player = backend.speaker.player.return_value.__enter__.return_value
    player.play = play_with_wait if 'wait' in parameters else play_without_wait
    monkeypatch.setattr(Audio.sys, 'platform', platform)
    if platform == 'darwin':
        monkeypatch.setattr(Audio, 'device_id', lambda device: str(device.id))
    if platform == 'win32':
        monkeypatch.setattr(Audio.PCMOutput, '_write_wasapi', staticmethod(play_without_wait))
    output = Audio.PCMOutput('sink-usb', lambda: False)
    output.write(bytes(1024))
    output.finish()
    assert len(calls) > 2
    assert calls == ([{'wait': False}] * len(calls) if module == 'coreaudio' else [{}] * len(calls))


@pytest.mark.parametrize('frames', [3, 32, 480, 512])
@pytest.mark.parametrize('channels', [1, 2, 6])
def test_wasapi_acquires_and_releases_only_copied_frames(backend, clock, monkeypatch, frames, channels):
    import cffi

    ffi = cffi.FFI()
    monkeypatch.setitem(sys.modules, 'soundcard.mediafoundation', SimpleNamespace(_ffi=ffi))
    monkeypatch.setattr(Audio.sys, 'platform', 'win32')
    player = backend.speaker.player.return_value.__enter__.return_value
    player.channelmap = list(range(channels))
    player._render_available_frames.side_effect = chain([0, 2], repeat(4096))
    buffer = ffi.new('float[]', [13.5] * (4096 * channels))
    player._render_buffer.return_value = [buffer]
    written = []

    def release(count):
        written.append(np.frombuffer(ffi.buffer(buffer, count * channels * 4), dtype=np.float32).copy())

    player._render_release.side_effect = release
    samples = np.arange(frames, dtype='<i2')
    output = Audio.PCMOutput('sink-usb', lambda: False)
    output.write(samples.tobytes())
    acquired = [call.args[0] for call in player._render_buffer.call_args_list]
    released = [call.args[0] for call in player._render_release.call_args_list]
    assert acquired == released
    assert sum(released) == frames
    assert max(released) <= 480
    np.testing.assert_allclose(np.concatenate(written).reshape(-1, channels), np.repeat(samples[:, None] / 32768, channels, axis=1))
    assert buffer[480 * channels] == 13.5
    player.play.assert_not_called()
    output.close()
    backend.speaker.player.return_value.__exit__.assert_called_once()
    backend.session.exit.assert_called_once()


def test_wasapi_interrupt_while_waiting_for_render_space(backend, clock, monkeypatch):
    monkeypatch.setitem(sys.modules, 'soundcard.mediafoundation', SimpleNamespace(_ffi=MagicMock()))
    monkeypatch.setattr(Audio.sys, 'platform', 'win32')
    aborted = [False]
    player = backend.speaker.player.return_value.__enter__.return_value
    player.channelmap = [0, 1]
    player._render_available_frames.return_value = 0
    monkeypatch.setattr(Audio, 'sleep', lambda duration: aborted.__setitem__(0, True))
    output = Audio.PCMOutput('sink-usb', lambda: aborted[0])
    output.write(bytes(1024))
    output.finish()
    player._render_buffer.assert_not_called()
    player._render_release.assert_not_called()
    backend.session.exit.assert_called_once()


def test_abort_stops_submitting_chunks_and_skips_tail(backend, clock):
    aborted = [False]
    output = Audio.PCMOutput('sink-usb', lambda: aborted[0])
    player = backend.speaker.player.return_value.__enter__.return_value
    player.play.side_effect = lambda samples: aborted.__setitem__(0, True)
    output.write(bytes(24000 * 2))
    output.finish()
    assert player.play.call_count == 1
    assert clock[0] == 0
    backend.speaker.player.return_value.__exit__.assert_called_once()


def test_pacing_does_not_double_wait_for_a_blocking_backend(backend, clock):
    output = Audio.PCMOutput('sink-usb', lambda: False)
    player = backend.speaker.player.return_value.__enter__.return_value

    def blocking_play(samples):
        clock[0] += len(samples) / 24000

    player.play.side_effect = blocking_play
    output.write(bytes(24000 * 2))
    assert clock[0] == pytest.approx(1.0)
    output.close()


def test_large_provider_chunk_is_split_and_queue_ahead_is_bounded(backend, clock):
    output = Audio.PCMOutput('sink-usb', lambda: False)
    player = backend.speaker.player.return_value.__enter__.return_value
    output.write(bytes(24000 * 2))
    assert player.play.call_count == 50
    assert max(len(call.args[0]) for call in player.play.call_args_list) == 480
    assert clock[0] == pytest.approx(0.98)
    output.close()


def test_play_failure_can_close_resources(backend, clock):
    output = Audio.PCMOutput('sink-usb', lambda: False)
    backend.speaker.player.return_value.__enter__.return_value.play.side_effect = RuntimeError('Disconnected')
    with pytest.raises(RuntimeError, match='Disconnected'):
        output.write(bytes(960))
    output.close()
    backend.session.exit.assert_called_once()


def test_context_exit_failure_still_releases_session(backend, clock):
    output = Audio.PCMOutput('sink-usb', lambda: False)
    output.write(bytes(2))
    backend.speaker.player.return_value.__exit__.side_effect = RuntimeError('Exit failed')
    with pytest.raises(RuntimeError, match='Exit failed'):
        output.finish()
    backend.session.exit.assert_called_once()


def test_windows_com_is_balanced_on_worker_thread(monkeypatch):
    monkeypatch.setattr(Audio.sys, 'platform', 'win32')
    soundcard = MagicMock()
    pythoncom = MagicMock()
    monkeypatch.setitem(sys.modules, 'soundcard', soundcard)
    monkeypatch.setitem(sys.modules, 'pythoncom', pythoncom)
    with Audio.audio_session() as actual:
        assert actual is soundcard
    pythoncom.CoInitializeEx.assert_called_once_with(pythoncom.COINIT_MULTITHREADED)
    pythoncom.CoUninitialize.assert_called_once()
