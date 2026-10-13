"""Test zajedničkog core-a: fetch_numbers + filteriranje + JSON oblik za HA atribute."""
import asyncio
from datetime import date

from mojtelekom.core import Option, fetch_numbers, normalize_features, to_dict
from mojtelekom.core.portal import ServiceRef, parse_service_data
from tests.test_portal_parsing import MOREDATA


class FakeClient:
    """Lažni klijent portala — parsiranje na stvarnom markupu, bez mreže."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def services(self) -> list[ServiceRef]:
        # Dialup nema broj u fragmentu, pa se mora preskočiti.
        return [ServiceRef("MobilePrepaid", "20362835"), ServiceRef("Dialup", "18425796")]

    async def service(self, service_type: str, service_id: str):
        self.calls.append(("service", service_type, service_id))
        return parse_service_data(MOREDATA) if service_type == "MobilePrepaid" else None

    async def account(self, service_id: str):
        self.calls.append(("account", service_id))
        return 52440.43, date(2026, 12, 31)

    async def options(self, service_id: str):
        self.calls.append(("options", service_id))
        return [Option("Internet Tjedan")]


def test_fetch_numbers_builds_full_model():
    numbers = asyncio.run(fetch_numbers(FakeClient(), ["status", "prepaid", "usage", "options"]))

    assert len(numbers) == 1  # Dialup preskočen
    number = numbers[0]
    assert number.msisdn == "385991234567"
    assert number.tariff == "Simpa"
    assert number.status == "active"
    assert number.prepaid.balance == 3.62
    assert number.prepaid.currency == "EUR"
    assert number.prepaid.valid_until == date(2026, 12, 31)
    assert number.usage.data_remaining_mb == 52440.43
    assert [option.name for option in number.options] == ["Internet Tjedan"]


def test_fetch_numbers_skips_disabled_features_at_source():
    client = FakeClient()
    numbers = asyncio.run(fetch_numbers(client, ["status"]))

    assert numbers[0].prepaid is None and numbers[0].usage is None and numbers[0].options == []
    # account/options se ni ne dohvaćaju kad su značajke isključene
    assert {call[0] for call in client.calls} == {"service"}


def test_to_dict_is_json_ready_for_ha_attributes():
    numbers = asyncio.run(fetch_numbers(FakeClient(), ["status", "prepaid", "options"]))
    data = to_dict(numbers[0])

    assert data["prepaid"]["valid_until"] == "2026-12-31"  # datum kao ISO string
    assert data["options"] == [{"name": "Internet Tjedan", "valid_until": None}]
    assert isinstance(data["fetched_at"], str)


def test_normalize_features_keeps_status_and_drops_unknown():
    # Prazan odabir u HA opcijama ne smije ostaviti integraciju bez entiteta.
    assert normalize_features([]) == ["status"]
    assert normalize_features(None) == ["status"]
    assert normalize_features(["options"]) == ["options", "status"]
    assert normalize_features(["prepaid", "nepoznato"]) == ["prepaid", "status"]
