"""Phase 43: voluntary mergers between firms with mutual advantages."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from market_sim.kpi import chf
from market_sim.models import STAGES

if TYPE_CHECKING:
    from market_sim.runner import RunState, SimulationRunner


class Mergers:
    """Evaluate, form and report mergers between active firms."""

    def __init__(self, runner: SimulationRunner, seed: int) -> None:
        self.cfg = runner.config.mergers
        self.rng = random.Random(f"mergers-{seed}")
        self.counter = 0
        self.log: list[dict] = []
        self.new_firms: dict[str, dict] = {}
        self.stats = {"mergers": 0, "mergers_blocked": 0}

    def year_end(self, runner: SimulationRunner, state: RunState) -> None:
        """Apply integration costs and consider mergers at the end of the year."""
        env = runner.env
        year = state.year
        day = runner.config.simulation.days_per_year

        for firm_id in sorted(self.new_firms):
            entry = self.new_firms[firm_id]
            if entry["year"] + 1 == year:
                env.merger_efficiency.pop(firm_id, None)
                env.merger_fixed_factor[firm_id] = 1 - entry["saving"]

        if not self.cfg.enabled or self.cfg.max_per_year == 0:
            return

        summaries = state.summaries[-1]
        groups = getattr(runner, "holding_groups", None)
        candidates = [
            firm
            for firm in runner._firms()
            if env.runtimes[firm.id].active
            and firm.id in summaries
            and summaries[firm.id].revenue > 0
            and (groups is None or groups.group_of(firm.id) is None)
            and not (
                firm.id in self.new_firms
                and self.new_firms[firm.id]["year"] == year
            )
        ]
        candidates.sort(key=lambda firm: firm.id)

        # Draw every candidate's roll before making any decisions.
        rolls = {firm.id: self.rng.random() for firm in candidates}

        def market_key(firm) -> tuple[str, str]:
            return firm.stage, firm.category if firm.stage == "factory" else "all"

        totals: dict[tuple[str, str], float] = {}
        for firm in runner._firms():
            if env.runtimes[firm.id].active and firm.id in summaries:
                key = market_key(firm)
                totals[key] = totals.get(key, 0.0) + summaries[firm.id].revenue
        shares = {
            firm.id: summaries[firm.id].revenue / (totals.get(market_key(firm), 0.0) or 1.0)
            for firm in candidates
        }

        def weak(firm) -> bool:
            summary = summaries[firm.id]
            return (
                summary.profit <= 0
                or summary.profit / summary.revenue < self.cfg.weak_margin
                or env.runtimes[firm.id].consecutive_loss_years >= 1
            )

        def fixed_cost_ratio(firm) -> float:
            breakdown = state.financial_breakdown.get(firm.id, [])
            if not breakdown:
                fixed_cost = 0.0
            else:
                fixed_cost = breakdown[-1].get("fixed_cost", 0.0)
            revenue = summaries[firm.id].revenue
            return fixed_cost / revenue if revenue > 0 else 0.0

        def compatible(a, b) -> bool:
            same_channel = (
                (a.channel if a.stage == "retailer" else "store")
                == (b.channel if b.stage == "retailer" else "store")
            )
            if not same_channel:
                return False
            if a.stage == b.stage:
                return a.stage != "factory" or a.category == b.category
            return abs(STAGES.index(a.stage) - STAGES.index(b.stage)) == 1

        merged: set[str] = set()
        formed = 0
        for a in candidates:
            if a.id in merged:
                continue

            rev_a = summaries[a.id].revenue
            partners = [
                b
                for b in candidates
                if b.id != a.id
                and b.id not in merged
                and compatible(a, b)
                and min(rev_a, summaries[b.id].revenue)
                / max(rev_a, summaries[b.id].revenue)
                >= self.cfg.min_size_ratio
            ]
            partners.sort(key=lambda firm: (-summaries[firm.id].revenue, firm.id))

            for b in partners:
                if formed >= self.cfg.max_per_year:
                    return

                rev_b = summaries[b.id].revenue
                saving_mid = (self.cfg.fixed_saving_min + self.cfg.fixed_saving_max) / 2
                if a.stage != b.stage:
                    saving_mid /= 2

                fc_a = fixed_cost_ratio(a)
                fc_b = fixed_cost_ratio(b)
                combined_ratio = (
                    (fc_a * rev_a + fc_b * rev_b)
                    * (1 - saving_mid)
                    / (rev_a + rev_b)
                )
                combined_revenue = rev_a + rev_b

                def advantage(firm, own_revenue: float, own_ratio: float) -> tuple[bool, float]:
                    cost_gain = (
                        (own_ratio - combined_ratio) / own_ratio
                        if own_ratio > 0
                        else 0.0
                    )
                    key = market_key(firm)
                    combined_share = max(
                        shares[firm.id],
                        combined_revenue / (totals.get(key, 0.0) or 1.0),
                    )
                    share_gain = combined_share - shares[firm.id]
                    sees_advantage = (
                        cost_gain > 0 or share_gain >= self.cfg.min_share_gain
                    )
                    probability = (
                        min(
                            1.0,
                            self.cfg.base_probability
                            * (
                                1
                                + max(0.0, min(1.0, cost_gain))
                                + share_gain
                            )
                            * (
                                self.cfg.weak_multiplier
                                if weak(firm)
                                else 1.0
                            ),
                        )
                        if sees_advantage
                        else 0.0
                    )
                    return rolls[firm.id] < probability, share_gain

                agrees_a, _ = advantage(a, rev_a, fc_a)
                agrees_b, _ = advantage(b, rev_b, fc_b)
                if not (agrees_a and agrees_b):
                    continue

                combined_shares = []
                involved_stages = sorted(
                    {a.stage, b.stage}, key=STAGES.index
                )
                for stage in involved_stages:
                    stage_firms = [firm for firm in (a, b) if firm.stage == stage]
                    key = market_key(stage_firms[0])
                    stage_revenue = sum(
                        summaries[firm.id].revenue for firm in stage_firms
                    )
                    combined_shares.append(
                        stage_revenue / (totals.get(key, 0.0) or 1.0)
                    )
                combined_share = max(combined_shares, default=0.0)
                if combined_share > self.cfg.max_market_share:
                    state.events.append({
                        "year": year,
                        "day": day,
                        "firm": a.id,
                        "event": "merger_blocked",
                        "details": (
                            f"Staat verbietet Fusion von {a.name} und {b.name}, "
                            f"gemeinsamer Marktanteil {combined_share:.0%}"
                        ),
                    })
                    self.stats["mergers_blocked"] += 1
                    continue

                self._merge(runner, state, a, b)
                merged.update((a.id, b.id))
                formed += 1
                if formed >= self.cfg.max_per_year:
                    return
                break

    def _merge(self, runner: SimulationRunner, state: RunState, a, b) -> None:
        """Create a merged firm, transfer its assets and close its parents."""
        env = runner.env
        summaries = state.summaries[-1]
        rev_a = summaries[a.id].revenue
        rev_b = summaries[b.id].revenue
        if rev_a > rev_b or (rev_a == rev_b and a.id < b.id):
            big, small = a, b
        else:
            big, small = b, a

        rev_big = summaries[big.id].revenue
        rev_small = summaries[small.id].revenue
        total_revenue = rev_big + rev_small

        existing_ids = {firm.id for firm in runner._firms()}
        while True:
            self.counter += 1
            new_id = f"{big.stage}_f{self.counter:02d}"
            if new_id not in existing_ids and new_id not in env.runtimes:
                break

        ratio = rev_small / rev_big if rev_big > 0 else 0.0
        name = (
            f"{big.name} & {small.name}"
            if ratio >= self.cfg.double_name_ratio and " & " not in big.name + small.name
            else big.name
        )

        extra_regions = []
        for region in [*big.extra_regions, *small.extra_regions, small.region]:
            if region is not None and region != big.region and region not in extra_regions:
                extra_regions.append(region)

        upstream_stage = runner.network.upstream_stage(big.stage)
        existing_firms = {firm.id: firm for firm in runner._firms()}
        if upstream_stage is None:
            suppliers = []
        else:
            suppliers = [
                supplier_id
                for supplier_id in dict.fromkeys([*big.suppliers, *small.suppliers])
                if supplier_id in existing_firms
                and existing_firms[supplier_id].stage == upstream_stage
            ]

        def weighted_mean(field: str) -> float:
            return (
                getattr(big, field) * rev_big + getattr(small, field) * rev_small
            ) / total_revenue

        new = big.model_copy(deep=True, update={
            "id": new_id,
            "name": name,
            "cash": big.cash,
            "capacity": big.capacity + small.capacity,
            "machine_capacity": big.machine_capacity + small.machine_capacity,
            "employees": big.employees + small.employees,
            "inventory": 0,
            "backlog": 0,
            "extra_regions": extra_regions,
            "suppliers": suppliers,
            "quality_level": weighted_mean("quality_level"),
            "reputation": weighted_mean("reputation"),
            "wage_level": weighted_mean("wage_level"),
            "reliability": weighted_mean("reliability"),
            "r_and_d_level": max(big.r_and_d_level, small.r_and_d_level),
            "r_and_d_budget": big.r_and_d_budget + small.r_and_d_budget,
            "overtime_level": big.overtime_level,
            "importer": (
                big.importer and small.importer
                if big.stage == small.stage
                else big.importer
            ),
            "category": big.category,
        })

        brand_book = env.brand_book
        if brand_book is not None:
            for firm in (big, small):
                for brand_id in sorted(brand_book.brands_of(firm.id)):
                    brand_book.brands[brand_id].owner = new.id

        runner.add_firm(new, state)

        for firm in runner._firms():
            if firm.id in (big.id, small.id):
                continue
            had_old_supplier = big.id in firm.suppliers or small.id in firm.suppliers
            firm.suppliers = [
                supplier_id
                for supplier_id in firm.suppliers
                if supplier_id not in (big.id, small.id)
            ]
            if (
                had_old_supplier
                and runner.network.upstream_stage(firm.stage) == new.stage
                and new.id not in firm.suppliers
            ):
                firm.suppliers.append(new.id)

        rt_big = env.runtimes[big.id]
        rt_small = env.runtimes[small.id]
        n_rt = env.runtimes[new.id]
        total_cash = rt_big.cash + rt_small.cash
        n_rt.adjust_cash(total_cash - n_rt.cash, f"fusion:{big.id}+{small.id}")
        if env.banking is not None:
            env.banking.transfer_loans(big.id, new.id)  # Phase 55: investment loans go along
            env.banking.transfer_loans(small.id, new.id)
        if hasattr(env, "transfer_commodity_stock"):
            env.transfer_commodity_stock(big.id, new.id)
            env.transfer_commodity_stock(small.id, new.id)
        for old_runtime in (rt_big, rt_small):
            old_runtime.adjust_cash(-old_runtime.cash, f"fusion_in:{new.id}")
            for brand_id, units in old_runtime.stock.items():
                n_rt.stock[brand_id] = n_rt.stock.get(brand_id, 0) + units
            n_rt.inventory += old_runtime.inventory
            old_runtime.stock = {}
            old_runtime.inventory = 0

        n_rt.last_year_revenue = rt_big.last_year_revenue + rt_small.last_year_revenue
        n_rt.credit_limit = max(rt_big.credit_limit, rt_small.credit_limit)
        n_rt.employees = new.employees
        for field in ("quality_level", "reputation", "reliability"):
            if hasattr(n_rt, field):
                value_big = getattr(rt_big, field, getattr(big, field))
                value_small = getattr(rt_small, field, getattr(small, field))
                setattr(
                    n_rt,
                    field,
                    (value_big * rev_big + value_small * rev_small) / total_revenue,
                )

        lab = runner.lab
        if hasattr(lab, "transfer"):
            lab.transfer(big.id, new.id)
            lab.transfer(small.id, new.id)
        progress = getattr(lab, "progress", None)
        if isinstance(progress, dict):
            merged_progress = progress.setdefault(new.id, {})
            old_progress = (progress.get(big.id, {}), progress.get(small.id, {}))
            for project in sorted(set(old_progress[0]) | set(old_progress[1])):
                levels = (old_progress[0].get(project), old_progress[1].get(project))
                if "implemented" in levels:
                    merged_progress[project] = "implemented"
                elif "researched" in levels:
                    merged_progress[project] = "researched"

        patent_office = getattr(runner, "patent_office", None)
        if patent_office is not None:
            patent_office.transfer(big.id, new.id, state.year)
            patent_office.transfer(small.id, new.id, state.year)

        for firm in (big, small):
            runner.close_firm_now(
                firm.id, state.year, state, "merger", f"fusioniert zu {new.name}"
            )

        env.merger_efficiency[new.id] = 1 - self.cfg.efficiency_loss
        env.merger_fixed_factor[new.id] = 1 + self.cfg.integration_cost_share
        saving = self.rng.uniform(
            self.cfg.fixed_saving_min, self.cfg.fixed_saving_max
        )
        self.new_firms[new.id] = {"year": state.year, "saving": saving}

        stock_market = getattr(runner, "stock_market", None)
        if stock_market is not None:
            shares = runner.config.stock_market.shares_per_firm
            price_big = stock_market.price(big.id)
            price_small = stock_market.price(small.id)
        else:
            shares = 0
            price_big = price_small = None

        cap_big = (
            price_big * shares if price_big is not None else rev_big
        )
        cap_small = (
            price_small * shares if price_small is not None else rev_small
        )
        if cap_big + cap_small > 0:
            share_big = cap_big / (cap_big + cap_small)
        else:
            share_big = rev_big / total_revenue if total_revenue > 0 else 0.5
        share_small = 1 - share_big

        day = runner.config.simulation.days_per_year
        state.events.append({
            "year": state.year,
            "day": day,
            "firm": new.id,
            "event": "merger_formed",
            "details": (
                f"{big.name} und {small.name} fusionieren zu {new.name} "
                f"(ohne Geldfluss). Aktien nach Börsenwert: "
                f"{share_big:.0%} / {share_small:.0%}. "
                f"Jahr 1: Integrationskosten, danach tiefere Fixkosten ({saving:.0%})"
            ),
        })
        self.log.append({
            "year": state.year,
            "new": new.id,
            "name": new.name,
            "parents": [big.id, small.id],
            "share_parents": [share_big, share_small],
            "cash": total_cash,
            "saving": saving,
        })
        self.stats["mergers"] += 1
        runner.decision_log.record(
            state.year,
            new.id,
            "merger",
            {"parents": [big.id, small.id]},
            "Fusion zweier Firmen mit gegenseitigem Vorteil",
        )

    def report(self) -> list[dict]:
        """Return copies of the merger log."""
        return [
            {
                **row,
                "parents": list(row["parents"]),
                "share_parents": list(row["share_parents"]),
            }
            for row in self.log
        ]
