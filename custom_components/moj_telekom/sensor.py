from __future__ import annotations

import logging
from datetime import date
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_FEATURES, DEFAULT_FEATURES, DOMAIN
from .coordinator import MojTelekomCoordinator
from .core import FEATURES, normalize_features

_LOGGER = logging.getLogger(__name__)

# Značajka -> (oznaka, ikona, device class, state class). SAMO značajke koje daju senzor!
# `options` namjerno nije ovdje: nema svoj senzor, nego dolazi kao atribut `aktivne_opcije`
# na ostalim senzorima (zato je u core.FEATURES, ali ne u ovoj mapi).
FEATURE_META: dict[str, tuple[str, str, SensorDeviceClass | None, SensorStateClass | None]] = {
    "prepaid": ("Prepaid stanje", "mdi:cash", SensorDeviceClass.MONETARY, SensorStateClass.TOTAL),
    "usage": ("Preostali promet", "mdi:web", SensorDeviceClass.DATA_SIZE, SensorStateClass.TOTAL),
    "valid_until": ("Vrijedi do", "mdi:calendar-check", SensorDeviceClass.DATE, None),
    "status": ("Status", "mdi:sim", None, None),
    "options": ("Aktivne opcije", "mdi:playlist-check", None, None),
}
SENSOR_FEATURES = tuple(feature for feature in FEATURES if feature in FEATURE_META)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: MojTelekomCoordinator = hass.data[DOMAIN][entry.entry_id]
    configured = entry.options.get(CONF_FEATURES, DEFAULT_FEATURES)
    features = normalize_features(configured)
    if sorted(features) != sorted(configured):
        _LOGGER.warning("Moj Telekom: popis značajki u opcijama je nepotpun (%s) — koristim %s", configured, features)

    sensor_features = [feature for feature in features if feature in SENSOR_FEATURES]
    numbers = coordinator.data or []
    if not numbers:
        _LOGGER.warning(
            "Moj Telekom: portal nije vratio ni jedan broj, pa nema ni entiteta. "
            "Provjeri da račun ima mobilne usluge i pogledaj ranije poruke u dnevniku."
        )
    async_add_entities(
        MojTelekomSensor(coordinator, entry, number["msisdn"], feature)
        for number in numbers
        for feature in sensor_features
    )


class MojTelekomSensor(CoordinatorEntity[MojTelekomCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self, coordinator: MojTelekomCoordinator, entry: ConfigEntry, msisdn: str, feature: str
    ) -> None:
        super().__init__(coordinator)
        self._msisdn = msisdn
        self._feature = feature
        label, icon, device_class, state_class = FEATURE_META[feature]
        self._attr_name = label
        self._attr_unique_id = f"{entry.entry_id}_{msisdn}_{feature}"
        self._attr_icon = icon
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, msisdn)},
            name=self._number.get("alias") or msisdn,
            manufacturer="Hrvatski Telekom",
            model="Moj Telekom broj",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def _number(self) -> dict[str, Any] | None:
        for number in self.coordinator.data or []:
            if number.get("msisdn") == self._msisdn:
                return number
        return None

    @property
    def available(self) -> bool:
        return super().available and self._number is not None

    @property
    def native_value(self):
        number = self._number
        if number is None:
            return None
        match self._feature:
            case "prepaid":
                prepaid = number.get("prepaid")
                return prepaid["balance"] if prepaid else None
            case "usage":
                usage = number.get("usage")
                # Preostali besplatni MB; ako ih portal ne navede, stanje ostaje nepoznato.
                return usage.get("data_remaining_mb") if usage else None
            case "valid_until":
                # HA za device_class DATE traži date objekt, ne string.
                value = number.get("valid_until")
                return date.fromisoformat(value) if value else None
            case "options":
                names = [option.get("name") for option in number.get("options", [])]
                return ", ".join(names) if names else "nema aktivnih"
            case "status":
                return number.get("status")
        return None

    @property
    def native_unit_of_measurement(self):
        number = self._number or {}
        match self._feature:
            case "prepaid":
                return (number.get("prepaid") or {}).get("currency")
            case "usage":
                # "MB" je vrijednost koju HA traži za data_size; novije verzije imaju
                # UnitOfInformation.MEGABYTES, starije UnitOfDataSize.MEGABYTES — literal
                # radi na objema bez uvjetnog uvoza.
                return "MB"
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        number = self._number or {}
        attrs: dict[str, Any] = {
            "msisdn": self._msisdn,
            # Kojoj značajki senzor pripada (status | prepaid | usage | valid_until | options).
            # Korisno za template kartice i automatizacije koje ne žele pisati entity ID-eve.
            "feature": self._feature,
            "status": number.get("status"),
            "tarifa": number.get("tariff"),
        }
        if number.get("options"):
            attrs["aktivne_opcije"] = [
                {"naziv": option.get("name"), "vrijedi_do": option.get("valid_until")}
                for option in number["options"]
            ]
        if self._feature == "prepaid":
            attrs["vrijedi_do"] = number.get("valid_until")
        if (usage := number.get("usage")) and self._feature == "usage":
            attrs["data_remaining_mb"] = usage.get("data_remaining_mb")
        return attrs
