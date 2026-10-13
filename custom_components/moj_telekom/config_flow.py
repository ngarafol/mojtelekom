"""Konfiguracijski i opcijski tok: prijava Telekom ID podacima kao na portalu."""
from __future__ import annotations

import logging

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_FEATURES,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    DEFAULT_FEATURES,
    DEFAULT_SCAN_INTERVAL_MIN,
    DOMAIN,
    FEATURE_LABELS,
)
from .core import AuthError, PortalClient, fetch_numbers, resolve_credentials

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            credentials = resolve_credentials(user_input)
            if credentials is None:
                errors["base"] = "no_credentials"
            else:
                username, password = credentials
                await self.async_set_unique_id(username)
                self._abort_if_unique_id_configured()
                client = PortalClient(username, password)
                try:
                    # Dovoljna je provjera prijave i popisa usluga ("status" ne vuče ostalo).
                    await fetch_numbers(client, ["status"])
                except AuthError as err:
                    _LOGGER.warning("Moj Telekom: prijava nije prošla: %s", err)
                    errors["base"] = "auth"
                except (aiohttp.ClientError, TimeoutError) as err:
                    _LOGGER.warning("Moj Telekom: dohvat nije uspio: %s", err)
                    errors["base"] = "cannot_connect"
                else:
                    # Ostale iznimke (npr. promijenjen markup portala) namjerno idu dalje:
                    # HA ih prikaže kao "unknown error", a log pokaže pravi uzrok.
                    data = {CONF_USERNAME: username}
                    if user_input.get(CONF_PASSWORD):
                        # Lozinku spremamo samo ako ju je korisnik stvarno upisao; ako dolazi
                        # iz okoline, u .storage (i backupima) nema nikakve tajne.
                        data[CONF_PASSWORD] = user_input[CONF_PASSWORD]
                    return self.async_create_entry(title=f"Moj Telekom ({username})", data=data)
                finally:
                    await client.close()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    # Prazno = lozinka dolazi iz okoline (MT_PASSWORD), pa se ne sprema u HA.
                    vol.Optional(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> OptionsFlow:
        return OptionsFlow()


class OptionsFlow(config_entries.OptionsFlowWithReload):
    """Promjena opcija sama reloada integraciju (zato u __init__.py nema update listenera)."""

    async def async_step_init(self, user_input: dict | None = None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_FEATURES,
                        default=self.config_entry.options.get(CONF_FEATURES, DEFAULT_FEATURES),
                    ): cv.multi_select(FEATURE_LABELS),
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MIN
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=5, max=1440)),
                }
            ),
        )
