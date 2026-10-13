from __future__ import annotations

from datetime import timedelta

from .core import FEATURES

DOMAIN = "moj_telekom"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_FEATURES = "features"
CONF_SCAN_INTERVAL = "scan_interval_minutes"

# Portal je osjetljiv na broj zahtjeva; 15 min uz dijeljenu sesiju je ~36 zahtjeva/h.
DEFAULT_SCAN_INTERVAL_MIN = 15
DEFAULT_SCAN_INTERVAL = timedelta(minutes=DEFAULT_SCAN_INTERVAL_MIN)
DEFAULT_FEATURES = list(FEATURES)

# Prikaz u HA UI-u (multi-select u opcijama)
FEATURE_LABELS = {
    "status": "Status broja",
    "prepaid": "Prepaid stanje",
    "usage": "Potrošnja paketa",
    "invoice": "Računi",
    "options": "Aktivne opcije",
}
