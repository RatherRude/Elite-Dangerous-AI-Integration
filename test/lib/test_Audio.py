import sys
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from src.lib import Audio


@pytest.fixture
def backend(monkeypatch):
    microphone = MagicMock(id="source-usb", name="USB", channels=2)
    speaker = MagicMock(id="sink-usb", name="USB", channels=2)
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
def test_output_selection_never_matches_names_substrings_or_other_direction(backend, selection):
    with pytest.raises(ValueError, match='select a device again'):
        Audio.resolve_device(backend.soundcard, selection, 'output')
    backend.soundcard.default_speaker.assert_not_called()


@pytest.mark.parametrize('selection', Audio.DEFAULT_ALIASES)
@pytest.mark.parametrize('direction', ['input', 'output'])
def test_intentional_default_aliases(backend, selection, direction):
    expected = backend.microphone if direction == 'input' else backend.speaker
    assert Audio.resolve_device(backend.soundcard, selection, direction) is expected


def test_duplicate_names_remain_distinct(backend):
    backend.soundcard.all_speakers.return_value.append(MagicMock(id='sink-other', name='USB'))
    labels = Audio.device_labels('output')
    assert list(labels) == ['default', 'sink-usb', 'sink-other']
    assert labels['sink-usb'] != labels['sink-other']


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
