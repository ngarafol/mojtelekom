# GENERIRANO iz mojtelekom/core/portal.py — ne uređivati; pokreni scripts/sync_core.py
"""Klijent za Moj Telekom web portal (moj.hrvatskitelekom.hr).

Portal je ASP.NET aplikacija iza Keycloak SSO-a (realm HrvatskiTelekom, client
moj.hrvatskitelekom.hr). Nema javnog JSON API-ja za stanje — podaci dolaze kao HTML
fragmenti, pa se parsiraju (funkcije parse_* su čiste i testirane bez mreže).

Prednost pred mobilnom aplikacijom: portal nema DexProtector, root detekciju ni
vezanje na potpis APK-a, pa je jedini uvjet korisnički račun (Telekom ID).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date
from hashlib import sha1
from html import unescape
from pathlib import Path
from urllib.parse import urljoin
from uuid import uuid4

import aiohttp

from .models import Option

BASE = "https://moj.hrvatskitelekom.hr"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

_TH_TD = re.compile(r"<th[^>]*>\s*([^<>:]+):?\s*</th>\s*<td[^>]*>(.*?)</td>", re.S)
_SERVICE = re.compile(r"serviceType=([A-Za-z]+)&(?:amp;)?ajaxrequest=true&(?:amp;)?serviceId=(\d+)")
_NUMBER_LINK = re.compile(r'/korisnici-bonova/[a-z-]+\?serviceid=(\d+)">\s*([\d\s]+?)\s*</a>')
_TARIFF = re.compile(r"Tarifa[^:<>]*:\s*([^<>\r\n]+)")
_TAGS = re.compile(r"<[^>]+>")
# Keycloakova OIDC form_post stranica koristi VELIKA slova atribute, login forma mala.
_FORM_ACTION = re.compile(r"<form[^>]+action=\"([^\"]+)\"", re.I)
_INPUTS = re.compile(r"<input[^>]+name=\"([^\"]+)\"[^>]*value=\"([^\"]*)\"", re.I)
_FEEDBACK = re.compile(r"id=\"(?:input-error|kc-feedback-text|kc-error-message)\"[^>]*>(.*?)<", re.I | re.S)
_DATE = re.compile(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})")


def _date_in(html: str) -> date | None:
    match = _DATE.search(_TAGS.sub(" ", html))
    if not match:
        return None
    try:
        return date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
    except ValueError:
        return None


class AuthError(RuntimeError):
    """Prijava nije prošla: krivi podaci, captcha/2FA ili se login tok promijenio."""


@dataclass
class ServiceRef:
    service_type: str
    service_id: str


@dataclass
class PrepaidData:
    msisdn: str
    service_id: str
    tariff: str | None = None
    balance: float | None = None
    currency: str = "EUR"
    bonus: float | None = None


def _clean(value: str) -> str | None:
    text = re.sub(r"\s+", " ", unescape(_TAGS.sub(" ", value))).strip()
    if not text or text.lower().startswith("nema podataka"):
        return None
    return text


def _pair(html: str, label: str) -> str | None:
    """Vrijednost iz <th>label:</th><td>vrijednost</td>."""
    for key, value in _TH_TD.findall(html):
        if label.lower() in key.lower():
            return _clean(value)
    return None


def _hr_float(value: str | None) -> float | None:
    """Hrvatski zapis: '164234,4' -> 164234.4"""
    if not value:
        return None
    match = re.match(r"([\d.,]+)", value)
    if not match:
        return None
    try:
        return float(match.group(1).replace(".", "").replace(",", "."))
    except ValueError:
        return None


def parse_msisdn(display: str) -> str:
    """'099 1234567' -> '385991234567' (podržava i već međunarodni zapis)."""
    digits = re.sub(r"\D", "", display).lstrip("0")
    return digits if digits.startswith("385") else f"385{digits}"


def parse_services(html: str) -> list[ServiceRef]:
    """Sve usluge s naslovnice. Isti (tip, id) par se preskače jer portal zna
    iscrtati isti blok dvaput (mobilni + desktop markup)."""
    seen: set[tuple[str, str]] = set()
    out: list[ServiceRef] = []
    for service_type, service_id in _SERVICE.findall(html):
        if (service_type, service_id) not in seen:
            seen.add((service_type, service_id))
            out.append(ServiceRef(service_type, service_id))
    return out


def parse_service_data(html: str) -> PrepaidData | None:
    """Parsira /moredata/ fragment jednog broja (radi za prepaid; ostali tipovi daju bez stanja)."""
    link = _NUMBER_LINK.search(html)
    if not link:
        return None
    balance_text = _pair(html, "Stanje bona")
    # Tarifu tražimo u sirovom HTML-u: u <th> iza naziva slijedi <br> i link "Promijenite tarifu".
    tariff_match = _TARIFF.search(html)
    currency = re.search(r"[A-Z]{3}", balance_text) if balance_text else None
    return PrepaidData(
        msisdn=parse_msisdn(link.group(2)),
        service_id=link.group(1),
        tariff=tariff_match.group(1).strip() if tariff_match else None,
        balance=_hr_float(balance_text),
        currency=currency.group(0) if currency else "EUR",
        bonus=_hr_float(_pair(html, "Stanje bonus računa")),
    )


def parse_options(html: str) -> list[Option]:
    """Aktivne opcije s /korisnici-bonova/opcije.

    Aktivna opcija u svom <li> bloku nosi poziv DeactivateOption(...), dok neaktivne
    iz kataloga nose ActivateOption(...). Portal za opcije zasad ne prikazuje rok
    (rok imaju bon i SIM kartica), pa je valid_until None — ako se datum jednom pojavi
    u bloku opcije, pokupit će se.
    """
    options: list[Option] = []
    for block in re.findall(r"<li>(.*?)</li>", html, re.S):
        name = re.search(r'<h2 class="h2title">(.*?)</h2>', block, re.S)
        if not name or "deactivateoption(" not in block.lower():
            continue
        options.append(Option(name=_clean(name.group(1)) or "", valid_until=_date_in(block)))
    return options


def parse_account(html: str) -> tuple[float | None, date | None]:
    """Iz /korisnici-bonova/stanje-racuna: (besplatni MB, datum do kojeg SIM vrijedi)."""
    free_mb = _hr_float(_pair(html, "Besplatno MB podatkovnog prometa"))
    valid_text = _pair(html, "SIM kartica vrijedi do")
    valid_until = None
    if valid_text:
        match = re.match(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})", valid_text)
        if match:
            valid_until = date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
    return free_mb, valid_until


def _debug_dir() -> Path:
    path = Path("mt-debug")
    path.mkdir(exist_ok=True)
    return path


def parse_form(html: str) -> tuple[str | None, dict[str, str]]:
    """(action, skrivena polja) iz HTML forme. Neosjetljivo na velika slova jer
    Keycloakova form_post stranica piše <FORM ACTION=...> i <INPUT NAME=...>."""
    action = _FORM_ACTION.search(html)
    fields = {name: unescape(value) for name, value in _INPUTS.findall(html)}
    return (unescape(action.group(1)) if action else None), fields


def _feedback(html: str) -> str | None:
    """Poruka koju Keycloak ispiše kod neuspjele prijave (npr. 'Invalid username or password.')."""
    match = _FEEDBACK.search(html)
    return _clean(match.group(1)) if match else None


def _blocker(html: str) -> str | None:
    """Poruka ako prijava traži nešto što ne možemo automatizirati."""
    if re.search(r'name="otp"', html, re.I):
        return "portal traži jednokratni kod (2FA)"
    if re.search(r'name="captcha"', html, re.I):
        return "portal traži captcha-u"
    return None


class PortalClient:
    """Drži cookie sesiju; kod isteka se sam ponovno prijavi."""

    def __init__(self, username: str, password: str, debug: bool | None = None) -> None:
        self._username = username
        self._password = password
        self._session: aiohttp.ClientSession | None = None
        self._debug = (os.getenv("MT_DEBUG") is not None) if debug is None else debug
        self._trace: list[str] = []

    # --- debug pomagala (uključeno s MT_DEBUG=1) ---
    def _note(self, message: str) -> None:
        if not self._debug:
            return
        self._trace.append(message)
        _debug_dir().joinpath("trace.txt").write_text("\n".join(self._trace), encoding="utf-8")

    def _dump(self, name: str, text: str) -> None:
        if self._debug:
            _debug_dir().joinpath(name).write_text(text, encoding="utf-8")

    def _note_response(self, label: str, resp: aiohttp.ClientResponse, text: str) -> None:
        chain = " -> ".join(f"{r.status}" for r in (*resp.history, resp))
        self._note(
            f"{label}: {resp.request_info.method} {resp.request_info.url} | status {resp.status} "
            f"| lanac {chain} | finalni {resp.url} | len {len(text)} "
            f"| code={'name=\"code\"' in text.lower()} | form={'<form' in text.lower()} "
            f"| Location {resp.headers.get('Location')} | Set-Cookie {self._set_cookie_names(resp)}"
        )

    def _cookie_names(self) -> list[str]:
        return sorted(c.key for c in self._session.cookie_jar) if self._session else []

    @staticmethod
    def _set_cookie_names(resp: aiohttp.ClientResponse) -> list[str]:
        names = []
        for r in (*resp.history, resp):
            for header in r.headers.getall("Set-Cookie", []):
                if match := re.match(r"\s*([^=;]+)=", header):
                    names.append(match.group(1).strip())
        return names

    async def _sess(self) -> aiohttp.ClientSession:
        """Sesija se stvara lijeno i živi dok je klijent živ (HA je drži između pollova)."""
        if self._session is None:
            self._session = aiohttp.ClientSession(headers={"User-Agent": UA})
        return self._session

    async def close(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> PortalClient:
        try:
            await self._login()
        except BaseException:
            await self.close()
            raise
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def _login_page(self) -> str | None:
        """HTML Keycloak login forme, ili None ako sesija još vrijedi.

        Redoslijed je bitan i prati browser:
        1. GET / — portal zatraži tihu SSO provjeru (prompt=none) i Keycloak vrati
           form_post s error=login_required.
        2. Taj odgovor se mora potrošiti (POST na /sso/challenge).
        3. Tek tada /public/telekom-id-prijava izda *interaktivni* challenge (bez
           prompt=none) sa svježim stateom i nonceom — stari state portal odbija na callbacku.
        """
        session = await self._sess()
        async with session.get(f"{BASE}/") as resp:
            page = await resp.text()
        if "moreData" in page:
            return None
        self._note_response("1-portal-home", resp, page)
        self._dump("1-portal-home.html", page)

        if re.search(r'name="error"', page, re.I):
            action, fields = parse_form(page)
            fields.pop("continue", None)  # submit gumb iz <noscript> nije dio pravog POST-a
            if action:
                async with session.post(action, data=fields) as resp:
                    page = await resp.text()
                self._note_response("2-probe-potrosen", resp, page)
                self._dump("2-probe-potrosen.html", page)

        async with session.get(f"{BASE}/public/telekom-id-prijava") as resp:
            page = await resp.text()
        self._note_response("3-login-form", resp, page)
        self._dump("3-login-form.html", page)
        return page

    async def _login(self) -> None:
        session = await self._sess()
        page = await self._login_page()
        if page is None:
            return
        if (blocker := _blocker(page)) is not None:
            raise AuthError(f"Automatska prijava nije moguća — {blocker}.")

        action, payload = parse_form(page)
        if not action:
            raise AuthError("Na SSO stranici nema login forme — portal je promijenjen ili nije dostupan.")
        self._note(f"3-post-credentials: {action[:160]} | polja {sorted(payload)}")
        payload.update({"username": self._username, "password": self._password})

        async with session.post(action, data=payload) as resp:
            page, url = await resp.text(), str(resp.url)
        self._note_response("3-nakon-vjerodajnica", resp, page)
        self._dump("3-nakon-vjerodajnica.html", page)
        if (blocker := _blocker(page)) is not None:
            raise AuthError(f"Automatska prijava nije moguća — {blocker}.")

        if re.search(r'name="code"', page, re.I):  # form_post stranica -> natrag na portal
            callback, fields = parse_form(page)
            fields.pop("continue", None)  # submit gumb iz <noscript> nije dio pravog POST-a
            self._note(f"4-post-callback: {callback} | polja {sorted(fields)} | kolačići {self._cookie_names()}")
            if callback:
                # Bez automatskog praćenja: prvi hop (i njegov Set-Cookie) je ključan za dijagnozu.
                async with session.post(callback, data=fields, allow_redirects=False) as resp:
                    body = await resp.text()
                    location = resp.headers.get("Location")
                    self._note_response("4-odgovor-na-callback", resp, body)
                    self._dump("4-nakon-callbacka.html", body)
                if location:
                    target = urljoin(callback, location)
                    async with session.get(target) as resp:
                        body = await resp.text()
                        self._note_response("4b-nakon-location", resp, body)
                        self._dump("4b-nakon-location.html", body)
        elif "moj.hrvatskitelekom.hr" not in url:
            reason = _feedback(page) or "nepoznat razlog (Keycloak nije vratio autorizacijski kod)"
            raise AuthError(f"Prijava nije prošla: {reason}")

        async with session.get(f"{BASE}/") as resp:
            home = await resp.text()
        self._note_response("5-provjera-sesije", resp, home)
        self._dump("5-provjera-sesije.html", home)
        self._note(f"kolačići: {sorted(c.key for c in session.cookie_jar)}")
        if "moreData" not in home:
            raise AuthError("Prijava nije prošla — provjeri MT_USERNAME/MT_PASSWORD (ili portal traži captcha/2FA).")

    def _dump_page(self, path: str, text: str) -> None:
        slug = re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-")[:45]
        self._dump(f"podaci-{slug}-{sha1(path.encode()).hexdigest()[:6]}.html", text)

    async def raw(self, path: str) -> str:
        """Dohvat bez provjere sadržaja — koristi ga `mojtelekom dump` za pregled stranica."""
        session = await self._sess()
        async with session.get(f"{BASE}{path}") as resp:
            text = await resp.text()
        self._dump_page(path, text)
        return text

    async def _get(self, path: str, expect: str) -> str:
        """GET s pozitivnom provjerom sadržaja.

        Kod istekle sesije portal vrati javnu login stranicu s HTTP 200, pa se to bez
        provjere tiho pretvori u "nema podataka". Zato tražimo marker koji dolazi samo
        na traženoj stranici: kod krivog sadržaja slijedi ponovna prijava i još jedan
        pokušaj, a na kraju greška (bolje glasno nego prazan senzor).
        """
        session = await self._sess()
        for attempt in (1, 2):
            async with session.get(f"{BASE}{path}") as resp:
                text = await resp.text()
            self._dump_page(path, text)
            if expect in text:
                return text
            self._note(f"neocekivan sadrzaj: nema {expect!r} na {path[:70]}")
            if attempt == 1:
                await self._login()
        raise AuthError(f"Portal nije vratio očekivani sadržaj ({expect!r}) — sesija je vjerojatno istekla.")

    async def services(self) -> list[ServiceRef]:
        return parse_services(await self._get("/", expect="moreData"))

    async def service(self, service_type: str, service_id: str) -> PrepaidData | None:
        path = (
            f"/moredata/?serviceType={service_type}&ajaxrequest=true"
            f"&serviceId={service_id}&ajaxRequestId={uuid4()}"
        )
        return parse_service_data(await self._get(path, expect=service_id))

    async def account(self, service_id: str) -> tuple[float | None, date | None]:
        path = f"/korisnici-bonova/stanje-racuna?serviceid={service_id}"
        return parse_account(await self._get(path, expect="Stanje na računu"))

    async def options(self, service_id: str) -> list[Option]:
        path = f"/korisnici-bonova/opcije?serviceid={service_id}"
        return parse_options(await self._get(path, expect=service_id))
