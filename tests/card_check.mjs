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

const MINUTE = 60 * 1000;
const ENTRY = "entry123";
const entity = (feature) => ({
  entity_id: `sensor.b${feature}`,
  unique_id: `${ENTRY}_385991234567_${feature}`,
  platform: "moj_telekom",
  device_id: "dev1",
});

const hass = {
  devices: { dev1: { name: "Moj Telekom 099 1234567" } },
  // kao u HA: hass.entities je rječnik po entity_id
  entities: Object.fromEntries(
    ["prepaid", "usage", "valid_until", "options", "status"]
      .map((feature) => [entity(feature).entity_id, entity(feature)])
      .concat([["sensor.drugi", { entity_id: "sensor.drugi", unique_id: "x", platform: "druga_integracija", device_id: "dev2" }]]),
  ),
  states: {
    "sensor.bprepaid": {
      state: "3.62",
      attributes: {
        device_class: "monetary", feature: "prepaid", unit_of_measurement: "EUR",
        msisdn: "385991234567", tarifa: "Simpa", vrijedi_do: "2027-01-10",
        aktivne_opcije: [{ naziv: "Internet Tjedan", vrijedi_do: null }],
        azurirano: new Date(Date.now() - 7 * MINUTE).toISOString(),
      },
    },
    "sensor.busage": { state: "52440.43", attributes: { feature: "usage", unit_of_measurement: "MB" } },
    "sensor.bvalid_until": { state: "2027-01-10", attributes: { feature: "valid_until", device_class: "date" } },
    "sensor.boptions": { state: "Internet Tjedan", attributes: { feature: "options" } },
    "sensor.bstatus": { state: "active", attributes: { feature: "status", msisdn: "385991234567" } },
    "sensor.drugi": { state: "1", attributes: {} },
  },
};

// 1) grupiranje: samo naši entiteti, jedan broj, ispravno razvrstane značajke
const groups = Card.groupNumbers(hass);
assert.equal(groups.length, 1, "mora biti točno jedna grupa (tuđi entitet se ignorira)");
assert.equal(groups[0].msisdn, "385991234567");
for (const feature of ["prepaid", "usage", "valid_until", "options", "status"]) {
  assert.ok(groups[0][feature], `značajka ${feature} mora biti prepoznata`);
}

// 2) prepoznavanje preživi preimenovanje entity_id (feature atribut ostaje)
const renamed = structuredClone(hass);
const movedEntry = renamed.entities["sensor.bprepaid"];
delete renamed.entities["sensor.bprepaid"];
movedEntry.entity_id = "sensor.moj_preimenovani_bon";
renamed.entities[movedEntry.entity_id] = movedEntry;
renamed.states["sensor.moj_preimenovani_bon"] = renamed.states["sensor.bprepaid"];
delete renamed.states["sensor.bprepaid"];
assert.ok(Card.groupNumbers(renamed)[0].prepaid, "prepoznavanje ide po atributu feature, ne po imenu");

// 3) formatiranje
assert.match(Card.fmtDate("2027-01-10"), /10\.?\s*0?1\.?\s*2027/, "datum u hrvatskom zapisu");
assert.equal(Card.fmtDate(null), null);
assert.equal(Card.fmtNumber("nepoznato"), null);
assert.equal(Card.fmtMsisdn("385991234567"), "099 1234567");
assert.equal(Card.relTime(new Date(Date.now() - 5 * MINUTE).toISOString()), "prije 5 min");
assert.equal(Card.relTime(new Date(Date.now() - 3 * 60 * MINUTE).toISOString()), "prije 3 h");
assert.equal(Card.relTime(new Date(Date.now() - 2 * 24 * 60 * MINUTE).toISOString()), "prije 2 d");

// 4) render: hero bon, stat pločice, chips, starost podataka
const card = new Card();
card.setConfig({ title: "Moj Telekom" });
card.hass = hass;
const html = card.shadowRoot.innerHTML;
assert.match(html, /Moj Telekom/);
assert.match(html, /class="value">3,62</, "bon je veliki hero broj");
assert.match(html, /class="unit">EUR</, "valuta uz bon");
assert.match(html, /Stanje bona/, "oznaka hero vrijednosti");
assert.match(html, /Vrijedi do<\/span><span class="v">10\.\s?01\.\s?2027/, "datum do kojeg vrijedi");
assert.match(html, /Preostali promet/);
assert.match(html, /Tarifa/);
assert.match(html, /class="chip">Internet Tjedan</, "opcije su chips");
assert.match(html, /prije 7 min/, "starost podataka");
assert.doesNotMatch(html, /druga_integracija/, "tuđi entiteti ne smiju u karticu");
assert.doesNotMatch(html, /tile low/, "bon 3.62 EUR uz prag 3 ne smije biti crven");

// 5) prag za nizak bon
const lowCard = new Card();
lowCard.setConfig({ low_balance: 3 });
lowCard.hass = {
  ...hass,
  states: { ...hass.states, "sensor.bprepaid": { ...hass.states["sensor.bprepaid"], state: "2.5" } },
};
assert.match(lowCard.shadowRoot.innerHTML, /class="tile low"/, "bon 2.5 EUR uz prag 3 mora biti crven");

// 6) bez senzora opcija: fallback na atribut + "nema aktivnih opcija"
const noOptions = structuredClone(hass);
delete noOptions.entities["sensor.boptions"];
delete noOptions.states["sensor.boptions"];
const attrCard = new Card();
attrCard.setConfig({});
attrCard.hass = noOptions;
assert.match(attrCard.shadowRoot.innerHTML, /class="chip">Internet Tjedan</, "fallback na atribut aktivne_opcije");

const emptyOptions = structuredClone(noOptions);
emptyOptions.states["sensor.bprepaid"].attributes.aktivne_opcije = [];
const emptyChipsCard = new Card();
emptyChipsCard.setConfig({});
emptyChipsCard.hass = emptyOptions;
assert.match(emptyChipsCard.shadowRoot.innerHTML, /nema aktivnih opcija/);

// 7) broj se ne ponavlja ispod naziva ako je uređaj nazvan po broju
const namedByNumber = structuredClone(hass);
namedByNumber.devices.dev1.name = "Moj Telekom 099 1234567";
const prettyCard = new Card();
prettyCard.setConfig({});
prettyCard.hass = namedByNumber;
assert.doesNotMatch(prettyCard.shadowRoot.innerHTML, /<div class="msisdn">[^<]/, "broj se ne smije ponavljati");
// a ako je uređaj preimenovan, broj se prikazuje
const renamedDevice = structuredClone(hass);
renamedDevice.devices.dev1.name = "Markov mobitel";
const renamedCard = new Card();
renamedCard.setConfig({});
renamedCard.hass = renamedDevice;
assert.match(renamedCard.shadowRoot.innerHTML, /099 1234567/, "preimenovan uređaj mora pokazati broj (nacionalni zapis)");

// 8) prazno stanje
const empty = new Card();
empty.setConfig({});
empty.hass = { entities: {}, states: {}, devices: {} };
assert.match(empty.shadowRoot.innerHTML, /Još nema podataka/);

// 9) broj brojeva u zaglavlju + hrvatski plural
assert.match(html, /1 broj/, "zaglavlje prikazuje broj brojeva");
assert.equal(Card.pluralBroj(1), "1 broj");
assert.equal(Card.pluralBroj(3), "3 broja");
assert.equal(Card.pluralBroj(5), "5 brojeva");
assert.equal(Card.pluralBroj(21), "21 broj");
assert.equal(Card.pluralBroj(22), "22 broja");
assert.equal(Card.pluralBroj(11), "11 brojeva");

console.log("kartica: sve provjere prošle");
