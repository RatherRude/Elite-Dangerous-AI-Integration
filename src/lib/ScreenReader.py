from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import sleep
from typing import Any, final

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
        ".......................",
        ".......................",
        ".................#.....",
        ".....############......",
        ".....############......",
        "....####.......###.....",
        "....###........##......",
        "....###........##......",
        "....###.........#......",
        "....###....###.........",
        "....###..####..........",
        "....###..#########.....",
        "....###.##########.....",
        "....###...###..........",
        "....###....####........",
        "....###................",
        "....###........##......",
        "....###.....#..##......",
        "....####......###......",
        ".....############......",
        ".....#############.....",
        ".......................",
        ".......................",
        ".......................",
    )
)

COPY_ICON_TEMPLATE = tuple(
    row.replace(" ", "")
    for row in (
        ".......................",
        ".......................",
        ".......................",
        ".......................",
        ".....#########.........",
        "....############.......",
        "....##.......##........",
        "....##.......###.......",
        "....##...##########....",
        "....##############.....",
        "....#######..#.#.#.....",
        "....######.###..##.....",
        "....##.########.##.....",
        "....##############.....",
        ".....##########.##.....",
        "........######..##.....",
        "........###.#...##.....",
        "........##########.....",
        ".........#########.....",
        ".................#.....",
        ".......................",
        ".......................",
        ".......................",
    )
)
TARGET_ICON_TEMPLATE = tuple(
    row.replace(" ", "")
    for row in (
        ".......................",
        ".......................",
        "................#.#....",
        "...#####......#####....",
        "...#####......#####....",
        "...######.....#####....",
        "...#####.#.##.#####....",
        "....###..#####.####....",
        "......#.#######..#.....",
        ".......#########.......",
        ".......###.#.###.#.....",
        ".......##....###.......",
        ".......###...###.......",
        ".....#.########.#......",
        "...####.###########....",
        "...#####..##.######....",
        "...#######.#..#####....",
        "...######.....#####....",
        "..######.......###.....",
        ".......................",
        ".......................",
        ".......................",
        ".......................",
    )
)
ORRERY_ICON_TEMPLATE = tuple(
    row.replace(" ", "")
    for row in (
        ".......................",
        ".......................",
        ".......................",
        "......#.#######.#......",
        "......##########..#....",
        ".....####.....#####....",
        "....###....#########...",
        "..####..#######.####...",
        "...##..########.####...",
        "...##..##.#.####..##...",
        "..###.##..###.###.###..",
        "..###.##.####..##.###..",
        "..###.##.####..##.##...",
        "..#######.###.###.##...",
        "...##.###...####..##...",
        "...#############.###...",
        "...####.#######.###....",
        "..#####....###.###.....",
        "..##.######.#####......",
        ".......#########.......",
        "........######.........",
        ".......................",
        ".......................",
        ".......................",
    )
)
INFO_ICON_TEMPLATE = tuple(
    row.replace(" ", "")
    for row in (
        ".......................",
        ".......................",
        "..........##...........",
        ".......########.##.....",
        "....#.####...######....",
        "....####.......####....",
        "....##....##...####....",
        "...###....###..####....",
        "...##......#.....####..",
        "...##....###......##...",
        "..###....###......##...",
        "...##.....##......##...",
        ".#.##....###......##...",
        "...##....#####...###...",
        "...#####.#####...##....",
        "...#####......#.###....",
        "....####....#..###.....",
        "....#####....####......",
        ".....##########........",
        "....#.#...###..#.......",
        "............#..........",
        ".......................",
        ".......................",
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


def icon_glyph_mask(
    inner_hsv: np.ndarray,
    *,
    hue_deg: float,
    hue_tolerance_deg: float,
    selected_saturation_min: int,
    selected_saturation_max: int | None,
    selected_value_min: int,
) -> np.ndarray:
    # A transformed HUD profile can clamp the candidate threshold to 255.
    # Resampling makes even the bright background slightly darker than that;
    # leave headroom so it is not mistaken for part of the dark glyph.
    background_value = float(np.percentile(inner_hsv[:, :, 2], 90))
    value_min = min(selected_value_min, max(1, round(background_value * 0.9)))
    selected_color = (
        (hue_distance_deg(inner_hsv[:, :, 0], hue_deg) <= hue_tolerance_deg)
        & (inner_hsv[:, :, 1] >= selected_saturation_min)
        & (inner_hsv[:, :, 1] <= (255 if selected_saturation_max is None else selected_saturation_max))
        & (inner_hsv[:, :, 2] >= value_min)
    )
    return ~selected_color


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
    diagnostics_out: dict[str, Any] | None = None,
) -> float | None:
    """Match a glyph at any reliable scale within an icon-sized button."""
    height, width = roi_hsv.shape[:2]
    if width > max_size or height > max_size or abs(width - height) > 8:
        return None
    if width <= border_px * 2 or height <= border_px * 2:
        return None

    inner = roi_hsv[border_px : height - border_px, border_px : width - border_px]
    template = binary_template(template_rows)
    glyph_y, glyph_x = np.nonzero(template)
    if not glyph_y.size:
        return None
    # Padding is not part of the icon's shape or scale.
    glyph_template = template[
        glyph_y.min() : glyph_y.max() + 1,
        glyph_x.min() : glyph_x.max() + 1,
    ]
    if not np.ptp(glyph_template):
        return None

    glyph_mask = icon_glyph_mask(
        inner,
        hue_deg=hue_deg,
        hue_tolerance_deg=hue_tolerance_deg,
        selected_saturation_min=selected_saturation_min,
        selected_saturation_max=selected_saturation_max,
        selected_value_min=selected_value_min,
    ).astype(np.float32)
    glyph_pixels = float(glyph_mask.sum())
    if glyph_pixels == 0 or glyph_pixels == glyph_mask.size:
        return None

    # Retain the original comparison, then search uniformly scaled glyphs at
    # pixel-sized height steps. Preserve aspect ratio rather than stretching
    # every icon to the button's dimensions.
    candidates = [template]
    template_height, template_width = glyph_template.shape
    for scaled_height in range(8, inner.shape[0] + 1):
        scaled_width = round(template_width * scaled_height / template_height)
        if scaled_width < 8 or scaled_width > inner.shape[1]:
            continue
        candidates.append(cv2.resize(
            glyph_template, (scaled_width, scaled_height), interpolation=cv2.INTER_NEAREST,
        ))

    integral = cv2.integral(glyph_mask)
    best_score = -1.0
    best_details: dict[str, Any] = {}
    for candidate in candidates:
        candidate_height, candidate_width = candidate.shape
        if candidate_height > inner.shape[0] or candidate_width > inner.shape[1]:
            continue
        if not np.ptp(candidate):
            continue
        result = cv2.matchTemplate(glyph_mask, candidate, cv2.TM_CCOEFF_NORMED)
        # A tiny matching fragment of a different icon must not win. Compare
        # windows containing most of the observed glyph, allowing some noise.
        window_pixels = (
            integral[candidate_height:, candidate_width:]
            - integral[:-candidate_height, candidate_width:]
            - integral[candidate_height:, :-candidate_width]
            + integral[:-candidate_height, :-candidate_width]
        )
        valid = window_pixels >= glyph_pixels * 0.8
        if valid.any():
            scores = np.where(valid, result, -1.0)
            score = float(scores.max())
            if score > best_score:
                best_score = score
                if diagnostics_out is not None:
                    match_y, match_x = np.unravel_index(scores.argmax(), scores.shape)
                    best_details = {
                        "x": int(match_x), "y": int(match_y),
                        "w": candidate_width, "h": candidate_height,
                        "trimmed": candidate is not template,
                    }

    if diagnostics_out is not None:
        diagnostics_out.update(score=best_score, required=match_required, **best_details)

    if best_score < match_required:
        return None
    return best_score


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
    diagnostics_out: list[dict[str, Any]] | None = None,
) -> tuple[str | None, float | None]:
    best_name: str | None = None
    best_score: float | None = None

    for template_name, (template_rows, match_required) in ICON_TEMPLATES.items():
        details: dict[str, Any] = {"name": template_name, "score": None, "required": match_required}
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
            diagnostics_out=details if diagnostics_out is not None else None,
        )
        if diagnostics_out is not None:
            diagnostics_out.append(details)
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
    diagnostics_out: list[dict[str, Any]] | None = None,
) -> Detection | None:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]

    best: Detection | None = None
    diagnostics: list[dict[str, Any]] = []
    for profile in profiles:
        content_sat_min = round(profile.content_saturation_min * 255.0)
        content_sat_max = round(profile.content_saturation_max * 255.0)
        candidate_value_min = round(profile.candidate_value_min * 255.0)
        candidate_mask = np.uint8(
            (sat >= content_sat_min)
            & (sat <= content_sat_max)
            & (val >= candidate_value_min)
        ) * 255

        # Bridge small text/icon holes without inventing large new regions.
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        candidate_mask = cv2.morphologyEx(candidate_mask, cv2.MORPH_CLOSE, kernel, iterations=1)

        contours, _ = cv2.findContours(candidate_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        profile_diagnostics: dict[str, Any] = {
            "profile": profile.name,
            "sample_hex": profile.sample_hex,
            "saturation_range": [content_sat_min, content_sat_max],
            "candidate_value_min": candidate_value_min,
            "candidate_pixels": int(cv2.countNonZero(candidate_mask)),
            "contours": len(contours),
            "size_candidates": 0,
            "rejected_by_size": 0,
            "rejected_by_border": 0,
            "rejected_by_content": 0,
            "accepted": 0,
            "candidates": [],
        }
        candidate_diagnostics: list[dict[str, Any]] = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w < min_width or h < min_height:
                profile_diagnostics["rejected_by_size"] += 1
                continue
            if w <= border_px * 2 or h <= border_px * 2:
                profile_diagnostics["rejected_by_size"] += 1
                continue
            profile_diagnostics["size_candidates"] += 1
            # The closed colour contour can include neighbouring UI pixels.
            # Find the actual rectangular border within a few pixels of its
            # bounding box, rather than assuming the contour is the border.
            best_box = (x, y, w, h)
            best_rank = (-1, -1, -1.0)
            required_border = border_required if border_required is not None else profile.border_required
            for left in range(3):
                for top in range(3):
                    for right in range(3):
                        for bottom in range(4):
                            bx, by = x + left, y + top
                            bw, bh = w - left - right, h - top - bottom
                            if bw < min_width or bh < min_height:
                                continue
                            patch = hsv[by : by + bh, bx : bx + bw]
                            edge = apply_top_right_border_exclusion(
                                border_mask(bh, bw, border_px),
                                profile.exclude_top_right_border_height_fraction,
                            )
                            saturated = (
                                (patch[:, :, 1] >= round(profile.border_saturation_min * 255.0))
                                & (patch[:, :, 1] <= round(profile.border_saturation_max * 255.0))
                            )
                            edge_hues = patch[:, :, 0][edge & saturated]
                            if not edge_hues.size:
                                continue
                            edge_hue = circular_mean_hue_deg(edge_hues)
                            matching_border = saturated & (
                                hue_distance_deg(patch[:, :, 0], edge_hue) <= hue_tolerance_deg
                            )
                            score = float(matching_border[edge].mean())
                            bottom_score = float(matching_border[-1].mean())
                            # Prefer the largest box that clears the original
                            # border threshold, preserving the icon interior.
                            rank = (int(score >= required_border and bottom_score >= 0.7), bw * bh, score)
                            if rank > best_rank:
                                best_rank = rank
                                best_box = (bx, by, bw, bh)
            x, y, w, h = best_box
            candidate_diagnostic: dict[str, Any] = {
                "x": x,
                "y": y,
                "w": w,
                "h": h,
                "area": w * h,
            }

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
                candidate_diagnostic["rejected"] = "empty-border-ring"
                candidate_diagnostics.append(candidate_diagnostic)
                continue

            candidate_diagnostic["ring_saturation_match"] = round(float(saturated_ring.mean()), 4)
            ring_hue = roi_hue[ring][saturated_ring]
            if ring_hue.size == 0:
                profile_diagnostics["rejected_by_border"] += 1
                candidate_diagnostic["rejected"] = "border-saturation"
                candidate_diagnostics.append(candidate_diagnostic)
                continue
            hue_deg = circular_mean_hue_deg(ring_hue)
            candidate_diagnostic["hue_deg"] = round(hue_deg, 2)

            ring_hue_ok = hue_distance_deg(roi_hue[ring], hue_deg) <= hue_tolerance_deg
            border_ok = saturated_ring & ring_hue_ok
            border_match = float(border_ok.mean())
            required_border = border_required if border_required is not None else profile.border_required
            candidate_diagnostic["border_match"] = round(border_match, 4)
            candidate_diagnostic["border_required"] = required_border
            if border_match < required_border:
                profile_diagnostics["rejected_by_border"] += 1
                candidate_diagnostic["rejected"] = "border-match"
                candidate_diagnostics.append(candidate_diagnostic)
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
            candidate_diagnostic["content_match"] = round(content_match, 4)
            candidate_diagnostic["content_required"] = required_content
            if content_match < required_content:
                profile_diagnostics["rejected_by_content"] += 1
                candidate_diagnostic["rejected"] = "content-match"
                candidate_diagnostics.append(candidate_diagnostic)
                continue

            icon_diagnostics: list[dict[str, Any]] = []
            icon_template, icon_match = identify_icon_template(
                roi_hsv,
                hue_deg=hue_deg,
                hue_tolerance_deg=hue_tolerance_deg,
                border_px=border_px,
                selected_saturation_min=round(profile.content_saturation_min * 255.0),
                selected_saturation_max=round(profile.content_saturation_max * 255.0),
                selected_value_min=round(profile.candidate_value_min * 255.0),
                diagnostics_out=icon_diagnostics if diagnostics_out is not None else None,
            )
            if diagnostics_out is not None:
                candidate_diagnostic["icons"] = icon_diagnostics

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
            profile_diagnostics["accepted"] += 1
            candidate_diagnostic["accepted"] = True
            candidate_diagnostics.append(candidate_diagnostic)
            if best is None or detection.area > best.area:
                best = detection
        profile_diagnostics["candidates"] = sorted(
            candidate_diagnostics,
            key=lambda candidate: candidate["area"],
            reverse=True,
        )
        diagnostics.append(profile_diagnostics)

    if diagnostics_out is not None:
        diagnostics_out.extend(diagnostics)

    if best is None:
        log(
            "warn",
            "ScreenReader selection detection failed",
            {
                "image_shape": list(image.shape),
                "border_px": border_px,
                "hue_tolerance_deg": hue_tolerance_deg,
                "min_width": min_width,
                "min_height": min_height,
                "profiles": diagnostics,
            },
        )

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
        debug_directory: str | Path | None = None,
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
        self.debug_directory = Path(debug_directory) if debug_directory is not None else None

    def detect_selected_area(self, image: np.ndarray | None = None) -> Detection | None:
        if image is None:
            image = self.get_screen()
        if image is None:
            return None

        return self._detect_selected_area(image)

    def detect_selected_area_with_diagnostics(
        self,
        image: np.ndarray,
    ) -> tuple[Detection | None, list[dict[str, Any]]]:
        diagnostics: list[dict[str, Any]] = []
        detection = self._detect_selected_area(image, diagnostics_out=diagnostics)
        return detection, diagnostics

    def _detect_selected_area(
        self,
        image: np.ndarray,
        *,
        diagnostics_out: list[dict[str, Any]] | None = None,
    ) -> Detection | None:
        return find_detection(
            image,
            profiles=self.profiles,
            border_px=self.border_px,
            border_required=self.border_required,
            content_required=self.content_required,
            hue_tolerance_deg=self.hue_tolerance_deg,
            min_width=self.min_width,
            min_height=self.min_height,
            diagnostics_out=diagnostics_out,
        )

    def read_selected_area(self, image: np.ndarray | None = None) -> ScreenReadResult:
        if image is None:
            image = self.get_screen()
        if image is None:
            raise Exception("Unable to capture screen for OCR")

        diagnostics: list[dict[str, Any]] = []
        if self.debug_directory is not None:
            detection, diagnostics = self.detect_selected_area_with_diagnostics(image)
        else:
            detection = self.detect_selected_area(image)
        if detection is None:
            if self.debug_directory is not None:
                self.save_debug_bundle(image, None, [], diagnostics, error="No selected area detected")
            else:
                self.save_debug_image(image, "no-selected-area")
            raise Exception("No selected area detected")

        lines: list[OcrLine] = []
        error: str | None = None
        try:
            lines = self.read_detection_text(image, detection)
            return ScreenReadResult(detection=detection, ocr_lines=lines)
        except Exception as exc:
            error = str(exc)
            raise
        finally:
            if self.debug_directory is not None:
                self.save_debug_bundle(image, detection, lines, diagnostics, error=error)

    def save_debug_bundle(
        self,
        image: np.ndarray,
        detection: Detection | None,
        lines: list[OcrLine],
        diagnostics: list[dict[str, Any]],
        *,
        error: str | None = None,
        stage: str = "read",
    ) -> Path | None:
        """Save the exact frame used for a read, not a later screenshot."""
        if self.debug_directory is None:
            return None
        try:
            self.debug_directory.mkdir(parents=True, exist_ok=True)
            stem = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ") + f"-{stage}"

            def write_image(suffix: str, pixels: np.ndarray) -> None:
                path = self.debug_directory / f"{stem}-{suffix}.png"
                if not cv2.imwrite(str(path), pixels):
                    raise OSError(f"OpenCV could not write {path}")

            write_image("source", image)
            annotated = image.copy()
            for profile in diagnostics:
                for candidate in profile["candidates"]:
                    x, y, w, h = (candidate[key] for key in ("x", "y", "w", "h"))
                    color = (0, 180, 0) if candidate.get("accepted") else (0, 0, 180)
                    cv2.rectangle(annotated, (x, y), (x + w - 1, y + h - 1), color, 1)
            if detection is not None:
                x, y, w, h = detection.x, detection.y, detection.w, detection.h
                cv2.rectangle(annotated, (x, y), (x + w - 1, y + h - 1), (0, 255, 255), 2)
                label = f"{detection.icon_template or 'unknown'} {detection.icon_match or 0:.3f}"
                cv2.putText(annotated, label, (x, max(18, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                crop = crop_detection(image, detection)
                write_image("selection", cv2.resize(crop, None, fx=8, fy=8, interpolation=cv2.INTER_NEAREST))
                profile = next(p for p in self.profiles if p.name == detection.profile)
                hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)[self.border_px:-self.border_px, self.border_px:-self.border_px]
                mask = icon_glyph_mask(
                    hsv,
                    hue_deg=detection.hue_deg,
                    hue_tolerance_deg=self.hue_tolerance_deg,
                    selected_saturation_min=round(profile.content_saturation_min * 255),
                    selected_saturation_max=round(profile.content_saturation_max * 255),
                    selected_value_min=round(profile.candidate_value_min * 255),
                )
                glyph = np.uint8(mask) * 255
                write_image("glyph", cv2.resize(glyph, None, fx=8, fy=8, interpolation=cv2.INTER_NEAREST))
                # Show the winning template at its actual scale and position.
                candidate = next((
                    c for p in diagnostics if p["profile"] == detection.profile
                    for c in p["candidates"] if (c["x"], c["y"], c["w"], c["h"]) == (x, y, w, h)
                ), {})
                scored = [i for i in candidate.get("icons", []) if i.get("w") is not None]
                if scored:
                    best = max(scored, key=lambda i: i["score"])
                    template = binary_template(ICON_TEMPLATES[best["name"]][0])
                    if best["trimmed"]:
                        ty, tx = np.nonzero(template)
                        template = template[ty.min():ty.max() + 1, tx.min():tx.max() + 1]
                    template = cv2.resize(template, (best["w"], best["h"]), interpolation=cv2.INTER_NEAREST)
                    overlay = np.zeros((*glyph.shape, 3), dtype=np.uint8)
                    overlay[:, :, 1] = glyph
                    overlay[best["y"]:best["y"] + best["h"], best["x"]:best["x"] + best["w"], 2] = np.uint8(template * 255)
                    write_image("comparison", cv2.resize(overlay, None, fx=8, fy=8, interpolation=cv2.INTER_NEAREST))
            write_image("annotated", annotated)
            metadata_path = self.debug_directory / f"{stem}-read.json"
            metadata_path.write_text(json.dumps({
                "stage": stage,
                "detection": asdict(detection) if detection else None,
                "ocr_lines": [asdict(line) for line in lines],
                "error": error,
                "profiles": diagnostics,
            }, indent=2), encoding="utf-8")
            log("debug", "ScreenReader debug read", str(metadata_path), detection, [line.text for line in lines])
            return metadata_path
        except Exception as exc:
            log("warn", "Unable to save ScreenReader debug bundle", exc)
            return None

    def capture_debug_state(self, stage: str) -> Path | None:
        if self.debug_directory is None:
            return None
        try:
            image = self.get_screen()
            if image is None:
                log("warn", "Unable to capture debug state", stage)
                return None
            detection, diagnostics = self.detect_selected_area_with_diagnostics(image)
            return self.save_debug_bundle(image, detection, [], diagnostics, stage=stage)
        except Exception as error:
            log("warn", "Unable to capture debug state", stage, error)
            return None

    @staticmethod
    def save_debug_image(image: np.ndarray, reason: str) -> Path | None:
        try:
            output_dir = Path.cwd() / "logs" / "screen-reader"
            output_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
            output_path = output_dir / f"{reason}-{timestamp}.png"
            if not cv2.imwrite(str(output_path), image):
                raise OSError(f"OpenCV could not write {output_path}")
            log("warn", "Saved ScreenReader debug image", str(output_path))
            return output_path
        except Exception as error:
            log("error", "Failed to save ScreenReader debug image", error)
            return None

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

    def get_screen(self, new_height: int = 720) -> np.ndarray | None:
        pil_img = self.screenshot(new_height=new_height)
        if pil_img is None:
            return None
        return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    def get_game_window_handle(self):
        from .Screenshot import get_windows_game_window_handle

        return get_windows_game_window_handle()

    def setGameWindowActive(self):
        set_game_window_active()

    def screenshot(self, new_height: int = 720):
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
