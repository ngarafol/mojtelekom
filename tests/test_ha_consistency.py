"""Konzistentnost core značajki i HA platforme senzora.

Ovaj test bi uhvatio bug koji je rušio cijelu platformu senzora:
značajka postoji u `core.FEATURES` (i nudi se u opcijama), ali nema unos u `FEATURE_META`
→ `KeyError` u `MojTelekomSensor.__init__` i niti jedan entitet se ne stvori.
"""
from __future__ import annotations

import ast
from pathlib import Path

from mojtelekom.core import FEATURES

SENSOR_PY = (
    Path(__file__).resolve().parent.parent / "custom_components" / "moj_telekom" / "sensor.py"
)

# Značajke koje SVJESNO nemaju svoj senzor — dolaze kao atributi na ostalim senzorima.
ATTRIBUTE_ONLY = {"options"}


def _module() -> ast.Module:
    return ast.parse(SENSOR_PY.read_text(encoding="utf-8"), str(SENSOR_PY))


def _feature_meta_keys() -> set[str]:
    for node in ast.walk(_module()):
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == "FEATURE_META":
            return {ast.literal_eval(key) for key in node.value.keys}
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == "FEATURE_META":
            return {ast.literal_eval(key) for key in node.value.keys}
    raise AssertionError("FEATURE_META nije nađen u sensor.py")


def test_every_core_feature_is_either_sensor_or_explicitly_attribute_only():
    meta = _feature_meta_keys()
    assert meta <= set(FEATURES), f"FEATURE_META ima značajke kojih nema u core.FEATURES: {meta - set(FEATURES)}"
    unhandled = set(FEATURES) - meta - ATTRIBUTE_ONLY
    assert not unhandled, (
        f"Značajke bez senzora i bez izuzeća: {sorted(unhandled)}. "
        "Dodaj ih u FEATURE_META ili u ATTRIBUTE_ONLY ako dolaze samo kao atributi."
    )


def test_entities_are_created_only_for_sensor_features():
    """Platforma mora filtrirati značajke prije nego indeksira FEATURE_META."""
    calls = [
        node
        for node in ast.walk(_module())
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "async_add_entities"
    ]
    assert calls, "nema async_add_entities u sensor.py"
    uses_filtered = [
        node
        for node in ast.walk(calls[0])
        if isinstance(node, ast.Name) and node.id == "sensor_features"
    ]
    assert uses_filtered, "entiteti se moraju stvarati samo za `sensor_features`, ne za sve značajke"


def test_sensors_expose_feature_attribute():
    """Kartica i README templatei pronalaze senzore po atributu `feature` — ne mijenjaj to bez ažuriranja oboje."""
    source = SENSOR_PY.read_text(encoding="utf-8")
    assert '"feature": self._feature' in source


def test_entity_ids_get_mojtelekom_prefix():
    """Prefiks omogućuje filtriranje i kartice tipa entity_id: "*mojtelekom*"."""
    source = SENSOR_PY.read_text(encoding="utf-8")
    assert "def suggested_object_id" in source
    assert 'return f"mojtelekom_{self._msisdn}_{self._feature}"' in source
    assert "national_number(" in source  # ime uređaja: "Moj Telekom 099 8331732"
