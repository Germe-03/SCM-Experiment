# Spielmodus – Feedback 4: Lager-Reiter und Lieferanten pro Marke (verbindlich)

Mengen in Flaschen (unit_size = config.unit_scale.real_units_per_sim_unit), Preise in CHF pro Flasche.
Deutsch mit Umlauten, nie ß.

## Neue Entscheide (PlayerChoices, existiert noch nicht → Backend-Worker legt an)
- `brand_suppliers: {brand_id: supplier_id}` – fester Grosshändler je Marke; fehlt = automatisch.
  Der Controller rechnet vor jeder Runde daraus `supplier_shares` (Summe brand_plan-Flaschen je
  Lieferant; Marken ohne festen Lieferanten verteilen sich auf die automatische Regel → nicht in
  supplier_shares aufnehmen, ausser alle Marken haben einen Lieferanten). Nur wenn brand_suppliers gesetzt ist.

## Ansicht `/api/view/inventory`
```
{"kind": "haendler"|"hersteller",
 "summary": {"bottles", "value_chf", "capacity", "used", "days_of_cover", "in_transit"},
 "brands": [{"id","name","category","category_name","stock","in_transit","sales_per_day",
             "days_of_cover","unit_price","value_chf"}],          # Händler und Fertigware Hersteller
 "components": [{"name","stock","use_per_day","days_of_cover","price","value_chf"}],  # nur Hersteller
 "history": [{"label": "Jahr 1, Februar", "<kategorie oder marke>": flaschen, ...}],   # je Runde
 "warnings": [{"level":"rot"|"gelb","text"}]}
```
sales_per_day je Marke: aus dem Lagerabgang der letzten Runde (Controller merkt sich Stände je Runde)
oder Brand-Statistik; days_of_cover = stock / sales_per_day (999 wenn 0). Warnung rot «leer», gelb
«über 30 Tage».

## Ansicht `/api/view/brand_sources`
```
{"brands": {brand_id: [{"supplier_id","supplier_name","price","stock","deliverable_per_day",
                        "fill_rate"}]},
 "by_supplier": [{"supplier_id","name","categories": {kategorie: {"ordered","delivered","open"}}}]}
```
Grosshändler = env.supplier_candidates(firm_id); stock = Lager dieser Marke beim Grosshändler
(runtime.stock[brand]); price = Grosshändler-Preis × Marken-Faktor (brands.retail_price/value);
deliverable_per_day ≈ Lieferkapazität des Grosshändlers × Anteil der Marke an seinem Lager;
fill_rate aus env.delivery_book. by_supplier aus dem Ledger (record_items, Schlüssel "partner|kategorie").

## Cockpit
- Neuer Reiter «Lager» (reiter_lager.js, REITER.lager) nach «Einkauf».
- Einkauf (Händler): Markenzeile aufklappbar mit Grosshändlern aus brand_sources, Auswahl «automatisch» oder
  ein Grosshändler (→ choices.brand_suppliers), Warnung wenn Plan > Summe deliverable_per_day.
  Ausbau-Feld vom Einkauf in den Lager-Reiter verschieben. Logistik: Tabelle «Einkauf nach Anteilen» entfernen.
- Übersicht: Kachel «Lager» mit Link zum Reiter Lager; «Auslastung letztes Jahr» im ersten Jahr durch
  aktuelle Auslastung ersetzen.
