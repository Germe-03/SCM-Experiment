# SCM-Experiment

Experimente zum Wahlmodul **Supply Chain Management** (FHNW BSc Business AI):
vom klassischen Beer Game zu einer agentenbasierten Simulation des Schweizer
Getränkemarkts über 50 Jahre mit wechselnden, konkurrierenden Firmen.

Repository: <https://github.com/Germe-03/SCM-Experiment>

Das Repo hat zwei Teile, die bewusst getrennt bleiben:

| Teil | Ordner | Zweck |
|---|---|---|
| Beer-Game-Abgabe | `team_bundle/` | Vier Agenten (Retailer, Wholesaler, Distributor, Factory) für die `supplychainbench`-Engine des Moduls |
| Markt-Simulation | `market_sim/` | Eigenständige Simulation des Schweizer Getränkemarkts: Firmen, Marken, Kundenklassen, Staat, 50 Jahre |

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

### Stand: eine grosse Simulation (Phasen 0–7)

Statt einzelner Szenarien läuft jetzt ein langer Lauf über 50 Jahre, in dem
der Markt von selbst lebt. Bauplan, Begründungen und Messwerte jeder Phase
stehen in [`docs/bauplan-grosse-simulation.md`](docs/bauplan-grosse-simulation.md).

- **Lebendiger Markt:** Neueintritte, Bank mit Zins und Kreditlimite,
  Sanierung statt Zombie-Firmen, Strategiewechsel durch Ausprobieren und
  Nachahmen, Stornierung blockierter Bestellungen.
- **Kunden und Marken:** 30 Kundenklassen (Einkommen × Alter ×
  Trinkverhalten) mit Höchstpreis; Marken tragen ihre eigene Reputation.
- **Lange Zeit:** Teuerung, Löhne, Produktivität, alternde Bevölkerung,
  Trends; Rezession, Rohstoffknappheit, Kostenschock und Lohnschub treten
  zufällig auf.
- **Getränke und Ausland:** Bier, Wein (Weinlese, Reifung, Jahrgang) und
  Spirituosen mit festem Gesamtbedarf, Importeure mit Wechselkurs und Zoll,
  Export.
- **Orte und Logistik:** acht Regionen, Transportkosten, eigene Flotte oder
  Transportdienst, Ausbau und neue Standorte mit Bauzeit und Abschreibung.
- **Staat:** Gewinnsteuer, Straftaten mit versteckten Bussen, die die Firmen
  erst lernen müssen, Vergiftungsskandal mit Angst, Übernahmen und
  Wettbewerbsbehörde (Verbot, Zerschlagung).
- **F&E-Projekte:** teuer, langsam, unsicher; Ergebnisse sind mehr
  Produktivität, tiefere Rohstoffkosten oder neue Marken (auch alkoholfrei).

Zusätzliche Ausgaben eines Laufs: `brand_report.csv`, `class_report.csv`,
`rnd_projects.csv`. Jede Erweiterung lässt sich in `config/market.yaml` mit
`enabled: false` abschalten.

**Erweiterung 2 (Phasen 8–12,** siehe
[`docs/bauplan-erweiterung-2.md`](docs/bauplan-erweiterung-2.md)**):**
Marktanteil auf allen Stufen, Negativzins auf grosse Kassen, Bilanz «Hat sich
die Straftat gelohnt?», weitere F&E-Projekte, neuer Vergleich, Marktaufbau,
Entscheidungsprotokoll mit Konkursanalyse, schematische Schweizer Karte,
Bevölkerung mit Personas, Marketing, Restaurants, Beteiligungen, neue
Gesetze mit vorsichtiger Beurteilung ihrer Folgen, regionaler Arbeitsmarkt
und Texte vom lokalen Sprachmodell (Firmengeschichten, Chronik, Chat).

**Erweiterung 3 (Phasen 13–20,** siehe
[`docs/bauplan-banken-boerse.md`](docs/bauplan-banken-boerse.md)**):**
SNB mit Leitzins nach Taylor-Regel, drei Geschäftsbanken (später bis sechs)
mit Hausbank und höchstens zwei Konten pro Firma, Kreditlinie und
Kreditklemme, Bankpleite mit 30 % Einlagensicherung und freier Bankwahl,
Börse mit Tageskursen ab Jahr 5 und verkettetem Index, kleine Beteiligungen
über Börse und Hausbank. Neue Ausgaben: `bank_reports.csv`,
`stock_daily.csv`, `stock_weekly.csv`.

**TODO:**

- Zigaretten als eigene Kategorie mit Sucht und Regulierung (Idee 15).
- Begrenzter Regalplatz, damit Läden sich stärker spezialisieren.
- Bestellungen pro Marke statt Gesamtmengen.
- Lieferzeit abhängig von der Distanz (heute nur in der Lieferantenwahl).
- Grösseres Ollama-Modell (z. B. `qwen2.5:7b`) für besseres Deutsch.
- Börsengang über eine Bank statt «alle Firmen ab Jahr 5 handelbar»
  (siehe [`docs/bauplan-banken-boerse.md`](docs/bauplan-banken-boerse.md)).

### Modell in Kürze

- **Netzwerk:** Detailhandel → Grosshandel → Verteilung → Hersteller
  (Brauereien, Weingüter, Brennerei, Importeure). Zu Beginn 27 Firmen
  (`config/firms.yaml`), jede kauft bei allen aktiven Firmen der Stufe
  darüber; Firmen kommen und gehen während des Laufs.
- **Archetypen:** `low_cost`, `standard`, `reliable`, `premium`, `growth`;
  sie bestimmen Preis, Qualität, Löhne, Risiko und Lagerziel und können
  gewechselt werden.
- **Nachfrage:** 30 Kundenklassen mit Höchstpreis (`config/consumers.yaml`),
  fester Alkoholbedarf aufgeteilt auf Bier, Wein und Spirituosen, Marken mit
  eigener Reputation (`config/brands.yaml`), Sommer-Saisonalität, Trends.
- **Beschaffung:** Base-Stock-Bestellungen mit Obergrenze, Aufteilung auf
  mehrere Lieferanten nach Lieferpreis inkl. Transport, Zuverlässigkeit,
  Qualität und Reputation; zu lange offene Bestellungen verfallen.
- **Finanzen:** alle Kosten in realen CHF, Bank mit Zins und Kreditlimite,
  Sanierung, Steuern, Bussen, Investitionen mit Abschreibung.
- **Alle Stellschrauben** stehen in `config/market.yaml`; jede Erweiterung
  lässt sich dort mit `enabled: false` abschalten.

### Starten

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install pydantic pyyaml pytest
```

```bash
python -m market_sim.dashboard --seed 0 --out runs --open
```

```bash
python -m market_sim.run --seed 0 --out runs/seed0
```

```bash
python -m market_sim.experiment --seeds 0-9 --skip-years 2 --out runs/experiment
```

```bash
python -m pytest market_sim
```

- `dashboard` rechnet einen Lauf und schreibt `runs/dashboard.html` mit
  Reitern für Überblick, Markt, Firmen, Vergleich, Lieferkette, Finanzen,
  Staat, F&E, Marktaufbau und Ereignisse. Der Vergleich zeigt bis zu sechs
  Firmen in einem Diagramm, wahlweise relativ zum jährlichen Stufenschnitt.
- `run` schreibt `annual_reports.csv`, `firm_ranking.csv`, `system_kpis.csv`,
  `events.csv`, `brand_report.csv`, `class_report.csv` und
  `rnd_projects.csv` und `offence_ledger.csv`.
- `experiment` rechnet mehrere Seeds parallel und schreibt
  `experiment_runs.csv` (pro Seed) und `experiment_summary.csv` (Mittelwert,
  Streuung, Minimum, Maximum pro Kennzahl), ohne die Anlaufjahre.
- Ein 50-Jahres-Lauf dauert einige Minuten.


### Texte und Chat mit dem Sprachmodell

Standard ist GLM-5.3 über die kostenlose SwissAI-API (CSCS,
`ollama.provider: api` in `config/market.yaml`). Den Schlüssel von
<https://serving.swissai.svc.cscs.ch/api_key> als Umgebungsvariable
`SWISSAI_RESEARCH_API_KEY` setzen; er kommt nie ins Repo. Höchstens 14
Anfragen pro Minute, 112 Texte dauern so rund 8 Minuten. Mit
`provider: ollama` läuft stattdessen das lokale Modell (`llama3.2:3b`), dann
verlässt nichts den Rechner, aber ohne Grafikkarte dauert es Stunden. Das
Modell schreibt nur aus Fakten, die Python berechnet; Texte mit Zahlen, die
nicht in den Fakten stehen, werden durch eine Kurzfassung ersetzt.

```bash
python -m market_sim.dashboard --seed 0 --out runs --texts
```

```bash
python -m market_sim.serve --dir runs --port 8770
```

`--texts` schreibt Firmengeschichten und eine Jahreschronik ins Dashboard
(auf einem Rechner ohne Grafikkarte etwa eine bis zwei Stunden für 50 Jahre,
danach zwischengespeichert). `serve` liefert das Dashboard unter
<http://localhost:8770/dashboard.html> aus und beantwortet Fragen im Chat
unten rechts.

### Spielmodus (Firmen-Cockpit)

Im Spielmodus gründest du selbst eine Firma in einer der fünf Branchen
(Hersteller, Verteiler, Grosshändler, Detailhandel, Gastro) und führst sie
Monat für Monat. Alle anderen Firmen laufen wie im Experiment weiter.

```bash
python -m market_sim.game.server --port 8771 --saves runs/spielstaende
```

Danach im Browser <http://localhost:8771> öffnen.

- **Ablauf:** Gründung mit Branche, Region und Spieldauer (5 bis 50 Jahre).
  Eine Runde ist ein Monat. «Rest des Jahres überspringen» springt zum
  Januar, «Bis zum Ende simulieren» übergibt die Firma an den Autopiloten.
  Die Simulation läuft immer bis Jahr 50; danach erzeugt der Server das
  normale Beobachter-Dashboard (`/dashboard`, gespeichert unter
  `runs/spiele/<zeit>_<firma>/dashboard.html`).
- **Sicherung:** Nach jeder Runde wird automatisch nach
  `runs/spielstaende/automatisch.json` gesichert (die vorherige Sicherung
  bleibt als `automatisch_vorher.json`). Beim Start lädt der Server diese
  Sicherung wieder. «Neues Spiel» sichert das alte Spiel vorher als
  `vor_neuem_spiel.json`.
- **Reiter:** Übersicht, Firma, Markt, Forschung, Logistik, Einkauf (beim
  Hersteller: Produktion), Lager, Finanzen, Bank, Abschlüsse, Börse,
  Rohstoffe, Bevölkerung, Holding, Graubereich, Hilfe.
- **Händler** kaufen pro Getränkeart und Marke ein, wählen pro Marke einen
  Grosshändler und setzen pro Marke einen eigenen Verkaufspreis (auch alle
  um x % auf einmal). Lagerplatz und Regalkosten pro geführter Getränkeart
  begrenzen das Sortiment.
- **Hersteller** kaufen Rohstoffe zu Tageskursen ein; produziert wird so viel,
  wie Kapazität und Rohstoffe zulassen.
- **Lieferverträge:** Zwischen Hersteller und Verteiler, Verteiler und
  Grosshändler sowie Grosshändler und Detailhandel/Gastro lassen sich
  Verträge mit Menge pro Tag, Preis und Laufzeit abschliessen
  (`market_sim/contracts.py`). Vertragsware wird zuerst bestellt und zuerst
  geliefert. Andere Firmen nehmen Vorschläge an, wenn Preis und Menge passen,
  und schlagen dem Spieler selbst Verträge vor.
- **Holding:** Gekaufte Firmen werden Töchter; für jede Tochter braucht es
  einen CEO (Avatare in `market_sim/game/static/avatare/`, Bildvorlagen in
  [`docs/avatar-prompts.md`](docs/avatar-prompts.md)).
- **Berater:** ein Sprachmodell (GLM über SwissAI) gibt Tipps, sieht aber nur
  eigene und öffentliche Zahlen.
- Entwürfe und Schnittstellen: `docs/entwurf-spielmodus.md` und
  `docs/spielmodus-feedback1.md` bis `docs/spielmodus-feedback6.md`.

### Regeln, die im November 2026 geändert wurden

Diese Änderungen gelten für die ganze Simulation, also auch für das
Experiment; frühere Läufe sind damit nicht mehr direkt vergleichbar.

- **Übernahmen sind freiwillig:** Angeschlagene Firmen stehen zum Verkauf,
  Käufer entscheiden selbst nach Preis, Wert und Geld (`state.py`).
- **Börse:** Alle Firmen vom Start sind ab Tag 1 kotiert, jede neue Firma
  nach 3 Jahren (`tradable_from_year: 1`, `listing_min_years: 3`). Der
  Startkurs folgt dem Ertragswert.
- **Grundkosten nach Grösse:** Kleine Hersteller zahlen die Grundkosten nur
  anteilig (`fixed_costs.base_reference_units`).
- **Rohstoffkrisen abgeschwächt:** Missernte ×1.12 (vorher 1.30),
  Kostenschock ×1.10 (vorher 1.25).
- **Preisuntergrenze:** Firmen verkaufen nicht dauerhaft unter ihren
  Vollkosten des Vorjahres plus 2 % (`cost_floor_margin`); bei tiefer
  Auslastung höchstens bis zum Konkurrenzpreis.
- **Autopilot bestellt nach dem Absatz:** Händler bestellen mindestens so
  viel, wie sie verkaufen, mit einem Gedächtnis für die Nachfrage der
  letzten Monate. Vorher führte die zu tief gemessene Nachfrage zu leeren
  Regalen und einer Abwärtsspirale.
- **Abschlüsse:** Für jede Firma gibt es Erfolgsrechnung, Bilanz,
  Geldflussrechnung und Kalkulation pro Flasche (`financials.py`), im
  Dashboard im Reiter «Abschlüsse».

### Speicherstände

Mit `--checkpoints` speichert `run` nach jedem Jahr den ganzen Zustand als
`<out>/checkpoints/year_XX.pkl`. Ein Lauf lässt sich damit fortsetzen, das
Ergebnis ist exakt dasselbe wie ohne Unterbruch. Speicherstände sind
Pickle-Dateien; lade nur selbst erzeugte.

```bash
python -m market_sim.run --resume runs/seed0/checkpoints/year_20.pkl --out runs/resumed
```

### Ergebnisse

Phase 8 ergänzt Umsatzanteile und HHI für alle vorgelagerten Stufen,
Kategorieanteile für Hersteller sowie Negativzinsen auf grosse Guthaben.
Die Zinsschwelle ist das Maximum aus dem inflationsbereinigten Mindestbetrag
und dem konfigurierten Anteil am Vorjahresumsatz. `negative_interest_enabled`
schaltet die neue Zinsregel ab. `negative_interest_<stage>` misst nur die
Belastung; `interest_cost_<stage>` enthält weiterhin den Nettozins.

`offence_ledger.csv` enthält pro Firma, Straftat und Jahr die tatsächliche
Ersparnis, Busse, den geschätzten Reputationsschaden, Nettoertrag und das
Urteil `paid_off`. Die Schadensschätzung ist keine zusätzliche Buchung.
Neue Forschungsprojekte senken einzelne Materialkomponenten, Transport-
oder Lagerkosten; Robotik spart Personal bei gleicher Kapazität.
Projekte können mit `enabled` abgeschaltet und mit `selection_weight`
innerhalb der Archetyp-Präferenzen gewichtet werden.
Die Messung steht in [`docs/bauplan-erweiterung-2.md`](docs/bauplan-erweiterung-2.md).
Checkpoint-Version 11 ist erforderlich; ältere Speicherstände werden abgewiesen.

Die Messwerte jeder Ausbauphase stehen im Messprotokoll von
[`docs/bauplan-grosse-simulation.md`](docs/bauplan-grosse-simulation.md).
Stand nach Phase 7 (10 Seeds, 50 Jahre): Gewinn 12 % des Endkundenumsatzes
(5.6–15.7 %), Service Level 98 %, pro Lauf rund 37 Markteintritte und
19 Konkurse.

### Offene Punkte

- Bullwhip-Ratio senken (Forecast-Weitergabe, stärkere Glättung).
- Koeffizienten für Löhne, F&E und Handling sind Schätzungen, nicht an
  Branchendaten kalibriert.
- Ein börsenartiger Rohstoffmarkt liegt als Vorschlag in
  `docs/commodity-market-proposal.md`.
- Die Beer-Game-Agenten in `team_bundle/` nutzen noch die Mirror-Policy.

---

## Lizenz

Siehe [LICENSE](LICENSE).
