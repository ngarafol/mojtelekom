"""Vjerodajnice: config entry ima prednost, okolina je rezerva (da tajna ne ide u .storage)."""
from __future__ import annotations

from mojtelekom.core import ENV_PASSWORD, ENV_USERNAME, resolve_credentials


def test_uses_values_from_config_entry(monkeypatch):
    monkeypatch.setenv(ENV_USERNAME, "iz-okoline")
    monkeypatch.setenv(ENV_PASSWORD, "iz-okoline")
    assert resolve_credentials({"username": "upisano", "password": "tajna"}) == ("upisano", "tajna")


def test_falls_back_to_environment(monkeypatch):
    monkeypatch.setenv(ENV_USERNAME, "korisnik")
    monkeypatch.setenv(ENV_PASSWORD, "tajna-iz-okoline")
    # Lozinka nije upisana u integraciju -> dolazi iz okoline, u .storage nema tajne.
    assert resolve_credentials({"username": "korisnik"}) == ("korisnik", "tajna-iz-okoline")


def test_missing_pieces_return_none(monkeypatch):
    monkeypatch.delenv(ENV_USERNAME, raising=False)
    monkeypatch.delenv(ENV_PASSWORD, raising=False)
    assert resolve_credentials({}) is None
    assert resolve_credentials({"username": "samo-korisnik"}) is None
    assert resolve_credentials({"password": "samo-lozinka"}) is None


def test_blank_values_are_not_credentials(monkeypatch):
    monkeypatch.delenv(ENV_USERNAME, raising=False)
    monkeypatch.delenv(ENV_PASSWORD, raising=False)
    assert resolve_credentials({"username": "   ", "password": "  "}) is None
