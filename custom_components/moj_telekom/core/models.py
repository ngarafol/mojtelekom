# GENERIRANO iz mojtelekom/core/models.py — ne uređivati; pokreni scripts/sync_core.py
"""Podatkovni modeli i značajke.

Namjerno obični dataclassovi (bez pydantica) i bez ijednog HA uvoza: isti kod koriste
CLI/API i Home Assistant integracija, a HA nema pydantic u osnovnim ovisnostima.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime

FEATURES = ("status", "prepaid", "usage", "valid_until", "options")


@dataclass
class Prepaid:
    balance: float
    currency: str = "EUR"


@dataclass
class Usage:
    # Portal daje samo preostale "besplatne MB"; minute/SMS za Simpa brojeve piše "Nema podataka".
    data_remaining_mb: float | None = None


@dataclass
class Option:
    """Aktivna opcija/dodatak i rok ako ga portal navede (zasad ga ne navodi)."""

    name: str
    valid_until: date | None = None


@dataclass
class NumberInfo:
    """Stanje jednog broja. Isključene značajke budu None / prazna lista (vidi filter_features)."""

    msisdn: str
    status: str  # active | blocked | expired | unknown
    fetched_at: datetime
    alias: str | None = None
    tariff: str | None = None
    # "SIM kartica / bon vrijedi do" — datum do kojeg je broj aktivan.
    valid_until: date | None = None
    options: list[Option] = field(default_factory=list)
    prepaid: Prepaid | None = None
    usage: Usage | None = None


def filter_features(number: NumberInfo, features: Iterable[str]) -> NumberInfo:
    """Zadrži samo uključene značajke (status je uvijek prisutan)."""
    wanted = set(features)
    return replace(
        number,
        valid_until=number.valid_until if "valid_until" in wanted else None,
        prepaid=number.prepaid if "prepaid" in wanted else None,
        usage=number.usage if "usage" in wanted else None,
        options=number.options if "options" in wanted else [],
    )


def normalize_features(features: Iterable[str] | None) -> list[str]:
    """Očisti popis značajki i osiguraj da `status` uvijek ostane.

    Prazan odabir u HA opcijama (npr. slučajno odznačeno sve) inače ostavi integraciju
    bez ijednog entiteta — tiho i zbunjujuće.
    """
    wanted = [feature for feature in (features or []) if feature in FEATURES]
    if "status" not in wanted:
        wanted.append("status")
    return wanted


def _jsonable(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def to_dict(number: NumberInfo) -> dict:
    """Rječnik spreman za JSON i za HA atribute (datumi kao ISO stringovi)."""
    return _jsonable(asdict(number))
