# Umsetzung Erweiterung 5: Phasen 34–44

Zweig `erweiterung-5`, zusammengesetzt aus phase-34, -35, -36, -37, -38-39, -40-43. 400 Tests grün.

- 34 F&E-Baum: kein Fehlschlag, Hersteller 28 Schritte, übrige Stufen je 9, ca. 40 % günstiger, Stufen I–III.
- 35 Kuriere in «Firmen», «Vergleich», Ereignistexten, Strukturansicht. Keine Kurier-ETFs (Kuriere nicht kotiert). Branchen-ETFs = Stufen-ETFs (Schalter `branche`).
- 36 Banken: max. 5, 10 Jahre zwischen Gründungen, unter 3 Banken ohne Wartezeit.
- 37 Bevölkerung über Altersgruppen (1/17, 1/30, Tod 65+ 1/15, Zufluss 1/17 + 0.005).
- 38/39 Rohstoffmarkt (Band 70–140 %, Nachfrage max. ca. 4 %/Jahr) und Rohstofflager der Fabriken. Nur Malz, Hopfen, Verpackung, Energie.
- 40–42 Holdings bei jedem Kauf, Reserve 10/15 %, 3 % Steuer, 50-%-Regel, Verkauf, Auflösung, Dashboard.
- 43 Fusionen, `base_probability` 0.015.

## Messlauf Phase 44 (3 Seeds x 50 Jahre, neu gegen main e047929)

| | neu (Seed 0/1/2) | main (Seed 0/1/2) |
|---|---|---|
| aktive Firmen am Ende | 43 / 47 / 48 | 26 / 22 / 36 |
| Konkurse | 91 / 83 / 104 | 59 / 95 / 80 |
| Holdings gebildet / aufgelöst | 28/17, 35/25, 23/11 | – |
| Fusionen (verboten) | 2 (4) / 4 (3) / 6 (5) | – |
| Banken max. aktiv | 5 / 5 / 4 | 6 / 6 / 6 |
| Bevölkerung nach 50 J. | +18.6 % | +26.8 % |
| Anteil 65+ Ende | 22.5 % (nach Anpassung 30.1 %) | 31.1 % |
| F&E-Kosten pro Firma | 56.5 / 55.0 / 42.8 Mio. | 45.7 / 27.4 / 41.8 Mio. |
| Gewinn total | 52.4 / 67.6 / 10.6 Mia. | 33.1 / -36.3 / 26.1 Mia. |

Befunde: Fusionen selten genug, `base_probability` bleibt. Rohstoffpreise erreichen in jedem Lauf die Bandgrenzen 0.7 und 1.4. Die Bevölkerung altert mit den neuen Raten kaum (Anteil 65+ bleibt bei 22 %), main alterte stärker. F&E-Ausgaben pro Firma im Schnitt ca. +35 %.

Offen: Sichtprüfung im Browser, Kalibrierung Altersstruktur, Wasser/Weizen/Trauben als Rohstoffe, Aktien bei Fusion als neue Kurslinie.
