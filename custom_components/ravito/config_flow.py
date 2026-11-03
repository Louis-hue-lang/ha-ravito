"""Configuration via l'interface : adresse de Ravito et jeton d'API."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_URL
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .api import RavitoApi, RavitoAuthError, RavitoError
from .const import CONF_TOKEN, DEFAULT_URL, DOMAIN

TOKEN_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL, default=DEFAULT_URL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        ),
        vol.Required(CONF_TOKEN): TOKEN_SELECTOR,
    }
)


async def _validate(hass, url: str, token: str) -> dict[str, str]:
    api = RavitoApi(async_get_clientsession(hass), url, token.strip())
    try:
        await api.async_summary()
    except RavitoAuthError:
        return {"base": "invalid_auth"}
    except RavitoError:
        return {"base": "cannot_connect"}
    return {}


class RavitoConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_URL].strip().rstrip("/")
            await self.async_set_unique_id(urlparse(url).netloc.lower(), raise_on_progress=False)
            self._abort_if_unique_id_configured()
            errors = await _validate(self.hass, url, user_input[CONF_TOKEN])
            if not errors:
                return self.async_create_entry(
                    title="Ravito",
                    data={CONF_URL: url, CONF_TOKEN: user_input[CONF_TOKEN].strip()},
                )
        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            errors = await _validate(self.hass, entry.data[CONF_URL], user_input[CONF_TOKEN])
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_TOKEN: user_input[CONF_TOKEN].strip()}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): TOKEN_SELECTOR}),
            errors=errors,
        )
