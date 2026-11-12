# Spielmodus – Feedback 2: Schnittstellen (verbindlich für alle Worker)

Deutsch mit Umlauten, nie ß. Mengen im Cockpit immer in **Flaschen**; intern rechnet die Simulation in
Einheiten zu `config.unit_scale.real_units_per_sim_unit` (10'000) Flaschen. Spielerfirmen erkennt die
Simulation an `getattr(runner, "player_choices", {})` bzw. `env.player_choices` (Schlüssel = firm id);
`market_sim.game` wird aus der Simulation nie importiert.

## 1. Übernahmen freiwillig (Simulation, gilt für ALLE Firmen)
- `state.takeovers`: Angeschlagene Firmen (bisherige Regel) kommen auf eine Verkaufsliste
  `runner.takeover_offers: list[dict]` = `[{"target": id, "name": str, "stage": str, "price": float,
  "year": int, "reason": str}]` (jedes Jahr neu gebaut).
- Jede mögliche Käuferin entscheidet selbst (eigene Funktion `wants_to_buy(runner, buyer, target, price)`):
  nur wenn Preis < Wert (z.B. Jahresgewinn-Potenzial/Kapazitätswert), Kasse ≥ cash_cover·Preis ohne Kredit
  (Kredit nur bei strategy.risk_tolerance ≥ 0.6 und Eigenkapital/Schulden tragbar) und mit einer
  Zufallsentscheidung aus eigenem RNG-Strom (keine Ziehung aus den bestehenden Strömen).
  Niemand will → Firma bleibt auf der Liste / geht den normalen Konkursweg.
- Spielerfirmen sind NIE automatische Käuferinnen und nie automatische Ziele (das Spiel regelt Konkurs selbst).
- Gleiches für automatische Beteiligungen (`holdings.py`) und Fusionen (`mergers.py`): Spielerfirmen nie automatisch.
- Neue Config-Felder mit Defaults in `config.py` (z.B. `takeover_bid_probability`).

## 2. Keine stillen Kredite für Spieler
- `PlayerChoices.credit_mode` Standard ist jetzt `"never"`. Wo die Simulation `arrange_funding` für eine
  Spielerfirma aufruft, gilt: bei "never" kein Kredit (Investition fällt aus).

## 3. Sortiment (Handelsfirmen)
- Neues Feld `PlayerChoices.category_shares: {kategorie: anteil}` (beer, wine, spirits, softdrinks, water).
- Liefert ein Lieferant an eine Spielerfirma, folgt die Markenmischung der Lieferung diesen Anteilen,
  soweit der Lieferant Ware hat (Rest wie bisher). Beim Verteiler steuert es `_split_by_category`.
- Neue Laufzeit-Abfrage `env.stock_by_category(firm_id) -> {kategorie: einheiten}`.

## 4. Abschlüsse und Kalkulation (neues Modul `market_sim/financials.py`)
- `income_statement(runner, firm_id, year=None) -> dict`:
  `{"year", "revenue", "cogs", "gross_profit", "wages", "rent_fixed", "handling", "storage", "marketing",
    "research", "other_opex", "ebitda", "depreciation", "ebit", "interest", "ebt", "taxes", "net_income"}`
  (CHF; year=None = laufendes Jahr bis heute).
- `balance_sheet(runner, firm_id) -> dict`: `{"assets": {"cash", "inventory", "trucks", "sites",
  "participations", "securities", "total"}, "liabilities": {"loans", "other", "total"},
  "equity": float, "total": float}` (negative Kasse → als Kontokorrent unter liabilities).
- `cash_flow(runner, firm_id, year=None) -> dict`: `{"operating", "investing", "financing",
  "dividends_received", "dividends_paid", "change"}`.
- `ratios(...) -> {"gross_margin", "ebit_margin", "equity_ratio", "liquidity", "roe"}`.
- `annual_report(runner, firm_id, year) -> dict` = alles zusammen für ein abgeschlossenes Jahr;
  der Runner speichert am Jahresende `runner.annual_reports[year][firm_id]` (alle Firmen).
- `calculation(runner, firm_id) -> dict` pro Flasche: `{"purchase_price", "procurement_costs",
  "landed_cost", "overhead", "full_cost", "sell_price", "profit", "margin_pct", "break_even_price",
  "bottles_per_day"}` (Hersteller: purchase_price = Rohstoffe+Produktion pro Flasche).
- Dashboard: neuer Bereich «Abschlüsse» mit Erfolgsrechnung, Bilanz, Geldfluss und Kennzahlen je Firma.

## 5. Spiel-Backend
- Neue Ansichten (`/api/view/<name>`): `financials` (eigene Firma: income_statement laufendes Jahr +
  letztes volles Jahr, balance_sheet, cash_flow, ratios), `reports` (alle anderen Firmen: nur letzter
  veröffentlichter `annual_report`, `{"year", "firms": [{"id","name","stage", ...report}]}`),
  `calculation` (siehe oben, in CHF pro Flasche), `pricing` (`{"purchase_price", "sell_price",
  "margin_per_bottle", "margin_pct", "overhead_per_bottle", "profit_per_bottle", "break_even_price",
  "history": [{"label", "purchase", "sell"}]}`), `takeover_offers` (`{"offers": [...]}` aus runner.takeover_offers),
  `assortment` (`{"categories": [{"key","name","share_market","share_mine","stock_bottles"}]}`).
- `state()`: `kpis.revenue_last_year`, `kpis.profit_last_year`; `month_name` ("Januar"…);
  `years_total`, `years_left`; `end_reason_text` (Klartext); Preise auf 2 Stellen gerundet.
- `settings.order_qty` und Auftrag `expand` kommen vom Cockpit in **Flaschen**; der Controller rechnet
  in Einheiten um (aufrunden) und gibt sie in Flaschen zurück.
- Neuer Endpunkt `POST /api/check` mit `{settings, choices, orders}` → `{"warnings": [{"level":
  "rot"|"gelb", "text"}]}` (Menge ≫ Absatz/Kapazität, Preis unter Selbstkosten oder Marge −30 %,
  Lager leer, Kauf ohne Geld …). Das Cockpit ruft ihn vor «Runde beenden».
- Meldungen (`messages`): jede Übernahme, jeder Kredit, jede Dividende (rein/raus) mit Betrag;
  Tochter ohne CEO: Klartext + `{"action": "ceo", "firm": id}`; Verkaufsangebot einer angeschlagenen Firma.
- Spieldauer: `new_game(..., years=10)` (wählbar 5/10/20/30), Jahr immer 360 Tage (Server-Standard),
  Warnung «noch 1 Jahr» als Meldung. Optionen liefern `years_choices` und `region_labels` ({id: Name}).
- Server: alle statischen Dateien mit `Cache-Control: no-store`.

## 6. Cockpit
- Alles aus 1–5 anzeigen; Platzhalter «kommt gleich» ersetzen durch Fehlermeldung «… Ctrl + F5»;
  Kopfzeile darf Inhalt nicht überdecken; Streudiagramm mit Rand; Spielende: Klartext, Rückblick,
  Rundenknöpfe weg; Konkurs deutlich; Regionen deutsch; Kategorie bei der Gründung nur für Hersteller.
