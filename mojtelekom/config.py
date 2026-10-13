"""Konfiguracija isključivo iz env varijabla (jednostavno za Docker/HA/systemd)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from .core import FEATURES  # jedan izvor istine za značajke


@dataclass
class Settings:
    adapter: str = "mock"  # mock | real
    features: list[str] = field(default_factory=lambda: list(FEATURES))
    ttl_seconds: int = 60
    api_key: str | None = None
    username: str | None = None
    password: str | None = None

    @classmethod
    def from_env(cls) -> Settings:
        feats = [f.strip() for f in os.getenv("MT_FEATURES", "").split(",") if f.strip()]
        unknown = [f for f in feats if f not in FEATURES]
        if unknown:
            raise ValueError(f"Nepoznate značajke: {', '.join(unknown)} (dozvoljene: {', '.join(FEATURES)})")
        return cls(
            adapter=os.getenv("MT_ADAPTER", "mock"),
            features=feats or list(FEATURES),
            ttl_seconds=int(os.getenv("MT_TTL", "60")),
            api_key=os.getenv("MT_API_KEY") or None,
            username=os.getenv("MT_USERNAME") or None,
            password=os.getenv("MT_PASSWORD") or None,
        )
