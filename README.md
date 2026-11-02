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
- **Finanzen:** Umsatz, Wareneinsatz, Lager-, Backlog- und Handlingkosten,
  Löhne und F&E in realen CHF. Firmen mit zu tiefem Cash scheiden am
  Jahresende aus.
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
und `system_kpis.csv`. Das Dashboard ist eine eigenständige HTML-Datei, in
der man jede Firma einzeln anschauen kann. Ein 10-Jahres-Lauf dauert rund
20 Sekunden.

---

## 3. Erste Ergebnisse

Stand: aktueller Code auf `main`, 10 Jahre, Seeds 0, 1 und 2.
Alle 78 Tests laufen grün.

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
5. **Die Lieferfähigkeit ist hoch, der Bullwhip bleibt.** Lost Sales sind
   im Verhältnis zur Nachfrage sehr klein. Die Bestellschwankung ist aber
   immer noch 75- bis 130-mal so gross wie die Schwankung der
   Endkundennachfrage. Die Bestellglättung hat die frühere Explosion
   verhindert, gelöst ist das Problem aber nicht.

### Offene Punkte

- Bullwhip-Ratio weiter senken (Forecast-Weitergabe, stärkere Glättung).
- `service_level` steht immer bei 1.0, obwohl Lost Sales auftreten; die
  Kennzahl muss geprüft werden.
- Die Ergebnisse in `runs/` stammen von älteren Ständen und sollten neu
  gerechnet werden.
- Die Koeffizienten für Löhne, F&E und Handlingkosten sind Schätzungen und
  noch nicht an echten Branchendaten kalibriert.
- Brauereien haben noch unbegrenzte, kostenlose Rohstoffe. Ein Vorschlag für
  einen börsenartigen Rohstoffmarkt (Malz, Hopfen, Verpackung, Energie)
  liegt in `docs/commodity-market-proposal.md`.
- Die Beer-Game-Agenten in `team_bundle/` nutzen noch die Mirror-Policy.

---

## Lizenz

Siehe [LICENSE](LICENSE).
