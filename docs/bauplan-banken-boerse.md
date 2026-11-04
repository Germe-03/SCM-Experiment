# Bauplan 3: SNB, Banken und Börse

Stand: 2026-11-04. Grundlage sind Davids Wünsche nach Phase 12 und eine
Code-Recherche mit Codex (nur gelesen, nichts geändert). Die Phasen sind nach
Abhängigkeiten geordnet: zuerst der Leitzins, dann die Banken, dann Pleiten,
zuletzt Börse und Beteiligungen.

Regeln wie in den bisherigen Bauplänen: nach jeder Phase lauffähig, Tests
grün, 10 Seeds gemessen, alle Stellschrauben in YAML mit `enabled`-Schalter
(`enabled: false` = bisheriges Verhalten), Commit pro Phase ohne
Co-Autor-Zeile. Code schreibt Codex.

## Ausgangslage

- Heute gibt es eine einzige, unsichtbare Bank: `BankConfig` in
  `market_sim/config.py`, Zins in `Environment._apply_interest`
  (`market_sim/environment.py`). Fixer Grundzins 3 %, Zuschläge für
  Verlustjahre und Verschuldung, Habenzins, Negativzins ab Schwelle,
  Schuldenschnitt bei Sanierung.
- Die Kreditlimite ist keine Sperre, sondern nur ein Konkurskriterium am
  Jahresende. Eine Firma kann beliebig ins Minus gehen.
- `cash` ist eine einzige Zahl (Startkapital + Gewinn + Korrekturbuchungen).
- Beteiligungen (`market_sim/holdings.py`) laufen einmal pro Jahr direkt von
  Firma zu Firma, Wert = 4 × Gewinn + Kasse.
- Die Simulation rechnet Tag für Tag (`run_year`, 365 Tage).

---

## Phase 13: SNB und Leitzins

- Neue Datei `market_sim/banking.py` mit `CentralBank`.
- Einmal pro Jahr, nach der Teuerung, setzt die SNB den Leitzins fürs
  Folgejahr: Zielzins = Teuerung + 0.5 × (Teuerung − Ziel) + 0.5 × Konjunkturlücke.
  Ziel 1 %, Start 1 %, Grenzen −0.75 % bis 8 %, höchstens ±0.5
  Prozentpunkte pro Jahr. Konjunkturlücke = geglättete Abweichung der
  Nachfrage vom Trend, begrenzt auf ±10 % (im Dashboard als Modellindikator
  bezeichnen, nicht als BIP).
- Rückwirkung: höherer Realzins dämpft verzögert Nachfrage und Teuerung,
  klein und begrenzt.
- Der Leitzins ersetzt den fixen Grundzins von 3 %.
- Weggelassen: Mindestreserve, Devisenkäufe, Interbankenmarkt.
- Test: gleicher Schock, höherer Zins → tiefere Teuerung im Folgejahr.

## Phase 14: Drei Geschäftsbanken und Konten

- `CommercialBank` mit Eigenkapital, Krediten, Einlagen, Gewinn. Zum Start
  3 Banken mit Margen z. B. 1.5 / 2 / 2.5 %.
- Kreditzins = Leitzins + Marge der Bank + bisherige Zuschläge.
- Jede Firma startet mit einem Konto bei ihrer Hausbank (stabile,
  seedabhängige Zuteilung).
- **Höchstens 2 Konten pro Firma.** Ein zweites Konto bei einer anderen Bank
  darf eröffnet werden, wenn das Geld die Negativzins-Schwelle übersteigt, die
  Hausbank einen Kredit ablehnt oder die Hausbank schwach ist.
- Vereinfachung: Jede Firma speichert die Aufteilung ihres Guthabens
  (z. B. 70 % Bank A, 30 % Bank B). Schulden liegen nur bei der Bank, die den
  Kredit vergeben hat.
- Test: Zinsaufwand der Firmen = Zinsertrag der Banken; nie mehr als 2 Konten.

## Phase 15: Kreditgrenze

- Eigenkapital unter 10 % der Kredite → keine neuen Kredite (Kreditklemme).
  Bestehende Kredite werden nicht sofort gekündigt.
- Abgelehnte Firmen verschieben Ausbau, Standorte und F&E-Projekte.
- Prüfung vor Lieferung/Produktion sowie in `geography.py` und `research.py`.
- Test: zwei gleichzeitige Anträge nutzen denselben Spielraum nicht doppelt.

## Phase 16: Bankpleite und Ansteckung

- Eigenkapital ≤ 0 → Bank fällt.
- **Einlagensicherung 30 %:** Jede Firma bekommt 30 % ihres Guthabens bei
  der gefallenen Bank zurück, 70 % sind verloren (Buchung
  `bankpleite:<bank>`). Gilt pro Bank und ohne Obergrenze in Franken. Wer auf
  zwei Banken verteilt hat, verliert weniger. Zum Vergleich: esisuisse sichert
  in der Schweiz bis 100'000 Franken pro Kunde und Bank.
- **Keine Übernahme durch die stärkste Bank.** Jede betroffene Firma wählt
  selbst eine neue Bank nach Zins, Eigenkapital der Bank und etwas Zufall.
  Hat sie schon ein zweites Konto, kann sie dorthin wechseln.
- Schulden bei der gefallenen Bank bleiben und gehen an die gewählte Bank.
  Eine schwache Bank darf Firmen mit hohen Schulden ablehnen. Findet eine
  Firma keine Bank, muss sie den Kredit zurückzahlen (kann zum Konkurs führen).
- Ansteckung: Verluste der Firmen → Konkurse → Verluste anderer Banken.
  Prüfung am Jahresende in höchstens 3 Runden, damit keine Endlosschleife.
- Neue Banken: höchstens eine pro Jahr, insgesamt höchstens 6, wenn die
  Banken gut verdienen oder viele Kredite abgelehnt werden.
- Test: Verlust genau 70 % des Guthabens; Ausfall aller Banken endet sauber.

## Phase 17: Börse

- Neue Datei `market_sim/stock_market.py`.
- **Ab Simulationsjahr 5 sind alle aktiven Firmen handelbar**
  (`tradable_from_year: 5`), später gegründete Firmen sofort. Kein
  Börsengang nötig (siehe TODO unten).
- Kurs wird jeden Tag berechnet: innerer Wert (Gewinn der letzten Quartale ×
  Faktor + Kasse) mal Stimmung. Die Stimmung schwankt zufällig und kehrt
  immer wieder zum Wert zurück.
- Ereignisse wirken sofort: Vergiftung, Rückruf, Busse → Kurssturz;
  F&E-Erfolg → Sprung. Höherer Leitzins senkt den Faktor und damit alle Kurse.
- Kein Orderbuch: Gegenüber ist ein anonymes Publikum. Käufe von Firmen
  bewegen den Kurs nur wenig.
- Eigener Index über alle handelbaren Firmen.
- Speicher: Tageskurse als CSV, im Dashboard Wochen- und Monatskurse.
- Optional: Fällt der Kurs einer Bank stark, ziehen Firmen einmal im Monat
  Geld ab und gehen zur zweiten Bank (kleiner Bankensturm).
- Test: gleicher Seed → gleiche Kurse; Kurs nie negativ.

## Phase 18: Beteiligungen über die Bank

- **Kleine Beteiligungen unter 10 %:** nur über die Börse und nur über die
  Bank. Gebühr ca. 0.5 % an die Bank, Aktien liegen im Depot. Fällt die
  Bank, bleibt das Depot erhalten, nur das Kontogeld ist betroffen.
- **Grosse Beteiligungen ab 10 %:** weiter direkt wie in `holdings.py`.
  Fehlt das Geld, gibt die Hausbank einen Kredit, sofern ihre Kreditgrenze
  das zulässt. Die Bank kann so einen Kauf verhindern.
- Preis grosser Beteiligungen: Börsenkurs plus Aufschlag statt 4 × Gewinn.
- Test: Depot nach Bankpleite unverändert; Gebühr landet bei der Bank.

## Phase 19: Dashboard und Berichte

- `bank_reports.csv`, `stock_prices.csv`; Kennzahlen Leitzins, Teuerung,
  Kredite, Einlagen, Eigenkapital, Ablehnungsquote, Bankpleiten, Index.
- Events: `policy_rate_changed`, `credit_rejected`, `account_opened`,
  `bank_switched`, `bank_failed`, `bank_entry`, `stock_crash`.
- Finanzbereich: Leitzins und Teuerung, Bankvergleich, Kursgrafik mit
  Wochen/Monat; Geldfluss `bank` nach Bank aufgeschlüsselt.

---

## TODO

> **TODO (2026-11-04):** Börsengang. Vorerst sind alle Firmen ab Jahr 5
> handelbar. Später: Nur grössere Firmen gehen an die Börse, und zwar über
> eine Bank, die dafür eine Gebühr bekommt. Nicht kotierte Firmen können nur
> direkt (ab 10 %) beteiligt werden.
