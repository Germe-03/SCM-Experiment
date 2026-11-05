# Umsetzungsvorschlag: Post und Kuriere als eigene Transportanbieter

> Vorschlag, noch nicht implementiert. Erstellt 2026-11-04.
> Ziel: Der heutige anonyme «Transportdienst» wird zu echten Anbietern. Zu
> Beginn gibt es nur die **Post** (staatlich, kann nicht pleite gehen, nimmt
> keine Kredite auf). Im Lauf der 50 Jahre können **private Kuriere** in den
> Markt eintreten und der Post Kunden abjagen.

## 1. Warum

Heute (Phase 5, `market_sim/geography.py`) wählt jede Firma einmal im Jahr
zwischen eigener Flotte (`own_rate` 1.0, Fixkosten, Schadenrisiko) und einem
namenlosen Dienst (`service_rate` 1.4, kein Risiko). Der Dienst hat keine
Kapazität, keinen Gewinn und keine Konkurrenz. Damit fehlen drei typische
SCM-Themen:

- **Grundversorgung gegen Wettbewerb:** Die Post muss alle Regionen zum
  gleichen Preis bedienen, auch das Tessin. Kuriere picken sich die dichten,
  billigen Strecken heraus (Zürich, Genfersee, Mittelland).
- **Logistik als Engpass:** Ist der Anbieter voll, verlängert sich die
  Lieferzeit. Das schlägt direkt auf Rückstand und Bullwhip durch.
- **Make or buy beim Transport:** Eigene Flotte, Post oder Kurier wird zu
  einer echten Abwägung von Preis, Zuverlässigkeit und Risiko.

## 2. Die Akteure

### 2.1 Die Post (von Anfang an da)
- Eigenes Objekt `Carrier(kind="post")`, keine Firma in den vier Stufen.
- **Kann nicht pleite gehen und nimmt keine Kredite auf.** Ein Verlust wird
  am Jahresende vom Bund gedeckt und als `bundesbeitrag` gebucht (sichtbar im
  Dashboard, damit man sieht, was die Grundversorgung kostet).
- **Einheitstarif:** gleicher Preis pro Einheit und km in allen acht Regionen.
  Der Tarif wird einmal im Jahr festgelegt: Kosten des Vorjahres pro Einheit
  plus kleine Marge, höchstens `max_tariff_step` (z. B. 5 %) Änderung pro Jahr.
  Startwert = heutige `service_rate` 1.4, damit alte Läufe gleich bleiben.
- **Bedienpflicht:** nimmt jeden Auftrag an. Ist die Tageskapazität voll,
  wird der Rest später geliefert (längere Lieferzeit statt Ablehnung).
- Kosten: Fixkosten für Netz und Personal (hängen vom Arbeitsmarkt in
  `labor.py` ab) plus variable Kosten pro km. Wegen der hohen Fixkosten steigen
  die Kosten pro Einheit, wenn die Post Volumen verliert.
- Baut Kapazität langsam aus (politischer Entscheid, z. B. 1 Jahr Verzögerung).

### 2.2 Kuriere (können entstehen)
- Normale Firmen mit Kasse, Bankkredit, Konkurs und Sanierung wie alle
  anderen (bestehende Logik aus `market_entry` und `bank` wiederverwenden).
- **Eintritt:** Jedes Jahr pro Region eine Chance `entry_probability`
  (z. B. 0.15), aber nur wenn der Posttarif dort mindestens `min_margin`
  (z. B. 15 %) über den Kosten eines Kuriers liegt. Weil der Posttarif überall
  gleich ist, lohnt sich das zuerst in dichten, kurzen Strecken. Das
  Rosinenpicken entsteht so von selbst und muss nicht vorgegeben werden.
- **Wählt seine Regionen** und kann sie ausbauen oder aufgeben.
- **Setzt den Preis frei** pro Region (z. B. knapp unter der Post, je nach
  Strategie aggressiv oder vorsichtig, gekoppelt an `risk_tolerance`).
- Hat eine eigene Kapazität (Fahrzeuge) und eine Zuverlässigkeit
  (Verspätungs- und Schadenquote). Billige Kuriere sind weniger zuverlässig.
- Kann von einem anderen Kurier übernommen werden (bestehende Übernahmen und
  Wettbewerbsbehörde gelten).

### 2.3 Die Verlader (Firmen, die Ware verschicken)
Statt `transport_mode in {"own", "service"}` wählt jede Firma einmal im Jahr
pro Kundenregion den günstigsten Weg nach **Gesamtkosten**:

```
Gesamtkosten = Preis × km
             + erwarteter Schaden  (Schadenquote × Warenwert × Risikoscheu)
             + erwartete Verspätung (Verspätungstage × Rückstandskosten)
             + Wechselkosten        (nur im Jahr des Wechsels)
```

Die Verspätung wird aus dem Vorjahr gelernt (wie die versteckten Bussen in
Phase 6): Wer einmal schlecht beliefert wurde, merkt es sich. Das macht die
Post auch bei höherem Preis attraktiv, solange Kuriere unzuverlässig sind.

## 3. Was im Lauf passieren sollte (Erwartung)

1. **Jahre 1 bis ca. 10:** nur Post und eigene Flotten. Die Post macht
   leichten Gewinn oder deckt ihre Kosten.
2. **Erste Kuriere** tauchen in Zürich und am Genfersee auf, unterbieten die
   Post und nehmen ihr dort Volumen weg.
3. Die Post verliert gerade die günstigen Strecken, ihre Kosten pro Einheit
   steigen, der Einheitstarif steigt, noch mehr Kunden wechseln. Der
   Bundesbeitrag wächst.
4. Ein Teil der Kuriere geht in Rezessionen oder Preiskämpfen pleite, der
   Rest wird gross. Das Tessin bleibt bei der Post.

Ob das wirklich so kommt, ist die Frage des Experiments.

## 4. Mögliche Hebel für den Staat (Phase 4, optional)

Über das bestehende Gesetzesmodul (`laws.py`) als Gesetze, die zufällig oder
per Schwelle eingeführt werden:

- **Restmonopol:** Sendungen unter einer Grösse bleiben der Post vorbehalten.
- **Konzessionsabgabe:** Kuriere zahlen einen Anteil ihres Umsatzes in einen
  Grundversorgungsfonds, der den Bundesbeitrag senkt.
- **Tariffreiheit:** Die Post darf pro Region verschiedene Preise verlangen
  (dann verliert sie die Rolle als Grundversorgerin, das Tessin wird teurer).

## 5. Einbau in den bestehenden Code

- **Neues Modul** `market_sim/carriers.py` mit `Carrier`, `CarrierMarket`
  (Tarife, Kapazität, Warteschlange, Jahresabschluss, Eintritt von Kurieren).
- `geography.py`: `rate()` und `ship()` fragen den gewählten Carrier statt
  `service_rate`. `_choose_transport()` wird zur Wahl nach Gesamtkosten pro
  Region. Die eigene Flotte bleibt unverändert.
- `environment.py`: Lieferzeit = Grundlieferzeit + Wartetage beim Carrier
  (heute fest `default_lead_time_days`).
- `config.py` / `market.yaml`: neuer Block `carriers` mit
  `enabled: false` als Standard, damit alle bisherigen Läufe und Tests gleich
  bleiben.
- `dashboard.py`: Marktanteil Post / Kuriere / eigene Flotte, Posttarif,
  Bundesbeitrag, Kuriere pro Region auf der Schweizer Karte, mittlere
  Verspätung.
- Ausgabe `carrier_report.csv` pro Jahr und Carrier.

```yaml
carriers:
  enabled: false
  post:
    start_rate: 1.4
    margin: 0.03
    max_tariff_step: 0.05
    fixed_cost_per_day: 40000
    variable_rate: 0.9
    capacity_per_day: 2000
    expansion_delay_days: 365
  couriers:
    entry_probability: 0.15
    min_margin: 0.15
    start_cash: 5000000
    variable_rate: 0.8
    fixed_cost_per_day_per_region: 4000
    capacity_per_region: 300
    damage_probability: [0.005, 0.03]
    delay_probability: [0.02, 0.10]
  switching_cost_share: 0.02
```

(Die Zahlen sind Startwerte und müssen wie bei den anderen Phasen kalibriert
werden.)

## 6. Schritte

1. **Post als Akteur, gleiche Zahlen wie heute.** `Carrier` ersetzt den
   namenlosen Dienst, Tarif fest 1.4, Kapazität unbegrenzt. Test: Läufe mit
   gleichem Seed liefern dieselben Zahlen wie vorher.
2. **Kosten, Tarif und Bundesbeitrag der Post.** Test: Post endet nie mit
   Konkurs, nimmt nie Kredit, ein Verlust erscheint als Bundesbeitrag.
3. **Kapazität und Verspätung.** Test: Überlast verlängert die Lieferzeit,
   nichts geht verloren.
4. **Kuriere: Eintritt, Preise, Konkurs.** Tests: ohne Marge kein Eintritt;
   Kuriere starten in dichten Regionen; ein Kurier kann pleitegehen.
5. **Wahl nach Gesamtkosten.** Test: Ein unzuverlässiger, billiger Kurier
   verliert risikoscheue Kunden.
6. **Dashboard, Bericht, Gesetze (optional).**

## 7. Offene Fragen

- Soll die Post auf Kuriere reagieren dürfen (Rabatte für Grosskunden) oder
  strikt beim Einheitstarif bleiben?
- Sollen auch Läden (`retailer`) Transport einkaufen? Heute sind sie
  ausgenommen.
- Soll der Bundesbeitrag über Steuern wieder bei den Firmen landen
  (Gewinnsteuer leicht höher), oder nur als Zahl angezeigt werden?
