#!/usr/bin/env python3
"""Generira `custom_components/moj_telekom/core/` iz `mojtelekom/core/`.

Zašto kopija: HA integracija mora biti samostalna (HACS kopira samo mapu
`custom_components/moj_telekom`), a core se drži na jednom mjestu u paketu.

Test `tests/test_core_sync.py` pada ako kopija zaostane, pa se drift ne može prošvercati.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "mojtelekom" / "core"
DST = ROOT / "custom_components" / "moj_telekom" / "core"
HEADER = "# GENERIRANO iz mojtelekom/core/{name} — ne uređivati; pokreni scripts/sync_core.py\n"


def render(name: str, text: str) -> str:
    return HEADER.format(name=name) + text


def main() -> int:
    DST.mkdir(parents=True, exist_ok=True)
    changed = 0
    for source in sorted(SRC.glob("*.py")):
        target = DST / source.name
        content = render(source.name, source.read_text(encoding="utf-8"))
        if not target.exists() or target.read_text(encoding="utf-8") != content:
            target.write_text(content, encoding="utf-8")
            print(f"  ažurirano: {target.relative_to(ROOT)}")
            changed += 1
    print(f"core: {changed} datoteka ažurirano" if changed else "core: već u sinkronizaciji")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
