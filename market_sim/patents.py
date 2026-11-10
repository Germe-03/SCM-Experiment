"""Phase 25: patents on the first successful research of patentable tree stages (no licences)."""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from market_sim.kpi import PROJECT_DE, chf
from market_sim.models import behaviour_of

if TYPE_CHECKING:
    from market_sim.runner import RunState, SimulationRunner


class PatentOffice:
    """Grants, transfers and expires patents; blocks implementation by others.

    Phase 26: willing firms may infringe a patent; the office then detects, fines and
    orders compensation with its own random stream (old streams stay unchanged).
    """

    def __init__(self, runner: SimulationRunner, seed: int = 0) -> None:
        self.cfg = runner.config.patents
        self.active: dict[tuple[str, str], dict] = {}
        self.history: list[dict] = []
        self.stats = {"patents_granted": 0, "patent_fees": 0.0}
        self.rng = random.Random(f"patent-infringement-{seed}")
        # (firm, tree, stage) -> running infringement; finished ones move to infringement_history.
        self.infringements: dict[tuple[str, str, str], dict] = {}
        self.infringement_history: list[dict] = []
        self.ledger: list[dict] = []
        self.beliefs: dict[str, float] = {}

    @property
    def infringement_enabled(self) -> bool:
        """Return whether patent infringement is switched on."""
        return self.cfg.infringement.enabled

    def fee(self, years: int, price_index: float) -> float:
        """Return the patent fee for a term of the given length."""
        return (self.cfg.base_fee + self.cfg.fee_per_year * years) * price_index

    def choose_years(self, firm, cash: float, price_index: float) -> int:
        """Choose a patent term: long archetypes and cash-rich firms patent longer."""
        if (
            behaviour_of(firm) in self.cfg.long_archetypes
            or cash >= self.cfg.rich_cash_multiple * self.fee(self.cfg.max_years, price_index)
        ):
            return self.cfg.max_years
        if behaviour_of(firm) in self.cfg.short_archetypes:
            return self.cfg.min_years
        return (self.cfg.min_years + self.cfg.max_years) // 2

    def holder(self, tree: str, stage_name: str) -> str | None:
        """Return the holder of the active patent for a stage, if any."""
        patent = self.active.get((tree, stage_name))
        return patent["holder"] if patent else None

    def blocked(self, firm_id: str, tree: str, stage_name: str) -> bool:
        """Return whether another holder's active patent blocks a firm."""
        patent = self.active.get((tree, stage_name))
        if not patent:
            return False
        return patent["holder"] != firm_id and firm_id not in patent["prior_users"]

    def on_research_success(
        self,
        runner: SimulationRunner,
        state: RunState,
        firm,
        tree: str,
        stage,
        first: bool,
    ) -> dict | None:
        """Grant a patent on the first successful research of a patentable stage."""
        if (
            not self.cfg.enabled
            or not first
            or not getattr(stage, "patentable", False)
            or (tree, stage.name) in self.active
        ):
            return None

        runtime = runner.env.runtimes[firm.id]
        price = runner.long_run.price_index
        years = self.choose_years(firm, runtime.cash, price)
        fee = self.fee(years, price)
        if runtime.cash < self.cfg.cash_cover * fee or not runner.env.can_spend(firm.id, fee):
            return None
        runtime.adjust_cash(-fee, "staat:Patentgebühr")

        # Firms that implemented the stage before the patent count as prior users.
        prior_users = {
            other_id
            for other_id, progress in runner.lab.progress.items()
            if other_id != firm.id and progress.get(stage.name) == "implemented"
        }
        prior_users.update(
            other_id
            for other_id, (name, _, _, _, _, step, run_tree) in runner.lab.running.items()
            if other_id != firm.id
            and name == stage.name
            and step == "implementation"
            and run_tree == tree
        )

        patent = {
            "tree": tree,
            "stage": stage.name,
            "holder": firm.id,
            "first_holder": firm.id,
            "granted_year": state.year,
            "years": years,
            "expires_year": state.year + years,
            "fee": fee,
            "prior_users": sorted(prior_users),
            "status": "active",
            "end_year": None,
        }
        self.active[(tree, stage.name)] = patent
        self.history.append(patent)
        self.stats["patents_granted"] += 1
        self.stats["patent_fees"] += fee

        label = PROJECT_DE.get(stage.name, stage.name)
        days = runner.config.simulation.days_per_year
        state.events.append({
            "year": state.year,
            "day": days,
            "firm": firm.id,
            "event": "patent_granted",
            "details": (
                f"{label}: Patent für {years} Jahre bis Jahr {state.year + years}, "
                f"Gebühr {chf(fee)}"
            ),
        })
        return patent

    def transfer(self, seller_id: str, buyer_id: str, year: int) -> None:
        """Move a seller's active patents to the buyer (takeover)."""
        for key in sorted(self.active):
            patent = self.active[key]
            if patent["holder"] == seller_id:
                patent["holder"] = buyer_id

    # -- Phase 26: patent infringement --------------------------------------
    def _belief(self, firm_id: str) -> float:
        """Return a firm's believed detection probability (one draw per firm, cached)."""
        if firm_id not in self.beliefs:
            cfg = self.cfg.infringement
            spread = cfg.belief_spread
            self.beliefs[firm_id] = min(
                0.99, cfg.detection_probability * math.exp(self.rng.uniform(-spread, spread))
            )
        return self.beliefs[firm_id]

    def yearly_gain(self, stage, revenue: float) -> float:
        """Return the estimated yearly gain from using a stage."""
        return stage.effect * max(0.0, revenue) * self.cfg.infringement.advantage_per_effect

    def consider_infringement(
        self,
        runner: SimulationRunner,
        state: RunState,
        firm,
        tree: str,
        stage,
    ) -> bool:
        """Let a willing firm weigh implementing another holder's patented stage."""
        cfg = self.cfg.infringement
        actor = getattr(runner, "state_actor", None)
        if (
            not cfg.enabled
            or actor is None
            or not self.blocked(firm.id, tree, stage.name)
            or not actor.willing(firm.id)
        ):
            return False
        patent = self.active[(tree, stage.name)]
        runtime = runner.env.runtimes[firm.id]
        price = runner.long_run.price_index
        revenue = max(1.0, runtime.last_year_revenue)
        belief = self._belief(firm.id)
        years_left = max(1, patent["expires_year"] - state.year)
        benefit = self.yearly_gain(stage, revenue) * years_left
        damages = max(cfg.min_damages * price, benefit)
        believed_fine = cfg.fine_fixed * price + cfg.fine_revenue_share * revenue
        reputation_cost = cfg.reputation_hit * revenue * actor.cfg.reputation_value_factor
        penalty = belief * (believed_fine + damages + reputation_cost)
        risk = runner.strategies[firm.id].risk_tolerance if firm.id in runner.strategies else 0.5
        weighted = penalty * (1 + actor.cfg.aversion * (1 - risk))
        committed = benefit > weighted
        runner.decision_log.record(
            state.year,
            firm.id,
            "offence",
            {
                "offence": "patentverletzung",
                "committed": committed,
                "stage": stage.name,
                "holder": patent["holder"],
                "believed_detection_probability": belief,
                "believed_fine": believed_fine,
                "believed_damages": damages,
                "expected_gain": benefit,
                "risk_adjusted_penalty": weighted,
            },
            "Erwarteter Vorteil übersteigt risikogewichtete Busse und Schadenersatz"
            if committed
            else "Erwarteter Vorteil deckt risikogewichtete Busse und Schadenersatz nicht",
        )
        if committed:
            self.infringements[(firm.id, tree, stage.name)] = {
                "firm": firm.id,
                "holder": patent["holder"],
                "tree": tree,
                "stage": stage.name,
                "start_year": state.year,
                "active_year": None,
                "end_year": None,
                "status": "planned",
                "gain": 0.0,
                "undo": None,
            }
        return committed

    def on_implemented(self, firm_id: str, tree: str, stage_name: str, record: dict) -> None:
        """Mark an infringement as active once the illegal implementation is finished."""
        infringement = self.infringements.get((firm_id, tree, stage_name))
        if infringement is None:
            return
        infringement["status"] = "active"
        infringement["undo"] = record

    def _end_infringement(self, key: tuple[str, str, str], status: str, year: int) -> None:
        infringement = self.infringements.pop(key)
        infringement["status"] = status
        infringement["end_year"] = year
        self.infringement_history.append(infringement)

    def _book_row(self, runner: SimulationRunner, row: dict) -> None:
        self.ledger.append(row)
        actor = getattr(runner, "state_actor", None)
        if actor is not None:
            actor.offence_ledger.append(dict(row))

    def _infringement_year_end(self, runner: SimulationRunner, state: RunState) -> None:
        """Detect, fine and stop infringements; end them unpunished once the patent is gone."""
        if not self.infringements:
            return
        cfg = self.cfg.infringement
        env = runner.env
        actor = getattr(runner, "state_actor", None)
        days = runner.config.simulation.days_per_year
        price = runner.long_run.price_index
        summaries = state.summaries[-1] if state.summaries else {}
        learning = actor.cfg.learning_rate if actor is not None else 0.0
        for key in sorted(self.infringements):
            firm_id, tree, name = key
            infringement = self.infringements[key]
            if not env.runtimes[firm_id].active:
                # The infringer closed (bankruptcy or takeover): nothing left to punish.
                self._end_infringement(key, "dropped", state.year)
                continue
            patent = self.active.get((tree, name))
            holder = patent["holder"] if patent else None
            legal = holder is None or holder == firm_id or not env.runtimes[holder].active
            if infringement["status"] != "active":
                if legal:
                    self._end_infringement(key, "ended", state.year)
                continue
            if infringement["active_year"] is None:
                # Implemented this year: the use starts now, the first check comes next year.
                infringement["active_year"] = state.year
                continue
            roll = self.rng.random()
            if legal:
                self._end_infringement(key, "ended", state.year)
                continue

            firm = runner.network.firm(firm_id)
            runtime = env.runtimes[firm_id]
            stage = runner.lab.stages[tree][name]
            summary = summaries.get(firm_id)
            revenue = summary.revenue if summary is not None else runtime.last_year_revenue
            gain = self.yearly_gain(stage, revenue)
            infringement["gain"] += gain
            infringement["holder"] = holder
            caught = roll < cfg.detection_probability
            belief = self._belief(firm_id)
            self.beliefs[firm_id] = belief + learning * ((1.0 if caught else 0.0) - belief)
            if actor is not None:
                actor.stats["offences"] += 1

            fine = damage = compensation = 0.0
            if caught:
                fine = cfg.fine_fixed * price + cfg.fine_revenue_share * revenue
                runtime.adjust_cash(-fine, "staat:Busse patentverletzung")
                compensation = max(cfg.min_damages * price, infringement["gain"])
                runtime.adjust_cash(-compensation, f"schadenersatz:{holder}")
                env.runtimes[holder].adjust_cash(compensation, f"schadenersatz:{firm_id}")
                previous = (
                    actor.previous_revenue.get(firm_id, runtime.last_year_revenue)
                    if actor is not None
                    else runtime.last_year_revenue
                )
                value_factor = actor.cfg.reputation_value_factor if actor is not None else 0.0
                damage = cfg.reputation_hit * previous * value_factor
                firm.reputation = max(0.0, firm.reputation - cfg.reputation_hit)
                runner.lab.undo_stage(runner, firm, stage, infringement["undo"] or {})
                if actor is not None:
                    actor.stats["offences_detected"] += 1
                    actor.stats["fines"] += fine
                label = PROJECT_DE.get(name, name)
                state.events.append({
                    "year": state.year,
                    "day": days,
                    "firm": firm_id,
                    "event": "offence_detected",
                    "details": (
                        f"Patentverletzung ({label}, Patent von {holder}), Busse {chf(fine)}, "
                        f"Schadenersatz {chf(compensation)}"
                    ),
                })
                infringement["fine"] = fine
                infringement["compensation"] = compensation

            net = gain - fine - damage - compensation
            self._book_row(runner, {
                "firm": firm_id,
                "offence": "patentverletzung",
                "year": state.year,
                "gain": gain,
                "fine": fine,
                "damage": damage,
                "compensation": compensation,
                "net": net,
                "paid_off": net > 0,
                "holder": holder,
            })
            if caught:
                self._end_infringement(key, "caught", state.year)

    def year_end(self, runner: SimulationRunner, state: RunState) -> None:
        """Expire patents at term end and lapse patents of bankrupt holders."""
        self._infringement_year_end(runner, state)
        days = runner.config.simulation.days_per_year
        for key in sorted(self.active):
            patent = self.active[key]
            holder = patent["holder"]
            label = PROJECT_DE.get(patent["stage"], patent["stage"])
            if not runner.env.runtimes[holder].active:
                patent["status"] = "lapsed"
                patent["end_year"] = state.year
                del self.active[key]
                state.events.append({
                    "year": state.year,
                    "day": days,
                    "firm": holder,
                    "event": "patent_expired",
                    "details": f"{label}: Patent verfällt (Konkurs von {holder})",
                })
            elif state.year >= patent["expires_year"]:
                patent["status"] = "expired"
                patent["end_year"] = state.year
                del self.active[key]
                state.events.append({
                    "year": state.year,
                    "day": days,
                    "firm": holder,
                    "event": "patent_expired",
                    "details": f"{label}: Patent abgelaufen, alle dürfen umsetzen",
                })
        # Phase 26: once the patent is gone, an undetected infringement ends unpunished.
        for key in sorted(self.infringements):
            if (key[1], key[2]) not in self.active:
                self._end_infringement(key, "ended", state.year)

    def report(self) -> list[dict]:
        """Return copies of all patents ever granted, in grant order."""
        copies = []
        for patent in self.history:
            copy = dict(patent)
            copy["prior_users"] = list(patent["prior_users"])
            copies.append(copy)
        return copies
