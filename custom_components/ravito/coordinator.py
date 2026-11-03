"""Coordinateur : relit le résumé de Ravito (liste, stock, péremptions, menu) chaque minute."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import RavitoApi, RavitoAuthError, RavitoError
from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class RavitoCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """data = réponse de GET /api/ha/summary."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: RavitoApi) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.api = api
        self.entry = entry

    @property
    def scope(self) -> str | None:
        return (self.data or {}).get("scope")

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.api.async_summary()
        except RavitoAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except RavitoError as err:
            raise UpdateFailed(str(err)) from err
