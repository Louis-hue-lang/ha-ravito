"""Liste de courses de Ravito, en lecture seule (elle se modifie dans l'app)."""
from __future__ import annotations

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import RavitoCoordinator
from .sensor import RavitoEntity


def _quantity_label(line: dict) -> str:
    quantity = line.get("quantity") or 1
    text = f"{quantity:g}" if isinstance(quantity, (int, float)) else str(quantity)
    # « pièce » n'apporte rien : « Cordon Bleu (×2) » plutôt que « (2 pièce) »
    if line.get("unit") and line["unit"].lower() not in ("pièce", "pièces"):
        return f"{text} {line['unit']}"
    return "" if quantity == 1 else f"×{text}"


def _summary(line: dict) -> str:
    label = _quantity_label(line)
    return f"{line['name']} ({label})" if label else line["name"]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([RavitoShoppingList(entry.runtime_data)])


class RavitoShoppingList(RavitoEntity, TodoListEntity):
    _attr_translation_key = "liste_de_courses"
    _attr_icon = "mdi:cart"
    # Ni ajout, ni coche, ni suppression depuis Home Assistant
    _attr_supported_features = TodoListEntityFeature(0)

    def __init__(self, coordinator: RavitoCoordinator) -> None:
        super().__init__(coordinator, "liste_de_courses")

    @property
    def todo_items(self) -> list[TodoItem]:
        # Rangées par rayon, comme dans l'app
        lines = sorted(
            self.coordinator.data.get("shopping_list", {}).get("items", []),
            key=lambda l: (l.get("category_order") is None, l.get("category_order") or 0, l["name"].lower()),
        )
        return [
            TodoItem(
                uid=str(line["id"]),
                summary=_summary(line),
                status=TodoItemStatus.NEEDS_ACTION,
                description=" ".join(
                    p for p in (line.get("category_icon"), line.get("category")) if p
                ) or None,
            )
            for line in lines
        ]
