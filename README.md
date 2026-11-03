# SCM-Experiment

Experimente zum Wahlmodul **Supply Chain Management** (FHNW BSc Business AI):
vom klassischen Beer Game zu einer agentenbasierten Simulation des Schweizer
Biermarkts mit 22 konkurrierenden Firmen.

Repository: <https://github.com/Germe-03/SCM-Experiment>

Das Repo hat zwei Teile, die bewusst getrennt bleiben:

| Teil | Ordner | Zweck |
|---|---|---|
| Beer-Game-Abgabe | `team_bundle/` | Vier Agenten (Retailer, Wholesaler, Distributor, Factory) für die `supplychainbench`-Engine des Moduls |
| Markt-Simulation | `market_sim/` | Eigenständige Multi-Firm-Simulation: mehrere Firmen pro Stufe, Preise, Qualität, Reputation, Cash, Löhne, F&E, Konkurs |

---

## 1. Beer-Game-Abgabe (`team_bundle/`)

Die Engine `supplychainbench_v2` ist ein geschlossenes Wheel des Moduls und
nicht Teil dieses Repos. Pro Stufe darf nur die Methode `step()` in
`<rolle>/agent.py` verändert werden; sie sieht nur die lokale Beobachtung und
gibt eine Bestellmenge (`order_qty`) zurück. Regeln und Ablauf stehen in
[`team_bundle/README.md`](team_bundle/README.md), die Rollen sind in den
`walkthrough_*.md` beschrieben.

**Stand:** Alle vier Agenten nutzen noch die Mirror-Policy
(`order_qty = incoming_order_qty`). Sie ist gültig, erzeugt aber den
typischen Bullwhip-Effekt. Base-Stock, gleitender Durchschnitt und
Forecast-Nachrichten (Phase 2) sind die nächsten Schritte.

```bash
cd team_bundle
supplychainbench test-bundle .
```

---

## 2. Markt-Simulation (`market_sim/`)

Weil die Engine nur genau eine Firma pro Stufe und nur eine Bestellmenge
kennt, wurde die Markt-Simulation als eigenes Paket gebaut. Die bewährte
Tick-Mechanik der Engine wurde nachgebaut und per Paritätstest gegen die
Referenz geprüft. Die Herleitung steht in
[`docs/market-extension-plan.md`](docs/market-extension-plan.md).

### Modell in Kürze

- **Netzwerk:** 10 Retailer → 6 Wholesaler → 4 Distributoren → 2 Brauereien
  (Factories), jede Stufe mit allen Firmen der Nachbarstufe verbunden
  (`config/firms.yaml`).
- **Archetypen:** `low_cost`, `standard`, `reliable`, `premium`, `growth`;
  sie bestimmen Preis, Qualität, Löhne, Risiko und Lagerziel.
- **Nachfrage:** rund 94'400 Simulationseinheiten pro Jahr (1 Einheit =
  10'000 reale Einheiten), preiselastisch, mit
  Sommer-Saisonalität und drei Kundensegmenten (Schnäppchen 55 %,
  Mainstream 30 %, Premium 15 %), die Preis, Qualität, Reputation und
  Verfügbarkeit unterschiedlich gewichten (`config/market.yaml`).
- **Beschaffung:** Base-Stock-Bestellungen inkl. offener Bestellungen, mit
  Glättung und Obergrenze; Aufteilung auf mehrere Lieferanten, Auswahl nach
  Preis, Zuverlässigkeit und Reputation.
- **Finanzen:** Umsatz, Wareneinsatz, Rohstoffe der Brauereien, Lager-,
  Backlog- und Handlingkosten, Fixkosten, Löhne und F&E in realen CHF. Firmen
  scheiden am Jahresende aus, wenn ihr Cash im Verhältnis zum Startkapital zu
  tief liegt (siehe Abschnitt Experiment).
- **Rückkopplungen:** Lohn → Reputation, erreichte Lieferquote →
  Zuverlässigkeit, Preissprünge → Reputation, Überlast → Qualität,
  verzögerte F&E → Qualität. Die Strategie wird jährlich anhand der
  Vorjahreszahlen angepasst.

### Starten

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install pydantic pyyaml pytest
```

```bash
python -m market_sim.run --seed 0 --out runs/seed0
```

```bash
python -m market_sim.dashboard --seed 0 --out runs --open
```

```bash
python -m pytest market_sim
```

`run` schreibt `annual_reports.csv` (pro Firma und Jahr), `firm_ranking.csv`
(inkl. `exit_year` für Firmen, die Konkurs gegangen sind) und
`system_kpis.csv` sowie das Ereignisprotokoll `events.csv`. In der Konsole stehen ausgeschiedene Firmen separat von
Firmen, die noch aktiv sind, aber negatives Cash haben.

### Speicherstände und Szenarien

Mit `--checkpoints` speichert die Simulation nach jedem Jahr den ganzen Zustand
(alle Firmen, Lager, Kasse, Zufallsgeneratoren) als
`<out>/checkpoints/year_XX.pkl`. Ein Lauf lässt sich damit fortsetzen, und
das Ergebnis ist exakt dasselbe wie bei einem Lauf ohne Unterbruch.

```bash
python -m market_sim.run --seed 0 --out runs/base --checkpoints
```

```bash
python -m market_sim.run --resume runs/base/checkpoints/year_05.pkl --out runs/resumed
```

Von jedem Speicherstand aus kann man ein Was-wäre-wenn-Szenario abzweigen. Die
Jahre davor bleiben identisch, ab dem Abzweig gilt die Änderung bis zum Ende.
Mit `--baseline` entstehen zusätzlich `comparison.csv` (pro Jahr) und
`firm_comparison.csv` (pro Firma).

```bash
python -m market_sim.scenario --from runs/base/checkpoints/year_05.pkl --scenario nachfrage_einbruch --out runs/fork_nachfrage --baseline runs/base
```

Die Szenarien stehen in `market_sim/config/scenarios.yaml`:

- `nachfrage_einbruch`: Die Konsumnachfrage sinkt dauerhaft um 20 %.
- `brauerei_engpass`: Beide Brauereien verlieren 30 % Produktionskapazität.
- `preiserhoehung_brauerei`: Beide Brauereien erhöhen ihre Preise um 20 %.

Speicherstände sind Pickle-Dateien. Lade nur Dateien, die du selbst erzeugt
hast. Das Dashboard ist eine eigenständige HTML-Datei, in
der man jede Firma einzeln anschauen kann. Ein 10-Jahres-Lauf dauert rund
20 Sekunden.

### Experiment

Der Markt soll beobachtbar sein: echter Konkurrenzdruck, Seeds mit eigenem
Verlauf und Szenarien mit messbarer Wirkung.

```bash
python -m market_sim.experiment --seeds 0-9 --scenarios basis,nachfrage_einbruch,brauerei_engpass,preiserhoehung_brauerei --fork-year 5 --out runs/experiment_a
```

Pro Seed läuft die Basis einmal und speichert den Speicherstand im Forkjahr
(`<out>/checkpoints/seed_XX/year_05.pkl`). Jedes Szenario startet aus einer
frisch geladenen Kopie davon. Die Seeds laufen in getrennten Prozessen
(`--workers`), nichts wird geteilt, kein Szenario beeinflusst ein anderes.
`basis` ist der Lauf ohne Änderung. Mit `--years` und `--days-per-year` lässt
sich ein kurzer Probelauf machen. Verglichen werden die Jahre nach dem
Forkjahr. Ausgabe:

- `experiment_summary.csv`: Mittelwert, Standardabweichung, Minimum, Maximum
  und Anzahl Seeds pro Szenario und Kennzahl.
- `experiment_runs.csv`: die Rohwerte pro Seed und Szenario.
- Eine Konsolenzusammenfassung mit der Differenz zur Basis.

Ein normaler Lauf (`python -m market_sim.run`) schreibt zusätzlich
`events.csv` und die neuen Spalten in `system_kpis.csv`.

#### Neue Kennzahlen (`system_kpis.csv`)

- `margin_<stufe>`: Gewinn geteilt durch Umsatz der aktiven Firmen einer Stufe.
- `utilization_<stufe>`: mittlere Kapazitätsauslastung der aktiven Firmen.
- `market_share_movement`: Summe der absoluten Änderungen der Retailer-Marktanteile
  gegenüber dem Vorjahr (0.10 heisst 10 Prozentpunkte).
- `firms_with_loss`, `bankruptcies`, `market_entries` (auch bei Firmen, die
  während eines Laufs über das Firmenregister ergänzt werden) und `retailer_price_spread` (Standardabweichung
  der mittleren Retailer-Preise).

#### Ereignisprotokoll (`events.csv`)

Eine Zeile pro Ereignis mit `year`, `day`, `firm`, `event`, `details`:
`bankruptcy`, `price_increase` / `price_cut` (Jahresmittelpreis ändert sich um
mehr als 5 %), `supplier_switch` (grösster Lieferant wechselt),
`capacity_limit` (Auslastung über 95 % an mindestens 7 Tagen in Folge) und die
  Marktereignisse `heat_summer`, `harvest_failure` und `recall` sowie
  `market_entry` aus dem Firmenregister. Das Protokoll
liegt im Speicherstand; Fortsetzen ergibt dieselbe Datei wie ein Lauf ohne
Unterbruch.

#### Was kalibriert wurde (`config/market.yaml`)

- `commodities`: Rohstoffkosten der Brauereien pro produzierter Einheit
  (Malz, Hopfen, Verpackung, Energie) mit einem schwankenden Preisindex pro Komponente.
- `costs.personnel_cost_scale` und `costs.initial_cash_scale`: Löhne, Einstellung,
  F&E und Startkapital liegen auf derselben Geldskala wie der Umsatz.
- `fixed_costs`: Fixkosten pro Tag und pro Kapazitätseinheit; Überkapazität kostet Geld.
- Kapazität pro Stufe auf das 1.2- bis 1.4-Fache der Nachfrage (`firms.yaml`),
  Mindestbelegschaft `workforce.min_employees` (vorher fest 5 Mitarbeiter, die
  eigentliche Ursache der Überkapazität).
- `bankruptcy`: Austritt bei Cash unter −1 × Startkapital oder nach 4 Jahren
  in Folge mit negativem Cash. Eine Stufe behält mindestens 2 Firmen und verliert
  höchstens 1 Firma pro Jahr (so kippt nicht die ganze Kette auf einmal).
- `adaptive_strategy`: Preise reagieren auf den Konkurrenzpreis
  (`competitive_pull`) und auf Marktanteilsverlust (`undercut_fraction`);
  Preisbänder liegen um den Stufen-Basispreis.
- `start_variation` und `events`: Startkapital, Qualität und Reputation
  streuen pro Seed (±20 / 10 / 15 %). Der generische Ereignisrahmen konfiguriert
  Typ, Aktivierung, Wahrscheinlichkeit, Dauer, Stärke und Wirkung; alles ist pro Seed festgelegt.
- `supplier_discovery.enabled`: Leere Lieferantenlisten entdecken zur Laufzeit
  alle aktiven Firmen der direkt vorgelagerten Stufe; eine nicht leere Liste
  schränkt diese Kandidaten ein.

#### Vorher und nachher (Mittel über Seeds 0–4, 10 Jahre)

| Kennzahl | Vorher | Nachher | Ziel |
|---|---:|---:|---|
| Systemgewinn / Endkundenumsatz | 48.8 % | 11.7 % | 5–15 % |
| Marge Brauerei | 60.3 % | 8.2 % | 8–15 % |
| Marge Distributor | 22.3 % | 4.1 % | 2–6 % |
| Marge Wholesaler | 11.7 % | 2.7 % | 2–6 % |
| Marge Retailer | 6.9 % | 3.3 % | 1–5 % |
| Auslastung (Mittel aller Stufen) | 9.7 % | 71.3 % | 65–90 % |
| Ausgeschiedene Firmen pro Lauf | 1 | 4.4 (3–6) | 1–5, höchstens 7 |
| Firmenjahre mit Verlust (von 220) | 22 | 48 | – |
| Marktanteilsverschiebung pro Jahr | 4.3 Pkt. | 10.7 Pkt. | über 5 Pkt. |
| Konzentration (HHI) | 0.106 | 0.111 | – |
| Bullwhip-Ratio | 93.8 | 101.1 | nicht explodieren |
| Preisanstieg Jahr 1 bis 10 | +17 % | +5 % | – |
| Verlorene Verkäufe (10 Jahre, Summe) | 2'142 | 95'754 | – |
| Streuung des Systemgewinns zwischen Seeds | 48.7–48.8 % | 8.4–13.6 % | – |

Alle Ziele aus der Aufgabe sind erreicht. Die Marge der Wholesaler liegt knapp
am unteren Rand. Die verlorenen Verkäufe sind deutlich gestiegen: Das ist die
Kehrseite der knappen Kapazität. Sie fallen vor allem in den Jahren 1 bis 3
an (Service-Level dort 78–99 %), danach nur noch nach Konkursen und
Marktereignissen. Im Mittel über 10 Jahre liefert der Markt rund 96 % der
Nachfrage (vorher praktisch 100 %).

#### Beispiel: 5 Seeds, alle Szenarien, Fork nach Jahr 5

Mittelwert ± Standardabweichung über die Jahre 6 bis 10. Werte in CHF.

| Szenario | Gewinn (Mrd.) | Verlorene Verkäufe | Kundenpreis | HHI | Service-Level | Konkurse |
|---|---:|---:|---:|---:|---:|---:|
| basis | 3.00 ± 0.48 | 26'221 ± 17'570 | 53'668 ± 800 | 0.109 | 98.6 % | 2.6 |
| nachfrage_einbruch | 1.18 ± 0.38 | 16'558 ± 13'108 | 53'709 ± 981 | 0.109 | 99.6 % | 3.4 |
| brauerei_engpass | −4.65 ± 1.94 | 251'024 ± 54'358 | 53'928 ± 1'230 | 0.136 | 44.8 % | 6.8 |
| preiserhoehung_brauerei | −0.25 ± 3.00 | 129'622 ± 73'835 | 54'047 ± 517 | 0.121 | 73.0 % | 5.4 |

- Der Brauerei-Engpass wirkt jetzt stark (vorher +1 Mio. CHF über 5 Jahre):
  rund zehnmal so viele verlorene Verkäufe, Service-Level halbiert, mehr
  Konzentration und mehr Konkurse. Der Kundenpreis steigt dabei nur um etwa 0.5 %;
  der Engpass zeigt sich in leeren Regalen, nicht in höheren Preisen.
- Bei der Preiserhöhung der Brauereien streuen die Seeds stark (Gewinn
  ±3.0 Mrd. statt ±0.5 Mrd. in der Basis). Wer dort mit einem Seed rechnet,
  zieht falsche Schlüsse.
- Ein Nachfrageeinbruch senkt den Gewinn um rund 60 %, entlastet aber die
  Kapazität: weniger verlorene Verkäufe, höheres Service-Level.

Kalibrierungsgrenzen: Die Ökonomie ist empfindlich. Kleine Änderungen an
Fixkosten oder Kapazität kippten in der Entwicklung einzelne Läufe in eine
Lieferkrise (Service-Level unter 40 %). Wer Parameter ändert, sollte deshalb
immer mehrere Seeds messen. Die Zahlen sind Modellannahmen, keine Branchendaten.

---

## 3. Erste Ergebnisse (Stand vor der Kalibrierung)

Dieser Abschnitt zeigt den Stand **vor** der Kalibrierung (Seeds 0, 1 und 2,
92 Tests). Die damaligen Zahlen sind nur noch als Vergleich gedacht: Der Markt
war zu bequem (Systemgewinn 49 % des Umsatzes, Auslastung 10 %). Die aktuellen
Werte stehen im Abschnitt «Experiment».

### Systemkennzahlen (Seed 0)

| Jahr | Gesamtgewinn (Mrd. CHF) | Lost Sales | Ø Qualität | Bullwhip-Ratio | Konzentration (HHI) |
|---:|---:|---:|---:|---:|---:|
| 1 | 1.80 | 16 | 0.73 | 96.8 | 0.101 |
| 3 | 1.78 | 824 | 0.77 | 82.4 | 0.101 |
| 5 | 1.76 | 0 | 0.80 | 75.6 | 0.102 |
| 7 | 1.75 | 204 | 0.83 | 78.5 | 0.113 |
| 10 | 1.73 | 10 | 0.86 | 107.0 | 0.115 |

Die Seeds 1 und 2 liegen sehr nahe daran (Gesamtgewinn 1.73–1.80 Mrd. CHF
pro Jahr). Die Rangfolge der Firmen ist in allen drei Seeds praktisch gleich.

### Kumulierter Gewinn über 10 Jahre (Seed 0, Auswahl)

| Firma | Stufe | Archetyp | Gewinn (Mio. CHF) | Marktanteil Ende |
|---|---|---|---:|---:|
| factory_01 | Brauerei | premium | 4'173 | – |
| factory_02 | Brauerei | growth | 2'869 | – |
| distributor_04 | Distributor | growth | 2'660 | – |
| wholesaler_03 | Wholesaler | premium | 1'334 | – |
| retailer_01 | Retailer | standard | 451 | 10.3 % |
| retailer_02 | Retailer | low_cost | 43 | 14.4 % |
| distributor_02 | Distributor | low_cost | −5 | – |
| wholesaler_02 | Wholesaler | low_cost | −62 | – |
| retailer_10 | Retailer | growth | −133 | 0 % (Konkurs nach Jahr 6) |

### Beobachtungen

1. **Der Gewinn sammelt sich oben in der Kette.** Die zwei Brauereien
   verdienen zusammen rund 7 Mrd. CHF, alle zehn Retailer zusammen etwa
   2.5 Mrd. CHF. Wenige Anbieter auf der oberen Stufe haben mehr
   Verhandlungsmacht.
2. **Marktanteil ist nicht gleich Gewinn.** Die `low_cost`-Retailer haben
   mit gut 14 % den grössten Marktanteil, aber nur rund einen Zehntel des
   Gewinns der `standard`- und `premium`-Retailer. Auf den oberen Stufen
   schreiben die `low_cost`-Firmen sogar Verluste.
3. **Premium lohnt sich.** Auf jeder Stufe gehört eine `premium`-Firma zu den
   Gewinnern; die durchschnittliche Qualität steigt über 10 Jahre von 0.73
   auf 0.86, der durchschnittliche Kundenpreis um rund 17 %.
4. **Aggressives Wachstum kann scheitern.** `retailer_10` (growth) rutscht ab
   Jahr 3 in wachsende Verluste und scheidet in allen drei Seeds nach Jahr 6 aus.
   Danach steigt die Konzentration (HHI) von 0.101 auf 0.115.
5. **Die Lieferfähigkeit ist hoch, der Bullwhip bleibt.** Das Service-Level
   liegt bei 100 %, denn die «Lost Sales» sind Kunden, die bei ihrem
   Wunschhändler nichts bekommen und dann bei einem anderen Händler kaufen
   (Jahr 1, Seed 0: 65'447 Einheiten Nachfrage, 65'447 verkauft). Für den
   einzelnen Händler ist das ein verlorener Verkauf, für den Markt nicht.
   Die Bestellschwankung ist aber
   immer noch 75- bis 130-mal so gross wie die Schwankung der
   Endkundennachfrage. Die Bestellglättung hat die frühere Explosion
   verhindert, gelöst ist das Problem aber nicht.

### Szenarien ab Jahr 5 (Seed 0)

Alle drei Szenarien zweigen vom gleichen Speicherstand nach Jahr 5 ab und
laufen bis Jahr 10. Die Werte sind Unterschiede zum normalen Lauf über die
Jahre 6 bis 10.

| Szenario | Gewinn gesamt | Brauereien | Distributoren | Wholesaler | Retailer | Neue Konkurse |
|---|---:|---:|---:|---:|---:|---|
| Nachfrage −20 % | −1'761 Mio. | −626 Mio. | −504 Mio. | −357 Mio. | −275 Mio. | keine |
| Brauerei-Kapazität −30 % | +1 Mio. | +3 Mio. | −2 Mio. | 0 | 0 | keine |
| Brauerei-Preise +20 % | +183 Mio. | +2'593 Mio. | −1'528 Mio. | −349 Mio. | −533 Mio. | 4 Firmen |

1. **Ein Nachfrageeinbruch trifft alle, oben am stärksten.** Der Gewinn sinkt
   jedes Jahr um rund 350 Mio. CHF, also etwa 20 %. Die Brauereien verlieren
   am meisten, aber keine Firma geht deswegen Konkurs.
2. **Die Brauereien haben viel Reserve.** 30 % weniger Kapazität ändern fast
   nichts. Die Brauereien laufen also weit unter ihrer Grenze. Für einen
   echten Engpass müsste die Kürzung viel grösser sein, oder das Modell hat
   zu viel Kapazität angesetzt. Das ist ein Punkt für die Kalibrierung.
3. **Preismacht verschiebt Gewinn und erzeugt Konkurse.** Höhere
   Brauereipreise verschieben rund 2.6 Mrd. CHF Gewinn zu den Brauereien.
   Die Firmen weiter unten in der Kette verlieren, und vier
   `low_cost`-Firmen gehen Konkurs: `distributor_02` (nach Jahr 7),
   `wholesaler_02` (nach Jahr 8), `retailer_02` und `retailer_06` (beide
   nach Jahr 9). Billiganbieter haben zu wenig Marge, um höhere
   Einkaufspreise aufzufangen.

### Offene Punkte

- Bullwhip-Ratio weiter senken (Forecast-Weitergabe, stärkere Glättung);
  aktuell rund 100.
- Die Ergebnisse in `runs/` stammen von älteren Ständen und sollten neu
  gerechnet werden. Alte Speicherstände sind nicht mehr kompatibel
  (Checkpoint-Version 2).
- Markteintritte neuer Firmen (bei dauerhaft hoher Marge einer Stufe) sind
  noch nicht umgesetzt; die Kennzahl `market_entries` bleibt 0.
- Die Koeffizienten für Löhne, F&E und Handlingkosten sind Schätzungen und
  noch nicht an echten Branchendaten kalibriert.
- Rohstoffe haben jetzt Kosten und einen schwankenden Preisindex. Ein
  börsenartiger Rohstoffmarkt mit Lieferanten liegt weiterhin nur als
  Vorschlag in `docs/commodity-market-proposal.md`.
- Die Beer-Game-Agenten in `team_bundle/` nutzen noch die Mirror-Policy.

---

## Lizenz

Siehe [LICENSE](LICENSE).
