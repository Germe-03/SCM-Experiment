# Umsetzungsvorschlag: Dynamischer Rohstoff-Markt (börsenartig)

> Vorschlag, noch nicht implementiert. Erstellt 2026-07-02.
> Ziel: Brauereien beziehen Rohstoffe (Malz, Hopfen, Verpackung, Energie) zu
> **marktgetriebenen, schwankenden Preisen** — ähnlich einer Börse. Damit wird
> Beschaffung zu einer echten Strategie (günstig einkaufen, absichern, lagern)
> und Input-Kosten-Risiko zu einem Wettbewerbsfaktor.

## 1. Warum

Heute haben Factories **unbegrenzte, kostenlose Vormaterialien** (Produktion
entsteht aus dem Nichts, kein Einkaufspreis). Das nimmt der obersten Stufe jede
Kosten-/Beschaffungsdynamik. Ein Rohstoffmarkt bringt:
- **Input-Kosten-Risiko**: Preisspitzen (Missernte, Energiekrise) treffen
  schlecht beschaffende Firmen hart → echte Gewinner/Verlierer.
- **Beschaffungsstrategie** als neuer Hebel: Spot vs. Vorrat vs. Termingeschäft.
- **Kopplung an bestehende Hebel**: Risikobereitschaft, Cash, Kapazität, Qualität
  (bessere Rohstoffe → höhere Qualität).

## 2. Kernbausteine

### 2.1 Rohstoffe & Stückliste (Bill of Materials)
Ein Bier-Sim-Unit braucht definierte Mengen je Rohstoff, z. B.:
`1 Bier = a·Malz + b·Hopfen + c·Verpackung + d·Energie`.
Produktion konsumiert Rohstoffe aus dem Rohstofflager der Factory; fehlt etwas,
ist die Produktion **gedeckelt** (zusätzlich zur bestehenden Kapazitätsgrenze).

### 2.2 Preisbildung — zwei Varianten
**Variante A — exogen stochastisch (MVP, einfach):**
Jeder Rohstoffpreis folgt einem **Mean-Reversion-Prozess** (Ornstein-Uhlenbeck)
plus Saison plus gelegentliche Schocks:
```
p_{t+1} = p_t + κ·(μ_saison(t) − p_t) + σ·ε_t   (+ Sprung bei seltenem Schock)
```
κ = Rückkehrgeschwindigkeit, μ = saisonaler Gleichgewichtspreis (Ernte-Zyklus),
σ = Volatilität. Deterministisch bei festem Seed. Preise „bewegen sich selbst".

**Variante B — endogen (die echte „Börse"):**
Der Preis ergibt sich aus **Angebot & Nachfrage** aller Käufer. Pro Tick:
- Factories geben **Gebote** ab (Menge, Maximalpreis) gemäß Beschaffungspolitik.
- Eine Angebotskurve (fix oder mit Kapazität/Schocks) trifft die aggregierte
  Nachfrage → **markträumender Preis** (Call-Auktion / Order-Book-Clearing).
- Mehr Nachfrage → höherer Clearing-Preis; alle zahlen denselben Marktpreis.
Das ist „börsenartig": der Preis reagiert darauf, wie viel alle kaufen, es gibt
Knappheit und Preis-Feedback. Empfehlung: **A als MVP, dann B**.

### 2.3 Beschaffungsstrategie (neuer Entscheidungs-Hebel)
- **Spot-Kauf**: kaufe heute, was für die Produktion nötig ist (JIT).
- **Vorrats-/Stockpiling**: kaufe billig auf Vorrat (Preisrisiko ↓, aber
  Lagerkosten + Kapitalbindung ↑).
- **Termingeschäft/Hedging (Phase 3)**: sichere heute einen Preis für spätere
  Lieferung (Forward). Belohnt gute Prognose, bestraft Fehlspekulation.
Die Jahresstrategie bekommt eine `procurement_policy` (jit | stockpile | hedge),
gekoppelt an das bestehende `risk_tolerance`.

## 3. Integration in den bestehenden Code

- **Neues Modul** `market_sim/commodities.py`: `Commodity`, `CommodityMarket`
  (Preisprozess bzw. Order-Book-Clearing), deterministisch per Seed. Import-clean
  von der Engine (wie der Rest).
- **Config** `market.yaml` → `commodities:` (Liste: name, init_price, κ, σ, Saison,
  Schock-Wahrscheinlichkeit) und `bom:` (Rohstoff-Koeffizienten je Bier-Unit).
- **Factory-Erweiterung** (`environment.py` / Runtime): Rohstofflager je Factory,
  Produktion konsumiert laut BOM, Rohstoffkosten fließen in COGS/Cash
  (Cash-Identität erweitern). Produktion = min(Kapazität, Rohstoff-limitierte Menge).
- **Runner**: pro Tick Preise fortschreiben (Variante A) bzw. Gebote sammeln &
  Markt räumen (Variante B); Factories beschaffen laut Politik.
- **Policies**: Jahres-`procurement_policy` + tägliche Rohstoff-Kaufmenge.
- **KPIs/Dashboard**: Rohstoffpreis-Zeitreihen, Input-Kosten je Factory,
  Beschaffungs-Performance (Ø-Einkaufspreis vs. Marktdurchschnitt).
- **Parität bleibt unberührt**: der Rohstoffmarkt ist ein Markt-Modus-Addon im
  Runner/Factory-Pfad; der S3-Parity-Test (equal_backlog, keine Produ­ktions­kosten)
  läuft unverändert.

## 4. Phasen-Roadmap

- **Phase 1 (MVP)**: Rohstoffe + BOM + exogene Mean-Reversion-Preise (Variante A)
  + Spot-Beschaffung + Input-Kosten in COGS. Größter Nutzen bei geringem Risiko.
- **Phase 2**: endogene Preisbildung (Order-Book/Clearing, Variante B) → echte
  Börse mit Knappheits-Feedback.
- **Phase 3**: Vorrat + Termingeschäfte/Hedging + Schocks + Ernte-Saison.
- **Phase 4 (optional)**: Rohstoffe stufenübergreifend handelbar, Spekulation,
  mehrere Bezugsquellen/Lieferländer.

## 5. Risiken & Entscheidungen
- **Stabilität**: Mean-Reversion + Preis-Clamps, sonst divergieren Preise.
- **Determinismus**: eigener Seed-Strang für die Preispfade (reproduzierbar).
- **Kalibrierung**: BOM + Preise so, dass Factory-Margen sinnvoll bleiben (nicht
  alle sofort defizitär) — analog zur Geld-Skalen-Kalibrierung.
- **Komplexität von Variante B**: Order-Book-Clearing ist deutlich aufwändiger;
  A liefert 80 % des Nutzens.

## 6. Aufwand (grob)
- Phase 1: mittel (1 neues Modul, Factory-COGS-Erweiterung, Config, Tests).
- Phase 2: mittel–hoch (Clearing-Mechanik + Gebotslogik).
- Phase 3: hoch (Termingeschäfte + Prognose-Kopplung).
