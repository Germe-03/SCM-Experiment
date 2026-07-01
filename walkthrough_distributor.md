# Walkthrough — distributor tier

The distributor sits between the wholesaler (downstream) and the
factory (upstream). Two tiers removed from the customer. Its
`incoming_order_qty` is whatever the wholesaler ordered two ticks
ago — already twice-filtered noise relative to true demand.

## What the distributor sees each tick

| Field | Meaning at the distributor tier |
|---|---|
| `timestep` | Current period `t`. |
| `role` | Always `"distributor"` at this tier. |
| `inventory_on_hand` | Stock in your depot. |
| `backlog` | Unfulfilled wholesaler orders piled up. |
| `incoming_order_qty` | What the wholesaler just ordered. |
| `incoming_shipment_qty` | What the factory is delivering to you now. |
| `pipeline_inventory` | Units ordered from factory, not yet arrived. |
| `order_history_window` | Recent wholesaler orders, up to 8 ticks back. |
| `shipment_history_window` | Recent factory deliveries, up to 8 ticks back. |
| `costs_to_date` | Your cumulative holding + backlog cost. |

## What the distributor decides

`AgentDecision(order_qty=<int>)` — units to order from the factory.

## The Mirror starting policy

```python
def step(self, observation, inbox, t):
    return AgentDecision(order_qty=observation.incoming_order_qty)
```

## A concrete bad policy and why it fails

```python
# BAD — "react to last week's delivery"
return AgentDecision(order_qty=max(0, 15 - observation.incoming_shipment_qty))
```

This ties your ordering rule to a noisy single-tick upstream
signal. When the factory happens to deliver 0 one tick and 10 the
next (normal), your orders swing wildly. Factory lead time is the
longest in the chain — every swing propagates for 3–4 ticks.

## A concrete improvement direction

The distributor is the tier where **smoothing pays the most**,
because every swing it creates takes the longest to settle. A
simple tactic: cap the rate at which you change orders from tick
to tick.

```python
from collections import deque

class DistributorAgent(Agent):
    def reset(self, *, role, config, seed):
        super().reset(role=role, config=config, seed=seed)
        self._last_order = 5

    def step(self, observation, inbox, t):
        target_position = 25
        position = (observation.inventory_on_hand
                    + observation.pipeline_inventory
                    - observation.backlog)
        raw = max(0, target_position - position)
        # Smooth: never change by more than ±3 units/tick.
        capped = max(self._last_order - 3, min(self._last_order + 3, raw))
        self._last_order = capped
        return AgentDecision(order_qty=capped)
```

The `self._last_order` state makes this tier stateful. Set
`memory_mode: bounded_buffer` and `memory_max_entries: 1` in
`distributor/agent.yaml`.

## Tier-specific gotcha

The distributor is where forecasting breaks down. Your
`incoming_order_qty` stream is the wholesaler's orders, which is
already a filtered view of the retailer's orders, which is
already a filtered view of the customer. Trying to infer
customer-level seasonality from this signal is a losing game at
this tier. Prefer **stability** over **accuracy**: a smooth
wrong-ish order is usually cheaper than a reactive right-ish order.
