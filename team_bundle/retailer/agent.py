"""Retailer agent — student-edited starter.

This file is the *only* place you control the retailer's policy. The
harness instantiates `RetailerAgent` once per run and calls `step()`
once per simulated period.

Default behavior: order exactly what the customer asked for. This is
the canonical "Mirror" policy and it produces the textbook bullwhip.
Replace the body of `step()` with your own decision rule.
"""

from __future__ import annotations

from typing import Any

from supplychainbench_v2.sdk import Agent, AgentDecision, LocalObservation, Message


class RetailerAgent(Agent):
    def reset(self, *, role: str, config: dict[str, Any], seed: int) -> None:
        super().reset(role=role, config=config, seed=seed)

    def step(
        self,
        observation: LocalObservation,
        inbox: list[Message],
        t: int,
    ) -> AgentDecision:
        return AgentDecision(order_qty=observation.incoming_order_qty)
