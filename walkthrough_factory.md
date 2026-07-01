# Walkthrough — factory tier

The factory is the most upstream tier. It has **no supplier**: its
`order_qty` represents units to **start producing**, not units to
request. Production lead time is the same as shipping lead time
(2 ticks), so an order placed now becomes finished goods in 2
ticks and ships downstream in the following tick.

## What the factory sees each tick

| Field | Meaning at the factory tier |
|---|---|
| `timestep` | Current period `t`. |
| `role` | Always `"factory"` at this tier. |
| `inventory_on_hand` | Finished goods ready to ship. |
| `backlog` | Unfulfilled distributor orders. |
| `incoming_order_qty` | What the distributor just ordered. |
| `incoming_shipment_qty` | Units that just came off the production line. |
| `pipeline_inventory` | Production started but not yet finished. |
| `order_history_window` | Recent distributor orders, up to 8 ticks back. |
| `shipment_history_window` | Recent production finishes, up to 8 ticks back. |
| `costs_to_date` | Your cumulative holding + backlog cost. |

## What the factory decides

`AgentDecision(order_qty=<int>)` — units to **start producing**
this tick. There is no upstream inbox to worry about (no agent
sends messages to the factory).

## The Mirror starting policy

```python
def step(self, observation, inbox, t):
    return AgentDecision(order_qty=observation.incoming_order_qty)
```

"Produce exactly what the distributor just ordered."

## A concrete bad policy and why it fails

```python
# BAD — "always run the line at capacity"
return AgentDecision(order_qty=20)
```

Factory has no cap on production but **does pay holding cost** on
the finished goods. Running flat-out is a strict loss on `s1.1`
(mean demand is 5) — you produce 15 extra units every tick and
they sit in inventory forever. `total_cost` explodes, composite
collapses.

## A concrete improvement direction

The factory should ride the **pipeline** hardest. Your
`pipeline_inventory` includes in-production units already on the
line — you don't need to re-order them. A target-pipeline policy:

```python
class FactoryAgent(Agent):
    def step(self, observation, inbox, t):
        # Keep ~10 units worth of finished goods on hand, and ~8
        # units in production, minus what's already backordered.
        target_position = 18
        position = (observation.inventory_on_hand
                    + observation.pipeline_inventory
                    - observation.backlog)
        return AgentDecision(order_qty=max(0, target_position - position))
```

No memory needed; this is stateless. `memory_mode: stateless` in
`factory/agent.yaml`.

## Tier-specific gotcha

The factory is the tier that **pays for the entire upstream
bullwhip**. Every swing that wholesaler and distributor add
lands on your order book. A factory that reacts one-for-one to
distributor orders will over-produce and under-produce on the same
cycle, burning holding cost on the "up" swings and backlog cost
on the "down" swings.

**One piece of classic advice**: on `s2.3` (step demand up at
`t=180`), a well-tuned factory sees the distributor's order-rate
rise **before** its own inventory runs out (because of the chain
of lead times). The factory that pre-builds a small buffer at
`t=175..180` costs very little; the factory that waits for
backlog to start accumulating before ramping up pays heavily.

For reference, the instructor's Base-Stock starter uses an
on-hand + pipeline target with demand-driven updating. Read it at
`supplychainbench_v2.starters.base_stock` in the installed
package; **do not import it into your bundle**.
