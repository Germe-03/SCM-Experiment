# Bauplan Erweiterung 4: Phasen 21–33

> Stand 2026-11-05. Nichts davon ist umgesetzt. Ausgangspunkt: `main` bei
> `b1441fb` (Phasen 1–20 fertig, 286 Tests grün laut letztem Stand).
> Phasen 21–27 hat David so bestätigt («passt so»). Phasen 28–33 stammen aus
> den bestehenden Vorschlägen und TODOs im Repo und haben noch offene Fragen
> (am Ende jeder Phase markiert).

## Arbeitsregeln

- Deutsch mit Schweizer Rechtschreibung, kein ß. Kurze, einfache Statusmeldungen.
- Code per MCP `delegate-coder` (`delegate_write_file`) schreiben lassen, für
  echte Logik mit `model: "swissai:CSCS-Inference/zai-org/GLM-5.3"`, für
  Kleinkram `ibm/granite4.1:3b`; Diff prüfen, nur bei Fehlern selbst
  nachbessern. Kleine Edits (wenige Zeilen) selbst.
- Tests: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider market_sim/tests`
  (der normale Cache-Ordner `.pytest_cache` ist gesperrt). Lange Läufe im
  Hintergrund starten.
- Ordner `.test-tmp-stocks-*` sind gesperrte Testreste, nicht anfassen.
- Neue Funktionen bekommen einen Schalter in `market.yaml` / `config.py`.
  Wo nichts anderes steht, im Standardlauf eingeschaltet; Tests für alte
  Verhaltensweisen müssen weiter grün sein.
- Pro Phase: Tests ergänzen, alle Tests laufen lassen, `runs/dashboard.html`
  neu erzeugen und im Browser prüfen, ein Commit pro Phase **ohne**
  Co-Authored-By-Zeile. Pushen erst, wenn David es sagt.
- Nach jeder Phase einen Eintrag im Umsetzungs-Log unten ergänzen.

---

## Phase 21: Milliarden statt Millionen

Problem: Texte zeigen «2'652 Mio. CHF» statt «2,65 Mia. CHF».

- `market_sim/texts.py`: neue Funktion `_chf(value)` → unter 1'000 Mio.
  «52 Mio. CHF», ab 1'000 Mio. «2,65 Mia. CHF» (Komma, 2 Stellen, negative
  Werte gleich). Alle `f"{_mio(...)} Mio. CHF"` in `firm_facts`,
  `year_facts` und `_readable()` darauf umstellen.
- Systemprompt in `texts.py`: Regel anpassen, «Mio.» und «Mia.» genau so
  übernehmen wie in den Fakten. `llm.numbers_in` liest «2,65» schon als 2.65.
- `market_sim/dashboard.py`:
  - `pretty()`: Beträge «X Mio. CHF» mit X ≥ 1'000 in den angezeigten Texten
    zu «X/1000 Mia. CHF» (2 Nachkommastellen, Komma) umwandeln, damit auch
    der bestehende Cache `runs/texts_seed0_50y.json` richtig erscheint.
  - `chf()`: «Mrd. CHF» → «Mia. CHF» mit Komma als Dezimalzeichen.
- Tests: `_chf`, `_readable`, Umwandlung «2'652 Mio. CHF» → «2,65 Mia. CHF»,
  «52 Mio. CHF» bleibt.

## Phase 22: Aktienkurs im Reiter Vergleich

- Neue Kennzahl «Aktienkurs» in den Chips von `renderCompare()`
  (`CMP_METRICS`), nur sichtbar, wenn mindestens eine gewählte Firma Kurse hat.
- Grafik mit Wochenwerten aus `D.stocks` im gewählten Zeitraum, Farben der
  Firmen wie im Vergleich.
- Statt «relativ zum Stufenschnitt» zwei Schalter: «Start = 100» und
  «Börsenindex einblenden» (hier **standardmässig aus**).
- Lücken bei Banken, vor dem Börsengang und nach dem Austritt; Hinweis
  «… ist nicht an der Börse».
- Tabelle darunter: letzter Kurs, Veränderung im Zeitraum in %, Höchst- und
  Tiefstkurs mit Jahr.
- Reiter Börse (`sx-compare`) und Firmendetails (`fd-price`): derselbe
  Schalter «Börsenindex einblenden», dort standardmässig **an**. Zustand pro
  Reiter im Browser merken (`store`).
- Tests: Dashboard-Check (cjs) für Kennzahl, Schalter, Index aus.

## Phase 23: ETFs (nur Anzeige)

- Ein ETF ist wie der Börsenindex ein Messinstrument, **noch nicht kaufbar**.
- Gruppen: pro Region (Heimatregion `firm.region`, 8 Regionen), pro Kategorie
  (nur Hersteller: Bier, Wein, Spirituosen, inkl. Importeure), pro Stufe
  (Hersteller, Verteilung, Grosshandel, Detailhandel, Gastronomie).
- Gewichtung nach Börsenwert (Option gleichgewichtet), Start 100 Punkte,
  verkettet wie der Index in `stock_market.py`, damit Börsengänge und
  Austritte keinen Sprung machen. Leerer ETF hat keinen Kurs.
- Umsetzung: `StockMarketConfig` um `etfs_enabled`, Gruppen, Gewichtung;
  neue Klasse `EtfBook` in `stock_market.py`, täglich nach den Kursen;
  eigene Zeilen (nicht in `daily_rows`, sonst hält `_stock_weekly` sie für
  Firmen); Export als `D.etfs` in `dashboard_data.py` (Definitionen,
  Wochenwerte, Mitglieder).
- Dashboard Reiter Börse: Karte «ETFs» mit Umschalter Regionen/Kategorien/
  Stufen, Tabelle «ETF-Übersicht» (Name, Anzahl Firmen, Stand, Rendite,
  grösste Firma, Spaltenfilter), Klick zeigt Mitglieder mit Gewicht;
  Firmendetails «Enthalten in: …».
- Tests: richtige Mitglieder, kein Sprung bei Börsengang/Konkurs, leerer ETF,
  Gleichgewichtung, Determinismus.
- Später (eigene Phase, nicht jetzt): ETFs kaufbar für Firmen/Banken mit
  Gebühr und Ausschüttungen.

## Phase 24: Forschungsbäume

Ersetzt die 10 losen Projekte in `research.py` / `market.yaml`.

- **Ein Baum pro Branche**, von allen Firmen der Branche geteilt, jede Firma
  hat ihren eigenen Fortschritt: Hersteller, Verteilung, Grosshandel,
  Detailhandel, Gastronomie, Banken.
- Stufen mit Voraussetzungen, je höher desto teurer/länger/unsicherer.
  Vorschlag:
  - Hersteller: Prozessautomation → Robotik → Smart Factory (braucht auch
    Prognose-Software); Ausbeute-Optimierung → Rezeptur-Optimierung → eigene
    Hefezucht; Leichtere Flaschen → Mehrwegsystem; Wärmerückgewinnung →
    klimaneutrale Brauerei (+ Reputation); Neue Marke → alkoholfreies Produkt
    → neue Geschmacksrichtung; Wein: kürzere Reifezeit.
  - Verteilung: Routenplanung → Kühlkette → Prognose-Software.
  - Grosshandel: Lagerautomation → Kommissionier-Roboter → Bestellprognose.
  - Detailhandel: Self-Checkout → Kundenkarte → Onlineshop mit Lieferdienst.
  - Gastronomie: Kassen-/Reservationssystem → Küchenautomation → Hausbier
    und Signature-Drinks.
  - Banken: Online-Banking → Kreditscoring (weniger Ausfälle) → Mobile App
    (mehr Kunden).
  - Wirkungen über bestehende Hebel: `component_factor`, `transport_factor`,
    `holding_cost`, Produktivität, neue Marken, Kundenbindung,
    `loss_given_default`, Kundenzahl Bank.
- **Zwei Schritte pro Stufe:** Forschung (Betrag x, Dauer, Erfolgschance)
  und danach Umsetzung (fester Betrag, gleich für alle). Erst nach der
  Umsetzung wirkt die Stufe.
- Mehrere Firmen dürfen dieselbe Stufe gleichzeitig erforschen (voller Preis).
- **«Es spricht sich herum»:** Nach dem ersten Erfolg zahlen Nachzügler
  weniger für die Forschung: einfach −75 %, mittel −50 %, komplex −25 %.
  Die Umsetzung kostet immer gleich viel.
- Wahl: Firmen wählen aus freigeschalteten Stufen; Archetypen bevorzugen
  Bäume/Äste statt einzelner Projekte. Gewinn- und Kassenbedingung wie heute.
- Die heutigen 10 Projekte werden erste Stufen (Vergleichbarkeit).
- Tests: Voraussetzungen, Rabatt nach Komplexität, Umsetzung voller Preis,
  gleichzeitige Forschung, Wirkung erst nach Umsetzung, Übernahme übergibt
  den Fortschritt.

## Phase 25: Patente

- Nur bei wertschöpfenden Firmen: Hersteller (Produkte, Rezepturen,
  Verfahren: Smart Factory, Hefezucht, Mehrweg, alkoholfreies Produkt, neue
  Geschmacksrichtung), dazu Kühlkette (Verteilung) und Kommissionier-Roboter
  (Grosshandel). Detailhandel, Gastronomie, Banken: keine Patente.
- Wer eine patentierbare Stufe als Erste erforscht, kann eine Gebühr zahlen;
  Laufzeit **3 bis 5 Jahre**, die Firma wählt (länger = teurer; Premium und
  reiche Firmen eher lang).
- Während der Laufzeit dürfen andere forschen, aber **nicht umsetzen**.
  Vorbenutzungsrecht: Wer die Umsetzung vor der Anmeldung begonnen hat, darf
  weitermachen. Keine Lizenzen.
- Nach Ablauf dürfen alle umsetzen.
- Übernahme: Patente gehen an die Käuferin. Konkurs: Patent verfällt.
- Börse: `event_shocks` um `patent_granted` (leicht positiv) ergänzen.
- Neues Modul `market_sim/patents.py`, Ereignisse `patent_granted`,
  `patent_expired`, Kosten im Geldfluss.

## Phase 26: Patentverletzung als Straftat

- Neue Straftat nach dem Muster in `StateConfig.offences` / Straftatenlogik:
  nur «willige» Firmen wägen ab, Vorteil gegen geschätzte Entdeckung.
- Entdeckung höher als bei anderen Delikten (z. B. 50 % pro Jahr).
- Bei Entdeckung: Busse an den Staat **und** Schadenersatz an den
  Patentinhaber (unerlaubter Vorteil, mindestens fester Betrag), Nutzung
  sofort stoppen (Wirkung weg), Reputationsverlust, Börsenschock.
- Erscheint in `offence_ledger` («Hat es sich gelohnt?»), Reiter Staat und
  Chronik.

## Phase 27: Dashboard F&E und Messlauf

- Reiter F&E: pro Branche der Baum als Grafik (Stufen eingefärbt nach Anzahl
  Firmen erforscht/umgesetzt, patentiert mit Inhaber und Ablaufjahr,
  gesperrt), Tabelle Patente.
- Firmendetails: eigener Fortschritt als kleiner Baum, Patente,
  Schadenersatz bezahlt/erhalten.
- Reiter Finanzen: Forschung, Umsetzung, Patentgebühren, Schadenersatz als
  eigene Positionen. Reiter Staat: Patentverletzungen.
- Texte/Chronik: Fakten zu Patenten und Patentverletzungen.
- Messlauf 3 Seeds × 50 Jahre: F&E-Ausgaben, Gewinne, Konkurse im
  vernünftigen Rahmen; Ergebnis im Umsetzungs-Log.

---

## Phase 28: Post als Akteur

Vorlage: `docs/post-kuriere-proposal.md` (Schritte 1–3).

- Neues Modul `market_sim/carriers.py` mit `Carrier` und `CarrierMarket`;
  die Post ersetzt den namenlosen Transportdienst (`service_rate`).
- Zuerst gleiche Zahlen wie heute (Tarif 1.4, Kapazität unbegrenzt), Test:
  gleicher Seed → gleiche Ergebnisse.
- Dann Kosten (Fixkosten Netz/Personal, variable Kosten), Einheitstarif mit
  höchstens 5 % Änderung pro Jahr, Post geht nie pleite und nimmt keine
  Kredite, Verlust als `bundesbeitrag`.
- Kapazität und Verspätung: Überlast verlängert die Lieferzeit, nichts geht
  verloren (`environment.py`, Lieferzeit + Wartetage).
- Block `carriers` in `market.yaml`, Standard `enabled: false` bis zur
  Kalibrierung.

## Phase 29: Kuriere und Wahl nach Gesamtkosten

Vorlage: `docs/post-kuriere-proposal.md` (Schritte 4–5).

- Kuriere als normale Firmen mit Kasse, Kredit, Konkurs, Übernahme.
- Eintritt pro Region mit Wahrscheinlichkeit, nur wenn der Posttarif die
  Kurierkosten um eine Mindestmarge übersteigt (Rosinenpicken entsteht von
  selbst); Regionen ausbauen/aufgeben; freier Preis je nach Risiko.
- Kapazität und Zuverlässigkeit (Verspätungs- und Schadenquote).
- Verlader wählen jährlich pro Kundenregion nach Gesamtkosten (Preis × km +
  erwarteter Schaden + erwartete Verspätung + Wechselkosten), Verspätung
  aus dem Vorjahr gelernt.
- Tests: ohne Marge kein Eintritt, Start in dichten Regionen, Kurier kann
  pleitegehen, unzuverlässiger billiger Kurier verliert risikoscheue Kunden.

## Phase 30: Post und Kuriere im Dashboard, Gesetze

- Marktanteile Post / Kuriere / eigene Flotte, Posttarif, Bundesbeitrag,
  Kuriere pro Region auf der Karte, mittlere Verspätung,
  `carrier_report.csv`.
- Optional als Gesetze (`laws.py`): Restmonopol, Konzessionsabgabe,
  Tariffreiheit.
- Kalibrieren, dann `carriers.enabled: true`.

**Entscheid David (2026-11-05):** Die Post bleibt beim Einheitstarif (keine
Rabatte). Nur die Verlader (Hersteller, Verteilung, Grosshandel) kaufen
Transport, Läden nicht. Der Bundesbeitrag wird nur angezeigt und fliesst nicht
über Steuern zurück.

## Phase 31: Börsengang über eine Bank

Vorlage: TODO in `docs/bauplan-banken-boerse.md`.

- Statt «alle Firmen ab Jahr 5»: nur grössere Firmen gehen an die Börse,
  über eine Bank, die eine Gebühr erhält. Nicht kotierte Firmen nur direkt
  (ab 10 %) beteiligbar.
- Auswirkungen auf Index und ETFs (Phase 23) prüfen.

**Entscheid David (2026-11-05):** Börsengang über eine Bank vorerst weglassen.

## Phase 32: Rohstoffbörse ausbauen

Vorlage: `docs/commodity-market-proposal.md`. Heute gibt es bereits
Rohstoffkosten mit schwankendem Preisindex (`commodities` in
`market.yaml`, Variante A).

- Beschaffungsstrategie der Hersteller: Spot, Vorrat (Lagerkosten,
  Kapitalbindung), Termingeschäft (Preis heute für später), gekoppelt an
  `risk_tolerance`.
- Optional Variante B: Preis aus Angebot und Nachfrage aller Hersteller.
- Dashboard: Rohstoffpreise, Einkaufspreis je Hersteller gegen Marktschnitt.

**Entscheid David (2026-11-05):** Vorerst so lassen wie jetzt (Variante A).
**TODO:** Beschaffungsstrategie (Spot, Vorrat, Termingeschäft) und optional
Variante B später umsetzen.

## Phase 33: Offene Punkte der Banken

Vorlage: «Offene Punkte» in `docs/bauplan-banken-boerse.md`.

- Eigenkapitalquote als Eigenkapital / Bilanzsumme statt / Kredite.
- Hausbank und Zweitbank im Firmendetail anzeigen.
- 10-Seed-Messung nachholen und im Log festhalten.

## Nicht eingeplant (Entscheid offen)

- Zigaretten als weitere Produktkategorie (TODO seit Phase 6).
- ETFs kaufbar machen (nach Phase 23).
- Lizenzen für Patente (bewusst weggelassen).

---

## Umsetzungs-Log

(Pro Phase: Datum, was gebaut wurde, Messwerte, Anzahl Tests, Commit.)

- **Phase 21, 2026-11-05:** `texts._chf()` schreibt ab 1'000 Mio. «2,65 Mia. CHF»
  (Fakten, `_readable`, Systemprompt). Dashboard: `pretty()` wandelt alte
  Cache-Texte «2'652 Mio. CHF» um, `chf()` zeigt «Mia.» statt «Mrd.» mit Komma,
  Spaltenfilter liest «Mia.». Neue Tests: `test_texts` (2), `dashboard_money_check.cjs`.
  `runs/dashboard.html` neu, im Browser geprüft (Chronik zeigt z. B. «-4,26 Mia. CHF»).
- **Phase 22, 2026-11-05:** Neue Datei `market_sim/dashboard_stocks.js` (wird wie die
  Spaltenfilter ins Dashboard eingefügt). Reiter Vergleich: Kennzahl «Aktienkurs»
  nur wenn eine gewählte Firma Kurse hat, Schalter «Start = 100» und «Börsenindex
  einblenden» (aus), Hinweis «… ist nicht an der Börse», Tabelle mit letztem Kurs,
  Veränderung, Höchst- und Tiefstkurs mit Jahr; «relativ zum Stufenschnitt» dort
  ausgeblendet. Reiter Börse und Firmendetails: Schalter «Börsenindex einblenden»
  (an), Zustand pro Reiter gemerkt. Test: `dashboard_phase22_check.cjs`.
  Im Browser geprüft (Vergleich, Börse, Firmendetails).
- **Phase 23, 2026-11-05:** `EtfBook` in `stock_market.py` (täglich nach den Kursen,
  eigene Zeilen parallel zu `daily_rows`), ETFs pro Region (8), Kategorie (Bier,
  Wein, Spirituosen, nur Hersteller inkl. Importeure) und Stufe (5); verkettet,
  Start 100, Börsenwert- oder Gleichgewichtung. Schalter `etfs_enabled`,
  `etf_groups`, `etf_weighting`, `etf_base` in `market.yaml`. Export `D.etfs`
  (Definitionen, Wochenwerte). Dashboard: Karte «ETFs» im Reiter Börse mit
  Umschalter, Tabelle mit Spaltenfilter, Mitglieder mit Gewicht, «Enthalten in»
  in den Firmendetails (`dashboard_etfs.js`). `chart()` räumt eine alte Grafik
  auf derselben Fläche jetzt selbst ab. Tests: `test_etfs.py` (10), ETF-Teil in
  `dashboard_phase19_check.cjs`; 300 Tests grün. Seed 0, 50 Jahre: 16 ETFs;
  einzelne ETFs fallen gegen 0 (z. B. Bier), weil die Kurse ihrer Mitglieder um
  über 99 % abstürzen, Nachrechnung aus Wochenkursen bestätigt die Werte.
- **Phase 24, 2026-11-05:** Entscheid David: Bankenbaum später, Wirkungen über
  bestehende Hebel. Neues Modul `research_tree.py` (`ResearchTreeLab`, erbt von
  `ResearchLab`), fünf Bäume in `market.yaml` (`research.trees`, Schalter
  `trees_enabled: true`): Hersteller 15 Stufen, Verteilung, Grosshandel,
  Detailhandel, Gastronomie je 3. Forschung, danach Umsetzung (fester Betrag), erst
  die Umsetzung wirkt; Voraussetzungen, die eine Firma wegen ihrer Kategorie nie
  erreicht, gelten als erfüllt (z. B. Wein: Neue Geschmacksrichtung ohne
  alkoholfreies Produkt). Nachzügler-Rabatt 75/50/25 %, Vorlieben pro Archetyp
  nach Ast (`branch_preferences`), Übernahme übergibt Fortschritt als «erforscht».
  Neue Wirkungen: Reputation, Bekanntheit des Ladens, Marge im Lokal
  (`BrandBook.markup_bonus`), kürzere Reifezeit. Alte Projekte bleiben bei
  `trees_enabled: false` (Tests in `test_research.py` laufen so). Tests:
  `test_research_tree.py` (11); 311 Tests grün. Seed 0, 50 Jahre: 153 Schritte
  (66 Forschung erfolgreich, 31 Fehlschläge, 56 Umsetzungen), 63-mal
  Nachzügler-Rabatt, Kosten total 5,00 Mia. CHF. Hinweis: Die Texte im Cache
  `runs/texts_seed0_50y.json` stammen aus dem Lauf vor Phase 24.
- **Phase 25, 2026-11-05:** Neues Modul `patents.py` (`PatentOffice`), Block
  `patents` in `market.yaml` (an), `patentable: true` bei Smart Factory, Hefezucht,
  Mehrwegsystem, alkoholfreiem Produkt, neuer Geschmacksrichtung, Kühlkette und
  Kommissionier-Roboter. Wer zuerst erfolgreich erforscht, patentiert, wenn er die
  Gebühr tragen kann ((2 Mio. + 1 Mio. pro Jahr) x Preisindex, an den Staat,
  «staat:Patentgebühr» im Geldfluss); Laufzeit 5 Jahre für Premium und reiche
  Firmen, 3 für Billiganbieter, sonst 4. Andere forschen weiter, setzen aber erst
  nach Ablauf um (Vorbenutzungsrecht für bereits laufende oder fertige
  Umsetzungen). Übernahme: Patent an die Käuferin; Konkurs: Patent verfällt.
  Ereignisse `patent_granted` (Börse +0.05), `patent_expired`; Export `D.patents`.
  Tests: `test_patents.py` (10); 321 Tests grün.
- **Phase 33, 2026-11-05:** Eigenkapitalquote der Banken = Eigenkapital /
  Bilanzsumme. Bilanzsumme = grösserer Wert aus Krediten oder Einlagen +
  Eigenkapital (Aktiven: Kredite plus SNB-Reserven; Passiven: Einlagen,
  Eigenkapital und SNB-Refinanzierung für eine Lücke). `CommercialBank` hat neu
  `balance_total`, `capital_ratio` (neu definiert) und `risk_weighted_ratio`
  (Eigenkapital / Kredite, die alte Quote). `bank_reports.csv` und `D.banks`
  zeigen alle drei Werte. Das Dashboard rechnete schon mit derselben Formel
  (`bankRatio`). Entscheid: Kreditgrenze (`min_capital_ratio` 10 %),
  Ausschüttungsgrenze (`target_capital_ratio` 15 %), Sicherheitswertung bei der
  Bankwahl und Auslöser für Zweitkonten rechnen weiter mit Eigenkapital /
  Kredite. Das entspricht einer risikogewichteten Quote: SNB-Reserven haben das
  Risikogewicht 0. Grund: Mit der Bilanzsumme schwankt die Quote mit den
  Einlagen und nicht mit dem Kreditrisiko. Die Schwellen hätten sich so nicht
  vergleichbar umrechnen lassen. Dadurch bleibt das Verhalten unverändert (gleiche
  Seeds, gleiche Ergebnisse). Firmendetail: «Hausbank: … · Zweitbank: …» mit
  Link zur Bankdetailansicht (vorher «Bank: … (Hausbank/Zweitkonto)»). Tests:
  `test_banking.py` (+1), `dashboard_phase19_check.cjs` ergänzt; 322 Tests grün.
  **10-Seed-Messung** (Seeds 1–10, je 50 Jahre, `market_sim.experiment`):

  | | Mittel | Min | Max |
  |---|---|---|---|
  | Firmenkonkurse total | 71.5 | 51 | 110 |
  | Gewinn aller Firmen total | 31,5 Mia. | −17,2 Mia. | 77,0 Mia. |
  | Bankpleiten | 1.5 | 0 | 4 |
  | Neue Banken | 3.5 | 3 | 5 |
  | Aktive Banken im Jahr 50 | 5.0 | 3 | 6 |
  | Zweitkonten eröffnet | 40.8 | 34 | 47 |
  | Kreditablehnungen | 199 | 157 | 270 |
  | Abschreibungen der Banken total | 8,29 Mia. | 5,44 Mia. | 13,5 Mia. |
  | Gewinn der Banken total | 9,92 Mia. | −0,61 Mia. | 23,8 Mia. |
  | EK-Quote (EK / Bilanzsumme), Mittel aller Bankjahre | 21.0 % | 18.0 % | 25.3 % |
  | EK-Quote im Jahr 50 (Mittel aktiver Banken) | 17.9 % | 6.8 % | 26.3 % |
  | Tiefste EK-Quote einer Bank (pro Seed) | 3.1 % | 0.3 % | 7.6 % |
  | Leitzins im Mittel | 0.63 % | 0.27 % | 0.95 % |
  | Teuerung im Mittel | 0.94 % | 0.74 % | 1.11 % |
  | Börsenindex Jahr 50 | 6272 | 428 | 12'140 |

  Die alte Quote (EK / Kredite) erreichte pro Seed Höchstwerte von 12'900 %
  bis 1'742'000 %. Die neue Quote bleibt zwischen 0 und 100 %. Nur neu gegründete
  Banken ohne Kunden zeigen 100 %. Bankpleiten gab es in 6 von 10 Seeds
  (Seed 4: 4 Pleiten, 110 Konkurse, nur noch 3 Banken). In 3 Seeds ist der
  Gewinn aller Firmen über 50 Jahre negativ.
