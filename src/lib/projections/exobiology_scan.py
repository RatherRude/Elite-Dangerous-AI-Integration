import json
import math
from typing import Optional, cast

from typing_extensions import override
from pydantic import BaseModel, Field

from ..Config import get_asset_path
from ..Event import Event, GameEvent, ProjectedEvent, StatusEvent
from ..EventManager import Projection


class ExobiologyScanStateScan(BaseModel):
    """Location of an exobiology scan sample."""
    lat: float = Field(description="Latitude of the scan location")
    long: float = Field(description="Longitude of the scan location")


class ExobiologyScanStateModel(BaseModel):
    """Current exobiology scanning state."""
    within_scan_radius: Optional[bool] = Field(default=True, description="Whether commander is within minimum sample distance")
    scan_radius: Optional[int] = Field(default=None, description="Required distance between samples in meters")
    scans: list[ExobiologyScanStateScan] = Field(default_factory=list, description="Locations of completed scans")
    lat: Optional[float] = Field(default=None, description="Commander's current latitude")
    long: Optional[float] = Field(default=None, description="Commander's current longitude")
    life_form: Optional[str] = Field(default=None, description="Currently scanned life form species")


class ExobiologyScan(Projection[ExobiologyScanStateModel]):
    StateModel = ExobiologyScanStateModel
    with open(get_asset_path("exobiology_colony_sizes.json"), encoding="utf-8") as handle:
        colony_size = json.load(handle)

    def haversine_distance(self, new_value: ExobiologyScanStateScan, old_value: ExobiologyScanStateScan, radius: int):
        lat1, lon1 = math.radians(new_value.lat), math.radians(new_value.long)
        lat2, lon2 = math.radians(old_value.lat), math.radians(old_value.long)

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        # Haversine formula
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        distance = radius * c
        return distance

    @override
    def process(self, event: Event) -> list[ProjectedEvent]:
        projected_events: list[ProjectedEvent] = []

        if isinstance(event, StatusEvent) and event.status.get("event") == "Status":
            latitude = event.status.get("Latitude", 0.0)
            longitude = event.status.get("Longitude", 0.0)
            self.state.lat = latitude if isinstance(latitude, float) else 0.0
            self.state.long = longitude if isinstance(longitude, float) else 0.0

            if self.state.scans and self.state.scan_radius:
                in_scan_radius = False
                if (
                    self.state.lat != 0
                    and self.state.long != 0
                    and event.status.get("PlanetRadius", False)
                ):
                    planet_radius = event.status.get("PlanetRadius", 0.0)
                    if not isinstance(planet_radius, (int, float)):
                        planet_radius = 0.0
                    distance_obj = ExobiologyScanStateScan(lat=self.state.lat, long=self.state.long)
                    scan_radius = self.state.scan_radius
                    if scan_radius is None:
                        scan_radius = 0
                    for scan in self.state.scans:
                        distance = self.haversine_distance(scan, distance_obj, int(planet_radius))
                        if distance < scan_radius:
                            in_scan_radius = True
                            break
                    if in_scan_radius:
                        if not self.state.within_scan_radius:
                            projected_events.append(ProjectedEvent(content={"event": "ScanOrganicTooClose"}))
                            self.state.within_scan_radius = in_scan_radius
                    else:
                        if self.state.within_scan_radius:
                            projected_events.append(ProjectedEvent(content={"event": "ScanOrganicFarEnough"}))
                            self.state.within_scan_radius = in_scan_radius
                else:
                    if self.state.scans:
                        self.state.scans.clear()
                        self.state.scan_radius = None

        if isinstance(event, GameEvent) and event.content.get("event") == "ScanOrganic":
            scan_content = cast(dict[str, object], event.content)
            scan_type = scan_content.get("ScanType")
            if scan_type == "Log":
                self.state.scans.clear()
                self.state.scans.append(ExobiologyScanStateScan(lat=self.state.lat or 0, long=self.state.long or 0))
                genus = scan_content.get("Genus")
                if isinstance(genus, str):
                    colony_radius = self.colony_size.get(genus[11:-1])
                    if isinstance(colony_radius, int):
                        self.state.scan_radius = colony_radius
                species = event.content.get("Species_Localised", event.content.get("Species", "unknown species"))
                if not isinstance(species, str):
                    species = "unknown species"
                variant = event.content.get("Variant_Localised", event.content.get("Variant", ""))
                if not isinstance(variant, str):
                    variant = ""
                if variant and variant != species:
                    life_form = f"{variant} ({species})"
                else:
                    life_form = f"{species}"
                self.state.life_form = life_form
                self.state.within_scan_radius = True
                projected_events.append(ProjectedEvent(content={**scan_content, "event": "ScanOrganicFirst", "NewSampleDistance": self.state.scan_radius}))

            elif scan_type == "Sample":
                if len(self.state.scans) == 1:
                    self.state.scans.append(ExobiologyScanStateScan(lat=self.state.lat or 0, long=self.state.long or 0))
                    self.state.within_scan_radius = True
                    projected_events.append(ProjectedEvent(content={**scan_content, "event": "ScanOrganicSecond"}))
                elif len(self.state.scans) == 2:
                    projected_events.append(ProjectedEvent(content={**scan_content, "event": "ScanOrganicThird"}))
                    if self.state.scans:
                        self.state.scans.clear()
                        self.state.scan_radius = None
                else:
                    projected_events.append(ProjectedEvent(content={**scan_content, "event": "ScanOrganic"}))

            elif scan_type == "Analyse":
                pass

        if isinstance(event, GameEvent) and event.content.get("event") in ["SupercruiseEntry", "FSDJump", "Died", "Shutdown", "JoinACrew"]:
            self.state.scans.clear()
            self.state.scan_radius = None

        return projected_events
