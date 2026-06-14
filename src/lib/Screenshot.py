from __future__ import annotations

import platform
import subprocess
import tempfile
from pathlib import Path
from time import sleep

from PIL import Image

from .Logger import log


WINDOWS_GAME_WINDOW_TITLE = "Elite - Dangerous (CLIENT)"
MACOS_STEAM_STREAMING_PROCESS_NAMES = ("steamstreamingclient", "streaming_client", "Steam Streaming Client")


def resize_and_crop_16_9(image: Image.Image, new_height: int) -> Image.Image:
    width, height = image.size
    aspect_ratio = width / height
    new_width = int(new_height * aspect_ratio)
    image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    target_width = int(new_height * (16 / 9))
    left = (new_width - target_width) / 2
    return image.crop((left, 0, left + target_width, new_height))


def get_windows_game_window_handle():
    if platform.system() != "Windows":
        return None

    import win32gui

    return win32gui.FindWindow(0, WINDOWS_GAME_WINDOW_TITLE)


def set_windows_game_window_active() -> None:
    handle = get_windows_game_window_handle()
    if not handle:
        log("info", "Unable to find Elite game window")
        return

    import win32gui

    try:
        win32gui.SetForegroundWindow(handle)
        sleep(0.15)
        log("debug", "Set game window as active")
    except Exception:
        log("warn", "Failed to set game window as active")


def screenshot_windows_game_window(new_height: int) -> Image.Image | None:
    handle = get_windows_game_window_handle()
    if not handle:
        log("warn", "Window not found!")
        return None

    import pyautogui
    import win32gui

    set_windows_game_window_active()
    x, y, x1, y1 = win32gui.GetClientRect(handle)
    x, y = win32gui.ClientToScreen(handle, (x, y))
    x1, y1 = win32gui.ClientToScreen(handle, (x1, y1))
    width = x1 - x
    height = y1 - y
    image = pyautogui.screenshot(region=(x, y, width, height)).convert("RGB")
    return resize_and_crop_16_9(image, new_height)


def _macos_steam_streaming_window_bounds() -> tuple[int, int, int, int] | None:
    try:
        import Quartz
    except ImportError:
        log("warn", "Quartz is not installed; macOS window screenshot is unavailable")
        return None

    windows = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly,
        Quartz.kCGNullWindowID,
    )
    process_names = {name.lower() for name in MACOS_STEAM_STREAMING_PROCESS_NAMES}
    candidates = []
    for window in windows:
        owner = str(window.get("kCGWindowOwnerName", "")).lower()
        if owner not in process_names:
            continue

        bounds = window.get("kCGWindowBounds")
        if not bounds:
            continue

        width = int(bounds.get("Width", 0))
        height = int(bounds.get("Height", 0))
        if width <= 0 or height <= 0:
            continue

        candidates.append(
            (
                width * height,
                int(bounds.get("X", 0)),
                int(bounds.get("Y", 0)),
                width,
                height,
            )
        )

    if not candidates:
        log("warn", "Steam Streaming Client window not found")
        return None

    _, x, y, width, height = max(candidates)
    return x, y, width, height


def screenshot_macos_steam_streaming_client(new_height: int) -> Image.Image | None:
    bounds = _macos_steam_streaming_window_bounds()
    if bounds is None:
        return None

    x, y, width, height = bounds
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        path = Path(tmp.name)

    try:
        subprocess.run(
            ["screencapture", "-x", "-R", f"{x},{y},{width},{height}", str(path)],
            check=True,
            capture_output=True,
            timeout=10,
        )
        with Image.open(path) as image:
            return resize_and_crop_16_9(image.convert("RGB"), new_height)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        log("warn", f"Unable to capture Steam Streaming Client screenshot: {exc}")
        return None
    finally:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def screenshot_game_window(new_height: int) -> Image.Image | None:
    system = platform.system()
    if system == "Windows":
        return screenshot_windows_game_window(new_height)
    if system == "Darwin":
        return screenshot_macos_steam_streaming_client(new_height)

    return None


def set_game_window_active() -> None:
    if platform.system() == "Windows":
        set_windows_game_window_active()
