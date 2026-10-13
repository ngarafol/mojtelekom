# GENERIRANO iz mojtelekom/core/fetch.py — ne uređivati; pokreni scripts/sync_core.py
"""Zajednički dohvat: od prijave na portal do gotovih brojeva.

Isti put koriste CLI/API (preko adaptera) i HA integracija (preko koordinatora), pa
se logika "što se dohvaća po kojem broju" održava na jednom mjestu.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from .models import FEATURES, NumberInfo, Prepaid, Usage, filter_features
from .portal import PortalClient


async def fetch_numbers(client: PortalClient, features: Iterable[str] = FEATURES) -> list[NumberInfo]:
    """Vrati stanje svih usluga koje klijent vidi.

    Portal prikazuje samo aktivne usluge (blokade se ovdje ne vide), a usluge bez broja
    (npr. Dialup) se preskaču jer se ne uklapaju u model.
    """
    now = datetime.now(timezone.utc)
    wanted = set(features)
    numbers: list[NumberInfo] = []

    for ref in await client.services():
        data = await client.service(ref.service_type, ref.service_id)
        if data is None:
            continue

        prepaid = usage = None
        valid_until = None
        if ref.service_type == "MobilePrepaid":
            # Stranica stanja daje preostale MB i "vrijedi do", pa je tražimo samo ako je
            # barem jedna od tih značajki uključena (inače je čisti gubitak).
            free_mb = None
            if wanted & {"prepaid", "usage", "valid_until"}:
                free_mb, valid_until = await client.account(ref.service_id)
            usage = Usage(data_remaining_mb=free_mb)
            if data.balance is not None:
                prepaid = Prepaid(balance=data.balance, currency=data.currency)
        elif data.balance is not None:
            prepaid = Prepaid(balance=data.balance, currency=data.currency)

        numbers.append(
            NumberInfo(
                msisdn=data.msisdn,
                status="active",
                fetched_at=now,
                tariff=data.tariff,
                valid_until=valid_until,
                # Opcije tražimo samo ako su uključene — štedi jedan request po broju.
                options=await client.options(ref.service_id) if "options" in wanted else [],
                prepaid=prepaid,
                usage=usage,
            )
        )

    return [filter_features(number, wanted) for number in numbers]
