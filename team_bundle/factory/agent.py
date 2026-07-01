"""Factory agent — student-edited starter.

The factory is the most upstream tier — it has no upstream supplier.
Its `order_qty` represents production starts. There is no `inbox`
upstream of the factory.

Default behavior: produce exactly what the downstream tier asked for.
Replace the body of `step()` with your own decision rule.
"""

from __future__ import annotations

from typing import Any

from supplychainbench_v2.sdk import Agent, AgentDecision, LocalObservation, Message


class FactoryAgent(Agent):
    def reset(self, *, role: str, config: dict[str, Any], seed: int) -> None:
        super().reset(role=role, config=config, seed=seed)

    def step(
        self,
        observation: LocalObservation,
        inbox: list[Message],
        t: int,
    ) -> AgentDecision:
        return AgentDecision(order_qty=observation.incoming_order_qty)
