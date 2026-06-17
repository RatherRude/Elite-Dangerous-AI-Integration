import os
from xml.etree.ElementTree import parse

from .Logger import log

REFERENCE_PRIMARY = (255, 117, 0)  # #FF7500
REFERENCE_SECONDARY = (105, 217, 218)  # #69D9DA
REFERENCE_ORANGE = REFERENCE_SECONDARY
IDENTITY_MATRIX: list[list[float]] = [
    [1.0, 0.0, 0.0],
    [0.0, 1.0, 0.0],
    [0.0, 0.0, 1.0],
]
MATRIX_TAGS = ("MatrixRed", "MatrixGreen", "MatrixBlue")
GRAPHICS_OVERRIDE_FILENAME = "GraphicsConfigurationOverride.xml"


class HudColorMatrix:
    def __init__(self, matrix: list[list[float]]):
        self._matrix = matrix

    @property
    def matrix(self) -> list[list[float]]:
        return self._matrix

    @classmethod
    def identity(cls) -> "HudColorMatrix":
        return cls(IDENTITY_MATRIX)

    @classmethod
    def load_from_appdata(cls, appdata_path: str) -> "HudColorMatrix":
        path = os.path.join(
            appdata_path,
            "Options",
            "Graphics",
            GRAPHICS_OVERRIDE_FILENAME,
        )
        return cls(cls._read_matrix_from_file(path))

    @classmethod
    def _read_matrix_from_file(cls, path: str) -> list[list[float]]:
        if not os.path.isfile(path):
            log("debug", "HUD color matrix file not found, using identity matrix", path)
            return IDENTITY_MATRIX

        try:
            root = parse(path).getroot()
            rows = []
            for tag in MATRIX_TAGS:
                element = root.find(f".//{tag}")
                if element is None or not element.text:
                    log("warning", f"Missing {tag} in HUD color matrix file, using identity matrix", path)
                    return IDENTITY_MATRIX
                row = cls._parse_matrix_row(element.text)
                if len(row) != 3:
                    log("warning", f"Invalid {tag} in HUD color matrix file, using identity matrix", path)
                    return IDENTITY_MATRIX
                rows.append(row)
            log("debug", "Loaded HUD color matrix from", path, rows)
            return rows
        except Exception as e:
            log("warning", "Failed to read HUD color matrix, using identity matrix", path, e)
            return IDENTITY_MATRIX

    @staticmethod
    def _parse_matrix_row(value: str) -> list[float]:
        return [float(part.strip()) for part in value.split(",") if part.strip()]

    def shift_color(self, red: int, green: int, blue: int) -> tuple[int, int, int]:
        # Each XML line (MatrixRed/MatrixGreen/MatrixBlue) describes how one
        # input channel contributes to all output channels, so we apply the
        # parsed matrix as a column-wise mix (transpose of an output-row layout).
        input_channels = (red / 255.0, green / 255.0, blue / 255.0)
        shifted_channels = []
        for output_index in range(3):
            mixed = sum(
                self._matrix[input_index][output_index] * input_channels[input_index]
                for input_index in range(3)
            )
            shifted_channels.append(self._clamp_channel(mixed))
        return (
            shifted_channels[0],
            shifted_channels[1],
            shifted_channels[2],
        )

    @staticmethod
    def _clamp_channel(value: float) -> int:
        return max(0, min(255, round(value * 255)))

    def shift_reference_orange(self) -> str:
        red, green, blue = self.shift_color(*REFERENCE_ORANGE)
        return f"#{red:02x}{green:02x}{blue:02x}"

    def shift_primary_color(self) -> str:
        red, green, blue = self.shift_color(*REFERENCE_PRIMARY)
        return f"#{red:02x}{green:02x}{blue:02x}"

    def shift_secondary_color(self) -> str:
        red, green, blue = self.shift_color(*REFERENCE_SECONDARY)
        return f"#{red:02x}{green:02x}{blue:02x}"
