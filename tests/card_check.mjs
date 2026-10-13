/**
 * Provjera logike kartice bez browsera: DOM stubovi + lažni `hass`.
 * Pokreće se iz pytest-a (tests/test_card.py), a može i direktno: `node tests/card_check.mjs`.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

class HTMLElementStub {
  constructor() {
    this.shadowRoot = { innerHTML: "" };
  }
  attachShadow() {
    return this.shadowRoot;
  }
}

globalThis.HTMLElement = HTMLElementStub;
globalThis.window = globalThis;
globalThis.customElements = { define: () => {}, get: () => undefined };

const cardPath = join(
  dirname(fileURLToPath(import.meta.url)),
  "..", "custom_components", "moj_telekom", "www", "moj-telekom-card.js",
);
eval(readFileSync(cardPath, "utf8")); // kartica se izlaže na window.* (i za konzolu i za test)

const Card = globalThis.MojTelekomCard;
assert.ok(Card, "kartica nije izložila MojTelekomCard");

const hass = {
  devices: { dev1: { name: "385991234567" } },
  entities: {
    "sensor.a": { entity_id: "sensor.a_prepaid_stanje", platform: "moj_telekom", device_id: "dev1" },
    "sensor.b": { entity_id: "sensor.a_potrosnja_data", platform: "moj_telekom", device_id: "dev1" },
    "sensor.c": { entity_id: "sensor.a_status", platform: "moj_telekom", device_id: "dev1" },
    "sensor.d": { entity_id: "sensor.drugi", platform: "druga_integracija", device_id: "dev2" },
  },
  states: {
    "sensor.a_prepaid_stanje": {
      state: "3.62",
      attributes: {
        device_class: "monetary", msisdn: "385991234567", tarifa: "Simpa",
        vrijedi_do: "2027-01-10", aktivne_opcije: [{ naziv: "Internet Tjedan", vrijedi_do: null }],
      },
    },
    "sensor.a_potrosnja_data": { state: "52440.43", attributes: { unit_of_measurement: "MB" } },
    "sensor.a_status": { state: "active", attributes: { msisdn: "385991234567" } },
    "sensor.drugi": { state: "1", attributes: {} },
  },
};

// 1) grupiranje: samo naši entiteti, jedan broj
const groups = Card.groupNumbers(hass);
assert.equal(groups.length, 1, "mora biti točno jedna grupa (tuđi entitet se ignorira)");
assert.equal(groups[0].msisdn, "385991234567");
assert.equal(groups[0].name, "385991234567");
assert.ok(groups[0].prepaid && groups[0].usage && groups[0].status, "sve tri vrste senzora morale su se prepoznati");

// 2) prepoznavanje po device_class/unit, ne po imenu entiteta (preživi preimenovanje)
const renamed = structuredClone(hass);
renamed.entities["sensor.a"].entity_id = "sensor.preimenovan_prepaid_stanje";
renamed.states["sensor.preimenovan_prepaid_stanje"] = renamed.states["sensor.a_prepaid_stanje"];
delete renamed.states["sensor.a_prepaid_stanje"];
assert.ok(Card.groupNumbers(renamed)[0].prepaid, "prepoznavanje mora raditi i nakon preimenovanja");

// 3) formatiranje
assert.match(Card.fmtDate("2027-01-10"), /10\.?\s*0?1\.?\s*2027/, "datum u hrvatskom zapisu");
assert.equal(Card.fmtDate(null), null);
assert.equal(Card.fmtNumber("nepoznato"), null);

// 4) render: bon, crveno kad je nizak, MB, tarifa i opcije
const card = new Card();
card.setConfig({ title: "Moj Telekom" });
card.hass = hass;
const html = card.shadowRoot.innerHTML;
assert.match(html, /Moj Telekom/);
assert.match(html, /3,62 EUR/, "bon u hrvatskom zapisu");
assert.doesNotMatch(html, /class="low"/, "bon 3.62 EUR uz prag 3 ne smije biti crven");
assert.match(html, /Tarifa/);
assert.match(html, /Internet Tjedan/);
assert.doesNotMatch(html, /druga_integracija/, "tuđi entiteti ne smiju u karticu");

// prag: bon 2.5 EUR mora biti crven
const lowCard = new Card();
lowCard.setConfig({ low_balance: 3 });
lowCard.hass = {
  ...hass,
  states: { ...hass.states, "sensor.a_prepaid_stanje": { ...hass.states["sensor.a_prepaid_stanje"], state: "2.5" } },
};
assert.match(lowCard.shadowRoot.innerHTML, /class="low"/, "bon 2.5 EUR uz prag 3 mora biti crven");

// 5) prazno stanje
const empty = new Card();
empty.setConfig({});
empty.hass = { entities: {}, states: {}, devices: {} };
assert.match(empty.shadowRoot.innerHTML, /Još nema podataka/);

console.log("kartica: sve provjere prošle");
