"""Phase 10: marketing budgets that build awareness of brands and stores."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from market_sim.runner import RunState, SimulationRunner


class Marketing:
    """Yearly budgets, daily spending and the awareness that results from it."""

    def __init__(self, runner: SimulationRunner) -> None:
        self.cfg = runner.config.marketing
        self.daily_budget: dict[str, float] = {}
        self.spent: dict[str, float] = {}
        self.banned_categories: set[str] = set()
        self.stats = {"marketing_spend": 0.0}

    def year_start(self, runner: SimulationRunner) -> None:
        """Set this year's budget per firm from its archetype and last year's revenue."""
        env = runner.env
        days = runner.config.simulation.days_per_year
        self.daily_budget = {}
        for firm in runner._firms():
            runtime = env.runtimes[firm.id]
            if not self.cfg.enabled or not runtime.active or runtime.cash <= 0:
                continue
            share = self.cfg.budget_share.get(runner.network.firm(firm.id).archetype, 0.0)
            if firm.stage in ("wholesaler", "distributor"):
                continue  # trade firms do not advertise to consumers
            self.daily_budget[firm.id] = share * runtime.last_year_revenue / days

    def daily(self, env) -> None:
        for firm_id, amount in self.daily_budget.items():
            runtime = env.runtimes[firm_id]
            if not runtime.active or amount <= 0:
                continue
            if not env.can_spend(firm_id, amount):
                continue
            runtime.fixed_cost += amount
            runtime.marketing_cost += amount
            self.spent[firm_id] = self.spent.get(firm_id, 0.0) + amount
            self.stats["marketing_spend"] += amount

    def year_end(self, runner: SimulationRunner, state: RunState) -> None:
        """Awareness fades and grows with this year's spending (diminishing returns)."""
        book = runner.env.brand_book
        cfg = self.cfg
        index = runner.long_run.price_index or 1.0
        spend_by_brand: dict[str, float] = {}
        for firm_id, amount in self.spent.items():
            firm = runner.network.firm(firm_id)
            if firm.stage == "retailer":
                aware = book.store_awareness.get(firm_id, cfg.start_awareness)
                gain = 1 - math.exp(-amount / index * cfg.effect_per_chf)
                book.store_awareness[firm_id] = aware * (1 - cfg.decay_per_year) + (1 - aware * (1 - cfg.decay_per_year)) * gain
            else:
                own = book.brands_of(firm_id)
                total = sum(book.production_share.get(b, 1.0) for b in own) or 1.0
                for b in own:
                    spend_by_brand[b] = spend_by_brand.get(b, 0.0) + amount * book.production_share.get(b, 1.0) / total
        for brand_id, brand in book.brands.items():
            aware = book.awareness.get(brand_id, cfg.start_awareness) * (1 - cfg.decay_per_year)
            spend = 0.0 if brand.category in self.banned_categories else spend_by_brand.get(brand_id, 0.0)
            gain = 1 - math.exp(-spend / index * cfg.effect_per_chf)
            book.awareness[brand_id] = aware + (1 - aware) * gain
        for firm in runner.network.firms_in("retailer"):
            if firm.id not in self.spent and firm.id in book.store_awareness:
                book.store_awareness[firm.id] *= 1 - cfg.decay_per_year
        self.spent = {}
