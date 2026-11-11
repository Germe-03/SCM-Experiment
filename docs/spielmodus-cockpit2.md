# Spielmodus Cockpit 2: Umbau nach Rückmeldung

Stand 12.11.2026. Alles in einem Zug umsetzen, am Schluss pushen.

## Rückmeldung des Nutzers (Kurzfassung)
Nicht alles auf einer Seite, sondern Reiter. Vergleich mit der Konkurrenz. Sehen, was passiert, wenn man eine Grösse ändert, und wofür sie steht. Kein Forschungsbudget: im Baum anschauen und wählen. Lieferkapazität und Nachfrage als Spanne von–bis. Lastwagen kaufen. Aktienkurse sehen und einzelne Aktien kaufen. Rohstoffpreise, Leitzins, Banken, Bevölkerung sehen – alles aus dem Experiment, ausser was einen unfairen Vorteil gäbe (z.B. Gewinn/Verlust der Konkurrenz). Marketingstrategie festlegen. Regeln brechen nicht als blosser Haken. Autopilot erklären: was passiert, wenn er an ist. Schweizer Karte. Dunkelmodus. Lieferant direkt wählen oder Regel (immer günstigster, beste Qualität …). Kredite aktiv aufnehmen. Positionierung nicht wählen: die Simulation stuft die Firma nach ihren Entscheiden ein.

## Was gute Managerspiele ausmacht (Recherche) und was wir daraus machen
- **Ursache und Wirkung sichtbar** (Spieler müssen sehen, was ihre Entscheide bewirken): Wirkungsprotokoll nach jeder Runde («Preis +10 % → Absatz −8 %, Umsatz +2 %»), Preis-Absatz-Grafik aus dem eigenen Verlauf, bei jedem Feld «Wofür» und «Was passiert, wenn …».
- **Übersicht auf einen Blick, Vertiefung per Klick** (Two Point Hospital, Football Manager): Reiter; Übersicht mit Ampel-Warnungen (Kasse knapp, Rückstand, Kapazität voll, Kein CEO); Details in eigenen Reitern.
- **Nicht zu viel auf einmal**: pro Reiter ein Thema, Erklärtexte einklappbar, Glossar im Reiter «Hilfe».
- **Sofortige Rückmeldung**: geplante Aufträge sofort als «geplant» sichtbar; Ergebnisse der Aufträge oben im nächsten Stand.
- **Posteingang wie im Football Manager**: Meldungen bleiben rechts, wichtige oben.

## Reiter
Übersicht · Firma · Markt · Forschung · Logistik · Finanzen · Börse · Rohstoffe · Bevölkerung · Holding · Graubereich · Hilfe. Rechts immer: Meldungen und Berater. Kopfzeile: Firmenname, Branche, Einstufung (z.B. «Discount»), Jahr/Monat, Hell/Dunkel-Schalter, Speichern. Unten fix: «Runde beenden», «Wie bisher weiter», «Firma verkaufen».

## Gemeinsame Schnittstellen

### PlayerChoices (market_sim/game/choices.py, fertig)
Neu: `marketing_focus` (0..1 Anteil Marke, Rest Laden/Lokal), `marketing_target` ("18-34"|"35-64"|"65+"|None), `supplier_id`, `supplier_rule` ("price"|"quality"|"reliability"|"lead_time"|None), `offences` als dict name→Intensität 0..1 (Liste bleibt gültig = 1.0), Methode `offence_intensity(name)`.
`research_target` bleibt (Baum-Wahl). Das Settings-Feld `r_and_d_budget` und `positioning` werden im Cockpit nicht mehr angeboten (Forschung kostet über den Baum; Einstufung macht die Simulation).

### Neue Aufträge (orders, wie Phase 4, ausgeführt am Halt)
- `"loan": {"amount": float, "bank_id": str|None}` – Kredit aufnehmen (Angebot der Bank, sonst Ablehnung mit Grund)
- `"truck": {"type": str, "mode": "buy"|"lease"}` – Lastwagen beim günstigsten Händler
- `"stock": {"buy": {firm_id: shares}, "sell": {firm_id: shares}}` – einzelne Aktien

### market_sim/game/actions.py
```python
def loan_offers(runner, firm_id, amount) -> list[dict]   # je aktive Bank: {"bank_id","bank","rate","years","ok","reason"}
def take_loan(runner, state, firm_id, amount, bank_id, year, day) -> dict  # {"ok","message"}
def truck_offers(runner, firm_id) -> list[dict]          # je Typ: {"type","label","capacity","price","annual_cost","life_years","lease_possible"}
def buy_truck(runner, state, firm_id, type_name, mode, year, day) -> dict
class Depot:   # Aktien der Spielerfirma (Spielebene, gehört der Session)
    shares: dict[str, float]; paid: dict[str, float]
    def buy(self, runner, firm_id_owner, target_id, shares) -> dict
    def sell(self, runner, firm_id_owner, target_id, shares) -> dict
    def positions(self, runner) -> list[dict]   # {"id","name","shares","price","value","paid","gain"}
    def pay_dividends(self, runner, state, owner_id) -> float   # am ersten Halt eines neuen Jahres
```

### market_sim/game/world*.py – Lese-Ansichten (nur öffentliche oder eigene Daten)
Alle Funktionen `(runner, state, player_id, **extra) -> dict`, JSON-fähig, deutsch beschriftet, nie Gewinn/Kasse fremder Firmen.
- world_market.py: `compare`, `capacity`, `market`, `suppliers`, `population`, `swiss_map`
- world_finance.py: `macro` (braucht `history` vom Controller), `banks` (mit `loan_offers` für `amount`), `stocks` (braucht `depot`), `commodities` (braucht `history`), `trucks`
- world_firm.py: `research_tree`, `autopilot`, `classification`, `glossary`

Formen (Felder mindestens):
- compare: `{"stage","rows":[{"id","name","is_player","branch","region","category","revenue","market_share","avg_price","quality","reputation","service_level","capacity_utilization","archetype","archetype_label","listed","stock_price","revenue_history":[...]}],"years":[...]}` – für die Spielerfirma zusätzlich `profit`.
- capacity: `{"capacity_per_day","truck_capacity","utilization_last_year","demand":{"min","max","avg"},"sales":{"min","max","avg"},"stage_demand":{"min","max","avg"},"inventory","backlog","days_of_stock"}`
- market: `{"categories":[{"name","share"}],"stage_capacity_per_day","stage_demand_per_day","firms_in_stage","price_band":{"min","max"},"rival_price"}`
- suppliers: `{"candidates":[{"id","name","price","quality","reliability","reputation","lead_time_days","region"}],"current":[ids],"rule","fixed"}`
- population: `{"persons","index","age_groups":[{"group","persons"}],"income_levels":[{"level","persons"}],"regions":[{"name","share","persons"}],"classes":[...]}`
- swiss_map: `{"outline":[[x,y],...],"regions":[{"name","x","y","share"}],"firms":[{"id","name","region","stage","branch","is_player","is_daughter"}]}` (Umriss = CH_OUTLINE aus dashboard.py)
- macro: `{"policy_rate","inflation","price_index","fx_rate","history":[{"label","policy_rate","inflation","fx_rate"}]}`
- banks: `{"banks":[{"id","name","margin","equity","capital_ratio","active"}],"accounts":{bank: share},"loans":[{"bank","amount","rate","years","remaining","purpose"}],"offers":[...loan_offers...],"credit_limit"}`
- stocks: `{"listed":[{"id","name","branch","price","change","market_cap","history":[...]}],"index","depot":[...positions...],"fee"}` (`history`: höchstens 60 Punkte)
- commodities: `{"current":[{"name","index","change"}],"electricity","history":[{"label", name: index ...}]}`
- trucks: `{"offers":[...truck_offers...],"fleet":[{"type","label","age_years","value"}],"transport_mode","dealers":[{"id","name"}]}`
- research_tree: `{"tree","stages":[{"name","label","branch","kind","cost","duration_days","effect","requires":[...],"status","depth","patentable"}],"running":{"stage","days_left"}|null}` status ∈ implemented|researched|running|available|locked
- autopilot: `{key: {"text": "Was der Autopilot tut", "value": aktueller Wert oder null}}` für marketing_budget, research_target, credit_mode, bank_id, payout_ratio, listing, transport_mode, auto_invest, commodity_courage, markup_factor, supplier
- classification: `{"archetype","label","explanation","history":[{"year","label"}]}`
- glossary: `{"terms":[{"term","text"}]}`

### Controller und Server (market_sim/game/controller.py, server.py)
- GET `/api/view/<name>` (Name wie oben, Query `amount` bei banks) → `controller.view(name, **query)`.
- State-JSON zusätzlich: `"effects"` (Wirkungsprotokoll, letzte 12 Runden: `{"label","changes":[Text],"deltas":{"sales","revenue","cash","price","demand"}}`), `"warnings"` (Ampel: `{"level":"rot"|"gelb","text"}`), `"classification"` (Label), `"depot_value"`.
- Controller führt pro Halt eine Makro-Historie (Leitzins, Teuerung, Wechselkurs, Rohstoffe, Strom).

## Simulation (bestehende Dateien, ohne Spieler unverändert)
- environment.py: `supplier_id` → nur dieser Lieferant, solange aktiv und Kandidat; `supplier_rule` → Bewertung stark nach diesem Kriterium.
- marketing.py (+ brands.py falls nötig): `marketing_focus` teilt das Budget Marke/Laden; `marketing_target` verstärkt die Wirkung in dieser Altersgruppe (×1.5) und schwächt die anderen (×0.75).
- state.py: Verstösse mit Intensität: Vorteil × Intensität; Entdeckungswahrscheinlichkeit × (0.4 + 0.6 × Intensität) pro Jahr; Busse wie bisher. Zufallsfolge ohne Spieler unverändert.

## Oberfläche (market_sim/game/static/)
- `cockpit.html`: Kopfzeile, Reiterleiste, je Reiter `<section id="tab-<key>" class="reiter-inhalt" hidden>`, rechte Spalte (Meldungen, Berater), Fusszeile mit Runden-Knöpfen, Spielende/Rückblick, Dialoge. Keys: uebersicht, firma, markt, forschung, logistik, finanzen, boerse, rohstoffe, bevoelkerung, holding, graubereich, hilfe.
- `cockpit.js` (Kern): Laden des Zustands, Reiterwechsel (Hash `#markt`), Hell/Dunkel-Schalter (`html[data-theme]`, localStorage, Standard = System), Runde beenden (sammelt settings, choices, orders), Übersicht, Reiter «Firma».
- Reiter-Module registrieren sich so (eigene Dateien):
```js
window.REITER = window.REITER || {};
REITER.markt = { async render(el, ctx) { ... } };
// ctx = {
//   state,                                  // aktueller State
//   ansicht: (name, query) => Promise<json>, // GET /api/view/<name>?...
//   plane: (key, value) => void,            // Auftrag für die nächste Runde (loan, truck, stock …); value null = weg
//   geplant: () => object,                  // alle geplanten Aufträge
//   entscheide: (patch) => void,            // geänderte choices für die nächste Runde (z.B. {supplier_rule:'price'})
//   geld, zahl, prozent,                    // Formatierer (de-CH, CHF mit Hochkomma)
//   linien: (series, optionen) => SVGElement // einfache Liniengrafik: series=[{name,werte:[...],farbe}], optionen={labels,hoehe}
//   neuZeichnen: () => void                 // aktuellen Reiter neu rendern
// }
```
  `render` wird bei jedem Öffnen des Reiters und nach jeder Runde aufgerufen.
- Farben nur über CSS-Variablen; Dunkelmodus via `[data-theme="dark"]` und `prefers-color-scheme`.
- Jedes Eingabefeld hat ein ⓘ mit «Wofür» und «Was passiert, wenn …» (Texte deutsch, einfach). Felder mit Autopilot zeigen den Autopilot-Text aus `/api/view/autopilot` und den aktuellen Autopilot-Wert.
