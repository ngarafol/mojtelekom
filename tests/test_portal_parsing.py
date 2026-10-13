"""Testovi parsiranja portala — bez mreže, na sintetičkim fragmentima iste strukture
kao pravi odgovori portala (bez stvarnih brojeva i podataka korisnika)."""
import asyncio
from datetime import date, datetime, timezone

import pytest

from mojtelekom.adapters import PortalAdapter
from mojtelekom.config import Settings
from mojtelekom.core.portal import (
    _blocker,
    _feedback,
    parse_account,
    parse_form,
    parse_msisdn,
    parse_options,
    parse_service_data,
    parse_services,
)

HOME = """
<ul>
  <li class="box"><img src="/WebResources/css/i/preloader.gif">
    <div class="moreData" style="display:none;">serviceType=MobilePrepaid&amp;ajaxrequest=true&amp;serviceId=20506172</div></li>
  <li class="box"><img src="/WebResources/css/i/preloader.gif">
    <div class="moreData" style="display:none;">serviceType=MobilePrepaid&amp;ajaxrequest=true&amp;serviceId=20362835</div></li>
  <li class="box"><img src="/WebResources/css/i/preloader.gif">
    <div class="moreData" style="display:none;">serviceType=Dialup&amp;ajaxrequest=true&amp;serviceId=20506172</div></li>
</ul>
"""

MOREDATA = """
<a href="javascript:PerformRefresh('tok123');" class="refresh" title="Osvjezite podatke"></a><dl>
  <dt><a href="/korisnici-bonova/stanje-racuna?serviceid=20506172">099 1234567</a></dt>
  <dd class="package-status"><table><thead><tr>
      <th class="align-left" scope="col">Tarifa za korisnike bonova: Simpa<br><a href="/korisnici-bonova/tarifa?serviceid=20506172">
                    Promijenite tarifu
                  </a></th>
      <th class="align-right" scope="col"></th>
  </tr></thead><tbody></tbody></table></dd>
  <dd class="billing-status"><table>
      <tr><th>Stanje bona:</th><td>3,62 EUR</td></tr>
      <tr><th>Stanje bonus racuna:</th><td>
                        Nema podataka
                      </td></tr>
  </table></dd>
</dl>
"""

MOREDATA_NO_BALANCE = """
<dt><a href="/korisnici-bonova/pregled?serviceid=999">099 7654321</a></dt>
<dd><table><tr><th>Stanje bona:</th><td>Nema podataka</td></tr></table></dd>
"""

ACCOUNT = """
<table><tbody>
  <tr><th scope="row">Besplatne SMS poruke unutar HT mreze:</th><td class="align-right">Nema podataka</td></tr>
  <tr><th scope="row">Besplatno MB podatkovnog prometa:</th><td class="align-right">164234,4</td></tr>
  <tr><th scope="row">SIM kartica vrijedi do:</th><td class="align-right">10. 01. 2027.</td></tr>
</tbody></table>
"""


def test_parse_services_deduplicates():
    refs = parse_services(HOME)
    assert [(r.service_type, r.service_id) for r in refs] == [
        ("MobilePrepaid", "20506172"),
        ("MobilePrepaid", "20362835"),
        ("Dialup", "20506172"),
    ]


def test_parse_service_data_extracts_balance_tariff_and_number():
    data = parse_service_data(MOREDATA)
    assert data is not None
    assert data.msisdn == "385991234567"  # '099 1234567' -> međunarodni oblik
    assert data.balance == 3.62  # hrvatski decimalni zarez
    assert data.currency == "EUR"
    assert data.tariff == "Simpa"  # ne smije uhvatiti i tekst linka "Promijenite tarifu"
    assert data.bonus is None  # "Nema podataka" -> None, ne 0


def test_parse_service_data_without_balance():
    data = parse_service_data(MOREDATA_NO_BALANCE)
    assert data is not None and data.balance is None


def test_parse_account_free_mb_and_sim_validity():
    free_mb, valid_until = parse_account(ACCOUNT)
    assert free_mb == 164234.4
    assert valid_until == date(2027, 1, 10)


def test_msisdn_normalisation():
    assert parse_msisdn("099 1234567") == "385991234567"
    assert parse_msisdn("+385 99 123 4567") == "385991234567"


def test_portal_adapter_requires_credentials():
    adapter = PortalAdapter(Settings(adapter="portal"))
    with pytest.raises(RuntimeError, match="MT_USERNAME"):
        asyncio.run(adapter.fetch())


# --- forme za prijavu (markup prema stvarnim odgovorima Keycloaka) ---

# OIDC form_post stranica (nakon uspješne prijave) piše atribute VELIKIM slovima.
FORM_POST = """<HTML><HEAD><TITLE>OIDC Form_Post Response</TITLE></HEAD>
<BODY Onload="document.forms[0].submit()">
<FORM METHOD="POST" ACTION="https://moj.hrvatskitelekom.hr/sso/challenge?callbackUrl=https%3a%2f%2fmoj.hrvatskitelekom.hr%3a443%2fpublic">
<INPUT TYPE="HIDDEN" NAME="state" VALUE="OpenIdConnect.AuthenticationProperties=abc.def" />
<INPUT TYPE="HIDDEN" NAME="code" VALUE="kod-123" />
</FORM></BODY></HTML>"""

LOGIN_FORM = """<form id="kc-form-login" action="https://sso.hrvatskitelekom.hr/auth/realms/HrvatskiTelekom/login-actions/authenticate?session_code=s1&amp;execution=e1&amp;client_id=moj.hrvatskitelekom.hr&amp;tab_id=t1" method="post">
<input id="username" name="username" type="text"><input name="password" type="password"></form>"""

LOGIN_ERROR = '<div id="kc-feedback-text" class="alert alert-error">Invalid username or password.</div>'


def test_parse_form_handles_uppercase_form_post_page():
    action, fields = parse_form(FORM_POST)
    assert action == "https://moj.hrvatskitelekom.hr/sso/challenge?callbackUrl=https%3a%2f%2fmoj.hrvatskitelekom.hr%3a443%2fpublic"
    assert fields["code"] == "kod-123"
    assert fields["state"].startswith("OpenIdConnect.AuthenticationProperties=")


def test_parse_form_handles_lowercase_login_form():
    action, fields = parse_form(LOGIN_FORM)
    assert action is not None and action.endswith("tab_id=t1")
    assert "&amp;" not in action  # HTML entiteti se raspetljaju
    # username/password nemaju value u formi — dodajemo ih sami
    assert "username" not in fields and "password" not in fields


def test_feedback_reads_keycloak_error():
    assert _feedback(LOGIN_ERROR) == "Invalid username or password."


def test_blocker_detects_2fa():
    assert _blocker('<input name="otp" type="text">') == "portal traži jednokratni kod (2FA)"
    assert _blocker(LOGIN_FORM) is None


# Javna stranica koju portal vrati kad sesija istekne (HTTP 200!) — na njoj se ne smije
# naći nijedan marker koji tražimo u _get(), inače bismo prazne podatke prijavili kao stvarne.
PUBLIC_PAGE = """<html><head><title>Moj Telekom Portal | Hrvatski Telekom</title></head><body>
<h1>Prijava jednokratnim PIN-om</h1><p>Upišite broj mobitela ili e-mail adresu...</p>
<a href="/public/telekom-id-prijava">Prijava Telekom ID podacima</a></body></html>"""


def test_expired_session_page_matches_no_expectation():
    assert "moreData" not in PUBLIC_PAGE  # provjera naslovnice
    assert "Stanje na računu" not in PUBLIC_PAGE  # provjera stranice stanja
    assert parse_services(PUBLIC_PAGE) == []  # ne izmišljamo usluge iz login stranice
    assert parse_account(PUBLIC_PAGE) == (None, None)  # ni prazne MB/datume


def test_fragments_carry_marker_used_by_guard():
    # _get() za pojedinu uslugu traži serviceId u fragmentu — mora ga stvarno sadržavati.
    assert "20506172" in MOREDATA
    assert "/korisnici-bonova/" in MOREDATA


# Katalog opcija: aktivna nosi DeactivateOption(...), neaktivna ActivateOption(...).
OPTIONS_PAGE = """
<ul class="lista-proizvoda">
  <li><dl><dt><h2 class="h2title">Internet Tjedan</h2></dt>
    <dd class="desc"><p>50% popusta!</p></dd>
    <dd class="status"><a href="javascript:DeactivateOption('tok1','tok2','tok3','tok4');">Deaktivirajte</a></dd>
  </dl></li>
  <li><dl><dt><h2 class="h2title">Simpa S</h2></dt>
    <dd class="desc"><p>7 GB</p></dd>
    <dd class="status"><a href="javascript:ActivateOption('tok1','tok2');">Aktivirajte</a></dd>
  </dl></li>
  <li><dl><dt><h2 class="h2title">Travel &amp; Surf</h2></dt>
    <dd class="status"><a href="javascript:ActivateOption('tok3','tok4');">Aktivirajte</a></dd>
  </dl></li>
</ul>
<script>function DeactivateOption(a,b,c,d){ /* definicija, ne opcija */ }</script>
"""


def test_parse_options_returns_only_active():
    options = parse_options(OPTIONS_PAGE)
    assert [o.name for o in options] == ["Internet Tjedan"]  # ne Simpa S / Travel
    assert options[0].valid_until is None  # portal zasad ne prikazuje rok za opcije


def test_parse_options_picks_up_date_if_present():
    # Ako HT jednom doda rok u blok opcije, parser ga pokupi (valid_until je pripremljen).
    page = OPTIONS_PAGE.replace("50% popusta!", "Vrijedi do: 30.11.2026.")
    assert parse_options(page)[0].valid_until == date(2026, 11, 30)


def test_parse_options_ignores_javascript_definitions():
    # Na stranicama bez kataloga (npr. Dialup) DeactivateOption postoji samo u <script>.
    page = "<script>function DeactivateOption(a,b){}</script>DeactivateOption('x','y','z','w')"
    assert parse_options(page) == []


def test_options_feature_toggle():
    from mojtelekom.core import NumberInfo, Option
    from mojtelekom.service import Service

    number = NumberInfo(
        msisdn="385991234567", status="active", options=[Option(name="Internet Tjedan")],
        fetched_at=datetime.now(timezone.utc),
    )
    assert Service(Settings(adapter="mock", features=["status"]))._filter(number).options == []
    assert Service(Settings(adapter="mock", features=["status", "options"]))._filter(number).options[0].name == "Internet Tjedan"
