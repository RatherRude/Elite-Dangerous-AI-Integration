import json
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from time import sleep
from typing import Any, Callable, Literal

import requests
from pyautogui import typewrite

from ..Logger import log
from ..Projections import ProjectedStates, get_state_dict
from ..Screenshot import set_game_window_active
from ..HudColorMatrix import HudColorMatrix


SPANSH_SYSTEMS_URL = "https://spansh.co.uk/api/systems/search"
SPANSH_STATIONS_URL = "https://spansh.co.uk/api/stations/search"
SPANSH_BODIES_URL = "https://spansh.co.uk/api/bodies/search"
PLOT_TARGET_SEARCH_SIZE = 10

STATION_TYPE_SYSTEM_MAP_CATEGORY = {
    "Asteroid base": "ORBITAL PORTS",
    "Coriolis Starport": "ORBITAL PORTS",
    "Dockable Planet Station": "PLANETARY PORTS",
    "Dodec Starport": "ORBITAL PORTS",
    "Drake-Class Carrier": "FLEET CARRIERS",
    "Mega ship": "INSTALLATIONS",
    "Ocellus Starport": "ORBITAL PORTS",
    "Orbis Starport": "ORBITAL PORTS",
    "Outpost": "ORBITAL PORTS",
    "Planetary Construction Depot": "PLANETARY PORTS",
    "Planetary Outpost": "PLANETARY PORTS",
    "Planetary Port": "PLANETARY PORTS",
    "Settlement": "ODYSSEY SETTLEMENTS",
    "Space Construction Depot": "ORBITAL PORTS",
    "Surface Settlement": "SURFACE SETTLEMENTS",
}


@dataclass(frozen=True)
class ResolvedPlotTarget:
    target_type: Literal["system", "station", "body"]
    name: str
    system_name: str
    system_map_category: str | None
    distance: float | None
    match_score: float
    details: dict[str, Any]
    is_landable: bool | None = None


class Plotter:
    def __init__(
        self,
        *,
        keys: Any = None,
        event_manager: Any = None,
        screen_reader_hud_color_matrix: HudColorMatrix | None = None,
        prepare_system_request: Callable[[dict[str, Any], Any], dict[str, Any]] | None = None,
        prepare_station_request: Callable[[dict[str, Any], Any], dict[str, Any]] | None = None,
        prepare_body_request: Callable[[dict[str, Any], Any], dict[str, Any]] | None = None,
        spansh_post: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
        enable_in_system_navigation: bool = False,
    ) -> None:
        self.keys = keys
        self.event_manager = event_manager
        self.screen_reader_hud_color_matrix = screen_reader_hud_color_matrix
        self.prepare_system_request = prepare_system_request
        self.prepare_station_request = prepare_station_request
        self.prepare_body_request = prepare_body_request
        self.spansh_post = spansh_post or self._spansh_post
        self.enable_in_system_navigation = enable_in_system_navigation

    @staticmethod
    def normalize_plot_name(name: str) -> str:
        return "".join(str(name).upper().split())

    @classmethod
    def is_plot_name_exact_match(cls, query: str, candidate: str) -> bool:
        query_normalized = cls.normalize_plot_name(query)
        candidate_normalized = cls.normalize_plot_name(candidate)
        return bool(query_normalized and query_normalized == candidate_normalized)

    @classmethod
    def plot_name_match_score(cls, query: str, candidate: str) -> float:
        query_normalized = cls.normalize_plot_name(query)
        candidate_normalized = cls.normalize_plot_name(candidate)
        if not query_normalized or not candidate_normalized:
            return 0.0
        if query_normalized == candidate_normalized:
            return 1.0
        if candidate_normalized.startswith(query_normalized) or query_normalized.startswith(candidate_normalized):
            return 0.9

        max_distance = max(1, len(query_normalized) // 3)
        distance = cls._levenshtein_distance(query_normalized, candidate_normalized)
        if distance > max_distance:
            return 0.0

        max_len = max(len(query_normalized), len(candidate_normalized), 1)
        return 0.8 * (1 - distance / max_len)

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

    @staticmethod
    def system_map_category_for_station(station: dict[str, Any]) -> str | None:
        station_type = str(station.get("type") or "").strip()
        if station_type in STATION_TYPE_SYSTEM_MAP_CATEGORY:
            return STATION_TYPE_SYSTEM_MAP_CATEGORY[station_type]
        for known_type, category in STATION_TYPE_SYSTEM_MAP_CATEGORY.items():
            if known_type.casefold() == station_type.casefold():
                return category
        return None

    @staticmethod
    def ensure_in_system_plot_target(resolved: ResolvedPlotTarget) -> None:
        if resolved.target_type == "station":
            if not resolved.system_map_category:
                station_type = resolved.details.get("station_type", "unknown")
                raise Exception(
                    f"Station {resolved.name!r} has unknown type {station_type!r} and cannot be selected in the system map."
                )
            return

        if resolved.target_type != "body":
            return

        if resolved.is_landable is False:
            raise Exception(
                f"Body {resolved.name!r} is not landable and cannot be selected from the landfall planets list."
            )

    @staticmethod
    def _spansh_post(url: str, request_body: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(url, json=request_body, timeout=15)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _plot_target_details(
        target_type: Literal["system", "station", "body"],
        name: str,
        system_name: str,
        distance: float | None,
        *,
        station_type: str | None = None,
        is_landable: bool | None = None,
    ) -> dict[str, Any]:
        details = {
            "query_type": target_type,
            "name": name,
            "system_name": system_name,
            "distance": distance,
        }
        if station_type is not None:
            details["station_type"] = station_type
        if is_landable is not None:
            details["is_landable"] = is_landable
        return details

    @staticmethod
    def spansh_plot_search_name(query: str) -> str:
        query = str(query).strip()
        if not query:
            return query
        return query[:-1] + "?"

    @classmethod
    def _plot_search_obj(cls, query: str) -> dict[str, Any]:
        return {"name": cls.spansh_plot_search_name(query), "size": 1}

    def _apply_plot_request_routing(self, request_body: dict[str, Any], projected_states: Any) -> dict[str, Any]:
        location = get_state_dict(projected_states, 'Location')
        star_pos = location.get('StarPos')

        request_body["sort"] = [{"distance": {"direction": "asc"}}]
        request_body["size"] = 1
        request_body.pop("reference_route", None)
        filters = request_body.get("filters", {})
        filters.pop("type", None)
        filters.pop("has_large_pad", None)

        if isinstance(star_pos, list) and len(star_pos) >= 3:
            request_body.pop("reference_system", None)
            request_body["reference_coords"] = {
                "x": star_pos[0],
                "y": star_pos[1],
                "z": star_pos[2],
            }
        else:
            request_body.pop("reference_coords", None)
            request_body["reference_system"] = location.get('StarSystem', 'Sol')

        return request_body

    @classmethod
    def _plot_candidate_score(cls, query: str, candidate_name: str) -> float:
        if cls.is_plot_name_exact_match(query, candidate_name):
            return 1.0
        return cls.plot_name_match_score(query, candidate_name)

    def _plot_candidates_from_systems(self, query: str, projected_states: Any) -> list[ResolvedPlotTarget]:
        if self.prepare_system_request is None:
            raise Exception("prepare_system_request is required")
        request_body = self.prepare_system_request(self._plot_search_obj(query), projected_states)
        self._apply_plot_request_routing(request_body, projected_states)
        data = self.spansh_post(SPANSH_SYSTEMS_URL, request_body)
        candidates: list[ResolvedPlotTarget] = []

        for system in data.get("results", [])[:PLOT_TARGET_SEARCH_SIZE]:
            name = str(system.get("name") or "").strip()
            if not name:
                continue
            distance = system.get("distance")
            distance_value = float(distance) if distance is not None else None
            candidates.append(ResolvedPlotTarget(
                target_type="system",
                name=name,
                system_name=name,
                system_map_category=None,
                distance=distance_value,
                match_score=self._plot_candidate_score(query, name),
                details=self._plot_target_details("system", name, name, distance_value),
            ))

        return candidates

    def _plot_candidates_from_stations(self, query: str, projected_states: Any) -> list[ResolvedPlotTarget]:
        if self.prepare_station_request is None:
            raise Exception("prepare_station_request is required")
        request_body = self.prepare_station_request(self._plot_search_obj(query), projected_states)
        self._apply_plot_request_routing(request_body, projected_states)
        log('info', 'station requestion', request_body)
        data = self.spansh_post(SPANSH_STATIONS_URL, request_body)
        candidates: list[ResolvedPlotTarget] = []

        for station in data.get("results", [])[:PLOT_TARGET_SEARCH_SIZE]:
            name = str(station.get("name") or "").strip()
            system_name = str(station.get("system_name") or "").strip()
            station_type = str(station.get("type") or "").strip()
            if not name or not system_name:
                continue
            distance = station.get("distance")
            distance_value = float(distance) if distance is not None else None
            if name != query:
                continue
            candidates.append(ResolvedPlotTarget(
                target_type="station",
                name=name,
                system_name=system_name,
                system_map_category=self.system_map_category_for_station(station),
                distance=distance_value,
                match_score=self._plot_candidate_score(query, name),
                details=self._plot_target_details(
                    "station",
                    name,
                    system_name,
                    distance_value,
                    station_type=station_type or None,
                ),
            ))

        return candidates

    def _plot_candidates_from_bodies(self, query: str, projected_states: Any) -> list[ResolvedPlotTarget]:
        if self.prepare_body_request is None:
            raise Exception("prepare_body_request is required")
        request_body = self.prepare_body_request(self._plot_search_obj(query), projected_states)
        self._apply_plot_request_routing(request_body, projected_states)
        data = self.spansh_post(SPANSH_BODIES_URL, request_body)
        candidates: list[ResolvedPlotTarget] = []

        for body in data.get("results", [])[:PLOT_TARGET_SEARCH_SIZE]:
            if body.get("type") != "Planet":
                continue
            name = str(body.get("name") or "").strip()
            system_name = str(body.get("system_name") or "").strip()
            if not name or not system_name:
                continue
            distance = body.get("distance")
            distance_value = float(distance) if distance is not None else None
            is_landable = body.get("is_landable")
            landable_value = is_landable if isinstance(is_landable, bool) else None
            candidates.append(ResolvedPlotTarget(
                target_type="body",
                name=name,
                system_name=system_name,
                system_map_category="LANDFALL PLANETS",
                distance=distance_value,
                match_score=self._plot_candidate_score(query, name),
                details=self._plot_target_details(
                    "body",
                    name,
                    system_name,
                    distance_value,
                    is_landable=landable_value,
                ),
                is_landable=landable_value,
            ))

        return candidates

    @classmethod
    def _select_best_plot_target(cls, candidates: list[ResolvedPlotTarget], query: str) -> ResolvedPlotTarget | None:
        if not candidates:
            return None

        exact_matches = [candidate for candidate in candidates if cls.is_plot_name_exact_match(query, candidate.name)]
        if exact_matches:
            return min(
                exact_matches,
                key=lambda candidate: candidate.distance if candidate.distance is not None else float("inf"),
            )

        def sort_key(candidate: ResolvedPlotTarget) -> tuple[float, float]:
            distance = candidate.distance if candidate.distance is not None else float("inf")
            return (-candidate.match_score, distance)

        return sorted(candidates, key=sort_key)[0]

    @staticmethod
    def plot_search_query(
        *,
        system: str | None = None,
        station: str | None = None,
        body: str | None = None,
    ) -> str | None:
        for value in (station, body, system):
            if value and str(value).strip():
                return str(value).strip()
        return None

    def lookup_plot_target(
        self,
        *,
        system: str | None = None,
        station: str | None = None,
        body: str | None = None,
        projected_states: Any,
    ) -> ResolvedPlotTarget | None:
        query = self.plot_search_query(system=system, station=station, body=body)
        if not query:
            return None
        return self.resolve_plot_target(query, projected_states)

    def resolve_plot_target(self, query: str, projected_states: Any) -> ResolvedPlotTarget | None:
        query = str(query or "").strip()
        if not query:
            return None

        search_jobs = {
            "system": self._plot_candidates_from_systems,
            "station": self._plot_candidates_from_stations,
            "body": self._plot_candidates_from_bodies,
        }
        candidates: list[ResolvedPlotTarget] = []

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(search_fn, query, projected_states): target_type
                for target_type, search_fn in search_jobs.items()
            }
            for future in as_completed(futures):
                target_type = futures[future]
                try:
                    candidates.extend(future.result())
                except Exception as error:
                    log("warn", "Plot target lookup failed", f"{target_type}: {error}")

        best_match = self._select_best_plot_target(candidates, query)
        if best_match:
            log(
                "info",
                "Resolved plot target",
                f"{query!r} -> {best_match.target_type} {best_match.name!r} in {best_match.system_name!r}",
            )
        else:
            log("warn", "Could not resolve plot target", query)
        return best_match

    def plot_to_target(self, args: dict[str, Any], projected_states: ProjectedStates, galaxymap_key: str = "GalaxyMapOpen") -> str:
        set_game_window_active()
        system, station, body = self._parse_plot_target_args(args)
        if not any((system, station, body)):
            raise Exception("At least one of system, station, or body must be provided.")

        resolved = self.lookup_plot_target(
            system=system,
            station=station,
            body=body,
            projected_states=projected_states,
        )
        current_system = get_state_dict(projected_states, 'Location').get('StarSystem', 'Unknown')

        if resolved:
            nav_route = get_state_dict(projected_states, 'NavInfo').get('NavRoute', [])
            if nav_route and self._systems_match(nav_route[-1].get('StarSystem', ''), resolved.system_name):
                if resolved.target_type == 'system' or not self._systems_match(resolved.system_name, current_system):
                    return f"The route to {resolved.system_name} is already set"

            if resolved.target_type == 'system' and self._systems_match(resolved.system_name, current_system):
                return f"Already in {resolved.system_name}."

            if resolved.target_type in ('station', 'body') and self._systems_match(resolved.system_name, current_system):
                if not self.enable_in_system_navigation:
                    return (
                        f"Best location found: {json.dumps(resolved.details)}. "
                        f"{resolved.name} is in the current system already."
                    )
                return self._plot_in_system(resolved, projected_states)

            return self._plot_galaxy_route(
                resolved.system_name,
                resolved.details,
                projected_states,
                galaxymap_key,
                resolved_target=resolved,
            )

        if system:
            nav_route = get_state_dict(projected_states, 'NavInfo').get('NavRoute', [])
            if nav_route and self._systems_match(nav_route[-1].get('StarSystem', ''), system):
                return f"The route to {system} is already set"
            if self._systems_match(system, current_system):
                return f"Already in {system}."
            return self._plot_galaxy_route(system, None, projected_states, galaxymap_key)

        raise Exception(
            f"Could not resolve plot target from station={station!r}, body={body!r}, system={system!r}."
        )

    @staticmethod
    def _parse_plot_target_args(args: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
        def clean(value: Any) -> str | None:
            if value is None:
                return None
            text = str(value).strip()
            return text or None

        return clean(args.get('system')), clean(args.get('station')), clean(args.get('body'))

    @staticmethod
    def _systems_match(system_a: str, system_b: str) -> bool:
        return system_a.strip().casefold() == system_b.strip().casefold()

    def _navigate_system_map_target(self, resolved_target: ResolvedPlotTarget) -> None:
        from ..ScreenReader import ScreenReader
        from ..SystemMap import SystemMap

        self._require_ui_dependencies()
        self.ensure_in_system_plot_target(resolved_target)
        category = resolved_target.system_map_category or "LANDFALL PLANETS"
        SystemMap(ScreenReader(hud_color_matrix=self.screen_reader_hud_color_matrix), self.keys).run(
            category=category,
            entry=resolved_target.name,
        )

    def _select_orrery_from_galaxy_map(self, screen_reader: Any, max_steps: int = 30) -> None:
        self._require_ui_dependencies()
        self.keys.send('UI_Right')
        sleep(0.1)
        self.keys.send('UI_Right')
        sleep(0.1)

        selection = screen_reader.read_selected_area()
        detection = selection.detection
        if detection is not None and detection.icon_template != 'info':
            raise Exception(f"Unexpected ScreenReader Result: {str(selection)}")

        for _ in range(8):
            self.keys.send('UI_Down')
            sleep(0.1)

        for _ in range(10):
            selection = screen_reader.read_selected_area()
            detection = selection.detection
            if detection is not None and detection.icon_template == 'orrery':
                self.keys.send('UI_Select')
                sleep(0.1)
                return
            if detection is not None and detection.icon_template == 'target':
                self.keys.send('UI_Up')
                sleep(0.1)
                self.keys.send('UI_Up')
                sleep(0.1)
                self.keys.send('UI_Select')
                sleep(0.1)
                return
            self.keys.send('UI_Down')
            sleep(0.1)

        raise Exception("Could not find orrery icon in galaxy map system list")

    def _plot_in_system_from_galaxy_map(self, resolved_target: ResolvedPlotTarget, projected_states: ProjectedStates) -> None:
        from ..ScreenReader import ScreenReader

        self._require_ui_dependencies()
        screen_reader = ScreenReader(hud_color_matrix=self.screen_reader_hud_color_matrix)
        self._select_orrery_from_galaxy_map(screen_reader)

        try:
            self.event_manager.wait_for_condition('CurrentStatus', lambda s: s.GuiFocus == "SystemMap", 4)
        except TimeoutError:
            raise Exception("Failed to open system map from galaxy map orrery view")

        sleep(3)
        self._navigate_system_map_target(resolved_target)

    def _plot_in_system(
        self,
        resolved_target: ResolvedPlotTarget,
        projected_states: ProjectedStates,
        sys_map_key: str = "SystemMapOpen",
    ) -> str:
        current_gui = self._ensure_system_map_open(projected_states, sys_map_key)
        if current_gui != "SystemMap":
            sleep(3)

        self._navigate_system_map_target(resolved_target)

        if current_gui != "SystemMap":
            self.keys.send(sys_map_key)

        return (
            f"Best location found: {json.dumps(resolved_target.details)}. "
            f"In-system navigation to {resolved_target.name} completed."
        )

    def _ensure_system_map_open(self, projected_states: ProjectedStates, sys_map_key: str = "SystemMapOpen") -> str:
        self._require_ui_dependencies()
        current_gui = get_state_dict(projected_states, 'CurrentStatus').get('GuiFocus', '')

        if current_gui in ['SAA', 'FSS', 'Codex']:
            raise Exception('System map can not be opened currently, the active GUI needs to be closed first')

        if current_gui == 'SystemMap':
            return current_gui

        self.keys.send(sys_map_key)
        try:
            self.event_manager.wait_for_condition('CurrentStatus', lambda s: s.GuiFocus == "SystemMap", 4)
        except TimeoutError:
            self.keys.send("UI_Back", repeat=10, repeat_delay=0.05)
            self.keys.send(sys_map_key)
            try:
                self.event_manager.wait_for_condition('CurrentStatus', lambda s: s.GuiFocus == "SystemMap", 4)
            except TimeoutError:
                raise Exception("System map can not be opened currently, the current GUI needs to be closed first")

        return current_gui

    def _ensure_galaxy_map_open(self, projected_states: ProjectedStates, galaxymap_key: str) -> str:
        self._require_ui_dependencies()
        current_gui = get_state_dict(projected_states, 'CurrentStatus').get('GuiFocus', '')

        if current_gui in ['SAA', 'FSS', 'Codex']:
            raise Exception('Galaxy map can not be opened currently, the active GUI needs to be closed first')

        if current_gui == 'GalaxyMap':
            return current_gui

        self.keys.send(galaxymap_key)
        try:
            self.event_manager.wait_for_condition('CurrentStatus', lambda s: s.GuiFocus == "GalaxyMap", 4)
        except TimeoutError:
            self.keys.send("UI_Back", repeat=10, repeat_delay=0.05)
            self.keys.send(galaxymap_key)
            try:
                self.event_manager.wait_for_condition('CurrentStatus', lambda s: s.GuiFocus == "GalaxyMap", 5)
            except TimeoutError:
                raise Exception("Galaxy map can not be opened currently, the current GUI needs to be closed first")

        return current_gui

    def _plot_galaxy_route(
        self,
        system_name: str,
        details: dict[str, Any] | None,
        projected_states: ProjectedStates,
        galaxymap_key: str = "GalaxyMapOpen",
        resolved_target: ResolvedPlotTarget | None = None,
    ) -> str:
        self._require_ui_dependencies()
        current_gui = self._ensure_galaxy_map_open(projected_states, galaxymap_key)
        keep_galaxy_map_open = (
            self.enable_in_system_navigation
            and resolved_target is not None
            and resolved_target.target_type in ('station', 'body')
        )

        collisions = self.keys.get_collisions('UI_Up')
        if 'CamTranslateForward' in collisions:
            raise Exception(
                "Unable to enter system name due to a collision between the 'UI Panel Up' and 'Galaxy Cam Translate Forward' keys. "
                + "Please change the keybinding for 'Galaxy Cam Translate' to Shift + WASD under General Controls > Galaxy Map."
            )

        collisions = self.keys.get_collisions('UI_Right')
        if 'CamTranslateRight' in collisions:
            raise Exception(
                "Unable to enter system name due to a collision between the 'UI Panel Right' and 'Galaxy Cam Translate Right' keys. "
                + "Please change the keybinding for 'Galaxy Cam Translate' to Shift + WASD under General Controls > Galaxy Map."
            )

        self.keys.send('CamZoomIn')
        sleep(0.05)

        self.keys.send('UI_Up')
        sleep(.05)
        if current_gui == "GalaxyMap":
            self.keys.send('UI_Left', repeat=3)
            sleep(.05)
            self.keys.send('UI_Right')
            sleep(.05)
            self.keys.send('UI_Up')
            sleep(.05)
        self.keys.send('UI_Select')
        sleep(.05)

        typewrite(system_name, interval=0.02)
        sleep(0.05)

        self.keys.send_key('Down', 'Key_Enter')
        sleep(0.05)
        self.keys.send_key('Up', 'Key_Enter')

        sleep(0.05)
        self.keys.send('UI_Right')
        sleep(.5)
        self.keys.send('UI_Select')

        current_system = get_state_dict(projected_states, 'Location').get('StarSystem', 'Unknown')
        distance_ly, zoom_wait_time = self.calculate_navigation_distance_and_timing(current_system, system_name)
        log('info', 'zoom_wait_time', zoom_wait_time)

        sleep(0.05)
        self.keys.send('CamZoomOut')
        sleep(zoom_wait_time)
        self.keys.send('UI_Select', hold=1)
        sleep(0.05)

        try:
            data = self.event_manager.wait_for_condition(
                'NavInfo',
                lambda s: s.NavRoute and len(s.NavRoute) > 0 and s.NavRoute[-1].StarSystem.lower() == system_name.lower(),
                zoom_wait_time,
            )
            jump_amount = len(data.NavRoute) if data else 0

            if not keep_galaxy_map_open and current_gui != "GalaxyMap":
                self.keys.send(galaxymap_key)

            prefix = f"Best location found: {json.dumps(details)}. " if details else ""
            distance_text = f"Distance: {distance_ly} LY, " if distance_ly > 0 else ""
            message = prefix + f"Route to {system_name} successfully plotted ({distance_text}Jumps: {jump_amount})"

            if keep_galaxy_map_open and resolved_target is not None:
                self._plot_in_system_from_galaxy_map(resolved_target, projected_states)
                message += f" In-system navigation to {resolved_target.name} configured."

            return message
        except TimeoutError:
            return f"Failed to plot a route to {system_name}"

    @staticmethod
    def calculate_navigation_distance_and_timing(current_system: str, target_system: str) -> tuple[float, int]:
        distance_ly = 0.0

        if current_system != 'Unknown' and target_system:
            try:
                edsm_url = "https://www.edsm.net/api-v1/systems"
                params = {
                    'systemName[]': [current_system, target_system],
                    'showCoordinates': 1,
                }

                log('debug', 'Distance Calculation', f"Requesting coordinates for {current_system} -> {target_system}")
                response = requests.get(edsm_url, params=params, timeout=5)

                if response.status_code == 200:
                    systems_data = response.json()

                    if len(systems_data) >= 2:
                        current_coords = None
                        target_coords = None

                        for system in systems_data:
                            if system.get('name', '').lower() == current_system.lower():
                                current_coords = system.get('coords')
                            elif system.get('name', '').lower() == target_system.lower():
                                target_coords = system.get('coords')

                        if current_coords and target_coords:
                            x1, y1, z1 = current_coords['x'], current_coords['y'], current_coords['z']
                            x2, y2, z2 = target_coords['x'], target_coords['y'], target_coords['z']

                            distance_ly = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2 + (z2 - z1) ** 2)
                            distance_ly = round(distance_ly, 2)

                            if distance_ly > 20000:
                                raise Exception(f"Distance of {distance_ly} LY from {current_system} to {target_system} is too far to plot (max 20000 LY)")
                        else:
                            log('warn', 'Distance Calculation', f"Could not find coordinates for one or both systems: {current_system}, {target_system}")
                    else:
                        log('warn', 'Distance Calculation', f"EDSM API returned insufficient data for systems: {current_system}, {target_system}")
                else:
                    log('warn', 'Distance Calculation', f"EDSM API request failed with status {response.status_code}")

            except requests.RequestException as e:
                log('error', 'Distance Calculation', f"Failed to request system coordinates from EDSM API: {str(e)}")
            except Exception as e:
                if "too far to plot" in str(e):
                    raise
                log('error', 'Distance Calculation', f"Unexpected error during distance calculation: {str(e)}")

        zoom_wait_time = 3

        if distance_ly > 0:
            additional_time = int(distance_ly / 1000)
            zoom_wait_time += additional_time

        if distance_ly == 0:
            zoom_wait_time += 2
            log('warn', 'Navigation Timing', "Distance could not be determined, adding 2 extra seconds to wait time")

        return distance_ly, zoom_wait_time

    def _require_ui_dependencies(self) -> None:
        if self.keys is None or self.event_manager is None:
            raise Exception("Plotter UI dependencies are not configured")
