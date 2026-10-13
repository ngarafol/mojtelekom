"""CLI: `mojtelekom status` (jednokratni ispis) i `mojtelekom serve` (API + WebUI)."""
from __future__ import annotations

import argparse
import asyncio


def main() -> None:
    p = argparse.ArgumentParser(prog="mojtelekom", description="Checker stanja brojeva iz Moj Telekom aplikacije")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="Ispiši stanje svih brojeva")
    sp = sub.add_parser("serve", help="Pokreni REST API + WebUI")
    sp.add_argument("--host", default="127.0.0.1")
    sp.add_argument("--port", type=int, default=8088)
    dp = sub.add_parser("dump", help="Spremi HTML stranice portala u mt-debug/ (pregled što portal vraća)")
    dp.add_argument("paths", nargs="*", help="dodatne putanje portala, npr. /korisnik/uredjivanje-usluga")
    args = p.parse_args()

    from .config import Settings
    settings = Settings.from_env()

    if args.cmd == "status":
        from .service import Service
        for n in asyncio.run(Service(settings).snapshot()):
            cols = [n.msisdn, n.alias or n.tariff or "-", n.status]
            if n.prepaid is not None:
                cols.append(f"{n.prepaid.balance:.2f} {n.prepaid.currency}")
                if n.prepaid.valid_until:
                    cols.append(f"vrijedi do {n.prepaid.valid_until:%d.%m.%Y}")
            if n.usage is not None and n.usage.data_remaining_mb is not None:
                cols.append(f"preostalo {n.usage.data_remaining_mb:.1f} MB")
            if n.options:
                cols.append(
                    "opcije: " + ", ".join(
                        o.name + (f" (do {o.valid_until:%d.%m.%Y})" if o.valid_until else "")
                        for o in n.options
                    )
                )
            print(" | ".join(cols))
    elif args.cmd == "dump":
        if not (settings.username and settings.password):
            print("Za dump treba MT_USERNAME i MT_PASSWORD.")
            raise SystemExit(1)
        asyncio.run(_dump_pages(settings, args.paths))
    else:
        import uvicorn
        uvicorn.run("mojtelekom.app:create_app", factory=True, host=args.host, port=args.port)


async def _dump_pages(settings, extra_paths: list[str]) -> None:
    """Popis stranica po usluzi — za razvoj parsera kad portal nešto promijeni."""
    from uuid import uuid4

    from .core import PortalClient

    async with PortalClient(settings.username, settings.password, debug=True) as client:
        paths = ["/"]
        for ref in await client.services():
            sid = ref.service_id
            paths += [
                f"/moredata/?serviceType={ref.service_type}&ajaxrequest=true&serviceId={sid}&ajaxRequestId={uuid4()}",
                f"/korisnici-bonova/stanje-racuna?serviceid={sid}",
                f"/korisnici-bonova/opcije?serviceid={sid}",
                f"/korisnici-bonova/tarifa?serviceid={sid}",
            ]
        paths += extra_paths
        for path in paths:
            text = await client.raw(path)
            print(f"{len(text):7d} B  {path}")


if __name__ == "__main__":
    main()
