"""Tests for the Post's carrier fleet management."""

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from market_sim.config import load_market_config
from market_sim.run import build_runner


@dataclass
class FakeTruckType:
    capacity: float


@dataclass
class FakeTruck:
    type: str
    age: int
    book_value: float
    purchase_price: float


class FakeTrucks:
    def __init__(self):
        self.types = {
            "klein": FakeTruckType(capacity=10),
            "gross": FakeTruckType(capacity=40),
        }
        self.fleets = {}
        self.carrier_owners = set()
        self.maintenance_calls = 0

    def buy_for_carrier(self, env, state, owner_id, type_name, pay):
        price = 100000 if type_name == "gross" else 40000
        pay(price=price)
        truck = FakeTruck(
            type=type_name,
            age=0,
            book_value=price,
            purchase_price=price,
        )
        self.fleets.setdefault(owner_id, []).append(truck)
        return truck

    def carrier_maintenance(self, env, state, owner_id, pay):
        self.maintenance_calls += 1
        return 1000 * len(self.fleets.get(owner_id, []))

    def annual_cost(self, env, type_name):
        return 20000

    def list_price(self, env, type_name):
        return 100000 if type_name == "gross" else 40000


def _config():
    config = load_market_config()
    carriers = config.carriers.model_copy(update={"enabled": True})
    trucks = config.trucks.model_copy(update={"enabled": False})
    return config.model_copy(update={"carriers": carriers, "trucks": trucks})


def _runner_and_state(year=1):
    runner, _ = build_runner(
        1,
        0,
        days_per_year=10,
        config=_config(),
    )
    runner.start()
    state = SimpleNamespace(year=year, events=[])
    return runner, state


def _set_demand(post, *, unit_km, days=10):
    post.unit_km = unit_km
    post.days = days


def test_post_buys_trucks_when_demand_exceeds_capacity():
    runner, state = _runner_and_state()
    trucks = FakeTrucks()
    runner.env.geography.trucks = trucks
    market = runner.env.geography.carriers

    demand = 40 * market.KM_PER_DAY * market.TARGET_UTILIZATION * 10 * 1.1
    _set_demand(market.post, unit_km=demand)

    market.year_end(runner, state)

    report = market.reports[-1]
    assert len(trucks.fleets["post"]) > 0
    assert "post" in trucks.carrier_owners
    assert report["trucks"] == len(trucks.fleets["post"])
    assert "truck_cost" in report


def test_existing_fleet_is_maintained_and_reduces_fixed_cost():
    runner, first_state = _runner_and_state()
    trucks = FakeTrucks()
    runner.env.geography.trucks = trucks
    market = runner.env.geography.carriers

    demand = 40 * market.KM_PER_DAY * market.TARGET_UTILIZATION * 10 * 1.1
    _set_demand(market.post, unit_km=demand)
    market.year_end(runner, first_state)

    fleet_size = len(trucks.fleets["post"])
    assert fleet_size > 0

    next_state = SimpleNamespace(year=2, events=[])
    _set_demand(market.post, unit_km=0, days=10)
    fixed_before = market.fixed_cost_year(runner)

    market.year_end(runner, next_state)

    report = market.reports[-1]
    maintenance = 1000 * fleet_size
    assert trucks.maintenance_calls == 1
    assert report["truck_cost"] >= maintenance
    assert report["fixed_cost"] == pytest.approx(
        fixed_before * (1 - market.VEHICLE_SHARE) + report["truck_cost"]
    )


def test_year_end_without_truck_market_keeps_old_fixed_cost():
    runner, state = _runner_and_state()
    runner.env.geography.trucks = None
    market = runner.env.geography.carriers
    _set_demand(market.post, unit_km=0)
    fixed_before = market.fixed_cost_year(runner)

    market.year_end(runner, state)

    report = market.reports[-1]
    assert report["trucks"] == 0
    assert report["truck_cost"] == 0.0
    assert report["fixed_cost"] == pytest.approx(fixed_before)


def test_zero_demand_does_not_buy_trucks_or_sell_existing_trucks():
    runner, state = _runner_and_state()
    trucks = FakeTrucks()
    existing = FakeTruck(
        type="klein",
        age=1,
        book_value=40000,
        purchase_price=40000,
    )
    trucks.fleets["post"] = [existing]
    runner.env.geography.trucks = trucks
    market = runner.env.geography.carriers
    _set_demand(market.post, unit_km=0)

    market.year_end(runner, state)

    assert trucks.fleets["post"] == [existing]
    assert market.reports[-1]["trucks"] == 1
