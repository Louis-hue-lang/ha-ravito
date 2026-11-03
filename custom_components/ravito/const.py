"""Constantes de l'intégration Ravito."""
from datetime import timedelta

DOMAIN = "ravito"

CONF_TOKEN = "token"
DEFAULT_URL = "https://ravito.fitoune.fr"

# 60 requêtes/min par jeton côté Ravito : une par minute laisse la place à la carte
SCAN_INTERVAL = timedelta(seconds=60)
