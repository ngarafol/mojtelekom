"""Dohvat stanja brojeva, ovisno o `MT_ADAPTER` (mock | portal).

Sav pravi posao je u `core.fetch_numbers` — isti kod koristi i HA integracija.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from .config import Settings
from .core import NumberInfo, Option, PortalClient, Prepaid, Usage, fetch_numbers


def _mock_numbers() -> list[NumberInfo]:
    """Lažni podaci za razvoj bez računa."""
    now = datetime.now(timezone.utc)
    return [
        NumberInfo(
            msisdn="385911234567",
            alias="Osobni",
            status="active",
            options=[Option(name="Internet Tjedan", valid_until=date(2026, 11, 5))],
            valid_until=(now + timedelta(days=45)).date(),
            prepaid=Prepaid(balance=12.34),
            usage=Usage(data_remaining_mb=2040),
            fetched_at=now,
        ),
        NumberInfo(
            msisdn="385921234567",
            alias="Posao",
            status="active",
            valid_until=(now + timedelta(days=3)).date(),
            prepaid=Prepaid(balance=0.87),
            usage=Usage(data_remaining_mb=4608),
            fetched_at=now,
        ),
        NumberInfo(
            msisdn="385951234567",
            alias="Djed",
            status="blocked",
            prepaid=Prepaid(balance=0.0),
            fetched_at=now,
        ),
    ]


async def fetch_for(settings: Settings) -> list[NumberInfo]:
    """Vrati brojeve prema konfiguraciji. Portal vraća samo aktivne usluge."""
    match settings.adapter:
        case "mock":
            return _mock_numbers()
        case "portal":
            if not (settings.username and settings.password):
                raise RuntimeError("Za MT_ADAPTER=portal postavi MT_USERNAME i MT_PASSWORD.")
            async with PortalClient(settings.username, settings.password) as client:
                return await fetch_numbers(client, settings.features)
        case other:
            raise ValueError(f"Nepoznat adapter: {other} (mock | portal)")
