"""Koordinator: drži klijent portala i dohvaća stanje brojeva."""
from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_FEATURES,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    DEFAULT_FEATURES,
    DEFAULT_SCAN_INTERVAL_MIN,
    DOMAIN,
)
from .core import AuthError, PortalClient, fetch_numbers, normalize_features, to_dict

_LOGGER = logging.getLogger(__name__)


class MojTelekomCoordinator(DataUpdateCoordinator[list[dict]]):
    """Klijent se drži između pollova — tako se ne prijavljujemo na svakom osvježavanju."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(
                minutes=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MIN)
            ),
        )
        self._client = PortalClient(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
        self._features = normalize_features(entry.options.get(CONF_FEATURES, DEFAULT_FEATURES))

    async def _async_update_data(self) -> list[dict]:
        try:
            numbers = await fetch_numbers(self._client, self._features)
        except AuthError as err:
            # Sljedeći pokušaj kreće s čistom sesijom (npr. istekao cookie).
            await self._client.close()
            raise UpdateFailed(str(err)) from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(f"Dohvat s portala nije uspio: {err}") from err
        if not numbers:
            # Tiho prazno stanje je najgori ishod: korisnik ne vidi ni grešku ni entitete.
            raise UpdateFailed(
                "Portal nije vratio ni jedan broj. Provjeri da račun ima mobilne usluge; "
                "ako ima, pošalji dijagnostiku (Uređaji → Moj Telekom → Download diagnostics)."
            )
        return [to_dict(number) for number in numbers]

    async def async_close(self) -> None:
        await self._client.close()
