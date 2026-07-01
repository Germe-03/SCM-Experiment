# Walkthrough — wholesaler tier

The wholesaler sits between the retailer (downstream) and the
distributor (upstream). It does **not** see the end customer. Its
`incoming_order_qty` is whatever the retailer ordered two ticks
ago (orders have lead time too).

## What the wholesaler sees each tick

Same `LocalObservation` shape as every other tier:

| Field | Meaning at the wholesaler tier |
|---|---|
| `timestep` | Current period `t`. |
| `role` | Always `"wholesaler"` at this tier. |
| `inventory_on_hand` | Stock in the wholesaler's warehouse. |
| `backlog` | Unfulfilled retailer orders piled up. |
| `incoming_order_qty` | What the retailer ordered. **Noisy relative to true demand.** |
| `incoming_shipment_qty` | What the distributor just delivered. |
| `pipeline_inventory` | Units ordered from distributor, not yet arrived. |
| `order_history_window` | Recent retailer orders, up to 8 ticks back. |
| `shipment_history_window` | Recent distributor deliveries, up to 8 ticks back. |
| `costs_to_date` | Your holding + backlog cost so far. |

The wholesaler cannot see: the customer's demand, the retailer's
inventory, the distributor's inventory. Only its own local view.

## What the wholesaler decides

`AgentDecision(order_qty=<int>)` — how many units to order from
the distributor.

## The Mirror starting policy

```python
def step(self, observation, inbox, t):
    return AgentDecision(order_qty=observation.incoming_order_qty)
```

"Order exactly what the retailer just ordered." This is where the
bullwhip compounds: if the retailer already amplified noise, the
wholesaler now passes it upstream unchanged, which in turn makes
the distributor amplify even more.

## A concrete bad policy and why it fails on `s2.3`

```python
# BAD — "panic when order spikes"
if observation.incoming_order_qty > 8:
    return AgentDecision(order_qty=observation.incoming_order_qty * 2)
return AgentDecision(order_qty=observation.incoming_order_qty)
```

On `s2.3`, the retailer's orders jump when the customer-demand
step hits at `t=180`. This policy *doubles* the first big order
upstream, which the distributor then amplifies again, which
resolves 4+ ticks later as a massive shipment — just as demand
stabilises. Result: huge over-stock for the rest of the horizon,
`bullwhip_ratio` goes through the roof.

## A concrete improvement direction

**Smooth your orders across a bounded window.** The wholesaler is
one level removed from the true demand, so trust the average more
than any single tick:

```python
from collections import deque

class WholesalerAgent(Agent):
    def reset(self, *, role, config, seed):
        super().reset(role=role, config=config, seed=seed)
        self._window = deque(maxlen=8)

    def step(self, observation, inbox, t):
        self._window.append(observation.incoming_order_qty)
        avg = sum(self._window) / len(self._window)
        target = 20
        position = (observation.inventory_on_hand
                    + observation.pipeline_inventory
                    - observation.backlog)
        return AgentDecision(order_qty=max(0, int(avg) + max(0, target - position)))
```

To use memory like this, set `memory_mode: bounded_buffer` and
`memory_max_entries: 8` in `wholesaler/agent.yaml`.

## Tier-specific gotcha

The wholesaler's lead time from the distributor is the same as
the retailer's lead time from you. So the wholesaler has to
account for **double** the total pipeline that the retailer does:
retailer-to-you + you-to-distributor. The further from the
customer, the more pipeline to reason about.
