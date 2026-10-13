"""HTTP API + WebUI. Pokretanje: `mojtelekom serve` (vidi cli.py)."""
from __future__ import annotations

from importlib import resources
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles

from .config import Settings
from .core import NumberInfo
from .service import Service


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    service = Service(settings)
    app = FastAPI(title="Moj Telekom checker", version="0.1.0")

    async def verify_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
        if settings.api_key and x_api_key != settings.api_key:
            raise HTTPException(status_code=401, detail="Nedostaje ili je neispravan X-API-Key")

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"ok": True, "adapter": settings.adapter, "features": settings.features}

    @app.get("/api/numbers", dependencies=[Depends(verify_key)])
    async def numbers(refresh: bool = False) -> list[NumberInfo]:
        return await service.snapshot(refresh)

    @app.get("/api/numbers/{msisdn}", dependencies=[Depends(verify_key)])
    async def number(msisdn: str, refresh: bool = False) -> NumberInfo:
        # radi i s trunk nulom: "0921234567" i "921234567" pogađaju "385921234567"
        wanted = msisdn.lstrip("+").lstrip("0")
        for n in await service.snapshot(refresh):
            if n.msisdn.endswith(wanted):
                return n
        raise HTTPException(status_code=404, detail="Broj nije nađen")

    web = resources.files(__package__).joinpath("web")
    app.mount("/", StaticFiles(directory=web, html=True))  # type: ignore[arg-type]
    return app
