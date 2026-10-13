"""Adapteri prema Moj Telekom backendu.

Adapter vraća sve što zna za svaki broj; Service filtrira po uključenim značajkama.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from .config import Settings
from .core import FEATURES, Invoice, NumberInfo, Option, PortalClient, Prepaid, Usage, fetch_numbers


class Adapter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch(self) -> list[NumberInfo]:
        raise NotImplementedError


class MockAdapter(Adapter):
    """Deterministični lažni podaci — za razvoj API-ja, WebUI-ja i HA integracije
    dok nemamo snimku pravog API-ja."""

    async def fetch(self) -> list[NumberInfo]:
        now = datetime.now(timezone.utc)
        return [
            NumberInfo(
                msisdn="385911234567",
                alias="Osobni",
                status="active",
                options=[Option(name="Internet Tjedan", valid_until=date(2026, 11, 5))],
                prepaid=Prepaid(balance=12.34, valid_until=(now + timedelta(days=45)).date()),
                usage=Usage(data_used_mb=8200, data_total_mb=10240, minutes_used=140, minutes_total=1000, sms_used=32, sms_total=100),
                invoice=Invoice(amount_due=0, status="paid"),
                fetched_at=now,
            ),
            NumberInfo(
                msisdn="385921234567",
                alias="Posao",
                status="active",
                prepaid=Prepaid(balance=0.87, valid_until=(now + timedelta(days=3)).date()),
                usage=Usage(data_used_mb=512, data_total_mb=5120, minutes_used=10, minutes_total=200),
                invoice=Invoice(amount_due=17.49, status="due", due_date=(now + timedelta(days=12)).date()),
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


class PortalAdapter(Adapter):
    """Čita podatke s Moj Telekom web portala (Keycloak prijava + HTML fragmenti).

    Sav posao (prijava, dohvat, filtriranje značajki) je u `core.fetch_numbers` — isti
    kod koristi i HA integracija, pa se održava na jednom mjestu.
    """

    async def fetch(self) -> list[NumberInfo]:
        if not (self.settings.username and self.settings.password):
            raise RuntimeError("Za MT_ADAPTER=portal postavi MT_USERNAME i MT_PASSWORD.")
        async with PortalClient(self.settings.username, self.settings.password) as client:
            return await fetch_numbers(client, self.settings.features)


class RealAdapter(Adapter):
    """Neslužbeni klijent za Moj Telekom mobilnu aplikaciju.

    Za implementaciju treba presretan HTTPS promet aplikacije (mitmproxy/HAR), iz kojeg se
    čitaju: 1) login/token endpoint, 2) endpoint s popisom brojeva, 3) endpoint sa stanjem
    i potrošnjom. Mapiranje odgovora u modele piše se ovdje — koraci u README.md.
    """

    async def fetch(self) -> list[NumberInfo]:
        raise NotImplementedError(
            "RealAdapter još nije implementiran — potrebna HAR snimka Moj Telekom aplikacije, vidi README.md."
        )


def get_adapter(settings: Settings) -> Adapter:
    match settings.adapter:
        case "mock":
            return MockAdapter(settings)
        case "portal":
            return PortalAdapter(settings)
        case "real":
            return RealAdapter(settings)
        case other:
            raise ValueError(f"Nepoznat adapter: {other} (mock | portal | real)")
