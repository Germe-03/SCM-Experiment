"""Firm data models and topology for the market supply network."""

from __future__ import annotations

from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


STAGES = ["retailer", "wholesaler", "distributor", "factory"]


class NetworkModel(BaseModel):
    """Base class that rejects unsupported network data fields."""

    model_config = ConfigDict(extra="forbid")


class Firm(NetworkModel):
    """Definition and initial economic state of one company."""

    id: str
    name: str
    stage: str
    archetype: str
    cash: float
    inventory: int
    backlog: int = 0
    sell_price: float
    quality_level: float
    reputation: float
    reliability: float
    capacity: int
    employees: int
    wage_level: float
    initial_wage_level: float | None = Field(default=None, ge=0, exclude=True)
    productivity_per_employee: float
    r_and_d_level: float
    r_and_d_budget: float
    initial_r_and_d_budget: float | None = Field(default=None, ge=0, exclude=True)
    supplier_priority: str
    suppliers: list[str] = Field(default_factory=list)
    overtime_level: float = 0.0
    machine_capacity: int = Field(default=0, ge=0)
    turnover_rate: float = 0.0
    # Phase 4: product category of a producer and whether it imports instead of brewing.
    category: str = "beer"
    importer: bool = False
    # Phase 5: home region, further sites and how the firm ships ("own" fleet or "service").
    region: str | None = None
    extra_regions: list[str] = Field(default_factory=list)
    transport_mode: str = "own"
    # Phase 10: "store" or "restaurant" (restaurants sit next to stores at the retail tier).
    channel: str = "store"
    # Phase 52: stable hidden behavioural disposition (an archetype key) that shapes the firm's
    # decisions; `archetype` is only the yearly classification of the observed behaviour.
    tendency: str = ""

    @property
    def behaviour(self) -> str:
        """Return the disposition that drives decisions (falls back to the archetype)."""
        return self.tendency or self.archetype

    @model_validator(mode="after")
    def _capture_initial_economic_anchors(self) -> Self:
        """P3 fix: retain immutable inputs for non-compounding annual policy."""
        if not self.tendency:
            self.tendency = self.archetype
        if self.initial_wage_level is None:
            self.initial_wage_level = self.wage_level
        if self.initial_r_and_d_budget is None:
            self.initial_r_and_d_budget = self.r_and_d_budget
        return self

    @field_validator("stage")
    @classmethod
    def _stage_must_be_known(cls, value: str) -> str:
        if value not in STAGES:
            raise ValueError(f"stage must be one of {STAGES} (got {value!r})")
        return value

    @field_validator(
        "quality_level", "reputation", "reliability", "r_and_d_level",
        "overtime_level", "turnover_rate",
    )
    @classmethod
    def _fraction_must_be_bounded(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("value must be within [0, 1]")
        return value


class Stage(NetworkModel):
    """A named supply-chain stage and its firms."""

    name: str
    firms: list[Firm]

    def firm(self, firm_id: str) -> Firm:
        """Return a firm in this stage by id."""

        for firm in self.firms:
            if firm.id == firm_id:
                return firm
        raise ValueError(f"unknown firm id {firm_id!r} in stage {self.name!r}")


class SupplyNetwork(NetworkModel):
    """Validated firms grouped into downstream-to-upstream stages."""

    stages: list[Stage]

    @model_validator(mode="after")
    def _validate_topology(self) -> Self:
        stage_names = [stage.name for stage in self.stages]
        if len(stage_names) != len(set(stage_names)):
            raise ValueError("stage names must be unique")
        unknown_stages = set(stage_names) - set(STAGES)
        if unknown_stages:
            raise ValueError(f"unknown network stages: {sorted(unknown_stages)}")
        missing_stages = set(STAGES) - set(stage_names)
        if missing_stages:
            raise ValueError(f"missing network stages: {sorted(missing_stages)}")

        firms = [firm for stage in self.stages for firm in stage.firms]
        ids = [firm.id for firm in firms]
        if len(ids) != len(set(ids)):
            raise ValueError("firm ids must be unique")
        firms_by_id = {firm.id: firm for firm in firms}

        for stage in self.stages:
            for firm in stage.firms:
                if firm.stage not in STAGES:
                    raise ValueError(
                        f"firm {firm.id!r} has unknown stage {firm.stage!r}"
                    )
                if firm.stage != stage.name:
                    raise ValueError(
                        f"firm {firm.id!r} is grouped under {stage.name!r}, "
                        f"but declares stage {firm.stage!r}"
                    )
                if firm.stage == STAGES[-1]:
                    if firm.suppliers:
                        raise ValueError(
                            f"factory {firm.id!r} must not have suppliers"
                        )
                    continue
                expected_stage = self.upstream_stage(firm.stage)
                for supplier_id in firm.suppliers:
                    supplier = firms_by_id.get(supplier_id)
                    if supplier is None:
                        raise ValueError(
                            f"firm {firm.id!r} references missing supplier "
                            f"{supplier_id!r}"
                        )
                    if supplier.stage != expected_stage:
                        raise ValueError(
                            f"supplier {supplier_id!r} for firm {firm.id!r} must "
                            f"be in stage {expected_stage!r}, not {supplier.stage!r}"
                        )
        return self

    def firms_in(self, stage: str) -> list[Firm]:
        """Return firms belonging to a named stage."""

        if stage not in STAGES:
            raise ValueError(f"unknown stage {stage!r}")
        for stage_group in self.stages:
            if stage_group.name == stage:
                return stage_group.firms
        raise ValueError(f"stage {stage!r} is not present in the network")

    def firm(self, firm_id: str) -> Firm:
        """Return a firm anywhere in the network by id."""

        for stage in self.stages:
            for firm in stage.firms:
                if firm.id == firm_id:
                    return firm
        raise ValueError(f"unknown firm id {firm_id!r}")

    def suppliers_of(self, firm_id: str) -> list[Firm]:
        """Resolve upstream candidates, optionally restricted by configured ids."""

        firm = self.firm(firm_id)
        upstream = self.upstream_stage(firm.stage)
        if upstream is None:
            return []
        allowed = set(firm.suppliers)
        return [
            supplier for supplier in self.firms_in(upstream)
            if not allowed or supplier.id in allowed
        ]

    def add_firm(self, firm: Firm) -> None:
        """Register a validated firm while preserving stage and id invariants."""

        if any(existing.id == firm.id for stage in self.stages for existing in stage.firms):
            raise ValueError(f"firm id {firm.id!r} already exists")
        candidate = SupplyNetwork(stages=[
            Stage(
                name=stage.name,
                firms=[*stage.firms, firm] if stage.name == firm.stage else list(stage.firms),
            )
            for stage in self.stages
        ])
        self.stages = candidate.stages

    @staticmethod
    def upstream_stage(stage: str) -> str | None:
        """Return the immediately upstream stage, if one exists."""

        if stage not in STAGES:
            raise ValueError(f"unknown stage {stage!r}")
        index = STAGES.index(stage)
        return STAGES[index + 1] if index < len(STAGES) - 1 else None

    @staticmethod
    def downstream_stage(stage: str) -> str | None:
        """Return the immediately downstream stage, if one exists."""

        if stage not in STAGES:
            raise ValueError(f"unknown stage {stage!r}")
        index = STAGES.index(stage)
        return STAGES[index - 1] if index > 0 else None


def load_firms(path: str | Path | None = None) -> SupplyNetwork:
    """Load firms from YAML and return a validated supply network."""

    config_path = (
        Path(path)
        if path is not None
        else Path(__file__).resolve().parent / "config" / "firms.yaml"
    )
    with config_path.open(encoding="utf-8") as config_file:
        data = yaml.safe_load(config_file)

    if not isinstance(data, dict) or not isinstance(data.get("firms"), list):
        raise ValueError(f"firm config must contain a 'firms' list: {config_path}")

    firms = [Firm.model_validate(item) for item in data["firms"]]
    stages = [
        Stage(name=stage, firms=[firm for firm in firms if firm.stage == stage])
        for stage in STAGES
    ]
    return SupplyNetwork(stages=stages)


def behaviour_of(firm) -> str:
    """Return the decision-driving disposition of a firm-like object (tendency, else archetype)."""
    return getattr(firm, "tendency", "") or firm.archetype
