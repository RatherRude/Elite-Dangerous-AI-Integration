from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from time import sleep
from typing import final

import cv2
import numpy as np

from .Logger import log
from .Screenshot import screenshot_game_window, set_game_window_active
from .HudColorMatrix import HudColorMatrix


@dataclass(frozen=True)
class Detection:
    profile: str
    x: int
    y: int
    w: int
    h: int
    area: int
    hue_deg: float
    border_match: float
    content_match: float
    icon_template: str | None = None
    icon_match: float | None = None


@dataclass(frozen=True)
class OcrLine:
    text: str
    confidence: float
    x: float | None = None
    y: float | None = None
    w: float | None = None
    h: float | None = None


@dataclass(frozen=True)
class ScreenReadResult:
    detection: Detection | None
    ocr_lines: list[OcrLine]

    @property
    def text(self) -> str:
        return " | ".join(line.text for line in self.ocr_lines)


@dataclass(frozen=True)
class Profile:
    name: str
    sample_hex: str
    border_saturation_min: float
    border_saturation_max: float
    border_required: float
    exclude_top_right_border_height_fraction: float
    content_saturation_min: float
    content_saturation_max: float
    content_required: float
    candidate_value_min: float


EXIT_ICON_TEMPLATE = tuple(
    row.replace(" ", "")
    for row in (
        "###################..",
        "####################.",
        "##................##.",
        "##................##.",
        "##................##.",
        "##...................",
        "##...................",
        "##...................",
        "##..........#........",
        "##......#####........",
        "##.....##############",
        "##.....#############.",
        "##.......####........",
        "##..........#........",
        "##...................",
        "##...................",
        "##...................",
        "##................##.",
        "##................##.",
        "##................##.",
        "####################.",
    )
)

COPY_ICON_TEMPLATE = tuple(
    row.replace(" ", "")
    for row in (
        "...............................",
        "...............................",
        "...............................",
        "...............................",
        "...............................",
        ".......############............",
        "......#........................",
        "......#........................",
        "......#........................",
        "......#........................",
        "......#........................",
        "......#.....#.#.#########......",
        "......#..#..#...........#......",
        "......#..###............#......",
        "......#...##.....#......#......",
        "......#...###....#......#......",
        "......#....########.....#......",
        "......#....#########....#......",
        "......#..#...#######....#......",
        "................###.....#......",
        "............#....#......#......",
        "............#...........#......",
        "............#...........#......",
        "............#...........#......",
        "................#..##..##......",
        "...............................",
        "...............................",
        "...............................",
        "...............................",
        "...............................",
    )
)
TARGET_ICON_TEMPLATE = tuple(
    row.replace(" ", "")
    for row in (
        "...............................",
        "...............................",
        "...............................",
        "...............................",
        ".....####.............####.....",
        ".....#####...........#####.....",
        ".....######.........######.....",
        "....######...........#####.....",
        ".....####.............####.....",
        "......##...............##......",
        ".............#####.............",
        "............########...........",
        "...........##.....##...........",
        "..........###......##..........",
        "..........##.......##..........",
        "..........##........#..........",
        "..........##.......##..........",
        "...........##......##..........",
        "...........###....##...........",
        "............#######............",
        "......##.....#####.....##......",
        ".....####.............####.....",
        ".....#####...........#####.....",
        ".....######.........######.....",
        ".....#####...........#####.....",
        ".....####.............###......",
        "...............................",
        "...............................",
        "...............................",
        "...............................",
    )
)
ORRERY_ICON_TEMPLATE = tuple(
    row.replace(" ", "")
    for row in (
        "...............................",
        "...............................",
        "...............................",
        "...........####.####...........",
        ".........##..........#.........",
        "........#.............#........",
        ".......#...............####....",
        "......#.........###....####....",
        ".....#......#######.....###....",
        ".....#.....#....####....###....",
        "....#.....#.........#.....#....",
        "....#................#.........",
        ".........#...........#.........",
        "...#.....#....###..........#...",
        "...#.....#....####.........#...",
        "...#.....#....####.........#...",
        ".........#....###..........#...",
        "....#....#.................#...",
        "....#..........................",
        "....##....#.........#.....#....",
        "....###....#....####......#....",
        "....####.......####......#.....",
        "....####........###............",
        "......#........................",
        "........#.............#........",
        ".........##.........##.........",
        "...........#########...........",
        "...............................",
        "...............................",
        "...............................",
    )
)
INFO_ICON_TEMPLATE = tuple(
    row.replace(" ", "")
    for row in (
        "..............................",
        "..............................",
        "..............................",
        "..............................",
        "..........#########...........",
        "........##.........#####......",
        ".......#.............####.....",
        "......#..............####.....",
        ".....#...............####.....",
        "....#.........##......###.....",
        "....#.........#.........#.....",
        "...#.....................#....",
        "...#.....................#....",
        "...#.........##..........#....",
        ".............##...............",
        "..............#...............",
        "...#..........#...............",
        "...#..........#..........#....",
        "...#..........#..........#....",
        "...#.........###.........#....",
        "....#.......#####.............",
        "....###.................#.....",
        "....#####..............#......",
        "....#####.....................",
        "....#####............#........",
        ".....#####..........#.........",
        "..........#########...........",
        "..............................",
        "..............................",
        "..............................",
    )
)
ICON_TEMPLATES: dict[str, tuple[tuple[str, ...], float]] = {
    "exit": (EXIT_ICON_TEMPLATE, 0.35),
    "orrery": (ORRERY_ICON_TEMPLATE, 0.35),
    "target": (TARGET_ICON_TEMPLATE, 0.35),
    "copy": (COPY_ICON_TEMPLATE, 0.35),
    "info": (INFO_ICON_TEMPLATE, 0.35),
}
EXIT_ICON_MATCH_REQUIRED = ICON_TEMPLATES["exit"][1]


def parse_hex_color(value: str) -> tuple[int, int, int]:
    text = value.strip().removeprefix("#")
    if len(text) != 6:
        raise argparse.ArgumentTypeError(f"expected RRGGBB color, got {value!r}")
    try:
        return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected RRGGBB color, got {value!r}") from exc


def sample_color_sv(sample_hex: str) -> tuple[float, float]:
    r, g, b = parse_hex_color(sample_hex)
    rgb = np.uint8([[[r, g, b]]])
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)[0, 0]
    return float(hsv[1]) / 255.0, float(hsv[2]) / 255.0


def sample_color_hsv(sample_hex: str) -> tuple[float, float, float]:
    r, g, b = parse_hex_color(sample_hex)
    rgb = np.uint8([[[r, g, b]]])
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)[0, 0]
    return float(hsv[0]) * 2.0, float(hsv[1]) / 255.0, float(hsv[2]) / 255.0


def format_hex_color(rgb: np.ndarray) -> str:
    values = np.clip(np.rint(rgb * 255.0), 0, 255).astype(np.uint8)
    return "".join(f"{int(value):02x}" for value in values)


def transform_rgb(rgb: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    return np.clip(rgb @ matrix, 0.0, 1.0)


def transformed_sample_hex(sample_hex: str, matrix: np.ndarray) -> str:
    r, g, b = parse_hex_color(sample_hex)
    rgb = np.array([r, g, b], dtype=np.float32) / 255.0
    return format_hex_color(transform_rgb(rgb, matrix))


def clamped_range(center: float, tolerance: float) -> tuple[float, float]:
    return max(0.0, center - tolerance), min(1.0, center + tolerance)


def transformed_sv_bounds(
    sample_hex: str,
    matrix: np.ndarray,
    *,
    saturation_tolerance: float,
    candidate_value_tolerance: float,
    hue_tolerance_deg: float,
) -> tuple[float, float, float]:
    hue_deg, sample_sat, sample_val = sample_color_hsv(sample_hex)
    saturations = np.linspace(*clamped_range(sample_sat, saturation_tolerance), num=9)
    values = np.linspace(max(0.0, sample_val - candidate_value_tolerance), 1.0, num=5)
    hue_offsets = np.linspace(-hue_tolerance_deg, hue_tolerance_deg, num=9)
    transformed_hsv_values: list[np.ndarray] = []

    for hue_offset in hue_offsets:
        hue = ((hue_deg + hue_offset) % 360.0) / 2.0
        for saturation in saturations:
            for value in values:
                hsv = np.uint8([[[round(hue), round(saturation * 255.0), round(value * 255.0)]]])
                rgb = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)[0, 0].astype(np.float32) / 255.0
                transformed = transform_rgb(rgb, matrix)
                transformed_rgb = np.uint8([[np.rint(transformed * 255.0)]])
                transformed_hsv_values.append(cv2.cvtColor(transformed_rgb, cv2.COLOR_RGB2HSV)[0, 0])

    transformed_hsv = np.array(transformed_hsv_values)
    return (
        float(transformed_hsv[:, 1].min()) / 255.0,
        float(transformed_hsv[:, 1].max()) / 255.0,
        float(transformed_hsv[:, 2].min()) / 255.0,
    )


def build_profiles(
    sample_colors: list[str],
    *,
    saturation_tolerance: float,
    candidate_value_tolerance: float,
    hue_tolerance_deg: float,
    hud_color_matrix: np.ndarray | None,
) -> list[Profile]:
    profiles: list[Profile] = []
    for sample_hex in sample_colors:
        normalized_hex = sample_hex.strip().removeprefix("#").lower()
        if hud_color_matrix is None:
            derived_hex = normalized_hex
            sample_sat, sample_val = sample_color_sv(sample_hex)
            border_min, border_max = clamped_range(sample_sat, saturation_tolerance)
            candidate_value_min = max(0.0, sample_val - candidate_value_tolerance)
        else:
            derived_hex = transformed_sample_hex(sample_hex, hud_color_matrix)
            border_min, border_max, candidate_value_min = transformed_sv_bounds(
                sample_hex,
                hud_color_matrix,
                saturation_tolerance=saturation_tolerance,
                candidate_value_tolerance=candidate_value_tolerance,
                hue_tolerance_deg=hue_tolerance_deg,
            )
        content_min, content_max = border_min, border_max
        profile_name = f"sample-{normalized_hex}"
        if derived_hex != normalized_hex:
            profile_name += f"-as-{derived_hex}"
        profiles.append(
            Profile(
                name=profile_name,
                sample_hex=derived_hex,
                border_saturation_min=border_min,
                border_saturation_max=border_max,
                border_required=0.90,
                exclude_top_right_border_height_fraction=0.5,
                content_saturation_min=content_min,
                content_saturation_max=content_max,
                content_required=0.70,
                candidate_value_min=candidate_value_min,
            )
        )
    return profiles


def normalize_hud_color_matrix(hud_color_matrix: HudColorMatrix | list[list[float]] | None) -> np.ndarray | None:
    if hud_color_matrix is None:
        return None
    matrix = hud_color_matrix.matrix if isinstance(hud_color_matrix, HudColorMatrix) else hud_color_matrix
    normalized = np.array(matrix, dtype=np.float32)
    if normalized.shape != (3, 3):
        raise ValueError(f"HUD color matrix must be 3x3, got {normalized.shape}")
    return normalized


def hue_distance_deg(hue: np.ndarray, target_deg: float) -> np.ndarray:
    deg = hue.astype(np.float32) * 2.0
    diff = np.abs(deg - target_deg)
    return np.minimum(diff, 360.0 - diff)


def circular_mean_hue_deg(hue: np.ndarray) -> float:
    deg = hue.astype(np.float32) * (math.pi / 90.0)
    sin_sum = np.sin(deg).sum()
    cos_sum = np.cos(deg).sum()
    angle = math.atan2(float(sin_sum), float(cos_sum))
    if angle < 0:
        angle += math.tau
    return math.degrees(angle)


def binary_template(rows: tuple[str, ...]) -> np.ndarray:
    width = max(len(row) for row in rows)
    normalized_rows = tuple(row.ljust(width, ".") for row in rows)
    return np.array([[1.0 if char == "#" else 0.0 for char in row] for row in normalized_rows], dtype=np.float32)


def match_binary_icon_template(
    roi_hsv: np.ndarray,
    template_rows: tuple[str, ...],
    *,
    hue_deg: float,
    hue_tolerance_deg: float,
    border_px: int,
    max_size: int = 80,
    match_required: float = 0.35,
    selected_saturation_min: int = 180,
    selected_saturation_max: int | None = None,
    selected_value_min: int = 100,
) -> float | None:
    height, width = roi_hsv.shape[:2]
    if width > max_size or height > max_size or abs(width - height) > 8:
        return None
    if width <= border_px * 2 or height <= border_px * 2:
        return None

    inner = roi_hsv[border_px : height - border_px, border_px : width - border_px]
    template = binary_template(template_rows)
    if inner.shape[0] < template.shape[0] or inner.shape[1] < template.shape[1]:
        return None

    inner_hue = inner[:, :, 0]
    inner_sat = inner[:, :, 1]
    inner_val = inner[:, :, 2]
    selected_saturation_max = 255 if selected_saturation_max is None else selected_saturation_max
    selected_color = (
        (hue_distance_deg(inner_hue, hue_deg) <= hue_tolerance_deg)
        & (inner_sat >= selected_saturation_min)
        & (inner_sat <= selected_saturation_max)
        & (inner_val >= selected_value_min)
    )
    glyph_mask = (~selected_color).astype(np.float32)
    result = cv2.matchTemplate(glyph_mask, template, cv2.TM_CCOEFF_NORMED)
    if result.size == 0:
        return None

    score = float(result.max())
    if score < match_required:
        return None
    return score


def match_exit_icon_template(
    roi_hsv: np.ndarray,
    *,
    hue_deg: float,
    hue_tolerance_deg: float,
    border_px: int,
    max_size: int = 80,
    selected_saturation_min: int = 180,
    selected_saturation_max: int | None = None,
    selected_value_min: int = 100,
) -> float | None:
    template_rows, match_required = ICON_TEMPLATES["exit"]
    return match_binary_icon_template(
        roi_hsv,
        template_rows,
        hue_deg=hue_deg,
        hue_tolerance_deg=hue_tolerance_deg,
        border_px=border_px,
        max_size=max_size,
        match_required=match_required,
        selected_saturation_min=selected_saturation_min,
        selected_saturation_max=selected_saturation_max,
        selected_value_min=selected_value_min,
    )


def identify_icon_template(
    roi_hsv: np.ndarray,
    *,
    hue_deg: float,
    hue_tolerance_deg: float,
    border_px: int,
    max_size: int = 80,
    selected_saturation_min: int = 180,
    selected_saturation_max: int | None = None,
    selected_value_min: int = 100,
) -> tuple[str | None, float | None]:
    best_name: str | None = None
    best_score: float | None = None

    for template_name, (template_rows, match_required) in ICON_TEMPLATES.items():
        score = match_binary_icon_template(
            roi_hsv,
            template_rows,
            hue_deg=hue_deg,
            hue_tolerance_deg=hue_tolerance_deg,
            border_px=border_px,
            max_size=max_size,
            match_required=match_required,
            selected_saturation_min=selected_saturation_min,
            selected_saturation_max=selected_saturation_max,
            selected_value_min=selected_value_min,
        )
        if score is None:
            continue
        if best_score is None or score > best_score:
            best_name = template_name
            best_score = score

    return best_name, best_score


def border_mask(height: int, width: int, border_px: int) -> np.ndarray:
    mask = np.zeros((height, width), dtype=bool)
    b = min(border_px, height // 2, width // 2)
    if b <= 0:
        return mask
    mask[:b, :] = True
    mask[-b:, :] = True
    mask[:, :b] = True
    mask[:, -b:] = True
    return mask


def apply_top_right_border_exclusion(mask: np.ndarray, height_fraction: float) -> np.ndarray:
    if height_fraction <= 0.0:
        return mask

    output = mask.copy()
    height, width = output.shape
    size = max(1, round(height * height_fraction))
    output[:size, max(0, width - size) :] = False
    return output


def find_detection(
    image: np.ndarray,
    *,
    profiles: list[Profile],
    border_px: int,
    border_required: float | None,
    content_required: float | None,
    hue_tolerance_deg: float,
    min_width: int,
    min_height: int,
) -> Detection | None:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]

    best: Detection | None = None
    for profile in profiles:
        content_sat_min = round(profile.content_saturation_min * 255.0)
        content_sat_max = round(profile.content_saturation_max * 255.0)
        candidate_mask = np.uint8(
            (sat >= content_sat_min)
            & (sat <= content_sat_max)
            & (val >= round(profile.candidate_value_min * 255.0))
        ) * 255

        # Bridge small text/icon holes without inventing large new regions.
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        candidate_mask = cv2.morphologyEx(candidate_mask, cv2.MORPH_CLOSE, kernel, iterations=1)

        contours, _ = cv2.findContours(candidate_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w < min_width or h < min_height:
                continue
            if w <= border_px * 2 or h <= border_px * 2:
                continue

            roi_hsv = hsv[y : y + h, x : x + w]
            roi_hue = roi_hsv[:, :, 0]
            roi_sat = roi_hsv[:, :, 1]

            full_ring = border_mask(h, w, border_px)
            ring = apply_top_right_border_exclusion(
                full_ring,
                profile.exclude_top_right_border_height_fraction,
            )
            ring_sat = roi_sat[ring]
            saturated_ring = (
                (ring_sat >= round(profile.border_saturation_min * 255.0))
                & (ring_sat <= round(profile.border_saturation_max * 255.0))
            )
            if saturated_ring.size == 0:
                continue

            ring_hue = roi_hue[ring][saturated_ring]
            if ring_hue.size == 0:
                continue
            hue_deg = circular_mean_hue_deg(ring_hue)

            ring_hue_ok = hue_distance_deg(roi_hue[ring], hue_deg) <= hue_tolerance_deg
            border_ok = saturated_ring & ring_hue_ok
            border_match = float(border_ok.mean())
            required_border = border_required if border_required is not None else profile.border_required
            if border_match < required_border:
                continue

            content = ~full_ring
            content_sat = roi_sat[content]
            content_sat_ok = (
                (content_sat >= round(profile.content_saturation_min * 255.0))
                & (content_sat <= round(profile.content_saturation_max * 255.0))
            )
            content_hue_ok = hue_distance_deg(roi_hue[content], hue_deg) <= hue_tolerance_deg
            content_match = float((content_sat_ok & content_hue_ok).mean())
            required_content = content_required if content_required is not None else profile.content_required
            if content_match < required_content:
                continue

            icon_template, icon_match = identify_icon_template(
                roi_hsv,
                hue_deg=hue_deg,
                hue_tolerance_deg=hue_tolerance_deg,
                border_px=border_px,
                selected_saturation_min=round(profile.content_saturation_min * 255.0),
                selected_saturation_max=round(profile.content_saturation_max * 255.0),
                selected_value_min=round(profile.candidate_value_min * 255.0),
            )

            detection = Detection(
                profile=profile.name,
                x=x,
                y=y,
                w=w,
                h=h,
                area=w * h,
                hue_deg=hue_deg,
                border_match=border_match,
                content_match=content_match,
                icon_template=icon_template,
                icon_match=icon_match,
            )
            if best is None or detection.area > best.area:
                best = detection

    return best


def crop_detection(image: np.ndarray, detection: Detection, padding: int = 0) -> np.ndarray:
    x0 = max(0, detection.x - padding)
    y0 = max(0, detection.y - padding)
    x1 = min(image.shape[1], detection.x + detection.w + padding)
    y1 = min(image.shape[0], detection.y + detection.h + padding)
    return image[y0:y1, x0:x1]


def ocr_item_bbox(item: object) -> tuple[float, float, float, float] | None:
    try:
        points = np.array(item[0], dtype=np.float32)  # type: ignore[index]
    except (TypeError, ValueError, IndexError):
        return None
    if points.ndim != 2 or points.shape[0] == 0 or points.shape[1] < 2:
        return None

    x0 = float(points[:, 0].min())
    y0 = float(points[:, 1].min())
    x1 = float(points[:, 0].max())
    y1 = float(points[:, 1].max())
    return x0, y0, x1 - x0, y1 - y0


def group_ocr_lines(boxes: list[OcrLine]) -> list[OcrLine]:
    groups: list[list[OcrLine]] = []
    for box in sorted(boxes, key=lambda line: ((line.y or 0.0) + (line.h or 0.0) / 2.0, line.x or 0.0)):
        if box.y is None or box.h is None:
            groups.append([box])
            continue

        center_y = box.y + box.h / 2.0
        matched_group: list[OcrLine] | None = None
        for group in groups:
            group_boxes = [line for line in group if line.y is not None and line.h is not None]
            if not group_boxes:
                continue
            group_center_y = sum(line.y + line.h / 2.0 for line in group_boxes) / len(group_boxes)
            group_height = sum(line.h for line in group_boxes) / len(group_boxes)
            if abs(center_y - group_center_y) <= max(8.0, min(box.h, group_height) * 0.75):
                matched_group = group
                break

        if matched_group is None:
            groups.append([box])
        else:
            matched_group.append(box)

    lines: list[OcrLine] = []
    for group in groups:
        ordered = sorted(group, key=lambda line: line.x or 0.0)
        text = " ".join(line.text for line in ordered).strip()
        if not text:
            continue
        confidences = [line.confidence for line in ordered]
        positioned = [line for line in ordered if line.x is not None and line.y is not None and line.w is not None and line.h is not None]
        if positioned:
            x0 = min(line.x for line in positioned if line.x is not None)
            y0 = min(line.y for line in positioned if line.y is not None)
            x1 = max((line.x or 0.0) + (line.w or 0.0) for line in positioned)
            y1 = max((line.y or 0.0) + (line.h or 0.0) for line in positioned)
            lines.append(OcrLine(text=text, confidence=float(sum(confidences) / len(confidences)), x=x0, y=y0, w=x1 - x0, h=y1 - y0))
        else:
            lines.append(OcrLine(text=text, confidence=float(sum(confidences) / len(confidences))))

    return sorted(lines, key=lambda line: (line.y if line.y is not None else float("inf"), line.x or 0.0))


@final
class ScreenReader:
    def __init__(
        self,
        sample_colors: list[str] | None = None,
        *,
        hud_color_matrix: HudColorMatrix | list[list[float]] | None = None,
        saturation_tolerance: float = 0.25,
        candidate_value_tolerance: float = 0.10,
        border_px: int = 4,
        border_required: float | None = None,
        content_required: float | None = None,
        hue_tolerance_deg: float = 10.0,
        min_width: int = 20,
        min_height: int = 20,
    ):
        self.hud_color_matrix = normalize_hud_color_matrix(hud_color_matrix)
        self.profiles = build_profiles(
            sample_colors or ["69d9da", "ff7500"],
            saturation_tolerance=saturation_tolerance,
            candidate_value_tolerance=candidate_value_tolerance,
            hue_tolerance_deg=hue_tolerance_deg,
            hud_color_matrix=self.hud_color_matrix,
        )
        self.border_px = border_px
        self.border_required = border_required
        self.content_required = content_required
        self.hue_tolerance_deg = hue_tolerance_deg
        self.min_width = min_width
        self.min_height = min_height
        self._ocr: object | None = None

    def detect_selected_area(self, image: np.ndarray | None = None) -> Detection | None:
        if image is None:
            image = self.get_screen()
        if image is None:
            return None

        return find_detection(
            image,
            profiles=self.profiles,
            border_px=self.border_px,
            border_required=self.border_required,
            content_required=self.content_required,
            hue_tolerance_deg=self.hue_tolerance_deg,
            min_width=self.min_width,
            min_height=self.min_height,
        )

    def read_selected_area(self, image: np.ndarray | None = None) -> ScreenReadResult:
        if image is None:
            image = self.get_screen()
        if image is None:
            raise Exception("Unable to capture screen for OCR")

        detection = self.detect_selected_area(image)
        if detection is None:
            raise Exception("No selected area detected")

        return ScreenReadResult(detection=detection, ocr_lines=self.read_detection_text(image, detection))

    def read_detection_text(self, image: np.ndarray, detection: Detection) -> list[OcrLine]:
        ocr = self.get_ocr()
        if ocr is None:
            return []

        crop = crop_detection(image, detection)
        result, _ = ocr(crop)  # type: ignore[operator]
        if not result:
            return []

        boxes: list[OcrLine] = []
        for item in result:
            if len(item) < 3:
                continue
            text = str(item[1]).strip()
            if not text:
                continue
            bbox = ocr_item_bbox(item)
            if bbox is None:
                boxes.append(OcrLine(text=text, confidence=float(item[2])))
                continue
            x, y, w, h = bbox
            boxes.append(OcrLine(text=text, confidence=float(item[2]), x=x, y=y, w=w, h=h))
        return group_ocr_lines(boxes)

    def get_ocr(self) -> object | None:
        if self._ocr is not None:
            return self._ocr
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError:
            log("warning", "rapidocr_onnxruntime is not installed; screen OCR is unavailable")
            return None

        self._ocr = RapidOCR()
        return self._ocr

    def get_screen(self, new_height: int = 1080) -> np.ndarray | None:
        pil_img = self.screenshot(new_height=new_height)
        if pil_img is None:
            return None
        return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    def get_game_window_handle(self):
        from .Screenshot import get_windows_game_window_handle

        return get_windows_game_window_handle()

    def setGameWindowActive(self):
        set_game_window_active()

    def screenshot(self, new_height: int = 1080):
        return screenshot_game_window(new_height)


if __name__ == "__main__":
    from .Config import load_config, load_hud_color_matrix

    config = load_config()
    hud_color_matrix = load_hud_color_matrix(config)
    reader = ScreenReader(hud_color_matrix=hud_color_matrix)
    while True:
        result = reader.read_selected_area()
        if result.detection is None:
            print("no selected area detected")
        else:
            detection = result.detection
            icon_text = ""
            if detection.icon_template is not None and detection.icon_match is not None:
                icon_text = f" icon={detection.icon_template}:{detection.icon_match:.3f}"
            ocr_text = f" ocr={result.text!r}" if result.text else ""
            print(
                f"x={detection.x} y={detection.y} w={detection.w} h={detection.h} "
                f"profile={detection.profile} hue={detection.hue_deg:.1f} "
                f"border={detection.border_match:.3f} content={detection.content_match:.3f}"
                f"{icon_text}{ocr_text}"
            )
        sleep(1)
