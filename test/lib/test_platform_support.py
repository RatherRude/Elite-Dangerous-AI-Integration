import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.lib.Config import assign_ptt, get_ed_appdata_path
from src.lib.ControllerManager import ControllerManager
from src.lib import directinput


def test_get_ed_appdata_path_uses_cwd_on_non_windows(monkeypatch, tmp_path):
    monkeypatch.setattr('platform.system', lambda: 'Darwin')
    monkeypatch.chdir(tmp_path)

    assert get_ed_appdata_path({"ed_appdata_path": ""}) == str(tmp_path)


def test_assign_ptt_uses_hotkey_listener_on_macos(monkeypatch):
    monkeypatch.setattr('platform.system', lambda: 'Darwin')
    controller_manager = MagicMock()

    def trigger_hotkey(callback):
        callback('Key.space')

    controller_manager.listen_hotkey.side_effect = trigger_hotkey
    monkeypatch.setattr('src.lib.Config.emit_message', lambda *args, **kwargs: None)
    monkeypatch.setattr('src.lib.Config.save_config', lambda *args, **kwargs: None)

    config = assign_ptt({"ptt_key": ""}, controller_manager)

    assert config['ptt_key'] == 'Key.space'
    controller_manager.listen_hotkey.assert_called_once()


def test_assign_ptt_can_store_secondary_hotkey(monkeypatch):
    monkeypatch.setattr('platform.system', lambda: 'Darwin')
    controller_manager = MagicMock()

    def trigger_hotkey(callback):
        callback('Button.x2')

    controller_manager.listen_hotkey.side_effect = trigger_hotkey
    monkeypatch.setattr('src.lib.Config.emit_message', lambda *args, **kwargs: None)
    monkeypatch.setattr('src.lib.Config.save_config', lambda *args, **kwargs: None)

    config = assign_ptt({"ptt_key": "Key.space", "ptt_key_secondary": ""}, controller_manager, index=1)

    assert config['ptt_key'] == 'Key.space'
    assert config['ptt_key_secondary'] == 'Button.x2'
    controller_manager.listen_hotkey.assert_called_once()


def test_controller_manager_register_hotkey_uses_listener_path():
    manager = object.__new__(ControllerManager)
    manager._start_listeners = MagicMock()

    manager.register_hotkey('Key.space', lambda _: None, lambda _: None)

    manager._start_listeners.assert_called_once()


def test_controller_manager_register_hotkey_supports_multiple_bindings():
    manager = object.__new__(ControllerManager)
    manager._start_listeners = MagicMock()

    on_press = MagicMock()
    on_release = MagicMock()

    manager.register_hotkey(['Key.space', 'Button.left'], on_press, on_release)

    press_listener, release_listener = manager._start_listeners.call_args[0]

    press_listener('Key.space')
    press_listener('Button.left')
    release_listener('Key.space')
    release_listener('Button.left')

    on_press.assert_called_once_with('Key.space')
    on_release.assert_called_once_with('Button.left')


def test_controller_manager_listen_hotkey_uses_listener_path():
    manager = object.__new__(ControllerManager)
    manager._start_listeners = MagicMock()

    manager.listen_hotkey(lambda _: None)

    manager._start_listeners.assert_called_once()


def test_controller_manager_start_listeners_skips_joystick_thread_on_macos(monkeypatch):
    monkeypatch.setattr('platform.system', lambda: 'Darwin')
    manager = object.__new__(ControllerManager)
    manager.joystick_hotkeys_supported = False
    manager.joystick_listener_running = False
    manager.keyboard_listener = None
    manager.mouse_listener = None
    manager.joystick_listener = None
    manager._stop_listeners = MagicMock()

    keyboard_listener = MagicMock()
    mouse_listener = MagicMock()
    keyboard_listener_cls = MagicMock(return_value=keyboard_listener)
    mouse_listener_cls = MagicMock(return_value=mouse_listener)

    monkeypatch.setattr('src.lib.ControllerManager.KeyboardListener', keyboard_listener_cls)
    monkeypatch.setattr('src.lib.ControllerManager.MouseListener', mouse_listener_cls)

    manager._start_listeners(lambda *_: None, lambda *_: None)

    keyboard_listener.start.assert_called_once()
    mouse_listener.start.assert_called_once()
    assert manager.joystick_listener is None
    assert manager.joystick_listener_running is False


def test_controller_manager_keyboard_emulation_raises_on_macos(monkeypatch):
    monkeypatch.setattr('platform.system', lambda: 'Darwin')

    manager = object.__new__(ControllerManager)
    manager.keyboard_controller = MagicMock()
    manager.mouse_controller = MagicMock()

    manager.emulate_hotkey('Key.space')

    manager.keyboard_controller.press.assert_called_once()
    manager.keyboard_controller.release.assert_called_once()


def test_directinput_keyboard_emulation_uses_pynput_on_macos(monkeypatch):
    monkeypatch.setattr('platform.system', lambda: 'Darwin')
    mock_keyboard = MagicMock()
    monkeypatch.setattr(directinput, 'pynput_keyboard', mock_keyboard)

    directinput.PressKey('a')
    directinput.ReleaseKey('a')

    assert mock_keyboard.press.call_count == 1
    assert mock_keyboard.release.call_count == 1


def test_directinput_press_and_release_key_uses_pynput_on_macos(monkeypatch):
    monkeypatch.setattr('platform.system', lambda: 'Darwin')
    mock_keyboard = MagicMock()
    monkeypatch.setattr(directinput, 'pynput_keyboard', mock_keyboard)
    monkeypatch.setattr('time.sleep', lambda *_: None)

    directinput.PressAndReleaseKey('a')

    assert mock_keyboard.press.call_count == 1
    assert mock_keyboard.release.call_count == 1


def test_directinput_mouse_button_emulation_uses_pynput_on_macos(monkeypatch):
    monkeypatch.setattr('platform.system', lambda: 'Darwin')
    mock_mouse = MagicMock()
    monkeypatch.setattr(directinput, 'pynput_mouse', mock_mouse)

    directinput.PressMouseButton('left')
    directinput.ReleaseMouseButton('left')

    assert mock_mouse.press.call_count == 1
    assert mock_mouse.release.call_count == 1


def test_directinput_extra_mouse_buttons_are_looked_up_lazily(monkeypatch):
    monkeypatch.setattr('platform.system', lambda: 'Darwin')
    mock_mouse = MagicMock()
    monkeypatch.setattr(directinput, 'pynput_mouse', mock_mouse)
    fake_left_button = object()
    monkeypatch.setattr(directinput, 'Button', SimpleNamespace(left=fake_left_button))

    directinput.PressMouseButton('left')

    mock_mouse.press.assert_called_once_with(fake_left_button)


def test_directinput_mouse_wheel_uses_pynput_on_macos(monkeypatch):
    monkeypatch.setattr('platform.system', lambda: 'Darwin')
    mock_mouse = MagicMock()
    monkeypatch.setattr(directinput, 'pynput_mouse', mock_mouse)

    directinput.ScrollMouseWheel(-1)

    mock_mouse.scroll.assert_called_once_with(0, -1)
