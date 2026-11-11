"""Phase 53: truck fleets, used-truck trade and dealers."""

from market_sim.run import build_runner
from market_sim.trucks import Truck


def make():
    runner, _ = build_runner(years=3, days_per_year=10)
    state = runner.start()
    return runner, state, runner.env.geography.trucks


def test_everyone_starts_with_the_post_and_a_dealer_exists():
    runner, state, trucks = make()
    assert trucks is not None
    assert all(f.transport_mode == "service" for f in runner._firms() if f.stage != "retailer")
    assert len(trucks.dealers) == trucks.DEALER_MIN_ACTIVE


def test_price_and_value_decline_with_age():
    runner, state, trucks = make()
    env = runner.env
    new = Truck(id="x", type="mittel")
    old = Truck(id="y", type="mittel", age=8)
    assert trucks.value(env, new) == trucks.list_price(env, "mittel")
    assert trucks.value(env, old) < trucks.value(env, new)
    assert trucks.list_price(env, "klein") < trucks.list_price(env, "gross")


def test_buy_and_occasion_limit():
    runner, state, trucks = make()
    env = runner.env
    runner.run_year(state)
    firm = next(f for f in runner._firms() if f.stage == "factory")
    dealer = next(iter(trucks.dealers.values()))
    trucks._restock(env)
    assert dealer.stock_total() > 0
    fleet = trucks.fleets.setdefault(firm.id, [])
    for i in range(3):
        fleet.append(Truck(id=f"o{i}", type="klein", age=9, owner=firm.id, book_value=1.0, purchase_price=1.0))
    dealer.sold_prev_new = 10
    sold = [trucks._sell_to_dealer(env, state, firm, t) for t in list(fleet)]
    assert sum(sold) == 2
    assert dealer.taken_back_year == 2
    dealer.sold_prev_new = 0
    dealer.taken_back_year = 0
    extra = Truck(id="o9", type="klein", age=9, owner=firm.id, book_value=1.0, purchase_price=1.0)
    trucks.fleets[firm.id].append(extra)
    assert not trucks._sell_to_dealer(env, state, firm, extra)


def test_end_of_life_is_scrapped_with_disposal_cost():
    runner, state, trucks = make()
    runner.run_year(state)
    firm = next(f for f in runner._firms() if f.stage == "factory")
    trucks.fleets[firm.id] = [Truck(id="z", type="klein", age=50, owner=firm.id)]
    trucks.begin_year_end(runner, state)
    assert trucks.fleets[firm.id] == []
    assert trucks.disposals and trucks.disposals[-1]["cost"] > 0
    assert trucks.pending[firm.id][0] > 0
    assert any(e["event"] == "truck_scrapped" for e in state.events)


def test_capacity_limits_own_shipping_and_export():
    runner, state, trucks = make()
    trucks.fleets["f"] = [Truck(id="a", type="klein", owner="f")]
    assert trucks.try_ship("f", 20)
    assert not trucks.try_ship("f", 10)
    assert trucks.export()["enabled"]
