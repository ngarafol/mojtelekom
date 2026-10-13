# Moj Telekom HR (neslužbeno)

Stanje brojeva iz **Moj Telekom** (Hrvatski Telekom) u Home Assistantu, CLI-ju i REST API-ju: prepaid bon, tarifa, preostali besplatni MB, rok bona/SIM kartice i aktivne opcije.

> **Status:** HT nema javni API za potrošačke usluge. Podaci se čitaju s web portala [moj.hrvatskitelekom.hr](https://moj.hrvatskitelekom.hr) uz prijavu Telekom ID podacima. Sve ostaje lokalno kod tebe.

## Arhitektura

```
                 ┌─ custom_components/moj_telekom  →  HA senzori (prijava u HA, bez servisa)
mojtelekom/core ─┤
(models, klijent,└─ mojtelekom  →  CLI "mojtelekom status" / REST API / WebUI
 fetch_numbers)
```

`mojtelekom/core` je jedini izvor logike (bez Home Assistanta i bez pydantica). HA integracija sadrži **generiranu kopiju** tog core-a jer HACS prenosi samo mapu integracije — kopiju radi `scripts/sync_core.py`, a test pada ako zaostane.

## Instalacija u Home Assistant

Zahtijeva HACS i Home Assistant **2024.11+** (koristi se `OptionsFlowWithReload`).

1. HACS → tri točke → **Custom repositories** → URL repozitorija, kategorija **Integration**.
2. Nađi **Moj Telekom** u HACS-u → **Download** → restartaj HA.
3. **Postavke → Uređaji i servisi → Dodaj integraciju → Moj Telekom** → upiši Telekom ID (korisničko ime ili e-mail) i lozinku.

Bez HACS-a: kopiraj mapu `custom_components/moj_telekom` u svoj HA `config/custom_components/` i restartaj.

Dobiješ uređaj po broju (naziv = broj) i senzore:

| Senzor | Stanje | Atributi |
|---|---|---|
| `sensor.<broj>_prepaid_stanje` | iznos bona | `vrijedi_do`, `tarifa`, `aktivne_opcije`, `status` |
| `sensor.<broj>_potrosnja_data` | preostali besplatni MB | `data_remaining_mb`, minute/SMS |
| `sensor.<broj>_status` | `active` | `tarifa`, `aktivne_opcije` |
| `sensor.<broj>_racun` | iznos duga | `dospijeva`, `status_racuna` |

Kroz **Konfiguriraj → Opcije** uključuješ/isključuješ značajke (`status`, `prepaid`, `usage`, `invoice`, `options`) i mijenjaš interval osvježavanja (5–1440 min, zadano 15). Isključena značajka se ne dohvaća — `options` recimo štedi jedan zahtjev po broju.

## CLI / REST API / WebUI (opcionalno)

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"

MT_ADAPTER=portal MT_USERNAME='korisnik' MT_PASSWORD='lozinka' mojtelekom status
mojtelekom serve            # REST + WebUI na http://127.0.0.1:8088
mojtelekom dump             # spremi HTML stranice portala u mt-debug/ (razvoj parsera)
mojtelekom dump /korisnik/uredjivanje-usluga   # + dodatne stranice
```

Ili Docker:

```bash
docker build -t mojtelekom .
docker run -d -p 8088:8088 -e MT_ADAPTER=portal -e MT_USERNAME=korisnik -e MT_PASSWORD=lozinka \
  -e MT_API_KEY=tajna --name mojtelekom mojtelekom
```

| Var | Zadano | Opis |
|---|---|---|
| `MT_ADAPTER` | `mock` | `mock` (lažni podaci), `portal` (stvarni podaci), `real` (mobilna app, skeleton) |
| `MT_FEATURES` | sve | Zarezom odvojene: `status,prepaid,usage,invoice,options` |
| `MT_TTL` | `60` | Cache u sekundama (čuva portal od ponovljenih dohvata) |
| `MT_API_KEY` | prazno | Ako je postavljen, `/api/*` traži `X-API-Key` header |
| `MT_USERNAME` / `MT_PASSWORD` | prazno | Telekom ID za `portal` adapter |
| `MT_DEBUG` | prazno | Sprema svaki korak prijave i dohvaćene stranice u `mt-debug/` |

REST: `GET /api/numbers` (cijela lista), `GET /api/numbers/{msisdn}`, `GET /healthz`.

## Kako čita podatke

Prijava ide na Keycloak SSO (`sso.hrvatskitelekom.hr`, realm `HrvatskiTelekom`, client `moj.hrvatskitelekom.hr`), a stanje se čita iz HTML-a portala:

| Podatak | Izvor |
|---|---|
| Bon, bonus račun, tarifa | `/moredata/?serviceType=MobilePrepaid&serviceId=…` |
| Preostali besplatni MB, minute/SMS, `SIM kartica vrijedi do` | `/korisnici-bonova/stanje-racuna?serviceid=…` |
| Aktivne opcije | `/korisnici-bonova/opcije?serviceid=…` (aktivna nosi `DeactivateOption(...)`) |

### Ograničenja

- **Nema statusa blokade** — portal prikazuje samo aktivne usluge.
- **Nema roka pojedine opcije.** Provjereno na svim mjestima (opcije, `/moredata/`, stanje računa, uredjivanje usluga, pregled plaćanja): portal taj podatak ne objavljuje, ima ga samo mobilna aplikacija preko svog zatvorenog API-ja. Zamjena: opcija nestane s popisa kad istekne, pa se na promjenu atributa `aktivne_opcije` veže HA automatizacija.
- **Bez 2FA/captcha**: ako račun traži jednokratni kod, prijava javlja jasnu grešku.
- Portal se može promijeniti bez najave — zato je parsiranje pokriveno testovima i postoji `mojtelekom dump` za pregled stvarnih stranica.
- Ako promijeniš lozinku, obriši i ponovno dodaj integraciju (reauth nije implementiran).

### Zaštita od tihog propusta

Kad sesija istekne, portal vrati javnu login stranicu s **HTTP 200**, što se lako pretvori u "nema podataka". Zato svaki dohvat traži marker koji dolazi samo na traženoj stranici (`moreData`, `serviceId`, `Stanje na računu`): kod krivog sadržaja slijedi ponovna prijava i još jedan pokušaj, a na kraju greška.

## Razvoj

```bash
pytest                                  # 22 testa (parsiranje, feature toggles, drift core-a)
python3 scripts/sync_core.py            # osvježi core unutar HA integracije
```

Struktura:

```
mojtelekom/core/     # modeli (dataclass), klijent portala, fetch_numbers — dijeli se
mojtelekom/          # CLI, REST API, WebUI, adapteri (mock/portal/real)
custom_components/moj_telekom/   # HA integracija (+ generirana core/ kopija)
scripts/sync_core.py
tests/
```

### Objava (za HACS)

```bash
git init && git add . && git commit -m "Moj Telekom integracija"
gh repo create mojtelekom --public --source=. --push     # ili ručno na GitHub
git tag v0.2.0 && git push --tags                        # HACS vidi release
```

*Napomena:* neslužbeni klijent s vlastitim podacima i vlastitim vjerodajnicama — siva zona. Računaj da HT može promijeniti portal i API bez najave.
