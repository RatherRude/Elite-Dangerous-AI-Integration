import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.lib.ScreenReader import (
    ICON_TEMPLATES,
    OcrLine,
    ScreenReader,
    binary_template,
    identify_icon_template,
    match_binary_icon_template,
    match_exit_icon_template,
)
from src.lib.HudColorMatrix import HudColorMatrix


LIVE_HUD_MATRIX = HudColorMatrix([
    [2.0, 0.0, -0.11], [0.0, 0.0, 0.75], [0.0, 1.0, 0.3],
])


def live_exit_image(scale: float = 1.0) -> np.ndarray:
    button = cv2.imread(str(Path(__file__).parent / "fixtures/system_map_exit_edhm.png"))
    assert button is not None
    button = cv2.resize(button, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    height, width = button.shape[:2]
    image[20:20 + height, 20:20 + width] = button
    return image


@pytest.mark.parametrize("scale", [0.75, 1.0, 1.5, 2.0])
def test_detect_selected_area_identifies_real_edhm_exit(scale: float) -> None:
    reader = ScreenReader(hud_color_matrix=LIVE_HUD_MATRIX)
    assert round(reader.profiles[1].candidate_value_min * 255) == 255

    detection = reader.detect_selected_area(live_exit_image(scale))

    assert detection is not None
    assert detection.icon_template == "exit"
    assert detection.icon_match is not None and detection.icon_match > ICON_TEMPLATES["exit"][1]


def test_debug_read_saves_exact_frame_masks_and_template_scores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reader = ScreenReader(hud_color_matrix=LIVE_HUD_MATRIX, debug_directory=tmp_path)
    image = live_exit_image()
    captures = []

    def capture():
        captures.append(True)
        return image

    monkeypatch.setattr(reader, "get_screen", capture)
    monkeypatch.setattr(reader, "read_detection_text", lambda *_: [OcrLine("BACK", 1.0)])
    result = reader.read_selected_area()

    assert len(captures) == 1
    assert result.detection is not None and result.detection.icon_template == "exit"
    assert np.array_equal(cv2.imread(str(next(tmp_path.glob("*-source.png")))), image)
    for suffix in ("annotated", "selection", "glyph", "comparison"):
        assert len(list(tmp_path.glob(f"*-{suffix}.png"))) == 1
    metadata = json.loads(next(tmp_path.glob("*-read.json")).read_text())
    assert metadata["ocr_lines"][0]["text"] == "BACK"
    candidate = next(c for p in metadata["profiles"] for c in p["candidates"] if c.get("accepted"))
    exit_score = next(icon for icon in candidate["icons"] if icon["name"] == "exit")
    assert exit_score["score"] > 0.8
    assert exit_score["w"] > 0 and exit_score["h"] > 0


def test_debug_read_saves_failed_detection(tmp_path: Path) -> None:
    reader = ScreenReader(debug_directory=tmp_path)

    with pytest.raises(Exception, match="^No selected area detected$"):
        reader.read_selected_area(np.zeros((100, 100, 3), dtype=np.uint8))

    metadata = json.loads(next(tmp_path.glob("*-read.json")).read_text())
    assert metadata["detection"] is None
    assert metadata["error"] == "No selected area detected"
    assert len(list(tmp_path.glob("*-source.png"))) == 1


def test_debug_read_saves_ocr_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reader = ScreenReader(hud_color_matrix=LIVE_HUD_MATRIX, debug_directory=tmp_path)

    def fail(*_):
        raise RuntimeError("OCR failed")

    monkeypatch.setattr(reader, "read_detection_text", fail)
    with pytest.raises(RuntimeError, match="OCR failed"):
        reader.read_selected_area(live_exit_image())

    metadata = json.loads(next(tmp_path.glob("*-read.json")).read_text())
    assert metadata["error"] == "OCR failed"
    assert metadata["detection"]["icon_template"] == "exit"


def test_unwritable_debug_directory_does_not_break_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    blocked = tmp_path / "file-not-directory"
    blocked.write_text("existing file")
    reader = ScreenReader(hud_color_matrix=LIVE_HUD_MATRIX, debug_directory=blocked)
    monkeypatch.setattr(reader, "read_detection_text", lambda *_: [])

    assert reader.read_selected_area(live_exit_image()).detection.icon_template == "exit"
    assert blocked.read_text() == "existing file"


def bgr_from_hex(value: str) -> tuple[int, int, int]:
    text = value.removeprefix("#")
    r = int(text[0:2], 16)
    g = int(text[2:4], 16)
    b = int(text[4:6], 16)
    return b, g, r


def bgr_from_rgb(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    r, g, b = rgb
    return b, g, r


@pytest.mark.parametrize("icon_name", ICON_TEMPLATES)
@pytest.mark.parametrize("height", [30, 31, 32])
def test_identify_icon_template_tolerates_empty_padding(icon_name: str, height: int) -> None:
    template = binary_template(ICON_TEMPLATES[icon_name][0])
    # Match the reported 31x30 button, as well as neighbouring button heights.
    inner_height = height - 8
    if template.shape[0] > inner_height:
        top = (template.shape[0] - inner_height) // 2
        cropped = template[top : top + inner_height]
        assert cropped.sum() == template.sum()
        template = cropped
    roi_hsv = np.full((height, 31, 3), (14, 255, 255), dtype=np.uint8)
    inner = roi_hsv[4:-4, 4:-4]
    # Dark orange glyph: same hue/saturation as the selected background.
    inner[:template.shape[0], :template.shape[1], 2][template.astype(bool)] = 20

    name, score = identify_icon_template(
        roi_hsv, hue_deg=28, hue_tolerance_deg=10, border_px=4,
    )

    assert name == icon_name
    assert score is not None and score > 0.99


@pytest.mark.parametrize("icon_name", ICON_TEMPLATES)
@pytest.mark.parametrize("scale", [0.65, 0.8, 1.0, 1.25, 1.5, 2.0, 2.75])
@pytest.mark.parametrize("interpolation", [cv2.INTER_NEAREST, cv2.INTER_LINEAR])
def test_identify_icon_template_is_scale_invariant(icon_name: str, scale: float, interpolation: int) -> None:
    template = binary_template(ICON_TEMPLATES[icon_name][0])
    scaled = cv2.resize(template, None, fx=scale, fy=scale, interpolation=interpolation) >= 0.5
    height, width = scaled.shape
    # Uneven padding also tests translation independently of glyph size.
    roi_hsv = np.full((height + 12, width + 14, 3), (14, 255, 255), dtype=np.uint8)
    roi_hsv[5:5 + height, 7:7 + width, 2][scaled] = 20

    name, score = identify_icon_template(
        roi_hsv, hue_deg=28, hue_tolerance_deg=10, border_px=4,
    )

    assert name == icon_name
    assert score is not None and score >= ICON_TEMPLATES[icon_name][1]


@pytest.mark.parametrize("size", [20, 30, 50, 80])
@pytest.mark.parametrize("value", [20, 255])
def test_identify_icon_template_rejects_uniform_buttons(size: int, value: int) -> None:
    roi_hsv = np.full((size, size, 3), (14, 255, value), dtype=np.uint8)

    assert identify_icon_template(
        roi_hsv, hue_deg=28, hue_tolerance_deg=10, border_px=4,
    ) == (None, None)


def test_identify_icon_template_rejects_blank_button() -> None:
    roi_hsv = np.full((30, 31, 3), (14, 255, 255), dtype=np.uint8)

    assert identify_icon_template(
        roi_hsv, hue_deg=28, hue_tolerance_deg=10, border_px=4,
    ) == (None, None)


@pytest.mark.parametrize("template_rows", [("....",) * 4, ("#" * 23,) * 24])
def test_match_binary_icon_template_rejects_featureless_templates(template_rows: tuple[str, ...]) -> None:
    roi_hsv = np.full((30, 31, 3), (14, 255, 255), dtype=np.uint8)

    assert match_binary_icon_template(
        roi_hsv, template_rows,
        hue_deg=28, hue_tolerance_deg=10, border_px=4,
    ) is None


def test_match_binary_icon_template_does_not_match_only_a_fragment() -> None:
    template_rows, _ = ICON_TEMPLATES["exit"]
    glyph = binary_template(template_rows).astype(bool)
    height, width = glyph.shape
    roi_hsv = np.full((78, 78, 3), (14, 255, 255), dtype=np.uint8)
    roi_hsv[5:5 + height, 5:5 + width, 2][glyph] = 20
    roi_hsv[48:48 + height, 48:48 + width, 2][glyph] = 20

    # There are two exact local matches, but neither represents the whole icon.
    assert match_binary_icon_template(
        roi_hsv, template_rows, match_required=0.99,
        hue_deg=28, hue_tolerance_deg=10, border_px=4,
    ) is None


def test_match_exit_icon_template_respects_configurable_size_limit() -> None:
    glyph = cv2.resize(
        binary_template(ICON_TEMPLATES["exit"][0]), None, fx=4, fy=4,
        interpolation=cv2.INTER_NEAREST,
    ).astype(bool)
    height, width = glyph.shape
    roi_hsv = np.full((height + 8, width + 8, 3), (14, 255, 255), dtype=np.uint8)
    roi_hsv[4:-4, 4:-4, 2][glyph] = 20

    assert match_exit_icon_template(
        roi_hsv, hue_deg=28, hue_tolerance_deg=10, border_px=4,
    ) is None
    score = match_exit_icon_template(
        roi_hsv, hue_deg=28, hue_tolerance_deg=10, border_px=4, max_size=120,
    )
    assert score is not None and score > 0.9


@pytest.mark.parametrize("hud_color_matrix", [None, HudColorMatrix([
    [1.0, 0.0, 0.235], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0],
])])
@pytest.mark.parametrize("scale", [0.75, 1.0, 1.5, 2.0])
def test_detect_selected_area_identifies_scaled_exit_button(hud_color_matrix: HudColorMatrix | None, scale: float) -> None:
    image = np.zeros((720, 1280, 3), dtype=np.uint8)
    rgb = (255, 117, 0)
    if hud_color_matrix is not None:
        rgb = hud_color_matrix.shift_color(*rgb)
    color = np.array(bgr_from_rgb(rgb), dtype=np.uint8)
    button = np.empty((30, 31, 3), dtype=np.uint8)
    button[:] = color
    glyph = binary_template(ICON_TEMPLATES["exit"][0])[1:-1].astype(bool)
    button[4:-4, 4:-4][glyph] = color // 4
    button = cv2.resize(button, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
    height, width = button.shape[:2]
    image[655:655 + height, 50:50 + width] = button

    detection = ScreenReader(
        sample_colors=["ff7500"], hud_color_matrix=hud_color_matrix,
    ).detect_selected_area(image)

    assert detection is not None
    assert (detection.x, detection.y, detection.w, detection.h) == (50, 655, width, height)
    assert detection.icon_template == "exit"
    assert detection.icon_match is not None and detection.icon_match > 0.7


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
