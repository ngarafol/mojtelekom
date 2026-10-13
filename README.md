# Moj Telekom HR (neslužbeno)

Stanje tvojih brojeva iz **Moj Telekom** (Hrvatski Telekom) u Home Assistantu: **prepaid bon**, tarifa, **preostali besplatni MB**, rok bona/SIM kartice i **aktivne opcije**.

## Zašto ovo postoji

Hrvatski Telekom nema javni API za potrošačke usluge, a mobilna aplikacija je zatvorena (DexProtector, root detekcija, vezanje na potpis APK-a). Ostaje web portal — i to je sve što ova integracija radi: prijavi se na [moj.hrvatskitelekom.hr](https://moj.hrvatskitelekom.hr) tvojim Telekom ID podacima i čita stanje broja.

Praktično to znači da u HA-u možeš:

- dobiti obavijest kad bon padne ispod nekog iznosa,
- pratiti koliko je MB ostalo i kad bon ili SIM istječe,
- dobiti obavijest kad aktivna opcija istekne,
- sve to bez otvaranja aplikacije i bez ručnog provjeravanja.

## Što ti treba

- Home Assistant **2024.11+** i [HACS](https://hacs.xyz)
- **Telekom ID** (korisničko ime ili e-mail + lozinka) — isti podaci kojima se prijavljuješ na portal
- Račun **bez 2FA**: ako portal pri prijavi traži jednokratni PIN, integracija to ne podržava

### Gdje ti je lozinka (i kako smanjiti rizik)

- Koristi se **samo** za prijavu na HT portal i SSO — nikamo drugo se ne šalje, **ne završava u logu** (u debug dumpu se bilježe samo *imena* polja), a **dijagnostika je redaktira**. Sesijski kolačić drži se **samo u memoriji**.
- U HA-u se sprema u `config/.storage/core.config_entries`, a HA config entryje drži **u čistom tekstu** (bez šifriranja). Taj fajl ulazi i u **backupe**. To je HA-ovo standardno ponašanje za integracije koje traže korisničke podatke — HA nema API za šifriranu pohranu vjerodajnica.
- **Ako želiš da tajna ne bude ni u `.storage` ni u backupu:** postavi `MT_USERNAME` / `MT_PASSWORD` u okolinu procesa, a polje lozinke u integraciji ostavi **prazno**. Tada HA ne sprema nikakvu tajnu (radi na **HA Container / HA Core**; na HA OS-u se env varijable ne mogu lako postaviti):

  ```bash
  docker run -d --name homeassistant -e MT_USERNAME='korisnik' -e MT_PASSWORD='lozinka' homeassistant/home-assistant
  # ili --env-file /path/secrets.env  (chmod 600)
  ```

  Env varijable nisu tajna pohrana (vidljive su korisniku koji vrti proces), ali **ne idu u backup**.
- Dodatno: uključi **šifrirane backupe** u HA-u, drži `config/` na šifriranom disku i ne stavljaj lozinku u `configuration.yaml` / `secrets.yaml`.
- Za CLI: lozinku daj kroz `read -rs` ili env varijablu, nikako u naredbeni redak (ostaje u povijesti).

Ništa se ne šalje trećim stranama — jedini odlazni promet ide na `moj.hrvatskitelekom.hr` i `sso.hrvatskitelekom.hr`.

## Instalacija

1. HACS → tri točke → **Custom repositories** → URL ovog repozitorija, kategorija **Integration**.
2. Nađi **Moj Telekom** u HACS-u → **Download** → restartaj Home Assistant.
3. **Postavke → Uređaji i servisi → Dodaj integraciju → Moj Telekom** → upiši Telekom ID i lozinku.

Bez HACS-a: kopiraj mapu `custom_components/moj_telekom` u svoj HA `config/custom_components/` i restartaj.

Integracija se prijavljuje sama — **ne treba pokretati nikakav servis, Docker ni add-on**.

## Što dobiješ

Za svaki broj na računu dobiješ uređaj (naziv = broj) i senzore:

| Senzor | Stanje | Atributi |
|---|---|---|
| `sensor.mojtelekom_<broj>_prepaid_stanje` | iznos bona (EUR) | `tarifa`, `aktivne_opcije`, `vrijedi_do`, `status`, `msisdn` |
| `sensor.mojtelekom_<broj>_vrijedi_do` | datum do kojeg broj/bon vrijedi | — |
| `sensor.mojtelekom_<broj>_preostali_promet` | preostali besplatni MB | `data_remaining_mb` |
| `sensor.mojtelekom_<broj>_aktivne_opcije` | nazivi aktivnih opcija (ili "nema aktivnih") | `aktivne_opcije` |
| `sensor.mojtelekom_<broj>_status` | `active` | `tarifa`, `aktivne_opcije` |

Svaki senzor u atributima nosi `msisdn` i **`feature`** (`status`/`prepaid`/`usage`/`valid_until`/`options`) — po tome ih template kartice i automatizacije mogu pronaći bez upisivanja entity ID-eva.

`<broj>` je međunarodni zapis bez `+`, pa entity ID izgleda npr. `sensor.mojtelekom_385991234567_prepaid_stanje`. **Prefiks `mojtelekom_` je tu namjerno** — lako filtriraš entitete (u tražilici upiši `mojtelekom`) i slažeš kartice (`entity_id: "*mojtelekom*"`). Naziv uređaja je "Moj Telekom 099 1234567", a možeš ga preimenovati (npr. "Markov mobitel").

> **Nadogradnja s starije verzije:** HA pamti entity ID-eve, pa oni ostaju stari (`sensor.<broj>_prepaid_stanje`). Da dobiješ prefiks, **obriši integraciju i dodaj je ponovno** (opcije se resetiraju na zadano), ili preimenuj entitete ručno.

Kroz **Konfiguriraj → Opcije** uključuješ/isključuješ značajke (`status`, `prepaid`, `usage`, `valid_until`, `options`) i mijenjaš interval osvježavanja (5–1440 min, zadano 15). Isključena značajka se uopće ne dohvaća — `options` recimo štedi jedan zahtjev po broju. Ručno osvježavanje: na kartici integracije ⋮ → **Osvježi** (ili akcija `homeassistant.update_entity`).

## Primjeri upotrebe

**Obavijest kad je bon nizak** (broj 099 1234567, bon pod 3 EUR):

```yaml
automation:
  - alias: "Moj Telekom: nizak bon"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.mojtelekom_385991234567_prepaid_stanje
        below: 3
    actions:
      - action: notify.mobile_app
        data:
          title: "Malo ti je bona"
          message: >-
            Na 099 1234567 ostalo je {{ states('sensor.mojtelekom_385991234567_prepaid_stanje') }} EUR.
```

**Podsjetnik 3 dana prije isteka bona:**

```yaml
automation:
  - alias: "Moj Telekom: bon istječe"
    triggers:
      - trigger: time
        at: "09:00:00"
    conditions:
      - condition: template
        value_template: >-
          {% set v = state_attr('sensor.mojtelekom_385991234567_prepaid_stanje', 'vrijedi_do') %}
          {{ v is not none and (v | as_datetime | as_local).date() == (now().date() + timedelta(days=3)) }}
    actions:
      - action: notify.mobile_app
        data:
          message: "Bon na 099 1234567 istječe za 3 dana."
```

**Obavijest kad opcija istekne** (opcija nestane s popisa aktivnih — rok portal ne objavljuje):

```yaml
automation:
  - alias: "Moj Telekom: opcija je istekla"
    triggers:
      - trigger: state
        entity_id: sensor.mojtelekom_385991234567_prepaid_stanje
        attribute: aktivne_opcije
    conditions:
      - condition: template
        value_template: >-
          {{ state_attr('sensor.mojtelekom_385991234567_prepaid_stanje', 'aktivne_opcije') | length == 0 }}
    actions:
      - action: notify.mobile_app
        data:
          message: "Nema više aktivnih opcija na 099 1234567."
```

### Gdje su entiteti

**Postavke → Uređaji i servisi → Moj Telekom** → klikni uređaj (naziv je broj) → popis svih entiteta. Entity ID i atribute vidiš klikom na entitet → ⚙ (zupčanik). Za brzi pregled: **Alatni programi za razvojne programere → Stanja** i u filtar upiši `prepaid_stanje`.

Svi entity ID-evi počinju s `mojtelekom_`, a u atributima svaki senzor nosi `feature` i `msisdn` — po tome ih filtriraš. Vrijednost (bon, MB, datum) je u **stanju** senzora, a tarifa i opcije su i u **atributima** — atributi se u karticama ne prikazuju sami. Zato:

### Sve senzore jednog broja — jedan klik (bez YAMLA)

**Postavke → Uređaji i servisi → Moj Telekom → klikni uređaj (broj) → gore desno **+ ADD TO DASHBOARD**.** HA sam napravi karticu sa svim senzorima tog broja i pita na koji dashboard.

Dobivenoj kartici možeš dodati retke s atributima (tarifa, opcije, rok):

```yaml
type: entities
title: Moj Telekom — 099 1234567
entities:
  - entity: sensor.mojtelekom_385991234567_prepaid_stanje
    name: Bon
  - entity: sensor.mojtelekom_385991234567_vrijedi_do
    name: Vrijedi do
  - entity: sensor.mojtelekom_385991234567_preostali_promet
    name: Preostali promet
  - entity: sensor.mojtelekom_385991234567_aktivne_opcije
    name: Aktivne opcije
  - entity: sensor.mojtelekom_385991234567_status
    name: Status
  - type: attribute
    entity: sensor.mojtelekom_385991234567_prepaid_stanje
    attribute: tarifa
    name: Tarifa
```

### Kartica koja dolazi s integracijom (preporučeno)

Integracija isporučuje i **vlastitu karticu** — učitava se sama, nema ručnog dodavanja resursa ni dodatnih HACS frontenda. Entitete pronalazi sama i grupira ih po broju, pa je dovoljno:

Dashboard → **Uredi** → **+ Dodaj karticu** → nađi **Moj Telekom** u izborniku (ili Ručno) → Spremi:

```yaml
type: custom:moj-telekom-card
title: Moj Telekom
low_balance: 3        # bon ispod ovog iznosa se prikaže crveno
```

Kartica po broju prikazuje: **bon** (crveno ispod `low_balance`), **vrijedi do**, **preostali promet**, **tarifu**, **aktivne opcije** i status ako nije `active`. `title` i `low_balance` su opcionalni.

### Ručne kartice (bez dodatka)

Ako želiš ugrađene HA kartice umjesto naše:

### Kartica s atributima (jedan broj)

Dashboard → **Uredi** → **+ Dodaj karticu** → dolje **Ručno (Manual)** → zalijepi:

```yaml
type: entities
title: Moj Telekom — 099 1234567
entities:
  - entity: sensor.mojtelekom_385991234567_prepaid_stanje
    name: Bon
  - entity: sensor.mojtelekom_385991234567_potrosnja_data
    name: Preostali MB
  - entity: sensor.mojtelekom_385991234567_status
    name: Status
  - type: attribute
    entity: sensor.mojtelekom_385991234567_prepaid_stanje
    attribute: tarifa
    name: Tarifa
  - type: attribute
    entity: sensor.mojtelekom_385991234567_prepaid_stanje
    attribute: vrijedi_do
    name: Bon vrijedi do
  - type: attribute
    entity: sensor.mojtelekom_385991234567_prepaid_stanje
    attribute: aktivne_opcije
    name: Aktivne opcije
```

### Kartica sa svim brojevima (Markdown)

Ista kartica prikazuje sve brojeve odjednom, s uredno formatiranim datumima i opcijama:

```yaml
type: markdown
title: Moj Telekom
content: |-
  {# svi senzori ove integracije nose atribut `feature` i `msisdn` #}
  {% set nasi = states.sensor | selectattr('attributes.feature', 'defined') | list %}
  {% for ms in nasi | map(attribute='attributes.msisdn') | unique | list %}
  {% set s = nasi | selectattr('attributes.msisdn', 'equalto', ms) | list %}
  {% set bon = s | selectattr('attributes.feature', 'equalto', 'prepaid') | first %}
  {% set rok = s | selectattr('attributes.feature', 'equalto', 'valid_until') | first %}
  {% set promet = s | selectattr('attributes.feature', 'equalto', 'usage') | first %}
  {% set opcije = s | selectattr('attributes.feature', 'equalto', 'options') | first %}
  ### {{ ms }}
  - **Bon:** {{ bon.state }} EUR{% if bon is defined and bon.attributes.tarifa %} · {{ bon.attributes.tarifa }}{% endif %}
  - **Vrijedi do:** {% if rok is defined and rok.state not in ['unknown', 'unavailable'] %}{{ (rok.state | as_datetime).strftime('%d.%m.%Y') }}{% else %}—{% endif %}
  - **Preostali promet:** {% if promet is defined and promet.state not in ['unknown', 'unavailable'] %}{{ promet.state }} MB{% else %}—{% endif %}
  - **Opcije:** {{ opcije.state if opcije is defined else '—' }}
  {% endfor %}
```

## Kako čita podatke

Prijava ide na Keycloak SSO (`sso.hrvatskitelekom.hr`), a stanje se čita iz HTML-a portala:

| Podatak | Izvor |
|---|---|
| Bon, bonus račun, tarifa | `/moredata/?serviceType=MobilePrepaid&serviceId=…` |
| Preostali besplatni MB, `SIM kartica vrijedi do` (→ `vrijedi_do`) | `/korisnici-bonova/stanje-racuna?serviceid=…` |
| Aktivne opcije | `/korisnici-bonova/opcije?serviceid=…` (aktivna nosi `DeactivateOption(...)`) |

Sesija se drži između osvježavanja, pa je prijava zapravo rijetka. Kad sesija istekne, portal vrati javnu login stranicu s **HTTP 200** — da se to ne pretvori tiho u "nema podataka", svaki dohvat provjerava marker koji dolazi samo na traženoj stranici, pa slijedi ponovna prijava i još jedan pokušaj.

## Ograničenja

- **Nema statusa blokade** — portal prikazuje samo aktivne usluge.
- **Nema roka pojedine opcije.** Provjereno na svim mjestima (opcije, stanje računa, uredjivanje usluga, pregled plaćanja): portal taj podatak ne objavljuje, ima ga samo mobilna aplikacija. Zato koristi automatizaciju na promjenu senzora `aktivne_opcije` (npr. kad postane "nema aktivnih").
- **Datum `vrijedi_do`** je ono što portal zove "SIM kartica vrijedi do" / "Bon vrijedi do" — datum do kojeg broj vrijedi.
- **Bez računa i bez postpaid usluga** — integracija čita stanje brojeva (prepaid bon, MB, opcije).
- **Bez 2FA/captcha** i bez automatske ponovne prijave nakon promjene lozinke (obriši i ponovno dodaj integraciju).
- Portal se može promijeniti bez najave — zato je parsiranje pokriveno testovima i postoji `mojtelekom dump` za pregled stvarnih stranica.

## Rješavanje problema

| Simptom | Što provjeriti |
|---|---|
| Pri dodavanju integracije: *"Prijava nije prošla"* | Prijavi se istim podacima u browseru na portal. Ako traži PIN/2FA, integracija to ne može. |
| *"Ne mogu se spojiti na Moj Telekom portal"* | Mreža/DNS na HA hostu; je li portal dostupan u browseru. |
| Senzori su *nedostupno* nakon što su radili | Postavke → Sustav → Dnevnik, filter `moj_telekom`. Najčešće istekla sesija (riješi se sama) ili promjena portala. |
| Vrijednosti izgledaju prazno | Smanji značajke/interval i pogledaj dnevnik; ako portal promijeni HTML, treba ažurirati parser. |
| Želiš prijaviti problem | **Postavke → Uređaji i servisi → Moj Telekom → ⋮ → Download diagnostics** — vjerodajnice se redaktiraju, brojevi maskiraju na zadnje 3 znamenke. |

Za dublju dijagnostiku (razvoj/prijava problema):

```bash
MT_ADAPTER=portal MT_DEBUG=1 MT_USERNAME='korisnik' MT_PASSWORD='lozinka' mojtelekom dump
```

To u `mt-debug/` sprema svaki korak prijave i sve dohvaćene stranice. **Pazi: te datoteke sadrže tvoje podatke** (brojeve, stanje, ime) — pregledaj ih prije nego ih podijeliš.

## Bez Home Assistanta (CLI / REST / WebUI)

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"

MT_ADAPTER=portal MT_USERNAME='korisnik' MT_PASSWORD='lozinka' mojtelekom status
mojtelekom serve            # REST + WebUI na http://127.0.0.1:8088
mojtelekom dump             # spremi HTML stranice portala u mt-debug/ (razvoj parsera)
```

| Var | Zadano | Opis |
|---|---|---|
| `MT_ADAPTER` | `mock` | `mock` (lažni podaci) ili `portal` (stvarni podaci) |
| `MT_FEATURES` | sve | Zarezom odvojene: `status,prepaid,usage,valid_until,options` |
| `MT_TTL` | `60` | Cache u sekundama (čuva portal od ponovljenih dohvata) |
| `MT_API_KEY` | prazno | Ako je postavljen, `/api/*` traži `X-API-Key` header |
| `MT_USERNAME` / `MT_PASSWORD` | prazno | Telekom ID za `portal` adapter |
| `MT_DEBUG` | prazno | Sprema korake prijave i dohvaćene stranice u `mt-debug/` |

REST: `GET /api/numbers`, `GET /api/numbers/{msisdn}`, `GET /healthz`.

## Razvoj

```bash
pytest                          # 44 testa (parsiranje, značajke, drift core-a, kartica, CLI, čuvari tajni)
python3 scripts/sync_core.py    # osvježi core unutar HA integracije
```

```
mojtelekom/core/                 # modeli (dataclass), klijent portala, fetch_numbers
mojtelekom/                      # CLI, REST API, WebUI, adapteri (mock/portal)
custom_components/moj_telekom/   # HA integracija (+ generirana core/ kopija, www/ kartica, diagnostics.py)
scripts/sync_core.py             # generira tu kopiju; test pada ako zaostane
tests/
```

`mojtelekom/core` je jedini izvor logike (bez Home Assistanta i bez pydantica) i dijeli ga HA integracija s CLI/API-jem. HA integracija nosi **generiranu kopiju** jer HACS prenosi samo mapu integracije.

### Objava nove verzije (za maintainera)

```bash
git tag v0.2.1 && git push --tags     # HACS vidi tag kao novu verziju
```

*Napomena:* neslužbeni klijent s vlastitim podacima i vlastitim vjerodajnicama — siva zona. HT može promijeniti portal bez najave.
