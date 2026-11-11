"""Workshop, service contracts, used trucks and the carrier interface of the truck market."""

import pytest

from market_sim.run import build_runner
from market_sim.trucks import Truck


def make():
    runner, _ = build_runner(years=3, days_per_year=10)
    state = runner.start()
    return runner, state, runner.env.geography.trucks


def test_repair_pays_dealer_workshop():
    runner, state, trucks = make()
    runner.run_year(state)
    firm = next(f for f in runner._firms() if f.stage == "factory")
    truck = Truck(
        id="w1", type="klein", age=5, owner=firm.id, purchase_price=1, book_value=1
    )
    trucks.fleets.setdefault(firm.id, []).append(truck)
    dealer = next(iter(trucks.dealers.values()))
    trucks._assign_service(truck, dealer)

    trucks._book_workshop(dealer, firm.id, "reparatur", 1000.0)

    assert dealer.revenue_workshop == pytest.approx(1000.0)
    assert dealer.pending["wcogs"] >= 1000.0 / (1 + trucks.WORKSHOP_MARGIN) - 1e-6
    assert dealer.pending["revenue"] >= 1000.0
    assert dealer.pending["wcogs"] > 0

    trucks.finish_year_end(runner, state)

    assert any(
        row["dealer"] == dealer.id
        and row["firm"] == firm.id
        and row["kind"] == "reparatur"
        and row["amount"] == 1000.0
        for row in trucks.workshop
    )
    dealer_rows = [row for row in trucks.dealer_history if row["dealer"] == dealer.id]
    assert dealer_rows
    assert any(row["revenue_workshop"] >= 1000.0 for row in dealer_rows)


def test_maintenance_goes_to_service_dealer_daily():
    runner, state, trucks = make()
    firm = next(f for f in runner._firms() if f.stage == "factory")
    dealer = next(iter(trucks.dealers.values()))
    truck = Truck(id="m1", type="klein", owner=firm.id, maint_daily=10.0)
    trucks.fleets.setdefault(firm.id, []).append(truck)
    trucks._assign_service(truck, dealer)

    trucks.daily(runner.env)

    assert dealer.revenue_workshop == pytest.approx(10.0)
    assert any(
        key[1] == dealer.id and key[2] == firm.id and key[3] == "wartung"
        for key in trucks._ws_acc
    )


def test_service_contract_binds_five_years():
    runner, state, trucks = make()
    d1, d2 = [trucks.dealers[key] for key in sorted(trucks.dealers)[:2]]
    d1.margin = 0.2
    d2.margin = 0.1
    truck = Truck(id="c1", type="klein")
    trucks._year = 3
    trucks._assign_service(truck, d1)

    assert truck.service_until == 3 + trucks.SERVICE_YEARS
    trucks._refresh_free_choice()
    assert trucks.service_dealer_for(truck) is d1

    trucks._year = truck.service_until + 1
    trucks._refresh_free_choice()
    assert trucks.service_dealer_for(truck) is d2


def test_inactive_dealer_frees_the_choice():
    runner, state, trucks = make()
    d1 = trucks.dealers[sorted(trucks.dealers)[0]]
    truck = Truck(id="c2", type="klein")
    trucks._assign_service(truck, d1)
    for dealer in trucks.dealers.values():
        dealer.margin = 0.1
    d1.active = False
    trucks._refresh_free_choice()

    remaining = [dealer for dealer in trucks.dealers.values() if dealer.active]
    expected = min(remaining, key=lambda dealer: (dealer.margin, dealer.id))
    assert trucks.service_dealer_for(truck) is expected


def test_buy_for_carrier():
    runner, state, trucks = make()
    carrier_id = "post_test"
    paid = []
    bills = []
    runner.run_year(state)
    trucks._restock(runner.env)

    truck = trucks.buy_for_carrier(
        runner.env, state, carrier_id, "mittel", paid.append
    )

    assert truck is not None
    assert len(paid) == 1
    assert paid[0] > 0
    assert truck in trucks.fleets[carrier_id]
    assert truck.owner == carrier_id
    assert carrier_id in trucks.carrier_owners
    assert truck.service_dealer in trucks.dealers
    assert truck.service_until > 0
    assert trucks.capacity(carrier_id) > 0
    assert trucks.try_ship(carrier_id, 1.0) is True

    trucks.begin_year_end(runner, state)
    assert carrier_id in trucks.fleets

    total = trucks.carrier_maintenance(
        runner.env, state, carrier_id, bills.append
    )
    assert total > 0
    assert total == pytest.approx(sum(bills))


def test_used_truck_is_sold():
    runner, state, trucks = make()
    runner.run_year(state)
    trucks._restock(runner.env)
    dealer = trucks.dealers[sorted(trucks.dealers)[0]]
    life = trucks.types["klein"].life_years
    truck = Truck(
        id="u1",
        type="klein",
        age=int(0.7 * life),
        owner=dealer.id,
        cost_basis=1000.0,
    )
    trucks._to_stock(truck)
    for other in trucks.dealers.values():
        other.stock_new["klein"] = []
        other.stock_used = [
            used for used in other.stock_used if used.type != "klein"
        ]
    dealer.stock_used.append(truck)

    offer = trucks._best_offer(runner.env, "klein", prefer_used=True)
    assert offer is not None
    assert offer[4] is True
    assert offer[5] is truck
    assert trucks._best_offer(runner.env, "klein") is None

    bought = trucks.buy_for_carrier(
        runner.env, state, "kurier_test", "klein", lambda price: None
    )
    assert bought is truck
    assert truck.bought_used is True
    assert dealer.sold_used_year == 1
    assert dealer.revenue_used > 0


def test_old_stock_is_scrapped():
    runner, state, trucks = make()
    dealer = trucks.dealers[sorted(trucks.dealers)[0]]
    truck = Truck(
        id="s1", type="klein", owner=dealer.id, cost_basis=500.0, stock_since=1
    )
    dealer.stock_used.append(truck)
    state.year = 1 + trucks.STOCK_MAX_YEARS + 1

    trucks.finish_year_end(runner, state)

    assert all(
        truck not in other.stock_used for other in trucks.dealers.values()
    )


def test_fleet_history_has_kind():
    runner, state, trucks = make()
    carrier_id = "post_test"
    runner.run_year(state)
    trucks._restock(runner.env)
    truck = trucks.buy_for_carrier(
        runner.env, state, carrier_id, "mittel", lambda price: None
    )
    assert truck is not None

    firm = next(f for f in runner._firms() if f.stage == "factory")
    firm_truck = Truck(id="f1", type="klein", owner=firm.id)
    trucks.fleets.setdefault(firm.id, []).append(firm_truck)

    trucks.finish_year_end(runner, state)

    assert all(row["kind"] in {"carrier", "firm"} for row in trucks.fleet_history)
    assert any(
        row["firm"] == carrier_id and row["kind"] == "carrier"
        for row in trucks.fleet_history
    )
    assert isinstance(trucks.export()["workshop"], list)
    required = {
        "revenue_new",
        "revenue_used",
        "revenue_workshop",
        "workshop_jobs",
        "service_contracts",
    }
    assert all(required.issubset(row) for row in trucks.dealer_history)
