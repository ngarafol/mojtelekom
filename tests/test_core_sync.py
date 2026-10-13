"""HA integracija sadrži generiranu kopiju core-a; ovdje se čuva da ne zaostane.

Home Assistant nije instaliran u ovom venv-u, pa se HA datoteke provjeravaju sintaksno —
dublju provjeru radi sam HA pri učitavanju integracije.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "mojtelekom" / "core"
DST = ROOT / "custom_components" / "moj_telekom" / "core"
HEADER = "# GENERIRANO iz mojtelekom/core/{name} — ne uređivati; pokreni scripts/sync_core.py\n"


def test_vendored_core_is_in_sync():
    src_files = sorted(path.name for path in SRC.glob("*.py"))
    dst_files = sorted(path.name for path in DST.glob("*.py"))
    assert src_files == dst_files, "skup datoteka se razlikuje — pokreni scripts/sync_core.py"
    for name in src_files:
        expected = HEADER.format(name=name) + (SRC / name).read_text(encoding="utf-8")
        actual = (DST / name).read_text(encoding="utf-8")
        assert actual == expected, f"{name} zaostaje — pokreni scripts/sync_core.py"


def test_ha_integration_files_compile():
    files = sorted((ROOT / "custom_components" / "moj_telekom").rglob("*.py"))
    assert files, "nema HA datoteka"
    for path in files:
        compile(path.read_text(encoding="utf-8"), str(path), "exec")


def test_core_has_no_home_assistant_or_pydantic_imports():
    """Core mora ostati bez HA i pydantica — inače ga HA (ili CLI) ne može učitati."""
    for path in sorted(SRC.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            for module in modules:
                assert not module.startswith(("homeassistant", "pydantic")), f"{path.name}: {module}"
