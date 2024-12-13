import threading
import time
from typing import Callable, Any
from inputs import get_gamepad
from pynput.keyboard import Controller as KeyboardController, Listener as KeyboardListener
from pynput.mouse import Controller as MouseController, Listener as MouseListener

class ControllerManager:
    def __init__(self):
        self.keyboard_controller = KeyboardController()
        self.mouse_controller = MouseController()
        self.is_pressed = False
        self.last_press = None
        self.last_release = None
        
        self.button_states = {
            'BTN_SOUTH': 'A',
            'BTN_EAST': 'B',
            'BTN_WEST': 'X', 
            'BTN_NORTH': 'Y',
            'BTN_START': 'Start',
            'BTN_SELECT': 'Select',
            'BTN_TL': 'LB',
            'BTN_TR': 'RB',
            'BTN_THUMBL': 'LS',
            'BTN_THUMBR': 'RS',
            'ABS_HAT0X': {-1: 'DPad.Left', 1: 'DPad.Right'},
            'ABS_HAT0Y': {-1: 'DPad.Up', 1: 'DPad.Down'}
        }
        
        self.controller_thread = None
        self.controller_running = False

    def register_hotkey(self, key: str, on_press: Callable[[str], Any], on_release: Callable[[str], Any]) -> None:
        def on_press_wrapper(k):
            if k == key and not self.is_pressed:
                self.is_pressed = True
                on_press(k)
                return True

        def on_release_wrapper(k):
            if k == key:
                self.is_pressed = False
                on_release(k)
                return True

        self._start_listeners(on_press_wrapper, on_release_wrapper)

    def listen_hotkey(self, callback: Callable[[str], any]):
        self.last_press = None
        self.last_release = None

        def on_press(key):
            self.last_press = str(key)
            return False

        def on_release(key):
            self.last_release = str(key)
            if self.last_press and self.last_release == self.last_press:
                self._stop_listeners()
                key = self.last_press
                self.last_press = None
                self.last_release = None
                callback(key)
            return False

        self._start_listeners(on_press, on_release)

    def _start_listeners(self, on_press, on_release):
        self._stop_listeners()

        def on_key_press(key):
            on_press(str(key))
            return True

        def on_key_release(key):
            on_release(str(key))
            return True

        def on_mouse_click(x, y, key, down):
            if down:
                on_press(str(key))
            else:
                on_release(str(key))
            return True

        self.keyboard_listener = KeyboardListener(on_press=on_key_press, on_release=on_key_release)
        self.keyboard_listener.start()
        self.mouse_listener = MouseListener(on_click=on_mouse_click)
        self.mouse_listener.start()

        def capture_controller():
            while self.controller_running:
                try:
                    events = get_gamepad()
                    for event in events:
                        if event.ev_type in ['Key', 'Absolute']:
                            if event.code in self.button_states:
                                button_mapping = self.button_states[event.code]
                                
                                # Handle D-pad
                                if isinstance(button_mapping, dict):
                                    if event.state in button_mapping:
                                        button_name = button_mapping[event.state]
                                        on_press(f"Controller.{button_name}")
                                    else:
                                        # Release all directions when centered
                                        for direction in button_mapping.values():
                                            on_release(f"Controller.{direction}")
                                # Handle regular buttons
                                else:
                                    if event.state == 1:
                                        on_press(f"Controller.{button_mapping}")
                                    else:
                                        on_release(f"Controller.{button_mapping}")
                except:
                    pass
                time.sleep(0.01)

        self.controller_running = True
        self.controller_thread = threading.Thread(target=capture_controller, daemon=True)
        self.controller_thread.start()

    def _stop_listeners(self):
        try:
            self.keyboard_listener.stop()
        except:
            pass
        try:
            self.mouse_listener.stop()
        except:
            pass
        self.controller_running = False

    def emulate_hotkey(self, key: str) -> None:
        try:
            key_obj = eval(key)
            self.keyboard_controller.press(key_obj)
            self.keyboard_controller.release(key_obj)
        except (NameError, SyntaxError):
            if key.startswith("Button."):
                button = eval(key)
                self.mouse_controller.click(button)
            else:
                print(f"Unknown key type: {key}")

if __name__ == "__main__":
    manager = ControllerManager()
    
    def on_press(key):
        print(f"Hotkey pressed: {key}")
    
    def on_release(key):
        print(f"Hotkey released: {key}")

    manager.register_hotkey("Key.space", on_press, on_release)
    
    while True:
        time.sleep(0.1)
