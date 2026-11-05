"""Phase 25: patents on the first successful research of patentable tree stages (no licences)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from market_sim.kpi import PROJECT_DE, chf

if TYPE_CHECKING:
    from market_sim.runner import RunState, SimulationRunner


class PatentOffice:
    """Grants, transfers and expires patents; blocks implementation by others."""

    def __init__(self, runner: SimulationRunner) -> None:
        self.cfg = runner.config.patents
        self.active: dict[tuple[str, str], dict] = {}
        self.history: list[dict] = []
        self.stats = {"patents_granted": 0, "patent_fees": 0.0}

    def fee(self, years: int, price_index: float) -> float:
        """Return the patent fee for a term of the given length."""
        return (self.cfg.base_fee + self.cfg.fee_per_year * years) * price_index

    def choose_years(self, firm, cash: float, price_index: float) -> int:
        """Choose a patent term: long archetypes and cash-rich firms patent longer."""
        if (
            firm.archetype in self.cfg.long_archetypes
            or cash >= self.cfg.rich_cash_multiple * self.fee(self.cfg.max_years, price_index)
        ):
            return self.cfg.max_years
        if firm.archetype in self.cfg.short_archetypes:
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

    def year_end(self, runner: SimulationRunner, state: RunState) -> None:
        """Expire patents at term end and lapse patents of bankrupt holders."""
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

    def report(self) -> list[dict]:
        """Return copies of all patents ever granted, in grant order."""
        copies = []
        for patent in self.history:
            copy = dict(patent)
            copy["prior_users"] = list(patent["prior_users"])
            copies.append(copy)
        return copies
