import pytest
from unittest.mock import MagicMock
import os
from xml.etree.ElementTree import fromstring
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
    fixed_scancodes = {
        "Key_A": 30,
        "Key_E": 18,
        "Key_G": 34,
        "Key_Q": 16,
    }
    monkeypatch.setattr(
        "src.lib.EDKeys.resolve_layout_key_name",
        lambda key_name: directinput.LayoutResolvedKey(
            virtual_key=0,
            scan_code=fixed_scancodes[key_name],
            shift_state=0,
        ),
    )

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


def test_layout_dependent_key_names_cover_map_punctuation():
    assert directinput.LAYOUT_DEPENDENT_KEY_CHARACTERS == {
        **{f"Key_{digit}": digit for digit in "1234567890"},
        **{f"Key_{letter.upper()}": letter.lower() for letter in "abcdefghijklmnopqrstuvwxyz"},
        "Key_Comma": ",",
        "Key_Period": ".",
        "Key_SemiColon": ";",
        "Key_Apostrophe": "'",
        "Key_Slash": "/",
        "Key_LeftBracket": "[",
        "Key_RightBracket": "]",
        "Key_BackSlash": "\\",
        "Key_Equals": "=",
        "Key_Minus": "-",
    }


def test_resolve_layout_character_uses_windows_layout(monkeypatch):
    class Win32Function:
        def __init__(self, callback):
            self.callback = callback

        def __call__(self, *args):
            return self.callback(*args)

    def get_keyboard_layout(thread_id):
        assert thread_id == 0
        return 0x040C

    def vk_key_scan(character, layout):
        assert (character, layout) == (",", 0x040C)
        return (0 << 8) | 0xBC

    def map_virtual_key(virtual_key, mode, layout):
        assert (virtual_key, mode, layout) == (0xBC, 0, 0x040C)
        return 0x33

    class User32:
        GetKeyboardLayout = Win32Function(get_keyboard_layout)
        VkKeyScanExW = Win32Function(vk_key_scan)
        MapVirtualKeyExW = Win32Function(map_virtual_key)

    class Windll:
        user32 = User32()

    monkeypatch.setattr(directinput.platform, "system", lambda: "Windows")
    monkeypatch.setattr(directinput.ctypes, "windll", Windll(), raising=False)

    assert directinput.resolve_layout_character(",") == directinput.LayoutResolvedKey(
        virtual_key=0xBC,
        scan_code=0x33,
        shift_state=0,
    )


def test_windows_layout_resolves_keyboard_punctuation(mock_directinput, binds_file, monkeypatch):
    monkeypatch.setattr(
        "src.lib.EDKeys.resolve_layout_key_name",
        lambda key_name: directinput.LayoutResolvedKey(
            virtual_key=0xBC,
            scan_code=0x33,
            shift_state=0,
        ),
    )

    keys = EDKeys(binds_file)
    binding = keys._prepare_binding(
        fromstring(
            '<Primary Device="Keyboard" Key="Key_Comma">'
            "</Primary>"
        )
    )

    assert binding == {"key": 0x33, "mods": []}


@pytest.mark.parametrize(
    ("key_name", "character"),
    [
        ("Key_A", "a"),
        ("Key_Q", "q"),
        ("Key_W", "w"),
        ("Key_Z", "z"),
    ],
)
def test_windows_layout_resolves_alphabetic_keys(
    mock_directinput, binds_file, monkeypatch, key_name, character
):
    fixed_scancodes = {
        "Key_A": 30,
        "Key_E": 18,
        "Key_G": 34,
        "Key_Q": 16,
    }

    def resolve_key(resolved_key_name):
        if resolved_key_name == key_name:
            return directinput.LayoutResolvedKey(
                virtual_key=ord(character.upper()),
                scan_code=0x1E,
                shift_state=0,
            )
        return directinput.LayoutResolvedKey(
            virtual_key=0,
            scan_code=fixed_scancodes[resolved_key_name],
            shift_state=0,
        )

    monkeypatch.setattr(
        "src.lib.EDKeys.resolve_layout_key_name",
        resolve_key,
    )

    keys = EDKeys(binds_file)
    binding = keys._prepare_binding(
        fromstring(f'<Primary Device="Keyboard" Key="{key_name}"></Primary>')
    )

    assert binding == {"key": 0x1E, "mods": []}


def test_windows_layout_adds_implicit_shift_modifier(mock_directinput, binds_file, monkeypatch):
    monkeypatch.setattr(
        "src.lib.EDKeys.resolve_layout_key_name",
        lambda key_name: directinput.LayoutResolvedKey(
            virtual_key=0xBA,
            scan_code=0x27,
            shift_state=1,
        ),
    )

    keys = EDKeys(binds_file)
    binding = keys._prepare_binding(
        fromstring(
            '<Primary Device="Keyboard" Key="Key_SemiColon">'
            "</Primary>"
        )
    )

    assert binding == {"key": 0x27, "mods": [42]}


def test_linux_bindings_use_pynput_characters_for_active_layout(
    mock_directinput, binds_file, monkeypatch
):
    monkeypatch.setattr("platform.system", lambda: "Linux")

    keys = EDKeys(binds_file)

    assert keys.keys["PrimaryFire"] == {"key": " ", "mods": []}
    assert keys.keys["CycleNextTarget"] == {"key": "e", "mods": []}
