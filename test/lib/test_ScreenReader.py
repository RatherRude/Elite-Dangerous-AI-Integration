import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.lib.ScreenReader import ScreenReader
from src.lib.HudColorMatrix import HudColorMatrix


def bgr_from_hex(value: str) -> tuple[int, int, int]:
    text = value.removeprefix("#")
    r = int(text[0:2], 16)
    g = int(text[2:4], 16)
    b = int(text[4:6], 16)
    return b, g, r


def bgr_from_rgb(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    r, g, b = rgb
    return b, g, r


def test_detect_selected_area_finds_largest_matching_rectangle() -> None:
    image = np.zeros((240, 320, 3), dtype=np.uint8)
    orange = bgr_from_hex("ff7500")
    cv2.rectangle(image, (40, 30), (90, 80), orange, thickness=-1)
    cv2.rectangle(image, (120, 90), (260, 170), orange, thickness=-1)

    detection = ScreenReader().detect_selected_area(image)

    assert detection is not None
    assert detection.x == 120
    assert detection.y == 90
    assert detection.w == 141
    assert detection.h == 81
    assert detection.profile == "sample-ff7500"


def test_detect_selected_area_ignores_sparse_bottom_fringe() -> None:
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    orange = bgr_from_hex("ff7500")
    cv2.rectangle(image, (20, 20), (50, 50), orange, thickness=-1)
    image[51, 20:22] = orange

    detection = ScreenReader().detect_selected_area(image)

    assert detection is not None
    assert (detection.x, detection.y, detection.w, detection.h) == (20, 20, 31, 31)


def test_detect_selected_area_ignores_two_connected_fringe_rows() -> None:
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    orange = bgr_from_hex("ff7500")
    cv2.rectangle(image, (20, 20), (50, 50), orange, thickness=-1)
    image[51:53, 20:22] = orange

    detection = ScreenReader().detect_selected_area(image)

    assert detection is not None
    assert (detection.x, detection.y, detection.w, detection.h) == (20, 20, 31, 31)


def test_detect_selected_area_trims_dense_wrong_colour_fringe() -> None:
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    orange = bgr_from_hex("ff7500")
    cv2.rectangle(image, (20, 20), (50, 50), orange, thickness=-1)
    # Qualifies for the candidate mask, but is not the border's hue.
    image[51, 20:51] = bgr_from_hex("00ff75")

    detection = ScreenReader().detect_selected_area(image)

    assert detection is not None
    assert (detection.x, detection.y, detection.w, detection.h) == (20, 20, 31, 31)


def test_detect_selected_area_keeps_original_saturation_bounds() -> None:
    reader = ScreenReader(hud_color_matrix=HudColorMatrix([
        [0.89, 0.94, 0.91], [0.0, 0.0, 0.0], [0.5, 0.5, 0.5],
    ]))
    profile = reader.profiles[1]
    assert round(profile.border_saturation_max * 255) == 14


def test_detect_selected_area_returns_none_without_matching_selection() -> None:
    image = np.zeros((240, 320, 3), dtype=np.uint8)

    assert ScreenReader().detect_selected_area(image) is None


def test_read_selected_area_saves_image_when_detection_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    image = np.zeros((240, 320, 3), dtype=np.uint8)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(Exception, match="^No selected area detected$"):
        ScreenReader().read_selected_area(image)

    saved_images = list((tmp_path / "logs" / "screen-reader").glob("no-selected-area-*.png"))
    assert len(saved_images) == 1
    saved_image = cv2.imread(str(saved_images[0]))
    assert saved_image is not None
    assert saved_image.shape == image.shape


def test_detect_selected_area_uses_full_hud_color_matrix() -> None:
    hud_color_matrix = HudColorMatrix([
        [1.0, 0.70, 0.70],
        [0.0, 0.45, 0.35],
        [0.0, 0.00, 0.25],
    ])
    shifted_orange = bgr_from_rgb(hud_color_matrix.shift_color(255, 117, 0))
    image = np.zeros((240, 320, 3), dtype=np.uint8)
    cv2.rectangle(image, (120, 90), (260, 170), shifted_orange, thickness=-1)

    assert ScreenReader().detect_selected_area(image) is None

    detection = ScreenReader(hud_color_matrix=hud_color_matrix).detect_selected_area(image)

    assert detection is not None
    assert detection.x == 120
    assert detection.y == 90
    assert detection.w == 141
    assert detection.h == 81
    assert detection.profile == "sample-ff7500-as-ffe7db"
