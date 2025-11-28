import pytest
from unittest.mock import MagicMock
import os
from src.lib.EDKeys import EDKeys

# Mock for directinput module
@pytest.fixture
def mock_directinput(monkeypatch):
    """Mock DirectInput related functionality"""
    mock_press = MagicMock()
    mock_release = MagicMock()
    
    monkeypatch.setattr('src.lib.EDKeys.PressKey', mock_press)
    monkeypatch.setattr('src.lib.EDKeys.ReleaseKey', mock_release)
    
    monkeypatch.setattr('platform.system', lambda: 'Windows')
    
    return {
        'PressKey': mock_press,
        'ReleaseKey': mock_release
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