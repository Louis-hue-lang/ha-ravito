"""Capteurs : à acheter, stock bas, péremptions, menu du jour."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RavitoCoordinator


class RavitoEntity(CoordinatorEntity[RavitoCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: RavitoCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Ravito",
            manufacturer="Ravito",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=entry.data[CONF_URL],
        )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            AchatsSensor(coordinator),
            StockBasSensor(coordinator),
            PeremptionsSensor(coordinator),
            MenuDuJourSensor(coordinator),
        ]
    )


class AchatsSensor(RavitoEntity, SensorEntity):
    """Lignes de la liste de courses pas encore cochées."""

    _attr_translation_key = "a_acheter"
    _attr_icon = "mdi:cart-outline"
    _attr_native_unit_of_measurement = "articles"

    def __init__(self, coordinator: RavitoCoordinator) -> None:
        super().__init__(coordinator, "a_acheter")

    @property
    def native_value(self) -> int:
        return self.coordinator.data.get("shopping_list", {}).get("unchecked", 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        lines = self.coordinator.data.get("shopping_list", {}).get("items", [])
        return {
            "total": len(lines),
            "articles": [l["name"] for l in lines if not l.get("checked")],
        }


class StockBasSensor(RavitoEntity, SensorEntity):
    """Articles sous leur objectif de stock."""

    _attr_translation_key = "stock_bas"
    _attr_icon = "mdi:package-variant"
    _attr_native_unit_of_measurement = "articles"

    def __init__(self, coordinator: RavitoCoordinator) -> None:
        super().__init__(coordinator, "stock_bas")

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.get("low_stock", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"articles": self.coordinator.data.get("low_stock", [])}


class PeremptionsSensor(RavitoEntity, SensorEntity):
    """Articles en stock qui périment d'ici 3 jours (périmés compris)."""

    _attr_translation_key = "peremptions"
    _attr_icon = "mdi:calendar-alert"
    _attr_native_unit_of_measurement = "articles"

    def __init__(self, coordinator: RavitoCoordinator) -> None:
        super().__init__(coordinator, "peremptions")

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.get("expiring", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        expiring = self.coordinator.data.get("expiring", [])
        return {
            "articles": expiring,
            "perimes": [e["name"] for e in expiring if e.get("days_left", 0) < 0],
        }


class MenuDuJourSensor(RavitoEntity, SensorEntity):
    """Plats prévus aujourd'hui ; la semaine en attribut."""

    _attr_translation_key = "menu_du_jour"
    _attr_icon = "mdi:silverware-fork-knife"

    def __init__(self, coordinator: RavitoCoordinator) -> None:
        super().__init__(coordinator, "menu_du_jour")

    @property
    def native_value(self) -> str:
        dishes = [m["recipe"] for m in self.coordinator.data.get("menu_today", [])]
        # Un état est limité à 255 caractères
        return (", ".join(dishes) or "Rien de prévu")[:255]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        return {"plats": data.get("menu_today", []), "semaine": data.get("menu_week", [])}
