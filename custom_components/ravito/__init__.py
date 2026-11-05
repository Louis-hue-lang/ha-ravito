"""Intégration Ravito : liste de courses (lecture), menu de la semaine et recettes."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL, Platform
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import RavitoApi, RavitoError, RavitoScopeError
from .const import CONF_TOKEN, DOMAIN
from .coordinator import RavitoCoordinator

PLATFORMS = [Platform.SENSOR, Platform.TODO]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
CARD_URL = "/ravito/ravito-card.js"
CARD_FILE = Path(__file__).parent / "frontend" / "ravito-card.js"
VERSION = "0.2.2"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Sert la carte Lovelace et les commandes WebSocket qu'elle appelle."""
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(CARD_FILE), False)]
    )
    add_extra_js_url(hass, f"{CARD_URL}?v={VERSION}")
    add_extra_js_url(hass, f"{CARD_URL}?v={VERSION}", es5=True)
    for command in (ws_recipes, ws_recipe, ws_menu, ws_menu_add, ws_menu_remove):
        websocket_api.async_register_command(hass, command)
    return True


def _coordinator(hass: HomeAssistant) -> RavitoCoordinator | None:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    return entries[0].runtime_data if entries else None


async def _run(hass, connection, msg, call, refresh: bool = False) -> None:
    """Appelle Ravito et répond à la carte ; base_url sert aux photos (adresses signées)."""
    coordinator = _coordinator(hass)
    if coordinator is None:
        connection.send_error(msg["id"], "not_configured", "Ravito n'est pas configuré")
        return
    try:
        result: Any = await call(coordinator.api)
    except RavitoScopeError:
        connection.send_error(
            msg["id"], "forbidden", "Le jeton Ravito doit avoir la portée « cuisine » pour modifier le menu"
        )
        return
    except RavitoError as err:
        connection.send_error(msg["id"], "ravito_error", str(err))
        return
    if refresh:
        # Le menu alimente les capteurs et la liste de courses
        await coordinator.async_request_refresh()
    connection.send_result(msg["id"], {"base_url": coordinator.api.url, "data": result})


@websocket_api.websocket_command({vol.Required("type"): "ravito/recipes"})
@websocket_api.async_response
async def ws_recipes(hass, connection, msg) -> None:
    await _run(hass, connection, msg, lambda api: api.async_recipes())


@websocket_api.websocket_command({vol.Required("type"): "ravito/recipe", vol.Required("recipe_id"): int})
@websocket_api.async_response
async def ws_recipe(hass, connection, msg) -> None:
    await _run(hass, connection, msg, lambda api: api.async_recipe(msg["recipe_id"]))


@websocket_api.websocket_command({vol.Required("type"): "ravito/menu"})
@websocket_api.async_response
async def ws_menu(hass, connection, msg) -> None:
    await _run(hass, connection, msg, lambda api: api.async_menu())


@websocket_api.websocket_command(
    {
        vol.Required("type"): "ravito/menu/add",
        vol.Required("recipe_id"): int,
        vol.Optional("day"): vol.Any(None, cv.date),
        vol.Optional("servings"): vol.Any(None, vol.All(int, vol.Range(min=1, max=99))),
    }
)
@websocket_api.async_response
async def ws_menu_add(hass, connection, msg) -> None:
    day = msg.get("day")
    await _run(
        hass,
        connection,
        msg,
        lambda api: api.async_add_to_menu(
            msg["recipe_id"], day.isoformat() if day else None, msg.get("servings")
        ),
        refresh=True,
    )


@websocket_api.websocket_command({vol.Required("type"): "ravito/menu/remove", vol.Required("entry_id"): int})
@websocket_api.async_response
async def ws_menu_remove(hass, connection, msg) -> None:
    await _run(hass, connection, msg, lambda api: api.async_remove_from_menu(msg["entry_id"]), refresh=True)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    api = RavitoApi(async_get_clientsession(hass), entry.data[CONF_URL], entry.data[CONF_TOKEN])
    coordinator = RavitoCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
