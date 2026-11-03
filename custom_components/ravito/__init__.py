"""Intégration Ravito : liste de courses, stock, menu et Chef à la voix."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL, Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import RavitoApi, RavitoError, RavitoScopeError
from .const import CONF_TOKEN, DOMAIN
from .coordinator import RavitoCoordinator

PLATFORMS = [Platform.SENSOR, Platform.TODO]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
CHEF_SCHEMA = vol.Schema({vol.Required("texte"): cv.string})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async def _chef(call: ServiceCall) -> ServiceResponse:
        """Une phrase dite à Chef ; « oui » / « non » répond à ses propositions."""
        entries = hass.config_entries.async_loaded_entries(DOMAIN)
        if not entries:
            raise ServiceValidationError("Ravito n'est pas configuré")
        coordinator: RavitoCoordinator = entries[0].runtime_data
        try:
            result = await coordinator.api.async_chef(call.data["texte"])
        except RavitoScopeError as err:
            raise ServiceValidationError(
                "Le jeton Ravito doit avoir la portée « cuisine » pour parler à Chef"
            ) from err
        except RavitoError as err:
            raise HomeAssistantError(str(err)) from err
        # Une action acceptée par « oui » a pu changer la liste ou le menu
        await coordinator.async_request_refresh()
        return {"speech": result.get("speech", ""), "messages": result.get("messages", [])}

    hass.services.async_register(
        DOMAIN, "chef", _chef, schema=CHEF_SCHEMA, supports_response=SupportsResponse.ONLY
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    api = RavitoApi(async_get_clientsession(hass), entry.data[CONF_URL], entry.data[CONF_TOKEN])
    coordinator = RavitoCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
