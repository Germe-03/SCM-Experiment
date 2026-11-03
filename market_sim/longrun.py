"""Phase 3: long runs with inflation, wage and productivity growth, population and trends."""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from market_sim.kpi import TREND_DE

if TYPE_CHECKING:
    from market_sim.runner import RunState, SimulationRunner


class LongRun:
    """Year-end drift of the economy; all draws come from one seeded generator."""

    def __init__(self, runner: SimulationRunner, seed: int) -> None:
        self.cfg = runner.config.long_run
        self.rng = random.Random(f"longrun-{seed}")
        self.price_index = 1.0
        self.population_index = 1.0
        trends = self.cfg.trends
        self.current: str | None = None
        self.previous: str | None = None
        self.progress = 1.0
        self.next_switch = self._draw_gap(0) if trends else None

    def _draw_gap(self, year: int) -> int:
        low, high = self.cfg.trend_years
        return year + self.rng.randint(low, high)

    def year_end(self, runner: SimulationRunner, state: RunState) -> None:
        """Apply one year of drift after the year ``state.year`` has finished."""
        cfg = self.cfg
        # Fixed draw order: inflation, trend switch, trend choice.
        inflation_roll = self.rng.gauss(cfg.inflation_mean, cfg.inflation_sd)
        switch_choice = self.rng.random()
        fx_roll = self.rng.gauss(0.0, 1.0)
        if not cfg.enabled:
            return
        inflation = max(cfg.inflation_min, min(cfg.inflation_max, inflation_roll))
        self._inflate(runner, 1 + inflation)
        self._grow_population(runner)
        self._advance_trends(runner, state, switch_choice)
        self._drift_exchange_rate(runner, fx_roll)
        runner.env.domestic_daily_demand = runner.demand.mean
        state.events.append({
            "year": state.year, "day": runner.config.simulation.days_per_year, "firm": "",
            "event": "inflation", "details": f"{inflation:.2%}, Preisindex {self.price_index:.3f}",
        })

    # -- inflation, wages and productivity -----------------------------
    def _inflate(self, runner: SimulationRunner, factor: float) -> None:
        config = runner.config
        self.price_index *= factor
        config.price.min *= factor
        config.price.max *= factor
        for band in config.stage_prices.values():
            band.base *= factor
            band.min *= factor
            band.max *= factor
        config.demand.reference_price *= factor
        costs = config.costs
        costs.holding_cost_per_unit *= factor
        costs.backlog_cost_per_unit *= factor
        costs.handling_cost_per_unit *= factor
        env = runner.env
        env.holding_cost *= factor
        env.backlog_cost *= factor
        for runtime in env.runtimes.values():
            runtime.holding_cost *= factor
            runtime.backlog_cost *= factor
        fixed = config.fixed_costs
        fixed.base_per_day = {k: v * factor for k, v in fixed.base_per_day.items()}
        fixed.per_capacity_unit_per_day = {k: v * factor for k, v in fixed.per_capacity_unit_per_day.items()}
        config.commodities.components = {k: v * factor for k, v in config.commodities.components.items()}
        config.workforce.hiring_cost_per_employee *= factor
        config.workforce.wage_reference *= factor * (1 + self.cfg.real_wage_growth)
        config.rnd.effect_per_chf /= factor
        for event in config.events.types:
            event.cost *= factor
        if config.consumers is not None:
            for cls in config.consumers.classes:
                cls.max_price *= factor
        wage_factor = factor * (1 + self.cfg.real_wage_growth)
        for firm in runner._firms():
            firm.initial_wage_level *= wage_factor
            firm.wage_level *= wage_factor
            firm.initial_r_and_d_budget *= factor
            firm.productivity_per_employee *= 1 + self.cfg.productivity_growth
            firm.capacity = max(firm.capacity, round(firm.capacity * (1 + self.cfg.productivity_growth)))

    # -- population ------------------------------------------------------
    def _grow_population(self, runner: SimulationRunner) -> None:
        growth = self.cfg.population_growth
        book = runner.env.brand_book
        config = runner.config
        if config.consumers is None:
            return
        before = sum(c.persons * c.units_per_person_per_year for c in config.consumers.classes)
        for cls in config.consumers.classes:
            cls.persons = max(1, round(cls.persons * (1 + growth.get(cls.age_group or "", 0.0))))
        after = sum(c.persons * c.units_per_person_per_year for c in config.consumers.classes)
        factor = after / before if before else 1.0
        self.population_index *= factor
        runner.demand.mean *= factor
        if book is not None:
            units = config.unit_scale.real_units_per_sim_unit
            book.class_volume = {
                c.name: c.persons * c.units_per_person_per_year / units for c in config.consumers.classes
            }

    def _drift_exchange_rate(self, runner: SimulationRunner, roll: float) -> None:
        """Phase 4: CHF per EUR follows a mean-reverting random walk around its start."""
        cats = runner.config.categories
        if not cats.enabled:
            return
        env = runner.env
        log_fx = math.log(env.fx_rate / cats.fx_start)
        log_fx = (1 - cats.fx_reversion) * log_fx + cats.fx_sd * roll
        env.fx_rate = cats.fx_start * math.exp(log_fx)

    # -- trends ----------------------------------------------------------
    def _advance_trends(self, runner: SimulationRunner, state: RunState, choice: float) -> None:
        trends = {t.name: t for t in self.cfg.trends}
        if not trends:
            return
        self.progress = min(1.0, self.progress + 1 / max(1, self.cfg.trend_transition_years))
        if self.next_switch is not None and state.year >= self.next_switch:
            options = sorted(name for name in trends if name != self.current)
            new = options[min(len(options) - 1, int(choice * len(options)))]
            self.previous, self.current, self.progress = self.current, new, 1 / max(1, self.cfg.trend_transition_years)
            self.next_switch = self._draw_gap(state.year)
            state.events.append({
                "year": state.year, "day": runner.config.simulation.days_per_year, "firm": "",
                "event": "trend_change",
                "details": f"{TREND_DE.get(self.previous, self.previous) if self.previous else 'kein Trend'} → {TREND_DE.get(new, new)}",
            })
        boosts = []
        if self.current:
            t = trends[self.current]
            boosts.append((t.trait, t.strength * self.progress, set(t.age_groups)))
        if self.previous and self.progress < 1.0:
            t = trends[self.previous]
            boosts.append((t.trait, t.strength * (1 - self.progress), set(t.age_groups)))
        book = runner.env.brand_book
        if book is not None:
            book.trend_boosts = boosts
            book.entrant_trait = trends[self.current].trait if self.current else None

    @property
    def trend(self) -> str:
        return self.current or ""
