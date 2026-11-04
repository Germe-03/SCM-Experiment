"""Phase 11: regional labour markets with scarce workers, wage pressure and poaching."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from market_sim.runner import RunState, SimulationRunner


class LaborMarket:
    """One pool of workers per region; firms compete for them with their wages."""

    def __init__(self, runner: SimulationRunner) -> None:
        self.cfg = runner.config.labor
        self.pool: dict[str, float] = {}
        self.wage_index: dict[str, float] = {}
        self.open_positions: dict[str, int] = {}
        self.stats = {"open_positions": 0, "poached_workers": 0, "hires": 0}
        self.base_population = None

    def _region(self, runner, firm) -> str:
        return firm.region or "all"

    def _init_pools(self, runner) -> None:
        """Workers live where people live: the pool follows the population of the regions."""
        total = sum(f.employees for f in runner._firms() if runner.env.runtimes[f.id].active)
        geo = runner.env.geography
        shares = geo.population if geo is not None else {"all": 1.0}
        self.pool = {r: total * (1 + self.cfg.initial_slack) * s for r, s in shares.items()}
        self.wage_index = {r: 1.0 for r in self.pool}
        self.base_population = runner.long_run.population_index

    def year_start(self, runner: SimulationRunner) -> None:
        """Wages adjust to scarcity, poorly paid staff leave, then firms hire from what is left."""
        if not self.cfg.enabled:
            return
        if not self.pool:
            self._init_pools(runner)
        cfg = self.cfg
        env = runner.env
        growth = runner.long_run.population_index / (self.base_population or 1.0)
        self.base_population = runner.long_run.population_index
        self.pool = {r: n * growth for r, n in self.pool.items()}
        firms = [f for f in runner._firms() if env.runtimes[f.id].active]
        by_region: dict[str, list] = {}
        for firm in firms:
            by_region.setdefault(self._region(runner, firm), []).append(firm)
        self.open_positions = {}
        for region, members in sorted(by_region.items()):
            pool = self.pool.setdefault(region, sum(f.employees for f in members) * (1 + cfg.initial_slack))
            if pool <= 0:
                continue
            index = self.wage_index.setdefault(region, 1.0)
            employed = sum(f.employees for f in members)
            tightness = employed / pool if pool else 1.0
            # Scarce workers push wages up, slack lets them drift back.
            if tightness > cfg.tight_threshold:
                index *= 1 + cfg.wage_pressure * (tightness - cfg.tight_threshold)
            else:
                index *= 1 - cfg.wage_relief * (cfg.tight_threshold - tightness)
            index = max(cfg.wage_index_min, min(cfg.wage_index_max, index))
            self.wage_index[region] = index
            for firm in members:
                firm.wage_level *= index
                env.runtimes[firm.id].wage_level = firm.wage_level
            # Poaching: firms paying clearly less than the regional average lose staff
            # to the best payer of the region.
            mean_wage = sum(f.wage_level * f.employees for f in members) / max(1, employed)
            best = max(members, key=lambda f: (f.wage_level, f.id))
            for firm in sorted(members, key=lambda f: f.id):
                if firm is best or firm.wage_level >= mean_wage * (1 - cfg.poach_gap):
                    continue
                leaving = min(firm.employees - 1, round(firm.employees * cfg.poach_rate))
                if leaving <= 0:
                    continue
                firm.employees -= leaving
                best.employees += leaving
                env.runtimes[firm.id].employees = firm.employees
                env.runtimes[best.id].employees = best.employees
                self.stats["poached_workers"] += leaving
            # Hiring: the best payers get the free workers first.
            free = max(0, int(pool - sum(f.employees for f in members)))
            for firm in sorted(members, key=lambda f: (-f.wage_level, f.id)):
                strategy = runner.strategies.get(firm.id)
                wanted = strategy.hiring_plan if strategy is not None else 0
                granted = max(0, min(wanted, free))
                free -= granted
                firm.employees = max(runner.config.workforce.min_employees, firm.employees + granted)
                env.runtimes[firm.id].employees = firm.employees
                self.stats["hires"] += granted
                if wanted > granted:
                    self.open_positions[firm.id] = wanted - granted
        self.stats["open_positions"] = sum(self.open_positions.values())

    def tightness(self, runner, region: str) -> float:
        employed = sum(f.employees for f in runner._firms()
                       if runner.env.runtimes[f.id].active and self._region(runner, f) == region)
        pool = self.pool.get(region, 0.0)
        return employed / pool if pool else 0.0
