# Bauplan 2: Nachvollziehen, mehr Markt, Ollama

Stand: 2026-11-03. Grundlage sind Davids 18 Ideen nach Abschluss von Phase 7
(siehe `bauplan-grosse-simulation.md`). Die Phasen sind nach Nutzen und
Abhängigkeiten geordnet: zuerst sichtbar machen, was schon passiert, dann
neue Marktmechanik, zuletzt die Ollama-Funktionen, die auf allem aufbauen.

Regeln wie im ersten Bauplan: nach jeder Phase lauffähig, Tests grün, 10 Seeds
gemessen, Messprotokoll am Ende, alle Stellschrauben in YAML mit
`enabled`-Schalter, Commit pro Phase ohne Co-Autor-Zeile.

## Zuordnung der Ideen

- Phase 8, Schnelle Gewinne: 4 Marktanteil aller Stufen, 9 Negativzins,
  7 Lohnt sich die Straftat, 18 mehr F&E-Projekte, 16 Vergleich neu,
  11 Marktaufbau-Grafik
- Phase 9, Nachvollziehen: 3 Entscheidungsprotokoll und Konkursanalyse,
  1 Schweizer Karte, 15 Bevölkerung mit Personas (Idee 14 Markenwege gestrichen)
- Phase 10, Mehr Markt: 8 Marketing, 2 Restaurants, 10 Beteiligungen,
  17 neue Gesetze
- Phase 11, Arbeitsmarkt: 13
- Phase 12, Ollama: 12 Firmengeschichten, 5 Beobachter, 6 Chat im Dashboard

---

## Phase 8: Schnelle Gewinne

**4. Marktanteil auf jeder Stufe.** Heute haben nur Händler einen
Marktanteil. Neu: Anteil am Umsatz der eigenen Stufe, also Grosshandel am
Einkauf der Händler, Verteilung am Einkauf des Grosshandels, Hersteller am
Einkauf der Verteilung (bei Herstellern zusätzlich pro Kategorie). Spalte
`market_share` in `annual_reports.csv` für alle, HHI pro Stufe in
`system_kpis.csv`, im Dashboard in Firmenliste, Detail und Vergleich.

**9. Negativzins auf grosse Kassen.** Heute gibt es 0.5 % Habenzins auf
jedes Guthaben. Neu: Habenzins bis zu einer Schwelle (z. B. 50 % des
Jahresumsatzes oder ein fixer Betrag), darüber ein Negativzins
(z. B. −0.75 %). Firmen mit viel Geld sollen investieren, Marketing machen
oder Beteiligungen kaufen (Phase 10). Neue Kennzahl: Negativzinsen pro Stufe.

**7. Hat sich die Straftat gelohnt?** Pro Firma und Straftat wird mitgezählt:
gesparter Betrag (tiefere Löhne, billigere Rohstoffe, gesparte Steuern),
bezahlte Bussen, geschätzter Schaden durch Reputationsverlust (entgangene
Marge). Ergebnis «hat sich gelohnt» oder «hat sich nicht gelohnt» mit
Zahlen. Neue Datei `offence_ledger.csv`, im Dashboard eine Tabelle im Reiter
Staat und ein Abschnitt in der Firmen-Detailansicht.

**18. Mehr F&E-Projekte.** Die Rohstoffkosten bestehen schon aus Malz,
Hopfen, Verpackung und Energie. Neue Projekte senken gezielt eine
Komponente: leichtere Flaschen (Verpackung), Wärmerückgewinnung (Energie),
Ausbeute-Optimierung (Malz und Hopfen), Routenplanung (Transportkosten),
Lagerautomation (Lagerkosten), Haltbarkeit (weniger Schwund), Robotik
(weniger Mitarbeitende bei gleicher Kapazität). Jedes Projekt mit Kosten,
Dauer, Erfolgswahrscheinlichkeit und Stufen, für die es passt.

**16. Vergleich neu gestalten.** Heute: acht Diagramme mit vielen Linien,
schwer lesbar. Neu:
- links eine feste Auswahlliste mit Suche und Farbe pro Firma (höchstens 6),
- oben eine Kennzahl wählen (Gewinn, Cash, Marktanteil, Reputation, Preis,
  Auslastung …), darunter ein grosses Diagramm für diese eine Kennzahl,
- darunter eine Vergleichstabelle (letztes Jahr, Durchschnitt, bestes und
  schlechtestes Jahr) mit Hervorhebung des Besten,
- Option «relativ zur Stufe» (Wert minus Stufendurchschnitt), damit man
  Firmen verschiedener Stufen fair vergleicht.

**11. Marktaufbau-Grafik.** Neuer Reiter «Marktaufbau»: die Stufen von oben
nach unten (Hersteller nach Kategorie, Verteilung, Grosshandel, Detailhandel,
Kunden), jede Firma als Balken über die Jahre, von Gründung bis Austritt,
mit Farbe für die Art des Austritts (Konkurs, Übernahme, Vergiftung).
Darüber eine Übersicht, was es zu kaufen gibt: Kategorien, Marken mit
Hersteller und Einführungsjahr. Ein Klick auf einen Balken öffnet die Firma.

---

## Phase 9: Nachvollziehen

**3. Entscheidungsprotokoll und Konkursanalyse.** Heute sieht man nur
Ergebnisse. Neu wird jede Entscheidung mit Grund festgehalten:
- jährlich: Preisband, Lohn, F&E-Budget, Lagerziel, Archetyp, Straftaten
  ja/nein mit der geschätzten Rechnung, Transportwahl, Investitionen,
  F&E-Projekt, Marketing (ab Phase 10),
- täglich verdichtet: Bestellmengen und Preise als Monatswerte.
Neue Datei `decisions.csv`. Für jede ausgeschiedene Firma erstellt das
Programm eine **Konkursanalyse**: die drei grössten Verlusttreiber der
letzten Jahre (Kostenblöcke, Umsatzrückgang, Bussen, Zinsen), die
Entscheidungen davor und die Marktereignisse in derselben Zeit, als
Zeitstrahl in der Firmen-Detailansicht. Regelbasiert, ohne LLM, damit die
Ursachen nachprüfbar sind.

**1. Karte der Schweiz.** Neuer Reiter «Karte» mit den acht Regionen als
vereinfachte Umrisse (eingebettetes SVG, keine externe Kartenquelle).
Ebenen zum Umschalten: Bevölkerung, Firmenstandorte (Symbol pro Stufe),
Händlerkapazität pro Einwohner, Margen der Händler, Transportwege der
grössten Lieferbeziehungen. Mit dem Zeitraum-Regler sieht man, wie sich das
über die Jahre verschiebt. Dafür wird neu pro Region gemessen, wie viel
verkauft wird (heute nur pro Laden).

**15. Bevölkerung mit Personas.** Neuer Reiter «Bevölkerung»: die 30 Klassen
als Raster (Einkommen × Alter × Trinkverhalten) mit Grösse, Konsum,
Höchstpreis, Kaufanteil und Lieblingskategorie. Zu jeder Klasse zwei
Personas, eine Frau und ein Mann (die Klassen sind nicht nach Geschlecht
getrennt, darum immer beide): Name, Alter, Wohnort, Beruf, Einkommen,
Trinkgewohnheit, typische Marke und ein Satz, was ihr beim Kauf wichtig ist.
Die Steckbriefe entstehen aus Vorlagen mit Schweizer Namen und Daten der
Klasse; die Texte kann Ollama in Phase 12 ausschmücken.

---

## Phase 10: Mehr Markt

**8. Marketing.** Firmen und Marken bekommen ein Marketingbudget.
Marketing baut **Bekanntheit** auf (pro Marke, 0 bis 1), die langsam wieder
zerfällt. Bekanntheit fliesst in die Punktzahl der Kunden ein (je nach
Klasse verschieden stark, junge Klassen reagieren stärker). Händler machen
Werbung für den Laden (Laden-Bekanntheit). Entscheidung jährlich nach
Archetyp und Kasse; der Staat kann Werbung einschränken (Phase 10, Gesetze).
Kennzahlen: Marketingausgaben, Bekanntheit pro Marke.

**2. Restaurants.** Neue Stufe parallel zum Detailhandel: Restaurants und
Bars kaufen beim Grosshandel, verkaufen deutlich teurer (Faktor etwa 3 für
Service), haben Sitzplätze als Kapazität und hohe Fixkosten. Jede Klasse
trinkt einen Teil ausser Haus (junge und reiche mehr, 65+ weniger). Der
Ausgehanteil reagiert auf Preise, Rezession und Trends. Restaurants nehmen
an Eintritten, Konkursen, Übernahmen und Strategiewechseln teil.

**10. Beteiligungen.** Firmen mit viel Geld können Anteile an anderen
Firmen kaufen (z. B. 10 bis 49 %), statt sie ganz zu übernehmen. Sie
erhalten einen Anteil am Gewinn als Dividende und tragen Wertverluste mit.
Kaufpreis nach Gewinn und Substanz. Die Wettbewerbsbehörde zählt
Beteiligungen über 25 % beim Marktanteil mit. Im Dashboard: wer hält was,
als Verflechtungsdiagramm.

**17. Neue Gesetze.** Der Staat erlässt zu zufälligen Zeitpunkten Gesetze
aus einem Katalog: Mindestlohn, höhere Alkoholsteuer, Werbeverbot für
Spirituosen, Mehrwegpflicht (Verpackung teurer), strengere Kontrollen
(höhere Entdeckungsrate), Zuckersteuer für Alkoholfreies, Importzoll.
Wichtig nach Davids Vorgabe:
- **Firmen kennen die Folgen nicht.** Sie merken sie an den eigenen Zahlen
  und passen sich über die bestehende Lernlogik an (Strategiewechsel,
  Preise, Schätzungen beim Staat).
- **Das Dashboard zeigt Folgen erst, wenn sie klar sind.** Nach einem Gesetz
  steht zuerst «Folgen noch unklar». Erst wenn sich eine Kennzahl nach
  mindestens drei Jahren deutlich stärker verändert hat als ihre normale
  Schwankung vor dem Gesetz, wird die Folge angezeigt («Händlermarge seit
  dem Mindestlohn −1.2 Prozentpunkte»). Sonst bleibt es bei «keine klare
  Folge erkennbar».

---

## Phase 11: Arbeitsmarkt (13)

Heute stellen Firmen ein, ohne dass es Arbeitskräfte knapp werden lässt.
Neu: Pro Region ein Pool an Arbeitskräften, der mit der Bevölkerung wächst.
Firmen konkurrieren über den Lohn; wer schlecht zahlt, verliert Leute an
besser zahlende Firmen der Region (Abwerbung). Ist der Pool knapp, steigen
die Löhne, Stellen bleiben offen und die Kapazität sinkt. Robotik aus der
F&E (Phase 8) wird dadurch wertvoller. Kennzahlen: offene Stellen,
Abwerbungen, Lohnniveau pro Region (auch auf der Karte).

---

## Phase 12: Ollama

Voraussetzung auf diesem Rechner (geprüft): Ollama 0.40.9 ist installiert,
vorhanden ist `llama3.2:3b`. Keine NVIDIA-Grafikkarte, 16 GB Arbeitsspeicher.
Das reicht, aber Texte entstehen langsam. Vorschlag: `qwen2.5:7b` für
Geschichten und Beobachtungen (besseres Deutsch, läuft im Hintergrund),
`llama3.2:3b` für den Chat (schneller). Alles bleibt abschaltbar; Tests
laufen mit einem Ersatz-LLM ohne Ollama.

Grundsatz für alle drei Funktionen: Python rechnet die Fakten, das Modell
schreibt nur Text, und jede Zahl im Text wird gegen die Fakten geprüft.

**12. Firmengeschichten.** Nach einem Lauf erhält jede Firma eine kurze
Geschichte (5 bis 8 Sätze): Gründung, Strategie, Wendepunkte, warum sie
gewachsen oder gescheitert ist. Grundlage sind Entscheidungsprotokoll und
Konkursanalyse aus Phase 9. Gespeichert in `stories.json`, angezeigt in der
Firmen-Detailansicht. Laufzeit: etwa eine halbe bis eine Stunde für
70 Firmen auf diesem Rechner, darum als eigener Befehl
(`python -m market_sim.stories`).

**5. Beobachter.** Ein Jahreskommentar wie in einer Wirtschaftszeitung:
was im Jahr wichtig war, wer gewonnen und verloren hat, welche Ereignisse
gewirkt haben. Als Reiter «Chronik» im Dashboard, ein Abschnitt pro Jahr.

**6. Chat unten rechts.** Ein Chat-Symbol im Dashboard. Weil eine HTML-Datei
nicht zuverlässig direkt mit Ollama sprechen kann, startet ein kleiner
lokaler Server (`python -m market_sim.serve`), der das Dashboard ausliefert
und Fragen an Ollama weitergibt. Das Modell bekommt Werkzeuge, um gezielt
Daten nachzuschlagen (Kennzahlen eines Jahres, eine Firma, Ereignisse,
Entscheidungen), statt alles auf einmal zu lesen. Antworten nennen die
Quelle («laut Jahresbericht Jahr 23»). Ohne laufenden Server zeigt das
Symbol einen Hinweis, wie man ihn startet.

---

## Entscheidungen (2026-11-03)

1. Idee 14 (Markenwege) ist gestrichen.
2. Restaurants sind eine eigene Stufe neben dem Detailhandel.
3. Ollama nutzt das vorhandene `llama3.2:3b`; das Modell ist in YAML
   wählbar, `qwen2.5:7b` kann später ergänzt werden (Download nicht ohne
   Davids Zustimmung).
4. Reihenfolge wie vorgeschlagen: Phase 8 bis 12. Umsetzung mit Codex, bei
   erreichtem Codex-Limit übernimmt Claude.

## Messprotokoll

- **2026-11-04, Phase 8:** Marktanteile für alle Stufen, Kategorieanteile
  für Hersteller und HHI für Grosshandel, Verteilung und Hersteller ergänzt.
  Grosse Guthaben zahlen 0.75 % Negativzins oberhalb der höheren Schwelle
  aus 50 Mio. CHF mit Preisindex und 50 % des Vorjahresumsatzes.
  Die Straftatenbilanz zeigt tatsächliche Ersparnisse, Bussen und geschätzten
  Reputationsschaden (`reputation_value_factor: 0.5`) in
  `offence_ledger.csv`, im Reiter Staat und bei der Firma.
  Sechs neue F&E-Projekte senken Material-, Transport- und Lagerkosten
  oder sparen mit Robotik Personal bei gleicher Kapazität. Der Vergleich
  zeigt höchstens sechs Firmen, eine Kennzahl und optional den Abstand zum
  Stufenschnitt. Marktaufbau zeigt Marken und Firmenlebensläufe als SVG.
  Checkpoint-Version auf 11 erhöht.
  Erste Messung mit gleichen Projektgewichten: Gewinn im Mittel 9.18 %
  des Endkundenumsatzes, Service Level 95.69 %, schwächster Seed nur
  76.33 %. Deshalb nur die Auswahlgewichte der sechs neuen Projekte
  (`research.projects[].selection_weight`) von 1.0 auf 0.25 gesenkt;
  bestehende Projekte behalten 1.0. So werden Kapazitätsinvestitionen
  weniger verdrängt. Zinssätze, Schwellen, Projektkosten und Wirkungen
  blieben unverändert.
  Zweite Messung: Seeds 0–9, jeweils 50 Jahre, Auswertung ab Jahr 3.
  Gewinnquote im Mittel **9.50 %** (Spanne **3.65–15.66 %**),
  Service Level **97.96 %** (Spanne **95.45–99.54 %**).
  Der Gewinnmittelwert liegt im Zielband; zwei einzelne Seeds liegen
  ausserhalb. Alle Seeds liegen über der Mindest-Lieferquote von 85 %.
  Im Mittel 35.6 Eintritte, 20.9 Konkurse und 25.5 Übernahmen je Lauf
  im ausgewerteten Zeitraum. Ergebnisse unter
  `market_sim/runs/phase8_check/`, erste Messung unter `phase8_initial/`.
  **172 Tests bestanden**, einschliesslich identischer Fortsetzung aus
  einem Checkpoint mit den neuen Projektwirkungen und der Straftatenbilanz.
  Dashboard für drei Jahre erzeugt; JavaScript-Syntax und ausführbare
  Vergleichsprüfungen mit Node geprüft. Eine Sichtprüfung im Browser war
  nicht möglich, weil der Browserzugriff nicht erreichbar war.
- **2026-11-04, Phase 9:** Entscheidungsprotokoll (`decisions.csv`: jährliche
  Planung jeder Firma, Monatsmittel von Bestellmengen und Preisen,
  Straftat-Entscheide mit der eigenen Schätzung der Firma, Investitionen,
  Projekte, Strategiewechsel, Übernahmen) und regelbasierte Konkursanalyse
  (`exit_analysis.json`: die grössten Treiber der letzten bis zu 5 Jahre,
  Entscheidungen und Marktereignisse, ein deutscher Satz pro Firma; Treiber
  unter 1 % des Umsatzes werden weggelassen). Neue Reiter «Karte»
  (schematische Schweiz aus einem groben Umriss, in die 8 Regionen geteilt;
  Ebenen Bevölkerung, Firmen, Händler pro Kopf, Händlermarge, Umsatz pro
  Region; Umsatz pro Region über das Einzugsgebiet jedes Ladens verteilt,
  `region_report.csv`) und «Bevölkerung» (30 Klassen als Raster, je eine
  Frau und ein Mann als Persona aus Vorlagen, `personas.json`). In der
  Firmendetailansicht eine Zeitleiste der Entscheidungen mit Filtern und
  ein Kasten «Warum ausgeschieden?». Neue Hersteller heissen nach ihrer
  Kategorie. Codex erreichte mitten in der Phase sein Limit; Dashboard,
  Tests und Korrekturen (kaputte Umlaute in YAML und Texten, gelockerte
  Prüfung der Eintrittsnamen) hat Claude gemacht. Die Ökonomie ist
  unverändert: Seed 0 über 10 Jahre ergibt vorher und nachher genau
  CHF 9'190'532'019 Gewinn, darum keine neue Kalibrierung.
