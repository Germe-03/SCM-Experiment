# Bauplan: Eine grosse Markt-Simulation statt vieler Szenarien

Stand: 2026-11-03. Grundlage sind die 20 Erweiterungsideen von David und der
aktuelle Code in `market_sim/` (22 feste Firmen, 1 Produkt, 3 Kundensegmente,
10 Jahre, Szenarien als Abzweig vom Speicherstand).

## Ziel

Ein einziger langer Lauf (50 Jahre), in dem der Markt von selbst lebt: Firmen
kommen und gehen, wechseln ihre Strategie, kaufen einander, bauen Standorte,
verkaufen mehrere Getränke und Marken an echte Kundenklassen. Was heute ein
Szenario ist (Nachfrageeinbruch, Brauerei-Engpass, Preisschock), wird zu einem
zufälligen Ereignis innerhalb dieses Laufs, so wie heute schon Hitzesommer und
Rückruf.

## Regeln für den ganzen Umbau

1. **Nach jeder Phase läuft die Simulation.** Keine Phase lässt den Code halb
   umgebaut zurück. Jede Phase endet mit grünen Tests und einem Messlauf.
2. **Immer mehrere Seeds messen.** Die Wirtschaft im Modell reagiert
   empfindlich. Jede Phase endet mit `market_sim.experiment` über mindestens
   10 Seeds und einer kurzen Notiz im Abschnitt «Messprotokoll» unten.
3. **Alle Zahlen in YAML.** Neue Stellschrauben kommen in `config/*.yaml`,
   nicht in den Code.
4. **Neue Funktionen lassen sich abschalten** (`enabled: false`), damit man
   alt und neu vergleichen kann und alte Tests weiterlaufen.
5. **Speicherstand-Version erhöhen**, sobald sich der gespeicherte Zustand
   ändert (`CHECKPOINT_VERSION` in `checkpoint.py`, heute 3).
6. **Jedes neue Ereignis landet in `events.csv`**, jede neue Grösse in
   `system_kpis.csv` oder `annual_reports.csv` und im Dashboard.
7. **Tests zuerst**, Code über Codex (siehe Skill `codex-dev`).

## Zuordnung der 20 Ideen

- Phase 0 (Vorarbeit): Grundlage für 1, 11, 19
- Phase 1 (Lebendiger Markt): 1 Neueintritte, 5 Geldknappheit, 20 Strategiewechsel
- Phase 2 (Kunden und Marken): 7 Kundenklassen, 10 Marken, 4 Reputation und Zahlungsbereitschaft
- Phase 3 (Lange Zeit): 16 50 Jahre und Trends, 3 Lohnkosten, Szenarien werden Ereignisse
- Phase 4 (Mehr Getränke, Ausland): 14 andere Getränke, 6 Wein, 12 Import, 13 Export
- Phase 5 (Orte und Logistik): 17 Standorte und Wege, 2 Transportdienst, 19 mehrere Standorte
- Phase 6 (Staat): 9 Straftaten, 11 Übernahmen und Zerschlagung, 15 Zigaretten (optional)
- Phase 7 (Ausbau): 18 F&E-Projekte, 8 LLM-Bericht

Der LLM-Bericht (8) hängt von nichts ab und kann jederzeit vorgezogen werden.

---

## Phase 0: Vorarbeit

**Warum:** Heute stehen alle 22 Firmen fest in `firms.yaml`, und jede Firma
hat eine feste Lieferantenliste. Neue Firmen, Übernahmen und Standorte gehen
so nicht.

**Was gebaut wird:**

- Lieferanten werden nicht mehr als Liste gespeichert, sondern bei Bedarf
  bestimmt: «alle aktiven Firmen der Stufe darüber». Die Liste in `firms.yaml`
  bleibt als optionale Einschränkung erlaubt.
- Ein Firmenregister, in das man während des Laufs Firmen eintragen und
  austragen kann (heute gibt es nur `close_firm` in `environment.py`).
  Betroffen sind `models.py`, `environment.py`, `runner.py`, `policies.py`.
- Der Ereignis-Rahmen aus `_draw_market_events` (`runner.py`) wird allgemein:
  Ein Ereignis hat Typ, Wahrscheinlichkeit pro Jahr, Dauer, Stärke und
  Wirkung. Die drei bestehenden Ereignisse ziehen dorthin um.
- Laufzeitmessung: Wie lange dauern 10, 30 und 50 Jahre heute? Wo geht die
  Zeit hin? Das Ergebnis steht im Messprotokoll und ist die Messlatte für
  die späteren Phasen.

**Fertig, wenn:** Alle bestehenden Tests grün sind und ein Lauf mit Seed 0
Zahl für Zahl dasselbe Ergebnis liefert wie vorher.

---

## Phase 1: Lebendiger Markt (Ideen 1, 5, 20)

Diese Phase verändert die bestehende Simulation am wenigsten und bringt am
meisten Leben hinein.

### 1a. Neueintritte (Idee 1)

- Am Jahresende würfelt jede Stufe, ob eine neue Firma eintritt.
  Wahrscheinlichkeit = Grundwert + Zuschlag, wenn die Marge der Stufe über
  einer Schwelle liegt. Höchstens 1 Eintritt pro Stufe und Jahr, und eine
  Obergrenze für die Firmenzahl pro Stufe.
- Die neue Firma bekommt einen zufälligen Archetyp, wenig Startkapital,
  kleine Kapazität und tiefe Reputation (etwa 0.4–0.5). Namen kommen aus
  einer Namensliste in YAML.
- Ereignis `market_entry`, Kennzahl `market_entries` (gibt es schon, steht
  heute immer auf 0).

### 1b. Bank, Zinsen und Geldknappheit (Idee 5)

Heute kostet negatives Cash keinen Zins: Firmen leihen sich gratis bis zum
Minus ihres Startkapitals. Das wird ersetzt.

- Negatives Cash ist ein Kredit. Zins = Grundzins + Aufschlag je nach Risiko
  (Verlustjahre, Verschuldung im Verhältnis zum Umsatz).
- Jede Firma hat eine Kreditlimite, die von ihrer Lage abhängt. Positives
  Cash bekommt einen kleinen Habenzins.
- Die Konkursregel wird: «Die Bank kündigt den Kredit», also Cash unter der
  Kreditlimite. Die heutige feste Regel (−1 × Startkapital, 4 Jahre negativ)
  fällt weg oder bleibt als Fallback abschaltbar.
- Neue Kennzahlen: Zinsaufwand, Verschuldung pro Stufe.

### 1c. Strategiewechsel (Idee 20)

Heute bleibt der Archetyp einer Firma für immer gleich.

- Wer mehrere Jahre schlecht abschneidet (Verlust oder Rendite im untersten
  Drittel der Stufe), darf den Archetyp wechseln.
- Gewählt wird so: mit kleiner Wahrscheinlichkeit zufällig (Ausprobieren),
  sonst der Archetyp, der in der eigenen Stufe in den letzten 3 Jahren am
  besten lief (Nachahmen). Keine Firma weiss, was wirklich am besten ist.
- Ein Wechsel kostet: Umstellungskosten und eine kurze Reputationsdelle.
  Danach gilt eine Sperrfrist von einigen Jahren.
- Ereignis `strategy_change` mit altem und neuem Archetyp.

**Fertig, wenn** (10 Seeds, 30 Jahre):

- In jeder Stufe gibt es über den Lauf Eintritte.
- Die Firmenzahl pendelt, statt auf das Minimum zu fallen oder dauerhaft an
  der Obergrenze zu kleben.
- Strategiewechsel kommen vor, aber nicht jedes Jahr bei jeder Firma.
- Die Margen liegen weiter in den Zielbändern aus dem README.

---

## Phase 2: Kunden und Marken (Ideen 7, 10, 4)

Der grosse Umbau. Danach kauft nicht mehr «der Markt» Bier, sondern
Kundenklassen kaufen Marken in Läden.

### 2a. Kundenklassen (Idee 7)

- Neue Datei `config/consumers.yaml`, rund 30 Klassen aus drei Merkmalen,
  zum Beispiel Einkommen (5 Stufen) × Alter (3) × Trinkverhalten (2).
- Jede Klasse hat: Anzahl Personen, Verbrauch pro Kopf und Jahr, Höchstpreis,
  Gewichte für Preis, Qualität, Marken-Reputation, Laden-Reputation und
  Verfügbarkeit.
- Anker für die Zahlen: rund 7.5 Mio. Erwachsene, nicht 9 Mio. Der Verbrauch
  aller Klassen zusammen muss die heutige Jahresnachfrage ergeben
  (94'400 Simulationseinheiten). Für echte Werte: BFS (Einkommen,
  Bevölkerung) und Schweizer Brauerei-Verband (Bierkonsum pro Kopf, grob
  55 Liter pro Jahr; zu prüfen).
- Der Höchstpreis ersetzt die heutige Elastizitätsformel in
  `ConsumerDemandGenerator` (`runner.py`): Wer nichts unter seinem
  Höchstpreis findet, kauft nichts. Das ist ein echter verlorener Verkauf.
- Die heutigen 3 Segmente bleiben als abschaltbare Variante, damit man
  vergleichen kann.

### 2b. Marken (Idee 10)

- Neues Datenmodell `Brand`: Besitzer (Brauerei), Positionierung, Qualität,
  Reputation. Jede Brauerei startet mit 1–2 Marken.
- **Lager werden pro Marke geführt**, auf allen Stufen (heute eine Zahl pro
  Firma). Bestellungen und Lieferungen ebenfalls. Das ist der teuerste Teil
  des Umbaus und betrifft vor allem `environment.py` und `policies.py`.
- Händler legen jährlich ihr Sortiment fest: welche Marken, mit welchem
  Anteil am Lager.

### 2c. Reputation bestimmt Zahlungsbereitschaft (Idee 4)

- Zwei Reputationen: die **Marke** (Qualität, Rückrufe, später Werbung und
  Skandale) und der **Laden** (Lieferfähigkeit, Preisstabilität, Löhne, wie
  heute).
- Der Höchstpreis einer Klasse für eine Marke = Grund-Höchstpreis ×
  Faktor aus der Marken-Reputation. Gute Marken dürfen teurer sein.
- Die Marken-Reputation ändert sich langsam und wird im Dashboard pro Marke
  über die Jahre gezeigt. Das beantwortet die Frage «welche Gesamtreputation
  hat ein Bier am Ende».

> **Umgesetzt mit Vereinfachung (2026-11-03):** Bestellungen bleiben
> Gesamtmengen. Jede Lieferung trägt die Marken-Mischung des Lieferanten mit
> (`FirmRuntime.stock`, `incoming_brands`), Brauereien produzieren ihre Marken
> im Verhältnis der Vorjahresverkäufe. Händler wählen ihr Sortiment also nicht
> direkt; es ergibt sich aus der Wahl ihrer Lieferanten. Bestellungen pro Marke
> sind ein möglicher späterer Ausbau. Marken- und Klassenwerte stehen in
> `brand_report.csv` und `class_report.csv` statt in `system_kpis.csv`, weil
> die Zahl der Marken während des Laufs wächst.

### Kaufentscheid pro Tag (ersetzt `_fulfill_consumer_demand`)

1. Jede Klasse hat ihren Tagesbedarf.
2. Kandidaten sind alle Paare (Laden, Marke), die vorrätig sind und unter dem
   Höchstpreis liegen.
3. Jedes Paar bekommt eine Punktzahl nach den Gewichten der Klasse, der
   Bedarf wird nach Punktzahl verteilt.
4. Was ein Laden nicht liefern kann, geht an das nächstbeste Paar; was
   übrig bleibt, ist verloren.

**Laufzeit:** 30 Klassen × Läden × Marken pro Tag ist deutlich mehr Rechnung
als heute. Vor und nach dem Umbau messen. Wenn es zu langsam wird, die
Verteilung mit numpy rechnen.

**Neue Kennzahlen:** Marktanteil pro Marke, Nichtkäufe pro Klasse, mittlerer
bezahlter Preis pro Klasse.

**Fertig, wenn:** Gesamtnachfrage und Margen ungefähr wie vor dem Umbau
liegen (10 Seeds), und arme Klassen bei Preiserhöhungen sichtbar aus dem
Markt fallen, reiche nicht.

---

## Phase 3: Lange Zeit (Ideen 16, 3) und Szenarien werden Ereignisse

### 3a. 50 Jahre

- Standard wird 50 Jahre.
- **Teuerung:** ein Preisindex, der Löhne, Fixkosten, Rohstoffe und
  Höchstpreise der Kunden langsam mitzieht. Ohne Teuerung wären Preise und
  Löhne 50 Jahre lang gleich.
- **Lohnkosten (Idee 3):** Löhne steigen über die Zeit etwas schneller als
  die Teuerung, dazu gibt es das Ereignis «Lohnschub» (z. B. Fachkräftemangel).
  So wird Idee 3 eine Entwicklung statt einer einzigen Zahl, und die Firmen
  können sich anpassen.
- **Bevölkerung:** Die Klassen wachsen oder schrumpfen langsam, das Alter
  verschiebt sich.

### 3b. Trends (Idee 16)

- Liste von Trends in YAML, zum Beispiel Craft-Bier, alkoholfrei, Gesundheit,
  günstig, Premium, später Wein-Boom.
- Ein Trend verschiebt die Gewichte und den Verbrauch bestimmter Klassen
  zugunsten bestimmter Marken-Merkmale.
- Alle 3–8 Jahre (Zufall) wechselt der Trend, mit einem Übergang über
  1–2 Jahre. Ereignis `trend_change`.
- Dafür bekommen Marken Merkmale (z. B. `craft`, `alkoholfrei`), die eine
  Brauerei über eine neue Marke oder später über F&E erreicht.

### 3c. Szenarien werden Ereignisse

- `nachfrage_einbruch` wird «Rezession», `brauerei_engpass` wird
  «Rohstoffknappheit», `preiserhoehung_brauerei` wird «Kostenschock». Jedes
  hat eine Wahrscheinlichkeit, Dauer und Stärke im Ereignis-Rahmen aus
  Phase 0.
- `scenario.py` bleibt als Werkzeug für gezielte Vergleiche, ist aber nicht
  mehr der Hauptweg.

**Dashboard:** Zeitachse über 50 Jahre, Trends und Ereignisse als farbige
Bänder im Hintergrund.

**Fertig, wenn:** 10 Seeds über 50 Jahre laufen, der Markt am Ende noch
Wettbewerb hat (genug Firmen, kein Dauermonopol), und Trends sichtbar
Gewinner und Verlierer erzeugen. Laufzeit pro Seed im Messprotokoll.

---

## Phase 4: Mehr Getränke und Ausland (Ideen 14, 6, 12, 13)

### 4a. Getränkekategorien (Idee 14)

- Neue Ebene über der Marke: Kategorie (Bier, Wein, Spirituosen). Jede
  Kategorie hat Herstellungsdauer, Rohstoffe, Preisband, Haltbarkeit.
- **Fester Bedarf:** Jede Klasse hat einen festen Alkoholbedarf (in
  Standardgläsern) und verteilt ihn nach Vorliebe und Trend auf die
  Kategorien. Liegt eine Kategorie über dem Höchstpreis, weicht die Klasse
  teilweise auf eine andere aus.
- Neue Hersteller pro Kategorie (Weingüter, Brennereien) auf der obersten
  Stufe. Wholesaler und Distributoren handeln mehrere Kategorien.
- Läden haben begrenzten Regalplatz und wählen ihr Sortiment. So entstehen
  Spezialisten (Weinhandlung) und Vollsortimenter von selbst.

### 4b. Wein (Idee 6)

- Wein wird einmal pro Jahr geerntet und reift je nach Sorte 1–3 Jahre.
  Die Weingüter müssen also Jahre im Voraus entscheiden, wie viel sie machen.
- Die Qualität eines Jahrgangs hängt vom Wetter ab (das bestehende Ereignis
  «Ernteausfall» wird zu «Wetterjahr» mit guter oder schlechter Ernte).

### 4c. Import (Idee 12)

- Importeure auf der obersten Stufe, ohne eigene Produktion: Sie kaufen im
  Ausland zu einem Preis in EUR.
- Wechselkurs CHF/EUR als Zufallspfad, Zoll, längere Lieferzeit.
- Ausländische Marken haben vollständige Reputation wie inländische.

### 4d. Export (Idee 13)

- Hersteller können ins Ausland verkaufen: Nachfrage zum Weltmarktpreis,
  minus Transport, abhängig vom Wechselkurs. Nur Marken über einer
  Qualitätsschwelle.
- Export fängt Überkapazität auf und macht den Wechselkurs wichtig.

**Fertig, wenn:** Es nach 20 Jahren sowohl spezialisierte als auch
Vollsortiment-Läden gibt, der Wein-Jahrgang sichtbar auf Preise und Gewinne
wirkt und ein starker Franken Importe fördert und Exporte bremst.

---

## Phase 5: Orte und Logistik (Ideen 17, 2, 19)

### 5a. Regionen und Wege (Idee 17)

- 8–12 Regionen (Kantone gebündelt) mit Bevölkerung und einer
  Distanzmatrix in YAML. Die Kundenklassen werden auf die Regionen verteilt.
- Jede Firma hat einen Standort. Läden verkaufen in ihrer Region.
- Transportkosten pro Einheit und Kilometer, mit einem Treibstoffindex.
  Die Lieferzeit hängt von der Distanz ab (heute fest 2 Tage).
- Die Lieferantenwahl (`selection.py`) rechnet Distanz und Lieferzeit ein
  (das Gewicht `lead_time` gibt es schon).

### 5b. Selber liefern oder Transportdienst (Idee 2)

- Selber liefern: Fixkosten für die eigene Flotte, dazu Risiken (Bruch,
  Verspätung, Unfall) mit Wahrscheinlichkeit.
- Transportdienst: teurer pro Einheit und Kilometer, dafür zuverlässiger
  und er zahlt Schäden. Er schafft selbst keinen Mehrwert.
- Jede Firma entscheidet jährlich, wie sie liefert, je nach eigener
  Risikobereitschaft (`risk_tolerance` gibt es schon in `strategy.py`).
- Zuerst ist der Transportdienst ein Akteur von aussen ohne Kapazitätsgrenze.
  Später kann er eine echte Firma mit eigener Flotte werden.

### 5c. Mehrere Standorte und Ausbau (Idee 19)

- Eine Firma kann einen bestehenden Standort ausbauen oder einen neuen
  bauen. Kosten: Baukosten, Bauzeit (1–2 Jahre ohne Wirkung), danach
  Abschreibung über mehrere Jahre. Finanziert über Cash oder Kredit
  (Phase 1).
- Ein neuer Standort öffnet eine neue Region.

**Fertig, wenn:** Firmen in dicht besiedelten Regionen anders abschneiden
als in abgelegenen, und die Wahl Transportdienst oder eigene Flotte je nach
Firma verschieden ausfällt.

---

## Phase 6: Staat (Ideen 9, 11, 15)

### 6a. Der Staat

- Ein Akteur mit Gewinnsteuer, Alkoholsteuer (pro Kategorie), Kontrollen,
  Bussen und einer Wettbewerbsbehörde.

### 6b. Straftaten (Idee 9)

- Katalog in YAML, zum Beispiel:
  - Lohndumping: Lohnkosten tiefer
  - Pfusch an Rohstoffen: Rohstoffkosten tiefer, Gefahr einer Vergiftung
  - Preisabsprache: Preise in einer Region höher
  - Steuerhinterziehung: weniger Steuern
- Jede Tat hat einen Nutzen, eine Entdeckungswahrscheinlichkeit pro Jahr,
  eine Busse (fix + Anteil am Umsatz) und einen Reputationsschaden.
  Manche Taten lohnen sich tatsächlich, weil die Busse kleiner ist als der
  Nutzen.
- **Die Firmen kennen die wahren Werte nicht.** Jede Firma startet mit einer
  eigenen, zufälligen Schätzung und passt sie an, wenn sie Urteile gegen
  andere sieht (Urteile sind öffentlich). Sie entscheidet nach erwartetem
  Nutzen und eigener Risikobereitschaft.
- **Vergiftung:** Pfusch kann zu Kranken und Toten führen. Folgen: Die Firma
  wird sofort geschlossen (Konkurs). Die Toten fallen dauerhaft aus der
  Nachfrage. Dazu kommt Angst: Die Nachfrage der ganzen Kategorie sinkt um
  einen Anteil, der langsam abklingt (Halbwertszeit in YAML). Bekannte
  Marken mit guter Reputation trifft die Angst weniger. Die Stärke ist
  einstellbar, Standard ist ein Skandal, der spürbar ist, aber nicht den
  ganzen Markt zerstört.
- Ereignisse `offense_detected`, `fine`, `poisoning`.

### 6c. Übernahmen und Zerschlagung (Idee 11)

- Am Jahresende: Firmen kurz vor dem Konkurs werden zuerst zum Kauf
  angeboten, dazu freiwillige Übernahmen.
- Käufer brauchen Cash oder Kredit. Preis = Substanzwert + Aufschlag.
  Übernommen werden Kapazität, Kunden, Marken und Mitarbeiter.
- Die Wettbewerbsbehörde verbietet eine Übernahme, wenn der Marktanteil
  danach über einer Schwelle läge. Liegt eine Firma über einer höheren
  Schwelle, muss sie einen Standort verkaufen (Zerschlagung, braucht
  Phase 5).
- Ereignisse `takeover`, `takeover_blocked`, `breakup`.

### 6d. Zigaretten (Idee 15, optional)

- Neue Kategorie ohne Alkohol, mit eigener Lieferkette (Tabakfirmen).
- Neu ist die **Sucht:** Die Nachfrage hängt stark vom Vorjahr ab und
  reagiert kaum auf den Preis. Dazu hohe Steuern und Werbeverbote.
- Nur bauen, wenn nach Phase 6 noch Zeit bleibt.

**Fertig, wenn:** In 10 Seeds Straftaten vorkommen, manche entdeckt werden
und manche nicht, die Firmen ihre Schätzung sichtbar anpassen, Übernahmen
stattfinden und die Wettbewerbsbehörde mindestens einmal eingreift.

---

## Phase 7: Ausbau (Ideen 18, 8)

### 7a. F&E-Projekte (Idee 18)

- Statt nur eines Budgets gibt es einen Projektkatalog: neue Marke, tiefere
  Rohstoffkosten, mehr Kapazität pro Mitarbeiter, alkoholfreies Bier (passt
  zu den Trends), längere Haltbarkeit.
- Jedes Projekt hat Kosten, Dauer und Erfolgswahrscheinlichkeit. F&E ist
  bewusst teuer und unsicher.
- Firmen wählen Projekte passend zu ihrem Archetyp.
- Eigene Dashboard-Seite: Budget, laufende Projekte, Erfolge und Misserfolge
  pro Firma.

### 7b. Bericht mit lokalem LLM (Idee 8)

- Neues Modul `market_sim/report.py` und Schalter `--report` in `run.py`.
- Python rechnet zuerst die Fakten aus (grösste Änderungen, Konkurse,
  Übernahmen, Trends, Skandale) und gibt sie als kompaktes JSON weiter.
  Das LLM liest keine rohen CSV-Dateien.
- Aufruf über Ollama auf dem eigenen Rechner (`http://localhost:11434`),
  Modell in YAML wählbar (z. B. ein Qwen- oder Gemma-Modell mit 8–14 Mrd.
  Parametern, je nach Grafikkarte).
- Prüfung danach: Jede Zahl im Text muss in den Fakten vorkommen, sonst wird
  der Abschnitt markiert.
- Ausgabe `report.md` und ein Reiter im Dashboard.
- Tests mit einem Ersatz-LLM, damit die Tests ohne Ollama laufen.

---

## Offene Entscheidungen für David

1. **Übernahmen über Stufen hinweg:** Darf eine Brauerei einen Händler
   kaufen? Das würde die feste Stufenordnung aufbrechen. Vorschlag: zuerst
   nur innerhalb einer Stufe.
2. **Alte Nachfrage behalten?** Die 3 Segmente und die Elastizitätsformel als
   abschaltbare Variante behalten (Vorschlag) oder ganz entfernen.
3. **Grösse der Vergiftung:** Wie viele Tote, wie stark die Angst? Vorschlag:
   spürbar, aber nicht marktzerstörend, einstellbar.
4. **Zigaretten:** ja oder nein?
5. **Regionen:** wie viele? Vorschlag: 8–12.
6. **Transportdienst:** Akteur von aussen (Vorschlag) oder echte Firma mit
   eigener Flotte und eigenem Konkursrisiko?
7. **Das Beer Game in `team_bundle/`** bleibt unberührt.

## Risiken

- **Kalibrierung:** Jede Phase verschiebt Margen und Konkurse. Ohne Messung
  über viele Seeds kippt der Markt still in eine Dauerkrise.
- **Laufzeit:** 50 Jahre × Klassen × Marken × Regionen kann pro Seed viele
  Minuten dauern. Früh messen, notfalls numpy.
- **Zu viele Stellschrauben:** Jede Phase bringt neue Parameter. Pro Phase
  nur die nötigen einführen und im Messprotokoll festhalten, welche
  geschätzt und welche belegt sind.
- **Phase 2 ist der Engpass:** Lager pro Marke betreffen fast den ganzen
  Code. Diese Phase in kleine Schritte teilen (zuerst Klassen mit einer
  Marke pro Brauerei, dann Sortiment, dann Höchstpreis).

## Messprotokoll

Pro Phase: Datum, Befehl, Seeds, Jahre, wichtigste Kennzahlen, Laufzeit pro
Seed, was angepasst wurde.

- **2026-11-03, Phase 0:** Referenz und Tests mit
  `.venv\Scripts\python.exe -m pytest market_sim -q` sowie Seed 0 über 10 Jahre.
  114 Tests bestanden. Die vor dem Umbau erfassten Werte blieben exakt gleich:
  Gesamtgewinn CHF 5'806'633'636.570863, 26'748 verlorene Verkäufe und
  Bullwhip-Ratio 139.688565 im Jahr 10. Einzelmessungen mit Seed 0:
  10 Jahre 26.66 s, 30 Jahre 82.13 s, 50 Jahre 135.94 s. cProfile über
  10 Jahre: 61.14 s mit Profil-Overhead; kumuliert entfielen 46.05 s auf
  `MarketEnvironment.step`, 12.59 s auf `_apply_rnd`, 9.06 s auf
  `split_order` und 5.91 s auf `_fulfill_consumer_demand`. Noch nichts
  optimiert.
- **2026-11-03, Phase-0-Kalibrierung:**
  `.venv\Scripts\python.exe -m market_sim.experiment --seeds 0-9 --scenarios basis --years 10 --out runs/phase0_check`.
  Der parallele Gesamtlauf dauerte 50.52 s; als vergleichbare Laufzeit pro
  Seed gilt die Einzelmessung von 26.66 s. Auswertung der Jahre 6 bis 10:
  neun Seeds hatten im Mittel 99.54 % Service Level, Stufenmargen von 2.9 %
  (Retailer), 1.9 % (Wholesaler), 4.0 % (Distributor) und 7.8 % (Factory)
  sowie 2.44 Konkurse. Seed 6 kollabierte mit 36.20 % Service Level und zehn
  Konkursen und drückte den Mittelwert aller Seeds auf 93.20 %. Keine Werte
  angepasst, weil Phase 0 die bestehende Seed-0-Rechnung exakt erhalten muss;
  die Zielgrösse Systemgewinn zu Endkundenumsatz bleibt damit unverändert bei
  den im README kalibrierten 11.7 % für Seeds 0 bis 4.
- **2026-11-03, Phase 1:** Neueintritte, Bank mit Zins und Kreditlimite,
  Strategiewechsel. Messung mit eigenem Skript (10 Seeds parallel, je
  30 Jahre, `run_simulation`). Erster Lauf mit allen drei Funktionen: 6 von
  10 Seeds brachen zusammen (Gewinn −91 % des Umsatzes, Service Level 60 %).
  Einzeln abgeschaltet zeigte sich: Die Bank allein ist harmlos (10.2 %,
  97.3 %), Neueintritte (−0.5 %, 89.6 %) und Strategiewechsel (1.3 %,
  79.7 %) lösten den Zusammenbruch aus. Ursache war ein alter Modellfehler:
  Bestellungen blieben bei einem langsamen Lieferanten unbegrenzt in der
  Warteschlange (z. B. 3'265 Einheiten Rückstand bei einer Brauerei mit
  88 Einheiten Tageskapazität, während die andere Brauerei 920 Einheiten an
  Lager hatte). Die Kunden zählten diese Bestellungen als «unterwegs» und
  bestellten nie anderswo. Behoben mit `policy.max_backlog_days: 10`: Was
  über 10 Tageskapazitäten des Lieferanten hinaus offen ist, wird storniert.
  Ergebnis mit allen Funktionen (30 Jahre, 10 Seeds): Gewinn 7.8 % des
  Endkundenumsatzes (5.8–10.2 %), Service Level 97.8 % (tiefstes Jahr 76 %),
  im Mittel 14.5 Neueintritte und 17.3 Konkurse pro Lauf, 0.49
  Strategiewechsel pro Firma und 10 Jahre. Jede Stufe hatte Eintritte, die
  Firmenzahl pendelt (Retailer 6–12, Wholesaler 3–9, Distributoren 2–6,
  Brauereien 2–4). Seed 6 bricht nicht mehr zusammen. Ohne die drei neuen
  Funktionen, nur mit Stornierung: 13.1 % und 98.4 %. Laufzeit rund 110 s pro
  Seed über 30 Jahre bei 10 parallelen Läufen. 127 Tests bestanden. Neue
  Stellschrauben im Strategiewechsel (`count_bottom_third`,
  `min_return_gap`, `stages`) sind vorhanden, aber auf den Standardwerten.
- **2026-11-03, Phase 2:** 30 Kundenklassen mit Höchstpreis und 4 Marken
  (2 pro Brauerei, neue Brauereien bekommen eine eigene Marke). Messung wie
  Phase 1 (10 Seeds, 30 Jahre, alle Funktionen an). Drei Fehler beim Aufbau
  gefunden und behoben: (1) Händler mit leerem Lager bekamen keine Nachfrage
  und bestellten deshalb nie nach; (2) kleine Klassen rundeten ihre wenigen
  Flaschen pro Tag immer auf dieselbe bestbewertete Kombination aus Laden und
  Marke, die Händler gingen reihenweise Konkurs (Gewinn 2.4 %, am Ende nur
  2–5 Händler); jetzt werden die Wünsche aller Klassen zuerst mit Bruchteilen
  summiert und erst dann gerundet; (3) Höchstpreise der unteren Einkommen und
  die Preisfaktoren der Marken waren zu streng. Angepasst: Höchstpreise
  4.8 / 5.4 / 6.0 / 6.8 / 8.0 CHF je Einkommensstufe, Preisfaktoren Premium
  1.10, Standard 1.00, Günstig 0.95. Ergebnis: Gewinn 14.3 % des
  Endkundenumsatzes (8.7–17.0 %), Service Level 98.9 % (tiefstes Jahr 61 %),
  14.4 Neueintritte und 15.2 Konkurse pro Lauf, 0.49 Strategiewechsel pro
  Firma und 10 Jahre, am Ende 4–11 Händler. Preistest nach 10 Jahren (Seed 0,
  volle Lager): Bei 20 % höheren Ladenpreisen kauft die tiefste
  Einkommensstufe nichts mehr (Anteil ohne Kauf von 0 % auf 100 %), die
  Stufen 2 bis 5 kaufen weiter (unter 2 % ohne Kauf). Laufzeit rund 250 s pro
  Seed über 30 Jahre bei 10 parallelen Läufen, gut doppelt so lang wie in
  Phase 1; noch nicht optimiert. Das alte Modell bleibt mit
  `consumer_model: segments` wählbar.
