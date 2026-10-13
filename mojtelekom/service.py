"""Service sloj: dohvat preko adaptera + TTL cache + filtriranje po značajkama."""
from __future__ import annotations

import time

from .adapters import get_adapter
from .config import Settings
from .core import NumberInfo, filter_features


class Service:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.adapter = get_adapter(settings)
        self._cache: list[NumberInfo] | None = None
        self._fetched = 0.0

    async def snapshot(self, refresh: bool = False) -> list[NumberInfo]:
        stale = time.monotonic() - self._fetched > self.settings.ttl_seconds
        if refresh or self._cache is None or stale:
            self._cache = await self.adapter.fetch()
            self._fetched = time.monotonic()
        return [self._filter(n) for n in self._cache]

    def _filter(self, n: NumberInfo) -> NumberInfo:
        return filter_features(n, self.settings.features)
