"""Moj Telekom — HA integracija koja čita stanje brojeva s web portala."""
from __future__ import annotations

import json
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import MojTelekomCoordinator

PLATFORMS = ["sensor"]
CARD_URL = "/moj_telekom/moj-telekom-card.js"


def card_version() -> str:
    """Verzija iz manifesta — ide u URL kartice da browser ne zadrži stari JS."""
    try:
        manifest = json.loads((Path(__file__).parent / "manifest.json").read_text(encoding="utf-8"))
        return str(manifest.get("version") or "")
    except (OSError, ValueError):
        return ""


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Posluži karticu i učitaj je automatski — korisnik je samo doda na dashboard."""
    card_path = Path(__file__).parent / "www" / "moj-telekom-card.js"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(card_path), True)]
    )
    # ?v=<verzija> mijenja URL pri svakoj nadogradnji, pa stari JS modul ne može ostati
    # u browseru (prije je to tražilo ručni hard refresh).
    version = card_version()
    add_extra_js_url(hass, f"{CARD_URL}?v={version}" if version else CARD_URL)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = MojTelekomCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()  # ili ConfigEntryNotReady
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator: MojTelekomCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_close()
    return unloaded
