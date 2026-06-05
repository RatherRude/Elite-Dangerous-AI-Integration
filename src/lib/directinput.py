# direct inputs
# source to this solution and code:
# http://stackoverflow.com/questions/14489013/simulate-python-keypresses-for-controlling-a-game
# http://www.gamespp.com/directx/directInputKeyboardScanCodes.html

import ctypes
import time
import platform
from typing import final

from pynput.keyboard import Controller, KeyCode  # pyright: ignore[reportMissingModuleSource]
from pynput.mouse import Button, Controller as MouseController  # pyright: ignore[reportMissingModuleSource]

SendInput = ctypes.windll.user32.SendInput if 'windll' in dir(ctypes) else None
pynput_keyboard = Controller()
pynput_mouse = MouseController()

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_XDOWN = 0x0080
MOUSEEVENTF_XUP = 0x0100
MOUSEEVENTF_WHEEL = 0x0800
XBUTTON1 = 0x0001
XBUTTON2 = 0x0002
WHEEL_DELTA = 120

WINDOWS_MOUSE_BUTTONS = {
    "left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP, 0),
    "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP, 0),
    "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP, 0),
    "x1": (MOUSEEVENTF_XDOWN, MOUSEEVENTF_XUP, XBUTTON1),
    "x2": (MOUSEEVENTF_XDOWN, MOUSEEVENTF_XUP, XBUTTON2),
}

# C struct redefinitions

PUL = ctypes.POINTER(ctypes.c_ulong)


@final
class KeyBdInput(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]


@final
class HardwareInput(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_ulong),
                ("wParamL", ctypes.c_short),
                ("wParamH", ctypes.c_ushort)]


@final
class MouseInput(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time",ctypes.c_ulong),
                ("dwExtraInfo", PUL)]


@final
class Input_I(ctypes.Union):
    _fields_ = [("ki", KeyBdInput),
                 ("mi", MouseInput),
                 ("hi", HardwareInput)]


@final
class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong),
                ("ii", Input_I)]


# Actual Functions

def _send_mouse_input(flags: int, mouse_data: int = 0):
    assert SendInput is not None
    extra = ctypes.c_ulong(0)
    ii_ = Input_I()
    ii_.mi = MouseInput(0, 0, mouse_data, flags, 0, ctypes.pointer(extra))
    x = Input(ctypes.c_ulong(0), ii_)
    SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))

def _get_pynput_mouse_button(button: str):
    pynput_button = getattr(Button, button, None)
    if pynput_button is None:
        raise KeyError(f"Unsupported mouse button {button} on this platform.")
    return pynput_button

def PressKey(keyCode: int | str):
    if platform.system() == 'Windows':
        assert SendInput is not None
        assert isinstance(keyCode, int)
        extra = ctypes.c_ulong(0)
        ii_ = Input_I()
        flags = 0x0008  # KEYEVENTF_SCANCODE
        
        # Only apply KEYEVENTF_EXTENDEDKEY to extended keys
        if keyCode > 127:
            flags |= 0x0001  # KEYEVENTF_EXTENDEDKEY
            
        ii_.ki = KeyBdInput(0, keyCode, flags, 0, ctypes.pointer(extra))
        x = Input(ctypes.c_ulong(1), ii_)
        SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))
    else:
        pynput_keyboard.press(KeyCode.from_vk(keyCode) if isinstance(keyCode, int) else KeyCode.from_char(keyCode))

def ReleaseKey(keyCode: int | str):
    if platform.system() == 'Windows':
        assert SendInput is not None
        assert isinstance(keyCode, int)
        extra = ctypes.c_ulong(0)
        ii_ = Input_I()
        flags = 0x0008 | 0x0002  # KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP
        
        # Only apply KEYEVENTF_EXTENDEDKEY to extended keys
        if keyCode > 127:
            flags |= 0x0001  # KEYEVENTF_EXTENDEDKEY
            
        ii_.ki = KeyBdInput(0, keyCode, flags, 0, ctypes.pointer(extra))
        x = Input(ctypes.c_ulong(1), ii_)
        SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))
    else:
        pynput_keyboard.release(KeyCode.from_vk(keyCode) if isinstance(keyCode, int) else KeyCode.from_char(keyCode))

def PressMouseButton(button: str):
    if platform.system() == 'Windows':
        down_flag, _, mouse_data = WINDOWS_MOUSE_BUTTONS[button]
        _send_mouse_input(down_flag, mouse_data)
    else:
        pynput_mouse.press(_get_pynput_mouse_button(button))

def ReleaseMouseButton(button: str):
    if platform.system() == 'Windows':
        _, up_flag, mouse_data = WINDOWS_MOUSE_BUTTONS[button]
        _send_mouse_input(up_flag, mouse_data)
    else:
        pynput_mouse.release(_get_pynput_mouse_button(button))

def ScrollMouseWheel(clicks: int):
    if platform.system() == 'Windows':
        _send_mouse_input(MOUSEEVENTF_WHEEL, clicks * WHEEL_DELTA)
    else:
        pynput_mouse.scroll(0, clicks)

def PressAndReleaseKey(hexKeyCode: int | str):
    PressKey(hexKeyCode)
    time.sleep(0.1)
    ReleaseKey(hexKeyCode)
    time.sleep(0.5)

