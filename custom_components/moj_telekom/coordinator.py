"""Koordinator: drži klijent portala i dohvaća stanje brojeva."""
from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_FEATURES, CONF_SCAN_INTERVAL, DEFAULT_FEATURES, DEFAULT_SCAN_INTERVAL_MIN, DOMAIN
from .core import (
    AuthError,
    PortalClient,
    PortalUnavailableError,
    fetch_numbers,
    normalize_features,
    resolve_credentials,
    to_dict,
)

_LOGGER = logging.getLogger(__name__)

# Koliko uzastopnih prolaznih grešaka toleriramo uz zadržane vrijednosti (15 min * 2 = 30 min).
TRANSIENT_GRACE = 2


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
        self._entry_data = dict(entry.data)
        self._features = normalize_features(entry.options.get(CONF_FEATURES, DEFAULT_FEATURES))
        # Klijent se stvara pri prvom dohvaćanju: lozinka može doći iz okoline (MT_PASSWORD),
        # pa u config entryju tada nije spremljena nikakva tajna.
        self._client: PortalClient | None = None
        self._failures = 0

    async def _async_update_data(self) -> list[dict]:
        credentials = resolve_credentials(self._entry_data)
        if credentials is None:
            raise UpdateFailed(
                "Nema podataka za prijavu: upiši lozinku u integraciji ili postavi "
                "MT_USERNAME i MT_PASSWORD u okolinu procesa."
            )
        if self._client is None:
            self._client = PortalClient(*credentials)

        try:
            numbers = await fetch_numbers(self._client, self._features)
        except AuthError as err:
            # Sljedeći pokušaj kreće s čistom sesijom (npr. istekao cookie).
            await self._client.close()
            return self._transient(err)
        except (PortalUnavailableError, aiohttp.ClientError, TimeoutError) as err:
            return self._transient(err)
        else:
            self._failures = 0
        if not numbers:
            # Tiho prazno stanje je najgori ishod: korisnik ne vidi ni grešku ni entitete.
            raise UpdateFailed(
                "Portal nije vratio ni jedan broj. Provjeri da račun ima mobilne usluge; "
                "ako ima, pošalji dijagnostiku (Uređaji → Moj Telekom → Download diagnostics)."
            )
        return [to_dict(number) for number in numbers]

    def _transient(self, err: Exception) -> list[dict]:
        """Prolazna greška (sesija/portal/mreža): zadrži zadnje vrijednosti umjesto da
        entiteti na jedan ciklus padnu u "nedostupno". Nakon TRANSIENT_GRACE uzastopnih
        grešaka ipak javlja grešku, da se stvarni problem ne skriva zauvijek.
        """
        self._failures += 1
        if self.data is not None and self._failures <= TRANSIENT_GRACE:
            _LOGGER.warning(
                "Moj Telekom: privremeni problem pri dohvatu (%s) — zadržavam zadnje poznate "
                "vrijednosti (%d/%d).",
                err,
                self._failures,
                TRANSIENT_GRACE,
            )
            return self.data
        raise UpdateFailed(str(err)) from err

    async def async_close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None
