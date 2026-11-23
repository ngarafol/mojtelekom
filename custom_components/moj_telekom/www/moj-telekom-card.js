/**
 * Moj Telekom kartica — dolazi s integracijom; nije potreban HACS frontend ni ručno
 * dodavanje resursa.
 *
 * Prikazuje po broju: veliki bon, do kada vrijedi, preostali promet, tarifu, aktivne
 * opcije i status, uz oznaku koliko su podaci stari. Entitete nalazi sama (platforma
 * `moj_telekom`) i grupira ih po uređaju:
 *   type: custom:moj-telekom-card
 */

const MOJ_TELEKOM_VERSION = "0.7.4";

// Redoslijed je bitan: "valid_until" sadrži donju crtu, pa se traži prije ostalih.
const KNOWN_FEATURES = ["valid_until", "prepaid", "usage", "options", "status"];

/** "2027-01-10" -> "10.01.2027." */
function fmtDate(value) {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleDateString("hr-HR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

/** Broj u hrvatskom zapisu; null ako vrijednost nije broj (npr. "unknown"). */
function fmtNumber(value, digits = 2) {
  const num = Number(value);
  if (!Number.isFinite(num)) return null;
  return num.toLocaleString("hr-HR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/** "385991234567" -> "099 1234567" (samo za prikaz). */
function fmtMsisdn(msisdn) {
  return msisdn && msisdn.startsWith("385") && msisdn.length === 12
    ? `0${msisdn.slice(3, 5)} ${msisdn.slice(5)}`
    : msisdn;
}

/** ISO -> "prije 7 min" / "prije 2 h" / "prije 3 d" */
function relTime(value) {
  if (!value) return null;
  const then = new Date(value).getTime();
  if (Number.isNaN(then)) return null;
  const minutes = Math.max(0, Math.round((Date.now() - then) / 60000));
  if (minutes < 1) return "upravo sada";
  if (minutes < 60) return `prije ${minutes} min`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `prije ${hours} h`;
  return `prije ${Math.round(hours / 24)} d`;
}

/** Hrvatski plural za "broj": 1 broj, 2 broja, 5 brojeva, 21 broj... */
function pluralBroj(count) {
  const last = count % 10;
  const lastTwo = count % 100;
  if (last === 1 && lastTwo !== 11) return `${count} broj`;
  if (last >= 2 && last <= 4 && (lastTwo < 12 || lastTwo > 14)) return `${count} broja`;
  return `${count} brojeva`;
}

/** "385998331732" / "+385 99 833 1732" / "099 8331732" -> "998331732" (za usporedbu). */
function normalizeMsisdn(value) {
  const digits = String(value ?? "").replace(/\D/g, "");
  return digits.replace(/^385/, "").replace(/^0+/, "");
}

/** Kojoj značajki pripada entitet — iz atributa `feature` na senzoru. */
function featureOf(hass, entityId) {
  const feature = hass.states?.[entityId]?.attributes?.feature;
  return KNOWN_FEATURES.includes(feature) ? feature : null;
}

/** Grupira entitete integracije po uređaju (broju). */
function groupNumbers(hass) {
  const groups = new Map();
  for (const entry of Object.values(hass.entities || {})) {
    if (entry.platform !== "moj_telekom") continue;
    const state = hass.states?.[entry.entity_id];
    if (!state) continue;
    const key = entry.device_id || state.attributes.msisdn || entry.entity_id;
    if (!groups.has(key)) {
      groups.set(key, {
        name: hass.devices?.[key]?.name || state.attributes.msisdn || key,
        msisdn: state.attributes.msisdn,
      });
    }
    groups.get(key)[featureOf(hass, entry.entity_id) || "status"] = state;
  }
  return [...groups.values()];
}

const escapeHtml = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);

const STYLES = `
  :host { display: block; }
  ha-card {
    padding: 0;
    overflow: hidden;
    background: var(--card-background-color);
  }
  .head {
    display: flex; align-items: center; gap: 10px;
    padding: 16px 18px 12px;
    border-bottom: 1px solid var(--divider-color);
  }
  .head ha-icon { color: var(--moj-accent, #e00074); --mdc-icon-size: 24px; }
  .head .title { font-size: 1.05rem; font-weight: 600; letter-spacing: -0.01em; }
  .head .hint { margin-left: auto; font-size: 0.75rem; color: var(--secondary-text-color); }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 14px;
    padding: 16px 18px 18px;
  }

  .tile {
    position: relative;
    border: 1px solid var(--divider-color);
    border-radius: 14px;
    padding: 14px 16px 12px;
    background:
      linear-gradient(180deg, rgba(224, 0, 116, 0.06), transparent 55%),
      var(--card-background-color);
    transition: box-shadow 140ms ease, border-color 140ms ease;
  }
  /* Bez transforma: pomicanje elementa pod mišem izaziva oscilaciju na samom rubu. */
  .tile:hover { border-color: rgba(224, 0, 116, .55); box-shadow: 0 6px 18px rgba(0,0,0,.16); }
  .tile.low { border-color: var(--error-color); box-shadow: 0 0 0 1px var(--error-color) inset; }
  .tile.offline { opacity: .55; }

  .who { display: flex; align-items: center; gap: 8px; min-width: 0; }
  .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--success-color, #43a047); flex: none; }
  .dot.bad { background: var(--error-color); }
  .dot.unknown { background: var(--secondary-text-color); }
  .name { font-weight: 600; font-size: .9rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .msisdn { margin: 2px 0 0 16px; font-size: .75rem; color: var(--secondary-text-color); }

  .hero { display: flex; align-items: baseline; gap: 6px; margin: 14px 0 0; }
  .hero .value {
    font-size: 2.1rem; font-weight: 700; letter-spacing: -0.03em; line-height: 1;
    font-variant-numeric: tabular-nums;
  }
  .tile.low .hero .value { color: var(--error-color); }
  .hero .unit { font-size: .95rem; font-weight: 500; color: var(--secondary-text-color); }
  .hero-label { margin-top: 4px; font-size: .72rem; text-transform: uppercase; letter-spacing: .08em; color: var(--secondary-text-color); }

  .stats { margin-top: 14px; display: grid; gap: 8px; }
  .stat { display: flex; align-items: center; gap: 10px; font-size: .86rem; }
  .stat ha-icon { --mdc-icon-size: 18px; color: var(--secondary-text-color); flex: none; }
  .stat .k { color: var(--secondary-text-color); }
  .stat .v { margin-left: auto; font-weight: 500; text-align: right; }

  .chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }
  .chip {
    font-size: .74rem; padding: 3px 9px; border-radius: 999px;
    background: rgba(224, 0, 116, .14); color: var(--primary-text-color);
    border: 1px solid rgba(224, 0, 116, .35);
  }
  .chip.none { background: transparent; border-color: var(--divider-color); color: var(--secondary-text-color); }

  .foot { margin-top: 12px; font-size: .7rem; color: var(--secondary-text-color); display: flex; justify-content: space-between; }
  .empty { padding: 22px 18px; color: var(--secondary-text-color); font-size: .9rem; }
  .empty b { color: var(--primary-text-color); }

  @media (prefers-reduced-motion: reduce) { .tile { transition: none; } }
`;

const ICONS = {
  valid_until: "mdi:calendar-check",
  usage: "mdi:web",
  tariff: "mdi:sim",
  status: "mdi:cellphone",
  prepaid: "mdi:cash",
};

class MojTelekomCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = { title: "Moj Telekom", low_balance: 3 };
    this._lastHtml = null;
  }

  setConfig(config) {
    this._config = { title: "Moj Telekom", low_balance: 3, ...config };
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 2 + 4 * Math.max(1, groupNumbers(this._hass || {}).length);
  }

  _stat(icon, label, value) {
    return value == null || value === ""
      ? ""
      : `<div class="stat"><ha-icon icon="${escapeHtml(icon)}"></ha-icon>
           <span class="k">${escapeHtml(label)}</span><span class="v">${escapeHtml(value)}</span></div>`;
  }

  _tile(group) {
    const { prepaid, usage, valid_until: until, options, status } = group;
    const balance = prepaid ? Number(prepaid.state) : NaN;
    const hasBalance = Number.isFinite(balance);
    const low = hasBalance && balance <= Number(this._config.low_balance);

    const heroValue = hasBalance ? fmtNumber(balance) : fmtNumber(usage?.state, 0);
    const heroUnit = hasBalance ? (prepaid.attributes.unit_of_measurement || "EUR") : "MB";
    const heroLabel = hasBalance ? "Stanje bona" : usage ? "Preostali promet" : "Nema podataka";

    const untilValue = until ? until.state : prepaid?.attributes.vrijedi_do;
    const optionNames = options
      ? options.state
      : (prepaid?.attributes.aktivne_opcije || []).map((option) => option.naziv);
    const chips = Array.isArray(optionNames) ? optionNames : (optionNames || "").split(", ").filter(Boolean);

    const statusState = status?.state;
    const dotClass = statusState == null ? "unknown" : statusState === "active" ? "" : "bad";
    const updated = relTime(status?.attributes.azurirano || prepaid?.attributes.azurirano);
    const national = fmtMsisdn(group.msisdn);

    // Vlastita oznaka/lokacija iz konfiguracije kartice ima prednost nad imenom uređaja.
    // Tada je broj glavni red, a lokacija ispod njega — pa se odmah zna koji je koji.
    const wanted = normalizeMsisdn(group.msisdn);
    const label = Object.entries(this._config.labels || {}).find(
      ([key]) => normalizeMsisdn(key) === wanted,
    )?.[1];
    const primary = label ? (national || group.msisdn || group.name) : group.name;
    const subtitle = label ? label : (national && !String(group.name).includes(national) ? national : "");

    return `<div class="tile${low ? " low" : ""}">
      <div class="who"><span class="dot ${dotClass}"></span>
        <span class="name" title="${escapeHtml(primary)}">${escapeHtml(primary)}</span></div>
      ${subtitle ? `<div class="msisdn">${escapeHtml(subtitle)}</div>` : ""}

      <div class="hero">
        <span class="value">${heroValue == null ? "—" : escapeHtml(heroValue)}</span>
        ${heroValue == null ? "" : `<span class="unit">${escapeHtml(heroUnit)}</span>`}
      </div>
      <div class="hero-label">${escapeHtml(heroLabel)}</div>

      <div class="stats">
        ${this._stat(ICONS.valid_until, "Vrijedi do", fmtDate(untilValue))}
        ${this._stat(ICONS.usage, "Preostali promet", usage ? `${fmtNumber(usage.state, 0)} MB` : null)}
        ${this._stat(ICONS.tariff, "Tarifa", prepaid?.attributes.tarifa)}
        ${this._stat(ICONS.status, "Status", statusState && statusState !== "active" ? statusState : null)}
      </div>

      <div class="chips">${
        chips.length
          ? chips.map((name) => `<span class="chip">${escapeHtml(name)}</span>`).join("")
          : `<span class="chip none">nema aktivnih opcija</span>`
      }</div>
      <div class="foot"><span>${escapeHtml(updated || "")}</span></div>
    </div>`;
  }

  _build() {
    const groups = groupNumbers(this._hass || {});
    const body = groups.length
      ? `<div class="grid">${groups.map((group) => this._tile(group)).join("")}</div>`
      : `<div class="empty">Još nema podataka. Provjeri da je integracija <b>Moj Telekom</b>
         dodana i da joj prvi dohvat nije pao (Dnevnik → moj_telekom).</div>`;
    return `<style>${STYLES}</style><ha-card>
      <div class="head"><ha-icon icon="mdi:cellphone-message"></ha-icon>
        <span class="title">${escapeHtml(this._config.title || "Moj Telekom")}</span>
        <span class="hint">${pluralBroj(groups.length)}</span>
      </div>
      ${body}
    </ha-card>`;
  }

  _render() {
    // DOM mijenjamo samo kad se sadržaj stvarno promijenio. HA šalje `hass` na svaku
    // promjenu stanja; bez ovoga se kartica ruši i po nekoliko puta u sekundi, pa
    // hover/animacije "tit raju".
    const html = this._build();
    if (html !== this._lastHtml) {
      this._lastHtml = html;
      this.shadowRoot.innerHTML = html;
    }
  }
}

const existing = customElements.get("moj-telekom-card");
if (existing) {
  // Najčešće znači da je negdje ostala stara kopija (npr. /local/moj-telekom-card.js
  // dodan kao Lovelace resurs) — prva registracija pobjedi, pa se vidi stari izgled.
  console.warn(
    "[Moj Telekom] kartica je već registrirana — vjerojatno postoji stara kopija kao " +
    "Lovelace resurs (Postavke → Dashboards → Resources). Obriši je i osvježi stranicu.",
    existing,
  );
} else {
  customElements.define("moj-telekom-card", MojTelekomCard);
}

// Da se kartica pojavi u izborniku kartica i bude dostupna za testiranje u konzoli.
window.customCards = window.customCards || [];
window.customCards.push({
  type: "moj-telekom-card",
  name: "Moj Telekom",
  description: "Bon, do kada vrijedi, preostali promet, tarifa i aktivne opcije za sve brojeve.",
  preview: false,
});
window.MojTelekomCard = MojTelekomCard;
// Izloženo i za testove (tests/card_check.mjs) i za brzu provjeru u konzoli browsera.
window.MojTelekomCard.groupNumbers = groupNumbers;
window.MojTelekomCard.fmtDate = fmtDate;
window.MojTelekomCard.fmtNumber = fmtNumber;
window.MojTelekomCard.fmtMsisdn = fmtMsisdn;
window.MojTelekomCard.relTime = relTime;
window.MojTelekomCard.pluralBroj = pluralBroj;
window.MojTelekomCard.normalizeMsisdn = normalizeMsisdn;
window.MojTelekomCard.version = MOJ_TELEKOM_VERSION;
