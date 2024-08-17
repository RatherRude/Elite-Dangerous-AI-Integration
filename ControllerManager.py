import tkinter as tk
from pynput.keyboard import Key, Controller as KeyboardController, Listener as KeyboardListener
from pynput.mouse import Controller as MouseController, Button, Listener as MouseListener
import pygame
import threading
import time
from typing import Callable, Any


class ControllerManager:
    def __init__(self):
        self.keyboard_controller = KeyboardController()
        self.mouse_controller = MouseController()

        self.is_pressed = False
        self.last_press = None
        self.last_release = None

        pygame.init()
        pygame.joystick.init()
        self.joystick = None
        if pygame.joystick.get_count() > 0:
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()

        self.capture_event_thread = None
        self.capture_event_thread_running = False

    # PPT: Registers event listener for ptt
    def register_hotkey(self, key: str, on_press: Callable[[str], Any], on_release: Callable[[str], Any]) -> None:
        def on_press_wrapper(k):
            if k == key and not self.is_pressed:
                self.is_pressed = True
                on_press(k)
                return True  # Keep listening after capturing the event

        def on_release_wrapper(k):
            if k == key:
                self.is_pressed = False
                on_release(k)
                return True  # Keep listening after capturing the event

        self._start_listeners(on_press_wrapper, on_release_wrapper)



    # PTT: Captures mouse, keyboard, and controller inputs to save them as PTT key
    def listen_hotkey(self) -> str:
        self.last_press = None
        self.last_release = None
        def on_press(key):
            self.last_press = str(key)
            return False

        def on_release(key):
            self.last_release = str(key)
            return False

        self._start_listeners(on_press, on_release)

        # Wait for the event to be captured
        while not self.last_press or self.last_release != self.last_press:
            time.sleep(0.1)

        self._stop_listeners()

        key = self.last_press
        self.last_press = None
        self.last_release = None

        return key

    # TBD
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

    def _start_listeners(self, on_press, on_release):
        self._stop_listeners()
        for _event in pygame.event.get():
            pass

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

        def capture_event():
            while self.joystick_listener_running:
                events = pygame.event.get()
                for event in events:
                    if event.type == pygame.JOYBUTTONDOWN:
                        on_press(str(event.button))
                    if event.type == pygame.JOYBUTTONUP:
                        on_release(str(event.button))
                time.sleep(0.01)  # Small sleep to prevent high CPU usage

        # Start a thread for capturing game controller events
        self.joystick_listener_running = True
        self.joystick_listener = threading.Thread(target=capture_event)
        self.joystick_listener.start()

    def _stop_listeners(self):
        # Stop existing listeners
        try:
            self.keyboard_listener.stop()
        except:
            pass

        try:
            self.mouse_listener.stop()
        except:
            pass

        self.joystick_listener_running = False


# Example Usage:
if __name__ == "__main__":
    manager = ControllerManager()


    # Registering a hotkey example
    def on_press(key):
        print(f"Hotkey pressed: {key}")


    def on_release(key):
        print(f"Hotkey released: {key}")


    manager.register_hotkey("Key.space", on_press, on_release)

    # Listening for a hotkey
    print(f"Captured hotkey: {manager.listen_hotkey()}")

    # Emulating a hotkey
    manager.emulate_hotkey("Key.space")

    while True:
        time.sleep(0.1)