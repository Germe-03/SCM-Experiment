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
- **Phase 26, 2026-11-05:** Patentverletzung bleibt ausserhalb von `state.offences`
  (alte Zufallsfolgen bleiben gleich), Block `patents.infringement` in `market.yaml`
  (an). `PatentOffice` hat einen eigenen Zufallsstrom: «willige» Firmen wägen bei einer
  fremd patentierten, erforschten Stufe ab (Vorteil = Wirkung x Vorjahresumsatz x 0.2 x
  Restlaufzeit gegen geschätzte Entdeckung x (Busse + Schadenersatz + Reputation)) und
  setzen trotzdem um. Ab dem Jahr nach der Umsetzung jährlich 50 % Entdeckung: Busse an
  den Staat («staat:Busse patentverletzung»), Schadenersatz an den Inhaber (mindestens
  5 Mio. x Preisindex, «schadenersatz:…»), Reputation −5 %, Wirkung weg (`undo_stage`,
  neue Marken werden nicht mehr produziert), Stufe wieder «erforscht», Ereignis
  `offence_detected` (Börsenschock). Unentdeckt bis Ablauf oder Übernahme des Inhabers:
  straflos. Zeilen «patentverletzung» in `offence_ledger` (mit Schadenersatz und
  Inhaber, auch in der CSV). Mit ausgeschaltetem Schalter gleiche Ergebnisse wie vorher
  (12-Jahres-Lauf geprüft). Seed 0, 30 Jahre: 1 Patent, keine Verletzung. Offen:
  Dashboard zeigt «patentverletzung» noch ohne deutschen Namen. Tests:
  `test_patent_infringement.py` (7); 328 Tests grün.
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
- **Phase 27 (Dashboard-Teil), 2026-11-05:** Neue Datei `market_sim/dashboard_rnd.js`
  (Platzhalter `__RND__`), Export `D.rnd_trees` (leer ohne Bäume). Reiter F&E: Baum pro
  Branche als SVG (Chips, eingefärbt nach erforscht/umgesetzt bis Ende Zeitraum, Patent
  mit Inhaber und Ablaufjahr, «gesperrt»), Tabelle «Patente» mit Spaltenfilter, Spalte
  «Schritt» in der Projekttabelle, Ausgaben aufgeteilt in Forschung, Umsetzung,
  Patentgebühren, Schadenersatz (Aufteilung aus abgeschlossenen Projekten geschätzt).
  Firmendetails: kleiner eigener Baum, eigene Patente, Schadenersatz bezahlt/erhalten.
  Finanzen: Karte mit denselben vier Posten. Staat: Patentverletzungen (vorbereitet für
  Phase 26: `compensation`, `holder`), Ledger mit Spalte Schadenersatz falls vorhanden.
  Geldfluss: F&E getrennt in Forschung/Umsetzung, `schadenersatz:<Firma>` mit
  Partnername. Texte: Fakten zu umgesetzten Stufen, Patenten, Schadenersatz und
  Patentverletzungen. Tests: `dashboard_phase27_check.cjs`, `test_phase27_dashboard.py`
  (4); 325 Tests grün. Offen: Messlauf 3 Seeds × 50 Jahre, Sichtprüfung im Browser.
- **Phase 27 Messlauf, 2026-11-05:** 3 Seeds x 50 Jahre auf `main` (Phasen 21-27, 33).
  Forschung 3,26-3,65 Mia. CHF, Umsetzung 1,32-1,49 Mia. CHF pro Lauf; 150-175
  Schritte, 53-65 Umsetzungen, vor allem Gastronomie, Detailhandel und Logistik;
  Hersteller kommen kaum über die erste Stufe hinaus. Gewinn aller Firmen total
  9,2 / -17,1 / 1,7 Mia. CHF; Konkurse 72 / 80 / 85, Übernahmen 46 / 39 / 42
  (im Rahmen der 10-Seed-Messung aus Phase 33). Je Lauf nur 2 Patente (Kühlkette,
  Kommissionier-Roboter), Patentverletzung nur in Seed 2 (2 Jahre, 1-mal entdeckt).
  Dashboard im Browser geprüft (F&E-Baum, Patente, Finanzen, Staat, Firmendetails).
  Offen: Hersteller-Bäume werden kaum genutzt (Kosten und Kassenbedingung prüfen).
- **Phase 28, 2026-11-05:** Neues Modul `carriers.py` (`Carrier`, `CarrierMarket`), Block
  `carriers` in `market.yaml` (`enabled: false` bis zur Kalibrierung). Die Post ersetzt den
  namenlosen Dienst: `Geography.unit_transport_cost` und die Wahl eigene Flotte/Dienst
  fragen den Posttarif statt `service_rate`. Einheitstarif für alle Regionen, einmal im Jahr
  aus Kosten pro Einheit-km plus Marge, höchstens 5 % Änderung. Kosten: Fixkosten Netz und
  Personal (x Preisindex x mittlerer Lohnindex, wachsen mit der Kapazität) plus variable
  Kosten pro km. Verlust deckt der Bund (`bundesbeitrag`, nur angezeigt, Ereignis), die
  Post geht nie pleite und nimmt keine Kredite. Kapazität pro Tag: Überlast hält Pakete
  zurück, sie gehen Tage später ab (längere Lieferzeit), nichts geht verloren; bei hoher
  Auslastung baut die Post nach `expansion_delay_days` aus. Kein eigener Zufall: Der
  Schadenwurf in `ship()` bleibt gleich, darum ist ein Lauf mit Tarif 1.4 fest und
  unbegrenzter Kapazität genau gleich wie ohne Post (Test). Ausgabe `carrier_report.csv`,
  `RunResult.carriers`. Tests: `test_carriers.py` (7); 328 Tests grün.
- **Phase 29, 2026-11-05:** Neues Modul `couriers.py` (`CourierMarket` erbt von
  `CarrierMarket`), Block `carriers.couriers` (an, wirkt nur mit `carriers.enabled`).
  **Entscheid:** Kuriere sind leichte Akteure im `CourierMarket` mit Kasse, Kreditlimite
  (Zins = Leitzins + Aufschlag), Konkurs und Übernahme (Wettbewerbsbehörde: keine
  Übernahme über 60 % Kurieranteil einer Region), keine fünfte Firmenstufe; die volle
  Firmenmaschine (Bank, Börse, Strategien) hätte die Phase vervielfacht. Eintritt pro
  Region (ein Zufallswurf pro Region und Jahr, eigener Zufall `couriers-{seed}`), nur wenn
  der Posttarif die Kurierkosten um `min_margin` übersteigt; Kurierkosten pro km sind in
  dünn besiedelten Regionen höher (`density_exponent`), darum starten Kuriere in der
  Genferseeregion und in Zürich, das Tessin bleibt bei der Post. Regionen ausbauen bei
  Gewinn, aufgeben nach zwei Verlustjahren. Preis je Region frei: unter der Post je nach
  Risikobereitschaft, nie unter Kosten plus Aufschlag; risikofreudige Kuriere sind
  billiger, aber weniger zuverlässig. Verlader im Dienstmodus wählen jährlich pro
  Kundenregion nach Gesamtkosten (Preis x km + erwarteter Schaden + Verspätung aus dem
  Vorjahr + Wechselkosten). Eigene Flotte oder Kauf bleibt die Jahreswahl pro Firma
  (Flottenfixkosten lassen sich nicht auf Regionen aufteilen). Kalibrierung: Wechselkosten
  als Anteil der Transportrechnung statt des Warenwerts, Verspätungskosten eigener Wert
  `delay_cost_per_unit_day` (5 CHF), Kurier-Schadenquote 0,1–1 %; sonst gewann nie ein
  Kurier. Seed 0, 8 Jahre: 2 Eintritte (Genfersee, Zürich), 30 Wechsel, eine Übernahme,
  Regionen auf- und zugemacht. Tests: `test_couriers.py` (6); 334 Tests grün.
- **Phase 30, 2026-11-05:** Neuer Reiter «Transport» (`dashboard_carriers.js`, eingefügt
  über `__CARRIERS__`): Kennzahlen, Marktanteile eigene Flotte / Post / Kuriere,
  Posttarif und Bundesbeitrag, mittlere Verspätung, Kuriere pro Region als kleine Karte,
  Tabelle aller Anbieter. Export `D.carriers`, `carrier_report.csv` (seit Phase 28).
  Gesetze (Restmonopol, Konzessionsabgabe, Tariffreiheit) **nicht gebaut**: sie brauchen
  neue Gesetzesarten in `laws.py` und Eingriffe in Tarif und Wahl, also nicht klein.
  Messlauf 3 Seeds x 50 Jahre, aus / an (Kuriere an): Die Post gerät in eine Spirale.
  Kuriere nehmen ihr dichte Strecken weg, die Fixkosten bleiben, der Tarif steigt jedes
  Jahr um 5 % bis 3,2–3,7 CHF, am Ende fahren alle Verlader mit eigener Flotte (Anteil
  Post und Kuriere 0 %). Bundesbeitrag total 0,73–0,81 Mia. CHF. Gewinne aller Firmen
  total ändern sich stark (Seed 0: 9,2 → 42,0 Mia., Seed 1: −17,1 → −33,3 Mia.,
  Seed 2: 12,7 → −42,5 Mia.), Konkurse 72/80/92 → 56/92/119, Servicegrad Seed 2
  0,97 → 0,78. Darum bleibt `carriers.enabled: false`. Nötig vor dem Einschalten: Post-
  Fixkosten an das tatsächliche Volumen anpassen (oder bei Volumenverlust senken),
  Tarifspirale dämpfen und prüfen, warum der Servicegrad fällt (Verspätungen, Konkurse
  von Kurieren mit Kunden). Tests: `test_dashboard_carriers.py` (2).
