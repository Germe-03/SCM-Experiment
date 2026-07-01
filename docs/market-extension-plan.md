# Erweiterungsplan: Von der linearen Beer-Game-Simulation zur agentenbasierten Multi-Firm-Bier-Markt-Simulation (Schweiz)

> Status: **Nur Plan – keine Implementierung.** Erstellt am 2026-07-01.
> Ziel: das bestehende `supplychainbench`-Assignment kontrolliert zu einer
> Multi-Firm-Markt-Simulation skalieren, ohne die bestehende Abgabe kaputtzumachen.

---

## 0. Die wichtigste Erkenntnis zuerst (Architektur-Realität)

Bevor irgendein Plan Sinn ergibt, muss eine harte Randbedingung klar sein, die
die Analyse des tatsächlichen Codes zutage gefördert hat:

**Die eigentliche Simulations-Engine `supplychainbench_v2` ist NICHT Teil dieses
Repos.** Sie ist ein fertig gebautes, geschlossenes Wheel
(`supplychainbench_student-0.1.0-py3-none-any.whl`), installiert im venv des
Schwester-Projekts
`C:\Users\david\PycharmProjects\Supply-Chain-Management-SCM\.venv`.

Was in diesem Repo (`SCM-Experiment`) liegt, ist ausschliesslich die
**Abgabe („team_bundle")**: vier fast leere `agent.py`-Dateien, deren
`step()`-Methode wir füllen dürfen, plus vier `agent.yaml`, `manifest.json`,
Walkthroughs und ein Smoke-Test, der den *installierten* Validator aufruft.

Die Engine hat einen bewusst **sehr engen, strikt validierten Contract**
(Pydantic `extra="forbid"`), der das Zielbild **nicht** tragen kann:

| Was die Engine kann | Was das Zielbild braucht |
|---|---|
| Genau 4 Stufen, fest verdrahtet (`TIER_NAMES = ["retailer","wholesaler","distributor","factory"]`) | Mehrere konkurrierende Firmen pro Stufe |
| Genau **eine** Firma pro Stufe (`ChainState.tiers` = dict mit 4 Einträgen) | 2+ Firmen je Stufe, mit eigenem State |
| Lineare, fixe Topologie (retailer→…→factory) | Lieferantenauswahl über ein Kanten-Netzwerk |
| Entscheidung = **nur** `order_qty: int` (`AgentDecision`) | Preis, Bestellungen an *mehrere* Lieferanten, Produktion, Überstunden … |
| Nachfrage = ein Skalar an den Retailer | Preis-/Qualitäts-/Reputations-abhängige, verteilte Nachfrage |
| Kosten = Holding + Backlog | Cash, Umsatz, Gewinn, Löhne, F&E, Lost Sales |
| Beobachtung = lokale `LocalObservation` (fixe Felder, `extra="forbid"`) | Firmen-Zustand mit ~25 Feldern |

**Konsequenz:** Das Markt-Zielbild lässt sich **nicht** durch Erweitern der
`AgentDecision`/`LocalObservation`-Contracts oder der geschlossenen Engine
erreichen. Man kann keinen Preis und keine Lieferantenwahl durch ein Objekt
schleusen, das nur `order_qty` erlaubt und jedes Zusatzfeld hart ablehnt.

**Empfohlener Weg (Kern der ganzen Planung):**

> Die neue Markt-Simulation wird als **eigenes, separates Paket / eigener Modus**
> (`market_sim/`) gebaut – *neben* dem bestehenden `team_bundle`. Wir
> **erweitern nicht die geschlossene Engine**, sondern **portieren ihre bewährte
> Mechanik als Vorlage** und **importieren ihre wiederverwendbaren, reinen
> Bausteine** (Metriken, Demand-Primitive). Das bestehende `team_bundle` bleibt
> als lauffähige, abgabefähige **Baseline (Phase 1)** unangetastet.

Das erfüllt exakt die Vorgaben „so viel wie möglich erhalten", „keine komplette
Neuentwicklung wo Bestehendes erweiterbar ist", „neue Simulation als separater
Modus statt Überschreiben" – und ist zugleich der einzige *technisch mögliche*
Weg, weil die Engine geschlossen ist.

---

## 1. Kurze Analyse der aktuellen Projektstruktur

### 1a. Dieses Repo (`SCM-Experiment`) – die Abgabe

```
SCM-Experiment/
├── LICENSE, README.md               # praktisch leer
├── walkthrough_{retailer,wholesaler,distributor,factory}.md   # Tier-Doku + Policy-Ideen
└── team_bundle/
    ├── manifest.json                # team_id/team_name noch Platzhalter
    ├── {retailer,wholesaler,distributor,factory}/
    │   ├── agent.py                 # NUR step() editierbar; aktuell Mirror-Policy
    │   └── agent.yaml               # role, entrypoint, memory_mode, ...
    ├── tests/test_local.py          # ruft validate_bundle() der Engine auf
    └── README.md                    # erklärt Contract & Regeln
```

Aktueller Stand aller vier Agents: die triviale **Mirror-Policy**
`return AgentDecision(order_qty=observation.incoming_order_qty)` → erzeugt
lehrbuchmässig den Bullwhip-Effekt.

### 1b. Die Engine (installiertes Wheel, geschlossen)

`supplychainbench_v2` – die relevanten Module und was sie tun:

| Modul | Rolle | Für uns relevant? |
|---|---|---|
| `engine/state.py` | `TierState`, `ChainState`: Bestand, Backlog, 2-Slot-Lead-Time-Queues (`incoming_shipments/orders`), Kostenakkumulation | **Vorlage zum Forken** (Mechanik pro Firma) |
| `engine/environment.py` | Der 7-Schritt-Tick-Loop (receive → fulfill → history → place orders → cost → advance) | **Vorlage zum Forken** (Kern-Loop) |
| `sdk/contract.py` | `LocalObservation`, `AgentDecision`, `CostBreakdown` (alle `extra="forbid"`) | Vorbild für unsere neuen, breiteren Datenmodelle |
| `sdk/agent.py` | Abstrakte `Agent`-Basis (`reset/step/on_feedback`) | Vorbild für `Firm`-Agent-Interface |
| `metrics/core.py` | reine Funktionen: `coefficient_of_variation`, `calculate_bullwhip`, `fill_rate`, `average` | **Direkt importierbar & wiederverwendbar** |
| `metrics/composite.py` | `bullwhip_ratio_variance`, Composite-Score (geom. Mittel) | **Direkt importierbar** (Bullwhip-KPI, Vergleichbarkeit) |
| `metrics/stability.py` | Quartil-/Stabilitäts-Checks S1.1 vs S2.3 | Später für Robustheits-KPIs nützlich |
| `scenarios/library.py` | Demand-Primitive `iid_uniform(low,high)`, `step(low,high,switch_at)` | **Basis-Nachfrage** – als Marktgrundsignal wiederverwenden |
| `scenarios/scenario.py`, `builtin.py` | `Scenario`-Dataclass, S1.1/S2.3/Intro | Vorbild für unser Markt-Szenario-Objekt |
| `runner/harness.py`, `sdk/validator.py`, `cli.py` | Baut `LocalObservation`, ruft `step()`, validiert Bundles, CLI (`test-bundle`, `run-scenario`, `metrics`) | Nur für Phase-1-Baseline relevant |

### 1c. Schwester-Projekt `Supply-Chain-Management-SCM`

Weiter entwickeltes Projekt mit demselben Wheel, plus `simulate.py` (35 KB,
eigenes Excel-/HTML-Dashboard, das die Engine über `_load_agents` + Environment
ansteuert), `AGENTS.md`, `runs/`, Ergebnis-Tabellen. **Wichtig als Referenz für
zwei Dinge:** (1) das Muster, wie man die Engine programmatisch treibt und KPIs
rausschreibt (direkt übertragbar auf unseren Markt-Runner), und (2) die
Bezugsquelle des Wheels (`09_resources/…​.whl`) für unser Environment-Setup.

---

## 2. Was wiederverwendet / erweitert / abstrahiert wird

**Direkt wiederverwenden (importieren, unverändert):**
- `metrics/core.py`, `metrics/composite.py`, `metrics/stability.py` – für
  bullwhip_ratio, fill_rate/service_level, CV, Stabilität. Erhält die
  **Bewertungs-Vokabular-Kompatibilität** mit dem Kurs.
- `scenarios/library.py` Demand-Primitive als **Grundmarktsignal** (darüber
  legen wir Preis/Qualitäts-Elastizität).

**Als Vorlage forken (Muster kopieren, dann erweitern – NICHT die geschlossene
Klasse subclassen, weil wir Topologie und Entscheidungsfläche ändern):**
- `TierState` → `Firm` (gleiche Queue-Mechanik: 2-Slot-Pipeline, History-Fenster,
  Backlog-Logik; plus neue Felder).
- `Environment.step()` 7-Schritt-Pipeline → `MarketEnvironment.step(day)` mit
  denselben Grundschritten, erweitert um Preis/Nachfrageverteilung/Cash.

**Neu abstrahieren:**
- Die **fixe lineare Verdrahtung** (`TIER_ORDER[i-1]`/`[i+1]` in
  `_fulfill_orders`/`_place_orders`) → ein **Lieferanten-Kantengraph** zwischen
  benachbarten Stufen.
- Die **eine-Firma-pro-Stufe**-Annahme → `Stage` mit Firmenliste.
- **Skalare Nachfrage an einen Retailer** → **Marktnachfrage + Attraktivitäts-
  Verteilung** auf mehrere Retailer.

**Unangetastet lassen:**
- Das gesamte `team_bundle/` (Phase-1-Abgabe). Es bleibt lauffähig und
  abgabefähig; ein Guard-Test stellt das sicher.

---

## 3. Datenmodelle: erweitern vs. neu

Neue Modelle im Paket `market_sim/models.py` (Vorbild: `sdk/contract.py`, aber
`extra="forbid"` NICHT übernehmen, damit wir iterativ Felder ergänzen können):

**`Firm` (MVP-Priorität in Klammern):**
- Identität: `id`, `name`, `stage` *(P0)*
- Finanzen: `cash`, `revenue_ytd`, `profit_ytd` *(P0)*
- Fluss: `inventory`, `backlog`, `incoming_shipments`, `incoming_orders`,
  `order_history`, `shipment_history` *(P0 – 1:1 aus `TierState`)*
- Markt: `sell_price`, `quality_level`, `reputation`, `reliability` *(P0/P1)*
- Kapazität: `capacity` *(P0)*, `employees`, `wage_level`,
  `productivity_per_employee` *(P1)*
- Strategie/State: `suppliers` (erlaubte Kanten), `supplier_priority`,
  `r_and_d_budget`, `r_and_d_level` *(P1)*
- Später *(P2+)*: `turnover_rate`, `absenteeism_rate`, `training_level`,
  `hiring_cost`, `firing_cost`, `overtime_level`.

**`AnnualStrategy`** (einmal pro Jahr, validiert): positioning, base_price,
min_price, max_price, wage_level, r_and_d_budget, target_quality,
supplier_priority, target_safety_stock_days, risk_tolerance, hiring_plan.

**`DailyDecision`** (pro Tag, muss Strategie respektieren): `sell_price`
(geklemmt auf `[min_price, max_price]`), `orders: list[(supplier_id, qty)]`,
`production` (nur Factory), `overtime_level`, `fulfilment_policy`.

**`FirmObservation`** (was eine Firma pro Tag sieht – Analog zu
`LocalObservation`, aber breiter): eigener Firmen-State + sichtbare
Lieferanten-Kennzahlen (Preis/Reliability/Lieferzeit – *keine* fremden
Innenzustände) + letzte Marktnachfrage/eigener Absatz.

**`AnnualReport`** und **KPI-Records** wie in der Aufgabenstellung skizziert.

---

## 4. Lineare Kette → Multi-Firm-Netzwerk

- `Stage` = benannte Stufe mit `firms: list[Firm]`.
- `SupplyNetwork` = für jede benachbarte Stufenpaarung die **erlaubten Kanten**
  (welche Downstream-Firma bei welcher Upstream-Firma bestellen darf). MVP:
  vollverbunden 2×2 pro Ebene.
- `_fulfill_orders`/`_place_orders` werden von „Index ±1" auf „folge der
  gewählten Kante" umgestellt. Backlog/Pipeline bleiben pro (Firma), nicht pro
  Stufe.
- **Determinismus:** alle Firmenentscheidungen eines Tages werden auf dem
  *Tagesanfangs-Zustand* erhoben und dann in **fester, dokumentierter
  Reihenfolge** aufgelöst (kein „first come" je nach dict-Reihenfolge), sonst ist
  der 3650-Tage-Lauf nicht reproduzierbar.

---

## 5. Jahresstrategie & Tagesentscheidung im Step-System

Zeit-Mapping (passt sauber zum bestehenden System): die Engine zählt abstrakte
„periods"; die Kursszenarien laufen bereits **365 periods = 1 Jahr**. Also:

> **1 Tick = 1 Tag.** 10 Jahre = **3650 Ticks**. Lead-Times (heute 2 Ticks) = 2
> Tage, pro Kante konfigurierbar.

Zwei-Ebenen-Loop:
```
for year in range(10):
    if day_of_year == 0:
        report = build_annual_report(prev_year)     # Jahresbericht
        for firm: firm.strategy = firm.decide_annual(report)   # + Validierung
    for day_of_year in range(365):
        obs = build_observation(firm)
        dec = firm.decide_daily(obs)                 # geklemmt an strategy
        env.resolve_day(all_decisions)               # 13-Schritt-Tagesablauf
    finalize_year()                                  # KPIs, Report
```
Die 13 Schritte aus der Aufgabenstellung sind kompatibel mit dem 7-Schritt-Loop
der Engine – sie sind eine **Obermenge** (zusätzlich: Marktnachfrage berechnen &
verteilen, Verkauf an Endkunden, Cash/Umsatz, Reputation/Qualität/Mitarbeiter).

---

## 6. Integration von Nachfrage, Preis, Qualität, Kapazität, Mitarbeitern

- **Nachfrage:** Grundmarktnachfrage/Tag aus `scenarios/library` (z.B.
  `iid_uniform` um den Schweizer Tageswert ~259 Einheiten), dann
  `attractiveness = 0.35·price + 0.25·quality + 0.25·reputation + 0.15·availability`
  → proportionale Verteilung → Spillover bei Stockout → Rest = Lost Sales.
  **Kritisch:** Preis-Score beschränken (keine Division, die explodiert), sonst
  Instabilität.
- **Preis:** Tagespreis strikt in `[min_price, max_price]` der Jahresstrategie
  klemmen (Validierung + Test).
- **Qualität durch F&E (MVP, bewusst simpel):** eine kleine Verzögerungs-Queue
  (`deque` pending effects), F&E-Budget in Jahr *t* wirkt anteilig in *t, t+1,
  t+2*; `quality_level` in `[0,1]`, langsame Anpassung.
- **Kapazität:** `fulfilled = min(order/demand, inventory, capacity)`; Rest →
  Backlog (B2B) bzw. Lost Sales (Endkunde). `capacity` je Stufe aus
  Mitarbeitern × Produktivität (+ Überstunden), Factory zusätzlich
  `machine_capacity`.
- **Mitarbeiter (MVP, rein wirtschaftlich, kein Ethik-Score):** mehr MA → mehr
  Kapazität; Lohnkosten = `employees·wage_level`; höherer Lohn → geringere
  `turnover_rate` (linear); Fluktuation → Produktivitätsabschlag +
  Einstellungskosten. Überstunden: kurzfristig +Kapazität, langfristig
  +Fluktuation. Alles geklemmt.

---

## 7. Lieferantenauswahl

`supplier_score = w_price·price + w_reliability·reliability + w_quality·quality +
w_leadtime·leadtime + w_capacity·capacity` mit Default-Gewichten
(35/25/20/10/10). Die Gewichte werden durch `positioning` der Jahresstrategie
gesetzt (Low-Cost→Preis, Premium→Qualität, Reliable→Reliability,
Growth→Kapazität). Firma bestellt (MVP) beim höchstbewerteten zulässigen
Lieferanten; später Split über Top-N.

---

## 8. KPI-Logging & Jahresberichte

- Pro Firma/Tag: schlanke Records in eine Liste/`runs/*.csv` (revenue, profit,
  cash, inventory, backlog, lost_sales, price, quality, fill/service_level,
  capacity_utilization, employee_cost, turnover, r_and_d_spend, reputation).
- Aggregat/System: total_profit, total_backlog, total_lost_sales,
  avg_customer_price, avg_quality, market_concentration (HHI),
  **bullwhip_ratio (aus `metrics/composite.py` wiederverwendet)**, service_level.
- Jahresbericht pro Firma exakt im vorgegebenen Schema (inkl.
  `supplier_reliability` und regelbasierten `main_problems`). Dient später als
  Input für Strategie-/LLM-Agenten; MVP-Strategie ist **regelbasiert**.

---

## 9. Konfigurationsdateien

- `market_sim/config/market.yaml`: Schweizer Marktannahmen (1 Einheit = 10'000×
  0.5 L; ~94'400 Einheiten/Jahr; ~259/Tag), Preisgrenzen (4.99/1.99/9.99),
  sim_years=10, days_per_year=365, Lead-Times, holding/backlog-Kosten,
  Attraktivitäts- & Supplier-Score-Gewichte. **Zentral konfigurierbar** (Vorgabe).
- `market_sim/config/firms.yaml`: 2 Firmen je Stufe mit individuellen Attributen
  + Strategie-Archetyp (Low-Cost / Premium / Reliable / Growth …).
- Alter Beer-Game-Modus bleibt Default; neuer Modus via `--mode market`.

---

## 10. Zuerst zu schreibende Tests

1. **Guard:** `supplychainbench test-bundle team_bundle` läuft weiterhin grün
   (Phase-1-Abgabe nicht kaputt).
2. **Erhaltungssatz:** Einheiten bleiben erhalten (produziert = versandt +
   Bestandsänderung + Backlog-Änderung).
3. **Preisgrenzen:** Tagespreis immer in `[min,max]`.
4. **Nachfrageverteilung:** Summe verteilter Nachfrage + Lost Sales =
   Marktnachfrage.
5. **Supplier-Score:** deterministisch & korrekt gewichtet.
6. **Kapazitäts-Clamp:** `fulfilled ≤ min(order, inventory, capacity)`.
7. **Golden-Run:** 1-Jahres-Lauf bit-reproduzierbar bei festem Seed.
8. **Parity-Sanity:** Bei genau 1 Firma/Stufe + flacher Nachfrage reproduziert
   `MarketEnvironment` die lineare Beer-Game-Mechanik (beweist korrekten Port,
   bevor Wettbewerb dazukommt).

---

## 11. MVP-Roadmap (kleine, je per Codex umsetzbare Schritte)

Jeder Schritt = ein abgegrenzter Codex-Prompt + `git diff`-Review + Test.

- **S0 – Environment-Setup (kein Produktcode):** echtes Python installieren; venv
  in `SCM-Experiment` anlegen; Wheel aus dem Schwester-Projekt
  (`09_resources/…​.whl`) installieren; `test-bundle` + `run-scenario` grün.
- **S1 – Paketgerüst:** `market_sim/` skeleton, Config-Loader, `market.yaml`
  (Schweizer Zahlen). Test: Config lädt.
- **S2 – Datenmodelle:** `Firm`, `Stage`, `SupplyNetwork`, `firms.yaml` (2×4).
  Test: Netzwerk baubar.
- **S3 – Mechanik-Port:** `MarketEnvironment` mit 1 Firma/Stufe (Parity-Sanity).
- **S4 – Multi-Firm + Supplier-Score** (feste Gewichte). Tests 5/6.
- **S5 – Dynamische Endkundennachfrage** (Attraktivität/Spillover/Lost Sales).
  Test 4/2.
- **S6 – Preis + Kapazität + Cash/Kosten.** Test 3 + Cash-Identität.
- **S7 – Mitarbeiter (simpel) + F&E-Lag (simpel).**
- **S8 – Jahres-/Tagesebene + regelbasierte Archetypen.** Test: Tag respektiert
  Jahr.
- **S9 – KPI-Logging + Jahresbericht** (Schema). 
- **S10 – 10-Jahres-Lauf + CSV/Dashboard** (Muster aus `simulate.py` des
  Schwester-Projekts; nicht MVP-kritisch).

---

## 12. Risiken & kritische Modellierungsentscheidungen

- **#1 (grösste):** Engine ist geschlossen → Markt-Sim MUSS neues Paket sein,
  Mechanik wird geportet, nicht die Klasse erweitert.
- **Gleichzeitige vs. sequenzielle Firmenentscheidungen** → feste
  Auflösungsreihenfolge auf Tagesanfangs-Zustand (Reproduzierbarkeit).
- **Nachfrage-/Reputations-Rückkopplung** kann divergieren → alles auf `[0,1]`
  klemmen, langsame Anpassung, Preis-Score bounded.
- **Determinismus über 3650 Tage × 8 Firmen** → strikte Seed-Disziplin.
- **Cash/Bankrott:** MVP lässt negatives Cash zu und loggt es; **kein**
  Firmen-Exit im MVP (Komplexität).
- **Performance:** 3650 × 8 in reinem Python ist trivial – kein Thema.
- **Scope-Creep:** die Deferred-Liste (§13) strikt einhalten.

---

## 13. Bewusst (noch) NICHT eingebaut

Mehrere Produkte · Verträge · Marketing · Kredite/Financing · Regulator · CO2 ·
Ethik-Score · LLM-Agenten · Dashboard (über einfaches CSV hinaus) ·
Bankrott/Markteintritt-austritt. Ebenso: **kein** Anfassen der geschlossenen
Engine, **kein** Verändern des `team_bundle`-Contracts.

---

## 14. Offene Entscheidungen für dich (David)

1. **Verhältnis der beiden Repos:** Soll `market_sim/` hier in `SCM-Experiment`
   entstehen, oder im weiter entwickelten Schwester-Projekt
   `Supply-Chain-Management-SCM` (das venv + Wheel + `simulate.py` schon hat)?
2. **Python-Setup:** aktuell ist kein echtes Python auf dem PATH (nur der
   Windows-Store-Stub). S0 braucht eine echte Installation.
3. **Regelbasiert vs. später LLM:** MVP-Strategie regelbasiert bestätigt?

---

## 15. Umsetzungs-Log & getroffene Modell-Entscheidungen (Stand 2026-07-01)

Fortschritt: **S0–S6 fertig & verifiziert** (29 grüne Tests, S3-Parity + Cash-
Identität halten, `team_bundle/` unangetastet, Produktcode import-clean von
`supplychainbench_v2`). Code lebt in `market_sim/` (config.py, models.py,
selection.py, environment.py + 6 Test-Dateien). Alle Code-Änderungen von Codex
geschrieben, von Claude per Diff-Review + unabhängigem pytest verifiziert.

Erledigt:
- **S0** venv + Wheel (`supplychainbench_student-0.1.0`) + pytest; Bundle-Guard grün.
- **S1** Paketgerüst + `market.yaml` (Schweizer Zahlen) + pydantic-Loader.
- **S2** `Firm`/`Stage`/`SupplyNetwork` + `firms.yaml` (8 Firmen, 2/Stufe) + Topologie-Validierung.
- **S3** `MarketEnvironment` (7-Schritt-Port) + **Parity-Test gegen die Referenz-Engine** (tick-genau).
- **S4** Multi-Firm + Lieferantenauswahl (`selection.py`) + proportionale Zuteilung.
- **S5** Dynamische Endkundennachfrage (Attraktivität → Spillover → Lost Sales).
- **S6** Kapazitäts-Clamp + Cash/Umsatz/COGS/Löhne/Profit.

Bewusst getroffene Modell-Entscheidungen (per Flag parity-sicher gehalten):
- **Lieferanten-Score:** min-max-Normierung im Kandidatenset, Preis/Lieferzeit
  invertiert; `supplier_priority` verdoppelt das jeweilige Gewicht + Renormierung;
  Single-Sourcing (volle Menge zum besten Lieferanten); Tie-Break per id.
- **Fulfillment bei Knappheit:** proportional (Largest-Remainder, deterministisch),
  Rest bleibt Per-Edge-Backlog (B2B). Endkunde: kein Backlog.
- **Endkundennachfrage:** `consumer_demand_mode` — Default `equal_backlog`
  (Beer-Game/Parity), neu `attractiveness_lost` (Preis/Qualität/Reputation/
  Verfügbarkeit → Split → 1-Pass-Spillover → Lost Sales).
- **Kapazität:** `enforce_capacity` (Default aus = parity-sicher); an: Versand/Tag
  ≤ `capacity`, Factory-Produktion ≤ `capacity`.
- **Finanzen:** Umsatz/COGS symmetrisch beim Versand; Lohn/Tag = `employees ×
  wage_level / 30`; Factory ohne Einkaufskosten; negatives Cash erlaubt (kein
  Bankrott im MVP).

**S7–S10 ebenfalls fertig & verifiziert** (Stand 2026-07-01, **48 grüne Tests**):
- **S7** Mitarbeiter (Überstunden→Kapazität/Lohn, Fluktuation→Produktivität/
  Einstellungskosten) + F&E-Lag (verzögerte Qualität via Pending-Buffer), hinter
  `enable_workforce`/`enable_rnd` (Default aus). Koeffizienten zentral in
  `market.yaml` (`workforce:`, `rnd:`).
- **S8** Zwei Entscheidungsebenen: `AnnualStrategy` + `DailyDecision`
  (`strategy.py`), regelbasierte Archetyp-Policies (`policies.py`), zweistufiger
  `SimulationRunner` (`runner.py`). Bestellung per Base-Stock, dynamischer
  Tagespreis in Strategie-Preisspanne. Determinismus per Seed getestet.
- **S9** KPI/Reporting (`kpi.py`): voller `AnnualReport` + `SystemKPIs` (HHI,
  Bullwhip-Varianzverhältnis, Service-Level, eigene Metriken → Paket standalone),
  dynamische Reputation.
- **S10** Lauf-Entry-Point (`run.py`): `python -m market_sim.run --years 10`
  schreibt `runs/{annual_reports,system_kpis,firm_ranking}.csv` + Ranking-Summary.
- Test-Infra: `conftest.py` lenkt pytest-Temp auf `.pytest_tmp/` (der globale
  Temp `…\Temp\pytest-of-david` ist ACL-gesperrt, WinError 5).

## 16. ⚠️ Zentraler offener Befund: ökonomische Kalibrierung (→ „S11 Balancing")

Der MVP **läuft** deterministisch end-to-end, ist aber **wirtschaftlich noch
nicht kalibriert**: im 10-Jahres-Lauf (Seed 0) machen **alle** Firmen tief
Verlust (System ~−80 Mio/Jahr), distributor_b (growth) kumuliert ~−1,1 Mrd.
Die KPIs zeigen die Ursache eindeutig: **Bullwhip Jahr 1 ≈ 4,2·10⁸**, danach
0.00 — d.h. eine gewaltige Anfangs-Bestellexplosion, danach ersticken alle in
Beständen (Holding-Kosten). Das ist **kein Mechanik-Bug** (Invarianten getestet),
sondern fehlende Dämpfung + Margen:
- Tages-Bestellpolitik hat **kein Order-Smoothing / keinen Cap** → klassischer
  Bullwhip (genau das Thema des Beer Games) ungebremst.
- Preisspannen sind für alle Stufen die globalen `[1.99, 9.99]` → keine
  stufengerechten Margen (Factory kann bei 8 CHF „verkaufen").
- Anfangs-Pipeline/Bestände + `target_safety_stock_days` erzeugen einen großen
  Startpuls.

**Vorschlag S11 (Balancing, mit David):** Order-Smoothing/Caps in den Policies;
stufengerechte Preisbänder & Kostenmargen; Startzustand/Sicherheitsbestände
tunen; ggf. Bankrott/Exit. Alle Stellschrauben liegen zentral in `market.yaml`
und `firms.yaml` — das ist Tuning, kein Umbau.

**S9-Entscheidung:** Jahresberichte verwenden jahreslokale Fluss- und
Finanzwerte. Kapazitätsauslastung ist der Tagesmittelwert aus Versand durch
effektive Kapazität (Retailer inklusive Endkundenabsatz). Realisierte
Lieferantenzuverlässigkeit ist je tatsächlich gewähltem Lieferanten
`geliefert / bestellt`, auf `[0,1]` geklemmt. Reputation wird am Jahresende mit
konfigurierbarer Geschwindigkeit zum Ziel
`0.5 × Service-/Fill-Rate + 0.5 × Qualität` bewegt und auf `[0,1]` geklemmt.
Die Problemhinweise sind regelbasiert (Stockouts, Kapazitätsgrenze,
Qualitätsabstand, negatives Cash, Verlust).
