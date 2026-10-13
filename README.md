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

Podaci za prijavu spremaju se u HA config entry (`config/.storage/core.config_entries`) i koriste isključivo za prijavu na HT portal. Ništa se ne šalje trećim stranama — jedini odlazni promet ide na `moj.hrvatskitelekom.hr` i `sso.hrvatskitelekom.hr`.

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
| `sensor.<broj>_prepaid_stanje` | iznos bona (EUR) | `vrijedi_do`, `tarifa`, `aktivne_opcije`, `status`, `msisdn` |
| `sensor.<broj>_potrosnja_data` | preostali besplatni MB | `data_remaining_mb` |
| `sensor.<broj>_status` | `active` | `tarifa`, `aktivne_opcije` |

`<broj>` je međunarodni zapis bez `+`, npr. `sensor.385991234567_prepaid_stanje`. Entity ID možeš preimenovati, a naziv uređaja promijeniti u nešto čitljivije ("Markov mobitel").

Kroz **Konfiguriraj → Opcije** uključuješ/isključuješ značajke (`status`, `prepaid`, `usage`, `options`) i mijenjaš interval osvježavanja (5–1440 min, zadano 15). Isključena značajka se uopće ne dohvaća — `options` recimo štedi jedan zahtjev po broju. Ručno osvježavanje: na kartici integracije ⋮ → **Osvježi** (ili akcija `homeassistant.update_entity`).

## Primjeri upotrebe

**Obavijest kad je bon nizak** (broj 099 1234567, bon pod 3 EUR):

```yaml
automation:
  - alias: "Moj Telekom: nizak bon"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.385991234567_prepaid_stanje
        below: 3
    actions:
      - action: notify.mobile_app
        data:
          title: "Malo ti je bona"
          message: >-
            Na 099 1234567 ostalo je {{ states('sensor.385991234567_prepaid_stanje') }} EUR.
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
          {% set v = state_attr('sensor.385991234567_prepaid_stanje', 'vrijedi_do') %}
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
        entity_id: sensor.385991234567_prepaid_stanje
        attribute: aktivne_opcije
    conditions:
      - condition: template
        value_template: >-
          {{ state_attr('sensor.385991234567_prepaid_stanje', 'aktivne_opcije') | length == 0 }}
    actions:
      - action: notify.mobile_app
        data:
          message: "Nema više aktivnih opcija na 099 1234567."
```

### Gdje su entiteti

**Postavke → Uređaji i servisi → Moj Telekom** → klikni uređaj (naziv je broj) → popis svih entiteta. Entity ID i atribute vidiš klikom na entitet → ⚙ (zupčanik). Za brzi pregled: **Alatni programi za razvojne programere → Stanja** i u filtar upiši `prepaid_stanje`.

Vrijednost (bon, MB) je u **stanju** senzora, a tarifa, rok i opcije su u **atributima** — atributi se u karticama ne prikazuju sami. Zato:

### Kartica s atributima (jedan broj)

Dashboard → **Uredi** → **+ Dodaj karticu** → dolje **Ručno (Manual)** → zalijepi:

```yaml
type: entities
title: Moj Telekom — 099 1234567
entities:
  - entity: sensor.385991234567_prepaid_stanje
    name: Bon
  - entity: sensor.385991234567_potrosnja_data
    name: Preostali MB
  - entity: sensor.385991234567_status
    name: Status
  - type: attribute
    entity: sensor.385991234567_prepaid_stanje
    attribute: tarifa
    name: Tarifa
  - type: attribute
    entity: sensor.385991234567_prepaid_stanje
    attribute: vrijedi_do
    name: Bon vrijedi do
  - type: attribute
    entity: sensor.385991234567_prepaid_stanje
    attribute: aktivne_opcije
    name: Aktivne opcije
```

### Kartica sa svim brojevima (Markdown)

Ista kartica prikazuje sve brojeve odjednom, s uredno formatiranim datumima i opcijama:

```yaml
type: markdown
title: Moj Telekom
content: |-
  {% for s in states.sensor | selectattr('entity_id', 'search', '_prepaid_stanje') | sort(attribute='entity_id') %}
  {% set do = state_attr(s.entity_id, 'vrijedi_do') %}
  {% set opts = state_attr(s.entity_id, 'aktivne_opcije') %}
  {% set usage = states('sensor.' + (s.object_id | replace('_prepaid_stanje', '_potrosnja_data'))) %}
  ### {{ state_attr(s.entity_id, 'msisdn') }}
  - **Bon:** {{ s.state }} EUR{% if do %} (vrijedi do {{ (do | as_datetime).strftime('%d.%m.%Y') }}){% endif %}
  - **Tarifa:** {{ state_attr(s.entity_id, 'tarifa') or '—' }}
  - **Opcije:** {{ opts | map(attribute='naziv') | join(', ') if opts else '—' }}
  {% if usage not in ['unknown', 'unavailable'] %}- **Preostalo:** {{ usage }} MB
  {% endif %}
  {% endfor %}
```

## Kako čita podatke

Prijava ide na Keycloak SSO (`sso.hrvatskitelekom.hr`), a stanje se čita iz HTML-a portala:

| Podatak | Izvor |
|---|---|
| Bon, bonus račun, tarifa | `/moredata/?serviceType=MobilePrepaid&serviceId=…` |
| Preostali besplatni MB, `SIM kartica vrijedi do` | `/korisnici-bonova/stanje-racuna?serviceid=…` |
| Aktivne opcije | `/korisnici-bonova/opcije?serviceid=…` (aktivna nosi `DeactivateOption(...)`) |

Sesija se drži između osvježavanja, pa je prijava zapravo rijetka. Kad sesija istekne, portal vrati javnu login stranicu s **HTTP 200** — da se to ne pretvori tiho u "nema podataka", svaki dohvat provjerava marker koji dolazi samo na traženoj stranici, pa slijedi ponovna prijava i još jedan pokušaj.

## Ograničenja

- **Nema statusa blokade** — portal prikazuje samo aktivne usluge.
- **Nema roka pojedine opcije.** Provjereno na svim mjestima (opcije, stanje računa, uredjivanje usluga, pregled plaćanja): portal taj podatak ne objavljuje, ima ga samo mobilna aplikacija. Zato koristi automatizaciju na promjenu `aktivne_opcije`.
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
| `MT_FEATURES` | sve | Zarezom odvojene: `status,prepaid,usage,options` |
| `MT_TTL` | `60` | Cache u sekundama (čuva portal od ponovljenih dohvata) |
| `MT_API_KEY` | prazno | Ako je postavljen, `/api/*` traži `X-API-Key` header |
| `MT_USERNAME` / `MT_PASSWORD` | prazno | Telekom ID za `portal` adapter |
| `MT_DEBUG` | prazno | Sprema korake prijave i dohvaćene stranice u `mt-debug/` |

REST: `GET /api/numbers`, `GET /api/numbers/{msisdn}`, `GET /healthz`.

## Razvoj

```bash
pytest                          # 25 testova (parsiranje, značajke, drift core-a)
python3 scripts/sync_core.py    # osvježi core unutar HA integracije
```

```
mojtelekom/core/                 # modeli (dataclass), klijent portala, fetch_numbers
mojtelekom/                      # CLI, REST API, WebUI, adapteri (mock/portal)
custom_components/moj_telekom/   # HA integracija (+ generirana core/ kopija)
scripts/sync_core.py             # generira tu kopiju; test pada ako zaostane
tests/
```

`mojtelekom/core` je jedini izvor logike (bez Home Assistanta i bez pydantica) i dijeli ga HA integracija s CLI/API-jem. HA integracija nosi **generiranu kopiju** jer HACS prenosi samo mapu integracije.

### Objava nove verzije (za maintainera)

```bash
git tag v0.2.1 && git push --tags     # HACS vidi tag kao novu verziju
```

*Napomena:* neslužbeni klijent s vlastitim podacima i vlastitim vjerodajnicama — siva zona. HT može promijeniti portal bez najave.
