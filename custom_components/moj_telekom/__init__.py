"""Moj Telekom — HA integracija koja čita stanje brojeva s web portala."""
from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import MojTelekomCoordinator

PLATFORMS = ["sensor"]
CARD_URL = "/moj_telekom/moj-telekom-card.js"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Posluži karticu i učitaj je automatski — korisnik je samo doda na dashboard."""
    card_path = Path(__file__).parent / "www" / "moj-telekom-card.js"
    # Bez cachea: nakon HACS nadogradnje ne ostaje stara kartica u browseru.
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(card_path), False)]
    )
    add_extra_js_url(hass, CARD_URL)
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
