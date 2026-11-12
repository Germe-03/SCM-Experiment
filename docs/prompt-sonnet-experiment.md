Du arbeitest im Repo `C:\Users\david\PycharmProjects\SCM-Experiment` (GitHub: Germe-03/SCM-Experiment, Branch `main`). Es enthält `market_sim/`, eine regelbasierte Simulation des Schweizer Biermarkts mit 22 Firmen (10 Retailer, 6 Wholesaler, 4 Distributoren, 2 Brauereien). Lies zuerst `README.md`, `market_sim/config/market.yaml`, `market_sim/config/firms.yaml`, `market_sim/runner.py`, `market_sim/environment.py` und `market_sim/policies.py`.

## Ziel

Die Simulation soll wieder ein **Experiment** werden: Man soll Wettbewerb beobachten können, Seeds sollen sich unterscheiden, und Szenarien sollen messbare Wirkungen haben. Heute ist der Markt zu bequem. Bitte kalibriere die Ökonomie so, dass echter Konkurrenzdruck entsteht, und baue Werkzeuge, mit denen man das beobachten und vergleichen kann.

## Befund (gemessen am aktuellen Stand, Seed 0, 10 Jahre)

1. **Zu viel Geld im System.** Der Systemgewinn beträgt 46–52 % des Endkundenumsatzes. Die Gewinnmarge pro Stufe in Jahr 1: Brauerei 65 %, Distributor 18 %, Wholesaler 8 %, Retailer 4 %. Die Brauereien haben keine Rohstoffkosten (`purchase_cost` = 0). Löhne machen auf jeder Stufe nur 0.1 % des Umsatzes aus, F&E 0.0 %. Die Löhne sind real in CHF, der Umsatz ist aber mit `real_units_per_sim_unit: 10000` hochskaliert. Die einzigen relevanten Kosten sind Einkauf und `handling_cost_per_unit`.
2. **Riesige Überkapazität.** Die Nachfrage liegt bei etwa 180 Sim-Einheiten pro Tag (65'447 im Jahr 1). Die effektive Kapazität pro Stufe liegt bei 1'500–1'750 pro Tag. Die Auslastung beträgt auf allen Stufen etwa 10 %. Deshalb wirkt das Szenario `brauerei_engpass` (−30 % Kapazität) praktisch gar nicht (+1 Mio. CHF über 5 Jahre).
3. **Konkurs ist kaum möglich.** Das Startkapital liegt bei 0.5–1 Mio. CHF pro Firma, die Schwelle `bankruptcy.cash_threshold` bei −100 Mio. CHF, also beim 100- bis 200-Fachen des Startkapitals. In 10 Jahren scheidet nur 1 von 22 Firmen aus. Nur 24 von 220 Firmenjahren schliessen mit Verlust.
4. **Fast keine Dynamik.** Die Retailer-Marktanteile bleiben fast unverändert zwischen 8.6 und 14.4 %. Der HHI liegt fix bei etwa 0.10. Die Preise steigen über 10 Jahre um 17 %, trotz 10 Konkurrenten. Die Strategie passt sich nur in Schritten von 1 % pro Jahr an (`price_step_fraction: 0.01`). Es gibt keine Markteintritte.
5. **Seeds sind fast identisch.** Der Seed beeinflusst nur ±10 % Nachfragerauschen. Die Rangliste der Firmen ist bei Seed 0, 1 und 2 praktisch gleich. Mehrere Seeds bringen also keine Erkenntnis.
6. Die Bullwhip-Ratio liegt weiterhin bei 75–130.

Prüfe diese Zahlen zuerst selbst nach, mit einem kleinen Skript über `runs/base/annual_reports.csv` oder direkt über `market_sim.run.build_runner` und `financial_breakdown`. Falls etwas nicht stimmt, sag es, bevor du änderst.

## Aufgaben

### A. Ökonomie kalibrieren (Konkurrenzdruck)

- **Rohstoffkosten für Brauereien:** Führe Einkaufskosten pro produzierter Einheit ein (Malz, Hopfen, Verpackung, Energie), konfigurierbar in `market.yaml`. Optional mit einem einfachen Preisindex, der über die Zeit schwankt; der Vorschlag in `docs/commodity-market-proposal.md` ist eine Vorlage, die volle Börse ist aber **nicht** nötig.
- **Lohn- und Fixkosten auf eine Skala bringen:** Löhne, Einstellungskosten und F&E müssen auf derselben Geldskala wie Umsatz und Einkauf liegen, damit sie spürbar werden. Ergänze bei Bedarf einen Fixkostenblock pro Firma (Miete, Fahrzeuge, Maschinen), der mit der Kapazität wächst. So kostet Überkapazität Geld.
- **Kapazität realistisch machen:** Die Gesamtkapazität pro Stufe soll etwa das 1.2- bis 1.5-Fache der durchschnittlichen Nachfrage betragen, sodass die Sommer-Saison spürbar an die Grenze geht.
- **Konkurs relativ zur Firmengrösse:** Ersetze die absolute Schwelle von −100 Mio. CHF durch eine Regel relativ zur Firma, zum Beispiel «Cash unter −X × Startkapital» oder «zwei Jahre in Folge negatives Eigenkapital». Startkapital und Geldskala müssen zueinander passen.
- **Mehr Preiswettbewerb:** Die jährliche Strategie soll stärker auf Konkurrenten reagieren, zum Beispiel unterbieten, wenn Marktanteil verloren geht. Achte auf Stabilität: keine Preisspiralen auf null, keine Explosion beim Bullwhip.
- **Zielwerte für den Basislauf** (Mittel über Seeds 0–4, 10 Jahre):
  - Systemgewinn 5–15 % des Endkundenumsatzes.
  - Stufenmargen grob: Brauerei 8–15 %, Distributor und Wholesaler 2–6 %, Retailer 1–5 %.
  - Durchschnittliche Auslastung 65–90 %.
  - Pro Lauf scheiden im Mittel 1–5 Firmen aus, aber nie mehr als ein Drittel.
  - Retailer-Marktanteile bewegen sich spürbar: Die Summe der absoluten Anteilsänderungen pro Jahr liegt im Mittel über 5 Prozentpunkte.
  - Das Szenario `brauerei_engpass` hat eine klar messbare Wirkung, also mehr verlorene Verkäufe und höhere Preise.
  - Erkläre in einem kurzen Abschnitt, falls ein Ziel nicht erreichbar ist, und warum.

### B. Unterschiede zwischen Seeds

- Der Seed soll mehr als Rauschen steuern: zum Beispiel leicht zufällige Startwerte (Cash, Qualität, Reputation ±10–20 %) und zufällige Marktereignisse pro Jahr (Hitzesommer, Ernteausfall, Rückruf bei einer Firma), alles deterministisch pro Seed.
- Die Ereignisse müssen ins Ereignisprotokoll (siehe C) und dürfen Speicherstände und Fortsetzen nicht brechen. Das heisst: Der Test «Lauf mit Speicherstand in Jahr 5 und Fortsetzung = Lauf ohne Unterbruch» muss grün bleiben.

### C. Beobachten können (Experiment-Werkzeuge)

- **Neue Kennzahlen in `SystemKPIs`** (und damit in `system_kpis.csv`): Marge pro Stufe, Auslastung pro Stufe, Marktanteilsbewegung (Summe |Δ Anteil|), Anzahl Firmen mit Verlust, Konkurse und Markteintritte im Jahr, Preisstreuung unter den Retailern.
- **Ereignisprotokoll `events.csv`:** pro Zeile Jahr, Tag, Firma, Ereignis und Details. Ereignisse: Konkurs, Markteintritt, Preissenkung oder -erhöhung über 5 %, Lieferantenwechsel (grösster Lieferant ändert sich), Kapazitätsgrenze erreicht (über 95 % während mindestens 7 Tagen), Marktereignis aus B.
- **Experiment-Befehl** `python -m market_sim.experiment --seeds 0-9 --scenarios basis,nachfrage_einbruch,brauerei_engpass,preiserhoehung_brauerei --fork-year 5 --out runs/experiment_<name>`. Er rechnet jede Kombination, nutzt dafür die bestehenden Speicherstände und `market_sim/scenario.py`, und schreibt `experiment_summary.csv` mit Mittelwert, Standardabweichung, Minimum und Maximum der wichtigsten Kennzahlen pro Szenario. Dazu eine kurze Konsolenzusammenfassung. Kein Szenario, kein Seed darf die Ergebnisse eines anderen beeinflussen.
- **Optional, wenn Zeit bleibt:** Markteintritt einer neuen Firma, wenn die Durchschnittsmarge einer Stufe zwei Jahre über einem Schwellwert liegt, als Konfigurationsschalter. Und eine Vergleichsansicht im Dashboard für Basis gegen Szenario.

## Regeln

- `team_bundle/` nicht anfassen.
- Bestehende Funktionen (Speicherstände, `--resume`, Szenarien, `exit_year`, Dashboard) müssen weiter funktionieren.
- Tests: `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=<neuer Ordner unter %TEMP%> market_sim`. Der Standard-Temp-Ordner ist auf diesem Rechner gesperrt. Lass keine Temp-Ordner im Repo zurück. Alle Tests müssen grün sein. Wenn sich Erwartungen in bestehenden Tests wegen der neuen Kalibrierung ändern müssen, pass sie bewusst an und begründe es im Commit. Lösche keine Tests, nur damit sie bestehen. Schreib neue Tests für Rohstoffkosten, Konkursregel, Ereignisprotokoll, neue Kennzahlen und den Experiment-Befehl.
- Code-Stil wie im Repo: Type Hints, kompakt, Pydantic für Config mit `extra="forbid"`, kurze Kommentare nur wo nötig. Neue Stellschrauben gehören in `market.yaml`, nicht hart in den Code.
- Dokumentation auf Deutsch mit ä, ö, ü und ohne ß (immer «ss»). Ergänze die README um einen Abschnitt «Experiment», mit Befehlen, den neuen Kennzahlen und einem Vorher-Nachher-Vergleich der Befundzahlen oben.
- Arbeite in kleinen, sinnvollen Commits (Kalibrierung, Seeds und Ereignisse, Kennzahlen und Protokoll, Experiment-Befehl, README). **Commit-Nachrichten ohne «Co-Authored-By»-Zeile. Nicht pushen**, bevor David es freigibt.

## Abschluss

Zum Schluss lieferst du:
1. Was du geändert hast, kurz pro Commit.
2. Die Zielwerte aus A, gemessen über Seeds 0–4, vorher und nachher.
3. Die Ausgabe eines Experiments mit 5 Seeds und allen Szenarien, und die drei interessantesten Beobachtungen daraus.
4. Was offen oder unsicher ist.
