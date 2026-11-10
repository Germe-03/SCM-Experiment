"""Phase 10: new laws at random times and a cautious judgement of their effects."""

from __future__ import annotations

import random
from statistics import mean, pstdev
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from market_sim.runner import RunState, SimulationRunner


METRIC_DE = {
    "margin_retailer": "Händlermarge", "margin_wholesaler": "Grosshandelsmarge", "margin_factory": "Herstellermarge",
    "share_spirits": "Anteil Spirituosen", "share_wine": "Anteil Wein",
    "share_softdrinks": "Anteil Softdrinks", "share_water": "Anteil Wasser", "offences": "begangene Straftaten",
    "offences_detected": "entdeckte Straftaten", "average_customer_price": "Kundenpreis",
}


class LawBook:
    """Enacts laws; the firms only notice them through their own numbers."""

    def __init__(self, runner: SimulationRunner, seed: int) -> None:
        self.cfg = runner.config.laws
        self.rng = random.Random(f"laws-{seed}")
        self.enacted: list[dict[str, object]] = []
        self.minimum_wage: float | None = None

    def apply_yearly(self, runner: SimulationRunner) -> None:
        """Rules that hold every year after enactment (called after the annual plans)."""
        if self.minimum_wage is None:
            return
        floor = self.minimum_wage * runner.long_run.price_index
        for firm in runner._firms():
            if runner.env.runtimes[firm.id].active and firm.wage_level < floor:
                firm.wage_level = floor

    def year_end(self, runner: SimulationRunner, state: RunState) -> None:
        rolls = [self.rng.random() for _ in self.cfg.laws]
        if not self.cfg.enabled:
            return
        done = {law["name"] for law in self.enacted}
        for law, roll in zip(self.cfg.laws, rolls):
            if law.name in done or state.year < law.earliest_year or roll >= law.probability_per_year:
                continue
            self._enact(runner, law)
            self.enacted.append({"name": law.name, "title_de": law.title_de, "year": state.year,
                                 "watch": list(law.watch)})
            state.events.append({"year": state.year, "day": runner.config.simulation.days_per_year, "firm": "",
                                 "event": "law_enacted", "details": law.title_de})

    def _enact(self, runner: SimulationRunner, law) -> None:
        config, env = runner.config, runner.env
        if law.kind == "minimum_wage":
            # The floor sits a little above today's reference wage, in today's money.
            self.minimum_wage = law.strength * config.workforce.wage_reference / runner.long_run.price_index
        elif law.kind == "excise":
            env.excise[law.category] = env.excise.get(law.category, 0.0) + law.strength
        elif law.kind == "sugar_tax":
            # Like an excise tax on the unit cost, but only on softdrinks; part of the demand moves to water.
            category = law.category or "softdrinks"
            env.excise[category] = env.excise.get(category, 0.0) + law.strength
            book = env.brand_book
            if book is not None and law.demand_shift:
                book.law_shift[category] = book.law_shift.get(category, 1.0) * (1 - law.demand_shift)
                book.law_shift[law.shift_to] = book.law_shift.get(law.shift_to, 1.0) * (1 + law.demand_shift)
        elif law.kind == "deposit":
            # Deposit system: a fixed cost per unit (in today's money), growing with the price level.
            for category in law.categories or ["softdrinks", "water"]:
                env.deposit[category] = env.deposit.get(category, 0.0) + law.strength / runner.long_run.price_index
        elif law.kind == "ad_ban" and runner.marketing is not None:
            runner.marketing.banned_categories.add(law.category)
        elif law.kind == "packaging":
            components = config.commodities.components
            components["packaging"] = components.get("packaging", 0.0) * (1 + law.strength)
        elif law.kind == "controls":
            for offence in config.state.offences:
                offence.detection_probability = min(1.0, offence.detection_probability * law.strength)
        elif law.kind == "import_tariff":
            config.categories.imports.tariff += law.strength


def assess_laws(enacted: list[dict], system: list[dict], cfg) -> list[dict]:
    """Say what a law did only when it is clear; otherwise say that it is not yet clear."""
    by_year = {row["year"]: row for row in system}
    last_year = max(by_year) if by_year else 0
    rows = []
    for law in enacted:
        year = law["year"]
        after_years = [y for y in range(year + 1, year + 1 + cfg.window_years) if y in by_year]
        before_years = [y for y in range(year - cfg.window_years + 1, year + 1) if y in by_year]
        findings = []
        if len(after_years) < cfg.min_years_after:
            verdict = "Folgen noch unklar"
        else:
            for metric in law["watch"]:
                before = [float(by_year[y].get(metric, 0.0)) for y in before_years]
                after = [float(by_year[y].get(metric, 0.0)) for y in after_years]
                if len(before) < 2:
                    continue
                noise = pstdev(before)
                diff = mean(after) - mean(before)
                if noise > 0 and abs(diff) > cfg.clear_effect_sigma * noise:
                    findings.append({"metric": metric, "label_de": METRIC_DE.get(metric, metric),
                                     "before": mean(before), "after": mean(after), "change": diff})
            verdict = "Folge erkennbar" if findings else "keine klare Folge erkennbar"
        rows.append({**law, "years_observed": len(after_years), "verdict": verdict, "findings": findings,
                     "last_year": last_year})
    return rows
