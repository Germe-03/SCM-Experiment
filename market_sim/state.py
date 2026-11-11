"""Phase 6: the state with taxes, offences, fines, poisoning scandals, takeovers and antitrust."""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from market_sim.holding_groups import category_allows_buy
from market_sim.kpi import OFFENCE_DE, chf
from market_sim.models import EXTRA_STAGES, STAGES

if TYPE_CHECKING:
    from market_sim.runner import RunState, SimulationRunner


class StateActor:
    """Collects taxes, detects offences, punishes them and supervises takeovers.

    The true detection rates and fines are hidden. Each firm starts with its own wrong
    guess and learns from its own outcomes and from public verdicts.
    """

    def __init__(self, runner: SimulationRunner, seed: int) -> None:
        self.cfg = runner.config.state
        self.rng = random.Random(f"state-{seed}")
        self.seed = seed
        self.beliefs: dict[str, dict[str, list[float]]] = {}
        self.active: dict[str, set[str]] = {}
        self.offence_ledger: list[dict[str, object]] = []
        self.previous_revenue: dict[str, float] = {}
        self.fear: dict[str, float] = {}
        self.stats = self._empty_stats()
        for firm in runner._firms():
            self._new_beliefs(firm.id)

    @staticmethod
    def _empty_stats() -> dict[str, float]:
        return {"taxes": 0.0, "offences": 0, "offences_detected": 0, "fines": 0.0, "poisonings": 0,
                "takeovers": 0, "takeovers_blocked": 0, "breakups": 0}

    def _new_beliefs(self, firm_id: str) -> None:
        spread = self.cfg.belief_spread
        self.beliefs[firm_id] = {
            o.name: [
                min(0.99, o.detection_probability * math.exp(self.rng.uniform(-spread, spread))),
                o.fine_revenue_share * math.exp(self.rng.uniform(-spread, spread)),
            ]
            for o in self.cfg.offences
        }

    # -- start of year: decide and apply offences ----------------------
    def apply_offences(self, runner: SimulationRunner) -> None:
        """Called after the annual strategies are set."""
        env = runner.env
        self.active = {}
        env.firm_material_factor = {}
        env.material_savings = {}
        env.wage_savings = {}
        env.wage_saving_ratio = {}
        self.previous_revenue = {key: rt.last_year_revenue for key, rt in env.runtimes.items()}
        for firm in runner._firms():
            runtime = env.runtimes[firm.id]
            if not runtime.active:
                continue
            if firm.id not in self.beliefs:
                self._new_beliefs(firm.id)
            if not self.willing(firm.id):
                continue
            risk = runner.strategies[firm.id].risk_tolerance if firm.id in runner.strategies else 0.5
            last_revenue = max(1.0, runtime.last_year_revenue)
            for offence in self.cfg.offences:
                if offence.kind == "material" and firm.stage != "factory":
                    continue
                detect, fine_share = self.beliefs[firm.id][offence.name]
                benefit = offence.benefit * self._base(offence.kind, runtime, last_revenue)
                penalty = detect * (offence.fine_fixed + fine_share * last_revenue)
                committed = benefit > penalty * (1 + self.cfg.aversion * (1 - risk))
                runner.decision_log.record(env.period // runner.config.simulation.days_per_year + 1,
                    firm.id, "offence", {"offence": offence.name, "committed": committed,
                    "believed_detection_probability": detect,
                    "believed_fine": offence.fine_fixed + fine_share * last_revenue,
                    "expected_gain": benefit, "risk_adjusted_penalty": penalty * (1 + self.cfg.aversion * (1 - risk))},
                    "Erwarteter Vorteil übersteigt risikogewichtete Busse" if committed else "Erwarteter Vorteil deckt risikogewichtete Busse nicht")
                if committed:
                    self.active.setdefault(firm.id, set()).add(offence.name)
                    self.stats["offences"] += 1
                    if offence.kind == "wage":
                        before = firm.wage_level
                        firm.wage_level *= 1 - offence.benefit
                        runtime.wage_level = firm.wage_level
                        env.wage_saving_ratio[firm.id] = before / firm.wage_level - 1 if firm.wage_level else 0.0
                    elif offence.kind == "material":
                        env.firm_material_factor[firm.id] = 1 - offence.benefit

    def _distribute(self, runner, year, firm_id, runtime, summary, tax) -> None:
        """Gewinnverwendung nach der Gewinnsteuer (nur wenn runner.profit_distribution gesetzt ist)."""
        dist = getattr(runner, "profit_distribution", None)
        if dist is None:
            return
        parent_rt = None
        groups = getattr(runner, "holding_groups", None)
        if groups is not None and groups.is_sub_only(firm_id):
            group = groups.group_of(firm_id)
            parent_rt = runner.env.runtimes.get(group.listing_id) if group is not None else None
        dist.distribute(year, firm_id, runtime, summary.profit - tax, runtime.initial_cash,
                        max(0.0, summary.revenue - summary.profit) / 12.0, parent_rt)

    def willing(self, firm_id: str) -> bool:
        """Only some firms consider breaking the law at all; the rest never weigh it."""
        return random.Random(f"honesty-{self.seed}-{firm_id}").random() < self.cfg.willing_share

    def _base(self, kind: str, runtime, revenue: float) -> float:
        """Last year's money the offence acts on (wages, materials or profit tax)."""
        if kind == "wage":
            return runtime.wage_cost_last_year
        if kind == "material":
            return runtime.purchase_cost_last_year
        return max(0.0, runtime.profit_last_year) * self.cfg.profit_tax

    # -- end of year: taxes, detection, poisoning ----------------------
    def year_end(self, runner: SimulationRunner, state: RunState) -> None:
        cfg = self.cfg
        env = runner.env
        year = state.year
        day = runner.config.simulation.days_per_year
        summaries = state.summaries[-1]
        verdicts: dict[str, list[float]] = {}
        for dealer in runner._dealers():
            # Phase 56: truck dealers pay profit tax like everybody else (no offences, no random draws).
            d_rt = env.runtimes[dealer.id]
            if d_rt.active and dealer.id in summaries:
                tax = max(0.0, summaries[dealer.id].profit) * cfg.profit_tax
                d_rt.adjust_cash(-tax, "staat:Gewinnsteuer")
                self.stats["taxes"] += tax
                self._distribute(runner, year, dealer.id, d_rt, summaries[dealer.id], tax)
        for firm in runner._firms():
            runtime = env.runtimes[firm.id]
            rolls = [self.rng.random() for _ in cfg.offences] + [self.rng.random()]
            if not runtime.active or firm.id not in summaries:
                # Insolvent firms have already closed before the state's year-end visit.
                for offence in cfg.offences:
                    if offence.name in self.active.get(firm.id, ()):
                        gain = (env.wage_savings.get(firm.id, 0.0) if offence.kind == "wage" else
                                env.material_savings.get(firm.id, 0.0) if offence.kind == "material" else 0.0)
                        self.offence_ledger.append({"firm": firm.id, "offence": offence.name, "year": year,
                                                    "gain": gain, "fine": 0.0, "damage": 0.0,
                                                    "net": gain, "paid_off": gain > 0})
                continue
            summary = summaries[firm.id]
            runtime.wage_cost_last_year = runtime.wage_cost - runtime.wage_cost_mark
            runtime.purchase_cost_last_year = runtime.purchase_cost - runtime.purchase_cost_mark
            runtime.profit_last_year = summary.profit
            runtime.wage_cost_mark, runtime.purchase_cost_mark = runtime.wage_cost, runtime.purchase_cost
            evading = any(o.kind == "tax" and o.name in self.active.get(firm.id, ()) for o in cfg.offences)
            tax_offence = next((o for o in cfg.offences if o.kind == "tax"), None)
            tax = max(0.0, summary.profit) * cfg.profit_tax
            if evading and tax_offence is not None:
                tax *= 1 - tax_offence.benefit
            runtime.adjust_cash(-tax, "staat:Gewinnsteuer")
            self.stats["taxes"] += tax
            self._distribute(runner, year, firm.id, runtime, summary, tax)
            for offence, roll in zip(cfg.offences, rolls):
                if offence.name not in self.active.get(firm.id, ()):
                    continue
                caught = roll < offence.detection_probability
                gain = (env.wage_savings.get(firm.id, 0.0) if offence.kind == "wage" else
                        env.material_savings.get(firm.id, 0.0) if offence.kind == "material" else
                        max(0.0, summary.profit) * cfg.profit_tax * offence.benefit)
                fine = damage = 0.0
                belief = self.beliefs[firm.id][offence.name]
                belief[0] += cfg.learning_rate * ((1.0 if caught else 0.0) - belief[0])
                if caught:
                    fine = offence.fine_fixed * runner.long_run.price_index + offence.fine_revenue_share * summary.revenue
                    runtime.adjust_cash(-fine, f"staat:Busse {offence.name}")
                    damage = offence.reputation_hit * self.previous_revenue.get(firm.id, 0.0) * cfg.reputation_value_factor
                    firm.reputation = max(0.0, firm.reputation - offence.reputation_hit)
                    self.stats["offences_detected"] += 1
                    self.stats["fines"] += fine
                    verdicts.setdefault(offence.name, []).append(offence.fine_revenue_share)
                    state.events.append({"year": year, "day": day, "firm": firm.id, "event": "offence_detected",
                                         "details": f"{OFFENCE_DE.get(offence.name, offence.name)}, Busse {chf(fine)}"})
                net = gain - fine - damage
                self.offence_ledger.append({"firm": firm.id, "offence": offence.name, "year": year,
                                            "gain": gain, "fine": fine, "damage": damage,
                                            "net": net, "paid_off": net > 0})
            if (any(o.kind == "material" and o.name in self.active.get(firm.id, ()) for o in cfg.offences)
                    and rolls[-1] < cfg.poisoning_probability):
                self._poisoning(runner, state, firm, year, day)
        # Public verdicts: every firm hears about them and adjusts its guesses.
        for name, shares in verdicts.items():
            for beliefs in self.beliefs.values():
                beliefs[name][0] += cfg.public_learning * (1.0 - beliefs[name][0]) * min(1, len(shares)) * 0.5
                beliefs[name][1] += cfg.learning_rate * (shares[0] - beliefs[name][1])
        for category in list(self.fear):
            self.fear[category] *= 0.5 ** (1 / max(0.1, cfg.fear_half_life_years))
            if self.fear[category] < 0.005:
                del self.fear[category]
        if env.brand_book is not None:
            env.brand_book.fear = dict(self.fear)

    def _poisoning(self, runner, state, firm, year, day) -> None:
        """A tainted product kills consumers: the firm closes, the category loses trust."""
        cfg = self.cfg
        env = runner.env
        runner.close_firm_now(firm.id, year, state, "poisoning",
                              f"{cfg.poisoning_deaths} Tote, {cfg.poisoning_sick} Kranke")
        self.stats["poisonings"] += 1
        self.fear[firm.category] = min(0.9, self.fear.get(firm.category, 0.0) + cfg.fear_strength)
        consumers = runner.config.consumers
        if consumers is not None:
            total = sum(c.persons for c in consumers.classes)
            for cls in consumers.classes:
                cls.persons = max(1, cls.persons - round(cfg.poisoning_deaths * cls.persons / total))
        book = env.brand_book
        if book is not None:
            for brand in book.brands.values():
                if brand.category == firm.category and brand.owner != firm.id:
                    brand.reputation = max(0.0, brand.reputation - cfg.category_reputation_hit * (1 - brand.reputation))

    # -- takeovers and antitrust ----------------------------------------
    def takeovers(self, runner: SimulationRunner, state: RunState) -> None:
        cfg = self.cfg
        env = runner.env
        year = state.year
        day = runner.config.simulation.days_per_year
        summaries = state.summaries[-1]
        for stage in [*STAGES, *EXTRA_STAGES]:
            active = [f for f in runner.network.firms_in(stage) if env.runtimes[f.id].active and f.id in summaries]
            # Producers compete within their category (beer, wine, spirits), not across all drinks.
            group = (lambda f: f.category) if stage == "factory" else (lambda f: "all")
            totals: dict[str, float] = {}
            for f in active:
                totals[group(f)] = totals.get(group(f), 0.0) + summaries[f.id].revenue
            share = {f.id: summaries[f.id].revenue / (totals[group(f)] or 1.0) for f in active}
            targets = sorted(
                (f for f in active if env.runtimes[f.id].cash < -cfg.distress_fraction * env.runtimes[f.id].credit_limit
                 or env.runtimes[f.id].consecutive_loss_years >= cfg.distress_loss_years),
                key=lambda f: env.runtimes[f.id].cash,
            )
            done = 0
            groups = getattr(runner, "holding_groups", None)
            for target in targets:
                if groups is not None and target.id in groups.sub_of:
                    continue  # a subsidiary is only sold together with or by its holding
                if done >= cfg.max_takeovers_per_stage or len(active) - done <= 2:
                    break
                if stage == "factory" and not target.importer and sum(
                        1 for f in active if f.category == target.category and not f.importer
                        and env.runtimes[f.id].active) <= 1:
                    continue
                t_rt = env.runtimes[target.id]
                price = max(0.0, cfg.price_per_capacity_unit * runner.long_run.price_index
                            * env._effective_capacity(target.id) + t_rt.cash)
                if groups is not None:
                    # Holding mode: the target stays a firm and keeps its cash and debts; only the capacity is paid.
                    price = max(0.0, cfg.price_per_capacity_unit * runner.long_run.price_index
                                * env._effective_capacity(target.id))
                buyers = sorted(
                    (f for f in active if f.id != target.id and summaries[f.id].profit > 0
                     and (f.category == target.category
                          or (groups is not None and stage == "factory"
                              and category_allows_buy(f.category, target.category)))
                     and f.channel == target.channel
                     and (env.runtimes[f.id].cash >= cfg.cash_cover * price
                          or env.arrange_funding(f.id, price, "takeover", cfg.cash_cover, commit=False))),
                    key=lambda f: (-env.runtimes[f.id].cash, f.id),
                )
                for buyer in buyers:
                    # Across categories (brewery buys soft drinks) the markets do not overlap.
                    combined = share[buyer.id] + (share[target.id] if buyer.category == target.category else 0.0)
                    holdings = getattr(runner, "holdings", None)
                    if holdings is not None:
                        # Phase 10: big stakes count like own market share.
                        combined += sum(share.get(t, 0.0) for t in holdings.antitrust_partners(buyer.id) if t != target.id)
                    if groups is not None and groups.group_of(buyer.id) is not None:
                        combined += sum(share.get(t, 0.0) for t in groups.group_of(buyer.id).subs
                                        if t not in (buyer.id, target.id))
                    if combined > cfg.block_share and stage not in EXTRA_STAGES:
                        self.stats["takeovers_blocked"] += 1
                        state.events.append({"year": year, "day": day, "firm": buyer.id, "event": "takeover_blocked",
                                             "details": f"{target.id}, gemeinsamer Marktanteil {combined:.0%}"})
                        continue
                    need = price + (0.0 if groups is not None else max(0.0, -t_rt.cash))
                    if env.loans_enabled and groups is None:
                        # Phase 55: pay from cash or take an investment loan.
                        if not env.arrange_funding(buyer.id, need, "takeover", 1.0, state):
                            continue
                    elif not env.can_spend(buyer.id, need):
                        continue
                    if groups is not None:
                        if not groups.acquire(runner, state, buyer, target, price, year, day):
                            continue
                    else:
                        self._merge(runner, state, buyer, target, price, year, day)
                    share[buyer.id] = combined
                    share[target.id] = 0.0
                    done += 1
                    break
            if stage not in EXTRA_STAGES:
                self._break_up(runner, state, stage, active, share, year, day)

    def _merge(self, runner, state, buyer, target, price, year, day) -> None:
        env = runner.env
        b_rt, t_rt = env.runtimes[buyer.id], env.runtimes[target.id]
        b_rt.adjust_cash(-price + min(0.0, t_rt.cash), f"uebernahme:{target.id}")  # the buyer also takes over the debt
        if env.banking is not None:
            env.banking.transfer_loans(target.id, buyer.id)  # Phase 55: investment loans go along
        buyer.capacity += target.capacity
        buyer.machine_capacity += target.machine_capacity
        buyer.employees += target.employees
        b_rt.employees = buyer.employees
        geo = env.geography
        if geo is not None:
            for region in geo.sites(target):
                if region not in geo.sites(buyer):
                    buyer.extra_regions.append(region)
        if env.brand_book is not None:
            for brand_id in env.brand_book.brands_of(target.id):
                env.brand_book.brands[brand_id].owner = buyer.id
        for brand_id, units in t_rt.stock.items():
            b_rt.stock[brand_id] = b_rt.stock.get(brand_id, 0) + units
        b_rt.inventory += t_rt.inventory
        if hasattr(env, "transfer_commodity_stock"):
            env.transfer_commodity_stock(target.id, buyer.id)
        t_rt.stock = {}
        t_rt.inventory = 0
        t_rt.adjust_cash(-t_rt.cash, f"uebernommen:{buyer.id}")
        if target.stage == "truck_dealer" and getattr(geo, "trucks", None) is not None:
            geo.trucks.merge_dealers(target.id, buyer.id)  # Phase 56: stock goes to the buyer
        # Phase 24: the buyer receives the research progress (implementation still to pay).
        if hasattr(runner.lab, "transfer"):
            runner.lab.transfer(target.id, buyer.id)
        # Phase 25: patents go to the buyer.
        if getattr(runner, "patent_office", None) is not None:
            runner.patent_office.transfer(target.id, buyer.id, year)
        runner.close_firm_now(target.id, year, state, "takeover", f"gekauft von {buyer.id} für {chf(price)}")
        runner.decision_log.record(year, buyer.id, "takeover_bought", {"target": target.id, "price": price}, "Übernahme eines finanziell angeschlagenen Konkurrenten")
        self.stats["takeovers"] += 1

    def _break_up(self, runner, state, stage, active, share, year, day) -> None:
        """A dominant firm must sell a site to a new competitor."""
        cfg = self.cfg
        env = runner.env
        geo = env.geography
        for firm in active:
            if share.get(firm.id, 0.0) <= cfg.breakup_share or not env.runtimes[firm.id].active:
                continue
            if geo is None or not firm.extra_regions:
                continue
            region = firm.extra_regions.pop()
            moved = max(1, round(firm.capacity * cfg.breakup_fraction))
            firm.capacity = max(1, firm.capacity - moved)
            moved_machines = round(firm.machine_capacity * cfg.breakup_fraction)
            firm.machine_capacity -= moved_machines
            moved_staff = max(1, round(firm.employees * cfg.breakup_fraction))
            firm.employees = max(1, firm.employees - moved_staff)
            env.runtimes[firm.id].employees = firm.employees
            spin = runner.spin_off(firm, state, region, moved, moved_machines, moved_staff)
            self.stats["breakups"] += 1
            state.events.append({"year": year, "day": day, "firm": firm.id, "event": "breakup",
                                 "details": f"Marktanteil {share[firm.id]:.0%}, Standort {region} an {spin} verkauft"})
