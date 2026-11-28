from __future__ import annotations

import platform
import subprocess
import tempfile
from pathlib import Path
from time import sleep

from PIL import Image, ImageOps

from .Logger import log


WINDOWS_GAME_WINDOW_TITLE = "Elite - Dangerous (CLIENT)"
MACOS_STEAM_STREAMING_PROCESS_NAMES = ("steamstreamingclient", "streaming_client", "Steam Streaming Client")


def resize_and_crop_16_9(image: Image.Image, new_height: int) -> Image.Image:
    target_size = (round(new_height * (16 / 9)), new_height)
    return ImageOps.fit(
        image,
        target_size,
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )


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

    try:
        image = _capture_windows_game_client(handle)
        return resize_and_crop_16_9(image, new_height)
    except Exception as error:
        # A desktop-region fallback would reintroduce overlays into OCR.
        log("warn", "Unable to capture the game window without overlays", error)
        return None


def _capture_windows_game_client(handle: int) -> Image.Image:
    """Capture the HWND's client surface, not the desktop pixels covering it.

    PW_RENDERFULLCONTENT is needed for the game's accelerated surface.
    Separate overlay windows are excluded; overlays drawn into the game's
    own render surface cannot be separated by this method.
    """
    import ctypes
    from ctypes import wintypes
    import struct

    import win32gui

    if win32gui.IsIconic(handle):
        raise OSError("The game window is minimized; restore it before capturing")
    left, top, right, bottom = win32gui.GetClientRect(handle)
    width, height = right - left, bottom - top
    if width <= 0 or height <= 0:
        raise OSError("The game window has an empty client area")

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
    user32.PrintWindow.restype = wintypes.BOOL
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    gdi32.GetDIBits.argtypes = [
        wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
        ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT,
    ]
    gdi32.GetDIBits.restype = ctypes.c_int

    source_dc = win32gui.GetDC(handle)
    if not source_dc:
        raise OSError("Unable to acquire the game window device context")
    memory_dc = bitmap = old_bitmap = None
    try:
        memory_dc = win32gui.CreateCompatibleDC(source_dc)
        if not memory_dc:
            raise OSError("Unable to create a capture device context")
        bitmap = win32gui.CreateCompatibleBitmap(source_dc, width, height)
        if not bitmap:
            raise OSError("Unable to create a capture bitmap")
        old_bitmap = win32gui.SelectObject(memory_dc, bitmap)
        pw_clientonly = 0x1
        pw_renderfullcontent = 0x2
        if not user32.PrintWindow(handle, memory_dc, pw_clientonly | pw_renderfullcontent):
            raise OSError("PrintWindow failed to capture the game client surface")

        # GetDIBits requires the bitmap to be deselected from its DC. Request
        # top-down, 32-bit BGR pixels so row order and channel order are explicit.
        win32gui.SelectObject(memory_dc, old_bitmap)
        old_bitmap = None
        pixels = ctypes.create_string_buffer(width * height * 4)
        header = ctypes.create_string_buffer(struct.pack(
            "<IiiHHIIiiII", 40, width, -height, 1, 32, 0, len(pixels), 0, 0, 0, 0,
        ))
        rows = gdi32.GetDIBits(memory_dc, int(bitmap), 0, height, pixels, header, 0)
        if rows != height:
            raise OSError(f"GetDIBits returned {rows} of {height} game image rows")
        image = Image.frombytes("RGB", (width, height), pixels.raw, "raw", "BGRX", 0, 1)
        if image.getbbox() is None:
            raise OSError("PrintWindow returned a black frame; game window capture is unavailable")
        return image
    finally:
        if old_bitmap is not None:
            win32gui.SelectObject(memory_dc, old_bitmap)
        if bitmap:
            win32gui.DeleteObject(bitmap)
        if memory_dc:
            win32gui.DeleteDC(memory_dc)
        win32gui.ReleaseDC(handle, source_dc)


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
