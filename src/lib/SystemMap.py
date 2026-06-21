from __future__ import annotations
import sys
import traceback
import time
from typing import final

from .EDKeys import EDKeys
from .Logger import log
from .ScreenReader import ScreenReader, ScreenReadResult
from .Config import get_ed_appdata_path, load_config, load_hud_color_matrix


@final
class SystemMap:
    def __init__(self, screen_reader: ScreenReader, ed_keys: EDKeys):
        self.screen_reader = screen_reader
        self.ed_keys = ed_keys
        self.categories = ["ORBITAL PORTS", "INSTALLATIONS", "LANDFALL PLANETS", "PLANETARY PORTS", "SURFACE SETTLEMENTS", "ODYSSEY SETTLEMENTS", "FLEET CARRIERS"]
        self.wait_time = 0.5

    @staticmethod
    def _normalize_search_text(value: str) -> str:
        return "".join(value.upper().split())

    @staticmethod
    def _levenshtein_distance(a: str, b: str) -> int:
        if len(a) < len(b):
            a, b = b, a
        previous = list(range(len(b) + 1))
        for i, char_a in enumerate(a, start=1):
            current = [i]
            for j, char_b in enumerate(b, start=1):
                insertions = previous[j] + 1
                deletions = current[j - 1] + 1
                substitutions = previous[j - 1] + (char_a != char_b)
                current.append(min(insertions, deletions, substitutions))
            previous = current
        return previous[-1]

    @classmethod
    def selection_matches_entry(cls, selection: ScreenReadResult, entry: str) -> bool:
        if len(selection.ocr_lines) < 2:
            return False

        target = cls._normalize_search_text(entry)
        candidate = cls._normalize_search_text(selection.ocr_lines[1].text)
        if not target or not candidate:
            return False
        if target in candidate:
            return True

        max_distance = max(1, len(target) // 8)
        return cls._levenshtein_distance(target, candidate) <= max_distance

    def run(self, category: str = "LANDFALL PLANETS", entry: str = "HIP 58412 8 D") -> ScreenReadResult:
        log("debug", "Navigating system map", category, entry)
        self.ed_keys.send("UI_Down")
        time.sleep(self.wait_time)
        back = self.screen_reader.read_selected_area()
        if not back.detection or not back.detection.icon_template == 'exit':
            raise Exception(f"Unexpected ScreenReader Result: {str(back)}")

        self.ed_keys.send("UI_Up")
        time.sleep(self.wait_time)
        self.ed_keys.send("UI_Up")
        time.sleep(self.wait_time)
        self.ed_keys.send("UI_Select")
        time.sleep(self.wait_time)
        self.ed_keys.send("UI_Right")
        time.sleep(self.wait_time)
        for cat in self.categories:
            if category == cat:
                break
            self.ed_keys.send("UI_Down")
            time.sleep(self.wait_time)

        self.ed_keys.send("UI_Select")
        time.sleep(self.wait_time)
        match = None
        while not match:
            selection = self.screen_reader.read_selected_area()
            log("info", selection)
            if not selection.detection or selection.detection.icon_template == 'exit':
                raise Exception(f"Unexpected ScreenReader Result Exit: {str(selection)}")
            if self.selection_matches_entry(selection, entry):
                match = selection
            if not match:
                self.ed_keys.send("UI_Down")
                time.sleep(self.wait_time)
        log("info", "System map target matched", match)
        time.sleep(self.wait_time)
        self.ed_keys.send("UI_Select", hold=2)

        return match

if __name__ == "__main__":
    try:
        config = load_config()
        hud_color_matrix = load_hud_color_matrix(config)
        screen_reader = ScreenReader(hud_color_matrix=hud_color_matrix)
        ed_keys = EDKeys(
            get_ed_appdata_path(config),
            prefer_primary_bindings=config.get("prefer_primary_bindings", False),
        )

        ed_keys.send("SystemMapOpen")
        time.sleep(3)
        system_map = SystemMap(screen_reader, ed_keys)
        res = system_map.run()
        log("info", res)
    except Exception as e:
        log("error", e, traceback.format_exc())
        sys.exit(1)
