"""Passive decision journal and rule-based exit explanations."""

from dataclasses import dataclass, field

from market_sim.kpi import chf


@dataclass
class DecisionLog:
    enabled: bool = True
    entries: list[dict] = field(default_factory=list)
    monthly: dict = field(default_factory=dict)

    def record(self, year, firm, decision, value, reason, month=None):
        if self.enabled:
            self.entries.append(dict(year=year, month=month, firm=firm,
                                     decision=decision, value=value, reason=reason))

    def daily(self, year, day, days, firm, decision):
        if not self.enabled:
            return
        month = min(12, day * 12 // days + 1)
        totals = self.monthly.setdefault((year, month, firm), [0, 0.0, 0.0])
        totals[0] += 1
        totals[1] += decision.order_qty
        totals[2] += decision.sell_price

    def finish_year(self):
        for (year, month, firm), (count, orders, prices) in sorted(self.monthly.items()):
            for key, value in (("average_order_quantity", orders), ("average_sell_price", prices)):
                self.record(year, firm, key, value / count, "Mittel der aktiven Entscheidungstage", month)
        self.monthly.clear()

    def annual(self, year, firm, strategy):
        values = {"archetype": firm.archetype, "price_band": {
            "min": strategy.min_price, "base": strategy.base_price, "max": strategy.max_price},
            "transport_mode": firm.transport_mode}
        for key in ("wage_level", "r_and_d_budget", "target_safety_stock_days", "risk_tolerance", "overtime_level"):
            values[key] = getattr(strategy, key)
        for key, value in values.items():
            self.record(year, firm.id, key, value, "Jahresplanung nach Strategie und Vorjahresergebnis")


def exit_analysis(result, history_years=5, driver_count=3):
    """Rank accounting signals, not claims of proven causality."""
    output = {}
    labels = {"purchase_cost": "Einkauf und Rohstoffe", "wage_cost": "Löhne",
              "fixed_cost": "Fixkosten", "handling_cost": "Handling und Transport",
              "holding_cost": "Lagerkosten", "backlog_cost": "Rückstandskosten",
              "rnd_cost": "F&E", "hiring_cost": "Einstellungskosten",
              "interest_cost": "Zinsen", "negative_interest_cost": "Negativzinsen",
              "investment_depreciation": "Investitionsabschreibungen"}
    for firm_id, year in result.exits.items():
        firm = result.network.firm(firm_id)
        first_year = max(1, year - history_years + 1)
        rows = result.financial_breakdown[firm_id][first_year - 1:year]
        rows = [r for r in rows if r.get("revenue", 0) > 0]
        candidates = []
        if rows:
            first, last = rows[0], rows[-1]
            revenue = last["revenue"]
            for key, label in labels.items():
                # Depreciation is already included in fixed costs.
                a = first.get(key, 0) - (first.get("investment_depreciation", 0) if key == "fixed_cost" else 0)
                b = last.get(key, 0) - (last.get("investment_depreciation", 0) if key == "fixed_cost" else 0)
                growth = max(0, b / revenue - a / first["revenue"])
                if growth > 0.01:  # ignore shifts below one percent of revenue
                    candidates.append(dict(label_de=label, value=growth * revenue, share=b / revenue,
                                           text=f"{label} stiegen auf {b / revenue:.0%} des Umsatzes"))
            drop = max(0, first["revenue"] - revenue)
            if drop:
                candidates.append(dict(label_de="Umsatzrückgang", value=drop, share=drop / first["revenue"],
                                       text=f"der Umsatz fiel um {drop / first['revenue']:.0%}"))
        fines = [r for r in result.offence_ledger if r["firm"] == firm_id and first_year <= r["year"] <= year and r["fine"] > 0]
        if fines:
            amount = sum(r["fine"] for r in fines)
            candidates.append(dict(label_de="Bussen", value=amount,
                                   share=amount / sum(r["revenue"] for r in rows) if rows else 0,
                                   text=f"{len(fines)} Bussen kosteten {chf(amount)}"))
        drivers = sorted(candidates, key=lambda d: -d["value"])[:driver_count]
        exits = [e for e in result.events if e["firm"] == firm_id and e["event"] in ("bankruptcy", "takeover", "poisoning", "merger")]
        kind = exits[-1]["event"] if exits else "bankruptcy"
        events = []
        for event in result.events:
            if not first_year <= event["year"] <= year:
                continue
            if event["event"] == "market_entry":
                entrant = result.network.firm(event["firm"])
                if entrant.stage == firm.stage and entrant.region == firm.region:
                    events.append(event)
            elif not event["firm"] or event["event"] == "poisoning":
                events.append(event)
        descriptions = [d.pop("text") for d in drivers]
        explanation = ", ".join(descriptions) if descriptions else "keine eindeutigen finanziellen Rückgangstreiber in den verfügbaren Jahren"
        output[firm_id] = dict(exit_year=year, exit_type=kind, drivers=drivers,
                               decisions=[d for d in result.decisions if d["firm"] == firm_id and first_year <= d["year"] <= year],
                               events=events, summary_de=f"{firm.name} schied in Jahr {year} aus ({ {'bankruptcy': 'Konkurs', 'takeover': 'Übernahme', 'poisoning': 'Vergiftung', 'merger': 'Fusion'}[kind]}): {explanation}.")
    return output
