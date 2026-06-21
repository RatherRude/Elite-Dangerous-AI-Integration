import json
from pathlib import Path

from .Logger import log


EDHM_DEFAULT_INI_DIR = Path.home() / "EDHM_UI" / "ODYSS" / "EDHM" / "EDHM-Ini"
EDHM_REGISTRY_KEYS = (
    "SOFTWARE\\EDHM_UI",
    "SOFTWARE\\EDHM",
)
EDHM_REGISTRY_VALUES = (
    "DataFolder",
    "InstallLocation",
    "InstallPath",
    "Path",
    "",
)
EDHM_PROFILE_KEYS = (
    ("x150", "y150", "z150"),
    ("x151", "y151", "z151"),
    ("x152", "y152", "z152"),
)
EDHM_IDENTITY_MATRIX: list[list[float]] = [
    [1.0, 0.0, 0.0],
    [0.0, 1.0, 0.0],
    [0.0, 0.0, 1.0],
]


class EDHM:
    def __init__(self, install_path: Path | None = None):
        self.install_path = install_path

    @classmethod
    def from_system(cls) -> "EDHM":
        return cls(cls._get_registry_install_path())

    @property
    def is_installed(self) -> bool:
        return self.theme_settings_path is not None

    @property
    def theme_settings_path(self) -> Path | None:
        for candidate in self._candidate_ini_dirs():
            path = candidate / "ThemeSettings.json"
            if path.exists():
                return path
        return None

    def load_xml_profile(self) -> list[dict] | None:
        path = self.theme_settings_path
        if path is None:
            return None

        try:
            theme = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            log("warning", "Failed to read EDHM ThemeSettings.json", path, e)
            return None

        profile = theme.get("xml_profile")
        if not isinstance(profile, list):
            return None
        return profile

    def load_color_matrix(self) -> list[list[float]] | None:
        profile = self.load_xml_profile()
        if profile is None:
            return None

        values = {
            item.get("key"): item.get("value")
            for item in profile
            if isinstance(item, dict)
        }

        matrix: list[list[float]] = []
        for row_keys in EDHM_PROFILE_KEYS:
            row: list[float] = []
            for key in row_keys:
                value = values.get(key)
                if not isinstance(value, (int, float)):
                    log("warning", "Invalid EDHM xml_profile value", key, value)
                    return None
                row.append(float(value))
            matrix.append(row)

        if self._is_identity_matrix(matrix):
            return None

        log("debug", "Loaded HUD color matrix from EDHM xml_profile", matrix)
        return matrix

    def _candidate_ini_dirs(self) -> list[Path]:
        candidates: list[Path] = []
        if self.install_path:
            candidates.extend(
                (
                    self.install_path,
                    self.install_path / "ODYSS" / "EDHM" / "EDHM-Ini",
                    self.install_path / "EDHM" / "EDHM-Ini",
                    self.install_path / "EDHM-Ini",
                )
            )
        candidates.append(EDHM_DEFAULT_INI_DIR)
        return candidates

    @staticmethod
    def _get_registry_install_path() -> Path | None:
        try:
            import winreg

            for registry_key in EDHM_REGISTRY_KEYS:
                try:
                    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry_key)
                except FileNotFoundError:
                    continue

                try:
                    for registry_value in EDHM_REGISTRY_VALUES:
                        try:
                            value, _ = winreg.QueryValueEx(key, registry_value)
                        except FileNotFoundError:
                            continue
                        if value:
                            return Path(value)
                finally:
                    winreg.CloseKey(key)
        except Exception:
            return None

        return None

    @staticmethod
    def _is_identity_matrix(matrix: list[list[float]]) -> bool:
        return all(
            abs(value - EDHM_IDENTITY_MATRIX[row_index][column_index]) < 0.000001
            for row_index, row in enumerate(matrix)
            for column_index, value in enumerate(row)
        )
