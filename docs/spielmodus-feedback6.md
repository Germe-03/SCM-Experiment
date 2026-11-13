# Spielmodus – Feedback 6 (verbindlich)

Deutsch mit Umlauten, nie ß. Flaschen = Einheiten × config.unit_scale.real_units_per_sim_unit.

## A. Hersteller: Reiter «Produktion» (ersetzt «Einkauf» beim Hersteller)
- Produziert wird immer so viel, wie Kapazität und Rohstofflager zulassen. PlayerPolicy (Hersteller):
  order_qty = effektive Tageskapazität (env._effective_capacity); environment kürzt wie heute auf das, was
  Rohstoffe/Geld erlauben. Kein Lagerziel, keine feste Menge mehr (Karte «Produktion» im Firma-Reiter weg).
- Neue Ansicht `production`:
  `{"capacity_per_day": flaschen, "producible_per_day": flaschen (min aus Kapazität und Rohstoffen für 1 Tag),
    "materials": [{"name","label","stock","need_per_day_at_capacity","price","price_trend": "günstig"|"teuer"|"im Schnitt",
                   "cost_per_bottle"}],
    "cost_per_bottle": {"materials","energy","wages","fixed","handling","total"},  # zu aktuellen Marktpreisen
    "sell_price", "margin_per_bottle", "break_even_price",
    "orders_per_day" (Bestellungen der Kunden), "stock_bottles", "days_of_cover"}`
- Verkaufspreis wird im Reiter Produktion gesetzt (settings.base_price), Knopf «Preis um x % ändern» und
  «Preis = Kosten + x %».

## B. Lieferverträge (Deals) – neues Modul `market_sim/contracts.py`
- Erlaubte Paare (Lieferant → Kunde): Hersteller → Verteiler, Verteiler → Grosshändler, Grosshändler → Detailhändler/Gastro.
  Nicht: Detailhandel/Gastro mit Bevölkerung, Hersteller mit Rohstoffmarkt.
- Vertrag: `{"id","supplier","buyer","category" (oder null = alle),"units_per_day","price" (CHF/Flasche),
  "start_day" (global), "days","status": "angeboten"|"aktiv"|"abgelehnt"|"beendet","proposed_by"}`.
- `runner.contracts: ContractBook` mit `propose(...)`, `accept(id)`, `decline(id)`, `cancel(id)`, `active_for(firm_id)`.
- Wirkung im environment (nur aktive Verträge, sonst alles unverändert, keine neuen Zufallsziehungen für Firmen ohne
  Vertrag): Bestellt der Kunde, geht die Vertragsmenge zuerst an den Vertragslieferanten; der Lieferant beliefert
  Vertragskunden zuerst; Umsatz/Einkauf zum Vertragspreis. Liefert er weniger, zählt das als Unterlieferung.
- KI-Firmen: (1) entscheiden über Vorschläge des Spielers: annehmen, wenn Preis höchstens 5 % schlechter als ihr
  Marktpreis und Menge ≤ 50 % ihrer Kapazität (deterministisch aus eigenem RNG-Strom); (2) schlagen dem Spieler
  gelegentlich selbst Verträge vor (einmal pro Quartal höchstens 2 Angebote, eigener RNG-Strom). KI-KI-Verträge:
  nein (später).
- Spieler-Aufträge (orders): `contract_propose {partner, category, units_per_day (Flaschen), price, days}`,
  `contract_accept id`, `contract_decline id`, `contract_cancel id`.
- Ansicht `contracts`: `{"partners": [{"id","name","stage","role": "Lieferant"|"Kunde","market_price"}],
  "active": [...], "offers": [... von KI], "proposed": [... vom Spieler]}` (Mengen in Flaschen).

## C. Hersteller: Kunden für die eigene Marke gewinnen (Marketing)
- Ansicht `brand_marketing`: je Marke der Kategorie `{"id","name","owner","is_mine","awareness","reputation",
  "quality","price","share_of_sales","marketing_budget_year"}` – Konkurrenz sichtbar (öffentlich).
- Im Reiter Produktion Karte «Marke und Kunden»: Budget (choices.marketing_budget), Fokus Marke/Laden,
  Zielgruppe; dazu Wirkung (Bekanntheit, Anteil) im Vergleich zur Konkurrenz.
