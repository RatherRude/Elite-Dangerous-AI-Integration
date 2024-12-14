import threading
import time
from typing import Callable, Any
from inputs import get_gamepad
from pynput.keyboard import Controller as KeyboardController, Listener as KeyboardListener
from pynput.mouse import Controller as MouseController, Listener as MouseListener

class ControllerManager:
    def __init__(self):
        # Initialize controllers for keyboard and mouse emulation
        self.keyboard_controller = KeyboardController()
        self.mouse_controller = MouseController()
        self.is_pressed = False
        self.last_press = None
        self.last_release = None
        
        # Map controller buttons to their corresponding names
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
            'ABS_HAT0Y': {-1: 'DPad.Up', 1: 'DPad.Down'},
            'ABS_X': {'press': 0.6, 'release': 0.4, -1: 'LeftStick.Left', 1: 'LeftStick.Right'},
            'ABS_Y': {'press': 0.6, 'release': 0.4, -1: 'LeftStick.Up', 1: 'LeftStick.Down'},
            'ABS_RX': {'press': 0.6, 'release': 0.4, -1: 'RightStick.Left', 1: 'RightStick.Right'},
            'ABS_RY': {'press': 0.6, 'release': 0.4, -1: 'RightStick.Up', 1: 'RightStick.Down'},
            'ABS_Z': {'press': 0.6, 'release': 0.4, 1: 'LeftTrigger'},  # Left Trigger
            'ABS_RZ': {'press': 0.6, 'release': 0.4, 1: 'RightTrigger'} # Right Trigger
        }
        
        self.controller_thread = None
        self.controller_running = False
        
    # PPT: Registers event listener for ptt
    def register_hotkey(self, key: str, on_press: Callable[[str], Any], on_release: Callable[[str], Any]) -> None:
        def on_press_wrapper(k):
            if k == key and not self.is_pressed:
                self.is_pressed = True
                on_press(k)
                return True # Keep listening after capturing the event

        def on_release_wrapper(k):
            if k == key:
                self.is_pressed = False
                on_release(k)
                return True # Keep listening after capturing the event

        self._start_listeners(on_press_wrapper, on_release_wrapper)
        
    # PTT: Captures mouse, keyboard, and controller inputs to save them as PTT key
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

    # Initialize and start all input listeners
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

        # Start listeners for keyboard and mouse
        self.keyboard_listener = KeyboardListener(on_press=on_key_press, on_release=on_key_release)
        self.keyboard_listener.start()
        self.mouse_listener = MouseListener(on_click=on_mouse_click)
        self.mouse_listener.start()

        # Controller event capture thread
        def capture_controller():
            while self.controller_running:
                try:
                    events = get_gamepad()
                    for event in events:
                        if event.ev_type in ['Key', 'Absolute']:
                            if event.code in self.button_states:
                                button_mapping = self.button_states[event.code]
                                
                                # Handle D-pad and analog inputs
                                if isinstance(button_mapping, dict):
                                    if 'press' in button_mapping:
                                        # Handle analog sticks and triggers
                                        normalized_value = abs(event.state) / 32768
                                        direction = 1 if event.state > 0 else -1
                                        
                                        if normalized_value > button_mapping['press']:
                                            button_name = button_mapping[direction]
                                            on_press(f"Controller.{button_name}")
                                        elif normalized_value < button_mapping['release']:
                                            # Release both directions when below release threshold
                                            for direction in [-1, 1]:
                                                if direction in button_mapping:
                                                    on_release(f"Controller.{button_mapping[direction]}")
                                    else:
                                        # Handle D-pad
                                        if event.state in button_mapping:
                                            button_name = button_mapping[event.state]
                                            on_press(f"Controller.{button_name}")
                                        else:
                                            # Release all directions when D-pad is centered
                                            for direction in button_mapping.values():
                                                on_release(f"Controller.{direction}")
                                # Handle standard button inputs
                                else:
                                    if event.state == 1:
                                        on_press(f"Controller.{button_mapping}")
                                    else:
                                        on_release(f"Controller.{button_mapping}")
                except:
                    pass
                time.sleep(0.01) # Small sleep to prevent high CPU usage
                
        # Start a thread for capturing game controller events
        self.controller_running = True
        self.controller_thread = threading.Thread(target=capture_controller, daemon=True)
        self.controller_thread.start()

    # Stop existing listeners
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

    # Emulate keyboard or mouse input based on the provided key
    def emulate_hotkey(self, key: str) -> None:
        try:
            # Try to interpret key as a Key object
            key_obj = eval(key)
            self.keyboard_controller.press(key_obj)
            self.keyboard_controller.release(key_obj)
        except (NameError, SyntaxError):
            # If not a keyboard key, check for mouse button
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

    # Example usage with spacebar as hotkey
    manager.register_hotkey("Key.space", on_press, on_release)
    
    while True:
        time.sleep(0.1)
