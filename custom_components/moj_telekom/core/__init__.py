# GENERIRANO iz mojtelekom/core/__init__.py — ne uređivati; pokreni scripts/sync_core.py
"""Zajednički core: modeli, klijent portala i dohvat.

Bez Home Assistant i bez pydantica — namjerno, da ga mogu dijeliti CLI/API i HA integracija.
Ova se mapa kopira u `custom_components/moj_telekom/core/` skriptom `scripts/sync_core.py`.
"""
from .credentials import ENV_PASSWORD, ENV_USERNAME, resolve_credentials
from .fetch import fetch_numbers
from .models import (
    FEATURES,
    NumberInfo,
    Option,
    Prepaid,
    Usage,
    filter_features,
    national_number,
    normalize_features,
    to_dict,
)
from .portal import AuthError, PortalClient, PortalUnavailableError

__all__ = (
    "ENV_PASSWORD",
    "ENV_USERNAME",
    "FEATURES",
    "AuthError",
    "NumberInfo",
    "Option",
    "PortalClient",
    "PortalUnavailableError",
    "Prepaid",
    "Usage",
    "fetch_numbers",
    "filter_features",
    "national_number",
    "normalize_features",
    "resolve_credentials",
    "to_dict",
)
