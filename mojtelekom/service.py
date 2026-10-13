"""Service sloj: dohvat + TTL cache + filtriranje po značajkama.

Cache ima smisla samo kod dugoživućeg procesa (API/WebUI) — CLI se izvršava jednom."""
from __future__ import annotations

import time

from .adapters import fetch_for
from .config import Settings
from .core import NumberInfo, filter_features


class Service:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._cache: list[NumberInfo] | None = None
        self._fetched = 0.0

    async def snapshot(self) -> list[NumberInfo]:
        stale = time.monotonic() - self._fetched > self.settings.ttl_seconds
        if self._cache is None or stale:
            self._cache = await fetch_for(self.settings)
            self._fetched = time.monotonic()
        return [self._filter(n) for n in self._cache]

    def _filter(self, n: NumberInfo) -> NumberInfo:
        return filter_features(n, self.settings.features)
