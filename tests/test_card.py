"""Test kartice koja se isporučuje s integracijom.

Logika kartice je JavaScript, pa je pokrećemo u node-u (test preskače ako node nema).
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
INTEGRATION = ROOT / "custom_components" / "moj_telekom"


def test_card_file_exists_and_is_served():
    """__init__.py mora posluživati točno onu putanju na kojoj kartica stvarno jest."""
    card = INTEGRATION / "www" / "moj-telekom-card.js"
    assert card.is_file(), "kartica nedostaje"
    init = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
    assert 'CARD_URL = "/moj_telekom/moj-telekom-card.js"' in init
    assert 'Path(__file__).parent / "www" / "moj-telekom-card.js"' in init
    assert "add_extra_js_url(hass, CARD_URL)" in init


def test_manifest_declares_frontend_dependency():
    manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))
    assert "frontend" in manifest.get("dependencies", []), "bez toga add_extra_js_url ne radi"


@pytest.mark.skipif(shutil.which("node") is None, reason="node nije instaliran")
def test_card_logic_in_node():
    result = subprocess.run(
        ["node", str(ROOT / "tests" / "card_check.mjs")],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
