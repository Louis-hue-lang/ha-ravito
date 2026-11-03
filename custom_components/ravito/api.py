"""Client minimal pour l'API Home Assistant de Ravito (/api/ha/*)."""
from __future__ import annotations

from typing import Any

import aiohttp

TIMEOUT = aiohttp.ClientTimeout(total=20)


class RavitoError(Exception):
    """Erreur générique."""


class RavitoAuthError(RavitoError):
    """Jeton refusé (inconnu, révoqué ou compte supprimé)."""


class RavitoScopeError(RavitoError):
    """Portée du jeton insuffisante."""


class RavitoApi:
    def __init__(self, session: aiohttp.ClientSession, url: str, token: str) -> None:
        self._session = session
        self.url = url.rstrip("/")
        self._token = token

    async def _request(self, method: str, path: str, payload: dict | None = None) -> Any:
        try:
            async with self._session.request(
                method,
                f"{self.url}/api/ha{path}",
                json=payload,
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=TIMEOUT,
            ) as resp:
                if resp.status == 401:
                    raise RavitoAuthError("Jeton refusé")
                if resp.status == 403:
                    raise RavitoScopeError("Portée du jeton insuffisante")
                if resp.status >= 400:
                    try:
                        message = (await resp.json()).get("statusMessage")
                    except (aiohttp.ContentTypeError, ValueError, AttributeError):
                        message = None
                    raise RavitoError(message or f"HTTP {resp.status}")
                return await resp.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise RavitoError(f"Ravito injoignable : {err}") from err

    async def async_summary(self) -> dict[str, Any]:
        return await self._request("GET", "/summary")

    async def async_recipes(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/recipes")

    async def async_recipe(self, recipe_id: int) -> dict[str, Any]:
        return await self._request("GET", f"/recipes/{recipe_id}")

    async def async_menu(self) -> dict[str, Any]:
        return await self._request("GET", "/menu")

    async def async_add_to_menu(
        self, recipe_id: int, day: str | None, servings: int | None = None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"recipe_id": recipe_id, "day": day}
        if servings:
            payload["servings"] = servings
        return await self._request("POST", "/menu", payload)

    async def async_remove_from_menu(self, entry_id: int) -> dict[str, Any]:
        return await self._request("DELETE", f"/menu/{entry_id}")
