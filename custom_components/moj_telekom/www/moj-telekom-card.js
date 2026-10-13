/**
 * Moj Telekom kartica — dolazi s integracijom, nije potreban HACS frontend ni ručno
 * dodavanje resursa. Prikazuje sve brojeve: bon, do kada vrijedi, preostali promet,
 * tarifu, aktivne opcije i status.
 *
 * Entitete nalazi sama (preko `hass.entities`, platforma `moj_telekom`) i grupira ih po
 * uređaju, pa je dovoljno upisati:
 *   type: custom:moj-telekom-card
 */

const MOJ_TELEKOM_VERSION = "0.4.0";

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
  ha-card { padding: 16px; }
  .title { margin: 0 0 8px; font-size: 1.1rem; font-weight: 500; }
  .number { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--divider-color); }
  .number:first-of-type { margin-top: 0; padding-top: 0; border-top: none; }
  .name { font-weight: 600; }
  .msisdn { color: var(--secondary-text-color); font-size: 0.85rem; }
  dl { display: grid; grid-template-columns: auto 1fr; gap: 2px 16px; margin: 8px 0 0; }
  dt { color: var(--secondary-text-color); }
  dd { margin: 0; text-align: right; }
  .low { color: var(--error-color); font-weight: 600; }
  .empty { color: var(--secondary-text-color); }
`;

class MojTelekomCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = { title: "Moj Telekom", low_balance: 3 };
  }

  setConfig(config) {
    this._config = { title: "Moj Telekom", low_balance: 3, ...config };
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 1 + 4 * Math.max(1, groupNumbers(this._hass || {}).length);
  }

  _row(label, value, className) {
    return value == null || value === ""
      ? ""
      : `<dt>${escapeHtml(label)}</dt><dd${className ? ` class="${className}"` : ""}>${escapeHtml(value)}</dd>`;
  }

  _optionsText(group) {
    if (group.options) return group.options.state;
    const raw = group.prepaid?.attributes.aktivne_opcije;
    return raw?.length ? raw.map((option) => option.naziv).join(", ") : null;
  }

  _numberBlock(group) {
    const { prepaid, usage, valid_until: until, status } = group;
    const balance = prepaid ? Number(prepaid.state) : NaN;
    const low = Number.isFinite(balance) && balance <= Number(this._config.low_balance);
    const untilValue = until ? until.state : prepaid?.attributes.vrijedi_do;
    const rows = [
      this._row("Bon", prepaid ? `${fmtNumber(balance)} EUR` : null, low ? "low" : ""),
      this._row("Vrijedi do", fmtDate(untilValue)),
      this._row("Preostali promet", usage ? `${fmtNumber(usage.state, 0)} MB` : null),
      this._row("Tarifa", prepaid?.attributes.tarifa),
      this._row("Aktivne opcije", this._optionsText(group)),
      this._row("Status", status && status.state !== "active" ? status.state : null),
    ].join("");
    return `<div class="number">
      <div class="name">${escapeHtml(group.name)}</div>
      <div class="msisdn">${escapeHtml(group.msisdn || "")}</div>
      <dl>${rows}</dl>
    </div>`;
  }

  _render() {
    const groups = groupNumbers(this._hass || {});
    const body = groups.length
      ? groups.map((group) => this._numberBlock(group)).join("")
      : `<div class="empty">Još nema podataka. Provjeri da je integracija <b>Moj Telekom</b> dodana i da joj prvi dohvat nije pao (Dnevnik → moj_telekom).</div>`;
    this.shadowRoot.innerHTML = `<style>${STYLES}</style><ha-card>
      ${this._config.title ? `<h1 class="title">${escapeHtml(this._config.title)}</h1>` : ""}
      ${body}
    </ha-card>`;
  }
}

customElements.define("moj-telekom-card", MojTelekomCard);

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
window.MojTelekomCard.version = MOJ_TELEKOM_VERSION;
