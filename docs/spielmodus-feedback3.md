# Spielmodus – Feedback 3: Schnittstellen (verbindlich)

Deutsch mit Umlauten, nie ß. Cockpit-Mengen in Flaschen (unit_size = config.unit_scale.real_units_per_sim_unit).
Spielerfirmen: `getattr(runner, "player_choices", {})` / `env.player_choices`; Simulation importiert nie `market_sim.game`.
Neue Felder in `PlayerChoices` (existieren schon): component_plan, brand_plan, storage_order,
cancel_open_orders, daughter_rules. Grundsatz: Cockpit-Ansichten wie im Beobachter-Dashboard lösen
(dashboard_*.js als Vorlage, Chart.js).

## A. Simulation – environment.py / config.py
1. **Rohstoffe Hersteller:** Hat die Spielerfirma `component_plan {name: menge_pro_tag}`, kauft sie täglich
   genau diese Mengen (Preis = heutiger Komponentenpreis) statt automatisch. Fehlt ein Rohstoff im Lager,
   wird weniger produziert (bestehende Logik). Hilfsfunktion `env.component_need(firm_id, bottles_per_day)
   -> {name: menge_pro_tag}` (aus config amounts der Kategorie), `env.component_stock(firm_id) -> {name: menge}`,
   `env.component_prices(firm_id) -> {name: preis_pro_einheit}`.
2. **Lagerplatz** (alle Firmen haben eine Kapazität, wirkt nur für Spielerfirmen): `env.storage_capacity(firm_id)`
   und `env.storage_used(firm_id)` in Flaschen-Äquivalenten (Fertigware in Flaschen + Rohstoffe über
   `config.storage.space_per_component` je Einheit). Start-Kapazität = `config.storage.start_days` × Kapazität/Tag.
   Über der Kapazität: Zusatzmiete `config.storage.overflow_cost_per_bottle_day`. `storage_order` (Flaschen) baut
   für `config.storage.build_cost_per_bottle` aus (einmalig, dann None).
3. **Lieferungen:** je (Käufer, Lieferant) `env.delivery_book[firm_id][supplier_id] = {"ordered", "delivered", "open"}`
   in Einheiten (laufendes Jahr + seit Start). `cancel_open_orders=True` storniert offene Bestellungen der
   Spielerfirma (on_order/Pipeline beim Lieferanten abbauen, keine Kosten), dann None.
4. **Regal-Fixkosten (nur Spielerfirmen):** Händler zahlen je geführte Getränkeart (Lager > 0 oder brand_plan > 0)
   `config.storage.category_fixed_cost_per_year` (anteilig pro Tag). So lohnt Spezialisierung.
5. **Tochter-Regeln:** `daughter_rules[tochter_id]["no_credit"]` → arrange_funding für diese Firma ohne Kredit.

## B. Simulation – brands.py
`brand_plan {brand_id: flaschen_pro_tag}` einer Spielerfirma: Bestellungen und Lieferungen folgen der
Markenmischung (soweit Lieferant Ware hat). Hilfen: `book.brand_catalog(runner, firm_id) -> [{"id","name",
"category","owner","owner_name","positioning","value","quality","reputation","price","demand_share"}]`,
`book.demand_by_category(runner, region=None) -> {kategorie: flaschen_pro_tag}`.

## C. Spiel-Backend (market_sim/game/*, holdings.py, stock_market.py)
- Spiel läuft auf dem vollen Experiment (config.simulation.years, 50 Jahre). Die **Spielzeit** (years_total)
  endet nach der gewählten Dauer: dann wird die Spielerfirma wie beim Verkauf an den Autopiloten übergeben
  (Grund "ende"), die Simulation läuft bis Jahr 50 im Hintergrund weiter, danach
  `build_dashboard_data` + `write_dashboard_html` nach `runs/spiele/<zeit>_<firma>/dashboard.html`.
  Gilt auch für Verkauf und Konkurs. state: `dashboard_status` ("laeuft" | "fertig" | "fehler" | None),
  `dashboard_progress` (Jahr), `dashboard_url` ("/dashboard"). Server liefert `/dashboard` (die HTML-Datei).
- `POST /api/skip_year` {settings, choices, orders}: erste Runde mit diesen Eingaben, dann ohne Halt bis zum
  ersten Halt im nächsten Jahr (oder Spielende). Antwort = state.
- `POST /api/reset` → Spiel beenden ohne Speichern, zurück zur Gründung (state ohne Spiel).
- Prüfung `/api/check`: alles in Flaschen; vor dem ersten Verkauf Vergleich mit Kapazität/Nachfrage; kein
  «Lager leer», wenn Lieferungen unterwegs; Zahlen mit Tausendertrennung (1'234).
- Einstufung erst nach Jahr 1 (vorher "Noch nicht eingestuft – erste Einstufung Ende Jahr 1").
- Engpass-Text branchengerecht (Händler: Bestellmenge/Lieferant, Hersteller: Rohstoffe/Produktion);
  `bottleneck.utilization_now` (0..1) und `idle_cost_per_bottle` (Gemeinkosten-Anteil der Leerkapazität).
- Neue Ansichten: `purchasing` (Hersteller: {"target_bottles","need": {name: menge}, "stock", "prices",
  "history": [{"label", name: preis…}], "storage": {"capacity","used"}}; Händler: {"categories":
  [{"key","name","demand_per_day","rival_cover"}], "brands": brand_catalog, "plan", "storage"}),
  `deliveries` ({"suppliers": [{"id","name","ordered","delivered","open","fill_rate"}]} in Flaschen),
  `daughters` ({"rows": [{"id","name","price_paid","received","value_now","debt","return_per_year",
  "rules"}]}), `stocks_all` (alle Firmen inkl. Banken/Lastwagenhandel: {"firms":[{"id","name","branch",
  "listed"}], "series": {id: [{"day","price"}]}} – gleiche Daten wie Dashboard-Börse).
- Meldungen: Unterlieferung (fill_rate < 90 % über einen Monat) mit Rat; Tochter nimmt Kredit / kauft Anteile;
  Reserve-Abschöpfung mit Hinweis wenn Tochter danach im Minus; Verkaufsangebote gebündelt zu einer Meldung.
- `holdings.py`: Tochter mit `daughter_rules.no_stakes` kauft keine Beteiligungen.
- `stock_market.py`: Startbewertung prüfen – Kurse fallen heute in den ersten Tagen steil (Startkurs zu hoch).

## D. Cockpit (static/*)
Börse wie Dashboard (Liste links mit Häkchen, grosses Diagramm rechts, `stocks_all`); Einkauf Hersteller
(Produktionsziel → Bedarf → Bestellfelder, Kurse, Lageranzeige «danach X % voll»); Einkauf Händler
(Nachfrage je Getränkeart, Marken mit Menge, Regal-Fixkosten-Hinweis, kein Qualitätsfeld); Lieferungen;
Tochter-Rendite + Verbote; Knöpfe «Rest des Jahres überspringen» und «Neues Spiel»; nach Spielende
Fortschritt «Simulation läuft bis Jahr 50: Jahr X» und dann Link/Knopf «Dashboard öffnen».
