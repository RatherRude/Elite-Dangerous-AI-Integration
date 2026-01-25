from typing import Optional

from typing import Optional, cast

from typing_extensions import override
from pydantic import BaseModel, Field

from ..Event import Event, GameEvent
from ..EventManager import Projection
from ..EventModels import BackpackChangeEvent, BackpackEvent


class BackpackItem(BaseModel):
    """An item in the commander's backpack (on-foot inventory)."""
    Name: str = Field(description="Item internal name")
    OwnerID: int = Field(description="Owner identifier")
    Count: int = Field(description="Quantity of this item")
    Name_Localised: Optional[str] = Field(default=None, description="Human-readable item name")
    MissionID: Optional[int] = Field(default=None, description="Associated mission ID")


class BackpackStateModel(BaseModel):
    """Commander's on-foot backpack inventory."""
    Items: list[BackpackItem] = Field(default_factory=list, description="General items")
    Components: list[BackpackItem] = Field(default_factory=list, description="Crafting components")
    Consumables: list[BackpackItem] = Field(default_factory=list, description="Consumable items (medkits, batteries, etc.)")
    Data: list[BackpackItem] = Field(default_factory=list, description="Data items")


class Backpack(Projection[BackpackStateModel]):
    StateModel = BackpackStateModel

    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent) and event.content.get("event") == "Backpack":
            payload = cast(BackpackEvent, event.content)
            # Reset and update all categories with proper BackpackItem parsing
            self.state.Items = [
                BackpackItem(
                    Name=item.get("Name", ""),
                    OwnerID=item.get("OwnerID", 0),
                    Count=item.get("Count", 0),
                    Name_Localised=item.get("Name_Localised"),
                )
                for item in payload.get("Items", [])
            ]
            self.state.Components = [
                BackpackItem(
                    Name=item.get("Name", ""),
                    OwnerID=item.get("OwnerID", 0),
                    Count=item.get("Count", 0),
                    Name_Localised=item.get("Name_Localised"),
                )
                for item in payload.get("Components", [])
            ]
            self.state.Consumables = [
                BackpackItem(
                    Name=item.get("Name", ""),
                    OwnerID=item.get("OwnerID", 0),
                    Count=item.get("Count", 0),
                    Name_Localised=item.get("Name_Localised"),
                )
                for item in payload.get("Consumables", [])
            ]
            self.state.Data = [
                BackpackItem(
                    Name=item.get("Name", ""),
                    OwnerID=item.get("OwnerID", 0),
                    Count=item.get("Count", 0),
                    Name_Localised=item.get("Name_Localised"),
                )
                for item in payload.get("Data", [])
            ]

        if isinstance(event, GameEvent) and event.content.get("event") == "BackpackChange":
            payload = cast(BackpackChangeEvent, event.content)
            added = payload.get("Added", [])
            if added:
                for item in added:
                    item_type = item.get("Type", "")
                    new_item = BackpackItem(
                        Name=item.get("Name", ""),
                        OwnerID=item.get("OwnerID", 0),
                        Count=item.get("Count", 0),
                        Name_Localised=item.get("Name_Localised"),
                    )

                    if item_type == "Item":
                        self._add_or_update_item("Items", new_item)
                    elif item_type == "Component":
                        self._add_or_update_item("Components", new_item)
                    elif item_type == "Consumable":
                        self._add_or_update_item("Consumables", new_item)
                    elif item_type == "Data":
                        self._add_or_update_item("Data", new_item)

            removed = payload.get("Removed", [])
            if removed:
                for item in removed:
                    item_type = item.get("Type", "")
                    item_name = item.get("Name", "")
                    item_count = item.get("Count", 0)

                    if item_type == "Item":
                        self._remove_item("Items", item_name, item_count)
                    elif item_type == "Component":
                        self._remove_item("Components", item_name, item_count)
                    elif item_type == "Consumable":
                        self._remove_item("Consumables", item_name, item_count)
                    elif item_type == "Data":
                        self._remove_item("Data", item_name, item_count)

    def _add_or_update_item(self, category: str, new_item: BackpackItem) -> None:
        """Add a new item or update the count of an existing item in the specified category."""
        category_list: list[BackpackItem] = getattr(self.state, category)
        for item in category_list:
            if item.Name == new_item.Name:
                # Item exists, update count
                item.Count += new_item.Count
                return

        # Item doesn't exist, add it
        category_list.append(new_item)

    def _remove_item(self, category: str, item_name: str, count: int) -> None:
        """Remove an item or reduce its count in the specified category."""
        category_list: list[BackpackItem] = getattr(self.state, category)
        for i, item in enumerate(category_list):
            if item.Name == item_name:
                # Reduce count
                item.Count -= count

                # Remove item if count is zero or less
                if item.Count <= 0:
                    category_list.pop(i)

                break
