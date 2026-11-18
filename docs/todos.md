# Offene Todos

Stand 11.11.2026. Umgesetzt ist alles bis Phase 58 (Lastwagenhändler mit Werkstatt und Servicevertrag, Post/Kuriere mit Lastwagen, Händler-Beteiligungen, F&E-Tooltip und Baumlayout, Brauerei kauft Softdrink-Firma, Wein-Eintritte). Hier steht nur, was noch offen ist. Umsetzung erst auf Startzeichen.

## 1. DACH und Nachbarländer (Konzept, nicht beschlossen)

Heute ist das Ausland eine Blackbox (`CategoriesConfig.exports` mit share/fx_elasticity/world_price_factor, imports mit cost_factor 0.85 und tariff 0.05, ein Wechselkurs).

- **Länder:** DE, AT, LI (Stufe 1 = DACH), danach FR, IT. Je Land Regionen (z.B. DE: Bayern, Baden-Württemberg; AT: Vorarlberg, Tirol; FR: Elsass, Rhône-Alpes; IT: Lombardei, Piemont), Bevölkerung mit Alter und Einkommen, eigene Vorlieben (DE Bier, FR/IT Wein, AT beides), tieferes Preisniveau als in der Schweiz.
- **Währung:** EUR/CHF als ein Kurs (LI nutzt CHF), EZB als zweite Zentralbank mit eigenem Leitzins und eigener Teuerung (gleiche Regeln wie SNB).
- **Grenze:** Zoll und Freihandel (CH–EU Freihandel für Industriegüter, Agrar und Wein mit Kontingent und Zoll), Einfuhr-MwSt, Alkoholsteuern je Land, Grenzwartezeit für Lastwagen, Einkaufstourismus (Kunden in Grenzregionen kaufen im Ausland, wenn der Preisabstand gross ist).
- **Firmen:** ausländische Startfirmen je Land und Stufe; Schweizer Firmen dürfen Standorte oder Töchter im Ausland eröffnen und umgekehrt (Holdings über die Grenze); optional eine Grenze für Übernahmen wie die Lex Koller.
- **Transport:** Strecke zählt auch über die Grenze, die Post fährt nur in der Schweiz (Partnerpost im Ausland teurer), Kuriere und eigene Flotten international.
- **Börse:** SIX und eine EU-Börse oder ETFs je Land. **Wichtig:** Mit DACH die ETFs nach Region (ETF Zürich, Bern, Tessin …, `etf_groups` "region") abschaffen und durch ETFs nach Land ersetzen (ETF Schweiz, Deutschland, Österreich …). Kategorie- und Stufen-ETFs bleiben.
- **Dashboard:** Länder-Filter, Karte mit Nachbarländern, Reiter «Ausland» (Exporte und Importe je Land, Wechselkurs, Zölle, Einkaufstourismus).
- **Phasen:** 1 Länder, Regionen, Nachfrage, EUR; 2 Grenze (Zoll, MwSt, Steuern, Einkaufstourismus); 3 Firmen, Standorte, Holdings im Ausland; 4 EZB, Börse und ETFs, Dashboard; 5 FR und IT dazu. Auf die Laufzeit achten (mehr Firmen = längere Läufe), das Ausland evtl. gröber simulieren.

## 2. Bekannte offene Punkte

- **Eigene Lastwagen:** Nur 7 bis 14 Firmen haben eigene Lastwagen (Seed 0).
- **Lastwagenhändler:** 3 bis 5 aktiv, Werkstatt bringt 403 Mio. Umsatz über 50 Jahre, aber alle Händler zusammen machen über 50 Jahre 7 Mio. Verlust. Nur 14 Occasionen verkauft.
- **Wein:** Nur noch 3 Neueintritte statt fast jährlich; zwei davon geben nach 3 bis 4 Jahren auf. Domaine Lavaux SA scheidet in Jahr 48 aus.
- **Leasing:** Übergabe an eine Nachfolgefirma bei Fusion oder Übernahme ist nur im Test geprüft.
- **F&E-Baum und Händler-Karte:** nur mit Testdaten geprüft, nicht im Browser.

## 3. Spielstände als fertiger Zustand (Todo 18.11.2026, nicht begonnen)

Heute speichert ein Spielstand nur die Eingaben und rechnet beim Laden die ganze Simulation neu durch. Das dauert bei langen Spielen 10 bis 15 Minuten und ergibt ein anderes Spiel, sobald sich Regeln geändert haben.

- **Neu:** Gespeichert wird immer der aktuelle Stand als fertiger Zustand (ganze Simulation), Laden in Sekunden und unabhängig von späteren Regeländerungen.
- **Höchstens 3 Spielstände:** frei belegbar, es können verschiedene Spiele oder verschiedene Stände desselben Spiels sein.
- **Immer der aktuelle Stand:** Speichern legt den Stand von jetzt ab.
- Offen bei der Umsetzung: Was passiert beim Speichern, wenn alle 3 Plätze belegt sind (überschreiben mit Rückfrage?), und wie die automatische Sicherung dazu passt.
