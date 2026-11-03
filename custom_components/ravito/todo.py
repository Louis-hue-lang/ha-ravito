"""Liste de courses de Ravito en liste de tâches Home Assistant (carte native, Assist)."""
from __future__ import annotations

import re

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import RavitoError, RavitoScopeError
from .const import scope_allows
from .coordinator import RavitoCoordinator
from .sensor import RavitoEntity

# « 2 lait », « 2 x lait », « 1,5 farine » : quantité en tête
_QUANTITY_RE = re.compile(r"^(\d+(?:[.,]\d+)?)\s*(?:x\s+)?(.+)$", re.I)


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

    def __init__(self, coordinator: RavitoCoordinator) -> None:
        super().__init__(coordinator, "liste_de_courses")

    @property
    def supported_features(self) -> TodoListEntityFeature:
        # Ajouter et cocher demandent la portée « liste »
        if scope_allows(self.coordinator.scope, "liste"):
            return TodoListEntityFeature.CREATE_TODO_ITEM | TodoListEntityFeature.UPDATE_TODO_ITEM
        return TodoListEntityFeature(0)

    def _lines(self) -> list[dict]:
        return self.coordinator.data.get("shopping_list", {}).get("items", [])

    @property
    def todo_items(self) -> list[TodoItem]:
        # Rangées par rayon, comme dans l'app
        lines = sorted(
            self._lines(),
            key=lambda l: (l.get("category_order") is None, l.get("category_order") or 0, l["name"].lower()),
        )
        return [
            TodoItem(
                uid=str(line["id"]),
                summary=_summary(line),
                status=TodoItemStatus.COMPLETED if line.get("checked") else TodoItemStatus.NEEDS_ACTION,
                description=" ".join(
                    p for p in (line.get("category_icon"), line.get("category")) if p
                ) or None,
            )
            for line in lines
        ]

    async def _call(self, coro) -> None:
        try:
            await coro
        except RavitoScopeError as err:
            raise ServiceValidationError(
                "Le jeton Ravito doit avoir la portée « liste » pour modifier la liste"
            ) from err
        except RavitoError as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_request_refresh()

    async def async_create_todo_item(self, item: TodoItem) -> None:
        text = (item.summary or "").strip()
        quantity: float = 1
        if match := _QUANTITY_RE.match(text):
            quantity = float(match.group(1).replace(",", "."))
            text = match.group(2).strip()
        await self._call(self.coordinator.api.async_add_item(text, quantity))

    async def async_update_todo_item(self, item: TodoItem) -> None:
        line = next((l for l in self._lines() if str(l["id"]) == item.uid), None)
        if line is None:
            raise ServiceValidationError("Cette ligne n'est plus dans la liste de Ravito")
        if item.summary is not None and item.summary != _summary(line):
            raise ServiceValidationError("Renommer une ligne se fait dans l'app Ravito")
        checked = item.status == TodoItemStatus.COMPLETED
        if checked != bool(line.get("checked")):
            await self._call(self.coordinator.api.async_set_checked(line["id"], checked))
