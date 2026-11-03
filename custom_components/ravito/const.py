"""Constantes de l'intégration Ravito."""
from datetime import timedelta

DOMAIN = "ravito"

CONF_TOKEN = "token"
DEFAULT_URL = "https://ravito.fitoune.fr"

# 60 requêtes/min par jeton côté Ravito : une par minute laisse la place à l'écran /ecran
SCAN_INTERVAL = timedelta(seconds=60)

# Portées emboîtées des jetons Ravito
SCOPES = ("lecture", "liste", "cuisine")


def scope_allows(scope: str | None, needed: str) -> bool:
    if scope not in SCOPES:
        return False
    return SCOPES.index(scope) >= SCOPES.index(needed)
