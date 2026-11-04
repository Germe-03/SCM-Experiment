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

## Phase 20: Abschluss und Messprotokoll

Umgesetzt am 2026-11-04 auf dem Branch `bauplan-3-banken` (Phasen 13–19,
Phasen 15 und 16 in einem Commit). Code: Codex (13, 14, 15, 19) und die
günstigen Delegate-Modelle (16, 17, 18, Tests), Korrekturen von Hand.

### Abweichungen vom Plan

- **Kreditklemme stoppt nur Investitionen** (Ausbau, Standorte, F&E,
  Marketing, Beteiligungen, Übernahmen), nicht den Wareneinkauf. Mit
  Einkaufssperre (`banking.block_purchases: true`) gerieten Firmen in
  Abwärtsspiralen: ohne Ware kein Umsatz, Löhne liefen weiter, Schulden bis
  zum Neunfachen der Linie, 4–8 Konkurse pro Jahr und Zusammenbruch aller
  Banken in 2 von 3 Läufen.
- **Konkursdividende:** Die Bank verliert nur 20 % einer ausgefallenen Schuld
  (`loss_given_default: 0.2`), der Rest kommt aus der Konkursmasse.
- **SNB-Freibetrag:** 80 % der Reserven sind vom Negativzins befreit
  (`reserve_exemption: 0.8`, wie 2015–2022). Ohne Freibetrag frass der
  Negativzins auf Milliarden-Reserven das Eigenkapital in wenigen Jahren.
- **Alte Schulden bleiben bei der gefallenen Bank:** Findet ein Schuldner nach
  einer Pleite keine Bank, wird sein Kredit gekündigt; die neue Bank erbt
  seine Schuld nicht.
- Höchstzahl Banken zählt nur aktive Banken; gefallene machen Platz für neue.
- Kapitalausstattung: `start_equity_fraction: 1.2`, `payout_ratio: 0.3`.
- Gemessen wurden 3 statt 10 Seeds (je 50 Jahre, ca. 25 Minuten pro Lauf).

### Messwerte (Seeds 1–3, je 50 Jahre)

| | Seed 1 | Seed 2 | Seed 3 |
|---|---|---|---|
| Firmenkonkurse total | 47 | 76 | 31 |
| Leitzins min … max (Mittel) | −0.75 … 2.00 % (0.65 %) | −0.75 … 2.25 % (0.56 %) | −0.75 … 2.00 % (0.70 %) |
| Teuerung im Mittel | 1.11 % | 0.84 % | 0.74 % |
| Bankpleiten | 0 | 1 (neue Bank, 5 Kunden) | 0 |
| Neue Banken | 3 | 4 | 3 |
| Zweitkonten eröffnet | 21 | 20 | 24 |
| Kreditablehnungen | 153 | 172 | 109 |
| Börsenindex Jahr 5 → 50 (Tief) | 1072 → 8081 (1072) | 1031 → 2778 (645) | 1135 → 9391 (717) |
| Beteiligungen über Börse / mit Kredit | 18 / 20 | 13 / 10 | 20 / 13 |
| Abschreibungen der Banken total | 8.5 Mrd. | 8.1 Mrd. | 4.2 Mrd. |

Zum Vergleich die Läufe vor der Korrektur (gleiche Seeds): mit Einkaufssperre
und ohne Freibetrag fielen in Seed 2 und 3 alle Banken, danach 4 Konkurse pro
Jahr bis Jahr 50 (Obergrenze pro Stufe).

### Offene Punkte

- Eigenkapitalquote = Eigenkapital / Kredite; bei kaum Krediten zeigt das
  Dashboard sehr hohe Werte (z. B. 600 %). Besser wäre Eigenkapital / Bilanzsumme.
- Hausbank und Zweitbank einer Firma erscheinen noch nicht im Firmen-Detail.
- 10-Seed-Messung nachholen.

---

## TODO

> **TODO (2026-11-04):** Börsengang. Vorerst sind alle Firmen ab Jahr 5
> handelbar. Später: Nur grössere Firmen gehen an die Börse, und zwar über
> eine Bank, die dafür eine Gebühr bekommt. Nicht kotierte Firmen können nur
> direkt (ab 10 %) beteiligt werden.
