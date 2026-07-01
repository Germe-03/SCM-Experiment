# Walkthrough — retailer tier

The retailer faces the customer directly. In the bench, "the
customer" is the scenario's demand function (stationary random
for `s1.1`, step-jump for `s2.3`). The retailer orders upstream
from the wholesaler every tick.

## What the retailer sees each tick

`observation` is a `LocalObservation` object. These are the fields
the retailer can legitimately read:

| Field | Meaning at the retailer tier |
|---|---|
| `timestep` | Current period `t` (0..364 on `s1.1`). |
| `role` | Always `"retailer"` at this tier. |
| `inventory_on_hand` | How much stock is currently in the store. |
| `backlog` | How much unfulfilled customer demand has piled up. |
| `incoming_order_qty` | Customer demand this tick. **This is the only view of the market.** |
| `incoming_shipment_qty` | What the wholesaler is delivering right now. |
| `pipeline_inventory` | Units already ordered but not yet arrived (in transit). |
| `order_history_window` | Recent customer demand, up to 8 ticks back. |
| `shipment_history_window` | Recent deliveries from upstream, up to 8 ticks back. |
| `costs_to_date` | Holding cost + backlog cost accumulated so far. |

The retailer cannot see: the wholesaler's inventory, the demand
function, future demand, any other tier's state.

## What the retailer decides

Exactly one thing each tick: `AgentDecision(order_qty=<int>)` —
how many units to order from the wholesaler right now.

Messages (`decision.messages`) are Phase 2 (S10-onwards) and
optional.

## The Mirror starting policy

```python
def step(self, observation, inbox, t):
    return AgentDecision(order_qty=observation.incoming_order_qty)
```

"Order exactly what the customer just asked for." This is the
textbook setup for the bullwhip effect: lead-time means your
order won't arrive until 2 ticks later, so if demand spikes you're
already behind, and if demand drops you're already over-ordered.

## A concrete bad policy and why it fails on `s1.1`

```python
# BAD — "buffer heavily"
return AgentDecision(order_qty=observation.incoming_order_qty * 3)
```

Inventory piles up. Holding cost dominates total cost. On `s1.1`
(iid uniform demand in [3, 7], mean 5), you accumulate ~10
units/tick of unwanted stock. Composite blows up (worse than 1.0)
because `total_cost` tanks.

## A concrete improvement direction

Track your **inventory position** — on-hand plus pipeline minus
backlog — and order to keep it near a **target** chosen once per
run, not per-tick:

```python
target = 15  # chosen from experimentation
position = (observation.inventory_on_hand
            + observation.pipeline_inventory
            - observation.backlog)
gap = max(0, target - position)
return AgentDecision(order_qty=gap)
```

This is a base-stock policy. It smooths your orders because when
pipeline fills up, the gap closes automatically. It is not the
optimum — it is a concrete starting point above Mirror.

For reference, the instructor's Base-Stock starter uses the same
shape plus a demand-driven target (reacts to rolling-average
demand). See `supplychainbench_v2.starters.base_stock` in the
package sources; **read it, do not import it from your bundle**.

## Tier-specific gotcha

The retailer is the **only** tier that sees actual customer
demand. If your upstream tiers (wholesaler, distributor, factory)
try to forecast demand from their inboxes, they are forecasting
**your orders**, not the customer's. That's the bullwhip — the
further you are from the customer, the noisier the signal looks.
Your retailer policy directly shapes every upstream tier's input.
