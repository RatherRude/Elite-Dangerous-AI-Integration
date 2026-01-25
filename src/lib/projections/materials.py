import json
from typing import Any, Literal, Optional

from typing_extensions import override
from pydantic import BaseModel, Field

from ..Config import get_asset_path
from ..Event import Event, GameEvent
from ..EventManager import Projection


MaterialsCategory = Literal["Raw", "Manufactured", "Encoded"]


class MaterialEntry(BaseModel):
    """A material in the commander's inventory."""
    Name: str = Field(description="Material internal name")
    Count: int = Field(default=0, description="Quantity of this material")
    Name_Localised: Optional[str] = Field(default=None, description="Human-readable material name")


with open(get_asset_path("materials.json"), encoding="utf-8") as handle:
    MATERIAL_TEMPLATE = json.load(handle)

MATERIAL_NAME_LOOKUP: dict[str, MaterialsCategory] = {
    entry["Name"].lower(): category
    for category, items in MATERIAL_TEMPLATE.items()
    for entry in items
}


class MaterialsStateModel(BaseModel):
    """Commander's materials inventory for engineering and synthesis."""
    Raw: list[MaterialEntry] = Field(default_factory=list, description="Raw materials from mining and surface prospecting")
    Manufactured: list[MaterialEntry] = Field(default_factory=list, description="Manufactured materials from salvage and combat")
    Encoded: list[MaterialEntry] = Field(default_factory=list, description="Encoded data from scanning")
    LastUpdated: str = Field(default="", description="Timestamp of last materials update")


class Materials(Projection[MaterialsStateModel]):
    StateModel = MaterialsStateModel
    MATERIAL_CATEGORIES: tuple[MaterialsCategory, ...] = ("Raw", "Manufactured", "Encoded")
    TEMPLATE = MATERIAL_TEMPLATE
    LOOKUP = MATERIAL_NAME_LOOKUP

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        if not self.state.Raw:
            self.state.Raw = [MaterialEntry(**entry) for entry in MATERIAL_TEMPLATE["Raw"]]
        if not self.state.Manufactured:
            self.state.Manufactured = [MaterialEntry(**entry) for entry in MATERIAL_TEMPLATE["Manufactured"]]
        if not self.state.Encoded:
            self.state.Encoded = [MaterialEntry(**entry) for entry in MATERIAL_TEMPLATE["Encoded"]]

    def _get_bucket(self, category: MaterialsCategory) -> list[MaterialEntry]:
        return getattr(self.state, category)

    @override
    def process(self, event: Event) -> None:
        if not isinstance(event, GameEvent):
            return

        content = event.content
        event_name = content.get("event")

        # Update the stored timestamp when new data arrives.
        def update_timestamp() -> None:
            timestamp = content.get("timestamp")
            if isinstance(timestamp, str) and timestamp:
                self.state.LastUpdated = timestamp

        # Apply a delta to the appropriate material entry, creating it if needed.
        def update_material(name: str | None, delta: int, category: str | None = None, localized: str | None = None) -> None:
            if not name or delta == 0:
                return
            name_key = name.lower()
            bucket_name: MaterialsCategory | None = None
            if category:
                normalized = category.strip().lower()
                for option in self.MATERIAL_CATEGORIES:
                    if option.lower() == normalized:
                        bucket_name = option
                        break
            if not bucket_name:
                bucket_name = self.LOOKUP.get(name_key)
            if not bucket_name:
                return
            bucket = self._get_bucket(bucket_name)
            for entry in bucket:
                if entry.Name.lower() == name_key:
                    entry.Count = max(0, entry.Count + delta)
                    if localized:
                        entry.Name_Localised = localized
                    return
            if delta > 0:
                new_entry = MaterialEntry(Name=name, Count=delta, Name_Localised=localized)
                bucket.append(new_entry)

        if event_name == "Materials":
            for category in self.MATERIAL_CATEGORIES:
                items = content.get(category, [])
                incoming = {}
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict) and item.get("Name"):
                            incoming[item["Name"]] = item
                bucket = self._get_bucket(category)
                for entry in bucket:
                    payload = incoming.pop(entry.Name, None)
                    if payload:
                        entry.Count = payload.get("Count", 0) or 0
                        if payload.get("Name_Localised"):
                            entry.Name_Localised = payload["Name_Localised"]
                    else:
                        entry.Count = 0
                for payload in incoming.values():
                    new_entry = MaterialEntry(
                        Name=payload["Name"],
                        Count=payload.get("Count", 0) or 0,
                        Name_Localised=payload.get("Name_Localised"),
                    )
                    bucket.append(new_entry)
            update_timestamp()
            return

        if event_name == "MaterialTrade":
            paid = content.get("Paid")
            if isinstance(paid, dict):
                quantity = paid.get("Quantity", 0)
                if isinstance(quantity, int):
                    update_material(paid.get("Material"), -quantity, paid.get("Category"), paid.get("Material_Localised"))
            received = content.get("Received")
            if isinstance(received, dict):
                quantity = received.get("Quantity", 0)
                if isinstance(quantity, int):
                    update_material(received.get("Material"), quantity, received.get("Category"), received.get("Material_Localised"))
            update_timestamp()
            return

        if event_name == "MaterialCollected":
            count_value = content.get("Count", 0)
            name_value = content.get("Name")
            category_value = content.get("Category")
            localized_value = content.get("Name_Localised")
            if isinstance(count_value, int):
                update_material(
                    name_value if isinstance(name_value, str) else None,
                    count_value,
                    category_value if isinstance(category_value, str) else None,
                    localized_value if isinstance(localized_value, str) else None,
                )
                update_timestamp()
            return

        if event_name == "TechnologyBroker":
            materials = content.get("Materials")
            if isinstance(materials, list):
                for material in materials:
                    if isinstance(material, dict):
                        count_value = material.get("Count", 0)
                        if isinstance(count_value, int):
                            update_material(material.get("Name"), -count_value, material.get("Category"), material.get("Name_Localised"))
            update_timestamp()
            return

        if event_name == "EngineerCraft":
            ingredients = content.get("Ingredients")
            if isinstance(ingredients, list):
                for ingredient in ingredients:
                    if isinstance(ingredient, dict):
                        count_value = ingredient.get("Count", 0)
                        if isinstance(count_value, int):
                            update_material(ingredient.get("Name"), -count_value, None, ingredient.get("Name_Localised"))
            update_timestamp()
            return

        if event_name == "Synthesis":
            materials = content.get("Materials")
            if isinstance(materials, list):
                for material in materials:
                    if isinstance(material, dict):
                        count_value = material.get("Count", 0)
                        if isinstance(count_value, int):
                            update_material(material.get("Name"), -count_value)
            update_timestamp()
