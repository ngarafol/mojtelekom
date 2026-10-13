# GENERIRANO iz mojtelekom/core/credentials.py — ne uređivati; pokreni scripts/sync_core.py
"""Vjerodajnice za portal: iz config entryja (HA) ili iz okoline.

Rezerva iz okoline (`MT_USERNAME` / `MT_PASSWORD`) omogućuje da lozinka u Home Assistantu
**ne bude spremljena** u `.storage/core.config_entries` — koji HA drži u čistom tekstu i
uključuje u backupe — nego da dođe iz okoline procesa (HA Container / HA Core).

Napomena: varijable okoline nisu tajna pohrana; vidljive su korisniku koji vrti proces
(`docker inspect`, `/proc/<pid>/environ`). Bolje od čistog teksta u backupu, ali nije čarolija.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

ENV_USERNAME = "MT_USERNAME"
ENV_PASSWORD = "MT_PASSWORD"


def resolve_credentials(
    data: Mapping[str, Any],
    *,
    username_key: str = "username",
    password_key: str = "password",
) -> tuple[str, str] | None:
    """Vrati (korisnik, lozinka) ili None ako nešto nedostaje.

    Vrijednost iz config entryja ima prednost; ako je nema, gleda se okolina.
    """
    username = str(data.get(username_key) or "").strip() or os.environ.get(ENV_USERNAME, "").strip()
    password = str(data.get(password_key) or "") or os.environ.get(ENV_PASSWORD, "")
    if not username or not password:
        return None
    return username, password
