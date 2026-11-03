"""Client minimal pour l'API Home Assistant de Ravito (/api/ha/*)."""
from __future__ import annotations

from typing import Any

import aiohttp

TIMEOUT = aiohttp.ClientTimeout(total=20)
# Chef met quelques secondes à répondre
CHEF_TIMEOUT = aiohttp.ClientTimeout(total=60)


class RavitoError(Exception):
    """Erreur générique."""


class RavitoAuthError(RavitoError):
    """Jeton refusé (inconnu, révoqué ou compte supprimé)."""


class RavitoScopeError(RavitoError):
    """Portée du jeton insuffisante."""


class RavitoApi:
    def __init__(self, session: aiohttp.ClientSession, url: str, token: str) -> None:
        self._session = session
        self._url = url.rstrip("/")
        self._token = token

    async def _request(
        self, method: str, path: str, payload: dict | None = None, timeout=TIMEOUT
    ) -> Any:
        try:
            async with self._session.request(
                method,
                f"{self._url}/api/ha{path}",
                json=payload,
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=timeout,
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

    async def async_add_item(self, name: str, quantity: float = 1) -> dict[str, Any]:
        return await self._request("POST", "/shopping-list", {"name": name, "quantity": quantity})

    async def async_set_checked(self, item_id: int, checked: bool) -> dict[str, Any]:
        return await self._request("PATCH", f"/shopping-list/{item_id}", {"checked": checked})

    async def async_chef(self, text: str) -> dict[str, Any]:
        return await self._request("POST", "/chef", {"text": text}, timeout=CHEF_TIMEOUT)
