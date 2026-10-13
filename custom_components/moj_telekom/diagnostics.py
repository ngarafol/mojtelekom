"""Dijagnostika za prijavu problema (Postavke → Uređaji → Moj Telekom → Download diagnostics).

Vjerodajnice se redaktiraju, a brojevi maskiraju na zadnje tri znamenke — dovoljno da se
vidi koji broj ima problem, a da se ne dijeli puni broj.
"""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from .const import CONF_FEATURES, CONF_PASSWORD, CONF_USERNAME, DOMAIN

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD}


def _mask(msisdn: str | None) -> str:
    return f"***{msisdn[-3:]}" if msisdn and len(msisdn) > 3 else "***"


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    numbers = coordinator.data if coordinator else []
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": {
            "features": entry.options.get(CONF_FEATURES),
            "scan_interval_minutes": entry.options.get("scan_interval_minutes"),
        },
        "last_update_success": getattr(coordinator, "last_update_success", None),
        "numbers": [
            {
                "msisdn": _mask(number.get("msisdn")),
                "status": number.get("status"),
                "tariff": number.get("tariff"),
                "balance": (number.get("prepaid") or {}).get("balance"),
                "valid_until": (number.get("prepaid") or {}).get("valid_until"),
                "data_remaining_mb": (number.get("usage") or {}).get("data_remaining_mb"),
                "options": [option.get("name") for option in number.get("options", [])],
            }
            for number in numbers
        ],
    }
