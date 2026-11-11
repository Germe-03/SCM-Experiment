# Offene Todos

Stand 11.11.2026. Umgesetzt ist alles bis Phase 57 (Commit 9effa22). Hier steht nur, was noch offen ist. Umsetzung erst auf Startzeichen.

## 1. Lastwagenhändler neu bauen (Konzept, nicht beschlossen)

Anlass: Der Marktanteil der Händler ist eine Treppe aus 0 % und 100 %. Fast immer ist nur ein Händler aktiv, es werden nur 0 bis 12 Lastwagen pro Jahr verkauft, Händler geben nach 3 Verlustjahren auf, Occasionen werden nie weiterverkauft und die Lager- und Betriebskosten sind höher als die Marge.

1. **Werkstatt beim Händler:** Wartung und Reparaturen aller Lastwagen macht neu ein Händler (heute zahlt die Firma `maintenance_rate`/`repair_share` ins Leere). Preis = Kosten (Teile, Löhne) + Werkstattmarge. Jeder Händler hat eine Werkstattkapazität (Mechaniker); ist sie ausgelastet, steht der Lastwagen länger still.
2. **Servicevertrag beim Kauf:** 5 Jahre lang darf der Lastwagen nur beim verkaufenden Händler gewartet und repariert werden. Ausnahme: Der Händler ist pleite oder ausgetreten, dann wählt die Firma frei (günstigster oder naher Händler). Danach freie Wahl nach Preis und Nähe. Bei Leasing läuft der Servicevertrag über die Leasingdauer.
3. **Händler investieren:** Händler sind heute nicht in `runner._firms()` (STAGES) und können darum keine Beteiligungen kaufen (`holdings.py`). Neu: Überschüssiges Geld geht in Beteiligungen an anderen Firmen (Transportbranche bevorzugt), mit Dividenden und Verkauf bei Verlust, nach denselben Regeln wie bei anderen Firmen. Händler können auch selbst übernommen werden oder zu einer Holding gehören.
4. **Post und Kuriere brauchen Lastwagen:** Heute haben sie keine Fahrzeuge, die Kosten sind pauschal. Neu kaufen oder leasen sie ihre Lastwagen über die Händler (gleiche Typen, Strecke zählt). Die Flottengrösse folgt aus Menge mal km, die Wartung läuft beim Händler mit Servicevertrag, und die Fahrzeugkosten fliessen in Posttarif und Kurierpreise. So gibt es genug Geschäft für mehrere Händler.
5. **Occasionen weiterverkaufen:** Zurückgenommene Lastwagen und Leasing-Rückläufer aktiv an Firmen, Kuriere und Neueinsteiger verkaufen (günstiger Einstieg). Was zu lange im Lager steht, wird verschrottet.
6. **Ziel der Kalibrierung:** 3 bis 5 Händler gleichzeitig, die Werkstatt als stabiler Hauptertrag (real etwa 40 bis 50 % des Gewinns), Händler überleben Jahrzehnte. Fixkosten prüfen.
7. **Dashboard:** Marktanteil nur in aktiven Jahren zeigen (keine Striche auf 0 % vor und nach), alle Händler zeigen. Händler-Karte mit Umsatz aus Neuwagen, Occasionen und Werkstatt, mit Serviceverträgen und Beteiligungen. Bei Post und Kurieren die Flotte zeigen.

Mögliche Aufteilung: A Werkstatt und Servicevertrag (`trucks.py`); B Flotten von Post und Kurieren (`carriers.py`, `couriers.py`), gleichzeitig gegen eine vorher festgelegte Schnittstelle; C Händler-Beteiligungen (`holdings.py`, runner); D Dashboard und Kalibrierung.

## 2. F&E-Baum: Tooltip und überlappende Felder

- **Tooltip:** Fährt man mit der Maus über eine Stufe, zeigt ein Feld, was das Upgrade bringt: Wirkung (z.B. Kosten −x %, Kapazität +y %, Qualität), Forschungskosten, Dauer, Voraussetzungen.
- **Andere Firmen dürfen das nicht sehen:** In der Simulation kennen nur Firmen, die die Stufe erforscht oder umgesetzt haben, die genaue Wirkung. Die Konkurrenz entscheidet ohne dieses Wissen oder nur mit einer Schätzung. Im Dashboard sieht der Beobachter die Wirkung. Genaue Bedeutung vor der Umsetzung klären.
- **Fehler:** Die neuen Softdrink-Stufen liegen auf denselben Feldern wie die Bier-Stufen und überlappen, z.B. «Moderne Getränke-Abfüllanlage» über «Prozessautomation», «Leichtere PET-Flaschen» über «Leichtere Flaschen», «Energydrink» über «Alkoholfreies Produkt», «Softdrinks ins Sortiment» über «Neue Geschmacksrichtung». Stufen anderer Kategorien in eigene Spalten oder Zeilen legen, oder den Baum je Kategorie filtern.

## 3. Wein-Treppe

Ab etwa Jahr 22 tritt fast jedes Jahr ein neues Weingut ein und scheidet nach 1 bis 2 Jahren wieder aus; nur Domaine Lavaux SA hält 50 Jahre. Ursachen: erzwungener Eintritt bei Kapazitätsmangel pro Kategorie (runner.py, probability 1.0), Reifezeit (`maturation_days`) bringt Verluste vor dem ersten Verkauf, `distress_loss_years` 2, kein Kredit bei Verlustjahren.

Gegenmassnahmen (nicht: «bestehende Firma füllt die Lücke zuerst»):

1. Verlustjahre zählen bei Wein (allgemein bei Reifezeit) erst ab dem ersten Verkauf; ein erzwungener Eintritt gilt erst nach überstandener Reifezeit als gescheitert.
2. Neue Weingüter bekommen genug Startkapital für die Reifezeit oder starten mit einem Lager an fertigem Wein.
3. Wartezeit nach einem gescheiterten Eintritt, bevor wieder ein Eintritt erzwungen wird (pro Kategorie und Stufe).

## 4. DACH und Nachbarländer (Konzept, nicht beschlossen)

Heute ist das Ausland eine Blackbox (`CategoriesConfig.exports` mit share/fx_elasticity/world_price_factor, imports mit cost_factor 0.85 und tariff 0.05, ein Wechselkurs).

- **Länder:** DE, AT, LI (Stufe 1 = DACH), danach FR, IT. Je Land Regionen (z.B. DE: Bayern, Baden-Württemberg; AT: Vorarlberg, Tirol; FR: Elsass, Rhône-Alpes; IT: Lombardei, Piemont), Bevölkerung mit Alter und Einkommen, eigene Vorlieben (DE Bier, FR/IT Wein, AT beides), tieferes Preisniveau als in der Schweiz.
- **Währung:** EUR/CHF als ein Kurs (LI nutzt CHF), EZB als zweite Zentralbank mit eigenem Leitzins und eigener Teuerung (gleiche Regeln wie SNB).
- **Grenze:** Zoll und Freihandel (CH–EU Freihandel für Industriegüter, Agrar und Wein mit Kontingent und Zoll), Einfuhr-MwSt, Alkoholsteuern je Land, Grenzwartezeit für Lastwagen, Einkaufstourismus (Kunden in Grenzregionen kaufen im Ausland, wenn der Preisabstand gross ist).
- **Firmen:** ausländische Startfirmen je Land und Stufe; Schweizer Firmen dürfen Standorte oder Töchter im Ausland eröffnen und umgekehrt (Holdings über die Grenze); optional eine Grenze für Übernahmen wie die Lex Koller.
- **Transport:** Strecke zählt auch über die Grenze, die Post fährt nur in der Schweiz (Partnerpost im Ausland teurer), Kuriere und eigene Flotten international.
- **Börse:** SIX und eine EU-Börse oder ETFs je Land. **Wichtig:** Mit DACH die ETFs nach Region (ETF Zürich, Bern, Tessin …, `etf_groups` "region") abschaffen und durch ETFs nach Land ersetzen (ETF Schweiz, Deutschland, Österreich …). Kategorie- und Stufen-ETFs bleiben.
- **Dashboard:** Länder-Filter, Karte mit Nachbarländern, Reiter «Ausland» (Exporte und Importe je Land, Wechselkurs, Zölle, Einkaufstourismus).
- **Phasen:** 1 Länder, Regionen, Nachfrage, EUR; 2 Grenze (Zoll, MwSt, Steuern, Einkaufstourismus); 3 Firmen, Standorte, Holdings im Ausland; 4 EZB, Börse und ETFs, Dashboard; 5 FR und IT dazu. Auf die Laufzeit achten (mehr Firmen = längere Läufe), das Ausland evtl. gröber simulieren.

## 5. Bekannte offene Punkte aus den letzten Phasen

- **Softdrinks und Wasser:** 47 bis 55 % der verkauften Einheiten (etwa 30 % des Umsatzes). Ziel war 25 bis 35 %; nach Menge zu hoch.
- **Brauereien mit Softdrinks:** Bekommt eine Brauerei per F&E «Softdrinks ins Sortiment», bleibt sie in der Kategorie Bier. Zuckersteuer und Pfand treffen ihre Softdrinks nicht.
- **Eigene Lastwagen:** Nur 9 bis 14 Firmen haben eigene Lastwagen; der Eigenflottenanteil springt weiter.
- **Banken:** Kredite sind am Ende nur 1.6 % der Einlagen; der Negativzins kostet 9.65 Mia. und ist höher als der Einlagezins von 6.1 Mia.
- **Lastwagenhändler:** Lager und Beteiligungen sind nicht kreditfinanziert (siehe Punkt 1).
- **Leasing:** Übergabe an eine Nachfolgefirma bei Fusion oder Übernahme ist nur im Test geprüft, im Lauf mit Seed 0 kam sie nicht vor.
