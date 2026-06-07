import sys
from pathlib import Path

import cv2
import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.lib.ScreenReader import ScreenReader


def bgr_from_hex(value: str) -> tuple[int, int, int]:
    text = value.removeprefix("#")
    r = int(text[0:2], 16)
    g = int(text[2:4], 16)
    b = int(text[4:6], 16)
    return b, g, r


def test_detect_selected_area_finds_largest_matching_rectangle() -> None:
    image = np.zeros((240, 320, 3), dtype=np.uint8)
    orange = bgr_from_hex("fe8101")
    cv2.rectangle(image, (40, 30), (90, 80), orange, thickness=-1)
    cv2.rectangle(image, (120, 90), (260, 170), orange, thickness=-1)

    detection = ScreenReader().detect_selected_area(image)

    assert detection is not None
    assert detection.x == 120
    assert detection.y == 90
    assert detection.w == 141
    assert detection.h == 81
    assert detection.profile == "sample-fe8101"


def test_detect_selected_area_returns_none_without_matching_selection() -> None:
    image = np.zeros((240, 320, 3), dtype=np.uint8)

    assert ScreenReader().detect_selected_area(image) is None
