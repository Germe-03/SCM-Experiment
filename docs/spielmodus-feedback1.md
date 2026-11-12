# Spielmodus – Feedback 1: Schnittstellen

Ursache der «Millionenverluste»: 1 Simulationseinheit = `config.unit_scale.real_units_per_sim_unit`
(10'000) Flaschen. Franken sind echte Franken, Stückzahlen im Cockpit waren aber Simulationseinheiten
und `revenue_year` war Preis × Tagesabsatz. Ab jetzt zeigt das Cockpit Flaschen.

## Controller (`controller.py`)
- `state()["unit_size"]`: int, Flaschen pro Simulationseinheit.
- `kpis`: `inventory`, `backlog`, `recent_demand`, `recent_sales` in **Flaschen** (× unit_size);
  `revenue_year` = echter Umsatz des laufenden Jahres in CHF (Laufzeit-Umsatz minus Stand zu Jahresbeginn);
  neu `profit_year` (gleich berechnet), `capacity_per_day` in Flaschen.
- `history`-Einträge: `sales`, `demand`, `inventory`, `backlog` ebenfalls in Flaschen.
- Marktkategorien deutsch: beer→Bier, wine→Wein, spirits→Spirituosen, softdrinks→Softdrinks,
  water→Wasser (überall, wo der Controller Kategorienamen an die Ansichten gibt).
- Neue Ansichten in `VIEWS`:
  - `costs` → `world_firm.costs(runner, firm_id)`:
    `{"year": int, "unit_size": int, "revenue_year": float, "profit_year": float,
      "items": [{"key": str, "label": str, "chf_year": float, "share": float}]}`
    keys: purchase (Wareneinkauf), wages (Löhne), fixed (Miete und Fixkosten), handling (Umschlag),
    holding (Lagerkosten), backlog (Lieferrückstand), hiring (Einstellungen), rnd (Forschung),
    marketing, interest (Zinsen). share = Anteil am Umsatz (0..), sortiert absteigend nach chf_year.
  - `bottleneck` → `world_firm.bottleneck(runner, firm_id)`:
    `{"kind": "personal"|"lager"|"transport"|"nachfrage", "text": str (Deutsch, ein Satz mit Rat),
      "capacity_per_day": float, "demand_per_day": float, "sales_per_day": float,
      "transport_per_day": float|None, "days_of_stock": float}` alle Mengen in Flaschen.
- `trucks`-Ansicht: jedes Angebot zusätzlich `extra_sales_per_day` (Flaschen, ≥0),
  `extra_profit_year` (CHF, kann negativ sein), `payback_years` (float oder None = lohnt sich nie),
  `advice` (Deutsch, z.B. «Dein Engpass ist Personal, nicht Transport. Dieser Lastwagen erhöht deinen Absatz nicht.»).
- `stocks`-Ansicht: `note` (str|None, Deutsch: warum leer / ab wann), `index_history`
  (`[{"label": "Jahr 1, Monat 2", "value": float}]`).

## Einkauf bei mehreren Lieferanten
`PlayerChoices.supplier_shares: {firm_id: anteil}` – die Bestellung wird anteilig aufgeteilt
(normalisiert, unbekannte/inaktive Lieferanten weg; ist nichts übrig: Verhalten wie bisher).
Die Ansicht `suppliers` liefert die Kandidaten (id, name, price, quality, reliability, lead_time).

## Risiko weg
`PlayerSettings.risk_tolerance` bleibt intern auf 0.5 und ist im Cockpit nicht mehr sichtbar.
Für Spielerfirmen ersetzt:
- Kuriere: `courier_preference` "cheap" (wie Risiko 1) | "reliable" (wie Risiko 0) | None (0.5)
- Patentklagen: `patent_lawsuits` True (1) | False (0) | None (0.5)
- Rohstoff-Vorrat: `commodity_courage` (gibt es schon), Kredit: `credit_mode` (gibt es schon),
  Ausbau: `auto_invest` (gibt es schon), Regelbrüche: nur über `offences` (gibt es schon).
- Preis- und Überstunden-Schub aus `policies.py` gilt nie für Spielerfirmen.
