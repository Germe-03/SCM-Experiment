"""Truck capacity counts unit-km; partial fleets carry the base load, the rest goes with the Post."""

from market_sim.run import build_runner
from market_sim.trucks import Truck


def make():
    runner, _ = build_runner(years=3, days_per_year=10)
    state = runner.start()
    runner.run_year(state)
    carriers = runner.env.geography.carriers
    if carriers is not None and hasattr(carriers, "contracts"):
        carriers.contracts = {}  # no running transport contracts: the fleet decision is free
    return runner, state, runner.env.geography.trucks


def test_capacity_shrinks_with_distance():
    _, _, trucks = make()
    trucks.fleets["f"] = [Truck(id="a", type="klein", owner="f")]  # 25 units at 100 km = 2500 unit-km
    assert trucks.try_ship("f", 25, 100)
    trucks.used_today = {}
    assert not trucks.try_ship("f", 25, 200)
    assert trucks.try_ship("f", 12, 200)
    trucks.used_today = {}
    assert trucks.try_ship("f", 100, 1)  # below the minimum distance it still counts MIN_KM
    assert not trucks.try_ship("f", 150, 1)


def _firm(runner):
    return next(f for f in runner._firms() if f.stage == "factory")


def test_small_firm_with_long_hauls_buys_one_small_truck():
    runner, state, trucks = make()
    firm = _firm(runner)
    trucks.fleets[firm.id] = []
    runtime = runner.env.runtimes[firm.id]
    runtime.cash = 1e12
    days = trucks.days
    shipped = 20 * days  # 20 units per day
    km = 120.0           # 2400 unit-km per day: one small truck (2500) at 96 %
    service = shipped * km * 5.0
    own_variable = shipped * km * 0.5
    trucks.decide(runner, state, firm, shipped, own_variable, service, mean_km=km)
    assert [t.type for t in trucks.fleets[firm.id]] == ["klein"]
    assert firm.transport_mode == "own"


def test_short_hauls_do_not_justify_a_truck():
    runner, state, trucks = make()
    firm = _firm(runner)
    trucks.fleets[firm.id] = []
    runner.env.runtimes[firm.id].cash = 1e12
    shipped = 20 * trucks.days
    trucks.decide(runner, state, firm, shipped, shipped * 20 * 0.5, shipped * 20 * 5.0, mean_km=20.0)
    assert trucks.fleets[firm.id] == []


def test_partial_fleet_leaves_surplus_to_the_post():
    runner, state, trucks = make()
    firm = _firm(runner)
    trucks.fleets[firm.id] = []
    runner.env.runtimes[firm.id].cash = 1e12
    shipped = 50 * trucks.days  # 50 units/day x 100 km = 5000 unit-km
    trucks.decide(runner, state, firm, shipped, shipped * 100 * 0.5, shipped * 100 * 5.0, mean_km=100.0)
    cap = trucks.capacity(firm.id)
    assert 0 < cap <= 5000 / trucks.TARGET_UTILIZATION * 1.0 + 1e-9
    assert firm.transport_mode == "own"
    # Peak day: more than the fleet carries -> the surplus parcel goes with the Post.
    trucks.used_today = {}
    assert trucks.try_ship(firm.id, cap / 100, 100)
    assert not trucks.try_ship(firm.id, 10, 100)


def test_remove_and_take_back_leased():
    runner, state, trucks = make()
    env = runner.env
    firm = _firm(runner)
    dealer = next(iter(trucks.dealers.values()))
    dealer.sold_prev_new = 10
    truck = Truck(id="L1", type="klein", age=2, owner=firm.id, leased=True)
    trucks.fleets[firm.id] = [truck]
    assert trucks.take_back_leased(env, state, truck, dealer.id)
    assert trucks.last_takeback_price > 0 and not truck.leased
    assert truck in dealer.stock_used and trucks.fleets[firm.id] == []
    other = Truck(id="X", type="klein", owner=firm.id)
    trucks.fleets[firm.id] = [other]
    assert trucks.remove_truck(firm.id, "X") is other
    assert trucks.remove_truck(firm.id, "X") is None
