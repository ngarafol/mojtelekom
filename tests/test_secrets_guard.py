"""Čuvari da tajne ne cure: u log/ispis/dump i iz dijagnostike.

Testira se statički (AST), jer HA nije instaliran u ovom venv-u.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = [
    ROOT / "mojtelekom" / "core" / "portal.py",
    ROOT / "mojtelekom" / "core" / "credentials.py",
    ROOT / "mojtelekom" / "cli.py",
    *sorted((ROOT / "custom_components" / "moj_telekom").glob("*.py")),
]
DIAGNOSTICS = ROOT / "custom_components" / "moj_telekom" / "diagnostics.py"

# Funkcije koje završe u logu, na stdoutu ili u debug dumpu.
LOG_FUNCTION_NAMES = {
    "print", "_note", "debug", "info", "warning", "error", "exception", "critical", "log",
}


def _log_calls(tree: ast.AST) -> list[ast.Call]:
    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = getattr(func, "id", None) or getattr(func, "attr", None)
        if name in LOG_FUNCTION_NAMES:
            calls.append(node)
    return calls


def _interpolated_names(call: ast.Call) -> set[str]:
    """Imena koja se stvarno ubacuju u string (f-string), ne puki tekst poruke."""
    found: set[str] = set()
    for node in ast.walk(call):
        if isinstance(node, ast.FormattedValue):
            for inner in ast.walk(node.value):
                if isinstance(inner, ast.Name):
                    found.add(inner.id)
                elif isinstance(inner, ast.Attribute):
                    found.add(inner.attr)
    return found


def test_secrets_never_reach_logs_or_prints():
    for path in SOURCES:
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
        for call in _log_calls(tree):
            leaked = {name for name in _interpolated_names(call) if "password" in name.lower()}
            assert not leaked, f"{path.name}: lozinka ide u log/ispis (linija {call.lineno}): {leaked}"


def test_debug_dump_logs_field_names_not_values():
    source = (ROOT / "mojtelekom" / "core" / "portal.py").read_text(encoding="utf-8")
    # U dumpu smiju biti samo imena polja, i to prije nego se vjerodajnice dodaju u payload.
    assert "sorted(payload)" in source
    before, after = source.split("payload.update(")
    assert "polja {sorted(payload)}" in before, "dump mora zabilježiti polja prije dodavanja vjerodajnica"


def test_diagnostics_redacts_credentials():
    source = DIAGNOSTICS.read_text(encoding="utf-8")
    assert "async_redact_data" in source
    assert "TO_REDACT = {CONF_USERNAME, CONF_PASSWORD}" in source
    assert "_mask(" in source, "brojevi se maskiraju prije nego odu u dijagnostiku"
