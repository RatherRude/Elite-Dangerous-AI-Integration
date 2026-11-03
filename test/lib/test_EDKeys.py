import pytest
from unittest.mock import MagicMock, call
import os
from src.lib.EDKeys import EDKeys
from src.lib import directinput

# Mock for directinput module
@pytest.fixture
def mock_directinput(monkeypatch):
    """Mock DirectInput related functionality"""
    mock_press = MagicMock()
    mock_release = MagicMock()
    mock_press_mouse = MagicMock()
    mock_release_mouse = MagicMock()
    mock_scroll_mouse = MagicMock()
    
    monkeypatch.setattr('src.lib.EDKeys.PressKey', mock_press)
    monkeypatch.setattr('src.lib.EDKeys.ReleaseKey', mock_release)
    monkeypatch.setattr('src.lib.EDKeys.PressMouseButton', mock_press_mouse)
    monkeypatch.setattr('src.lib.EDKeys.ReleaseMouseButton', mock_release_mouse)
    monkeypatch.setattr('src.lib.EDKeys.ScrollMouseWheel', mock_scroll_mouse)
    
    monkeypatch.setattr('platform.system', lambda: 'Windows')
    
    return {
        'PressKey': mock_press,
        'ReleaseKey': mock_release,
        'PressMouseButton': mock_press_mouse,
        'ReleaseMouseButton': mock_release_mouse,
        'ScrollMouseWheel': mock_scroll_mouse,
    }

@pytest.fixture
def binds_file(tmp_path):
    """Create a test binds file with sample keybindings"""
    content = """<?xml version="1.0" encoding="UTF-8" ?>
    <Root>
        <PrimaryFire>
            <Primary Device="Keyboard" Key="Key_Space"/>
		    <Secondary Device="{NoDevice}" Key="" />
        </PrimaryFire>
        <SecondaryFire>
            <Primary Device="Keyboard" Key="Key_A">
                <Modifier Device="Keyboard" Key="Key_LeftShift"/>
            </Primary>
		    <Secondary Device="{NoDevice}" Key="" />
        </SecondaryFire>
        <CycleNextTarget>
            <Primary Device="Keyboard" Key="Key_Q"/>
            <Secondary Device="Keyboard" Key="Key_E"/>
        </CycleNextTarget>
        <HumanoidPrimaryFireButton>
            <Primary Device="Mouse" Key="Mouse_1" />
            <Secondary Device="{NoDevice}" Key="" />
        </HumanoidPrimaryFireButton>
        <HumanoidItemWheelButton_YUp>
            <Primary Device="{NoDevice}" Key="" />
            <Secondary Device="Mouse" Key="Pos_Mouse_ZAxis" />
        </HumanoidItemWheelButton_YUp>
        <KeyboardPrimaryMouseSecondary>
            <Primary Device="Keyboard" Key="Key_Q" />
            <Secondary Device="Mouse" Key="Mouse_2" />
        </KeyboardPrimaryMouseSecondary>
        <MousePrimaryKeyboardSecondary>
            <Primary Device="Mouse" Key="Mouse_2" />
            <Secondary Device="Keyboard" Key="Key_G" />
        </MousePrimaryKeyboardSecondary>
        <InvalidBinding>
            <Primary Device="Keyboard" Key="Key_Invalid"/>
        </InvalidBinding>
    </Root>
    """
    binds_path = tmp_path / "Options" / "Bindings" / "TestBindings.3.0.binds"
    os.makedirs(binds_path.parent)
    binds_path.write_text(content)
    return str(tmp_path)


@pytest.mark.parametrize("text", ["Wolf 397", "Wolf 597", "BD+21 55"])
def test_send_text_uses_literal_unicode_on_windows(mock_directinput, monkeypatch, text):
    keys = EDKeys.__new__(EDKeys)
    typing = MagicMock()
    monkeypatch.setattr("src.lib.EDKeys.SendUnicodeText", typing)

    keys.send_text(text)

    typing.assert_called_once_with(text)
    mock_directinput["PressKey"].assert_not_called()
    mock_directinput["ReleaseKey"].assert_not_called()


def test_send_text_surfaces_windows_input_failure(mock_directinput, monkeypatch):
    keys = EDKeys.__new__(EDKeys)
    typing = MagicMock(side_effect=RuntimeError("Input failed"))
    monkeypatch.setattr("src.lib.EDKeys.SendUnicodeText", typing)

    with pytest.raises(RuntimeError, match="Input failed"):
        keys.send_text("Wolf 397")

    mock_directinput["PressKey"].assert_not_called()


@pytest.mark.parametrize("text", ["Wolf 397", "Wolf 597", "BD+21 55", "\u00e9", "\U0001f680"])
def test_unicode_text_sends_literal_utf16_packets(mock_directinput, monkeypatch, text):
    captured = []

    def send(count, inputs, size):
        assert size == directinput.ctypes.sizeof(directinput.Input)
        for item in inputs:
            assert item.type == 1
            assert item.ii.ki.wVk == 0
            assert not item.ii.ki.dwExtraInfo
            captured.append((item.ii.ki.wScan, item.ii.ki.dwFlags))
        return count

    monkeypatch.setattr(directinput, "SendInput", send)
    pause = MagicMock()
    monkeypatch.setattr(directinput.time, "sleep", pause)

    directinput.SendUnicodeText(text, interval=0.1)

    encoded = text.encode("utf-16-le")
    units = [int.from_bytes(encoded[index:index + 2], "little") for index in range(0, len(encoded), 2)]
    assert captured == [(unit, flags) for unit in units for flags in (0x0004, 0x0006)]
    assert pause.call_args_list == [call(0.1)] * len(text)


@pytest.mark.parametrize("accepted", [0, 1])
def test_unicode_text_stops_when_windows_rejects_events(mock_directinput, monkeypatch, accepted):
    send = MagicMock(return_value=accepted)
    monkeypatch.setattr(directinput, "SendInput", send)
    pause = MagicMock()
    monkeypatch.setattr(directinput.time, "sleep", pause)

    with pytest.raises(RuntimeError, match=f"Windows accepted {accepted} of 2"):
        directinput.SendUnicodeText("Wolf 397")

    send.assert_called_once()
    pause.assert_not_called()


def test_unicode_text_validates_before_sending_any_character(mock_directinput, monkeypatch):
    send = MagicMock()
    monkeypatch.setattr(directinput, "SendInput", send)

    with pytest.raises(UnicodeEncodeError):
        directinput.SendUnicodeText("Wolf \ud800")

    send.assert_not_called()


def test_unicode_text_reports_unavailable_windows_input(mock_directinput, monkeypatch):
    monkeypatch.setattr(directinput, "SendInput", None)

    with pytest.raises(RuntimeError, match="only supported on Windows"):
        directinput.SendUnicodeText("Wolf 397")


def test_unicode_text_uses_original_typing_interval(mock_directinput, monkeypatch):
    monkeypatch.setattr(directinput, "SendInput", lambda count, inputs, size: count)
    pause = MagicMock()
    monkeypatch.setattr(directinput.time, "sleep", pause)

    directinput.SendUnicodeText("Wolf 397")

    assert pause.call_args_list == [call(0.02)] * len("Wolf 397")


@pytest.mark.parametrize("system", ["Linux", "Darwin"])
def test_send_text_preserves_non_windows_typing(mock_directinput, monkeypatch, system):
    keys = EDKeys.__new__(EDKeys)
    typing = MagicMock()
    monkeypatch.setattr("pyautogui.typewrite", typing)
    monkeypatch.setattr("platform.system", lambda: system)

    keys.send_text("Wolf 597")

    typing.assert_called_once_with("Wolf 597", interval=0.02)
    mock_directinput["PressKey"].assert_not_called()


def test_get_bindings_loads_valid_keys(mock_directinput, binds_file):
    """Test that valid keybindings are loaded correctly"""
    keys = EDKeys(binds_file)
    bindings = keys.keys
    
    expected_bindings = {
        'PrimaryFire': {'key': 57, 'mods': []},
        'SecondaryFire': {'key': 30, 'mods': [42]},
        'CycleNextTarget': {'key': 18, 'mods': []},
    }

    for key_name, expectations in expected_bindings.items():
        assert key_name in bindings
        assert bindings[key_name]['key'] == expectations['key']
        assert bindings[key_name]['mods'] == expectations['mods']
        assert key_name not in keys.missing_keys
    
    assert len(keys.missing_keys) == len(keys.required_keys) - len(expected_bindings)

def test_get_bindings_skips_unrecognized(mock_directinput, binds_file):
    """Test that unrecognized keys are skipped"""
    keys = EDKeys(binds_file)
    
    assert keys.keys
    assert 'InvalidBinding' not in keys.keys

def test_send_valid_key(mock_directinput, binds_file):
    """Test sending a valid key press"""
    keys = EDKeys(binds_file)
    keys.send('PrimaryFire')
    
    mock_directinput["PressKey"].assert_called_with(57)
    mock_directinput["ReleaseKey"].assert_called_with(57)

def test_send_with_modifier(mock_directinput, binds_file):
    """Test sending a key with modifier"""
    keys = EDKeys(binds_file)
    keys.send('SecondaryFire')
    
    # Should press modifier first
    assert mock_directinput["PressKey"].call_args_list[0][0][0] == 42
    assert mock_directinput["PressKey"].call_args_list[1][0][0] == 30

def test_send_invalid_key(mock_directinput, binds_file):
    """Test sending an invalid key raises exception"""
    keys = EDKeys(binds_file)
    with pytest.raises(Exception) as exc_info:
        keys.send('NonExistentKey')
    assert "Unable to retrieve keybinding" in str(exc_info.value)

def test_empty_bindings_directory(tmp_path, monkeypatch):
    """Test handling of empty bindings directory"""
    keys = EDKeys(str(tmp_path))
    assert keys.keys == {}

def test_send_with_hold(mock_directinput, binds_file):
    """Test sending a key with hold parameter"""
    keys = EDKeys(binds_file)
    keys.send('PrimaryFire', hold=0.1)
    
    assert mock_directinput["PressKey"].called
    assert mock_directinput["ReleaseKey"].called

@pytest.mark.parametrize(
    "prefer_primary, expected_key",
    [
        (False, 18),  # Secondary binding (Key_E)
        (True, 16),   # Primary binding (Key_Q)
    ],
)
def test_cycle_next_target_binding_respects_preference(mock_directinput, binds_file, prefer_primary, expected_key):
    """CycleNextTarget should load from secondary by default and primary when configured."""
    keys = EDKeys(binds_file, prefer_primary_bindings=prefer_primary)
    binding = keys.keys['CycleNextTarget']

    assert binding['key'] == expected_key
    assert binding['mods'] == []

def test_get_bindings_loads_mouse_buttons_and_wheel(mock_directinput, binds_file):
    """Mouse buttons and wheel axes should be loaded from Elite bindings."""
    keys = EDKeys(binds_file)

    assert keys.keys['HumanoidPrimaryFireButton'] == {
        'type': 'mouse_button',
        'button': 'left',
        'mods': [],
    }
    assert keys.keys['HumanoidItemWheelButton_YUp'] == {
        'type': 'mouse_wheel',
        'clicks': 1,
        'mods': [],
    }

def test_keyboard_bindings_are_preferred_over_mouse_bindings(mock_directinput, binds_file):
    """Keyboard bindings should win when a control has both keyboard and mouse assigned."""
    keys = EDKeys(binds_file)

    assert keys.keys['KeyboardPrimaryMouseSecondary']['key'] == 16
    assert keys.keys['MousePrimaryKeyboardSecondary']['key'] == 34

def test_send_mouse_button_supports_press_and_release_state(mock_directinput, binds_file):
    """Mouse button bindings should support held press and release calls."""
    keys = EDKeys(binds_file)

    keys.send('HumanoidPrimaryFireButton', state=1)
    keys.send('HumanoidPrimaryFireButton', state=0)

    mock_directinput["PressMouseButton"].assert_called_once_with('left')
    mock_directinput["ReleaseMouseButton"].assert_called_once_with('left')

def test_send_mouse_wheel_scrolls_once(mock_directinput, binds_file):
    """Mouse wheel bindings should emit scroll events."""
    keys = EDKeys(binds_file)

    keys.send('HumanoidItemWheelButton_YUp')

    mock_directinput["ScrollMouseWheel"].assert_called_once_with(1)
def test_pynput_enter_uses_special_key(monkeypatch):
    """macOS Enter should use pynput's special Key.enter from the macOS keymap."""
    mock_press = MagicMock()

    monkeypatch.setattr('platform.system', lambda: 'Darwin')
    monkeypatch.setattr(directinput.pynput_keyboard, 'press', mock_press)

    directinput.PressKey('Key.enter')

    mock_press.assert_called_once_with(directinput.Key.enter)

def test_macos_keymap_uses_pynput_special_keys(monkeypatch, binds_file):
    monkeypatch.setattr('platform.system', lambda: 'Darwin')

    keys = EDKeys(binds_file)

    assert keys.keymap['Key_Enter'] == 'Key.enter'
    assert keys.keymap['Key_LeftShift'] == 'Key.shift_l'
