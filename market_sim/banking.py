"""Monetary policy; commercial banking can build on this module later."""

from market_sim.config import CentralBankConfig


class CentralBank:
    def __init__(self, config: CentralBankConfig) -> None:
        self.cfg = config
        self.policy_rate = config.start_rate
        self.inflation = 0.0
        self.output_gap = 0.0
        self.demand_multiplier = 1.0

    @property
    def inflation_adjustment(self) -> float:
        cfg = self.cfg
        return max(-cfg.inflation_effect_cap,
                   min(cfg.inflation_effect_cap, cfg.inflation_effect * self.output_gap))

    def year_end(self, inflation: float, demand: float, expected: float) -> bool:
        """Set next year's rate and lagged demand effect, without random draws."""
        cfg = self.cfg
        if not cfg.enabled:
            return False
        old_rate = self.policy_rate
        self.inflation = inflation
        gap = demand / expected - 1 if expected > 0 else 0.0
        gap = max(-cfg.gap_cap, min(cfg.gap_cap, gap))
        self.output_gap += cfg.gap_smoothing * (gap - self.output_gap)
        # Demand next year responds to the rate in force this year.
        effect = -cfg.demand_effect * (old_rate - inflation - cfg.neutral_real_rate)
        self.demand_multiplier = 1 + max(-cfg.demand_effect_cap, min(cfg.demand_effect_cap, effect))
        target = (cfg.neutral_real_rate + inflation
                  + cfg.inflation_weight * (inflation - cfg.target_inflation)
                  + cfg.gap_weight * self.output_gap)
        target = round(target / 0.0025) * 0.0025
        self.policy_rate = max(cfg.min_rate, min(cfg.max_rate,
                               max(old_rate - cfg.max_step, min(old_rate + cfg.max_step, target))))
        self.policy_rate = round(self.policy_rate, 12)
        return self.policy_rate != old_rate
